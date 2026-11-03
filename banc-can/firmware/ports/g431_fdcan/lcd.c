/**
 * @file lcd.c
 * @brief Pilote HD44780 en mode 4 bits, sans lecture du drapeau « occupé ».
 *
 * Références : fiche Hitachi HD44780U (ADE-207-272), Table 6 (instructions et
 * temps d'exécution), Figure 24 (initialisation par instructions en 4 bits) et
 * « Bus Timing Characteristics ». Le TC1602A embarque un contrôleur compatible.
 */

#include "lcd.h"

#include "board.h"

#if BENCH_HAS_LCD

#include <string.h>

/* Instructions du contrôleur (HD44780U Table 6). */
#define LCD_CMD_CLEAR        0x01u
#define LCD_CMD_ENTRY_INC    0x06u /* I/D = 1 : le curseur avance, pas de décalage */
#define LCD_CMD_DISPLAY_OFF  0x08u
#define LCD_CMD_DISPLAY_ON   0x0Cu /* écran allumé, curseur et clignotement éteints */
#define LCD_CMD_FUNCTION_4B  0x28u /* DL = 0 (4 bits), N = 1 (2 lignes), F = 0 (5x8) */
#define LCD_CMD_SET_DDRAM    0x80u

/**
 * Délais d'exécution, en microsecondes. Le HD44780U annonce 37 µs, et 1,52 ms
 * pour l'effacement, avec un oscillateur à 270 kHz : la marge couvre les
 * contrôleurs compatibles dont l'oscillateur est plus lent.
 */
#define LCD_EXEC_US  50u
#define LCD_CLEAR_US 2000u

/**
 * Impulsion E d'au moins 450 ns, cycle d'au moins 1000 ns, données établies
 * 195 ns avant le front descendant : 1 µs pour chaque phase couvre tout.
 */
#define LCD_PULSE_US 1u

#define CYCLES_PER_US (BENCH_SYSCLK_HZ / 1000000u)

/** Valeur du compteur d'adresse quand on ne sait pas où il en est. */
#define ADDR_UNKNOWN 0xFFu

/** Adresse DDRAM du début de chaque ligne en mode 2 lignes. */
static const uint8_t k_row_addr[BENCH_LCD_ROWS] = {0x00u, 0x40u};

static char     s_wanted[BENCH_LCD_ROWS][BENCH_LCD_COLS];
static char     s_shown[BENCH_LCD_ROWS][BENCH_LCD_COLS];
static uint8_t  s_addr = ADDR_UNKNOWN;  /**< compteur d'adresse du contrôleur */
static uint32_t s_busy_since;           /**< CYCCNT à la fin du dernier envoi */
static uint32_t s_busy_cycles;          /**< temps d'exécution du dernier envoi */

/* ------------------------------------------------------------------ temps -- */

/**
 * Compteur de cycles DWT, relancé à chaque lecture.
 *
 * Un débogueur qui se connecte peut effacer TRCENA et figer le compteur :
 * STM32CubeProgrammer le fait en se déconnectant, juste après le reset qui suit
 * la programmation. Une attente active fondée sur le compteur ne se terminait
 * alors jamais. C'est arrivé sur carte : nœud figé dès le démarrage, DEMCR lu à
 * 0x00000001. Le compteur n'est jamais remis à zéro ici, car can_port.c en tire
 * ses horodatages.
 */
static uint32_t cycles_now(void) {
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    return DWT->CYCCNT;
}

static void delay_us(uint32_t us) {
    const uint32_t start = cycles_now();

    while ((cycles_now() - start) < us * CYCLES_PER_US) {
    }
}

static bool is_busy(void) {
    return (cycles_now() - s_busy_since) < s_busy_cycles;
}

static void wait_ready(void) {
    while (is_busy()) {
    }
}

/* ---------------------------------------------------------------- broches -- */

static GPIO_PinState level(uint32_t bit) {
    return (bit != 0u) ? GPIO_PIN_SET : GPIO_PIN_RESET;
}

/** Présente un quartet sur D4..D7 ; le contrôleur le lit au front descendant de E. */
static void write_nibble(uint8_t nibble) {
    HAL_GPIO_WritePin(BENCH_LCD_D4_PORT, BENCH_LCD_D4_PIN, level(nibble & 0x1u));
    HAL_GPIO_WritePin(BENCH_LCD_D5_PORT, BENCH_LCD_D5_PIN, level(nibble & 0x2u));
    HAL_GPIO_WritePin(BENCH_LCD_D6_PORT, BENCH_LCD_D6_PIN, level(nibble & 0x4u));
    HAL_GPIO_WritePin(BENCH_LCD_D7_PORT, BENCH_LCD_D7_PIN, level(nibble & 0x8u));
    delay_us(LCD_PULSE_US);
    HAL_GPIO_WritePin(BENCH_LCD_E_PORT, BENCH_LCD_E_PIN, GPIO_PIN_SET);
    delay_us(LCD_PULSE_US);
    HAL_GPIO_WritePin(BENCH_LCD_E_PORT, BENCH_LCD_E_PIN, GPIO_PIN_RESET);
    delay_us(LCD_PULSE_US);
}

/** Envoie un octet, poids fort d'abord, puis note son temps d'exécution. */
static void write_byte(bool is_data, uint8_t byte, uint32_t exec_us) {
    wait_ready();
    HAL_GPIO_WritePin(BENCH_LCD_RS_PORT, BENCH_LCD_RS_PIN, is_data ? GPIO_PIN_SET : GPIO_PIN_RESET);
    write_nibble((uint8_t)(byte >> 4));
    write_nibble((uint8_t)(byte & 0x0Fu));
    s_busy_since = cycles_now();
    s_busy_cycles = exec_us * CYCLES_PER_US;
}

static void gpio_init(void) {
    GPIO_InitTypeDef gpio = {0};

    BENCH_LCD_CLK_ENABLE();

    /* D7 = PA10 est aussi UCPD1_DBCC2 : à l'état haut, il active la résistance
     * de 5,1 kΩ vers la masse de la fonction « dead battery » sur PB4 = D5
     * (DS12589 Rev 6, Table 12, note 6). D5 doit rester une sortie franche. */
    HAL_PWREx_DisableUCPDDeadBattery();

    /* Toutes les lignes à 0 avant le passage en sortie : E ne doit produire
     * aucune impulsion parasite pendant la configuration. */
    HAL_GPIO_WritePin(BENCH_LCD_RS_PORT, BENCH_LCD_RS_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(BENCH_LCD_E_PORT, BENCH_LCD_E_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(BENCH_LCD_D4_PORT, BENCH_LCD_D4_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(BENCH_LCD_D5_PORT, BENCH_LCD_D5_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(BENCH_LCD_D6_PORT, BENCH_LCD_D6_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(BENCH_LCD_D7_PORT, BENCH_LCD_D7_PIN, GPIO_PIN_RESET);

    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;

    /* RS en premier : PB0 n'est tolérant qu'à 3,6 V, et l'entrée RS de bien des
     * contrôleurs compatibles a un tirage interne vers le 5 V du LCD. Pilotée
     * en sortie, la broche ne monte plus au-delà de 3,3 V. */
    gpio.Pin = BENCH_LCD_RS_PIN;
    HAL_GPIO_Init(BENCH_LCD_RS_PORT, &gpio);
    gpio.Pin = BENCH_LCD_E_PIN;
    HAL_GPIO_Init(BENCH_LCD_E_PORT, &gpio);
    gpio.Pin = BENCH_LCD_D4_PIN;
    HAL_GPIO_Init(BENCH_LCD_D4_PORT, &gpio);
    gpio.Pin = BENCH_LCD_D5_PIN;
    HAL_GPIO_Init(BENCH_LCD_D5_PORT, &gpio);
    gpio.Pin = BENCH_LCD_D6_PIN;
    HAL_GPIO_Init(BENCH_LCD_D6_PORT, &gpio);
    gpio.Pin = BENCH_LCD_D7_PIN;
    HAL_GPIO_Init(BENCH_LCD_D7_PORT, &gpio);
}

/* ------------------------------------------------------------------- écran -- */

void bench_lcd_init(void) {
    gpio_init();

    /* Initialisation par instructions (HD44780U Figure 24) : elle ramène le
     * contrôleur dans un état connu quel qu'il soit, y compris après un reset
     * du MCU survenu entre les deux quartets d'un octet, l'écran restant
     * alimenté. */
    HAL_Delay(50u);  /* plus de 40 ms après la montée de VDD */
    write_nibble(0x3u);
    delay_us(5000u);  /* plus de 4,1 ms */
    write_nibble(0x3u);
    delay_us(200u);  /* plus de 100 µs */
    write_nibble(0x3u);
    delay_us(200u);
    write_nibble(0x2u);  /* passage en 4 bits */
    delay_us(200u);

    s_busy_cycles = 0u;
    write_byte(false, LCD_CMD_FUNCTION_4B, LCD_EXEC_US);
    write_byte(false, LCD_CMD_DISPLAY_OFF, LCD_EXEC_US);
    write_byte(false, LCD_CMD_CLEAR, LCD_CLEAR_US);
    write_byte(false, LCD_CMD_ENTRY_INC, LCD_EXEC_US);
    write_byte(false, LCD_CMD_DISPLAY_ON, LCD_EXEC_US);

    /* Après l'effacement : DDRAM remplie d'espaces, compteur d'adresse à 0. */
    memset(s_shown, ' ', sizeof(s_shown));
    memset(s_wanted, ' ', sizeof(s_wanted));
    s_addr = 0u;
}

void bench_lcd_show(const bench_lcd_text_t *text) {
    for (uint32_t row = 0u; row < BENCH_LCD_ROWS; row++) {
        memcpy(s_wanted[row], text->row[row], BENCH_LCD_COLS);
    }
}

/** Première case où l'écran diffère du texte voulu ; faux s'il n'y en a aucune. */
static bool next_change(uint8_t *row, uint8_t *col) {
    for (uint8_t r = 0u; r < BENCH_LCD_ROWS; r++) {
        for (uint8_t c = 0u; c < BENCH_LCD_COLS; c++) {
            if (s_wanted[r][c] != s_shown[r][c]) {
                *row = r;
                *col = c;
                return true;
            }
        }
    }
    return false;
}

void bench_lcd_service(void) {
    uint8_t row;
    uint8_t col;

    if (is_busy() || !next_change(&row, &col)) {
        return;
    }

    const uint8_t addr = (uint8_t)(k_row_addr[row] + col);
    if (s_addr != addr) {
        /* Un octet par appel : le caractère partira au tour suivant. */
        write_byte(false, (uint8_t)(LCD_CMD_SET_DDRAM | addr), LCD_EXEC_US);
        s_addr = addr;
        return;
    }

    write_byte(true, (uint8_t)s_wanted[row][col], LCD_EXEC_US);
    s_shown[row][col] = s_wanted[row][col];
    s_addr++;  /* le contrôleur avance d'une case (LCD_CMD_ENTRY_INC) */
}

void bench_lcd_flush(void) {
    uint8_t row;
    uint8_t col;

    while (next_change(&row, &col)) {
        wait_ready();
        bench_lcd_service();
    }
    wait_ready();
}

#else /* pas d'afficheur sur cette carte */

void bench_lcd_init(void) {
}

void bench_lcd_show(const bench_lcd_text_t *text) {
    (void)text;
}

void bench_lcd_service(void) {
}

void bench_lcd_flush(void) {
}

#endif
