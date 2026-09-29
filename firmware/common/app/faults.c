/**
 * @file faults.c
 * @brief Réalisation des modes de faute sur le contrôleur, via l'interface CAN.
 */

#include "app/faults.h"

void bench_faults_init(bench_faults_t *faults, bench_can_t *can,
                       const bench_can_config_t *nominal) {
    faults->can = can;
    faults->nominal = *nominal;
    faults->applied = BENCH_MODE_NORMAL;
    faults->next_bad_dlc_ms = 0u;
    faults->last_reconfig_ok = true;
}

uint16_t bench_faults_id(const bench_node_t *node) {
    return (node->fault_param != 0u) ? node->fault_param : node->tx_id;
}

/** Rouvre le contrôleur avec une configuration dérivée de la nominale. */
static void reopen(bench_faults_t *faults, const bench_can_config_t *config) {
    faults->last_reconfig_ok = faults->can->ops->open(faults->can->ctx, config);
}

/** Défait ce que le mode appliqué avait changé dans le contrôleur. */
static void leave(bench_faults_t *faults, bench_mode_t mode) {
    switch (mode) {
        case BENCH_MODE_SILENT:
            faults->can->ops->set_silent(faults->can->ctx, false);
            break;
        case BENCH_MODE_WRONG_BITRATE:
            reopen(faults, &faults->nominal);
            break;
        case BENCH_MODE_HOLD_BUSOFF:
            /* La réouverture rétablit la reprise automatique ; recover() lance la
             * séquence de sortie si le nœud est encore en bus-off. */
            reopen(faults, &faults->nominal);
            (void)faults->can->ops->recover(faults->can->ctx);
            break;
        default:
            break;  /* babbling idiot et DLC incohérent ne touchent pas au contrôleur */
    }
}

/** Applique au contrôleur ce que le nouveau mode exige. */
static void enter(bench_faults_t *faults, bench_mode_t mode) {
    bench_can_config_t config = faults->nominal;

    switch (mode) {
        case BENCH_MODE_SILENT:
            faults->can->ops->set_silent(faults->can->ctx, true);
            break;
        case BENCH_MODE_WRONG_BITRATE:
            /* Prescaler doublé : 250 kbit/s, même point d'échantillonnage. Le nœud
             * devient illisible pour les autres, qui voient des erreurs de forme. */
            config.timing.prescaler = (uint16_t)(faults->nominal.timing.prescaler * 2u);
            reopen(faults, &config);
            break;
        case BENCH_MODE_HOLD_BUSOFF:
            /* Le passage en bus-off lui-même est provoqué de l'extérieur (SW2 ou
             * débit erroné d'un autre nœud). Ce mode garantit seulement qu'une fois
             * en bus-off, le nœud y reste jusqu'à la révocation. */
            config.busoff_policy = BENCH_BUSOFF_MANUAL;
            reopen(faults, &config);
            break;
        default:
            break;
    }
}

/** Émet une trame de faute ; renvoie 1 si le contrôleur l'a acceptée. */
static uint32_t emit(bench_faults_t *faults, uint16_t id, uint8_t dlc) {
    bench_can_frame_t frame = {0};
    frame.id = id;
    frame.dlc = dlc;
    return faults->can->ops->send(faults->can->ctx, &frame) ? 1u : 0u;
}

uint32_t bench_faults_step(bench_faults_t *faults, bench_mode_t mode, uint16_t fault_id,
                           uint32_t now_ms) {
    uint32_t sent = 0u;

    if (mode != faults->applied) {
        leave(faults, faults->applied);
        enter(faults, mode);
        faults->applied = mode;
        faults->next_bad_dlc_ms = now_ms;
    }

    if (fault_id == 0u) {
        return 0u;  /* aucun identifiant : rien à émettre, voir faults.h */
    }

    switch (mode) {
        case BENCH_MODE_BABBLING_IDIOT:
            /* La file d'émission se remplit à chaque tour : le bus est saturé à
             * la priorité de l'identifiant de faute, sans attente logicielle. */
            for (uint32_t i = 0u; i < BENCH_FAULT_FLOOD_BURST; i++) {
                sent += emit(faults, fault_id, 8u);
            }
            break;
        case BENCH_MODE_BAD_DLC:
            if ((int32_t)(now_ms - faults->next_bad_dlc_ms) >= 0) {
                sent += emit(faults, fault_id, BENCH_FAULT_BAD_DLC);
                faults->next_bad_dlc_ms = now_ms + BENCH_FAULT_BAD_DLC_PERIOD_MS;
            }
            break;
        default:
            break;
    }
    return sent;
}
