/**
 * @file can_port.h
 * @brief Port bxCAN du STM32F103 pour l'interface CAN abstraite.
 *
 * Expose les memes noms que le port G431 (`bench_port_can_t`,
 * `bench_port_can_bind`, `bench_port_can_poll`) : le programme principal
 * d'entry/ compile a l'identique sur les deux cartes.
 */

#ifndef BENCH_F103_CAN_PORT_H
#define BENCH_F103_CAN_PORT_H

#include "stm32f1xx_hal.h"

#include "can_if.h"
#include "util/ring_buffer.h"

/** Nom du controleur, pour le journal. */
#define BENCH_CAN_PERIPH_NAME "bxCAN"

/** Contexte du port bxCAN. */
typedef struct {
    CAN_HandleTypeDef     hcan;
    bench_ring_t         *rx_ring;         /**< rempli par l'ISR, vide par la boucle */
    volatile uint16_t     rx_fifo_lost;    /**< debordements de la FIFO 0 materielle */
    /** Toujours nul : bxCAN ne sait pas recevoir de trame CAN FD, qui apparait
     *  comme une erreur de forme dans LEC. Garde pour la symetrie du heartbeat. */
    volatile uint8_t      non_classic_rx;
    volatile uint8_t      ext_id_rx;       /**< trames a identifiant 29 bits, saturant */
    bench_can_config_t    config;          /**< derniere configuration appliquee */
    bool                  started;
} bench_port_can_t;

/**
 * @brief Relie le port a un tampon de reception et remplit l'interface abstraite.
 *
 * A appeler avant @c open(). Le F103C8 n'a qu'un seul bxCAN.
 */
void bench_port_can_bind(bench_port_can_t *port, bench_ring_t *rx_ring, bench_can_t *out);

/**
 * @brief Entretien periodique, a appeler depuis la boucle principale.
 *
 * Rien a faire sur bxCAN : la reprise automatique apres bus-off est materielle
 * (bit ABOM). La fonction existe pour garder la meme boucle que sur le G431.
 */
void bench_port_can_poll(bench_port_can_t *port);

#endif /* BENCH_F103_CAN_PORT_H */
