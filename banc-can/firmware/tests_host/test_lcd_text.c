/**
 * @file test_lcd_text.c
 * @brief Tests de la mise en forme des afficheurs LCD 16x2.
 *
 * Chaque ligne attendue est écrite en entier, espaces compris : une ligne plus
 * courte que 16 colonnes laisserait à l'écran la fin du texte précédent.
 */

#include "app/lcd_text.h"
#include "bench_test.h"

#define ASSERT_ROW(expected, actual)                                                        \
    do {                                                                                    \
        if (strcmp((expected), (actual)) != 0) {                                            \
            BENCH_FAIL("ligne attendue « %s », obtenue « %s »", (expected), (actual));      \
        }                                                                                   \
    } while (0)

/** La trame de N2 en mode scope : 0x20F, « Test ». */
static bench_lcd_rx_view_t view_test_frame(void) {
    bench_lcd_rx_view_t view = {0};

    view.tx_id = 0x0F0u;
    view.has_rx = true;
    view.last_rx.id = 0x20Fu;
    view.last_rx.dlc = 4u;
    view.last_rx.data[0] = 'T';
    view.last_rx.data[1] = 'e';
    view.last_rx.data[2] = 's';
    view.last_rx.data[3] = 't';
    view.rx_count = 123u;
    view.silent_ms = 20u;
    view.state = BENCH_CAN_ERROR_ACTIVE;
    return view;
}

BENCH_TEST(accueil_signale_le_repli_hsi) {
    bench_lcd_text_t text;

    bench_lcd_text_splash(&text, 1u, 0x0F0u, "HSI - NON VALIDE");
    ASSERT_ROW("N1 TX 0F0       ", text.row[0]);
    ASSERT_ROW("HSI - NON VALIDE", text.row[1]);
}

BENCH_TEST(attente_montre_ce_que_le_noeud_emet) {
    bench_lcd_text_t text;
    bench_lcd_rx_view_t view = {0};

    view.tx_id = 0x20Fu;
    view.state = BENCH_CAN_ERROR_PASSIVE;
    bench_lcd_text_rx(&text, &view);
    ASSERT_ROW("RX en attente...", text.row[0]);
    ASSERT_ROW("TX 20F    PASSIF", text.row[1]);
}

BENCH_TEST(trame_recue_conforme_au_schema) {
    /* docs/latex/schema_ecrans_lcd.tex : « RX 20F DLC4 » puis « Test ». */
    bench_lcd_text_t text;
    const bench_lcd_rx_view_t view = view_test_frame();

    bench_lcd_text_rx(&text, &view);
    ASSERT_ROW("RX 20F DLC4  123", text.row[0]);
    ASSERT_ROW("Test       ACTIF", text.row[1]);
}

BENCH_TEST(compteur_modulo_dix_mille) {
    bench_lcd_text_t text;
    bench_lcd_rx_view_t view = view_test_frame();

    view.rx_count = 123456u;
    bench_lcd_text_rx(&text, &view);
    ASSERT_ROW("RX 20F DLC4 3456", text.row[0]);
}

BENCH_TEST(silence_garde_la_derniere_trame) {
    bench_lcd_text_t text;
    bench_lcd_rx_view_t view = view_test_frame();

    view.silent_ms = 12345u;
    view.state = BENCH_CAN_BUS_OFF;
    bench_lcd_text_rx(&text, &view);
    ASSERT_ROW("RX 20F muet  12s", text.row[0]);
    ASSERT_ROW("Test     BUS-OFF", text.row[1]);
}

BENCH_TEST(silence_plafonne_a_999_s) {
    bench_lcd_text_t text;
    bench_lcd_rx_view_t view = view_test_frame();

    view.silent_ms = 5000000u;
    bench_lcd_text_rx(&text, &view);
    ASSERT_ROW("RX 20F muet 999s", text.row[0]);
}

BENCH_TEST(octets_non_affichables_remplaces) {
    /* 0x5C et 0x7E n'ont pas leur glyphe ASCII dans la ROM A00 du HD44780. */
    bench_lcd_text_t text;
    bench_lcd_rx_view_t view = view_test_frame();
    static const uint8_t bytes[8] = {0x00u, 'A', 0x5Cu, 0x7Eu, 0xFFu, ' ', 'z', 0x1Fu};

    view.last_rx.id = 0x7FFu;
    view.last_rx.dlc = 8u;
    for (uint32_t i = 0u; i < 8u; i++) {
        view.last_rx.data[i] = bytes[i];
    }
    bench_lcd_text_rx(&text, &view);
    ASSERT_ROW("RX 7FF DLC8  123", text.row[0]);
    ASSERT_ROW(".A... z.   ACTIF", text.row[1]);
}

BENCH_TEST(trame_vide_et_dlc_hors_norme) {
    bench_lcd_text_t text;
    bench_lcd_rx_view_t view = view_test_frame();

    view.last_rx.dlc = 0u;
    bench_lcd_text_rx(&text, &view);
    ASSERT_ROW("RX 20F DLC0  123", text.row[0]);
    ASSERT_ROW("           ACTIF", text.row[1]);

    /* Un DLC au-delà de 8 ne doit jamais faire lire au-delà des données. */
    view.last_rx.dlc = 15u;
    bench_lcd_text_rx(&text, &view);
    ASSERT_ROW("RX 20F DLC8  123", text.row[0]);
}

BENCH_TEST(lignes_toujours_de_seize_colonnes) {
    bench_lcd_text_t text;
    bench_lcd_rx_view_t view = view_test_frame();

    bench_lcd_text_splash(&text, 2u, 0x20Fu, "un libelle beaucoup trop long");
    BENCH_ASSERT_EQ_UINT(BENCH_LCD_COLS, strlen(text.row[0]));
    BENCH_ASSERT_EQ_UINT(BENCH_LCD_COLS, strlen(text.row[1]));

    for (int state = BENCH_CAN_ERROR_ACTIVE; state <= BENCH_CAN_BUS_OFF; state++) {
        view.state = (bench_can_state_t)state;
        bench_lcd_text_rx(&text, &view);
        BENCH_ASSERT_EQ_UINT(BENCH_LCD_COLS, strlen(text.row[0]));
        BENCH_ASSERT_EQ_UINT(BENCH_LCD_COLS, strlen(text.row[1]));
        BENCH_ASSERT(strlen(bench_lcd_state_name(view.state)) <= 7u);
    }
}

BENCH_TEST_MAIN(accueil_signale_le_repli_hsi, attente_montre_ce_que_le_noeud_emet,
                trame_recue_conforme_au_schema, compteur_modulo_dix_mille,
                silence_garde_la_derniere_trame, silence_plafonne_a_999_s,
                octets_non_affichables_remplaces, trame_vide_et_dlc_hors_norme,
                lignes_toujours_de_seize_colonnes)
