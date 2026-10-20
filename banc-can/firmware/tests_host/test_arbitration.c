/**
 * @file test_arbitration.c
 * @brief Tests du protocole ARM/GO et de la mesure du rang.
 *
 * Le scénario central rejoue des cycles complets à trois contendants et vérifie
 * que le classement attendu du dossier (N1 rang 1, N2 rang 2, N3 rang 3) est
 * bien obtenu, ainsi que les cas où le test doit se déclarer invalide.
 */

#include "bench_test.h"
#include "icd_gen.h"
#include "protocol/arbitration.h"

#define ID_ARM BENCH_ID_ARM
#define ID_GO  BENCH_ID_GO
#define ID_N1  BENCH_ID_ENERGY_COMMAND
#define ID_N2  BENCH_ID_IMU_SPEED
#define ID_N3  BENCH_ID_TEMP_BATTERY

static bench_can_frame_t f(uint16_t id) {
    bench_can_frame_t frame = {0};
    frame.id = id;
    frame.dlc = 8u;
    return frame;
}

/** Transmet une trame aux trois contendants, dans l'ordre du bus. */
static void broadcast(bench_arb_t *n1, bench_arb_t *n2, bench_arb_t *n3, uint16_t id) {
    const bench_can_frame_t frame = f(id);
    const bool contender = (id == ID_N1) || (id == ID_N2) || (id == ID_N3);

    (void)bench_arb_on_frame(n1, &frame, contender);
    (void)bench_arb_on_frame(n2, &frame, contender);
    (void)bench_arb_on_frame(n3, &frame, contender);
}

/**
 * Rejoue un cycle nominal : ARM, GO, puis les trois trames dans l'ordre imposé
 * par l'arbitrage (identifiant le plus faible d'abord).
 */
static void nominal_cycle(bench_arb_t *n1, bench_arb_t *n2, bench_arb_t *n3) {
    broadcast(n1, n2, n3, ID_ARM);
    broadcast(n1, n2, n3, ID_GO);

    /* N1 gagne : sa trame passe la première. */
    broadcast(n1, n2, n3, ID_N1);
    bench_arb_on_own_tx(n1);

    broadcast(n1, n2, n3, ID_N2);
    bench_arb_on_own_tx(n2);

    broadcast(n1, n2, n3, ID_N3);
    bench_arb_on_own_tx(n3);
}

static void init_three(bench_arb_t *n1, bench_arb_t *n2, bench_arb_t *n3) {
    bench_arb_init(n1, ID_ARM, ID_GO, ID_N1, true);
    bench_arb_init(n2, ID_ARM, ID_GO, ID_N2, true);
    bench_arb_init(n3, ID_ARM, ID_GO, ID_N3, true);
}

BENCH_TEST(classement_attendu_sur_mille_cycles) {
    bench_arb_t n1, n2, n3;
    init_three(&n1, &n2, &n3);

    for (uint32_t i = 0u; i < 1000u; i++) {
        nominal_cycle(&n1, &n2, &n3);
    }

    /* Résultat attendu du dossier (tableau 7), exprimé sans ambiguïté. */
    BENCH_ASSERT(bench_arb_all_cycles_at_rank(&n1, 1u));
    BENCH_ASSERT(bench_arb_all_cycles_at_rank(&n2, 2u));
    BENCH_ASSERT(bench_arb_all_cycles_at_rank(&n3, 3u));

    BENCH_ASSERT_EQ_UINT(1000u, n1.counters.cycles);
    BENCH_ASSERT_EQ_UINT(1000u, n1.counters.won);
    BENCH_ASSERT_EQ_UINT(0u, n1.counters.lost);

    BENCH_ASSERT_EQ_UINT(0u, n2.counters.won);
    BENCH_ASSERT_EQ_UINT(1000u, n2.counters.lost);

    BENCH_ASSERT_EQ_UINT(0u, n3.counters.won);
    /* N3 perd deux arbitrages par cycle mais « lost » compte des cycles : 1000,
     * ce qui lève l'ambiguïté du tableau 7 du dossier. */
    BENCH_ASSERT_EQ_UINT(1000u, n3.counters.lost);

    /* Tous les contendants doivent afficher le même nombre d'ARM reçus. */
    BENCH_ASSERT_EQ_UINT(1000u, n1.counters.arm_rx);
    BENCH_ASSERT_EQ_UINT(n1.counters.arm_rx, n2.counters.arm_rx);
    BENCH_ASSERT_EQ_UINT(n1.counters.arm_rx, n3.counters.arm_rx);

    BENCH_ASSERT_EQ_UINT(0u, n1.counters.invalid);
    BENCH_ASSERT_EQ_UINT(0u, n3.counters.invalid);
}

BENCH_TEST(armement_signale_aux_contendants_seulement) {
    bench_arb_t contender, witness;
    bench_arb_init(&contender, ID_ARM, ID_GO, ID_N1, true);
    bench_arb_init(&witness, ID_ARM, ID_GO, 0u, false);

    const bench_can_frame_t arm = f(ID_ARM);
    BENCH_ASSERT(bench_arb_on_frame(&contender, &arm, false));
    BENCH_ASSERT(!bench_arb_on_frame(&witness, &arm, false));

    /* Le nœud témoin compte tout de même les ARM, ce qui permet de contrôler la
     * validité du cycle depuis un nœud qui ne concourt pas. */
    BENCH_ASSERT_EQ_UINT(1u, witness.counters.arm_rx);
}

BENCH_TEST(go_sans_arm_invalide_le_cycle) {
    /* Un nœud qui a raté ARM émettrait seul juste après et apparaîtrait comme
     * vainqueur sans avoir affronté personne : le cycle doit être écarté. */
    bench_arb_t node;
    bench_arb_init(&node, ID_ARM, ID_GO, ID_N1, true);

    const bench_can_frame_t go = f(ID_GO);
    (void)bench_arb_on_frame(&node, &go, false);
    bench_arb_on_own_tx(&node);

    BENCH_ASSERT_EQ_UINT(0u, node.counters.cycles);
    BENCH_ASSERT_EQ_UINT(0u, node.counters.won);
    BENCH_ASSERT(!bench_arb_all_cycles_at_rank(&node, 1u));
}

BENCH_TEST(arm_pendant_un_cycle_en_cours_invalide_le_precedent) {
    bench_arb_t node;
    bench_arb_init(&node, ID_ARM, ID_GO, ID_N2, true);

    broadcast(&node, &node, &node, ID_ARM);  /* trois fois : sans importance ici */
    bench_arb_init(&node, ID_ARM, ID_GO, ID_N2, true);

    const bench_can_frame_t arm = f(ID_ARM);
    const bench_can_frame_t go = f(ID_GO);

    (void)bench_arb_on_frame(&node, &arm, false);
    (void)bench_arb_on_frame(&node, &go, false);
    /* Notre trame ne part jamais ; un nouvel ARM arrive. */
    (void)bench_arb_on_frame(&node, &arm, false);

    BENCH_ASSERT_EQ_UINT(1u, node.counters.invalid);
    BENCH_ASSERT_EQ_UINT(2u, node.counters.arm_rx);
    BENCH_ASSERT_EQ_UINT(0u, node.counters.cycles);
}

BENCH_TEST(trames_hors_cycle_ignorees) {
    /* Les trames reçues avant GO, ou émises par des nœuds non contendants, ne
     * doivent pas gonfler le rang. */
    bench_arb_t node;
    bench_arb_init(&node, ID_ARM, ID_GO, ID_N3, true);

    const bench_can_frame_t arm = f(ID_ARM);
    const bench_can_frame_t go = f(ID_GO);
    const bench_can_frame_t autre = f(ID_N1);
    const bench_can_frame_t heartbeat = f(BENCH_ID_HEARTBEAT_N1);

    (void)bench_arb_on_frame(&node, &arm, false);
    (void)bench_arb_on_frame(&node, &autre, true);   /* avant GO : ignorée */
    (void)bench_arb_on_frame(&node, &go, false);
    (void)bench_arb_on_frame(&node, &heartbeat, false);  /* non contendante */
    (void)bench_arb_on_frame(&node, &autre, true);       /* comptée */
    bench_arb_on_own_tx(&node);

    BENCH_ASSERT_EQ_UINT(2u, bench_arb_last_rank(&node));
}

BENCH_TEST(propre_trame_non_comptee) {
    /* Un nœud qui reçoit sa propre trame en écho ne doit pas s'auto-devancer. */
    bench_arb_t node;
    bench_arb_init(&node, ID_ARM, ID_GO, ID_N1, true);

    const bench_can_frame_t arm = f(ID_ARM);
    const bench_can_frame_t go = f(ID_GO);
    const bench_can_frame_t self = f(ID_N1);

    (void)bench_arb_on_frame(&node, &arm, false);
    (void)bench_arb_on_frame(&node, &go, false);
    (void)bench_arb_on_frame(&node, &self, true);
    bench_arb_on_own_tx(&node);

    BENCH_ASSERT_EQ_UINT(1u, bench_arb_last_rank(&node));
    BENCH_ASSERT_EQ_UINT(1u, node.counters.won);
}

BENCH_TEST(ordre_degrade_detecte) {
    /* Si l'ordre du bus n'est pas celui des priorités, le classement ne doit pas
     * être uniforme : c'est exactement ce que le test T3 doit faire ressortir. */
    bench_arb_t n1, n2, n3;
    init_three(&n1, &n2, &n3);

    nominal_cycle(&n1, &n2, &n3);

    /* Deuxième cycle en ordre inversé. */
    broadcast(&n1, &n2, &n3, ID_ARM);
    broadcast(&n1, &n2, &n3, ID_GO);
    broadcast(&n1, &n2, &n3, ID_N3);
    bench_arb_on_own_tx(&n3);
    broadcast(&n1, &n2, &n3, ID_N2);
    bench_arb_on_own_tx(&n2);
    broadcast(&n1, &n2, &n3, ID_N1);
    bench_arb_on_own_tx(&n1);

    BENCH_ASSERT(!bench_arb_all_cycles_at_rank(&n1, 1u));
    BENCH_ASSERT(!bench_arb_all_cycles_at_rank(&n3, 3u));
    BENCH_ASSERT_EQ_UINT(1u, n3.counters.rank_histogram[1]);
    BENCH_ASSERT_EQ_UINT(1u, n3.counters.rank_histogram[3]);
}

BENCH_TEST_MAIN(classement_attendu_sur_mille_cycles, armement_signale_aux_contendants_seulement,
                go_sans_arm_invalide_le_cycle, arm_pendant_un_cycle_en_cours_invalide_le_precedent,
                trames_hors_cycle_ignorees, propre_trame_non_comptee, ordre_degrade_detecte)
