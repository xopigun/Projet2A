/**
 * @file board.h
 * @brief Brochage et horloges de la carte NUCLEO-G431KB.
 *
 * **Tout** le brochage du nœud est ici, et nulle part ailleurs. Aucune autre
 * unité de compilation ne doit contenir de numéro de broche ni de fréquence.
 *
 * Sources
 * -------
 * Sauf mention contraire, chaque affectation vient de **UM2397 Rev 2**
 * (manuel utilisateur de la carte MB1430), Table 11 (connecteurs Arduino Nano)
 * et Table 12 (affectation des 32 broches du boîtier UFQFPN32).
 *
 * Écarts assumés par rapport au dossier de définition v0.1
 * --------------------------------------------------------
 * 1. Le dossier place I2C1 sur `PB8` (SCL) et `PB9` (SDA). **PB9 n'existe pas**
 *    sur le boîtier UFQFPN32 : UM2397 Table 12 énumère PA0-PA15, PB0, PB3-PB8,
 *    PF0, PF1 et PG10, sans PB9. De plus PB8 est la broche BOOT0, et une
 *    résistance de tirage I2C vers 3,3 V y forcerait le démarrage sur le
 *    bootloader système. I2C1 est donc porté par `PA15` et `PB7`.
 *
 * 2. Le dossier place une LED sur `PA2`, qui est le TX du port COM virtuel du
 *    ST-LINK (UM2397 Table 8 et Table 9 : SB1 fermé par défaut). La LED est
 *    déplacée sur `PB8`, où se trouve déjà la LED utilisateur LD2 de la carte.
 *    Piloter PB8 en sortie est sans danger : BOOT0 n'est échantillonné qu'au
 *    reset, et aucune résistance de tirage n'y est ajoutée.
 *
 * Montage matériel requis
 * -----------------------
 * - **Retirer le cavalier HW1** entre CN4 broche 5 (`D2` = PA12) et CN4 broche 4
 *   (`GND`), monté en sortie d'usine (UM2397 §5.1 étape 5 et §6.1). PA12 étant
 *   FDCAN1_TX, le laisser à la masse place le bus en dominant permanent.
 * - **Souder SB9 et SB10** pour connecter le quartz 24 MHz. Par défaut la carte
 *   démarre sur le HSI (UM2397 §6.5, Table 9 : SB8, SB9, SB10, SB11 et SB13 sont
 *   tous ouverts). Voir @ref BENCH_CLOCK_SOURCE.
 * - **Ne pas toucher à SB2 ni SB3**, fermés par défaut : ils reportent PA15 et
 *   PB7 sur A5 et A4, ce qui est l'emplacement I2C standard d'un Arduino Nano et
 *   n'entrave pas leur usage sur D5 et D4. En contrepartie, PA5 et PA6 doivent
 *   rester en entrée flottante, faute de quoi elles entrent en conflit avec PB7
 *   et PA15 via CN3 broches 7 et 8 (UM2397 Table 9).
 */

#ifndef BENCH_BOARD_H
#define BENCH_BOARD_H

#include "stm32g4xx_hal.h"

/** Nom affiché en zone « Identité » de l'écran. */
#define BENCH_BOARD_NAME "Nucleo-G431KB"

/* =========================================================================
 *  Horloges
 * ========================================================================= */

/**
 * @def BENCH_CLOCK_SOURCE
 * @brief Source d'horloge : `BENCH_CLOCK_HSE` (défaut) ou `BENCH_CLOCK_HSI`.
 *
 * Le HSI n'est **pas** une référence valable pour le CAN : il est spécifié à
 * ±1 %, soit plus du double de la tolérance admissible de 0,485 % à 500 kbit/s
 * (voir docs/bit_timing.md). Le repli existe uniquement pour permettre de
 * travailler avant la soudure de SB9/SB10 ; il se signale de trois façons : un
 * avertissement à la compilation, un bandeau « HSI - NON VALIDE » sur l'écran,
 * et le bit `clock_not_qualified` du heartbeat, qui empêche `canbench` de
 * prononcer un verdict de réussite.
 */
#define BENCH_CLOCK_HSE 1
#define BENCH_CLOCK_HSI 2

#ifndef BENCH_CLOCK_SOURCE
#define BENCH_CLOCK_SOURCE BENCH_CLOCK_HSE
#endif

#if BENCH_CLOCK_SOURCE == BENCH_CLOCK_HSI
#warning "Compilation sur HSI : reference d'horloge NON CONFORME pour le CAN "  \
         "(+/-1 % contre 0,485 % admissibles). Souder SB9 et SB10, puis "       \
         "recompiler sans -DBENCH_CLOCK_SOURCE=2. Aucun verdict de reussite "   \
         "ne peut etre prononce dans cet etat."
#define BENCH_CLOCK_QUALIFIED 0
#else
#define BENCH_CLOCK_QUALIFIED 1
#endif

/** Quartz X2 monté sur la carte : 24 MHz, 20 ppm, 6 pF (UM2397 §6.5). */
#define BENCH_HSE_HZ 24000000u

/**
 * HSI16 du STM32G4 : 15,88 à 16,08 MHz à 30 °C et 3,0 V, puis ±1 % de dérive
 * entre 0 et 85 °C (DS12589 Rev 6, Table 42). Les deux se cumulent.
 */
#define BENCH_HSI_HZ 16000000u

/**
 * Arbre d'horloge visé : HSE 24 MHz, PLLM 3 (8 MHz), PLLN 40 (VCO 320 MHz),
 * PLLR 2 (SYSCLK 160 MHz), PLLQ 4 (horloge noyau FDCAN 80 MHz).
 *
 * SYSCLK est volontairement à 160 MHz et non au maximum de 170 MHz : c'est le
 * prix d'un point d'échantillonnage exactement à 87,5 %, partagé avec le F103.
 * À 170 MHz le meilleur candidat tombe à 88,24 %, qui ne s'aligne pas.
 *
 * Contraintes vérifiées (DS12589 Rev 6 Table 45, RM0440 Rev 9 §7.4.4) :
 * entrée PLL 8 MHz dans [2,66 ; 16], VCO 320 MHz dans [96 ; 344],
 * PLLN 40 dans [8 ; 127], sorties R et Q au plus 170 MHz en Range 1 Boost.
 * 4 états d'attente flash couvrent jusqu'à 170 MHz en Boost (RM0440 Table 9).
 */
#define BENCH_PLL_M 3u
#define BENCH_PLL_N 40u
#define BENCH_PLL_R 2u
#define BENCH_PLL_Q 4u

#define BENCH_SYSCLK_HZ 160000000u
#define BENCH_PCLK1_HZ  160000000u

/** Horloge noyau du périphérique FDCAN, source du calcul de temps de bit. */
#define BENCH_FDCAN_CLK_HZ 80000000u

/* =========================================================================
 *  Temps de bit — valeurs produites par scripts/bit_timing.py
 * =========================================================================
 *  500 kbit/s : 80 MHz / 10 / 16 tq = 500 000 bit/s
 *  Point d'échantillonnage (1 + 13) / 16 = 87,50 %
 *  Tolérance d'oscillateur admissible : 0,485 %
 *
 *  Toute modification doit être revalidée par :
 *      python scripts/bit_timing.py --check
 *  qui échoue si les nœuds ne partagent pas le même point d'échantillonnage.
 * ========================================================================= */

#define BENCH_CAN_PRESCALER 10u
#define BENCH_CAN_TSEG1     13u  /**< hors bit de synchronisation */
#define BENCH_CAN_TSEG2     2u
#define BENCH_CAN_SJW       2u

/* =========================================================================
 *  FDCAN1  (UM2397 Table 11 et Table 12)
 * =========================================================================
 *  PA11 = CN4 broche 13 = ARD_D10
 *  PA12 = CN4 broche 5  = ARD_D2   <- retirer le cavalier HW1 !
 *
 *  Fonction alternée AF9 : DS12589 Rev 6, Table 13 (PA11 = FDCAN1_RX,
 *  PA12 = FDCAN1_TX). I2C1 en AF4 et USART2 en AF7 y sont confirmés aussi.
 * ========================================================================= */

#define BENCH_CAN_RX_PORT GPIOA
#define BENCH_CAN_RX_PIN  GPIO_PIN_11
#define BENCH_CAN_TX_PORT GPIOA
#define BENCH_CAN_TX_PIN  GPIO_PIN_12
#define BENCH_CAN_AF      GPIO_AF9_FDCAN1

/** Broche S du transceiver TJA1051T/3 : niveau haut = mode silencieux. */
#define BENCH_HAS_TRANSCEIVER_STANDBY 1
#define BENCH_TRX_S_PORT GPIOB
#define BENCH_TRX_S_PIN  GPIO_PIN_6  /**< CN4 broche 9 = ARD_D6 */

/* =========================================================================
 *  I2C1 — écran SSD1306 et capteur, bus partagé
 * =========================================================================
 *  PA15 = SCL = CN4 broche 8 (ARD_D5), reporté sur CN3 broche 7 (A5) par SB3
 *  PB7  = SDA = CN4 broche 7 (ARD_D4), reporté sur CN3 broche 8 (A4) par SB2
 * ========================================================================= */

#define BENCH_I2C_INSTANCE  I2C1
#define BENCH_I2C_SCL_PORT  GPIOA
#define BENCH_I2C_SCL_PIN   GPIO_PIN_15
#define BENCH_I2C_SDA_PORT  GPIOB
#define BENCH_I2C_SDA_PIN   GPIO_PIN_7
#define BENCH_I2C_AF        GPIO_AF4_I2C1
#define BENCH_I2C_HZ        400000u

/**
 * Broches à laisser en entrée flottante : SB2 et SB3 étant fermés, PA5 et PA6
 * sont reliées à PB7 et PA15 par les broches A4 et A5 du connecteur CN3. Les
 * configurer autrement crée un conflit électrique sur le bus I2C.
 */
#define BENCH_FLOATING_PORT GPIOA
#define BENCH_FLOATING_PINS (GPIO_PIN_5 | GPIO_PIN_6)

/** Adresses I2C 7 bits, décalées à gauche pour la HAL. */
#define BENCH_OLED_ADDR   (0x3Cu << 1)
#define BENCH_MPU6050_ADDR (0x68u << 1)

/* =========================================================================
 *  LEDs d'état
 * =========================================================================
 *  PB8 porte la LED utilisateur LD2 de la carte (UM2397 §6.6.1, SB7 fermé).
 *  PA0 et PA1 sont libres (CN3 broches 12 et 11 = A0 et A1).
 * ========================================================================= */

#define BENCH_LED_TX_PORT      GPIOB
#define BENCH_LED_TX_PIN       GPIO_PIN_8
#define BENCH_LED_ERROR_PORT   GPIOA
#define BENCH_LED_ERROR_PIN    GPIO_PIN_0
#define BENCH_LED_BUSOFF_PORT  GPIOA
#define BENCH_LED_BUSOFF_PIN   GPIO_PIN_1

/** Durée de l'impulsion de la LED TX, en millisecondes. */
#define BENCH_LED_TX_PULSE_MS 20u

/* =========================================================================
 *  Journal série — port COM virtuel du ST-LINK
 * =========================================================================
 *  USART2 sur PA2 (TX) et PA3 (RX), relié au VCP par SB1 et SB12, fermés par
 *  défaut (UM2397 Table 8 et Table 9).
 * ========================================================================= */

#define BENCH_HAS_SERIAL_LOG 1
#define BENCH_UART_INSTANCE  USART2
#define BENCH_UART_TX_PORT   GPIOA
#define BENCH_UART_TX_PIN    GPIO_PIN_2
#define BENCH_UART_RX_PORT   GPIOA
#define BENCH_UART_RX_PIN    GPIO_PIN_3
#define BENCH_UART_AF        GPIO_AF7_USART2
#define BENCH_UART_BAUD      115200u

/* =========================================================================
 *  Capteurs
 * ========================================================================= */

/** Capteur à effet Hall de N2 : entrée à front, CN3 broche 9 (A3). */
#define BENCH_HALL_PORT GPIOA
#define BENCH_HALL_PIN  GPIO_PIN_4

/** Bus 1-Wire du DS18B20 de N3 : CN3 broche 6 (A6). */
#define BENCH_ONEWIRE_PORT GPIOA
#define BENCH_ONEWIRE_PIN  GPIO_PIN_7

#endif /* BENCH_BOARD_H */
