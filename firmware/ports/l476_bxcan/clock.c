/**
 * @file clock.c
 * @brief Arbre d'horloge du STM32L476RG (pont CAN-USB).
 *
 * Objectif : SYSCLK = PCLK1 = 80 MHz, qui cadence le bxCAN. Avec un prédiviseur
 * de 10 et 16 quanta de temps, on obtient 500 kbit/s et un point
 * d'échantillonnage à 87,5 %, comme sur les autres cartes du banc.
 *
 * Deux sources, essayées dans cet ordre :
 *
 * - **HSE en mode bypass** : la Nucleo-64 reçoit par défaut 8 MHz du ST-LINK
 *   (MCO). C'est l'horloge d'un quartz : valable pour juger un débit.
 *   `TODO(verif)` : configuration d'usine des ponts SB50, SB54 et SB55.
 * - **HSI16**, si le HSE ne démarre pas. ±1 % : acceptable pour faire parler le
 *   pont avec les autres nœuds (eux aussi sur HSI) mais **pas** pour valider un
 *   débit. Le pont l'indique (`bench_clock_is_qualified()` faux).
 */

#include "clock.h"

#include "board.h"

static bool s_hse_used;

/** Tentative sur le HSE 8 MHz fourni par le ST-LINK : vrai si le PLL a accroché. */
static bool try_hse(void) {
    RCC_OscInitTypeDef osc = {0};

    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState = RCC_HSE_BYPASS;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLM = 1u;   /* 8 MHz / 1 */
    osc.PLL.PLLN = 20u;  /* VCO 160 MHz */
    osc.PLL.PLLP = RCC_PLLP_DIV7;
    osc.PLL.PLLQ = RCC_PLLQ_DIV2;
    osc.PLL.PLLR = RCC_PLLR_DIV2;  /* 80 MHz */
    return HAL_RCC_OscConfig(&osc) == HAL_OK;
}

static void use_hsi(void) {
    RCC_OscInitTypeDef osc = {0};

    /* Le HSE n'a pas démarré : on le coupe pour ne pas laisser un oscillateur
     * à moitié lancé, puis on bâtit le même arbre sur le HSI16. */
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE | RCC_OSCILLATORTYPE_HSI;
    osc.HSEState = RCC_HSE_OFF;
    osc.HSIState = RCC_HSI_ON;
    osc.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSI;
    osc.PLL.PLLM = 2u;   /* 16 MHz / 2 = 8 MHz */
    osc.PLL.PLLN = 20u;  /* VCO 160 MHz */
    osc.PLL.PLLP = RCC_PLLP_DIV7;
    osc.PLL.PLLQ = RCC_PLLQ_DIV2;
    osc.PLL.PLLR = RCC_PLLR_DIV2;  /* 80 MHz */
    if (HAL_RCC_OscConfig(&osc) != HAL_OK) {
        bench_clock_failure();
    }
}

void bench_clock_config(void) {
    RCC_ClkInitTypeDef clk = {0};

    s_hse_used = try_hse();
    if (!s_hse_used) {
        use_hsi();
    }

    clk.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_PCLK1 |
                    RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV1;  /* 80 MHz : maximum d'APB1, horloge du bxCAN */
    clk.APB2CLKDivider = RCC_HCLK_DIV1;

    /* Quatre états d'attente à 80 MHz (RM0351, FLASH_ACR.LATENCY). */
    if (HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_4) != HAL_OK) {
        bench_clock_failure();
    }
}

bool bench_clock_is_qualified(void) {
    return s_hse_used;
}

const char *bench_clock_source_name(void) {
    return s_hse_used ? "HSE 8MHz (MCO ST-LINK)" : "HSI16 - NON VALIDE";
}

uint32_t bench_clock_can_hz(void) {
    return HAL_RCC_GetPCLK1Freq();
}

/** Appelée par HAL_Init() : horloges des blocs système utilisés par la HAL. */
void HAL_MspInit(void) {
    __HAL_RCC_SYSCFG_CLK_ENABLE();
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

    (void)reason;  /* aucun texte : le port série porte le flux slcan */

    BENCH_LED_CLK_ENABLE();
    gpio.Pin = BENCH_LED_PIN;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(BENCH_LED_PORT, &gpio);

    for (;;) {
        HAL_GPIO_TogglePin(BENCH_LED_PORT, BENCH_LED_PIN);
        busy_wait(200000u);
    }
}

void bench_clock_failure(void) {
    bench_fatal("PLL");
}
