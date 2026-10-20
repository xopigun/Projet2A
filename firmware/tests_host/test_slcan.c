/**
 * @file test_slcan.c
 * @brief Tests du protocole slcan du pont CAN-USB.
 *
 * Les chaînes ci-dessous sont celles qu'émet python-can (`slcanBus`) : c'est ce
 * client que le logiciel du banc utilise, le pont doit donc le comprendre à la
 * lettre.
 */

#include "app/slcan.h"
#include "bench_test.h"

/** Envoie une ligne complète (terminée par \r) et retourne la commande obtenue. */
static bench_slcan_cmd_t parse(const char *text) {
    bench_slcan_parser_t parser;
    bench_slcan_cmd_t cmd = {0};
    bool done = false;

    bench_slcan_parser_init(&parser);
    for (const char *p = text; *p != '\0'; p++) {
        done = bench_slcan_feed(&parser, (uint8_t)*p, &cmd);
    }
    BENCH_ASSERT(done);
    return cmd;
}

BENCH_TEST(commandes_simples) {
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_OPEN, parse("O\r").type);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_LISTEN, parse("L\r").type);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_CLOSE, parse("C\r").type);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_VERSION, parse("V\r").type);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_SERIAL, parse("N\r").type);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_FLAGS, parse("F\r").type);
}

BENCH_TEST(ligne_vide_sans_reponse) {
    /* python-can écrit une ligne vide pour le débit de données (« \r » seul). */
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_NONE, parse("\r").type);
}

BENCH_TEST(debits) {
    BENCH_ASSERT_EQ_UINT(500000u, parse("S6\r").bitrate_bps);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_BITRATE, parse("S6\r").type);
    BENCH_ASSERT_EQ_UINT(125000u, parse("S4\r").bitrate_bps);
    BENCH_ASSERT_EQ_UINT(1000000u, parse("S8\r").bitrate_bps);
    BENCH_ASSERT_EQ_UINT(10000u, parse("S0\r").bitrate_bps);
}

BENCH_TEST(debits_non_reproductibles_refuses) {
    /* 750 kbit/s (S7) et 83,3 kbit/s (S9) n'ont pas de diviseur entier à 80 MHz. */
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("S7\r").type);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("S9\r").type);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("S\r").type);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("S66\r").type);
}

BENCH_TEST(trame_standard_emise_par_le_pc) {
    const bench_slcan_cmd_t cmd = parse("t1008DEADBEEF01020304\r");
    /* Rédigée comme python-can : « t » + id sur 3 chiffres + dlc + données. */
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_SEND, cmd.type);
    BENCH_ASSERT_EQ_UINT(0x100u, cmd.frame.id);
    BENCH_ASSERT_EQ_UINT(8u, cmd.frame.dlc);
    BENCH_ASSERT_EQ_UINT(0xDEu, cmd.frame.data[0]);
    BENCH_ASSERT_EQ_UINT(0x04u, cmd.frame.data[7]);
}

BENCH_TEST(trame_sans_donnees_et_minuscules) {
    bench_slcan_cmd_t cmd = parse("t7FF0\r");
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_SEND, cmd.type);
    BENCH_ASSERT_EQ_UINT(0x7FFu, cmd.frame.id);
    BENCH_ASSERT_EQ_UINT(0u, cmd.frame.dlc);

    cmd = parse("t2002ab0c\r");
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_SEND, cmd.type);
    BENCH_ASSERT_EQ_UINT(0xABu, cmd.frame.data[0]);
    BENCH_ASSERT_EQ_UINT(0x0Cu, cmd.frame.data[1]);
}

BENCH_TEST(trames_hors_can_2_0a_refusees) {
    /* Le banc est verrouillé en CAN 2.0A classic : étendues, distantes, FD
     * et identifiants de plus de 11 bits sont refusés, jamais émis. */
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("T000001230\r").type);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("r1000\r").type);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("R000001000\r").type);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("d10080011223344556677\r").type);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("b10080011223344556677\r").type);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("t8000\r").type);  /* 0x800 */
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("t1009\r").type);  /* dlc 9 */
}

BENCH_TEST(trames_mal_formees_refusees) {
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("t1002AA\r").type);     /* données courtes */
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("t1001AABB\r").type);   /* données longues */
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("t1G01AA\r").type);     /* id non hexa */
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("t1001ZZ\r").type);     /* donnée non hexa */
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("t10\r").type);         /* tronquée */
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("Q\r").type);           /* inconnue */
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("OO\r").type);          /* suffixe en trop */
}

BENCH_TEST(filtres_et_horodatage) {
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_ACCEPT, parse("M00000000\r").type);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_ACCEPT, parse("m00000000\r").type);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_ACCEPT, parse("Z0\r").type);
    /* Horodatage matériel non fourni : annoncer le contraire fausserait les dates. */
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, parse("Z1\r").type);
}

BENCH_TEST(ligne_trop_longue_rejetee_puis_reprise) {
    bench_slcan_parser_t parser;
    bench_slcan_cmd_t cmd = {0};
    bool done = false;

    bench_slcan_parser_init(&parser);
    for (int i = 0; i < 100; i++) {
        done = bench_slcan_feed(&parser, (uint8_t)'t', &cmd);
        BENCH_ASSERT(!done);
    }
    BENCH_ASSERT(bench_slcan_feed(&parser, (uint8_t)'\r', &cmd));
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_INVALID, cmd.type);

    /* L'analyseur est reparti de zéro : la commande suivante passe. */
    BENCH_ASSERT(bench_slcan_feed(&parser, (uint8_t)'O', &cmd) == false);
    BENCH_ASSERT(bench_slcan_feed(&parser, (uint8_t)'\r', &cmd));
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_OPEN, cmd.type);
}

BENCH_TEST(fin_de_ligne_crlf_tolere) {
    bench_slcan_parser_t parser;
    bench_slcan_cmd_t cmd = {0};

    bench_slcan_parser_init(&parser);
    BENCH_ASSERT(!bench_slcan_feed(&parser, (uint8_t)'V', &cmd));
    BENCH_ASSERT(bench_slcan_feed(&parser, (uint8_t)'\r', &cmd));
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_VERSION, cmd.type);
    BENCH_ASSERT(!bench_slcan_feed(&parser, (uint8_t)'\n', &cmd));  /* ignoré */
}

BENCH_TEST(mise_en_forme_d_une_trame_recue) {
    bench_can_frame_t frame = {0};
    char out[BENCH_SLCAN_FRAME_MAX];

    frame.id = 0x100u;
    frame.dlc = 8u;
    for (uint8_t i = 0u; i < 8u; i++) {
        frame.data[i] = (uint8_t)(0xA0u + i);
    }
    const size_t n = bench_slcan_format_frame(&frame, out, sizeof out);
    BENCH_ASSERT_EQ_UINT(22u, n);
    BENCH_ASSERT(memcmp(out, "t1008A0A1A2A3A4A5A6A7\r", 22u) == 0);

    frame.id = 0x7FFu;
    frame.dlc = 0u;
    BENCH_ASSERT_EQ_UINT(6u, bench_slcan_format_frame(&frame, out, sizeof out));
    BENCH_ASSERT(memcmp(out, "t7FF0\r", 6u) == 0);
}

BENCH_TEST(mise_en_forme_refuse_l_invalide) {
    bench_can_frame_t frame = {0};
    char out[BENCH_SLCAN_FRAME_MAX];

    frame.id = 0x800u;
    BENCH_ASSERT_EQ_UINT(0u, bench_slcan_format_frame(&frame, out, sizeof out));
    frame.id = 0x100u;
    frame.dlc = 9u;
    BENCH_ASSERT_EQ_UINT(0u, bench_slcan_format_frame(&frame, out, sizeof out));
    frame.dlc = 8u;
    BENCH_ASSERT_EQ_UINT(0u, bench_slcan_format_frame(&frame, out, 10u));  /* tampon court */
}

BENCH_TEST(aller_retour_emission_reception) {
    /* Ce que le pont formate, python-can le relit : on le rejoue à travers
     * l'analyseur, qui accepte la même grammaire. */
    bench_can_frame_t frame = {0};
    char out[BENCH_SLCAN_FRAME_MAX];

    frame.id = 0x2A5u;
    frame.dlc = 5u;
    for (uint8_t i = 0u; i < 5u; i++) {
        frame.data[i] = (uint8_t)(i * 37u + 1u);
    }
    const size_t n = bench_slcan_format_frame(&frame, out, sizeof out);
    BENCH_ASSERT(n > 0u);
    out[n] = '\0';

    const bench_slcan_cmd_t cmd = parse(out);
    BENCH_ASSERT_EQ_INT(BENCH_SLCAN_SEND, cmd.type);
    BENCH_ASSERT_EQ_UINT(frame.id, cmd.frame.id);
    BENCH_ASSERT_EQ_UINT(frame.dlc, cmd.frame.dlc);
    BENCH_ASSERT_EQ_MEM(frame.data, cmd.frame.data, 5u, "donnees");
}

BENCH_TEST(octet_d_etat) {
    bench_can_status_t status = {0};

    status.state = BENCH_CAN_ERROR_ACTIVE;
    BENCH_ASSERT_EQ_UINT(0x00u, bench_slcan_status_flags(&status, false));
    status.state = BENCH_CAN_ERROR_WARNING;
    BENCH_ASSERT_EQ_UINT(0x04u, bench_slcan_status_flags(&status, false));
    status.state = BENCH_CAN_ERROR_PASSIVE;
    BENCH_ASSERT_EQ_UINT(0x20u, bench_slcan_status_flags(&status, false));
    status.state = BENCH_CAN_BUS_OFF;
    BENCH_ASSERT_EQ_UINT(0x80u, bench_slcan_status_flags(&status, false));
    status.state = BENCH_CAN_ERROR_ACTIVE;
    BENCH_ASSERT_EQ_UINT(0x08u, bench_slcan_status_flags(&status, true));
}

/* Le harnais accepte 12 cas par fichier : les quatre premiers sont regroupés. */
BENCH_TEST(commandes_et_debits) {
    commandes_simples();
    ligne_vide_sans_reponse();
    debits();
    debits_non_reproductibles_refuses();
}

BENCH_TEST_MAIN(commandes_et_debits, trame_standard_emise_par_le_pc,
                trame_sans_donnees_et_minuscules, trames_hors_can_2_0a_refusees,
                trames_mal_formees_refusees, filtres_et_horodatage,
                ligne_trop_longue_rejetee_puis_reprise, fin_de_ligne_crlf_tolere,
                mise_en_forme_d_une_trame_recue, mise_en_forme_refuse_l_invalide,
                aller_retour_emission_reception, octet_d_etat)
