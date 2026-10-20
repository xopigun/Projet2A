/**
 * @file can_port.h
 * @brief Port FDCAN du STM32G431 pour l'interface CAN abstraite.
 */

#ifndef BENCH_G431_CAN_PORT_H
#define BENCH_G431_CAN_PORT_H

#include "stm32g4xx_hal.h"

#include "can_if.h"
#include "util/ring_buffer.h"

/** Nom du controleur, pour le journal : chaque port expose les memes noms. */
#define BENCH_CAN_PERIPH_NAME "FDCAN"

/** Contexte du port FDCAN. */
typedef struct {
    FDCAN_HandleTypeDef   hfdcan;
    bench_ring_t         *rx_ring;      /**< rempli par l'ISR, vide par la boucle */
    volatile uint16_t     rx_fifo_lost;    /**< pertes FIFO materielles */
    volatile uint8_t      non_classic_rx;  /**< trames CAN FD, saturant */
    volatile uint8_t      ext_id_rx;       /**< trames a identifiant 29 bits, saturant */
    bench_busoff_policy_t busoff_policy;
    bool                  silent;
    /** Tampon(s) d'émission portant la trame contendante armée ; 0 si aucune.
     *  Écrit par arm(), lu et remis à zéro par l'ISR de fin d'émission. */
    volatile uint32_t     armed_buffers;
    uint16_t              armed_id;
} bench_port_can_t;

/**
 * @brief Relie le port a un tampon de reception et remplit l'interface abstraite.
 *
 * A appeler avant @c open(). Le G431KB n'ayant qu'un seul FDCAN, un seul port
 * peut etre lie a la fois.
 */
void bench_port_can_bind(bench_port_can_t *port, bench_ring_t *rx_ring, bench_can_t *out);

/**
 * @brief Entretien periodique, a appeler depuis la boucle principale.
 *
 * Applique la politique de reprise apres bus-off : FDCAN n'a pas d'equivalent
 * materiel du bit ABOM de bxCAN, la reprise automatique est donc logicielle.
 */
void bench_port_can_poll(bench_port_can_t *port);

#endif /* BENCH_G431_CAN_PORT_H */
