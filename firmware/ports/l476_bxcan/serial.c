/**
 * @file serial.c
 * @brief USART2 sur le port COM virtuel du ST-LINK, octet par octet.
 */

#include "serial.h"

#include "board.h"

static UART_HandleTypeDef s_uart;
static uint32_t           s_overruns;

bool bench_serial_open(void) {
    return false;  /* pas de journal : le port série est le flux slcan */
}

bool bench_vcp_open(void) {
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
    s_uart.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;

    return HAL_UART_Init(&s_uart) == HAL_OK;
}

bool bench_vcp_read(uint8_t *byte) {
    USART_TypeDef *const usart = BENCH_UART_INSTANCE;
    const uint32_t isr = usart->ISR;

    if ((isr & USART_ISR_ORE) != 0u) {
        usart->ICR = USART_ICR_ORECF;  /* sans cela, la reception reste bloquee */
        s_overruns++;
    }
    if ((isr & USART_ISR_RXNE) == 0u) {
        return false;
    }
    *byte = (uint8_t)usart->RDR;
    return true;
}

bool bench_vcp_can_write(void) {
    return (BENCH_UART_INSTANCE->ISR & USART_ISR_TXE) != 0u;
}

void bench_vcp_write(uint8_t byte) {
    BENCH_UART_INSTANCE->TDR = byte;
}

uint32_t bench_vcp_overruns(void) {
    return s_overruns;
}
