/**
 * @file serial.h
 * @brief Journal serie du noeud N4 sur USART1 (PA9/PA10).
 *
 * La Blue Pill n'a pas de port COM virtuel, et son USB ne peut pas servir en
 * meme temps que le CAN (voir board.h). Le journal sort donc sur USART1, a
 * relier a un adaptateur USB-serie 3,3 V : PA9 vers le RX de l'adaptateur,
 * GND commun, jamais la broche VCC de l'adaptateur.
 *
 * Reglages cote PC : 115200 bauds, 8 bits, sans parite, 1 bit de stop.
 */

#ifndef BENCH_SERIAL_H
#define BENCH_SERIAL_H

#include <stdbool.h>

/**
 * @brief Ouvre USART1 et branche printf() dessus.
 * @return false si l'initialisation echoue.
 */
bool bench_serial_open(void);

#endif /* BENCH_SERIAL_H */
