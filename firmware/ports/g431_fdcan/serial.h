/**
 * @file serial.h
 * @brief Journal serie sur le port COM virtuel du ST-LINK (USART2, PA2/PA3).
 *
 * Optionnel : compile seulement si board.h definit BENCH_HAS_SERIAL_LOG. Une
 * fois ouvert, printf() est redirige vers le VCP par _write() de syscalls.c.
 *
 * Reglages cote PC : 115200 bauds, 8 bits, sans parite, 1 bit de stop.
 */

#ifndef BENCH_SERIAL_H
#define BENCH_SERIAL_H

#include <stdbool.h>

/**
 * @brief Ouvre USART2 et branche printf() dessus.
 * @return false si l'initialisation echoue.
 */
bool bench_serial_open(void);

#endif /* BENCH_SERIAL_H */
