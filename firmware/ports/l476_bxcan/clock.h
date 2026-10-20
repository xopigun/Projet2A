/**
 * @file clock.h
 * @brief Configuration et qualification de l'horloge du pont CAN-USB (L476).
 *
 * Meme interface que les ports G431 et F103.
 */

#ifndef BENCH_CLOCK_H
#define BENCH_CLOCK_H

#include <stdbool.h>
#include <stdint.h>

/** @brief Configure SYSCLK et PCLK1 a 80 MHz, sur le HSE si present, sinon le HSI. */
void bench_clock_config(void);

/** @brief Vrai si la reference d'horloge est un quartz (HSE), donc valable pour le CAN. */
bool bench_clock_is_qualified(void);

/** @brief Libelle court de la source d'horloge. */
const char *bench_clock_source_name(void);

/** @brief Horloge du controleur CAN effectivement obtenue, en Hz (PCLK1). */
uint32_t bench_clock_can_hz(void);

/**
 * @brief Arret fatal : LD2 clignote vite, plus rien n'est emis.
 *
 * Ne revient jamais. Le port COM virtuel porte le flux slcan : on n'y ecrit
 * aucun texte, qui serait pris pour des trames par le PC.
 */
void bench_fatal(const char *reason);

/** @brief Echec de demarrage du PLL ; appelle bench_fatal(). */
void bench_clock_failure(void);

#endif /* BENCH_CLOCK_H */
