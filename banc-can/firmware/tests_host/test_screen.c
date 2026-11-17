/**
 * @file test_screen.c
 * @brief Tests du rendu de l'écran de notes (image SSD1306).
 */

#include "app/node.h"
#include "app/screen.h"
#include "bench_test.h"
#include "util/font5x7.h"

static uint8_t s_fb[BENCH_SCREEN_BYTES];

BENCH_TEST(texte_dans_la_bonne_page) {
    bench_screen_clear(s_fb);
    bench_screen_text(s_fb, 1u, 2u, "A");
    const uint8_t *g = bench_font_glyph('A');
    BENCH_ASSERT_EQ_MEM(g, &s_fb[2u * 128u + 6u], 5u, "glyphe A en colonne 1, page 2");
    BENCH_ASSERT_EQ_UINT(0u, s_fb[2u * 128u + 11u]);  /* colonne d'espacement */
    BENCH_ASSERT_EQ_UINT(0u, s_fb[1u * 128u + 6u]);   /* page voisine intacte */
}

BENCH_TEST(pixel_et_bornes) {
    bench_screen_clear(s_fb);
    bench_screen_pixel(s_fb, 3u, 9u, 1);
    BENCH_ASSERT_EQ_UINT(0x02u, s_fb[128u + 3u]);
    bench_screen_pixel(s_fb, 200u, 9u, 1);  /* hors écran : ignoré */
    bench_screen_pixel(s_fb, 3u, 9u, 0);
    BENCH_ASSERT_EQ_UINT(0u, s_fb[128u + 3u]);
}

BENCH_TEST(ecran_de_notes_complet) {
    bench_node_t node;
    bench_node_init(&node, 2u, NULL, NULL, true);
    node.rxq.last.score[0] = 100u;
    node.rxq.last.score[2] = 0u;
    node.rxq.last.score_heartbeat = 50u;
    bench_can_status_t st = {0};
    bench_screen_quality(s_fb, &node, &st);

    /* Titre « N2 ... » : glyphe N en tête de la page 0. */
    BENCH_ASSERT_EQ_MEM(bench_font_glyph('N'), &s_fb[0], 5u, "titre");
    /* Barre pleine pour 100 sur la ligne ENERGY (page 2), vide pour 0 (page 4). */
    BENCH_ASSERT(s_fb[2u * 128u + 120u] != 0u);
    BENCH_ASSERT_EQ_UINT(0u, s_fb[4u * 128u + 120u]);
    /* Barre à moitié pour le heartbeat (page 5). */
    BENCH_ASSERT(s_fb[5u * 128u + 106u] != 0u);
    BENCH_ASSERT_EQ_UINT(0u, s_fb[5u * 128u + 126u]);
}

BENCH_TEST(compteurs_enormes_sans_debordement) {
    /* Régression du 17/11/2026 : des compteurs à 5 chiffres et l'état BUS-OFF
     * débordaient le tampon d'une ligne et écrasaient la pile du nœud. */
    bench_node_t node;
    bench_node_init(&node, 3u, NULL, NULL, true);
    node.rxq.total_lost = 4000000000u;
    node.rxq.total_bad = 123456u;
    node.rxq.total_late = 99999u;
    bench_can_status_t st = {0};
    st.state = BENCH_CAN_BUS_OFF;
    st.tec = 255u;
    st.rec = 255u;
    const bench_node_t before = node;
    for (int i = 0; i < 100; i++) {
        bench_screen_quality(s_fb, &node, &st);
    }
    BENCH_ASSERT_EQ_MEM(&before, &node, sizeof(node), "état du nœud intact");
    /* « P:99k A:99k R:99k » : 18 caractères, la 19e cellule reste vide. */
    BENCH_ASSERT_EQ_UINT(0u, s_fb[6u * 128u + 18u * 6u]);
}

BENCH_TEST_MAIN(texte_dans_la_bonne_page, pixel_et_bornes, ecran_de_notes_complet,
                compteurs_enormes_sans_debordement)
