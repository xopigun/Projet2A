/**
 * @file board.h
 * @brief Affectation des broches et de l'horloge — Nucleo-L476RG (MB1136), pont CAN-USB.
 *
 * Cette carte n'est pas un nœud du banc : elle sert d'**adaptateur** entre le bus
 * et le PC (`entry/slcan_bridge.c`, protocole slcan sur le port COM virtuel du
 * ST-LINK), à la place d'un CANable. Le STM32L476RG possède un bxCAN, le même
 * type de contrôleur que le F103 du nœud N4.
 *
 * Sources : UM1724 (Nucleo-64) et DS10198 (STM32L476xx). Ce qui n'a pas été
 * relu dans ces documents est marqué `TODO(verif)`.
 *
 * Connexions au bus :
 *
 *  | Signal  | Broche | Connecteur morpho    | Remarque                         |
 *  |---------|--------|----------------------|----------------------------------|
 *  | CAN1_RX | PA11   | CN10 broche 14       | AF9                              |
 *  | CAN1_TX | PA12   | CN10 broche 12       | AF9                              |
 *  | GND     | -      | CN10 broche 9 ou 20  | masse commune avec le bus        |
 *
 * `TODO(verif)` : numéros de broches de CN10 à confirmer dans UM1724 Table 19
 * avant câblage. PA11 et PA12 ne sont pas reliées au connecteur USB de la carte
 * (l'USB du L476 n'est pas utilisé), donc sans conflit.
 */

#ifndef BENCH_BOARD_H
#define BENCH_BOARD_H

#include "stm32l4xx_hal.h"

#define BENCH_BOARD_NAME "Nucleo-L476RG"

/* -------------------------------------------------------------------- horloge
 * HSE = 8 MHz fournis par le ST-LINK (broche MCO), configuration d'usine de la
 * carte (`TODO(verif)` : UM1724 §6.7, SB50/SB54/SB55). L'horloge est alors celle
 * d'un quartz ; si elle est absente, bench_clock_config() retombe sur le HSI16 et
 * le pont l'annonce (HSI non valide pour juger un débit).
 *
 * PLL : (8 MHz / 1) x 20 / 2 = 80 MHz. HSI : (16 MHz / 2) x 20 / 2 = 80 MHz.
 */
#define BENCH_HSE_HZ 8000000u
#define BENCH_HSI_HZ 16000000u

#define BENCH_SYSCLK_HZ 80000000u
#define BENCH_PCLK1_HZ  80000000u  /**< horloge du bxCAN */

/* ------------------------------------------------------------ temps de bit
 * 500 kbit/s : 80 MHz / 10 = 8 MHz, soit 16 quanta de 125 ns, point
 * d'échantillonnage à (1 + 13) / 16 = 87,5 % — le même que sur les autres
 * cartes. Les autres débits slcan (S0 à S8) gardent 16 quanta et changent le
 * prédiviseur : voir slcan_bridge.c.
 */
/** Prédiviseur de 500 kbit/s ; les autres débits slcan le recalculent (slcan_bridge.c). */
#define BENCH_CAN_PRESCALER 10u
#define BENCH_CAN_TSEG1 13u
#define BENCH_CAN_TSEG2 2u
#define BENCH_CAN_SJW   2u
#define BENCH_CAN_TQ_PER_BIT 16u

/* -------------------------------------------------------------------- CAN */
#define BENCH_CAN_RX_PORT GPIOA
#define BENCH_CAN_RX_PIN  GPIO_PIN_11
#define BENCH_CAN_TX_PORT GPIOA
#define BENCH_CAN_TX_PIN  GPIO_PIN_12
#define BENCH_CAN_AF      GPIO_AF9_CAN1

/** Pas de broche S de transceiver sur cette carte. */
#define BENCH_HAS_TRANSCEIVER_STANDBY 0

/* -------------------------------------------------------------------- LED */
/** LD2 (verte) = PA5 (UM1724 §6.5). Clignote à chaque trame transmise au PC. */
#define BENCH_LED_PORT GPIOA
#define BENCH_LED_PIN  GPIO_PIN_5
#define BENCH_LED_CLK_ENABLE() __HAL_RCC_GPIOA_CLK_ENABLE()
#define BENCH_LED_PULSE_MS 20u

/* ----------------------------------------------------- liaison avec le PC
 * Port COM virtuel du ST-LINK : USART2 sur PA2 (TX) et PA3 (RX), AF7 (UM1724
 * §6.8). C'est le canal slcan : rien d'autre ne doit y écrire (pas de printf).
 */
#define BENCH_HAS_SERIAL_LOG 0
#define BENCH_UART_INSTANCE  USART2
#define BENCH_UART_TX_PORT   GPIOA
#define BENCH_UART_TX_PIN    GPIO_PIN_2
#define BENCH_UART_RX_PORT   GPIOA
#define BENCH_UART_RX_PIN    GPIO_PIN_3
#define BENCH_UART_AF        GPIO_AF7_USART2
#define BENCH_UART_BAUD      115200u

/* Horloge fiable pour le CAN ? Renseigné à l'exécution par clock.c. */
#define BENCH_CLOCK_FIX_HINT \
    "Verifier que le ST-LINK fournit bien le MCO 8 MHz (UM1724, SB50/SB54/SB55)."

#endif /* BENCH_BOARD_H */
