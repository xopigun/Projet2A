/**
 * @file lcd_text.h
 * @brief Texte des afficheurs LCD 16x2 : mise en forme, sans aucun accès matériel.
 *
 * Le pilote HD44780 (`ports/g431_fdcan/lcd.c`) ne fait que recopier ce texte sur
 * l'écran. Toute la décision de « quoi afficher » est ici, testée sur l'hôte
 * (`tests_host/test_lcd_text.c`).
 *
 * Écran de réception, deux formes selon l'âge de la dernière trame :
 *
 * @code
 *   +----------------+      +----------------+
 *   |RX 20F DLC4  123|      |RX 20F muet  12s|   <- plus de trame depuis 1 s
 *   |Test       ACTIF|      |Test      PASSIF|
 *   +----------------+      +----------------+
 * @endcode
 *
 * Ligne 1 : identifiant et DLC de la dernière trame reçue, puis le nombre de
 * trames reçues (modulo 10 000) : il tourne tant que le bus vit. Ligne 2 : les
 * données en ASCII, puis l'état du contrôleur lu dans ses registres.
 *
 * Seuls les caractères 0x20 à 0x7D sont affichés tels quels, hors 0x5C : la ROM
 * A00 du HD44780 remplace « \ » par « ¥ » et 0x7E, 0x7F par des flèches. Tout
 * autre octet devient un point. Pour la même raison, aucun texte n'est accentué.
 */

#ifndef BENCH_LCD_TEXT_H
#define BENCH_LCD_TEXT_H

#include <stdbool.h>
#include <stdint.h>

#include "can_if.h"

#define BENCH_LCD_COLS 16u
#define BENCH_LCD_ROWS 2u

/** Au-delà de ce délai sans trame, la ligne 1 passe en forme « muet ». */
#define BENCH_LCD_SILENT_MS 1000u

/** Contenu complet de l'écran : deux lignes de 16 caractères, terminées par NUL. */
typedef struct {
    char row[BENCH_LCD_ROWS][BENCH_LCD_COLS + 1u];
} bench_lcd_text_t;

/** Ce que l'écran de réception doit montrer. */
typedef struct {
    uint16_t          tx_id;     /**< identifiant émis par ce nœud, montré en attente */
    bool              has_rx;    /**< au moins une trame reçue depuis le démarrage */
    bench_can_frame_t last_rx;   /**< dernière trame reçue */
    uint32_t          rx_count;  /**< trames reçues depuis le démarrage */
    uint32_t          silent_ms; /**< temps écoulé depuis la dernière trame reçue */
    bench_can_state_t state;     /**< état du contrôleur */
} bench_lcd_rx_view_t;

/**
 * @brief Écran d'accueil, montré au démarrage.
 *
 * Ligne 1 : `N1 TX 0F0`. Ligne 2 : la source d'horloge, soit
 * `HSI - NON VALIDE` en repli HSI — le bandeau exigé par docs/PLAN.md §3.2.
 */
void bench_lcd_text_splash(bench_lcd_text_t *out, uint8_t node_id, uint16_t tx_id,
                           const char *clock_name);

/** @brief Écran de réception : dernière trame reçue et état du contrôleur. */
void bench_lcd_text_rx(bench_lcd_text_t *out, const bench_lcd_rx_view_t *view);

/** @brief Libellé de l'état du contrôleur, 7 caractères au plus. */
const char *bench_lcd_state_name(bench_can_state_t state);

#endif /* BENCH_LCD_TEXT_H */
