/**
 * @file screen.h
 * @brief Écran de notes du nœud, rendu dans une image 128 × 64 de l'OLED SSD1306.
 *
 * L'image suit la mémoire du SSD1306 : 8 pages de 128 octets, chaque octet portant
 * 8 pixels verticaux (bit 0 en haut). Le port n'a plus qu'à l'envoyer page par page.
 *
 *     N4  NOTE DES TRAMES
 *     ---------------------
 *     ENERGY  N1  100 ######
 *     IMU     N2   98 #####
 *     TEMP    N3   --
 *     HEARTB.     100 ######
 *     P:0 A:0 R:0          (perdues, abîmées, en retard)
 *     ACTIF TEC0 REC0
 *
 * « EMET » remplace la note de la trame que le nœud émet lui-même ; « -- » signale
 * qu'aucune trame de ce type n'est arrivée pendant la dernière fenêtre.
 *
 * Aucune dépendance HAL : testé nativement (tests_host/test_screen.c).
 */

#ifndef BENCH_APP_SCREEN_H
#define BENCH_APP_SCREEN_H

#include <stdint.h>

#include "app/node.h"
#include "can_if.h"

#define BENCH_SCREEN_W     128u
#define BENCH_SCREEN_H     64u
#define BENCH_SCREEN_PAGES 8u
#define BENCH_SCREEN_BYTES (BENCH_SCREEN_W * BENCH_SCREEN_PAGES)

/** @brief Efface l'image. */
void bench_screen_clear(uint8_t *fb);

/** @brief Écrit @p text en colonne de caractère @p col (6 pixels) et page @p row. */
void bench_screen_text(uint8_t *fb, uint8_t col, uint8_t row, const char *text);

/** @brief Allume ou éteint un pixel. */
void bench_screen_pixel(uint8_t *fb, uint8_t x, uint8_t y, int on);

/** @brief Dessine l'écran de notes complet du nœud. */
void bench_screen_quality(uint8_t *fb, const bench_node_t *node, const bench_can_status_t *status);

#endif /* BENCH_APP_SCREEN_H */
