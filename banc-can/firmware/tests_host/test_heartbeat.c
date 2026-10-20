/**
 * @file test_heartbeat.c
 * @brief Tests du cadencement et du contenu du heartbeat.
 */

#include "bench_test.h"
#include "protocol/heartbeat.h"

BENCH_TEST(identifiants_par_noeud) {
    /* Profil « bench » : base 0x780, hors de 0x700-0x77F occupé par le heartbeat
     * CANopen, et à la priorité la plus basse du bus. */
    BENCH_ASSERT_EQ_UINT(BENCH_ID_HEARTBEAT_N1, bench_heartbeat_id(1u));
    BENCH_ASSERT_EQ_UINT(BENCH_ID_HEARTBEAT_N4, bench_heartbeat_id(4u));
    BENCH_ASSERT(bench_heartbeat_id(1u) > 0x77Fu);
}

BENCH_TEST(cadence_a_la_periode_demandee) {
    bench_heartbeat_sched_t hb;
    bench_heartbeat_init(&hb, 500u);

    BENCH_ASSERT(bench_heartbeat_due(&hb, 0u));      /* première émission immédiate */
    BENCH_ASSERT(!bench_heartbeat_due(&hb, 499u));
    BENCH_ASSERT(bench_heartbeat_due(&hb, 500u));
    BENCH_ASSERT(!bench_heartbeat_due(&hb, 999u));
    BENCH_ASSERT(bench_heartbeat_due(&hb, 1000u));
}

BENCH_TEST(suspension_pendant_un_test_d_arbitrage) {
    /* Un heartbeat qui s'intercalerait entre GO et les trames contendantes
     * fausserait le comptage du rang : l'émission doit être suspendue. */
    bench_heartbeat_sched_t hb;
    bench_heartbeat_init(&hb, 100u);

    BENCH_ASSERT(bench_heartbeat_due(&hb, 0u));

    bench_heartbeat_suspend(&hb, true);
    for (uint32_t t = 100u; t <= 2000u; t += 100u) {
        BENCH_ASSERT(!bench_heartbeat_due(&hb, t));
    }

    /* À la reprise, aucun retard n'est rattrapé d'un coup. */
    bench_heartbeat_suspend(&hb, false);
    BENCH_ASSERT(!bench_heartbeat_due(&hb, 2050u));
    BENCH_ASSERT(bench_heartbeat_due(&hb, 2100u));
}

BENCH_TEST(periode_reconfigurable) {
    bench_heartbeat_sched_t hb;
    bench_heartbeat_init(&hb, 500u);
    BENCH_ASSERT(bench_heartbeat_due(&hb, 0u));

    /* 0 signifie « ne pas modifier » (cf. BENCH_CFG.heartbeat_period_ms). */
    bench_heartbeat_set_period(&hb, 0u);
    BENCH_ASSERT_EQ_UINT(500u, hb.period_ms);

    bench_heartbeat_set_period(&hb, 100u);
    BENCH_ASSERT_EQ_UINT(100u, hb.period_ms);
    BENCH_ASSERT(bench_heartbeat_due(&hb, 500u));
    BENCH_ASSERT(bench_heartbeat_due(&hb, 600u));
}

BENCH_TEST(insensible_au_rebouclage_du_compteur) {
    /* Le compteur de millisecondes reboucle au bout d'environ 49 jours ; le banc
     * doit continuer d'émettre au lieu de se bloquer. */
    bench_heartbeat_sched_t hb;
    bench_heartbeat_init(&hb, 500u);

    const uint32_t presque_max = 0xFFFFFF00u;
    BENCH_ASSERT(bench_heartbeat_due(&hb, presque_max));
    BENCH_ASSERT(!bench_heartbeat_due(&hb, presque_max + 100u));
    BENCH_ASSERT(bench_heartbeat_due(&hb, presque_max + 500u));  /* après rebouclage */
}

BENCH_TEST(contenu_reflete_le_materiel) {
    bench_heartbeat_inputs_t inputs = {0};
    bench_can_status_t status = {0};
    bench_ring_t ring;
    uint8_t data[8];
    bench_heartbeat_t decoded;

    bench_ring_init(&ring);

    inputs.node_id = 2u;
    inputs.current_mode = 3u;
    inputs.fault_mode_active = true;
    inputs.silent_mode = false;
    inputs.clock_not_qualified = true;

    status.state = BENCH_CAN_ERROR_PASSIVE;
    status.tec = 130u;
    status.rec = 97u;
    status.last_error_code = 5u;
    status.rx_fifo_lost = 12u;

    /* Provoque deux rejets du tampon logiciel. */
    bench_can_frame_t frame = {0};
    for (uint32_t i = 0u; i < BENCH_RING_CAPACITY + 1u; i++) {
        frame.id = (uint16_t)i;
        (void)bench_ring_push(&ring, &frame);
    }

    bench_heartbeat_pack_frame(&inputs, &status, &ring, data);
    bench_heartbeat_unpack(&decoded, data);

    BENCH_ASSERT_EQ_UINT(BENCH_CAN_ERROR_PASSIVE, decoded.ctrl_state);
    BENCH_ASSERT_EQ_UINT(5u, decoded.last_error_code);
    BENCH_ASSERT_EQ_UINT(1u, decoded.clock_not_qualified);
    BENCH_ASSERT_EQ_UINT(1u, decoded.fault_mode_active);
    BENCH_ASSERT_EQ_UINT(0u, decoded.silent_mode);
    BENCH_ASSERT_EQ_UINT(130u, decoded.tec);
    BENCH_ASSERT_EQ_UINT(97u, decoded.rec);
    BENCH_ASSERT_EQ_UINT(3u, decoded.current_mode);

    /* Les deux origines de perte restent distinctes : matérielle et logicielle. */
    BENCH_ASSERT_EQ_UINT(12u, decoded.rx_fifo_lost);
    BENCH_ASSERT_EQ_UINT(2u, decoded.ring_overflow);
}

BENCH_TEST_MAIN(identifiants_par_noeud, cadence_a_la_periode_demandee,
                suspension_pendant_un_test_d_arbitrage, periode_reconfigurable,
                insensible_au_rebouclage_du_compteur, contenu_reflete_le_materiel)
