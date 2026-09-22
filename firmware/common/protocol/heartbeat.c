/**
 * @file heartbeat.c
 * @brief Cadencement et construction de la trame d'état périodique.
 */

#include "protocol/heartbeat.h"

#include <string.h>

void bench_heartbeat_init(bench_heartbeat_sched_t *hb, uint16_t period_ms) {
    memset(hb, 0, sizeof(*hb));
    hb->period_ms = period_ms;
}

void bench_heartbeat_set_period(bench_heartbeat_sched_t *hb, uint16_t period_ms) {
    if (period_ms != 0u) {
        hb->period_ms = period_ms;
    }
}

void bench_heartbeat_suspend(bench_heartbeat_sched_t *hb, bool suspended) {
    hb->suspended = suspended;
}

bool bench_heartbeat_due(bench_heartbeat_sched_t *hb, uint32_t now_ms) {
    if (hb->suspended || hb->period_ms == 0u) {
        /* On repousse l'échéance pendant la suspension : à la reprise, le nœud
         * n'émet pas d'un coup tous les heartbeats qu'il « doit ». */
        hb->next_due_ms = now_ms + hb->period_ms;
        hb->started = true;
        return false;
    }

    /* Première échéance : elle est posée à partir de l'instant courant, quelle
     * que soit la valeur du compteur au démarrage. */
    if (!hb->started) {
        hb->started = true;
        hb->next_due_ms = now_ms + hb->period_ms;
        return true;
    }

    /* Comparaison par différence signée : insensible au rebouclage du compteur
     * de millisecondes au bout de 49 jours. */
    if ((int32_t)(now_ms - hb->next_due_ms) < 0) {
        return false;
    }

    hb->next_due_ms = now_ms + hb->period_ms;
    return true;
}

uint16_t bench_heartbeat_id(uint8_t node_id) {
    return (uint16_t)(BENCH_HEARTBEAT_BASE + node_id);
}

void bench_heartbeat_pack_frame(const bench_heartbeat_inputs_t *inputs,
                                const bench_can_status_t *status, const bench_ring_t *ring,
                                uint8_t *data) {
    bench_heartbeat_t frame;
    memset(&frame, 0, sizeof(frame));

    frame.ctrl_state = (uint8_t)status->state;
    frame.last_error_code = status->last_error_code;
    frame.clock_not_qualified = inputs->clock_not_qualified ? 1u : 0u;
    frame.fault_mode_active = inputs->fault_mode_active ? 1u : 0u;
    frame.silent_mode = inputs->silent_mode ? 1u : 0u;
    frame.tec = status->tec;
    frame.rec = status->rec;
    frame.current_mode = inputs->current_mode;
    /* Les quatre compteurs saturent a 255 : ils servent a dire « ce n'est pas
     * nul », pas a mesurer finement. Toute valeur non nulle invalide la mesure. */
    frame.rx_fifo_lost = (status->rx_fifo_lost > 255u) ? 255u
                                                       : (uint8_t)status->rx_fifo_lost;
    const uint16_t dropped = bench_ring_dropped(ring);
    frame.ring_overflow = (dropped > 255u) ? 255u : (uint8_t)dropped;
    frame.non_classic_rx = status->non_classic_rx;
    frame.ext_id_rx = status->ext_id_rx;

    bench_heartbeat_pack(data, &frame);
}
