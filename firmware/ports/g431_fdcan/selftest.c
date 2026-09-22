/**
 * @file selftest.c
 * @brief Mise en route matérielle : autotest d'un nœud, en deux phases.
 *
 * Remplace `main.c` lorsque le firmware est compilé avec `-DBENCH_SELFTEST=ON`
 * (presets `n1-selftest` à `n3-selftest`). Tout est reporté sur le port COM
 * virtuel du ST-LINK, à 115200 bauds.
 *
 * **Phase 1 — bouclage interne.** Le FDCAN est ouvert en
 * `FDCAN_MODE_INTERNAL_LOOPBACK` : rien n'est émis sur PA12, et **ni transceiver
 * ni bus câblé ne sont nécessaires**. Une trame de chaque type de l'ICD est
 * émise, reçue, décodée et comparée octet par octet. Cette phase valide d'un
 * coup l'horloge, le temps de bit, la chaîne ISR → tampon circulaire et
 * l'encodage, avant même d'avoir soudé quoi que ce soit.
 *
 * Si la phase 1 échoue, inutile de chercher du côté du câblage : le problème est
 * dans la carte ou sa configuration.
 *
 * **Phase 2 — ping/pong sur le bus réel.** Le nœud repasse en mode normal. N1
 * émet périodiquement, N2 et N3 répondent à chaque trame de N1. Chaque nœud
 * affiche ses compteurs et l'état lu dans `PSR`/`ECR`. C'est ici que se
 * détectent un HW1 oublié, une terminaison manquante ou un transceiver mal
 * alimenté.
 *
 * Procédure pas à pas : docs/bringup.md.
 */

#include <stdio.h>

#include "app/node.h"
#include "board.h"
#include "can_port.h"
#include "clock.h"
#include "icd_gen.h"
#include "serial.h"
#include "util/ring_buffer.h"

#ifndef BENCH_NODE_ID
#error "BENCH_NODE_ID doit etre defini (1 a 4)."
#endif

static bench_ring_t     s_rx_ring;
static bench_g431_can_t s_port;
static bench_can_t      s_can;

/** Une trame de l'ICD à éprouver en bouclage, avec une charge utile connue. */
typedef struct {
    const char *name;
    uint16_t    id;
    uint8_t     dlc;
    uint8_t     data[8];
} selftest_frame_t;

/* Les charges utiles sont des motifs qui font ressortir une inversion d'octets
 * ou un décalage : 0x00/0xFF alternés, puis une rampe. */
static const selftest_frame_t k_frames[] = {
    {"ARM",            BENCH_ID_ARM,            8u, {0}},
    {"GO",             BENCH_ID_GO,             8u, {0}},
    {"BENCH_CFG",      BENCH_ID_BENCH_CFG,      8u, {0x01, 0x04, 0x34, 0x12, 0xE8, 0x03, 0xF4, 0x01}},
    {"BENCH_RESULT",   BENCH_ID_BENCH_RESULT,   8u, {0x02, 0x00, 0x00, 0x7B, 0xFF, 0xFF, 0x00, 0x00}},
    {"HEARTBEAT",      BENCH_ID_HEARTBEAT_N1,   8u, {0x25, 0x82, 0x61, 0x00, 0x0C, 0x00, 0x02, 0x00}},
    {"ENERGY_COMMAND", BENCH_ID_ENERGY_COMMAND, 8u, {0xFF, 0x7F, 0x00, 0x80, 0xFF, 0x3F, 0xAA, 0x55}},
    {"IMU_SPEED",      BENCH_ID_IMU_SPEED,      8u, {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08}},
    {"TEMP_BATTERY",   BENCH_ID_TEMP_BATTERY,   8u, {0x00, 0xFF, 0x55, 0xAA, 0x12, 0x34, 0x56, 0x78}},
};

#define FRAME_COUNT (sizeof(k_frames) / sizeof(k_frames[0]))

static void print_status(const char *label) {
    bench_can_status_t status;
    s_can.ops->status(s_can.ctx, &status);

    static const char *const k_states[] = {"error-active", "error-warning", "error-passive",
                                           "BUS-OFF"};
    printf("  %-14s etat=%-14s TEC=%3u REC=%3u LEC=%u pertes_fifo=%u tampon=%u\r\n", label,
           k_states[status.state], (unsigned)status.tec, (unsigned)status.rec,
           (unsigned)status.last_error_code, (unsigned)status.rx_fifo_lost,
           (unsigned)bench_ring_dropped(&s_rx_ring));
}

/** Attend une trame pendant au plus @p timeout_ms ; renvoie false sur expiration. */
static bool wait_frame(bench_can_frame_t *frame, uint32_t timeout_ms) {
    const uint32_t deadline = HAL_GetTick() + timeout_ms;

    while ((int32_t)(HAL_GetTick() - deadline) < 0) {
        if (bench_ring_pop(&s_rx_ring, frame)) {
            return true;
        }
    }
    return false;
}

static bool open_can(bool loopback) {
    bench_can_config_t config = {0};

    config.timing.prescaler = BENCH_CAN_PRESCALER;
    config.timing.tseg1 = BENCH_CAN_TSEG1;
    config.timing.tseg2 = BENCH_CAN_TSEG2;
    config.timing.sjw = BENCH_CAN_SJW;
    config.busoff_policy = BENCH_BUSOFF_AUTO;
    config.loopback = loopback;
    config.silent = false;
    config.auto_retransmit = true;

    return s_can.ops->open(s_can.ctx, &config);
}

/* ------------------------------------------------------------------ phase 1 -- */

static unsigned phase1_loopback(void) {
    unsigned failures = 0u;

    printf("\r\n=== Phase 1 : bouclage interne (aucun transceiver requis) ===\r\n");

    if (!open_can(true)) {
        printf("  ECHEC : ouverture du FDCAN impossible.\r\n");
        return 1u;
    }

    for (size_t i = 0u; i < FRAME_COUNT; i++) {
        const selftest_frame_t *expected = &k_frames[i];
        bench_can_frame_t tx = {0};
        bench_can_frame_t rx;

        tx.id = expected->id;
        tx.dlc = expected->dlc;
        for (uint8_t b = 0u; b < expected->dlc; b++) {
            tx.data[b] = expected->data[b];
        }

        if (!s_can.ops->send(s_can.ctx, &tx)) {
            printf("  [%-14s] ECHEC emission\r\n", expected->name);
            failures++;
            continue;
        }

        if (!wait_frame(&rx, 50u)) {
            printf("  [%-14s] ECHEC : aucune trame recue en 50 ms\r\n", expected->name);
            failures++;
            continue;
        }

        if (rx.id != expected->id || rx.dlc != expected->dlc) {
            printf("  [%-14s] ECHEC : recu id=0x%03X dlc=%u, attendu id=0x%03X dlc=%u\r\n",
                   expected->name, (unsigned)rx.id, (unsigned)rx.dlc, (unsigned)expected->id,
                   (unsigned)expected->dlc);
            failures++;
            continue;
        }

        unsigned bad_byte = 0xFFu;
        for (uint8_t b = 0u; b < expected->dlc; b++) {
            if (rx.data[b] != expected->data[b]) {
                bad_byte = b;
                break;
            }
        }
        if (bad_byte != 0xFFu) {
            printf("  [%-14s] ECHEC : octet %u recu 0x%02X, attendu 0x%02X\r\n",
                   expected->name, bad_byte, (unsigned)rx.data[bad_byte],
                   (unsigned)expected->data[bad_byte]);
            failures++;
            continue;
        }

        printf("  [%-14s] ok  id=0x%03X dlc=%u\r\n", expected->name, (unsigned)expected->id,
               (unsigned)expected->dlc);
    }

    print_status("apres phase 1");
    printf("  Resultat : %u/%u trames correctes.\r\n", (unsigned)(FRAME_COUNT - failures),
           (unsigned)FRAME_COUNT);
    return failures;
}

/* ------------------------------------------------------------------ phase 2 -- */

/** Identifiant émis par ce nœud pendant le ping/pong. */
static uint16_t own_id(void) {
    const uint16_t id = bench_node_tx_id(BENCH_NODE_ID);
    return (id != 0u) ? id : BENCH_ID_BENCH_RESULT;  /* N4 n'est pas contendant */
}

static void phase2_ping_pong(void) {
    uint32_t sent = 0u;
    uint32_t received = 0u;
    uint32_t echoes = 0u;
    uint32_t next_report_ms = 0u;
#if BENCH_NODE_ID == 1
    uint32_t next_tx_ms = 0u;  /* cadence d'emission, initiateur seulement */
    uint8_t counter = 0u;
#endif

    printf("\r\n=== Phase 2 : ping/pong sur le bus reel ===\r\n");
    printf("  Ce noeud est N%u, identifiant 0x%03X.\r\n", (unsigned)BENCH_NODE_ID,
           (unsigned)own_id());
#if BENCH_NODE_ID == 1
    printf("  Role : initiateur. Emet toutes les 100 ms.\r\n");
#else
    printf("  Role : repondeur. Repond a chaque trame de N1 (0x%03X).\r\n",
           (unsigned)BENCH_ID_ENERGY_COMMAND);
#endif
    printf("  Ctrl-C pour arreter la lecture ; le noeud continue de tourner.\r\n\r\n");

    if (!open_can(false)) {
        printf("  ECHEC : reouverture du FDCAN en mode normal impossible.\r\n");
        return;
    }

    for (;;) {
        const uint32_t now_ms = HAL_GetTick();
        bench_can_frame_t rx;

        bench_g431_can_poll(&s_port);

        while (bench_ring_pop(&s_rx_ring, &rx)) {
            received++;
            if (rx.id == own_id()) {
                continue;  /* notre propre trame, en echo */
            }
#if BENCH_NODE_ID != 1
            /* Repondeur : chaque trame de N1 declenche une reponse. */
            if (rx.id == BENCH_ID_ENERGY_COMMAND) {
                bench_can_frame_t tx = {0};
                tx.id = own_id();
                tx.dlc = 8u;
                tx.data[0] = rx.data[0];  /* renvoie le compteur recu */
                tx.data[1] = (uint8_t)BENCH_NODE_ID;
                if (s_can.ops->send(s_can.ctx, &tx)) {
                    sent++;
                }
            }
#else
            /* Initiateur : compte les reponses. */
            if (rx.id == BENCH_ID_IMU_SPEED || rx.id == BENCH_ID_TEMP_BATTERY) {
                echoes++;
            }
#endif
        }

#if BENCH_NODE_ID == 1
        if ((int32_t)(now_ms - next_tx_ms) >= 0) {
            bench_can_frame_t tx = {0};
            tx.id = own_id();
            tx.dlc = 8u;
            tx.data[0] = counter++;
            if (s_can.ops->send(s_can.ctx, &tx)) {
                sent++;
            }
            next_tx_ms = now_ms + 100u;
        }
#endif

        if ((int32_t)(now_ms - next_report_ms) >= 0) {
            printf("  t=%6lus  emises=%-6lu recues=%-6lu reponses=%-6lu\r\n",
                   (unsigned long)(now_ms / 1000u), (unsigned long)sent,
                   (unsigned long)received, (unsigned long)echoes);
            print_status("");
            next_report_ms = now_ms + 1000u;
        }
    }
}

/* --------------------------------------------------------------------- main -- */

int main(void) {
    HAL_Init();
    bench_clock_config();
    (void)bench_serial_open();

    printf("\r\n\r\n============================================================\r\n");
    printf(" Autotest du banc CAN — noeud N%u — %s\r\n", (unsigned)BENCH_NODE_ID,
           BENCH_BOARD_NAME);
    printf("============================================================\r\n");
    printf("  Horloge     : %s\r\n", bench_clock_source_name());
    printf("  FDCAN       : %lu Hz\r\n", (unsigned long)bench_clock_fdcan_hz());
    printf("  Temps de bit: BRP=%u, 1+%u+%u tq, SJW=%u -> %lu bit/s, SP=87,50 %%\r\n",
           BENCH_CAN_PRESCALER, BENCH_CAN_TSEG1, BENCH_CAN_TSEG2, BENCH_CAN_SJW,
           (unsigned long)BENCH_BITRATE);

    if (!bench_clock_is_qualified()) {
        printf("\r\n  *** ATTENTION : horloge HSI, reference NON CONFORME pour le CAN.\r\n");
        printf("  *** Souder SB9 et SB10, puis recompiler sans -DBENCH_CLOCK_SOURCE=2.\r\n");
        printf("  *** Aucun verdict de reussite ne peut etre prononce dans cet etat.\r\n");
    }

    bench_ring_init(&s_rx_ring);
    bench_g431_can_bind(&s_port, &s_rx_ring, &s_can);

    const unsigned failures = phase1_loopback();
    if (failures != 0u) {
        printf("\r\n  Phase 1 en echec : le probleme est dans la carte ou sa\r\n");
        printf("  configuration, pas dans le cablage. Phase 2 non lancee.\r\n");
        for (;;) {
        }
    }

    printf("\r\n  Phase 1 reussie. Avant la phase 2, verifier :\r\n");
    printf("    - cavalier HW1 (CN4 4-5) RETIRE sur chaque carte ;\r\n");
    printf("    - transceiver alimente en 5 V, VIO en 3,3 V ;\r\n");
    printf("    - environ 60 ohms entre CAN_H et CAN_L, hors tension.\r\n");

    phase2_ping_pong();
    return 0;
}

void HAL_MspInit(void) {
    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_RCC_SYSCFG_CLK_ENABLE();
}

void bench_clock_failure(void) {
    __disable_irq();
    for (;;) {
    }
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line) {
    (void)file;
    (void)line;
    bench_clock_failure();
}
#endif
