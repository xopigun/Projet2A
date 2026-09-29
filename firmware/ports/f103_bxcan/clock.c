/**
 * @file clock.c
 * @brief Configuration de l'arbre d'horloge du STM32F103 (nœud N4).
 *
 * HSE 8 MHz × 9 = 72 MHz pour le cœur ; APB1 divisé par 2 donne 36 MHz, son
 * maximum, qui cadence le bxCAN. Avec un prescaler de 9 et 8 quanta de temps,
 * on obtient 500 kbit/s et un point d'échantillonnage à 87,5 %, identique à
 * celui du G431 (voir scripts/bit_timing.py).
 *
 * Il n'y a pas de repli HSI : sur le F103, HSI / 2 × 16 plafonne à 64 MHz et
 * donnerait un autre arbre, donc un autre temps de bit. Un quartz qui ne démarre
 * pas est un arrêt fatal, affiché sur le journal série.
 */

#include "clock.h"

#include <stdio.h>

#include "board.h"
#include "serial.h"

void bench_clock_config(void) {
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};

    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState = RCC_HSE_ON;
    osc.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
    osc.HSIState = RCC_HSI_ON;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLMUL = RCC_PLL_MUL9;  /* 8 MHz x 9 = 72 MHz */

    if (HAL_RCC_OscConfig(&osc) != HAL_OK) {
        bench_clock_failure();
    }

    clk.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_PCLK1 |
                    RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV2;  /* 36 MHz : maximum d'APB1, horloge du bxCAN */
    clk.APB2CLKDivider = RCC_HCLK_DIV1;

    /* Deux états d'attente entre 48 et 72 MHz (RM0008, FLASH_ACR.LATENCY). */
    if (HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_2) != HAL_OK) {
        bench_clock_failure();
    }
}

bool bench_clock_is_qualified(void) {
    return BENCH_CLOCK_QUALIFIED != 0;
}

const char *bench_clock_source_name(void) {
    return "HSE 8MHz";
}

uint32_t bench_clock_can_hz(void) {
    return HAL_RCC_GetPCLK1Freq();
}

/** Appelée par HAL_Init() : AFIO sert au remappage du CAN sur PB8/PB9. */
void HAL_MspInit(void) {
    __HAL_RCC_AFIO_CLK_ENABLE();
    __HAL_RCC_PWR_CLK_ENABLE();
}

/* ------------------------------------------------------------------ arrets -- */

/** Attente active, indépendante de SysTick et des interruptions. */
static void busy_wait(uint32_t loops) {
    for (volatile uint32_t i = 0u; i < loops; i++) {
    }
}

void bench_fatal(const char *reason) {
    GPIO_InitTypeDef gpio = {0};

    /* Si l'horloge n'a pas pu être configurée, le MCU tourne encore sur le HSI
     * de reset : la HAL recalcule le débit de l'USART sur la fréquence réelle. */
    (void)bench_serial_open();
    printf("\r\n\r\n*** ARRET FATAL : %s\r\n", reason);
    printf("*** Le noeud n'emet plus rien. La LED PC13 clignote rapidement.\r\n");

    __HAL_RCC_GPIOC_CLK_ENABLE();
    gpio.Pin = BENCH_LED_TX_PIN;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;  /* PC13 : 2 MHz au plus (DS5319 Table 5, note 5) */
    HAL_GPIO_Init(BENCH_LED_TX_PORT, &gpio);

    for (;;) {
        HAL_GPIO_TogglePin(BENCH_LED_TX_PORT, BENCH_LED_TX_PIN);
        busy_wait(200000u);  /* quelques Hz, que l'horloge soit à 8 ou 72 MHz */
    }
}

void bench_clock_failure(void) {
    bench_fatal("le quartz HSE ou le PLL ne demarre pas. Verifier le quartz de 8 MHz "
                "de la carte (TODO(verif) V12).");
}
