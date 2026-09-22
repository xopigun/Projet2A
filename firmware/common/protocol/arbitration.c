/**
 * @file arbitration.c
 * @brief Machine d'états ARM/GO et comptage du rang d'arbitrage.
 */

#include "protocol/arbitration.h"

#include <string.h>

void bench_arb_init(bench_arb_t *arb, uint16_t arm_id, uint16_t go_id, uint16_t self_id,
                    bool is_contender) {
    memset(arb, 0, sizeof(*arb));
    arb->arm_id = arm_id;
    arb->go_id = go_id;
    arb->self_id = self_id;
    arb->is_contender = is_contender;
    arb->phase = BENCH_ARB_IDLE;
}

/** Clôt le cycle courant en l'enregistrant comme invalide. */
static void abandon_cycle(bench_arb_t *arb) {
    if (arb->phase != BENCH_ARB_IDLE) {
        arb->counters.invalid++;
    }
    arb->phase = BENCH_ARB_IDLE;
    arb->seen_contenders = 0u;
}

bool bench_arb_on_frame(bench_arb_t *arb, const bench_can_frame_t *frame,
                        bool is_contender_frame) {
    if (frame->id == arb->arm_id) {
        /* Un ARM alors qu'un cycle est en cours signifie que le précédent n'est
         * jamais allé à son terme : on le compte comme invalide plutôt que de
         * le laisser polluer l'histogramme. */
        if (arb->phase != BENCH_ARB_IDLE && arb->phase != BENCH_ARB_DONE) {
            abandon_cycle(arb);
        }
        arb->counters.arm_rx++;
        arb->seen_contenders = 0u;
        arb->phase = BENCH_ARB_ARMED;
        return arb->is_contender;
    }

    if (frame->id == arb->go_id) {
        if (arb->phase != BENCH_ARB_ARMED) {
            /* GO sans ARM préalable : ce nœud a raté la fenêtre d'armement.
             * Le cycle ne doit pas être comptabilisé. */
            abandon_cycle(arb);
            return false;
        }
        arb->phase = BENCH_ARB_COUNTING;
        arb->seen_contenders = 0u;
        return false;
    }

    /* Toute trame contendante reçue après GO et avant notre propre émission
     * nous précède : elle nous a battus à l'arbitrage. */
    if (arb->phase == BENCH_ARB_COUNTING && is_contender_frame && frame->id != arb->self_id) {
        if (arb->seen_contenders < UINT8_MAX) {
            arb->seen_contenders++;
        }
    }

    return false;
}

void bench_arb_on_own_tx(bench_arb_t *arb) {
    if (!arb->is_contender || arb->phase != BENCH_ARB_COUNTING) {
        return;
    }

    const uint32_t rank = (uint32_t)arb->seen_contenders + 1u;

    arb->counters.cycles++;
    if (rank == 1u) {
        arb->counters.won++;
    } else {
        arb->counters.lost++;
    }

    if (rank <= BENCH_MAX_RANK) {
        arb->counters.rank_histogram[rank]++;
        arb->last_rank = (uint8_t)rank;
    } else {
        /* Rang aberrant : plus de contendants qu'il n'en existe. On le range en
         * case 0 pour qu'il reste visible plutôt que d'être écrasé. */
        arb->counters.rank_histogram[0]++;
        arb->last_rank = 0u;
    }

    arb->phase = BENCH_ARB_DONE;
}

uint8_t bench_arb_last_rank(const bench_arb_t *arb) {
    return arb->last_rank;
}

bool bench_arb_all_cycles_at_rank(const bench_arb_t *arb, uint8_t expected_rank) {
    if (arb->counters.cycles == 0u || expected_rank > BENCH_MAX_RANK) {
        return false;
    }
    return arb->counters.rank_histogram[expected_rank] == arb->counters.cycles;
}
