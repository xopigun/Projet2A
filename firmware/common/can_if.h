/**
 * @file can_if.h
 * @brief Interface CAN abstraite, indépendante du microcontrôleur.
 *
 * Tout le code de @c firmware/common/ passe par cette interface. Les deux ports
 * — @c ports/g431_fdcan et @c ports/f103_bxcan — en fournissent une réalisation.
 * Aucun en-tête HAL ne doit apparaître ici : un test natif le vérifie
 * (@c firmware/tests_host/check_no_hal.cmake).
 *
 * Les compteurs d'erreur ne sont jamais recalculés en logiciel : ils sont lus
 * dans les registres du contrôleur (FDCAN @c PSR et @c ECR, bxCAN @c ESR). Le
 * banc doit mesurer le comportement du bus, pas celui de son propre logiciel.
 */

#ifndef BENCH_CAN_IF_H
#define BENCH_CAN_IF_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/** Une trame CAN 2.0A horodatée. */
typedef struct {
    uint32_t timestamp_us;  /**< date de fin de réception ou d'émission */
    uint16_t id;            /**< identifiant 11 bits */
    uint8_t  dlc;           /**< 0 à 8 */
    uint8_t  data[8];
} bench_can_frame_t;

/** État du contrôleur, tel que rapporté par le matériel. */
typedef enum {
    BENCH_CAN_ERROR_ACTIVE = 0,
    BENCH_CAN_ERROR_WARNING = 1,
    BENCH_CAN_ERROR_PASSIVE = 2,
    BENCH_CAN_BUS_OFF = 3,
} bench_can_state_t;

/**
 * @brief Instantané des compteurs du contrôleur.
 *
 * @c rx_fifo_lost compte les trames perdues par le matériel faute de place dans
 * la FIFO (FDCAN @c RF0L). Il est remonté dans le heartbeat pour distinguer une
 * perte due au bus d'une perte due à notre propre logiciel.
 */
typedef struct {
    bench_can_state_t state;
    uint8_t           tec;             /**< Transmit Error Counter */
    uint8_t           rec;             /**< Receive Error Counter */
    uint8_t           last_error_code; /**< LEC du contrôleur */
    uint16_t          rx_fifo_lost;
    /**
     * Trames signalées par le contrôleur comme étant au format CAN FD. Le bus
     * est en CAN 2.0A classic : toute valeur non nulle est une anomalie.
     */
    uint8_t non_classic_rx;
    /** Trames reçues avec un identifiant 29 bits ; l'ICD n'utilise que 11 bits. */
    uint8_t ext_id_rx;
} bench_can_status_t;

/** Politique de reprise après passage en bus-off. */
typedef enum {
    /** Reprise automatique dès les 128 × 11 bits récessifs écoulés. */
    BENCH_BUSOFF_AUTO = 0,
    /** Maintien en bus-off jusqu'à une commande BENCH_CFG explicite. */
    BENCH_BUSOFF_MANUAL = 1,
} bench_busoff_policy_t;

/** Paramètres de temps de bit, calculés par scripts/bit_timing.py. */
typedef struct {
    uint16_t prescaler;
    uint8_t  tseg1;  /**< hors bit de synchronisation */
    uint8_t  tseg2;
    uint8_t  sjw;
} bench_can_timing_t;

/** Configuration d'ouverture du contrôleur. */
typedef struct {
    bench_can_timing_t   timing;
    bench_busoff_policy_t busoff_policy;
    bool                 silent;  /**< mode moniteur : écoute sans acquitter */
    /**
     * Bouclage interne : le contrôleur se reçoit lui-même sans rien émettre sur
     * les broches. Permet de valider l'encodage et la chaîne ISR -> tampon
     * **sans transceiver ni bus câblé** (voir docs/bringup.md).
     *
     * @warning Ne valide **ni l'horloge ni le débit** : émetteur et récepteur
     * partagent la même horloge noyau, donc une PLL fausse se boucle sur
     * elle-même sans erreur. Seule une référence indépendante le prouve.
     */
    bool loopback;
    /**
     * Retransmission automatique. Toujours vraie en fonctionnement normal :
     * sans elle, un nœud qui perd l'arbitrage abandonne sa trame et le test
     * d'arbitrage n'a plus de sens.
     */
    bool auto_retransmit;
} bench_can_config_t;

/** Opérations fournies par un port matériel. */
typedef struct {
    bool (*open)(void *ctx, const bench_can_config_t *config);
    bool (*send)(void *ctx, const bench_can_frame_t *frame);
    /** Place une trame en attente d'émission sans déclencher l'envoi immédiat. */
    bool (*arm)(void *ctx, const bench_can_frame_t *frame);
    void (*status)(void *ctx, bench_can_status_t *status);
    /** Force la sortie du bus-off lorsque la politique est BENCH_BUSOFF_MANUAL. */
    bool (*recover)(void *ctx);
    void (*set_silent)(void *ctx, bool silent);
    uint32_t (*now_us)(void *ctx);
} bench_can_ops_t;

/** Un contrôleur CAN : ses opérations et le contexte du port. */
typedef struct {
    const bench_can_ops_t *ops;
    void                  *ctx;
} bench_can_t;

#endif /* BENCH_CAN_IF_H */
