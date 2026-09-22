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
        return;
    }

    node->mode = (bench_mode_t)cfg.mode;
    node->mode_deadline_ms = now_ms + cfg.duration_ms;
}

bool bench_node_on_frame(bench_node_t *node, const bench_can_frame_t *frame, uint32_t now_ms) {
    node->frames_received++;

    if (frame->id == BENCH_ID_BENCH_CFG) {
        bench_node_apply_cfg(node, frame->data, now_ms);
        return false;
    }

    const bench_frame_info_t *info = bench_frame_by_id(frame->id);
    const bool is_contender_frame = (info != NULL) && info->is_contender;

    /* Le heartbeat est suspendu dès qu'un cycle d'arbitrage commence : une
     * trame de heartbeat glissée entre GO et les contendants fausserait le rang. */
    if (frame->id == BENCH_ID_ARM) {
        bench_heartbeat_suspend(&node->heartbeat, true);
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
