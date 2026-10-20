/**
 * @file can_port.h
 * @brief Port bxCAN du STM32L476 pour l'interface CAN abstraite (pont CAN-USB).
 *
 * Copie du port F103, dont il garde les noms (`bench_port_can_t`,
 * `bench_port_can_bind`, `bench_port_can_poll`) : le L476 embarque le meme
 * bxCAN. Y sont ajoutes bench_port_can_close() et le mode « bus direct ».
 */

#ifndef BENCH_L476_CAN_PORT_H
#define BENCH_L476_CAN_PORT_H

#include "stm32l4xx_hal.h"

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
    /** Boîte(s) d'émission portant la trame contendante armée ; 0 si aucune.
     *  Écrit par arm(), lu et remis à zéro par l'ISR de fin d'émission. */
    volatile uint32_t     armed_mailboxes;
    uint16_t              armed_id;
} bench_port_can_t;

/**
 * @brief Relie le port a un tampon de reception et remplit l'interface abstraite.
 *
 * A appeler avant @c open(). Le L476 n'a qu'un seul bxCAN.
 */
void bench_port_can_bind(bench_port_can_t *port, bench_ring_t *rx_ring, bench_can_t *out);

/**
 * @brief Arrete le controleur et rend les broches au repos (commande slcan `C`).
 *
 * Idempotent. Les trames deja dans le tampon de reception restent lisibles.
 */
void bench_port_can_close(bench_port_can_t *port);

/**
 * @brief Entretien periodique, a appeler depuis la boucle principale.
 *
 * Rien a faire sur bxCAN : la reprise automatique apres bus-off est materielle
 * (bit ABOM). La fonction existe pour garder la meme boucle que sur le G431.
 */
void bench_port_can_poll(bench_port_can_t *port);

#endif /* BENCH_L476_CAN_PORT_H */
