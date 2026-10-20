/**
 * @file serial.c
 * @brief Journal serie sur le VCP du ST-LINK.
 */

#include "serial.h"

#include "board.h"

#if BENCH_HAS_SERIAL_LOG

#include <stdio.h>

static UART_HandleTypeDef s_uart;

/** Defini dans syscalls.c ; _write() y envoie la sortie de printf(). */
extern UART_HandleTypeDef *bench_log_uart;

bool bench_serial_open(void) {
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_USART2_CLK_ENABLE();

    gpio.Pin = BENCH_UART_TX_PIN | BENCH_UART_RX_PIN;
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = BENCH_UART_AF;
    HAL_GPIO_Init(BENCH_UART_TX_PORT, &gpio);

    s_uart.Instance = BENCH_UART_INSTANCE;
    s_uart.Init.BaudRate = BENCH_UART_BAUD;
    s_uart.Init.WordLength = UART_WORDLENGTH_8B;
    s_uart.Init.StopBits = UART_STOPBITS_1;
    s_uart.Init.Parity = UART_PARITY_NONE;
    s_uart.Init.Mode = UART_MODE_TX_RX;
    s_uart.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    s_uart.Init.OverSampling = UART_OVERSAMPLING_16;
    s_uart.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
    s_uart.Init.ClockPrescaler = UART_PRESCALER_DIV1;
    s_uart.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;

    if (HAL_UART_Init(&s_uart) != HAL_OK) {
        return false;
    }

    bench_log_uart = &s_uart;
    /* Sans tampon : chaque ligne part immediatement, ce qui evite de perdre la
     * fin du journal si la carte est reinitialisee pendant la mise en route. */
    setvbuf(stdout, NULL, _IONBF, 0);
    return true;
}

#else  /* journal serie desactive */

bool bench_serial_open(void) {
    return false;
}

#endif
