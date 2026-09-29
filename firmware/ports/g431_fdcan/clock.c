/**
 * @file clock.c
 * @brief Configuration de l'arbre d'horloge du STM32G431.
 *
 * Deux sources possibles, choisies à la compilation par `BENCH_CLOCK_SOURCE`
 * dans `board.h` :
 *
 * - **HSE** (défaut) : quartz 24 MHz de la carte. Exige d'avoir soudé SB9 et
 *   SB10, la carte démarrant sur le HSI en sortie d'usine (UM2397 §6.5).
 * - **HSI** (repli) : utilisable seulement pour travailler avant cette soudure.
 *   Le HSI est spécifié à ±1 %, soit plus du double de la tolérance admissible
 *   de 0,485 % à 500 kbit/s : la mesure n'a alors aucune valeur de preuve.
 *
 * Dans les deux cas l'objectif est une horloge noyau FDCAN de **80 MHz**, qui
 * donne un point d'échantillonnage exactement à 87,5 % avec un prescaler de 10
 * et 16 quanta de temps — le même que sur le F103.
 */

#include "clock.h"

#include <stdio.h>

#include "board.h"
#include "serial.h"

/**
 * @brief Configure PLL, SYSCLK et l'horloge noyau du FDCAN.
 *
 * En HSE : 24 MHz / M=3 = 8 MHz, × N=40 = VCO 320 MHz, / R=2 = SYSCLK 160 MHz,
 * / Q=4 = 80 MHz pour le FDCAN.
 *
 * En HSI : 16 MHz / M=2 = 8 MHz, puis le même VCO. L'arbre est identique en
 * aval, ce qui garde le même temps de bit — seule la **précision** de la
 * référence change, et c'est précisément le problème.
 */
void bench_clock_config(void) {
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};
    RCC_PeriphCLKInitTypeDef periph = {0};

    /* 160 MHz impose l'échelle de tension 1 (Boost) et 4 états d'attente flash. */
    HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1_BOOST);

#if BENCH_CLOCK_SOURCE == BENCH_CLOCK_HSE
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState = RCC_HSE_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLM = RCC_PLLM_DIV3;
#else
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSI;
    osc.HSIState = RCC_HSI_ON;
    osc.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSI;
    osc.PLL.PLLM = RCC_PLLM_DIV2;
#endif

    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLN = BENCH_PLL_N;
    osc.PLL.PLLP = RCC_PLLP_DIV2;
    osc.PLL.PLLQ = RCC_PLLQ_DIV4;  /* -> 80 MHz pour le FDCAN */
    osc.PLL.PLLR = RCC_PLLR_DIV2;  /* -> 160 MHz pour le coeur */

    if (HAL_RCC_OscConfig(&osc) != HAL_OK) {
        bench_clock_failure();
    }

    clk.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_PCLK1 |
                    RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV1;
    clk.APB2CLKDivider = RCC_HCLK_DIV1;

    if (HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_4) != HAL_OK) {
        bench_clock_failure();
    }

    /* L'horloge noyau du FDCAN vient de PLLQ, pas de PCLK1 : c'est ce qui
     * permet d'avoir 80 MHz tout en gardant 160 MHz pour le cœur. */
    periph.PeriphClockSelection = RCC_PERIPHCLK_FDCAN | RCC_PERIPHCLK_I2C1 |
                                  RCC_PERIPHCLK_USART2;
    periph.FdcanClockSelection = RCC_FDCANCLKSOURCE_PLL;
    periph.I2c1ClockSelection = RCC_I2C1CLKSOURCE_PCLK1;
    periph.Usart2ClockSelection = RCC_USART2CLKSOURCE_PCLK1;

    if (HAL_RCCEx_PeriphCLKConfig(&periph) != HAL_OK) {
        bench_clock_failure();
    }
}

bool bench_clock_is_qualified(void) {
    return BENCH_CLOCK_QUALIFIED != 0;
}

const char *bench_clock_source_name(void) {
#if BENCH_CLOCK_SOURCE == BENCH_CLOCK_HSE
    return "HSE 24MHz";
#else
    return "HSI - NON VALIDE";
#endif
}

uint32_t bench_clock_fdcan_hz(void) {
    return HAL_RCCEx_GetPeriphCLKFreq(RCC_PERIPHCLK_FDCAN);
}

/* ------------------------------------------------------------------ arrets -- */

/** Attente active, independante de SysTick et des interruptions. */
static void busy_wait(uint32_t loops) {
    for (volatile uint32_t i = 0u; i < loops; i++) {
    }
}

void bench_fatal(const char *reason) {
    GPIO_InitTypeDef gpio = {0};

    /* Le port serie est rouvert ici : si l'horloge n'a pas pu etre configuree,
     * le MCU tourne encore sur le HSI de reset et le VCP fonctionne dessus. */
    (void)bench_serial_open();
    printf("\r\n\r\n*** ARRET FATAL : %s\r\n", reason);
    printf("*** Le noeud n'emet plus rien. LD2 clignote rapidement.\r\n");

    __HAL_RCC_GPIOB_CLK_ENABLE();
    gpio.Pin = BENCH_LED_TX_PIN;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(BENCH_LED_TX_PORT, &gpio);

    for (;;) {
        HAL_GPIO_TogglePin(BENCH_LED_TX_PORT, BENCH_LED_TX_PIN);
        busy_wait(400000u);  /* quelques Hz, que l'horloge soit a 16 ou 160 MHz */
    }
}

void bench_clock_failure(void) {
#if BENCH_CLOCK_SOURCE == BENCH_CLOCK_HSE
    bench_fatal("le quartz HSE ne demarre pas. SB9 et SB10 sont-ils soudes ? "
                "Sinon, utiliser un preset *-hsi (repli non valide pour le debit).");
#else
    bench_fatal("echec de configuration du PLL sur HSI.");
#endif
}
