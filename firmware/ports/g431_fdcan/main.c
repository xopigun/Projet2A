/**
 * @file main.c
 * @brief Point d'entrée du firmware d'un nœud sur Nucleo-G431KB.
 *
 * Boucle principale coopérative : l'ISR ne fait que remplir le tampon
 * circulaire, tout le traitement se passe ici. Le rôle du nœud vient de
 * `BENCH_NODE_ID`, fixé par le preset CMake.
 */

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
static bench_g431_can_t s_port;
static bench_can_t      s_can;
static bench_node_t     s_node;

/** LED d'erreur allumée en error-passive, LED bus-off en bus-off. */
static void update_leds(const bench_can_status_t *status, uint32_t now_ms,
                        uint32_t last_tx_ms) {
    HAL_GPIO_WritePin(BENCH_LED_ERROR_PORT, BENCH_LED_ERROR_PIN,
                      (status->state == BENCH_CAN_ERROR_PASSIVE) ? GPIO_PIN_SET
                                                                 : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(BENCH_LED_BUSOFF_PORT, BENCH_LED_BUSOFF_PIN,
                      (status->state == BENCH_CAN_BUS_OFF) ? GPIO_PIN_SET : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(BENCH_LED_TX_PORT, BENCH_LED_TX_PIN,
                      ((now_ms - last_tx_ms) < BENCH_LED_TX_PULSE_MS) ? GPIO_PIN_SET
                                                                      : GPIO_PIN_RESET);
}

static void leds_init(void) {
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;

    gpio.Pin = BENCH_LED_ERROR_PIN | BENCH_LED_BUSOFF_PIN;
    HAL_GPIO_Init(BENCH_LED_ERROR_PORT, &gpio);

    /* PB8 est aussi BOOT0 : piloter la broche en sortie est sans danger, elle
     * n'est échantillonnée qu'au reset et ne porte aucune résistance de tirage. */
    gpio.Pin = BENCH_LED_TX_PIN;
    HAL_GPIO_Init(BENCH_LED_TX_PORT, &gpio);
}

int main(void) {
    HAL_Init();
    bench_clock_config();
    leds_init();

    bench_ring_init(&s_rx_ring);
    bench_g431_can_bind(&s_port, &s_rx_ring, &s_can);

    bench_can_config_t config = {0};
    config.timing.prescaler = BENCH_CAN_PRESCALER;
    config.timing.tseg1 = BENCH_CAN_TSEG1;
    config.timing.tseg2 = BENCH_CAN_TSEG2;
    config.timing.sjw = BENCH_CAN_SJW;
    config.busoff_policy = BENCH_BUSOFF_AUTO;
    config.silent = false;
    config.auto_retransmit = true;  /* indispensable à l'arbitrage */

    if (!s_can.ops->open(s_can.ctx, &config)) {
        bench_fatal("ouverture du FDCAN impossible.");
    }

    bench_node_init(&s_node, BENCH_NODE_ID, &s_can, &s_rx_ring, bench_clock_is_qualified());

    uint32_t last_tx_ms = 0u;

    for (;;) {
        const uint32_t now_ms = HAL_GetTick();
        bench_can_frame_t frame;
        bench_can_status_t status;

        bench_g431_can_poll(&s_port);
        s_can.ops->status(s_can.ctx, &status);

        /* Vidange du tampon : l'ordre de réception est conservé, c'est lui qui
         * porte la mesure du rang d'arbitrage. */
        while (bench_ring_pop(&s_rx_ring, &frame)) {
            if (bench_node_on_frame(&s_node, &frame, now_ms) && s_node.is_contender) {
                bench_can_frame_t tx = {0};
                tx.id = s_node.tx_id;
                tx.dlc = 8u;
                if (s_can.ops->arm(s_can.ctx, &tx)) {
                    s_node.frames_sent++;
                    last_tx_ms = now_ms;
                    bench_arb_on_own_tx(&s_node.arb);
                }
            }
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

void HAL_MspInit(void) {
    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_RCC_SYSCFG_CLK_ENABLE();
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line) {
    (void)file;
    (void)line;
    bench_fatal("assertion HAL en echec.");
}
#endif
