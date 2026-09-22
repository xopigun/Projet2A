/**
 * @file clock.h
 * @brief Configuration et qualification de l'horloge du noeud.
 */

#ifndef BENCH_CLOCK_H
#define BENCH_CLOCK_H

#include <stdbool.h>
#include <stdint.h>

/** @brief Configure PLL, SYSCLK et l'horloge noyau du FDCAN. */
void bench_clock_config(void);

/**
 * @brief Vrai si la reference d'horloge est conforme pour le CAN.
 *
 * Faux en repli HSI. Remonte dans le bit @c clock_not_qualified du heartbeat et
 * affiche sur l'ecran, ce qui interdit tout verdict de reussite.
 */
bool bench_clock_is_qualified(void);

/** @brief Libelle court de la source d'horloge, pour l'ecran et le journal. */
const char *bench_clock_source_name(void);

/** @brief Horloge noyau du FDCAN effectivement obtenue, en Hz. */
uint32_t bench_clock_fdcan_hz(void);

/** @brief Appelee si la configuration d'horloge echoue ; ne revient jamais. */
void bench_clock_failure(void);

#endif /* BENCH_CLOCK_H */
