/**
 * @file main.c
 * @brief Point d'entrée du firmware d'un nœud, commun aux deux cartes.
 *
 * Boucle principale coopérative : l'ISR ne fait que remplir le tampon
 * circulaire, tout le traitement se passe ici. Le rôle du nœud vient de
 * `BENCH_NODE_ID`, fixé par le preset CMake ; la carte et le contrôleur en
 * découlent (N1 à N3 sur Nucleo-G431KB, N4 sur Blue Pill F103).
 *
 * Ce fichier ne dépend du port que par des noms que chaque port fournit à
 * l'identique : `bench_port_can_t`, `bench_port_can_bind()`,
 * `bench_port_can_poll()`, et les constantes de son `board.h`. Les appels HAL
 * utilisés ici (`HAL_Init`, `HAL_GetTick`, `HAL_GPIO_*`) existent sous le même
 * nom dans les HAL G4 et F1.
 */

#include "app/faults.h"
#include "app/node.h"
#include "board.h"
#include "can_port.h"
#include "clock.h"
#include "icd_gen.h"
#include "util/ring_buffer.h"

#ifndef BENCH_NODE_ID
#error "BENCH_NODE_ID doit etre defini (1 a 4) ; utiliser un preset n1 a n4."
#endif

static bench_ring_t     s_rx_ring;
static bench_port_can_t s_port;
static bench_can_t      s_can;
static bench_node_t     s_node;
static bench_faults_t   s_faults;

/** LED d'erreur allumée en error-passive, LED bus-off en bus-off. */
static void update_leds(const bench_can_status_t *status, uint32_t now_ms,
                        uint32_t last_tx_ms) {
    HAL_GPIO_WritePin(BENCH_LED_ERROR_PORT, BENCH_LED_ERROR_PIN,
                      (status->state == BENCH_CAN_ERROR_PASSIVE) ? GPIO_PIN_SET
                                                                 : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(BENCH_LED_BUSOFF_PORT, BENCH_LED_BUSOFF_PIN,
                      (status->state == BENCH_CAN_BUS_OFF) ? GPIO_PIN_SET : GPIO_PIN_RESET);
    /* La polarité de la LED TX dépend de la carte : LD2 de la Nucleo s'allume
     * au niveau haut, la LED PC13 de la Blue Pill au niveau bas. */
    HAL_GPIO_WritePin(BENCH_LED_TX_PORT, BENCH_LED_TX_PIN,
                      ((now_ms - last_tx_ms) < BENCH_LED_TX_PULSE_MS) ? BENCH_LED_TX_ON
                                                                      : BENCH_LED_TX_OFF);
}

static void leds_init(void) {
    GPIO_InitTypeDef gpio = {0};

    BENCH_LED_CLK_ENABLE();

    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;

    gpio.Pin = BENCH_LED_ERROR_PIN;
    HAL_GPIO_Init(BENCH_LED_ERROR_PORT, &gpio);
    gpio.Pin = BENCH_LED_BUSOFF_PIN;
    HAL_GPIO_Init(BENCH_LED_BUSOFF_PORT, &gpio);

    /* Sur la Nucleo, PB8 est aussi BOOT0 : le piloter en sortie est sans danger,
     * il n'est échantillonné qu'au reset (RM0440 §2.6). */
    HAL_GPIO_WritePin(BENCH_LED_TX_PORT, BENCH_LED_TX_PIN, BENCH_LED_TX_OFF);
    gpio.Pin = BENCH_LED_TX_PIN;
    HAL_GPIO_Init(BENCH_LED_TX_PORT, &gpio);
}

int main(void) {
    HAL_Init();
    bench_clock_config();
    leds_init();

    bench_ring_init(&s_rx_ring);
    bench_port_can_bind(&s_port, &s_rx_ring, &s_can);

    bench_can_config_t config = {0};
    config.timing.prescaler = BENCH_CAN_PRESCALER;
    config.timing.tseg1 = BENCH_CAN_TSEG1;
    config.timing.tseg2 = BENCH_CAN_TSEG2;
    config.timing.sjw = BENCH_CAN_SJW;
    config.busoff_policy = BENCH_BUSOFF_AUTO;
    config.silent = false;
    config.auto_retransmit = true;  /* indispensable à l'arbitrage */

    if (!s_can.ops->open(s_can.ctx, &config)) {
        bench_fatal("ouverture du controleur " BENCH_CAN_PERIPH_NAME " impossible.");
    }

    bench_node_init(&s_node, BENCH_NODE_ID, &s_can, &s_rx_ring, bench_clock_is_qualified());
    bench_faults_init(&s_faults, &s_can, &config);

    uint32_t last_tx_ms = 0u;

    for (;;) {
        const uint32_t now_ms = HAL_GetTick();
        bench_can_frame_t frame;
        bench_can_status_t status;

        bench_port_can_poll(&s_port);
        s_can.ops->status(s_can.ctx, &status);

        /* Vidange du tampon : l'ordre de réception est conservé, c'est lui qui
         * porte la mesure du rang d'arbitrage. */
        while (bench_ring_pop(&s_rx_ring, &frame)) {
            if (bench_node_on_frame(&s_node, &frame, now_ms) && s_node.is_contender) {
                bench_can_frame_t tx = {0};
                tx.id = s_node.tx_id;
                tx.dlc = 8u;
                /* Le rang n'est pas figé ici mais à la confirmation d'émission,
                 * qui revient par le tampon (BENCH_FRAME_OWN_TX), dans l'ordre
                 * du bus : à l'armement, GO n'est pas encore passé. */
                if (s_can.ops->arm(s_can.ctx, &tx)) {
                    s_node.frames_sent++;
                    last_tx_ms = now_ms;
                }
            }
        }

        /* Le mode courant revient de lui-même à normal à l'échéance, dans
         * bench_node_tick() : l'exécuteur remet alors le contrôleur en état. */
        const uint32_t fault_frames =
            bench_faults_step(&s_faults, s_node.mode, bench_faults_id(&s_node), now_ms);
        if (fault_frames != 0u) {
            s_node.frames_sent += fault_frames;
            last_tx_ms = now_ms;
        }

        uint8_t heartbeat[8];
        if (bench_node_tick(&s_node, now_ms, &status, heartbeat)) {
            bench_can_frame_t hb = {0};
            hb.id = bench_heartbeat_id(s_node.node_id);
            hb.dlc = 8u;
            for (uint8_t i = 0u; i < 8u; i++) {
                hb.data[i] = heartbeat[i];
            }
            if (s_can.ops->send(s_can.ctx, &hb)) {
                last_tx_ms = now_ms;
            }
        }

        update_leds(&status, now_ms, last_tx_ms);
    }
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line) {
    (void)file;
    (void)line;
    bench_fatal("assertion HAL en echec.");
}
#endif
