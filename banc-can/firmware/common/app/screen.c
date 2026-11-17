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

/**
 * Ligne de texte bornée à COLS caractères. Tout ajout au-delà est ignoré : une
 * ligne trop longue est tronquée à l'écran, jamais écrite hors du tampon.
 * (Les compteurs à 5 chiffres débordaient le tampon d'une ligne et écrasaient
 * la pile : numéro de nœud et état corrompus, vus sur le banc le 17/11/2026.)
 */
typedef struct {
    char    text[COLS + 1u];
    uint8_t len;
} line_t;

static void line_init(line_t *l) {
    l->len = 0u;
    l->text[0] = '\0';
}

static void line_char(line_t *l, char c) {
    if (l->len < COLS) {
        l->text[l->len++] = c;
        l->text[l->len] = '\0';
    }
}

static void line_str(line_t *l, const char *s) {
    for (; *s != '\0'; s++) {
        line_char(l, *s);
    }
}

/** Nombre en 4 caractères au plus : 0 à 9999, puis « 10k » à « 99k ». */
static void line_count(line_t *l, uint32_t v) {
    char tmp[5];
    const int kilo = (v >= 10000u);
    put_uint(tmp, kilo ? ((v > 99999u ? 99999u : v) / 1000u) : v, 4u);
    for (uint8_t i = 0u; i < 4u; i++) {
        if (tmp[i] != ' ') {
            line_char(l, tmp[i]);
        }
    }
    if (kilo) {
        line_char(l, 'k');
    }
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
        line[12] = 'E';
        line[13] = 'M';
        line[14] = 'E';
        line[15] = 'T';
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
    line_t line;

    bench_screen_clear(fb);

    line_init(&line);
    line_char(&line, 'N');
    line_char(&line, (char)('0' + node->node_id % 10u));
    line_str(&line, "  NOTE DES TRAMES");
    bench_screen_text(fb, 0u, 0u, line.text);
    for (uint8_t x = 0u; x < BENCH_SCREEN_W; x++) {
        bench_screen_pixel(fb, x, 11u, 1);
    }

    const bench_rxq_window_t *w = &node->rxq.last;
    for (uint8_t k = 0u; k < BENCH_TRAFFIC_KINDS; k++) {
        score_line(fb, (uint8_t)(2u + k), labels[k], w->score[k], node->app_kind == (int8_t)k);
    }
    score_line(fb, 5u, "HEARTBEAT", w->score_heartbeat, 0);

    /* Perdues, abîmées, en retard depuis le démarrage : « P:12 A:3 R:0 ». */
    line_init(&line);
    line_str(&line, "P:");
    line_count(&line, node->rxq.total_lost);
    line_str(&line, " A:");
    line_count(&line, node->rxq.total_bad);
    line_str(&line, " R:");
    line_count(&line, node->rxq.total_late);
    bench_screen_text(fb, 0u, 6u, line.text);

    static const char *const states[4] = {"ACTIF", "ALERTE", "PASSIF", "BUS-OFF"};
    line_init(&line);
    line_str(&line, states[(uint8_t)status->state & 3u]);
    line_str(&line, " TEC");
    line_count(&line, status->tec);
    line_str(&line, " REC");
    line_count(&line, status->rec);
    bench_screen_text(fb, 0u, 7u, line.text);
}
