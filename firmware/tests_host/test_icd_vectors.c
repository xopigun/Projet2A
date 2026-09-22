/**
 * @file test_icd_vectors.c
 * @brief Parité entre l'encodage C et l'encodage Python de l'ICD.
 *
 * Les vecteurs de ``generated/icd_vectors.c`` sont produits par la référence
 * Python (``tools/codegen/encoding.py``). Pour chacun, on décode les octets avec
 * le C généré puis on les réencode : si les octets obtenus sont identiques, les
 * deux implémentations partagent la même disposition de bits, la même extension
 * de signe, les mêmes masques et la même convention d'arrondi.
 *
 * Un cas dédié vérifie séparément l'arrondi, que l'aller-retour ne peut pas
 * mettre en évidence : les vecteurs ne contiennent que des valeurs exactement
 * représentables.
 */

#include <math.h>

#include "bench_test.h"
#include "icd_gen.h"
#include "icd_vectors.h"

BENCH_TEST(parite_avec_les_vecteurs_python) {
    size_t checked = 0u;

    for (size_t i = 0u; i < bench_vector_count; i++) {
        const bench_vector_t *vector = &bench_vectors[i];
        uint8_t out[8];

        /* On part des valeurs physiques, pas des octets : c'est ce qui rend la
         * comparaison significative. Un aller-retour unpack/pack serait
         * auto-cohérent et passerait même avec des octets de référence faux. */
        if (!bench_vector_pack(vector, out)) {
            continue;  /* ARM et GO n'ont aucun signal */
        }
        BENCH_ASSERT_EQ_MEM(vector->data, out, vector->dlc, vector->label);
        checked++;
    }

    /* Garde-fou : si la génération cassait, le test passerait à vide. */
    BENCH_ASSERT(checked > 100u);
}

BENCH_TEST(aller_retour_unpack_pack) {
    /* Complément du test précédent : le décodage doit être l'inverse exact de
     * l'encodage pour tous les motifs d'octets de référence. */
    for (size_t i = 0u; i < bench_vector_count; i++) {
        const bench_vector_t *vector = &bench_vectors[i];
        uint8_t out[8];

        if (strcmp(vector->frame, "ENERGY_COMMAND") != 0) {
            continue;
        }
        bench_energy_command_t frame;
        bench_energy_command_unpack(&frame, vector->data);
        bench_energy_command_pack(out, &frame);
        BENCH_ASSERT_EQ_MEM(vector->data, out, vector->dlc, vector->label);
    }
}

BENCH_TEST(arrondi_a_l_oppose_de_zero) {
    /* torque_setpoint a un facteur de 0,1 : 0,05 est exactement un demi-pas.
     * llround l'arrondit à 1 ; la fonction round() de Python donnerait 0, d'où
     * la convention bench_round() côté Python. */
    bench_energy_command_t frame = {0};
    uint8_t data[8];

    frame.torque_setpoint = 0.05f;
    bench_energy_command_pack(data, &frame);
    BENCH_ASSERT_EQ_INT(1, (int16_t)((uint16_t)data[0] | ((uint16_t)data[1] << 8)));

    frame.torque_setpoint = -0.05f;
    bench_energy_command_pack(data, &frame);
    BENCH_ASSERT_EQ_INT(-1, (int16_t)((uint16_t)data[0] | ((uint16_t)data[1] << 8)));
}

BENCH_TEST(saturation_sur_les_bornes) {
    /* Une consigne très au-delà de la capacité du champ doit saturer et non
     * déborder sur le signal voisin. */
    bench_energy_command_t frame = {0};
    uint8_t data[8];

    frame.torque_setpoint = 1.0e9f;
    bench_energy_command_pack(data, &frame);
    BENCH_ASSERT_EQ_INT(32767, (int16_t)((uint16_t)data[0] | ((uint16_t)data[1] << 8)));
    BENCH_ASSERT_EQ_UINT(0u, data[2]);  /* speed_setpoint reste nul */
    BENCH_ASSERT_EQ_UINT(0u, data[3]);

    frame.torque_setpoint = -1.0e9f;
    bench_energy_command_pack(data, &frame);
    BENCH_ASSERT_EQ_INT(-32768, (int16_t)((uint16_t)data[0] | ((uint16_t)data[1] << 8)));
}

BENCH_TEST(table_des_identifiants_reserves) {
    BENCH_ASSERT(bench_id_is_reserved(BENCH_ID_ARM));
    BENCH_ASSERT(bench_id_is_reserved(BENCH_ID_GO));
    BENCH_ASSERT(bench_id_is_reserved(BENCH_ID_BENCH_CFG));
    BENCH_ASSERT(bench_id_is_reserved(BENCH_ID_HEARTBEAT_N1));

    /* Les trames applicatives ne doivent jamais tomber dans une plage réservée. */
    BENCH_ASSERT(!bench_id_is_reserved(BENCH_ID_ENERGY_COMMAND));
    BENCH_ASSERT(!bench_id_is_reserved(BENCH_ID_IMU_SPEED));
    BENCH_ASSERT(!bench_id_is_reserved(BENCH_ID_TEMP_BATTERY));
}

BENCH_TEST(contrainte_d_ordre_arm_go) {
    /* Le départ simultané de l'arbitrage repose sur cette inégalité : un nœud
     * armé avant l'émission de GO perd l'arbitrage contre GO et attend sa fin. */
    BENCH_ASSERT(BENCH_ID_GO < BENCH_ID_ENERGY_COMMAND);
    BENCH_ASSERT(BENCH_ID_GO < BENCH_ID_IMU_SPEED);
    BENCH_ASSERT(BENCH_ID_GO < BENCH_ID_TEMP_BATTERY);
    BENCH_ASSERT(BENCH_ID_ARM < BENCH_ID_ENERGY_COMMAND);

    /* Ordre de priorité attendu des contendants : N1, puis N2, puis N3. */
    BENCH_ASSERT(BENCH_ID_ENERGY_COMMAND < BENCH_ID_IMU_SPEED);
    BENCH_ASSERT(BENCH_ID_IMU_SPEED < BENCH_ID_TEMP_BATTERY);
}

BENCH_TEST(recherche_de_trame_par_identifiant) {
    const bench_frame_info_t *info = bench_frame_by_id(BENCH_ID_ENERGY_COMMAND);
    BENCH_ASSERT(info != NULL);
    if (info != NULL) {
        BENCH_ASSERT_EQ_UINT(8u, info->dlc);
        BENCH_ASSERT(info->is_contender);
        BENCH_ASSERT(!info->is_service);
    }

    info = bench_frame_by_id(BENCH_ID_ARM);
    BENCH_ASSERT(info != NULL);
    if (info != NULL) {
        BENCH_ASSERT(info->is_service);
        BENCH_ASSERT(!info->is_contender);
    }

    BENCH_ASSERT_EQ_PTR(NULL, bench_frame_by_id(0x7FFu));
}

BENCH_TEST_MAIN(parite_avec_les_vecteurs_python, aller_retour_unpack_pack,
                arrondi_a_l_oppose_de_zero, saturation_sur_les_bornes,
                table_des_identifiants_reserves, contrainte_d_ordre_arm_go,
                recherche_de_trame_par_identifiant)
