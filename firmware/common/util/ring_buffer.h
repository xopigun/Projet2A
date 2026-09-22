/**
 * @file ring_buffer.h
 * @brief Tampon circulaire de trames, écrit par l'ISR et lu par la boucle principale.
 *
 * L'ISR de réception ne fait que recopier la trame horodatée ici ; tout le reste
 * — décodage, affichage, capteurs — se passe dans la boucle principale. C'est ce
 * qui empêche le banc de mesurer ses propres défauts logiciels au lieu du
 * comportement du bus.
 *
 * Modèle de concurrence : un seul producteur (l'ISR) et un seul consommateur (la
 * boucle principale). Les indices sont manipulés de façon à ce qu'aucune section
 * critique ne soit nécessaire :
 *
 *  - le producteur ne modifie que @c head, le consommateur que @c tail ;
 *  - chacun ne lit l'indice de l'autre qu'une seule fois par opération ;
 *  - la capacité est une puissance de deux, donc l'avance d'indice est un
 *    masquage, atomique sur Cortex-M.
 *
 * En cas de saturation, la trame est **rejetée** et @c dropped est incrémenté :
 * on ne recouvre jamais une trame déjà reçue, car cela fausserait l'ordre des
 * trames dont dépend la mesure du rang d'arbitrage.
 */

#ifndef BENCH_RING_BUFFER_H
#define BENCH_RING_BUFFER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "can_if.h"

/** Capacité du tampon, en trames. Doit être une puissance de deux. */
#ifndef BENCH_RING_CAPACITY
#define BENCH_RING_CAPACITY 64u
#endif

#if (BENCH_RING_CAPACITY & (BENCH_RING_CAPACITY - 1u)) != 0u
#error "BENCH_RING_CAPACITY doit etre une puissance de deux"
#endif

typedef struct {
    bench_can_frame_t frames[BENCH_RING_CAPACITY];
    volatile uint32_t head;     /**< écrit par le producteur seul */
    volatile uint32_t tail;     /**< écrit par le consommateur seul */
    volatile uint16_t dropped;  /**< trames rejetées faute de place */
} bench_ring_t;

/** @brief Remet le tampon à zéro. À n'appeler qu'avec les interruptions coupées. */
void bench_ring_init(bench_ring_t *ring);

/**
 * @brief Dépose une trame. Appelée depuis l'ISR de réception.
 * @return false si le tampon est plein ; @c dropped est alors incrémenté.
 */
bool bench_ring_push(bench_ring_t *ring, const bench_can_frame_t *frame);

/**
 * @brief Retire la plus ancienne trame. Appelée depuis la boucle principale.
 * @return false si le tampon est vide.
 */
bool bench_ring_pop(bench_ring_t *ring, bench_can_frame_t *frame);

/** @brief Nombre de trames en attente. */
uint32_t bench_ring_count(const bench_ring_t *ring);

/** @brief Vrai si le tampon ne peut plus accepter de trame. */
bool bench_ring_is_full(const bench_ring_t *ring);

/** @brief Nombre de trames rejetées depuis l'initialisation. */
uint16_t bench_ring_dropped(const bench_ring_t *ring);

#endif /* BENCH_RING_BUFFER_H */
