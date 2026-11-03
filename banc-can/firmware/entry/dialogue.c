/**
 * @file dialogue.c
 * @brief Démonstration : N1 et N2 se parlent en texte, et chaque nœud répond à l'appel du PC.
 *
 * Remplace `main.c` lorsque le firmware est compilé avec `-DBENCH_DIALOGUE=ON`
 * (presets `n1-dialogue`, `n2-dialogue`, `n3-dialogue`). Le but est de **voir le
 * CAN fonctionner** dans un analyseur (ZCANPRO, BancCAN) et sur les écrans LCD :
 *
 * | Qui | Identifiant | Message           | Quand                                       |
 * |-----|-------------|-------------------|---------------------------------------------|
 * | N1  | 0x0A1       | « M'entends tu ? » | toutes les 5 s                             |
 * | N2  | 0x0A2       | « Oui »           | 300 ms après avoir reçu la question de N1    |
 * | N1  | 0x0A1       | « Tres bien »     | 300 ms après avoir reçu « Oui »              |
 * | PC  | 0x0B0       | octet 0 = n° du nœud appelé (0 = tous)          | à la demande |
 * | Nn  | 0x0B0 + n   | « Ici Nn »        | 100 ms après l'appel du PC (0x0B1, 0x0B2…)  |
 *
 * **Découpage des messages.** Une trame CAN classique ne porte que 8 octets.
 * Chaque message est donc envoyé en un ou plusieurs morceaux : l'octet 0 donne
 * le numéro du morceau (quartet haut, à partir de 1) et le nombre de morceaux
 * (quartet bas), les 7 octets suivants portent le texte en ASCII. Exemple,
 * « M'entends tu ? » (14 caractères) part en deux trames 0x0A1 :
 *
 *     12 4D 27 65 6E 74 65 6E    morceau 1/2 : "M'enten"
 *     22 64 73 20 74 75 20 3F    morceau 2/2 : "ds tu ?"
 *
 * Le récepteur recolle les morceaux et n'agit qu'une fois le message complet.
 * Le texte n'est pas accentué : l'écran HD44780 n'a pas de « è ».
 *
 * **Appel du PC.** Depuis ZCANPRO : trame standard 0x0B0, DLC 1, donnée `01`
 * pour appeler N1, `02` pour N2, `03` pour N3, `00` pour tous. Chaque nœud
 * appelé répond sur 0x0B0 + son numéro, décalé de 100 ms × son numéro pour que
 * les réponses à un appel général ne se chevauchent pas.
 *
 * Ces identifiants sont hors des plages réservées de l'ICD (0x010-0x01F,
 * 0x100-0x300, 0x780-0x78F) : ce firmware de démonstration ne se mélange pas
 * au protocole du banc.
 *
 * **Écran LCD** : ligne 1, le dernier message reçu (`<` puis le texte) ;
 * ligne 2, le dernier message envoyé (`>` puis le texte). Le journal série
 * (VCP, 115200 bauds) trace chaque message complet, envoyé ou reçu.
 */

#include <stdio.h>
#include <string.h>

#include "app/lcd_text.h"
#include "board.h"
#include "can_port.h"
#include "clock.h"
#include "icd_gen.h"
#include "lcd.h"
#include "serial.h"
#include "util/ring_buffer.h"

#if BENCH_NODE_ID < 1 || BENCH_NODE_ID > 3
#error "Le mode dialogue est prevu pour N1, N2 et N3 (Nucleo-G431KB)."
#endif

#define DLG_ID_N1        0x0A1u
#define DLG_ID_N2        0x0A2u
#define DLG_ID_CALL      0x0B0u /* appel du PC */
#define DLG_ID_ANSWER(n) (DLG_ID_CALL + (n))

#define DLG_PERIOD_MS       5000u /* N1 : une question toutes les 5 s */
#define DLG_REPLY_DELAY_MS  300u  /* pause avant de répondre, pour lire l'échange */
#define DLG_ANSWER_STEP_MS  100u  /* réponse à l'appel : 100 ms × numéro du nœud */
#define DLG_MAX_TEXT        48u
#define DLG_CHUNK           7u    /* caractères de texte par trame */

#define DLG_QUESTION "M'entends tu ?"
#define DLG_YES      "Oui"
#define DLG_GOOD     "Tres bien"

#if BENCH_NODE_ID == 1
#define DLG_MY_ID DLG_ID_N1
#elif BENCH_NODE_ID == 2
#define DLG_MY_ID DLG_ID_N2
#else
#define DLG_MY_ID DLG_ID_ANSWER(3)
#endif

/** Message en cours de réception, recollé morceau par morceau. */
typedef struct {
    char    text[DLG_MAX_TEXT + 1u];
    uint8_t len;
    uint8_t next_part; /* prochain morceau attendu, 0 = aucun message en cours */
} dlg_rx_t;

/** Réponse programmée : envoyée quand `at_ms` est atteint. */
typedef struct {
    bool     pending;
    uint32_t at_ms;
    uint16_t id;
    char     text[DLG_MAX_TEXT + 1u];
} dlg_pending_t;

static bench_ring_t     s_rx_ring;
static bench_port_can_t s_port;
static bench_can_t      s_can;
static bench_lcd_text_t s_screen;

static bool open_can(void) {
    bench_can_config_t config = {0};

    config.timing.prescaler = BENCH_CAN_PRESCALER;
    config.timing.tseg1 = BENCH_CAN_TSEG1;
    config.timing.tseg2 = BENCH_CAN_TSEG2;
    config.timing.sjw = BENCH_CAN_SJW;
    config.busoff_policy = BENCH_BUSOFF_AUTO;
    config.silent = false;
    config.loopback = false;
    config.auto_retransmit = true;

    return s_can.ops->open(s_can.ctx, &config);
}

/** Envoie @p text en autant de trames que nécessaire ; faux si une trame est refusée. */
static bool send_text(uint16_t id, const char *text) {
    const size_t len = strlen(text);
    const uint8_t parts = (uint8_t)((len + DLG_CHUNK - 1u) / DLG_CHUNK);
    bool ok = true;

    for (uint8_t p = 0u; p < parts; p++) {
        bench_can_frame_t tx = {0};
        const size_t from = (size_t)p * DLG_CHUNK;
        const size_t n = (len - from < DLG_CHUNK) ? (len - from) : DLG_CHUNK;

        tx.id = id;
        tx.data[0] = (uint8_t)(((p + 1u) << 4) | parts);
        memcpy(&tx.data[1], &text[from], n);
        tx.dlc = (uint8_t)(1u + n);
        ok = s_can.ops->send(s_can.ctx, &tx) && ok;
    }
    return ok;
}

#if BENCH_NODE_ID <= 2 /* N3 n'écoute que l'appel du PC, d'une seule trame */
/**
 * Ajoute un morceau au message en cours ; renvoie vrai quand le message est complet.
 * Un morceau hors séquence abandonne le message : on attend le prochain morceau 1.
 */
static bool collect(dlg_rx_t *rx, const bench_can_frame_t *frame) {
    if (frame->dlc < 1u) {
        return false;
    }
    const uint8_t part = (uint8_t)(frame->data[0] >> 4);
    const uint8_t parts = (uint8_t)(frame->data[0] & 0x0Fu);

    if (part == 1u) {
        rx->len = 0u;
        rx->next_part = 1u;
    }
    if (part == 0u || parts == 0u || part != rx->next_part) {
        rx->next_part = 0u;
        return false;
    }
    for (uint8_t i = 1u; i < frame->dlc && rx->len < DLG_MAX_TEXT; i++) {
        rx->text[rx->len++] = (char)frame->data[i];
    }
    rx->text[rx->len] = '\0';
    if (part == parts) {
        rx->next_part = 0u;
        return true;
    }
    rx->next_part++;
    return false;
}
#endif

/** Écrit « <c> texte » sur une ligne de l'écran, complétée d'espaces. */
static void screen_line(uint8_t row, char mark, const char *text) {
    char *line = s_screen.row[row];

    memset(line, ' ', BENCH_LCD_COLS);
    line[BENCH_LCD_COLS] = '\0';
    line[0] = mark;
    for (uint8_t i = 0u; text[i] != '\0' && i + 2u < BENCH_LCD_COLS; i++) {
        const char c = text[i];
        /* Mêmes règles que lcd_text.c : 0x20-0x7D affichés, sauf « \ ». */
        line[2u + i] = (c >= 0x20 && c <= 0x7D && c != 0x5C) ? c : '.';
    }
    bench_lcd_show(&s_screen);
}

static void say(uint16_t id, const char *text) {
    const bool ok = send_text(id, text);

    printf("  >> N%u envoie sur 0x%03X : \"%s\"%s\r\n", (unsigned)BENCH_NODE_ID,
           (unsigned)id, text, ok ? "" : "  (refusee : file d'emission pleine)");
    screen_line(1u, '>', text);
}

static void schedule(dlg_pending_t *out, uint32_t at_ms, uint16_t id, const char *text) {
    out->pending = true;
    out->at_ms = at_ms;
    out->id = id;
    strncpy(out->text, text, DLG_MAX_TEXT);
    out->text[DLG_MAX_TEXT] = '\0';
}

int main(void) {
    HAL_Init();
    bench_clock_config();
    (void)bench_serial_open();

    bench_lcd_init();
    bench_lcd_text_splash(&s_screen, BENCH_NODE_ID, DLG_MY_ID, bench_clock_source_name());
    bench_lcd_show(&s_screen);
    bench_lcd_flush();

    printf("\r\n\r\n============================================================\r\n");
    printf(" Dialogue CAN - noeud N%u - %s\r\n", (unsigned)BENCH_NODE_ID, BENCH_BOARD_NAME);
    printf("============================================================\r\n");
    printf("  Horloge : %s, %lu bit/s\r\n", bench_clock_source_name(),
           (unsigned long)BENCH_BITRATE);
    printf("  Appel du PC : 0x%03X, octet 0 = %u (ou 0 pour tous) -> reponse sur 0x%03X\r\n",
           (unsigned)DLG_ID_CALL, (unsigned)BENCH_NODE_ID,
           (unsigned)DLG_ID_ANSWER(BENCH_NODE_ID));
#if BENCH_NODE_ID == 1
    printf("  N1 demande \"%s\" sur 0x%03X toutes les %u s\r\n\r\n", DLG_QUESTION,
           (unsigned)DLG_ID_N1, (unsigned)(DLG_PERIOD_MS / 1000u));
#elif BENCH_NODE_ID == 2
    printf("  N2 repond \"%s\" sur 0x%03X a la question de N1\r\n\r\n", DLG_YES,
           (unsigned)DLG_ID_N2);
#else
    printf("  N3 ne repond qu'a l'appel du PC\r\n\r\n");
#endif

    bench_ring_init(&s_rx_ring);
    bench_port_can_bind(&s_port, &s_rx_ring, &s_can);
    if (!open_can()) {
        bench_fatal("ouverture du controleur " BENCH_CAN_PERIPH_NAME " impossible.");
    }

    dlg_rx_t from_n1 = {0};
    dlg_rx_t from_n2 = {0};
    dlg_pending_t reply = {0};
    dlg_pending_t answer = {0};
#if BENCH_NODE_ID == 1
    uint32_t next_question_ms = HAL_GetTick() + 2000u; /* après l'écran d'accueil */
#endif

    for (;;) {
        const uint32_t now_ms = HAL_GetTick();
        bench_can_frame_t rx;

        bench_port_can_poll(&s_port);

        while (bench_ring_pop(&s_rx_ring, &rx)) {
            if (rx.id == DLG_ID_CALL && rx.dlc >= 1u &&
                (rx.data[0] == 0u || rx.data[0] == BENCH_NODE_ID)) {
                char text[DLG_MAX_TEXT + 1u];
                snprintf(text, sizeof text, "Ici N%u", (unsigned)BENCH_NODE_ID);
                printf("  << appel du PC (0x%03X, %02X)\r\n", (unsigned)DLG_ID_CALL,
                       (unsigned)rx.data[0]);
                screen_line(0u, '<', rx.data[0] == 0u ? "PC appelle tous" : "PC m'appelle");
                schedule(&answer, now_ms + DLG_ANSWER_STEP_MS * BENCH_NODE_ID,
                         DLG_ID_ANSWER(BENCH_NODE_ID), text);
            }
#if BENCH_NODE_ID == 2
            (void)from_n2;
            if (rx.id == DLG_ID_N1 && collect(&from_n1, &rx)) {
                printf("  << N1 : \"%s\"\r\n", from_n1.text);
                screen_line(0u, '<', from_n1.text);
                if (strcmp(from_n1.text, DLG_QUESTION) == 0) {
                    schedule(&reply, now_ms + DLG_REPLY_DELAY_MS, DLG_ID_N2, DLG_YES);
                }
            }
#elif BENCH_NODE_ID == 1
            (void)from_n1;
            if (rx.id == DLG_ID_N2 && collect(&from_n2, &rx)) {
                printf("  << N2 : \"%s\"\r\n", from_n2.text);
                screen_line(0u, '<', from_n2.text);
                if (strcmp(from_n2.text, DLG_YES) == 0) {
                    schedule(&reply, now_ms + DLG_REPLY_DELAY_MS, DLG_ID_N1, DLG_GOOD);
                }
            }
#else
            (void)from_n1;
            (void)from_n2;
#endif
        }

#if BENCH_NODE_ID == 1
        if ((int32_t)(now_ms - next_question_ms) >= 0) {
            say(DLG_ID_N1, DLG_QUESTION);
            next_question_ms = now_ms + DLG_PERIOD_MS;
        }
#endif
        if (reply.pending && (int32_t)(now_ms - reply.at_ms) >= 0) {
            reply.pending = false;
            say(reply.id, reply.text);
        }
        if (answer.pending && (int32_t)(now_ms - answer.at_ms) >= 0) {
            answer.pending = false;
            say(answer.id, answer.text);
        }
        bench_lcd_service();
    }
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line) {
    (void)file;
    (void)line;
    bench_fatal("assertion HAL en echec.");
}
#endif
