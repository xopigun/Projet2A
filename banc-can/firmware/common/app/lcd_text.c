/**
 * @file lcd_text.c
 * @brief Mise en forme du texte des afficheurs LCD 16x2.
 */

#include "app/lcd_text.h"

#include <stdio.h>

/** Le compteur de trames reçues tient sur 4 colonnes. */
#define RX_COUNT_MODULO 10000u

/** Durée de silence affichée au plus, en secondes : 3 colonnes. */
#define SILENT_S_MAX 999u

/** Colonnes de la ligne 2 réservées aux données, avant l'état du contrôleur. */
#define DATA_COLS 8u

/**
 * Recopie @p text dans une ligne, complétée par des espaces et tronquée à
 * BENCH_LCD_COLS. L'écran ne garde ainsi jamais la fin d'un texte précédent.
 */
static void set_row(char *row, const char *text) {
    uint32_t col = 0u;

    while (col < BENCH_LCD_COLS && text[col] != '\0') {
        row[col] = text[col];
        col++;
    }
    while (col < BENCH_LCD_COLS) {
        row[col] = ' ';
        col++;
    }
    row[BENCH_LCD_COLS] = '\0';
}

/** Octet affichable tel quel par la ROM A00 du HD44780, sinon un point. */
static char printable(uint8_t byte) {
    return (byte >= 0x20u && byte <= 0x7Du && byte != 0x5Cu) ? (char)byte : '.';
}

const char *bench_lcd_state_name(bench_can_state_t state) {
    switch (state) {
        case BENCH_CAN_ERROR_ACTIVE:
            return "ACTIF";
        case BENCH_CAN_ERROR_WARNING:
            return "WARNING";
        case BENCH_CAN_ERROR_PASSIVE:
            return "PASSIF";
        case BENCH_CAN_BUS_OFF:
            return "BUS-OFF";
        default:
            return "?";
    }
}

void bench_lcd_text_splash(bench_lcd_text_t *out, uint8_t node_id, uint16_t tx_id,
                           const char *clock_name) {
    char line[24];

    (void)snprintf(line, sizeof(line), "N%u TX %03X", (unsigned)node_id, (unsigned)tx_id);
    set_row(out->row[0], line);
    set_row(out->row[1], clock_name);
}

void bench_lcd_text_rx(bench_lcd_text_t *out, const bench_lcd_rx_view_t *view) {
    char line[24];
    char data[DATA_COLS + 1u];
    uint32_t used = 0u;

    if (!view->has_rx) {
        set_row(out->row[0], "RX en attente...");
        (void)snprintf(line, sizeof(line), "TX %03X %9s", (unsigned)view->tx_id,
                       bench_lcd_state_name(view->state));
        set_row(out->row[1], line);
        return;
    }

    const bench_can_frame_t *rx = &view->last_rx;
    const uint8_t dlc = (rx->dlc > 8u) ? 8u : rx->dlc;

    if (view->silent_ms >= BENCH_LCD_SILENT_MS) {
        uint32_t seconds = view->silent_ms / 1000u;
        if (seconds > SILENT_S_MAX) {
            seconds = SILENT_S_MAX;
        }
        (void)snprintf(line, sizeof(line), "RX %03X muet %3lus", (unsigned)rx->id,
                       (unsigned long)seconds);
    } else {
        (void)snprintf(line, sizeof(line), "RX %03X DLC%u %4lu", (unsigned)rx->id,
                       (unsigned)dlc, (unsigned long)(view->rx_count % RX_COUNT_MODULO));
    }
    set_row(out->row[0], line);

    /* Huit octets au plus : ils tiennent tous dans les colonnes de données. */
    for (; used < dlc; used++) {
        data[used] = printable(rx->data[used]);
    }
    data[used] = '\0';
    (void)snprintf(line, sizeof(line), "%-8s %7s", data, bench_lcd_state_name(view->state));
    set_row(out->row[1], line);
}
