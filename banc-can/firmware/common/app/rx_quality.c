/**
 * @file rx_quality.c
 * @brief Note de qualité des trames reçues.
 */

#include "app/rx_quality.h"

#include <string.h>

/** Période de heartbeat par défaut, identique à celle de bench_node_init(). */
#define RXQ_HEARTBEAT_DEFAULT_MS 500u

/**
 * Au-delà de ce nombre de périodes de silence, une trame marque une reprise :
 * l'émetteur a redémarré ou a été débranché, la référence est reprise à neuf.
 */
#define RXQ_RESUME_PERIODS 20u

/** Tolérance de ponctualité : max(2 ms, 10 % de la période). */
static uint32_t tolerance_us(uint32_t period_us) {
    const uint32_t ten_pct = period_us / 10u;
    return (ten_pct > 2000u) ? ten_pct : 2000u;
}

static void sat_add(uint8_t *acc, uint32_t n) {
    const uint32_t v = (uint32_t)*acc + n;
    *acc = (v > 255u) ? 255u : (uint8_t)v;
}

/**
 * Pénalité de ponctualité pour un intervalle @p dt_us, quand @p periods périodes
 * de @p period_us étaient attendues. Gratuit dans la tolérance, puis linéaire
 * jusqu'à 30 points pour un écart d'une demi-période au-delà.
 */
static int timing_penalty(bench_rxq_t *q, uint32_t dt_us, uint32_t period_us, uint32_t periods) {
    const uint32_t expected = period_us * periods;
    const uint32_t dev = (dt_us > expected) ? (dt_us - expected) : (expected - dt_us);
    const uint32_t tol = tolerance_us(period_us);
    if (dev <= tol) {
        return 0;
    }
    sat_add(&q->late, 1u);
    q->total_late++;
    const uint32_t over = dev - tol;
    const uint32_t half = period_us / 2u;
    return (over >= half) ? 30 : (int)((over * 30u) / half);
}

static uint8_t finish(bench_rxq_t *q, bench_rxq_source_t *s, int score, uint32_t now_us) {
    if (score < 0) {
        score = 0;
    }
    s->seen = true;
    s->last_us = now_us;
    s->sum += (uint32_t)score;
    s->count++;
    s->last_score = (uint8_t)score;
    q->total_frames++;
    return (uint8_t)score;
}

/** Ponctualité jugée sur cette trame ? Consomme un éventuel sursis d'arbitrage. */
static bool judge_timing(bench_rxq_source_t *s) {
    const bool ok = s->timing_ref && s->skip_timing == 0u;
    if (s->skip_timing > 0u) {
        s->skip_timing--;
    }
    s->timing_ref = (s->skip_timing == 0u);
    return ok;
}

static uint8_t score_app(bench_rxq_t *q, uint8_t kind, const bench_can_frame_t *f) {
    const bench_traffic_desc_t *d = bench_traffic_desc(kind);
    bench_rxq_source_t *s = &q->app[kind];
    int score = 100;

    if (f->dlc != d->dlc || !bench_traffic_checksum_ok(kind, f->data)) {
        sat_add(&q->bad, 1u);
        q->total_bad++;
        (void)judge_timing(s);
        return finish(q, s, 0, f->timestamp_us);
    }

    /* Silence trop long : l'émetteur a redémarré (compteur et séquence repartis
     * de zéro) ou a été débranché. La trame est jugée comme une première trame,
     * sans compter jusqu'à 254 trames « perdues » sur un simple saut de compteur
     * (vu sur le banc le 24/11/2026 : P gonflé à chaque reset d'un voisin). */
    const uint32_t period_us = (uint32_t)d->period_ms * 1000u;
    const bool seen =
        s->seen && (f->timestamp_us - s->last_us) <= RXQ_RESUME_PERIODS * period_us;

    const uint8_t mask = (uint8_t)((1u << d->counter_bits) - 1u);
    const uint8_t counter = (uint8_t)(bench_traffic_counter(kind, f->data) & mask);
    uint32_t lost = 0u;
    bool bad = false;
    if (seen) {
        const uint8_t diff = (uint8_t)((uint8_t)(counter - s->last_counter) & mask);
        if (diff == 0u) {
            score -= 50;
            bad = true;
        } else {
            lost = (uint32_t)diff - 1u;
        }
    }
    if (lost > 0u) {
        score -= (lost >= 3u) ? 60 : (int)(20u * lost);
        sat_add(&q->lost, lost);
        q->total_lost += lost;
    }

    if (!bench_traffic_sensor_present(kind, f->data)) {
        const int step = bench_traffic_match_step(kind, f->data);
        if (step < 0) {
            score -= 40;
            bad = true;
        } else {
            if (seen && s->last_step >= 0) {
                const uint32_t expected = ((uint32_t)s->last_step + 1u + lost) % d->steps;
                if ((uint32_t)step != expected) {
                    score -= 20;
                    bad = true;
                }
            }
            s->last_step = (int8_t)step;
        }
    }
    if (bad) {
        sat_add(&q->bad, 1u);
        q->total_bad++;
    }

    const bool timed = judge_timing(s);
    if (timed && seen) {
        score -= timing_penalty(q, f->timestamp_us - s->last_us, period_us, lost + 1u);
    }
    s->last_counter = counter;
    return finish(q, s, score, f->timestamp_us);
}

static uint8_t score_heartbeat(bench_rxq_t *q, uint8_t index, const bench_can_frame_t *f) {
    bench_rxq_source_t *s = &q->hb[index];
    int score = 100;

    if (f->dlc != 8u) {
        sat_add(&q->bad, 1u);
        q->total_bad++;
        (void)judge_timing(s);
        return finish(q, s, 0, f->timestamp_us);
    }

    const bool timed = judge_timing(s);
    if (timed && s->seen) {
        const uint32_t period_us = (uint32_t)q->hb_period_ms[index] * 1000u;
        const uint32_t dt = f->timestamp_us - s->last_us;
        /* Périodes écoulées, arrondies : 3 périodes = 2 heartbeats manqués. */
        uint32_t periods = (dt + period_us / 2u) / period_us;
        if (periods == 0u) {
            periods = 1u;
        }
        if (periods > RXQ_RESUME_PERIODS) {
            /* Silence trop long : nœud redémarré ou débranché. On reprend une
             * référence sans compter des centaines de trames « perdues ». */
            return finish(q, s, score, f->timestamp_us);
        }
        const uint32_t lost = periods - 1u;
        if (lost > 0u) {
            score -= (lost >= 3u) ? 60 : (int)(20u * lost);
            sat_add(&q->lost, lost);
            q->total_lost += lost;
        }
        score -= timing_penalty(q, dt, period_us, periods);
    }
    return finish(q, s, score, f->timestamp_us);
}

void bench_rxq_init(bench_rxq_t *q, uint8_t node_id) {
    memset(q, 0, sizeof(*q));
    q->node_id = node_id;
    for (uint8_t i = 0u; i < BENCH_TRAFFIC_KINDS; i++) {
        q->app[i].last_step = -1;
        q->last.score[i] = BENCH_RXQ_NONE;
    }
    for (uint8_t i = 0u; i < BENCH_NODE_COUNT; i++) {
        q->hb[i].last_step = -1;
        q->hb_period_ms[i] = RXQ_HEARTBEAT_DEFAULT_MS;
    }
    q->last.score_heartbeat = BENCH_RXQ_NONE;
}

uint8_t bench_rxq_on_frame(bench_rxq_t *q, const bench_can_frame_t *frame) {
    if ((frame->flags & BENCH_FRAME_OWN_TX) != 0u) {
        return BENCH_RXQ_NONE;
    }
    const int kind = bench_traffic_kind_of(frame->id);
    if (kind >= 0) {
        return score_app(q, (uint8_t)kind, frame);
    }
    if (frame->id > BENCH_HEARTBEAT_BASE && frame->id <= BENCH_HEARTBEAT_BASE + BENCH_NODE_COUNT) {
        const uint8_t node = (uint8_t)(frame->id - BENCH_HEARTBEAT_BASE);
        if (node != q->node_id) {
            return score_heartbeat(q, (uint8_t)(node - 1u), frame);
        }
    }
    return BENCH_RXQ_NONE;
}

void bench_rxq_on_arm(bench_rxq_t *q) {
    /* L'émission périodique et le heartbeat s'interrompent pendant le cycle : la
     * trame contendante puis la reprise ne sont pas jugées sur leur ponctualité. */
    for (uint8_t i = 0u; i < BENCH_TRAFFIC_KINDS; i++) {
        q->app[i].skip_timing = 2u;
        q->app[i].timing_ref = false;
    }
    for (uint8_t i = 0u; i < BENCH_NODE_COUNT; i++) {
        q->hb[i].skip_timing = 1u;
        q->hb[i].timing_ref = false;
    }
}

void bench_rxq_on_cfg(bench_rxq_t *q, const uint8_t *data) {
    bench_bench_cfg_t cfg;
    bench_bench_cfg_unpack(&cfg, data);
    if (cfg.heartbeat_period_ms == 0u) {
        return;
    }
    for (uint8_t i = 0u; i < BENCH_NODE_COUNT; i++) {
        if (cfg.target_node == 0u || cfg.target_node == i + 1u) {
            q->hb_period_ms[i] = cfg.heartbeat_period_ms;
            q->hb[i].timing_ref = false;  /* nouvelle cadence : nouvelle référence */
        }
    }
}

static uint8_t mean(uint32_t sum, uint32_t count) {
    return (count == 0u) ? BENCH_RXQ_NONE : (uint8_t)((sum + count / 2u) / count);
}

void bench_rxq_report(bench_rxq_t *q, uint8_t *out) {
    bench_rxq_window_t w;
    for (uint8_t i = 0u; i < BENCH_TRAFFIC_KINDS; i++) {
        w.score[i] = mean(q->app[i].sum, q->app[i].count);
        q->app[i].sum = 0u;
        q->app[i].count = 0u;
    }
    uint32_t sum = 0u;
    uint32_t count = 0u;
    for (uint8_t i = 0u; i < BENCH_NODE_COUNT; i++) {
        sum += q->hb[i].sum;
        count += q->hb[i].count;
        q->hb[i].sum = 0u;
        q->hb[i].count = 0u;
    }
    w.score_heartbeat = mean(sum, count);
    w.lost = q->lost;
    w.bad = q->bad;
    w.late = q->late;
    q->lost = q->bad = q->late = 0u;
    q->last = w;

    bench_quality_t f;
    f.score_energy_command = w.score[0];
    f.score_imu_speed = w.score[1];
    f.score_temp_battery = w.score[2];
    f.score_heartbeat = w.score_heartbeat;
    f.frames_lost = w.lost;
    f.frames_bad = w.bad;
    f.frames_late = w.late;
    f.report_counter = q->report_counter++;
    bench_quality_pack(out, &f);
}
