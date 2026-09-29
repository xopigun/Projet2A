/**
 * @file board.h
 * @brief Brochage et horloges de la carte « Blue Pill » (STM32F103C8T6), nœud N4.
 *
 * **Tout** le brochage du nœud est ici, et nulle part ailleurs.
 *
 * Sources
 * -------
 * - **DS5319 Rev 20** (datasheet STM32F103x8/xB), Table 5 : numéros de broche
 *   du boîtier LQFP48, fonctions alternées par défaut et remappées, broches
 *   tolérantes au 5 V (FT).
 * - **RM0008 Rev 21** (manuel de référence STM32F10x) : §9.3.4 Table 34 pour le
 *   remappage du CAN, registre FLASH_ACR pour la latence, arbre d'horloge.
 *
 * La Blue Pill n'est **pas** une carte ST : aucun schéma officiel n'existe et
 * les clones varient. Ce qui relève de la carte plutôt que du microcontrôleur
 * est donc marqué `TODO(verif)` et se vérifie sur la carte reçue (voir
 * docs/bringup.md, section N4) :
 * - quartz de 8 MHz sur OSC_IN/OSC_OUT — `TODO(verif) V12` (marquage du quartz) ;
 * - LED utilisateur sur PC13, allumée au niveau bas — `TODO(verif) V13`.
 *
 * Choix de conception
 * -------------------
 * 1. **CAN remappé sur PB8 (RX) / PB9 (TX)** (`CAN_REMAP = 10`, RM0008 Table 34,
 *    disponible sur ce boîtier 48 broches). Par défaut le CAN est sur PA11/PA12,
 *    qui portent aussi l'USB et, sur la carte, la résistance de tirage de D+.
 *    Attention à RM0008 Table 34 : la ligne du TX y est libellée « CAN_RX » par
 *    coquille ; la description du registre AFIO_MAPR lève l'ambiguïté.
 * 2. **L'USB n'est pas utilisé.** RM0008 (§ bxCAN) : sur les F103 de densité
 *    moyenne, l'USB et le CAN partagent 512 octets de SRAM dédiée et ne peuvent
 *    pas fonctionner en même temps. Le journal passe donc par USART1 et un
 *    adaptateur USB-série 3,3 V.
 * 3. **Pas de repli HSI.** Le quartz est câblé d'origine sur la Blue Pill,
 *    contrairement à la Nucleo : il n'y a pas de soudure à attendre.
 */

#ifndef BENCH_BOARD_H
#define BENCH_BOARD_H

#include "stm32f1xx_hal.h"

/** Nom affiché en zone « Identité » de l'écran. */
#define BENCH_BOARD_NAME "Blue Pill F103"

/* =========================================================================
 *  Horloges (RM0008 §7 et FLASH_ACR)
 * =========================================================================
 *  HSE 8 MHz x PLLMUL 9 = SYSCLK 72 MHz, maximum du F103 (DS5319 Features).
 *  APB1 = 72 / 2 = 36 MHz, son maximum (RM0008 : « APB1 is limited to 36 MHz ») :
 *  horloge du bxCAN.
 *  Latence flash : 2 états d'attente entre 48 et 72 MHz (FLASH_ACR.LATENCY).
 * ========================================================================= */

/** Le quartz est la seule source prévue ; voir le choix n° 3 ci-dessus. */
#define BENCH_CLOCK_QUALIFIED 1

/** Quartz de la carte — `TODO(verif) V12` : lire le marquage sur la carte reçue. */
#define BENCH_HSE_HZ 8000000u

#define BENCH_PLL_MUL   9u
#define BENCH_SYSCLK_HZ 72000000u
#define BENCH_PCLK1_HZ  36000000u

/** Horloge du bxCAN (PCLK1), source du calcul de temps de bit. */
#define BENCH_BXCAN_CLK_HZ 36000000u

/* =========================================================================
 *  Temps de bit — valeurs produites par scripts/bit_timing.py
 * =========================================================================
 *  500 kbit/s : 36 MHz / 9 / 8 tq = 500 000 bit/s
 *  Point d'échantillonnage (1 + 6) / 8 = 87,50 %, identique au G431
 *  Tolérance d'oscillateur admissible : 0,485 %
 *
 *  Toute modification doit être revalidée par :
 *      python scripts/bit_timing.py --check
 * ========================================================================= */

#define BENCH_CAN_PRESCALER 9u
#define BENCH_CAN_TSEG1     6u  /**< hors bit de synchronisation */
#define BENCH_CAN_TSEG2     1u
#define BENCH_CAN_SJW       1u

/* =========================================================================
 *  bxCAN remappé (DS5319 Table 5, colonne « Remap »)
 * =========================================================================
 *  PB8 = CANRX, broche 45 du LQFP48, FT
 *  PB9 = CANTX, broche 46 du LQFP48, FT
 * ========================================================================= */

#define BENCH_CAN_RX_PORT GPIOB
#define BENCH_CAN_RX_PIN  GPIO_PIN_8
#define BENCH_CAN_TX_PORT GPIOB
#define BENCH_CAN_TX_PIN  GPIO_PIN_9

/**
 * Broche S du transceiver TJA1051T/3 : niveau haut = mode silencieux.
 * PB12 (broche 25, FT) : aucune fonction alternée utilisée par le banc.
 */
#define BENCH_HAS_TRANSCEIVER_STANDBY 1
#define BENCH_TRX_S_PORT GPIOB
#define BENCH_TRX_S_PIN  GPIO_PIN_12

/* =========================================================================
 *  I2C1 — écran SSD1306 (lot 6), affectation par défaut sans remappage
 * =========================================================================
 *  PB6 = SCL, broche 42 ; PB7 = SDA, broche 43 ; toutes deux FT.
 *  Le remappage d'I2C1 viserait PB8/PB9, déjà pris par le CAN.
 * ========================================================================= */

#define BENCH_I2C_INSTANCE  I2C1
#define BENCH_I2C_SCL_PORT  GPIOB
#define BENCH_I2C_SCL_PIN   GPIO_PIN_6
#define BENCH_I2C_SDA_PORT  GPIOB
#define BENCH_I2C_SDA_PIN   GPIO_PIN_7
#define BENCH_I2C_HZ        400000u

#define BENCH_OLED_ADDR (0x3Cu << 1)

/* =========================================================================
 *  LEDs d'état
 * =========================================================================
 *  PC13 : LED de la carte (`TODO(verif) V13`). DS5319 Table 5 note 5 : PC13
 *  ne peut qu'absorber 3 mA et ne doit pas servir de source de courant pour
 *  une LED ; la LED est donc forcément câblée en puits, allumée au niveau bas.
 *  PA0 (broche 10) et PA1 (broche 11) : LEDs externes, comme sur la Nucleo.
 * ========================================================================= */

#define BENCH_LED_TX_PORT      GPIOC
#define BENCH_LED_TX_PIN       GPIO_PIN_13
#define BENCH_LED_ERROR_PORT   GPIOA
#define BENCH_LED_ERROR_PIN    GPIO_PIN_0
#define BENCH_LED_BUSOFF_PORT  GPIOA
#define BENCH_LED_BUSOFF_PIN   GPIO_PIN_1

/** Horloges des ports GPIO portant les LEDs. */
#define BENCH_LED_CLK_ENABLE()        \
    do {                              \
        __HAL_RCC_GPIOA_CLK_ENABLE(); \
        __HAL_RCC_GPIOC_CLK_ENABLE(); \
    } while (0)

/** LED en puits : allumée au niveau bas. */
#define BENCH_LED_TX_ON  GPIO_PIN_RESET
#define BENCH_LED_TX_OFF GPIO_PIN_SET

/** Durée de l'impulsion de la LED TX, en millisecondes. */
#define BENCH_LED_TX_PULSE_MS 20u

/* =========================================================================
 *  Journal série — USART1, vers un adaptateur USB-série 3,3 V
 * =========================================================================
 *  PA9 = USART1_TX (broche 30), PA10 = USART1_RX (broche 31), toutes deux FT.
 *  Ne relier que GND et RX de l'adaptateur à PA9 : jamais sa broche VCC.
 * ========================================================================= */

#define BENCH_HAS_SERIAL_LOG 1
#define BENCH_UART_INSTANCE  USART1
#define BENCH_UART_TX_PORT   GPIOA
#define BENCH_UART_TX_PIN    GPIO_PIN_9
#define BENCH_UART_RX_PORT   GPIOA
#define BENCH_UART_RX_PIN    GPIO_PIN_10
#define BENCH_UART_BAUD      115200u

/* =========================================================================
 *  Textes de l'autotest propres à la carte
 * ========================================================================= */

/** Vérifications à faire avant la phase 2, affichées par l'autotest. */
#define BENCH_BOARD_PRECHECKS                                                  \
    "    - transceiver sur PB8 (RXD) et PB9 (TXD), et non sur PA11/PA12 ;\r\n" \
    "    - Blue Pill alimentee par son USB (5 V pour le transceiver) ;\r\n"    \
    "    - ST-Link : ne relier que SWDIO, SWCLK et GND, pas le 3,3 V ;\r\n"     \
    "    - environ 60 ohms entre CAN_H et CAN_L, hors tension.\r\n"

/** Remède affiché si l'horloge n'était pas qualifiée ; sans objet sur N4. */
#define BENCH_CLOCK_FIX_HINT "Verifier le quartz de 8 MHz de la carte."

#endif /* BENCH_BOARD_H */
