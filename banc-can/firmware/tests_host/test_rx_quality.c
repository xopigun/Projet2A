/**
 * @file test_rx_quality.c
 * @brief Tests de la note de qualité donnée par le récepteur à chaque trame.
 */

#include "app/rx_quality.h"
#include "app/traffic.h"
#include "bench_test.h"
#include "icd_gen.h"

#define MS 1000u

/** Trame applicative du pas @p step, compteur @p counter, reçue à @p t_us. */
static bench_can_frame_t app_frame(uint8_t kind, uint8_t step, uint8_t counter, uint32_t t_us) {
    bench_can_frame_t f = {0};
    f.id = bench_traffic_desc(kind)->can_id;
    f.dlc = 8u;
    f.timestamp_us = t_us;
    bench_traffic_build(kind, step, counter, f.data);
    return f;
}

static bench_can_frame_t heartbeat(uint8_t node, uint32_t t_us) {
    bench_can_frame_t f = {0};
    f.id = (uint16_t)(BENCH_HEARTBEAT_BASE + node);
    f.dlc = 8u;
    f.timestamp_us = t_us;
    return f;
}

/** Envoie @p n trames parfaites de ENERGY_COMMAND à 20 ms à partir du pas 0. */
static void perfect_energy(bench_rxq_t *q, uint8_t n) {
    for (uint8_t i = 0u; i < n; i++) {
        bench_can_frame_t f = app_frame(0u, (uint8_t)(i % 5u), i, (uint32_t)i * 20u * MS);
        BENCH_ASSERT_EQ_UINT(100u, bench_rxq_on_frame(q, &f));
    }
}

BENCH_TEST(flux_parfait_note_100) {
    bench_rxq_t q;
    bench_rxq_init(&q, 4u);
    perfect_energy(&q, 25u);
    uint8_t out[8];
    bench_rxq_report(&q, out);
    bench_quality_t r;
    bench_quality_unpack(&r, out);
    BENCH_ASSERT_EQ_UINT(100u, r.score_energy_command);
    BENCH_ASSERT_EQ_UINT(BENCH_RXQ_NONE, r.score_imu_speed);  /* rien reçu */
    BENCH_ASSERT_EQ_UINT(0u, r.frames_lost);
    BENCH_ASSERT_EQ_UINT(0u, r.frames_bad);
    BENCH_ASSERT_EQ_UINT(0u, r.frames_late);
    BENCH_ASSERT_EQ_UINT(0u, r.report_counter);
}

BENCH_TEST(trame_manquee_detectee_par_le_compteur) {
    bench_rxq_t q;
    bench_rxq_init(&q, 4u);
    perfect_energy(&q, 3u);  /* compteurs 0, 1, 2 ; pas 0, 1, 2 */
    /* La trame 3 (pas 3) se perd ; la 4 (pas 4) arrive à 80 ms. */
    bench_can_frame_t f = app_frame(0u, 4u, 4u, 80u * MS);
    BENCH_ASSERT_EQ_UINT(80u, bench_rxq_on_frame(&q, &f));
    BENCH_ASSERT_EQ_UINT(1u, q.lost);
    BENCH_ASSERT_EQ_UINT(0u, q.late);  /* deux périodes attendues : à l'heure */
}

BENCH_TEST(somme_fausse_note_0) {
    bench_rxq_t q;
    bench_rxq_init(&q, 4u);
    perfect_energy(&q, 2u);
    bench_can_frame_t f = app_frame(0u, 2u, 2u, 40u * MS);
    f.data[1] ^= 0x20u;
    BENCH_ASSERT_EQ_UINT(0u, bench_rxq_on_frame(&q, &f));
    BENCH_ASSERT_EQ_UINT(1u, q.bad);
}

BENCH_TEST(dlc_incoherent_note_0) {
    bench_rxq_t q;
    bench_rxq_init(&q, 1u);
    bench_can_frame_t f = app_frame(2u, 0u, 0u, 0u);
    f.dlc = 4u;
    BENCH_ASSERT_EQ_UINT(0u, bench_rxq_on_frame(&q, &f));
    BENCH_ASSERT_EQ_UINT(1u, q.bad);
}

BENCH_TEST(contenu_hors_sequence_penalise) {
    bench_rxq_t q;
    bench_rxq_init(&q, 1u);
    bench_can_frame_t f = app_frame(2u, 0u, 0u, 0u);
    BENCH_ASSERT_EQ_UINT(100u, bench_rxq_on_frame(&q, &f));
    /* Pas 1 attendu, pas 3 reçu, compteur continu : séquence décalée. */
    f = app_frame(2u, 3u, 1u, 20u * MS);
    BENCH_ASSERT_EQ_UINT(80u, bench_rxq_on_frame(&q, &f));
    /* Contenu inconnu de l'ICD. */
    f = app_frame(2u, 4u, 2u, 40u * MS);
    f.data[2] ^= 0x01u;
    BENCH_ASSERT_EQ_UINT(60u, bench_rxq_on_frame(&q, &f));
}

BENCH_TEST(retard_penalise_au_dela_de_la_tolerance) {
    bench_rxq_t q;
    bench_rxq_init(&q, 4u);
    perfect_energy(&q, 2u);  /* t = 0 et 20 ms */
    /* 21,5 ms : dans la tolérance de 2 ms. */
    bench_can_frame_t f = app_frame(0u, 2u, 2u, 41500u);
    BENCH_ASSERT_EQ_UINT(100u, bench_rxq_on_frame(&q, &f));
    /* 30 ms après : 10 ms d'écart, 8 au-delà de la tolérance, sur 10 ms de demi-période. */
    f = app_frame(0u, 3u, 3u, 71500u);
    BENCH_ASSERT_EQ_UINT(76u, bench_rxq_on_frame(&q, &f));
    BENCH_ASSERT_EQ_UINT(1u, q.late);
}

BENCH_TEST(arbitrage_suspend_la_ponctualite) {
    bench_rxq_t q;
    bench_rxq_init(&q, 4u);
    perfect_energy(&q, 2u);
    bench_rxq_on_arm(&q);
    /* Contendante 5 ms après, puis reprise 100 ms plus tard : non jugées. */
    bench_can_frame_t f = app_frame(0u, 2u, 2u, 25u * MS);
    BENCH_ASSERT_EQ_UINT(100u, bench_rxq_on_frame(&q, &f));
    f = app_frame(0u, 3u, 3u, 125u * MS);
    BENCH_ASSERT_EQ_UINT(100u, bench_rxq_on_frame(&q, &f));
    /* La suivante l'est de nouveau. */
    f = app_frame(0u, 4u, 4u, 145u * MS);
    BENCH_ASSERT_EQ_UINT(100u, bench_rxq_on_frame(&q, &f));
    f = app_frame(0u, 0u, 5u, 185u * MS);  /* 40 ms au lieu de 20, compteur continu */
    BENCH_ASSERT(bench_rxq_on_frame(&q, &f) < 100u);
}

BENCH_TEST(heartbeats_pertes_deduites_de_l_intervalle) {
    bench_rxq_t q;
    bench_rxq_init(&q, 1u);
    bench_can_frame_t f = heartbeat(2u, 0u);
    BENCH_ASSERT_EQ_UINT(100u, bench_rxq_on_frame(&q, &f));
    f = heartbeat(2u, 500u * MS);
    BENCH_ASSERT_EQ_UINT(100u, bench_rxq_on_frame(&q, &f));
    f = heartbeat(2u, 2000u * MS);  /* 3 périodes : 2 heartbeats manqués */
    BENCH_ASSERT_EQ_UINT(60u, bench_rxq_on_frame(&q, &f));
    BENCH_ASSERT_EQ_UINT(2u, q.lost);
    /* Son propre heartbeat n'est pas suivi. */
    f = heartbeat(1u, 2000u * MS);
    BENCH_ASSERT_EQ_UINT(BENCH_RXQ_NONE, bench_rxq_on_frame(&q, &f));
}

BENCH_TEST(long_silence_compte_comme_une_reprise) {
    /* Un nœud débranché une minute ne compte pas 120 heartbeats perdus. */
    bench_rxq_t q;
    bench_rxq_init(&q, 1u);
    bench_can_frame_t f = heartbeat(4u, 0u);
    (void)bench_rxq_on_frame(&q, &f);
    f = heartbeat(4u, 500u * MS);
    (void)bench_rxq_on_frame(&q, &f);
    f = heartbeat(4u, 60500u * MS);
    BENCH_ASSERT_EQ_UINT(100u, bench_rxq_on_frame(&q, &f));
    BENCH_ASSERT_EQ_UINT(0u, q.total_lost);
    f = heartbeat(4u, 61000u * MS);
    BENCH_ASSERT_EQ_UINT(100u, bench_rxq_on_frame(&q, &f));
}

BENCH_TEST(redemarrage_de_l_emetteur_compte_comme_une_reprise) {
    /* N1 redémarre : 2 s de silence, puis compteur et séquence repartent de 0.
     * Sans reprise, le saut de compteur 9 -> 0 compterait 246 trames perdues. */
    bench_rxq_t q;
    bench_rxq_init(&q, 2u);
    perfect_energy(&q, 10u);  /* compteurs 0 à 9, dernière trame à 180 ms */
    bench_can_frame_t f = app_frame(0u, 0u, 0u, 2180u * MS);
    BENCH_ASSERT_EQ_UINT(100u, bench_rxq_on_frame(&q, &f));
    BENCH_ASSERT_EQ_UINT(0u, q.total_lost);
    BENCH_ASSERT_EQ_UINT(0u, q.total_bad);
    BENCH_ASSERT_EQ_UINT(0u, q.total_late);
    /* La trame suivante est de nouveau jugée sur tout, ponctualité comprise. */
    f = app_frame(0u, 1u, 1u, 2200u * MS);
    BENCH_ASSERT_EQ_UINT(100u, bench_rxq_on_frame(&q, &f));
    f = app_frame(0u, 3u, 3u, 2240u * MS);  /* une trame manquée */
    BENCH_ASSERT_EQ_UINT(80u, bench_rxq_on_frame(&q, &f));
    BENCH_ASSERT_EQ_UINT(1u, q.total_lost);
}

BENCH_TEST(coupure_courte_reste_comptee) {
    /* 400 ms de silence (20 périodes) : ce n'est pas encore une reprise. */
    bench_rxq_t q;
    bench_rxq_init(&q, 2u);
    perfect_energy(&q, 2u);  /* dernière trame à 20 ms, compteur 1, pas 1 */
    bench_can_frame_t f = app_frame(0u, 1u, 21u, 420u * MS);
    BENCH_ASSERT_EQ_UINT(40u, bench_rxq_on_frame(&q, &f));
    BENCH_ASSERT_EQ_UINT(19u, q.total_lost);
    BENCH_ASSERT_EQ_UINT(0u, q.total_late);
}

BENCH_TEST(periode_de_heartbeat_reconfiguree) {
    bench_rxq_t q;
    bench_rxq_init(&q, 1u);
    bench_bench_cfg_t cfg = {0};
    cfg.target_node = 3u;
    cfg.heartbeat_period_ms = 100u;
    uint8_t data[8];
    bench_bench_cfg_pack(data, &cfg);
    bench_rxq_on_cfg(&q, data);
    BENCH_ASSERT_EQ_UINT(100u, q.hb_period_ms[2]);
    BENCH_ASSERT_EQ_UINT(500u, q.hb_period_ms[1]);
}

BENCH_TEST(rapport_moyenne_et_remise_a_zero) {
    bench_rxq_t q;
    bench_rxq_init(&q, 4u);
    perfect_energy(&q, 3u);
    bench_can_frame_t f = app_frame(0u, 3u, 3u, 60u * MS);
    f.dlc = 7u;  /* une trame à 0 sur 4 */
    (void)bench_rxq_on_frame(&q, &f);
    uint8_t out[8];
    bench_rxq_report(&q, out);
    bench_quality_t r;
    bench_quality_unpack(&r, out);
    BENCH_ASSERT_EQ_UINT(75u, r.score_energy_command);
    BENCH_ASSERT_EQ_UINT(1u, r.frames_bad);
    /* Fenêtre suivante : vide, compteur de rapport incrémenté. */
    bench_rxq_report(&q, out);
    bench_quality_unpack(&r, out);
    BENCH_ASSERT_EQ_UINT(BENCH_RXQ_NONE, r.score_energy_command);
    BENCH_ASSERT_EQ_UINT(0u, r.frames_bad);
    BENCH_ASSERT_EQ_UINT(1u, r.report_counter);
}

BENCH_TEST_MAIN(flux_parfait_note_100, trame_manquee_detectee_par_le_compteur, somme_fausse_note_0,
                dlc_incoherent_note_0, contenu_hors_sequence_penalise,
                retard_penalise_au_dela_de_la_tolerance, arbitrage_suspend_la_ponctualite,
                heartbeats_pertes_deduites_de_l_intervalle, long_silence_compte_comme_une_reprise,
                redemarrage_de_l_emetteur_compte_comme_une_reprise, coupure_courte_reste_comptee,
                periode_de_heartbeat_reconfiguree,
                rapport_moyenne_et_remise_a_zero)
