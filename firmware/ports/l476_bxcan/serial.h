/**
 * @file serial.h
 * @brief Liaison avec le PC par le port COM virtuel du ST-LINK (USART2, PA2/PA3).
 *
 * Contrairement aux autres cartes, ce port n'est **pas** un journal : c'est le
 * canal slcan du pont. printf() n'y est donc jamais branche (BENCH_HAS_SERIAL_LOG
 * vaut 0), et l'USART est lu et ecrit octet par octet par la boucle principale,
 * sans interruption.
 */

#ifndef BENCH_SERIAL_H
#define BENCH_SERIAL_H

#include <stdbool.h>
#include <stdint.h>

/** @brief Journal : inexistant sur cette carte, retourne toujours false. */
bool bench_serial_open(void);

/** @brief Ouvre USART2 a BENCH_UART_BAUD, 8N1. @return false si la HAL echoue. */
bool bench_vcp_open(void);

/** @brief Lit un octet recu s'il y en a un. Efface un debordement eventuel. */
bool bench_vcp_read(uint8_t *byte);

/** @brief Vrai si l'USART peut accepter un octet a emettre. */
bool bench_vcp_can_write(void);

/** @brief Emet un octet ; a n'appeler que si bench_vcp_can_write() est vrai. */
void bench_vcp_write(uint8_t byte);

/** @brief Nombre de debordements de l'USART en reception depuis l'ouverture. */
uint32_t bench_vcp_overruns(void);

#endif /* BENCH_SERIAL_H */
