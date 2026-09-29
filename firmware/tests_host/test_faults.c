/**
 * @file test_faults.c
 * @brief Tests de l'exécution des modes de faute, sur un contrôleur simulé.
 *
 * Le faux contrôleur enregistre chaque appel : on vérifie ce que l'exécuteur
 * demande au matériel, pas une interprétation de son état interne.
 */

#include "app/faults.h"
#include "app/node.h"
#include "bench_test.h"
#include "icd_gen.h"

/* ------------------------------------------------------ faux contrôleur -- */

typedef struct {
    unsigned           opens;
    bench_can_config_t last_open;
    bool               silent;
    unsigned           silent_calls;
    unsigned           recovers;
    unsigned           sends;
    bench_can_frame_t  last_sent;
    unsigned           free_slots;  /**< places libres en file d'émission */
} fake_can_t;

static bool fake_open(void *ctx, const bench_can_config_t *config) {
    fake_can_t *f = (fake_can_t *)ctx;
    f->opens++;
    f->last_open = *config;
    return true;
}

static bool fake_send(void *ctx, const bench_can_frame_t *frame) {
    fake_can_t *f = (fake_can_t *)ctx;
    if (f->free_slots == 0u) {
        return false;
    }
    f->free_slots--;
    f->sends++;
    f->last_sent = *frame;
    return true;
}

static void fake_status(void *ctx, bench_can_status_t *status) {
    (void)ctx;
    (void)status;
}

static bool fake_recover(void *ctx) {
    ((fake_can_t *)ctx)->recovers++;
    return true;
}

static void fake_set_silent(void *ctx, bool silent) {
    fake_can_t *f = (fake_can_t *)ctx;
    f->silent = silent;
    f->silent_calls++;
}

static uint32_t fake_now_us(void *ctx) {
    (void)ctx;
    return 0u;
}

static const bench_can_ops_t k_fake_ops = {
    .open = fake_open,
    .send = fake_send,
    .arm = fake_send,
    .status = fake_status,
    .recover = fake_recover,
    .set_silent = fake_set_silent,
    .now_us = fake_now_us,
};

static fake_can_t     s_fake;
static bench_can_t    s_can;
static bench_faults_t s_faults;

static bench_can_config_t nominal_config(void) {
    bench_can_config_t config = {0};
    config.timing.prescaler = 10u;
    config.timing.tseg1 = 13u;
    config.timing.tseg2 = 2u;
    config.timing.sjw = 2u;
    config.busoff_policy = BENCH_BUSOFF_AUTO;
    config.auto_retransmit = true;
    return config;
}

static void setup(void) {
    memset(&s_fake, 0, sizeof(s_fake));
    s_fake.free_slots = 1000u;
    s_can.ops = &k_fake_ops;
    s_can.ctx = &s_fake;
    const bench_can_config_t nominal = nominal_config();
    bench_faults_init(&s_faults, &s_can, &nominal);
}

/* ---------------------------------------------------------------- cas -- */

BENCH_TEST(mode_normal_ne_touche_a_rien) {
    setup();
    for (uint32_t t = 0u; t < 100u; t++) {
        BENCH_ASSERT_EQ_UINT(0u, bench_faults_step(&s_faults, BENCH_MODE_NORMAL, 0x400u, t));
    }
    BENCH_ASSERT_EQ_UINT(0u, s_fake.opens);
    BENCH_ASSERT_EQ_UINT(0u, s_fake.sends);
    BENCH_ASSERT_EQ_UINT(0u, s_fake.silent_calls);
}

BENCH_TEST(babbling_idiot_remplit_la_file_avec_l_identifiant_demande) {
    setup();
    const uint32_t sent = bench_faults_step(&s_faults, BENCH_MODE_BABBLING_IDIOT, 0x400u, 0u);

    BENCH_ASSERT_EQ_UINT(BENCH_FAULT_FLOOD_BURST, sent);
    BENCH_ASSERT_EQ_UINT(0x400u, s_fake.last_sent.id);
    BENCH_ASSERT_EQ_UINT(8u, s_fake.last_sent.dlc);

    /* File pleine : l'exécuteur ne se bloque pas, il réessaiera au tour suivant. */
    s_fake.free_slots = 0u;
    BENCH_ASSERT_EQ_UINT(0u, bench_faults_step(&s_faults, BENCH_MODE_BABBLING_IDIOT, 0x400u, 1u));
}

BENCH_TEST(sans_identifiant_de_faute_rien_n_est_emis) {
    /* Cas de N4 sans paramètre : un mode de faute n'invente pas d'identifiant. */
    setup();
    BENCH_ASSERT_EQ_UINT(0u, bench_faults_step(&s_faults, BENCH_MODE_BABBLING_IDIOT, 0u, 0u));
    BENCH_ASSERT_EQ_UINT(0u, bench_faults_step(&s_faults, BENCH_MODE_BAD_DLC, 0u, 100u));
    BENCH_ASSERT_EQ_UINT(0u, s_fake.sends);
}

BENCH_TEST(dlc_incoherent_cadence_comme_le_simulateur) {
    setup();
    unsigned sent = 0u;
    for (uint32_t t = 0u; t < 100u; t++) {
        sent += bench_faults_step(&s_faults, BENCH_MODE_BAD_DLC, 0x123u, t);
    }
    /* 100 ms à une trame toutes les 20 ms : 5 trames, première immédiate. */
    BENCH_ASSERT_EQ_UINT(100u / BENCH_FAULT_BAD_DLC_PERIOD_MS, sent);
    BENCH_ASSERT_EQ_UINT(BENCH_FAULT_BAD_DLC, s_fake.last_sent.dlc);
    BENCH_ASSERT_EQ_UINT(0x123u, s_fake.last_sent.id);
}

BENCH_TEST(debit_errone_puis_retour_au_nominal) {
    setup();
    bench_faults_step(&s_faults, BENCH_MODE_WRONG_BITRATE, 0u, 0u);
    BENCH_ASSERT_EQ_UINT(1u, s_fake.opens);
    BENCH_ASSERT_EQ_UINT(20u, s_fake.last_open.timing.prescaler);  /* 250 kbit/s */
    BENCH_ASSERT_EQ_UINT(13u, s_fake.last_open.timing.tseg1);      /* même point */

    /* Rester dans le mode ne rouvre pas le contrôleur à chaque tour. */
    bench_faults_step(&s_faults, BENCH_MODE_WRONG_BITRATE, 0u, 1u);
    BENCH_ASSERT_EQ_UINT(1u, s_fake.opens);

    bench_faults_step(&s_faults, BENCH_MODE_NORMAL, 0u, 2u);
    BENCH_ASSERT_EQ_UINT(2u, s_fake.opens);
    BENCH_ASSERT_EQ_UINT(10u, s_fake.last_open.timing.prescaler);
}

BENCH_TEST(silencieux_puis_retour) {
    setup();
    bench_faults_step(&s_faults, BENCH_MODE_SILENT, 0x400u, 0u);
    BENCH_ASSERT(s_fake.silent);
    BENCH_ASSERT_EQ_UINT(0u, s_fake.sends);  /* un nœud silencieux n'émet rien */

    bench_faults_step(&s_faults, BENCH_MODE_NORMAL, 0x400u, 1u);
    BENCH_ASSERT(!s_fake.silent);
    BENCH_ASSERT_EQ_UINT(2u, s_fake.silent_calls);
}

BENCH_TEST(bus_off_maintenu_desactive_la_reprise_puis_la_retablit) {
    setup();
    bench_faults_step(&s_faults, BENCH_MODE_HOLD_BUSOFF, 0u, 0u);
    BENCH_ASSERT_EQ_UINT(BENCH_BUSOFF_MANUAL, s_fake.last_open.busoff_policy);

    bench_faults_step(&s_faults, BENCH_MODE_NORMAL, 0u, 1u);
    BENCH_ASSERT_EQ_UINT(BENCH_BUSOFF_AUTO, s_fake.last_open.busoff_policy);
    BENCH_ASSERT_EQ_UINT(1u, s_fake.recovers);
}

BENCH_TEST(passage_direct_d_une_faute_a_une_autre) {
    /* Silencieux -> débit erroné : le mode moniteur doit être levé avant la
     * réouverture, sinon le nœud resterait muet à 250 kbit/s. */
    setup();
    bench_faults_step(&s_faults, BENCH_MODE_SILENT, 0u, 0u);
    bench_faults_step(&s_faults, BENCH_MODE_WRONG_BITRATE, 0u, 1u);
    BENCH_ASSERT(!s_fake.silent);
    BENCH_ASSERT_EQ_UINT(20u, s_fake.last_open.timing.prescaler);
}

BENCH_TEST(le_noeud_retient_le_parametre_et_l_oublie_a_l_echeance) {
    bench_node_t node;
    bench_ring_t ring;
    uint8_t cfg_data[8];
    uint8_t heartbeat[8];
    bench_can_status_t status = {0};

    setup();
    bench_ring_init(&ring);
    bench_node_init(&node, 4u, &s_can, &ring, true);
    BENCH_ASSERT_EQ_UINT(0u, bench_faults_id(&node));  /* N4 : pas de trame propre */

    bench_bench_cfg_t cfg = {0};
    cfg.target_node = 4u;
    cfg.mode = (uint8_t)BENCH_MODE_BABBLING_IDIOT;
    cfg.param_u16 = 0x400u;
    cfg.duration_ms = 1000u;
    bench_bench_cfg_pack(cfg_data, &cfg);
    bench_node_apply_cfg(&node, cfg_data, 0u);

    BENCH_ASSERT_EQ_UINT(BENCH_MODE_BABBLING_IDIOT, node.mode);
    BENCH_ASSERT_EQ_UINT(0x400u, bench_faults_id(&node));

    (void)bench_node_tick(&node, 1000u, &status, heartbeat);
    BENCH_ASSERT_EQ_UINT(BENCH_MODE_NORMAL, node.mode);
    BENCH_ASSERT_EQ_UINT(0u, bench_faults_id(&node));
}

BENCH_TEST(mode_inconnu_ignore) {
    bench_node_t node;
    bench_ring_t ring;
    uint8_t cfg_data[8];

    setup();
    bench_ring_init(&ring);
    bench_node_init(&node, 4u, &s_can, &ring, true);

    bench_bench_cfg_t cfg = {0};
    cfg.target_node = 4u;
    cfg.mode = 42u;
    cfg.duration_ms = 1000u;
    bench_bench_cfg_pack(cfg_data, &cfg);
    bench_node_apply_cfg(&node, cfg_data, 0u);

    BENCH_ASSERT_EQ_UINT(BENCH_MODE_NORMAL, node.mode);
}

BENCH_TEST_MAIN(mode_normal_ne_touche_a_rien,
                babbling_idiot_remplit_la_file_avec_l_identifiant_demande,
                sans_identifiant_de_faute_rien_n_est_emis,
                dlc_incoherent_cadence_comme_le_simulateur, debit_errone_puis_retour_au_nominal,
                silencieux_puis_retour, bus_off_maintenu_desactive_la_reprise_puis_la_retablit,
                passage_direct_d_une_faute_a_une_autre,
                le_noeud_retient_le_parametre_et_l_oublie_a_l_echeance, mode_inconnu_ignore)
