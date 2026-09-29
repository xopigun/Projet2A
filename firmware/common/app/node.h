/**
 * @file node.h
 * @brief Application d'un nœud du banc : un seul code, un rôle choisi à la compilation.
 *
 * Le rôle vient de `BENCH_NODE_ID` (1 à 4), fixé par le preset CMake. Aucun code
 * n'est spécifique à un groupe partenaire : les différences entre nœuds tiennent
 * à l'identifiant de leur trame contendante et à la source de leurs données.
 *
 * Cette couche ne connaît ni la HAL ni le brochage : elle ne parle qu'à
 * l'interface @ref bench_can_t. C'est ce qui la rend testable nativement.
 */

#ifndef BENCH_NODE_H
#define BENCH_NODE_H

#include <stdbool.h>
#include <stdint.h>

#include "can_if.h"
#include "protocol/arbitration.h"
#include "protocol/heartbeat.h"
#include "util/ring_buffer.h"

/** Modes de faute pilotés par BENCH_CFG (voir le signal `mode` de l'ICD). */
typedef enum {
    BENCH_MODE_NORMAL = 0,
    BENCH_MODE_BABBLING_IDIOT = 1, /**< inonde le bus d'un identifiant configurable */
    BENCH_MODE_WRONG_BITRATE = 2,  /**< se reconfigure à 250 kbit/s */
    BENCH_MODE_BAD_DLC = 3,        /**< émet un DLC incohérent avec l'ICD */
    BENCH_MODE_SILENT = 4,         /**< mode moniteur ; couvre l'arrêt d'acquittement */
    BENCH_MODE_HOLD_BUSOFF = 5,    /**< reste en bus-off jusqu'à révocation */
} bench_mode_t;

/** État complet d'un nœud. */
typedef struct {
    uint8_t     node_id;
    uint16_t    tx_id;        /**< identifiant de sa trame applicative */
    bool        is_contender;

    bench_can_t             *can;
    bench_ring_t            *rx_ring;
    bench_arb_t              arb;
    bench_heartbeat_sched_t  heartbeat;

    bench_mode_t mode;
    uint32_t     mode_deadline_ms;  /**< toute faute est bornée dans le temps */
    /** Paramètre du mode (BENCH_CFG.param_u16) : identifiant de faute, 0 si aucun. */
    uint16_t     fault_param;
    bool         clock_qualified;

    uint32_t frames_sent;
    uint32_t frames_received;
} bench_node_t;

/** @brief Initialise l'état applicatif du nœud. */
void bench_node_init(bench_node_t *node, uint8_t node_id, bench_can_t *can,
                     bench_ring_t *rx_ring, bool clock_qualified);

/**
 * @brief Traite une trame reçue : protocole ARM/GO, commandes, comptage.
 * @return true si le nœud doit armer sa trame contendante.
 */
bool bench_node_on_frame(bench_node_t *node, const bench_can_frame_t *frame, uint32_t now_ms);

/** @brief Applique une commande BENCH_CFG reçue. */
void bench_node_apply_cfg(bench_node_t *node, const uint8_t *data, uint32_t now_ms);

/**
 * @brief Échéances périodiques : fin d'un mode de faute, heartbeat.
 *
 * Renvoie true si un heartbeat doit être émis ; @p data reçoit alors sa charge
 * utile de 8 octets.
 */
bool bench_node_tick(bench_node_t *node, uint32_t now_ms, const bench_can_status_t *status,
                     uint8_t *data);

/** @brief Identifiant de la trame contendante associée à un rôle. */
uint16_t bench_node_tx_id(uint8_t node_id);

/** @brief Rang attendu du nœud dans un cycle d'arbitrage ; 0 s'il ne concourt pas. */
uint8_t bench_node_expected_rank(uint8_t node_id);

#endif /* BENCH_NODE_H */
