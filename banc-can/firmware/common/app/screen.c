/**
 * @file screen.c
 * @brief Écran de notes du nœud.
 */

#include "app/screen.h"

#include "app/traffic.h"
#include "util/font5x7.h"

#define CELL_W 6u  /* 5 pixels de glyphe + 1 d'espace */
#define COLS   (BENCH_SCREEN_W / CELL_W)

/* Barre de note : de la colonne 18 (x = 108) au bord droit. */
#define BAR_X  104u
#define BAR_W  (BENCH_SCREEN_W - BAR_X - 1u)

void bench_screen_clear(uint8_t *fb) {
    for (uint32_t i = 0u; i < BENCH_SCREEN_BYTES; i++) {
        fb[i] = 0u;
    }
}

void bench_screen_pixel(uint8_t *fb, uint8_t x, uint8_t y, int on) {
    if (x >= BENCH_SCREEN_W || y >= BENCH_SCREEN_H) {
        return;
    }
    uint8_t *byte = &fb[(uint32_t)(y / 8u) * BENCH_SCREEN_W + x];
    const uint8_t bit = (uint8_t)(1u << (y % 8u));
    *byte = on ? (uint8_t)(*byte | bit) : (uint8_t)(*byte & (uint8_t)~bit);
}

void bench_screen_text(uint8_t *fb, uint8_t col, uint8_t row, const char *text) {
    if (row >= BENCH_SCREEN_PAGES) {
        return;
    }
    for (; *text != '\0' && col < COLS; text++, col++) {
        const uint8_t *g = bench_font_glyph(*text);
        uint8_t *dst = &fb[(uint32_t)row * BENCH_SCREEN_W + (uint32_t)col * CELL_W];
        for (uint8_t i = 0u; i < BENCH_FONT_W; i++) {
            dst[i] = g[i];
        }
        dst[BENCH_FONT_W] = 0u;
    }
}

/** Écrit @p v (0 à 99999) aligné à droite sur @p width caractères. */
static void put_uint(char *out, uint32_t v, uint8_t width) {
    if (v > 99999u) {
        v = 99999u;
    }
    for (int i = (int)width - 1; i >= 0; i--) {
        out[i] = (char)('0' + (v % 10u));
        v /= 10u;
        if (v == 0u) {
            for (int j = i - 1; j >= 0; j--) {
                out[j] = ' ';
            }
            break;
        }
    }
}

/** Longueur utile d'un nombre, pour les compteurs écrits sans alignement. */
static uint8_t append_uint(char *out, uint32_t v) {
    char tmp[5];
    put_uint(tmp, v, 5u);
    uint8_t n = 0u;
    for (uint8_t i = 0u; i < 5u; i++) {
        if (tmp[i] != ' ') {
            out[n++] = tmp[i];
        }
    }
    return n;
}

static uint8_t append_str(char *out, const char *s) {
    uint8_t n = 0u;
    while (s[n] != '\0') {
        out[n] = s[n];
        n++;
    }
    return n;
}

static void score_line(uint8_t *fb, uint8_t row, const char *label, uint8_t score, int own) {
    char line[COLS + 1u];
    for (uint8_t i = 0u; i < COLS; i++) {
        line[i] = ' ';
    }
    line[COLS] = '\0';
    for (uint8_t i = 0u; label[i] != '\0' && i < 12u; i++) {
        line[i] = label[i];
    }
    if (own) {
        (void)append_str(&line[12], "EMET");
    } else if (score == BENCH_RXQ_NONE) {
        line[13] = '-';
        line[14] = '-';
    } else {
        put_uint(&line[12], score, 3u);
    }
    line[17] = '\0';
    bench_screen_text(fb, 0u, row, line);

    if (!own && score != BENCH_RXQ_NONE) {
        const uint8_t len = (uint8_t)(((uint32_t)score * BAR_W + 50u) / 100u);
        for (uint8_t x = 0u; x < len; x++) {
            for (uint8_t y = 1u; y < 7u; y++) {
                bench_screen_pixel(fb, (uint8_t)(BAR_X + x), (uint8_t)(row * 8u + y), 1);
            }
        }
    }
}

void bench_screen_quality(uint8_t *fb, const bench_node_t *node, const bench_can_status_t *status) {
    static const char *const labels[BENCH_TRAFFIC_KINDS] = {
        "ENERGY  N1", "IMU     N2", "TEMP    N3"};
    char line[COLS + 1u];
    uint8_t n;

    bench_screen_clear(fb);

    n = append_str(line, "N");
    line[n++] = (char)('0' + node->node_id % 10u);
    n = (uint8_t)(n + append_str(&line[n], "  NOTE DES TRAMES"));
    line[n] = '\0';
    bench_screen_text(fb, 0u, 0u, line);
    for (uint8_t x = 0u; x < BENCH_SCREEN_W; x++) {
        bench_screen_pixel(fb, x, 11u, 1);
    }

    const bench_rxq_window_t *w = &node->rxq.last;
    for (uint8_t k = 0u; k < BENCH_TRAFFIC_KINDS; k++) {
        score_line(fb, (uint8_t)(2u + k), labels[k], w->score[k], node->app_kind == (int8_t)k);
    }
    score_line(fb, 5u, "HEARTBEAT", w->score_heartbeat, 0);

    n = append_str(line, "PERD ");
    n = (uint8_t)(n + append_uint(&line[n], node->rxq.total_lost));
    n = (uint8_t)(n + append_str(&line[n], " ABIM "));
    n = (uint8_t)(n + append_uint(&line[n], node->rxq.total_bad));
    n = (uint8_t)(n + append_str(&line[n], " RET "));
    n = (uint8_t)(n + append_uint(&line[n], node->rxq.total_late));
    line[(n < COLS) ? n : COLS] = '\0';
    bench_screen_text(fb, 0u, 6u, line);

    static const char *const states[4] = {"ACTIF", "ALERTE", "PASSIF", "BUS-OFF"};
    n = append_str(line, states[(uint8_t)status->state & 3u]);
    n = (uint8_t)(n + append_str(&line[n], " TEC "));
    n = (uint8_t)(n + append_uint(&line[n], status->tec));
    n = (uint8_t)(n + append_str(&line[n], " REC "));
    n = (uint8_t)(n + append_uint(&line[n], status->rec));
    line[(n < COLS) ? n : COLS] = '\0';
    bench_screen_text(fb, 0u, 7u, line);
}
