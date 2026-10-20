/**
 * @file test_node.c
 * @brief Tests du nœud face au protocole ARM/GO, avec la confirmation d'émission.
 *
 * Ces cas couvrent le défaut D1 de docs/PLAN.md : le rang d'un nœud n'est figé
 * que par la confirmation d'émission (élément BENCH_FRAME_OWN_TX du tampon),
 * dans l'ordre réel du bus, et un départ avant GO ne doit jamais produire de
 * rang valide.
 */

#include "app/node.h"
#include "bench_test.h"
#include "icd_gen.h"

static bench_can_frame_t rx(uint16_t id) {
    bench_can_frame_t frame = {0};
    frame.id = id;
    frame.dlc = 8u;
    return frame;
}

static bench_can_frame_t own_tx(uint16_t id) {
    bench_can_frame_t frame = rx(id);
    frame.flags = BENCH_FRAME_OWN_TX;
    return frame;
}

static void setup(bench_node_t *node, bench_ring_t *ring, uint8_t node_id) {
    bench_ring_init(ring);
    bench_node_init(node, node_id, NULL, ring, true);
}

BENCH_TEST(rang_fige_a_la_confirmation_d_emission) {
    bench_node_t n2;
    bench_ring_t ring;
    setup(&n2, &ring, 2u);

    const bench_can_frame_t arm = rx(BENCH_ID_ARM);
    const bench_can_frame_t go = rx(BENCH_ID_GO);
    const bench_can_frame_t n1 = rx(BENCH_ID_ENERGY_COMMAND);
    const bench_can_frame_t mine = own_tx(BENCH_ID_IMU_SPEED);

    BENCH_ASSERT(bench_node_on_frame(&n2, &arm, 0u));  /* ARM : il faut armer */
    (void)bench_node_on_frame(&n2, &go, 0u);
    (void)bench_node_on_frame(&n2, &n1, 0u);            /* N1 l'emporte */
    (void)bench_node_on_frame(&n2, &mine, 0u);          /* puis notre trame part */

    BENCH_ASSERT_EQ_UINT(2u, bench_arb_last_rank(&n2.arb));
    BENCH_ASSERT_EQ_UINT(1u, n2.arb.counters.cycles);
    BENCH_ASSERT_EQ_UINT(0u, n2.arb.counters.invalid);
}

BENCH_TEST(la_confirmation_n_est_pas_comptee_comme_trame_recue) {
    bench_node_t n1;
    bench_ring_t ring;
    setup(&n1, &ring, 1u);

    const bench_can_frame_t mine = own_tx(BENCH_ID_ENERGY_COMMAND);
    (void)bench_node_on_frame(&n1, &mine, 0u);
    BENCH_ASSERT_EQ_UINT(0u, n1.frames_received);
}

BENCH_TEST(depart_avant_go_ne_donne_aucun_rang) {
    /* Le cas que D1 masquait : bus libre après ARM, la trame part seule, avant
     * GO. Elle n'a affronté personne ; elle ne doit pas être classée. */
    bench_node_t n1;
    bench_ring_t ring;
    setup(&n1, &ring, 1u);
    uint8_t heartbeat[8];
    bench_can_status_t status = {0};

    const bench_can_frame_t arm = rx(BENCH_ID_ARM);
    const bench_can_frame_t go = rx(BENCH_ID_GO);
    const bench_can_frame_t mine = own_tx(BENCH_ID_ENERGY_COMMAND);

    (void)bench_node_on_frame(&n1, &arm, 0u);
    (void)bench_node_on_frame(&n1, &mine, 0u);  /* partie avant GO */
    (void)bench_node_on_frame(&n1, &go, 0u);

    BENCH_ASSERT_EQ_UINT(0u, n1.arb.counters.cycles);
    BENCH_ASSERT_EQ_UINT(0u, bench_arb_last_rank(&n1.arb));

    /* Le délai de garde clôt le cycle comme invalide, et le heartbeat reprend. */
    (void)bench_node_tick(&n1, BENCH_ARB_TIMEOUT_MS - 1u, &status, heartbeat);
    BENCH_ASSERT_EQ_UINT(0u, n1.arb.counters.invalid);
    (void)bench_node_tick(&n1, BENCH_ARB_TIMEOUT_MS, &status, heartbeat);
    BENCH_ASSERT_EQ_UINT(1u, n1.arb.counters.invalid);
    BENCH_ASSERT_EQ_UINT(BENCH_ARB_IDLE, n1.arb.phase);
    BENCH_ASSERT(!n1.heartbeat.suspended);
}

BENCH_TEST(cycle_nominal_non_abandonne_par_le_delai_de_garde) {
    bench_node_t n3;
    bench_ring_t ring;
    setup(&n3, &ring, 3u);
    uint8_t heartbeat[8];
    bench_can_status_t status = {0};

    const bench_can_frame_t arm = rx(BENCH_ID_ARM);
    const bench_can_frame_t go = rx(BENCH_ID_GO);
    const bench_can_frame_t n1 = rx(BENCH_ID_ENERGY_COMMAND);
    const bench_can_frame_t n2 = rx(BENCH_ID_IMU_SPEED);
    const bench_can_frame_t mine = own_tx(BENCH_ID_TEMP_BATTERY);

    (void)bench_node_on_frame(&n3, &arm, 10u);
    (void)bench_node_on_frame(&n3, &go, 10u);
    (void)bench_node_on_frame(&n3, &n1, 10u);
    (void)bench_node_on_frame(&n3, &n2, 10u);
    (void)bench_node_on_frame(&n3, &mine, 10u);
    (void)bench_node_tick(&n3, 10u + 5u * BENCH_ARB_TIMEOUT_MS, &status, heartbeat);

    BENCH_ASSERT_EQ_UINT(3u, bench_arb_last_rank(&n3.arb));
    BENCH_ASSERT_EQ_UINT(0u, n3.arb.counters.invalid);
}

BENCH_TEST_MAIN(rang_fige_a_la_confirmation_d_emission,
                la_confirmation_n_est_pas_comptee_comme_trame_recue,
                depart_avant_go_ne_donne_aucun_rang,
                cycle_nominal_non_abandonne_par_le_delai_de_garde)
