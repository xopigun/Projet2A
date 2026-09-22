/**
 * @file test_ring_buffer.c
 * @brief Tests du tampon circulaire ISR -> boucle principale.
 */

#include "bench_test.h"
#include "util/ring_buffer.h"

static bench_can_frame_t frame_with(uint16_t id, uint32_t timestamp) {
    bench_can_frame_t frame = {0};
    frame.id = id;
    frame.dlc = 8u;
    frame.timestamp_us = timestamp;
    frame.data[0] = (uint8_t)(id & 0xFFu);
    return frame;
}

BENCH_TEST(vide_a_l_initialisation) {
    bench_ring_t ring;
    bench_can_frame_t frame;

    bench_ring_init(&ring);
    BENCH_ASSERT_EQ_UINT(0u, bench_ring_count(&ring));
    BENCH_ASSERT(!bench_ring_is_full(&ring));
    BENCH_ASSERT(!bench_ring_pop(&ring, &frame));
    BENCH_ASSERT_EQ_UINT(0u, bench_ring_dropped(&ring));
}

BENCH_TEST(conserve_l_ordre_de_reception) {
    /* L'ordre est essentiel : le rang d'arbitrage se déduit de l'ordre des
     * trames reçues entre la fin de GO et notre propre émission. */
    bench_ring_t ring;
    bench_can_frame_t frame;

    bench_ring_init(&ring);
    for (uint16_t i = 0u; i < 10u; i++) {
        const bench_can_frame_t pushed = frame_with((uint16_t)(0x100u + i), i * 100u);
        BENCH_ASSERT(bench_ring_push(&ring, &pushed));
    }
    BENCH_ASSERT_EQ_UINT(10u, bench_ring_count(&ring));

    for (uint16_t i = 0u; i < 10u; i++) {
        BENCH_ASSERT(bench_ring_pop(&ring, &frame));
        BENCH_ASSERT_EQ_UINT(0x100u + i, frame.id);
        BENCH_ASSERT_EQ_UINT(i * 100u, frame.timestamp_us);
    }
    BENCH_ASSERT(!bench_ring_pop(&ring, &frame));
}

BENCH_TEST(rejette_sans_ecraser_quand_plein) {
    /* En saturation on rejette la nouvelle trame ; on n'écrase jamais une trame
     * déjà reçue, ce qui fausserait l'ordre. */
    bench_ring_t ring;
    bench_can_frame_t frame;

    bench_ring_init(&ring);

    /* Une case reste libre en permanence : la capacité utile vaut N - 1. */
    const uint32_t usable = BENCH_RING_CAPACITY - 1u;
    for (uint32_t i = 0u; i < usable; i++) {
        const bench_can_frame_t pushed = frame_with((uint16_t)i, i);
        BENCH_ASSERT(bench_ring_push(&ring, &pushed));
    }
    BENCH_ASSERT(bench_ring_is_full(&ring));
    BENCH_ASSERT_EQ_UINT(usable, bench_ring_count(&ring));

    const bench_can_frame_t rejected = frame_with(0x7FFu, 999u);
    BENCH_ASSERT(!bench_ring_push(&ring, &rejected));
    BENCH_ASSERT_EQ_UINT(1u, bench_ring_dropped(&ring));

    /* La plus ancienne trame est intacte. */
    BENCH_ASSERT(bench_ring_pop(&ring, &frame));
    BENCH_ASSERT_EQ_UINT(0u, frame.id);
}

BENCH_TEST(compteur_de_rejets_sature) {
    /* Le compteur est remonté sur 16 bits dans le heartbeat : il doit saturer
     * et non reboucler, sans quoi un débordement massif passerait inaperçu. */
    bench_ring_t ring;
    bench_ring_init(&ring);

    for (uint32_t i = 0u; i < BENCH_RING_CAPACITY; i++) {
        const bench_can_frame_t pushed = frame_with((uint16_t)i, i);
        (void)bench_ring_push(&ring, &pushed);
    }
    for (uint32_t i = 0u; i < 70000u; i++) {
        const bench_can_frame_t pushed = frame_with(0x123u, i);
        (void)bench_ring_push(&ring, &pushed);
    }
    BENCH_ASSERT_EQ_UINT(UINT16_MAX, bench_ring_dropped(&ring));
}

BENCH_TEST(reboucle_indefiniment) {
    /* Usage réel : production et consommation alternées sur bien plus d'un tour,
     * pour éprouver le rebouclage des indices. */
    bench_ring_t ring;
    bench_can_frame_t frame;

    bench_ring_init(&ring);
    for (uint32_t i = 0u; i < BENCH_RING_CAPACITY * 10u; i++) {
        const bench_can_frame_t pushed = frame_with((uint16_t)(i & 0x7FFu), i);
        BENCH_ASSERT(bench_ring_push(&ring, &pushed));
        BENCH_ASSERT(bench_ring_pop(&ring, &frame));
        BENCH_ASSERT_EQ_UINT(i & 0x7FFu, frame.id);
        BENCH_ASSERT_EQ_UINT(0u, bench_ring_count(&ring));
    }
    BENCH_ASSERT_EQ_UINT(0u, bench_ring_dropped(&ring));
}

BENCH_TEST(remplissage_partiel_puis_vidage) {
    bench_ring_t ring;
    bench_can_frame_t frame;

    bench_ring_init(&ring);
    for (uint32_t tour = 0u; tour < 5u; tour++) {
        for (uint32_t i = 0u; i < 20u; i++) {
            const bench_can_frame_t pushed = frame_with((uint16_t)i, tour);
            BENCH_ASSERT(bench_ring_push(&ring, &pushed));
        }
        BENCH_ASSERT_EQ_UINT(20u, bench_ring_count(&ring));
        for (uint32_t i = 0u; i < 20u; i++) {
            BENCH_ASSERT(bench_ring_pop(&ring, &frame));
            BENCH_ASSERT_EQ_UINT(i, frame.id);
        }
        BENCH_ASSERT_EQ_UINT(0u, bench_ring_count(&ring));
    }
}

BENCH_TEST_MAIN(vide_a_l_initialisation, conserve_l_ordre_de_reception,
                rejette_sans_ecraser_quand_plein, compteur_de_rejets_sature,
                reboucle_indefiniment, remplissage_partiel_puis_vidage)
