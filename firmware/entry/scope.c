/**
 * @file scope.c
 * @brief Trames de mise au point pour l'oscilloscope : N1 et N2 émettent en continu.
 *
 * Remplace `main.c` lorsque le firmware est compilé avec `-DBENCH_SCOPE=ON`
 * (presets `n1-scope-direct` et `n2-scope-direct`). Le but est de pouvoir
 * **reconnaître à l'écran** quel nœud parle et ce qu'il dit, sans décodeur :
 *
 * | Nœud | Identifiant | Données                        | Cadence                       |
 * |------|-------------|--------------------------------|-------------------------------|
 * | N1   | 0x0F0       | `54 65 73 74` = ASCII « Test » | toutes les 20 ms              |
 * | N2   | 0x20F       | `54 65 73 74` = ASCII « Test » | 5 ms après chaque trame de N1 |
 *
 * Le message est du texte : « T » = 0x54, « e » = 0x65, « s » = 0x73, « t » = 0x74.
 * Les deux nœuds disent la même chose : c'est **l'identifiant** qui dit qui
 * parle. 0x0F0 = `000 1111 0000` pour N1 et 0x20F = `010 0000 1111` pour N2 se
 * distinguent d'un coup d'œil. N1 a l'identifiant le plus bas : s'il y avait
 * collision, il gagnerait l'arbitrage. La suite de bits exacte de chaque trame,
 * bourrage compris, est dans docs/oscilloscope.md.
 *
 * **Contenu fixe, volontairement.** Aucun compteur : la trame est identique à
 * chaque émission, donc l'oscilloscope peut se déclencher dessus et la superposer
 * sans qu'un champ change. Le CRC est donc fixe lui aussi.
 *
 * **Cadence découplée.** N2 émet 5 ms après avoir entendu N1 : les deux trames ne
 * se chevauchent jamais, et chacune est suivie de silence. Si N1 se tait, N2
 * émet quand même toutes les 20 ms, pour que le bus ne soit jamais muet.
 *
 * Le journal série (VCP, 115200 bauds) affiche une fois par seconde ce que le
 * nœud a émis et l'état du contrôleur.
 */

#include <stdio.h>

#include "board.h"
#include "can_port.h"
#include "clock.h"
#include "icd_gen.h"
#include "serial.h"
#include "util/ring_buffer.h"

#if BENCH_NODE_ID != 1 && BENCH_NODE_ID != 2
#error "Le mode scope ne definit des trames que pour N1 et N2."
#endif

#define SCOPE_PERIOD_MS      20u  /* cadence de N1, et de N2 si N1 est absent */
#define SCOPE_REPLY_DELAY_MS 5u   /* N2 : delai apres la trame de N1 */
#define SCOPE_N1_TIMEOUT_MS  60u  /* N2 : N1 est considere absent au-dela */

#define SCOPE_ID_N1 0x0F0u
#define SCOPE_ID_N2 0x20Fu

/** « Test » en ASCII : 0x54 0x65 0x73 0x74. Identique sur N1 et N2. */
#define SCOPE_DLC 4u
static const uint8_t k_data[SCOPE_DLC] = {'T', 'e', 's', 't'};

static bench_ring_t     s_rx_ring;
static bench_port_can_t s_port;
static bench_can_t      s_can;

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

static bool send_scope_frame(void) {
    bench_can_frame_t tx = {0};

#if BENCH_NODE_ID == 1
    tx.id = SCOPE_ID_N1;
#else
    tx.id = SCOPE_ID_N2;
#endif
    for (uint8_t i = 0u; i < SCOPE_DLC; i++) {
        tx.data[i] = k_data[i];
    }
    tx.dlc = SCOPE_DLC;
    return s_can.ops->send(s_can.ctx, &tx);
}

static void print_status(uint32_t now_ms, uint32_t sent, uint32_t heard) {
    bench_can_status_t status;
    static const char *const k_states[] = {"error-active", "error-warning", "error-passive",
                                           "BUS-OFF"};

    s_can.ops->status(s_can.ctx, &status);
    printf("  t=%6lus  emises=%-6lu entendues=%-6lu etat=%-13s TEC=%3u REC=%3u LEC=%u\r\n",
           (unsigned long)(now_ms / 1000u), (unsigned long)sent, (unsigned long)heard,
           k_states[status.state], (unsigned)status.tec, (unsigned)status.rec,
           (unsigned)status.last_error_code);
}

int main(void) {
    HAL_Init();
    bench_clock_config();
    (void)bench_serial_open();

    printf("\r\n\r\n============================================================\r\n");
    printf(" Trames pour oscilloscope - noeud N%u - %s\r\n", (unsigned)BENCH_NODE_ID,
           BENCH_BOARD_NAME);
    printf("============================================================\r\n");
    printf("  Horloge     : %s\r\n", bench_clock_source_name());
    printf("  Temps de bit: %lu bit/s\r\n", (unsigned long)BENCH_BITRATE);
#ifdef BENCH_CAN_DIRECT
    printf("  Bus         : DIRECT, sans transceiver (TX a drain ouvert)\r\n");
#endif
#if BENCH_NODE_ID == 1
    printf("  Ce noeud emet : id=0x%03X dlc=%u data=54 65 73 74 (Test)\r\n", SCOPE_ID_N1,
           (unsigned)SCOPE_DLC);
    printf("  Cadence       : toutes les %u ms\r\n", (unsigned)SCOPE_PERIOD_MS);
#else
    printf("  Ce noeud emet : id=0x%03X dlc=%u data=54 65 73 74 (Test)\r\n", SCOPE_ID_N2,
           (unsigned)SCOPE_DLC);
    printf("  Cadence       : %u ms apres chaque trame de N1 (0x%03X),\r\n",
           (unsigned)SCOPE_REPLY_DELAY_MS, SCOPE_ID_N1);
    printf("                  ou toutes les %u ms si N1 se tait.\r\n", (unsigned)SCOPE_PERIOD_MS);
#endif
    printf("\r\n");

    bench_ring_init(&s_rx_ring);
    bench_port_can_bind(&s_port, &s_rx_ring, &s_can);

    if (!open_can()) {
        bench_fatal("ouverture du controleur " BENCH_CAN_PERIPH_NAME " impossible.");
    }

    uint32_t sent = 0u;
    uint32_t heard = 0u;
    uint32_t next_tx_ms = HAL_GetTick() + SCOPE_PERIOD_MS;
    uint32_t next_report_ms = 0u;
#if BENCH_NODE_ID == 2
    uint32_t last_n1_ms = 0u;
    bool     n1_seen = false;
#endif

    for (;;) {
        const uint32_t now_ms = HAL_GetTick();
        bench_can_frame_t rx;

        bench_port_can_poll(&s_port);

        while (bench_ring_pop(&s_rx_ring, &rx)) {
            heard++;
#if BENCH_NODE_ID == 2
            if (rx.id == SCOPE_ID_N1) {
                /* N2 se cale sur N1 : sa trame suivra la sienne de 5 ms. */
                last_n1_ms = now_ms;
                n1_seen = true;
                next_tx_ms = now_ms + SCOPE_REPLY_DELAY_MS;
            }
#endif
        }

#if BENCH_NODE_ID == 2
        /* N1 absent : retour a une cadence propre, pour que le bus reste anime. */
        if (n1_seen && (now_ms - last_n1_ms) > SCOPE_N1_TIMEOUT_MS) {
            n1_seen = false;
            next_tx_ms = now_ms;
        }
#endif

        if ((int32_t)(now_ms - next_tx_ms) >= 0) {
            if (send_scope_frame()) {
                sent++;
            }
#if BENCH_NODE_ID == 1
            next_tx_ms += SCOPE_PERIOD_MS;
#else
            /* Avec N1 present, la prochaine emission est calee par sa prochaine
             * trame ; sans lui, on repart sur la cadence propre. */
            next_tx_ms = now_ms + (n1_seen ? (3u * SCOPE_PERIOD_MS) : SCOPE_PERIOD_MS);
#endif
        }

        if ((int32_t)(now_ms - next_report_ms) >= 0) {
            print_status(now_ms, sent, heard);
            next_report_ms = now_ms + 1000u;
        }
    }
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line) {
    (void)file;
    (void)line;
    bench_fatal("assertion HAL en echec.");
}
#endif
