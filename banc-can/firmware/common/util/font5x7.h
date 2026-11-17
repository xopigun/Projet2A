/**
 * @file font5x7.h
 * @brief Police 5 × 7 pixels, ASCII 0x20 à 0x7E, colonnes codées du bit 0 (haut) au bit 6.
 */

#ifndef BENCH_FONT5X7_H
#define BENCH_FONT5X7_H

#include <stdint.h>

#define BENCH_FONT_FIRST 0x20u
#define BENCH_FONT_LAST  0x7Eu
#define BENCH_FONT_W     5u

/** @brief Les 5 colonnes du caractère @p c ; un '?' pour un caractère hors police. */
const uint8_t *bench_font_glyph(char c);

#endif /* BENCH_FONT5X7_H */
