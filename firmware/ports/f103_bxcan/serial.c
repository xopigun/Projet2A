/**
 * @file serial.c
 * @brief Journal serie du noeud N4 sur USART1.
 */

#include "serial.h"

#include "board.h"

#if BENCH_HAS_SERIAL_LOG

#include <stdio.h>

static UART_HandleTypeDef s_uart;

/** Defini dans entry/syscalls.c ; _write() y envoie la sortie de printf(). */
extern UART_HandleTypeDef *bench_log_uart;

bool bench_serial_open(void) {
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_USART1_CLK_ENABLE();

    /* Sur le F1, la fonction alternee n'a pas de numero : TX en sortie
     * alternee push-pull, RX en entree (RM0008, configuration des GPIO pour
     * les peripheriques). */
    gpio.Pin = BENCH_UART_TX_PIN;
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(BENCH_UART_TX_PORT, &gpio);

    gpio.Pin = BENCH_UART_RX_PIN;
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_PULLUP;  /* ligne au repos si l'adaptateur est absent */
    HAL_GPIO_Init(BENCH_UART_RX_PORT, &gpio);

    s_uart.Instance = BENCH_UART_INSTANCE;
    s_uart.Init.BaudRate = BENCH_UART_BAUD;
    s_uart.Init.WordLength = UART_WORDLENGTH_8B;
    s_uart.Init.StopBits = UART_STOPBITS_1;
    s_uart.Init.Parity = UART_PARITY_NONE;
    s_uart.Init.Mode = UART_MODE_TX_RX;
    s_uart.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    s_uart.Init.OverSampling = UART_OVERSAMPLING_16;

    if (HAL_UART_Init(&s_uart) != HAL_OK) {
        return false;
    }

    bench_log_uart = &s_uart;
    /* Sans tampon : chaque ligne part immediatement. */
    setvbuf(stdout, NULL, _IONBF, 0);
    return true;
}

#else  /* journal serie desactive */

bool bench_serial_open(void) {
    return false;
}

#endif
