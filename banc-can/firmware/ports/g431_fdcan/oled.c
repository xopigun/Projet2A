/**
 * @file oled.c
 * @brief Pilote SSD1306 sur I2C1, envoi de l'image sur interruption.
 */

#include "oled.h"

#include "board.h"

/**
 * Retournement de l'image : 1 pour un écran monté à l'envers (barrette coudée de
 * la carte porteuse, où l'écran tient debout tête en bas), 0 sur fils Dupont.
 */
#ifndef BENCH_OLED_FLIP
#define BENCH_OLED_FLIP 0
#endif

/**
 * I2C1 à 100 kHz depuis PCLK1 = 160 MHz (RM0440 §37.4.11) : PRESC = 15
 * (100 ns), SCLDEL = 12 (1,3 µs), SDADEL = 4 (0,4 µs), SCLH = 45 (4,6 µs),
 * SCLL = 49 (5,0 µs). Le mode standard tolère les fils Dupont et les tirages
 * de 10 kΩ des modules ; l'envoi étant asynchrone, la vitesse n'importe pas.
 */
#define OLED_I2C_TIMING 0xF0C42D31u

#define OLED_PAGES     8u
#define OLED_PAGE_SIZE 128u

static I2C_HandleTypeDef s_i2c;
static bool             s_present;
static const uint8_t   *s_fb;
static uint8_t          s_page;
static bool             s_data_phase;
static bool             s_busy;
static uint8_t          s_cmd[3];

static bool send_commands(const uint8_t *cmds, uint16_t n) {
    return HAL_I2C_Mem_Write(&s_i2c, BENCH_OLED_ADDR, 0x00u, I2C_MEMADD_SIZE_8BIT,
                             (uint8_t *)cmds, n, 50u) == HAL_OK;
}

bool bench_oled_init(void) {
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_I2C1_CLK_ENABLE();

    gpio.Mode = GPIO_MODE_AF_OD;
    gpio.Pull = GPIO_PULLUP;  /* en renfort des tirages du module */
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    gpio.Alternate = BENCH_I2C_AF;
    gpio.Pin = BENCH_I2C_SCL_PIN;
    HAL_GPIO_Init(BENCH_I2C_SCL_PORT, &gpio);
    gpio.Pin = BENCH_I2C_SDA_PIN;
    HAL_GPIO_Init(BENCH_I2C_SDA_PORT, &gpio);

    s_i2c.Instance = BENCH_I2C_INSTANCE;
    s_i2c.Init.Timing = OLED_I2C_TIMING;
    s_i2c.Init.OwnAddress1 = 0u;
    s_i2c.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
    s_i2c.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
    s_i2c.Init.OwnAddress2 = 0u;
    s_i2c.Init.OwnAddress2Masks = I2C_OA2_NOMASK;
    s_i2c.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
    s_i2c.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
    if (HAL_I2C_Init(&s_i2c) != HAL_OK) {
        return false;
    }
    (void)HAL_I2CEx_ConfigAnalogFilter(&s_i2c, I2C_ANALOGFILTER_ENABLE);

    if (HAL_I2C_IsDeviceReady(&s_i2c, BENCH_OLED_ADDR, 2u, 10u) != HAL_OK) {
        return false;  /* pas d'écran sur ce nœud */
    }

    /* Séquence d'initialisation du SSD1306 128 × 64 (datasheet SSD1306 §8.9),
     * adressage par page, pompe de charge interne. */
    static const uint8_t init[] = {
        0xAE,             /* écran éteint */
        0xD5, 0x80,       /* horloge */
        0xA8, 0x3F,       /* multiplexage 64 lignes */
        0xD3, 0x00,       /* décalage vertical */
        0x40,             /* ligne de départ 0 */
        0x8D, 0x14,       /* pompe de charge */
        0x20, 0x02,       /* adressage par page */
#if BENCH_OLED_FLIP
        0xA0, 0xC0,       /* colonnes et lignes dans l'ordre : image retournée */
#else
        0xA1, 0xC8,       /* colonnes et lignes inversées : image à l'endroit */
#endif
        0xDA, 0x12,       /* broches COM */
        0x81, 0xCF,       /* contraste */
        0xD9, 0xF1,       /* précharge */
        0xDB, 0x40,       /* VCOMH */
        0xA4,             /* affichage de la RAM */
        0xA6,             /* vidéo normale */
        0x2E,             /* pas de défilement */
        0xAF,             /* écran allumé */
    };
    if (!send_commands(init, (uint16_t)sizeof(init))) {
        return false;
    }

    HAL_NVIC_SetPriority(I2C1_EV_IRQn, 3u, 0u);
    HAL_NVIC_SetPriority(I2C1_ER_IRQn, 3u, 0u);
    HAL_NVIC_EnableIRQ(I2C1_EV_IRQn);
    HAL_NVIC_EnableIRQ(I2C1_ER_IRQn);

    s_present = true;
    return true;
}

bool bench_oled_present(void) {
    return s_present;
}

bool bench_oled_idle(void) {
    return !s_busy;
}

void bench_oled_show(const uint8_t *fb) {
    if (!s_present || s_busy) {
        return;
    }
    s_fb = fb;
    s_page = 0u;
    s_data_phase = false;
    s_busy = true;
}

void bench_oled_poll(void) {
    if (!s_busy || HAL_I2C_GetState(&s_i2c) != HAL_I2C_STATE_READY) {
        return;
    }
    if (s_i2c.ErrorCode != HAL_I2C_ERROR_NONE) {
        /* Écran débranché ou parasite : on abandonne l'image, la suivante repartira. */
        s_i2c.ErrorCode = HAL_I2C_ERROR_NONE;
        s_busy = false;
        return;
    }
    if (s_page >= OLED_PAGES) {
        s_busy = false;
        return;
    }
    HAL_StatusTypeDef st;
    if (!s_data_phase) {
        s_cmd[0] = (uint8_t)(0xB0u | s_page); /* page */
        s_cmd[1] = 0x00u;                      /* colonne, quartet bas */
        s_cmd[2] = 0x10u;                      /* colonne, quartet haut */
        st = HAL_I2C_Mem_Write_IT(&s_i2c, BENCH_OLED_ADDR, 0x00u, I2C_MEMADD_SIZE_8BIT, s_cmd, 3u);
        s_data_phase = true;
    } else {
        st = HAL_I2C_Mem_Write_IT(&s_i2c, BENCH_OLED_ADDR, 0x40u, I2C_MEMADD_SIZE_8BIT,
                                  (uint8_t *)&s_fb[(uint32_t)s_page * OLED_PAGE_SIZE],
                                  OLED_PAGE_SIZE);
        s_data_phase = false;
        s_page++;
    }
    if (st != HAL_OK) {
        s_busy = false;
    }
}

void I2C1_EV_IRQHandler(void) {
    HAL_I2C_EV_IRQHandler(&s_i2c);
}

void I2C1_ER_IRQHandler(void) {
    HAL_I2C_ER_IRQHandler(&s_i2c);
}
