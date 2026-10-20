/**
 * @file stm32g4xx_hal_conf.h
 * @brief Sélection des modules HAL utilisés par le firmware du banc.
 *
 * Seuls les modules réellement nécessaires sont activés : chaque module activé
 * est compilé et occupe de la flash, or le STM32G431KB n'en offre que 128 Ko.
 *
 * Dérivé de `stm32g4xx_hal_conf_template.h` du sous-module
 * `firmware/vendor/stm32g4xx_hal_driver`, réduit au strict nécessaire.
 */

#ifndef STM32G4xx_HAL_CONF_H
#define STM32G4xx_HAL_CONF_H

#ifdef __cplusplus
extern "C" {
#endif

/* ----- Modules utilisés ------------------------------------------------- */
#define HAL_MODULE_ENABLED
#define HAL_CORTEX_MODULE_ENABLED
#define HAL_DMA_MODULE_ENABLED
#define HAL_EXTI_MODULE_ENABLED
#define HAL_FDCAN_MODULE_ENABLED
#define HAL_FLASH_MODULE_ENABLED
#define HAL_GPIO_MODULE_ENABLED
#define HAL_I2C_MODULE_ENABLED
#define HAL_PWR_MODULE_ENABLED
#define HAL_RCC_MODULE_ENABLED
#define HAL_UART_MODULE_ENABLED

/* ----- Horloges --------------------------------------------------------- */
/**
 * Quartz X2 de la carte (UM2397 §6.5). Disponible seulement si SB9 et SB10 sont
 * soudés ; voir firmware/boards/nucleo_g431kb/board.h.
 */
#if !defined(HSE_VALUE)
#define HSE_VALUE 24000000UL
#endif

#if !defined(HSE_STARTUP_TIMEOUT)
#define HSE_STARTUP_TIMEOUT 100UL
#endif

#if !defined(HSI_VALUE)
#define HSI_VALUE 16000000UL
#endif

/** Oscillateur interne 48 MHz, utilise par HAL_RCCEx_GetPeriphCLKFreq(). */
#if !defined(HSI48_VALUE)
#define HSI48_VALUE 48000000UL
#endif

#if !defined(LSI_VALUE)
#define LSI_VALUE 32000UL
#endif

#if !defined(LSE_VALUE)
#define LSE_VALUE 32768UL
#endif

#if !defined(LSE_STARTUP_TIMEOUT)
#define LSE_STARTUP_TIMEOUT 5000UL
#endif

#if !defined(EXTERNAL_CLOCK_VALUE)
#define EXTERNAL_CLOCK_VALUE 12288000UL
#endif

/* ----- Réglages généraux ------------------------------------------------ */
#define VDD_VALUE                 3300UL
#define TICK_INT_PRIORITY         15UL
#define USE_RTOS                  0U
#define PREFETCH_ENABLE           0U
#define INSTRUCTION_CACHE_ENABLE  1U
#define DATA_CACHE_ENABLE         1U

#define USE_HAL_FDCAN_REGISTER_CALLBACKS 0U
#define USE_HAL_I2C_REGISTER_CALLBACKS   0U
#define USE_HAL_UART_REGISTER_CALLBACKS  0U

/**
 * Vérification des paramètres de la HAL. Laissée active en Debug : le coût en
 * flash est acceptable et une erreur de configuration est détectée tout de
 * suite au lieu de se manifester par un comportement aberrant du bus.
 */
#ifndef NDEBUG
#define USE_FULL_ASSERT 1U
#endif

/* ----- En-têtes des modules --------------------------------------------- */
#ifdef HAL_RCC_MODULE_ENABLED
#include "stm32g4xx_hal_rcc.h"
#endif
#ifdef HAL_GPIO_MODULE_ENABLED
#include "stm32g4xx_hal_gpio.h"
#endif
#ifdef HAL_DMA_MODULE_ENABLED
#include "stm32g4xx_hal_dma.h"
#endif
#ifdef HAL_CORTEX_MODULE_ENABLED
#include "stm32g4xx_hal_cortex.h"
#endif
#ifdef HAL_EXTI_MODULE_ENABLED
#include "stm32g4xx_hal_exti.h"
#endif
#ifdef HAL_FDCAN_MODULE_ENABLED
#include "stm32g4xx_hal_fdcan.h"
#endif
#ifdef HAL_FLASH_MODULE_ENABLED
#include "stm32g4xx_hal_flash.h"
#endif
#ifdef HAL_I2C_MODULE_ENABLED
#include "stm32g4xx_hal_i2c.h"
#endif
#ifdef HAL_PWR_MODULE_ENABLED
#include "stm32g4xx_hal_pwr.h"
#endif
#ifdef HAL_UART_MODULE_ENABLED
#include "stm32g4xx_hal_uart.h"
#endif

#ifdef USE_FULL_ASSERT
#define assert_param(expr) ((expr) ? (void)0U : assert_failed((uint8_t *)__FILE__, __LINE__))
void assert_failed(uint8_t *file, uint32_t line);
#else
#define assert_param(expr) ((void)0U)
#endif

#ifdef __cplusplus
}
#endif

#endif /* STM32G4xx_HAL_CONF_H */
