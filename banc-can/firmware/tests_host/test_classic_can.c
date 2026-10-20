/**
 * @file test_classic_can.c
 * @brief Vérifie le verrouillage du protocole en CAN 2.0A classic.
 *
 * Le périphérique du G431 s'appelle FDCAN, mais le protocole utilisé par le banc
 * est **CAN 2.0A classic** : identifiants 11 bits, charge utile de 8 octets au
 * plus, pas de commutation de débit.
 *
 * Trois garde-fous existent, à trois moments différents :
 *
 * 1. **à la génération** — le validateur de l'ICD refuse un identifiant hors
 *    11 bits ou un DLC supérieur à 8 (testé côté Python) ;
 * 2. **à la compilation** — les `_Static_assert` de `icd_gen.h` cassent le build
 *    si une constante générée s'en écarte ; c'est ce que contrôle ce fichier,
 *    puisqu'il compile ;
 * 3. **à l'exécution** — `tx_common()` refuse d'émettre une trame non conforme,
 *    et l'ISR compte les trames FD ou à identifiant 29 bits reçues.
 *
 * Ce test couvre les niveaux 1 et 2 sur les constantes réellement générées. Le
 * niveau 3 dépend du matériel et relève de la mise en route (docs/bringup.md).
 */

#include "bench_test.h"
#include "icd_gen.h"
#include "protocol/heartbeat.h"

BENCH_TEST(constantes_de_verrouillage_definies) {
    /* Si ces constantes disparaissaient du code généré, les _Static_assert
     * disparaîtraient avec elles sans que rien ne le signale. */
    BENCH_ASSERT_EQ_UINT(8u, BENCH_CLASSIC_MAX_DLC);
    BENCH_ASSERT_EQ_UINT(0x7FFu, BENCH_CLASSIC_MAX_ID);
}

BENCH_TEST(tous_les_identifiants_tiennent_sur_11_bits) {
    for (size_t i = 0u; i < BENCH_BENCH_FRAME_COUNT; i++) {
        const bench_frame_info_t *frame = &bench_bench_frames[i];
        if (frame->can_id > BENCH_CLASSIC_MAX_ID) {
            BENCH_FAIL("%s : identifiant 0x%X hors des 11 bits", frame->name,
                       (unsigned)frame->can_id);
        }
    }
}

BENCH_TEST(tous_les_dlc_tiennent_en_classic) {
    for (size_t i = 0u; i < BENCH_BENCH_FRAME_COUNT; i++) {
        const bench_frame_info_t *frame = &bench_bench_frames[i];
        if (frame->dlc > BENCH_CLASSIC_MAX_DLC) {
            BENCH_FAIL("%s : DLC %u impossible en CAN 2.0 classic", frame->name,
                       (unsigned)frame->dlc);
        }
    }
}

BENCH_TEST(tous_les_profils_restent_classic) {
    /* Un profil réseau ne doit pas pouvoir faire sortir un identifiant des
     * 11 bits : c'est le risque d'un décalage de plage mal choisi. */
    for (size_t i = 0u; i < BENCH_ALT_HIGH_FRAME_COUNT; i++) {
        if (bench_alt_high_frames[i].can_id > BENCH_CLASSIC_MAX_ID) {
            BENCH_FAIL("profil alt_high : %s hors des 11 bits",
                       bench_alt_high_frames[i].name);
        }
    }
}

BENCH_TEST(compteurs_de_trames_non_conformes_remontes) {
    /* Une trame FD ou à identifiant 29 bits sur le bus doit se voir dans le
     * heartbeat, et non être ignorée silencieusement. */
    bench_heartbeat_inputs_t inputs = {0};
    bench_can_status_t status = {0};
    bench_ring_t ring;
    uint8_t data[8];
    bench_heartbeat_t decoded;

    bench_ring_init(&ring);
    status.non_classic_rx = 3u;
    status.ext_id_rx = 7u;

    bench_heartbeat_pack_frame(&inputs, &status, &ring, data);
    bench_heartbeat_unpack(&decoded, data);

    BENCH_ASSERT_EQ_UINT(3u, decoded.non_classic_rx);
    BENCH_ASSERT_EQ_UINT(7u, decoded.ext_id_rx);
}

BENCH_TEST(compteurs_saturent_sans_reboucler) {
    /* Les compteurs du heartbeat sont sur 8 bits : ils doivent saturer, sinon un
     * débordement massif repasserait par zéro et se lirait comme « sain ». */
    bench_heartbeat_inputs_t inputs = {0};
    bench_can_status_t status = {0};
    bench_ring_t ring;
    uint8_t data[8];
    bench_heartbeat_t decoded;

    bench_ring_init(&ring);
    status.rx_fifo_lost = 5000u;  /* bien au-delà de 255 */

    bench_heartbeat_pack_frame(&inputs, &status, &ring, data);
    bench_heartbeat_unpack(&decoded, data);

    BENCH_ASSERT_EQ_UINT(255u, decoded.rx_fifo_lost);
}

BENCH_TEST_MAIN(constantes_de_verrouillage_definies, tous_les_identifiants_tiennent_sur_11_bits,
                tous_les_dlc_tiennent_en_classic, tous_les_profils_restent_classic,
                compteurs_de_trames_non_conformes_remontes, compteurs_saturent_sans_reboucler)
