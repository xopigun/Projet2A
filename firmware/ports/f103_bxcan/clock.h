/**
 * @file clock.h
 * @brief Configuration et qualification de l'horloge du noeud N4.
 *
 * Meme interface que le port G431 : le programme principal (entry/) ne voit
 * aucune difference entre les deux cartes.
 */

#ifndef BENCH_CLOCK_H
#define BENCH_CLOCK_H

#include <stdbool.h>
#include <stdint.h>

/** @brief Configure le PLL sur le quartz : SYSCLK 72 MHz, PCLK1 36 MHz. */
void bench_clock_config(void);

/** @brief Vrai si la reference d'horloge est conforme pour le CAN (quartz). */
bool bench_clock_is_qualified(void);

/** @brief Libelle court de la source d'horloge, pour l'ecran et le journal. */
const char *bench_clock_source_name(void);

/** @brief Horloge du controleur CAN effectivement obtenue, en Hz (PCLK1). */
uint32_t bench_clock_can_hz(void);

/**
 * @brief Arret fatal, visible : message sur USART1 et LED PC13 qui clignote vite.
 *
 * Ne revient jamais. Le noeud cesse toute emission : un noeud mal configure ne
 * doit pas perturber le bus avec un temps de bit faux.
 */
void bench_fatal(const char *reason);

/** @brief Echec de demarrage du quartz ou du PLL ; appelle bench_fatal(). */
void bench_clock_failure(void);

#endif /* BENCH_CLOCK_H */
