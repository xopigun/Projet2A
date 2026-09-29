/**
 * @file node.c
 * @brief Application commune aux quatre nœuds.
 */

#include "app/node.h"

#include <string.h>

#include "icd_gen.h"

uint16_t bench_node_tx_id(uint8_t node_id) {
    switch (node_id) {
        case 1u:
            return BENCH_ID_ENERGY_COMMAND;
        case 2u:
            return BENCH_ID_IMU_SPEED;
        case 3u:
            return BENCH_ID_TEMP_BATTERY;
        default:
            return 0u;  /* N4 n'est pas contendant */
    }
}

uint8_t bench_node_expected_rank(uint8_t node_id) {
    return (node_id >= 1u && node_id <= 3u) ? node_id : 0u;
}

void bench_node_init(bench_node_t *node, uint8_t node_id, bench_can_t *can,
                     bench_ring_t *rx_ring, bool clock_qualified) {
    memset(node, 0, sizeof(*node));

    node->node_id = node_id;
    node->tx_id = bench_node_tx_id(node_id);
    node->is_contender = (node->tx_id != 0u);
    node->can = can;
    node->rx_ring = rx_ring;
    node->mode = BENCH_MODE_NORMAL;
    node->clock_qualified = clock_qualified;

    bench_arb_init(&node->arb, BENCH_ID_ARM, BENCH_ID_GO, node->tx_id, node->is_contender);
    bench_heartbeat_init(&node->heartbeat, 500u);
}

void bench_node_apply_cfg(bench_node_t *node, const uint8_t *data, uint32_t now_ms) {
    bench_bench_cfg_t cfg;
    bench_bench_cfg_unpack(&cfg, data);

    /* 0 = diffusion à tous les nœuds. */
    if (cfg.target_node != 0u && cfg.target_node != node->node_id) {
        return;
    }

    bench_heartbeat_set_period(&node->heartbeat, cfg.heartbeat_period_ms);

    /* Une durée nulle révoque immédiatement le mode courant : toute faute doit
     * rester révocable, y compris si le nœud ne répond plus normalement. */
    if (cfg.duration_ms == 0u) {
        node->mode = BENCH_MODE_NORMAL;
        node->mode_deadline_ms = 0u;
        node->fault_param = 0u;
        return;
    }

    /* Un mode inconnu est ignoré plutôt que stocké : le transtypage en
     * bench_mode_t d'une valeur hors énumération laisserait le nœud dans un état
     * que ni l'exécuteur de fautes ni le heartbeat ne savent décrire. */
    if (cfg.mode > (uint8_t)BENCH_MODE_HOLD_BUSOFF) {
        return;
    }

    node->mode = (bench_mode_t)cfg.mode;
    node->fault_param = cfg.param_u16;
    node->mode_deadline_ms = now_ms + cfg.duration_ms;
}

bool bench_node_on_frame(bench_node_t *node, const bench_can_frame_t *frame, uint32_t now_ms) {
    /* Confirmation d'émission de notre trame contendante, déposée par le port
     * dans l'ordre du bus : c'est elle, et non l'armement, qui fige le rang. */
    if ((frame->flags & BENCH_FRAME_OWN_TX) != 0u) {
        bench_arb_on_own_tx(&node->arb);
        return false;
    }

    node->frames_received++;

    if (frame->id == BENCH_ID_BENCH_CFG) {
        bench_node_apply_cfg(node, frame->data, now_ms);
        return false;
    }

    const bench_frame_info_t *info = bench_frame_by_id(frame->id);
    const bool is_contender_frame = (info != NULL) && info->is_contender;

    /* Le heartbeat est suspendu dès qu'un cycle d'arbitrage commence : une
     * trame de heartbeat glissée entre GO et les contendants fausserait le rang.
     *
     * La même règle vaudra pour l'émission périodique des trames applicatives
     * quand le lot 6 l'ajoutera : entre ARM et la fin de sa propre émission, un
     * nœud ne doit rien émettre d'autre que sa trame contendante. Une trame
     * périodique arrivant juste après GO serait comptée comme contendante. */
    if (frame->id == BENCH_ID_ARM) {
        bench_heartbeat_suspend(&node->heartbeat, true);
        node->arb_started_ms = now_ms;
    }

    return bench_arb_on_frame(&node->arb, frame, is_contender_frame);
}

bool bench_node_tick(bench_node_t *node, uint32_t now_ms, const bench_can_status_t *status,
                     uint8_t *data) {
    /* Toute faute est bornée dans le temps : si l'échéance est passée, le nœud
     * revient de lui-même en fonctionnement normal, même sans commande. */
    if (node->mode != BENCH_MODE_NORMAL &&
        (int32_t)(now_ms - node->mode_deadline_ms) >= 0) {
        node->mode = BENCH_MODE_NORMAL;
        node->mode_deadline_ms = 0u;
        node->fault_param = 0u;
    }

    /* Un cycle qui n'aboutit pas est abandonné : sans ce délai de garde, un
     * nœud parti avant GO resterait en comptage, heartbeat suspendu. */
    if ((node->arb.phase == BENCH_ARB_ARMED || node->arb.phase == BENCH_ARB_COUNTING) &&
        (now_ms - node->arb_started_ms) >= BENCH_ARB_TIMEOUT_MS) {
        bench_arb_abandon(&node->arb);
    }

    /* Hors cycle d'arbitrage, le heartbeat reprend. */
    if (node->arb.phase == BENCH_ARB_IDLE || node->arb.phase == BENCH_ARB_DONE) {
        bench_heartbeat_suspend(&node->heartbeat, false);
    }

    if (!bench_heartbeat_due(&node->heartbeat, now_ms)) {
        return false;
    }

    bench_heartbeat_inputs_t inputs = {0};
    inputs.node_id = node->node_id;
    inputs.current_mode = (uint8_t)node->mode;
    inputs.fault_mode_active = (node->mode != BENCH_MODE_NORMAL);
    inputs.silent_mode = (node->mode == BENCH_MODE_SILENT);
    inputs.clock_not_qualified = !node->clock_qualified;

    bench_heartbeat_pack_frame(&inputs, status, node->rx_ring, data);
    return true;
}
