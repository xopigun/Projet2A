/**
 * @file test_traffic.c
 * @brief Tests des trames applicatives périodiques (contenu, compteur, somme).
 */

#include "app/traffic.h"
#include "bench_test.h"
#include "icd_gen.h"

BENCH_TEST(une_trame_par_contendant) {
    BENCH_ASSERT_EQ_INT(0, bench_traffic_kind_of_node(1u));
    BENCH_ASSERT_EQ_INT(1, bench_traffic_kind_of_node(2u));
    BENCH_ASSERT_EQ_INT(2, bench_traffic_kind_of_node(3u));
    BENCH_ASSERT_EQ_INT(-1, bench_traffic_kind_of_node(4u));
    BENCH_ASSERT_EQ_INT(0, bench_traffic_kind_of(BENCH_ID_ENERGY_COMMAND));
    BENCH_ASSERT_EQ_INT(2, bench_traffic_kind_of(BENCH_ID_TEMP_BATTERY));
    BENCH_ASSERT_EQ_INT(-1, bench_traffic_kind_of(BENCH_ID_HEARTBEAT_N1));
    BENCH_ASSERT_EQ_UINT(20u, bench_traffic_desc(0u)->period_ms);
}

BENCH_TEST(contenu_conforme_a_la_sequence_de_l_icd) {
    uint8_t data[8];
    uint8_t ref[8];
    /* Pas 1 de ENERGY_COMMAND : 12,5 N.m, 1500 tr/min, 10 A, enable. */
    bench_traffic_build(0u, 1u, 7u, data);
    bench_energy_command_t f = bench_sim_energy_command[1];
    f.command_counter = 7u;
    f.checksum = 0u;
    bench_energy_command_pack(ref, &f);
    BENCH_ASSERT_EQ_MEM(ref, data, 7u, "octets 0 à 6");
    BENCH_ASSERT_EQ_UINT(7u, bench_traffic_counter(0u, data));
    BENCH_ASSERT(bench_traffic_checksum_ok(0u, data));
    BENCH_ASSERT_EQ_INT(1, bench_traffic_match_step(0u, data));
}

BENCH_TEST(somme_de_controle_detecte_un_octet_altere) {
    uint8_t data[8];
    bench_traffic_build(0u, 3u, 42u, data);
    BENCH_ASSERT(bench_traffic_checksum_ok(0u, data));
    data[2] ^= 0x10u;
    BENCH_ASSERT(!bench_traffic_checksum_ok(0u, data));
}

BENCH_TEST(compteur_tronque_a_la_largeur_du_champ) {
    uint8_t data[8];
    /* IMU_SPEED : compteur de 3 bits. */
    bench_traffic_build(1u, 0u, 13u, data);
    BENCH_ASSERT_EQ_UINT(13u & 7u, bench_traffic_counter(1u, data));
    /* Le compteur ne déborde pas sur wheel_speed (bits 0-3 de l'octet 7). */
    BENCH_ASSERT_EQ_INT(0, bench_traffic_match_step(1u, data));
    BENCH_ASSERT(!bench_traffic_sensor_present(1u, data));
}

BENCH_TEST(chaque_pas_est_reconnu) {
    for (uint8_t k = 0u; k < BENCH_TRAFFIC_KINDS; k++) {
        const bench_traffic_desc_t *d = bench_traffic_desc(k);
        for (uint8_t step = 0u; step < d->steps; step++) {
            uint8_t data[8];
            bench_traffic_build(k, step, (uint8_t)(step * 37u), data);
            BENCH_ASSERT_EQ_INT(step, bench_traffic_match_step(k, data));
        }
    }
}

BENCH_TEST(contenu_altere_non_reconnu) {
    uint8_t data[8];
    bench_traffic_build(2u, 1u, 0u, data);
    data[0] ^= 0x01u;  /* température décalée d'un pas de 1/16 °C */
    BENCH_ASSERT_EQ_INT(-1, bench_traffic_match_step(2u, data));
}

BENCH_TEST_MAIN(une_trame_par_contendant, contenu_conforme_a_la_sequence_de_l_icd,
                somme_de_controle_detecte_un_octet_altere, compteur_tronque_a_la_largeur_du_champ,
                chaque_pas_est_reconnu, contenu_altere_non_reconnu)
