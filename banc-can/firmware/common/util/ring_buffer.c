/**
 * @file ring_buffer.c
 * @brief Réalisation du tampon circulaire producteur/consommateur unique.
 */

#include "util/ring_buffer.h"

#include <string.h>

#define RING_MASK (BENCH_RING_CAPACITY - 1u)

void bench_ring_init(bench_ring_t *ring) {
    memset(ring, 0, sizeof(*ring));
}

bool bench_ring_push(bench_ring_t *ring, const bench_can_frame_t *frame) {
    const uint32_t head = ring->head;
    const uint32_t next = (head + 1u) & RING_MASK;

    /* Une case est laissée libre en permanence : c'est ce qui distingue le
     * tampon plein du tampon vide sans compteur partagé entre les deux
     * contextes, donc sans section critique. */
    if (next == ring->tail) {
        if (ring->dropped != UINT16_MAX) {
            ring->dropped++;
        }
        return false;
    }

    ring->frames[head] = *frame;
    /* La trame est intégralement écrite avant que head ne la rende visible. */
    ring->head = next;
    return true;
}

bool bench_ring_pop(bench_ring_t *ring, bench_can_frame_t *frame) {
    const uint32_t tail = ring->tail;

    if (tail == ring->head) {
        return false;
    }

    *frame = ring->frames[tail];
    ring->tail = (tail + 1u) & RING_MASK;
    return true;
}

uint32_t bench_ring_count(const bench_ring_t *ring) {
    return (ring->head - ring->tail) & RING_MASK;
}

bool bench_ring_is_full(const bench_ring_t *ring) {
    return ((ring->head + 1u) & RING_MASK) == ring->tail;
}

uint16_t bench_ring_dropped(const bench_ring_t *ring) {
    return ring->dropped;
}
