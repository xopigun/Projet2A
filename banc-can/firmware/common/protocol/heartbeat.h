/**
 * @file heartbeat.h
 * @brief Construction de la trame d'état périodique d'un nœud.
 *
 * Le heartbeat porte ce qui permet de juger la validité d'une mesure : l'état du
 * contrôleur et ses compteurs TEC/REC lus **dans le matériel**, les pertes FIFO
 * matérielles, les débordements du tampon logiciel, et le drapeau signalant que
 * le nœud tourne sur une référence d'horloge non conforme.
 *
 * Il est émis à période configurable (500 ms par défaut) et **suspendu pendant
 * un test d'arbitrage** : une trame de heartbeat qui s'intercalerait entre GO et
 * les trames contendantes fausserait le comptage du rang.
 */

#ifndef BENCH_HEARTBEAT_H
#define BENCH_HEARTBEAT_H

#include <stdbool.h>
#include <stdint.h>

#include "can_if.h"
#include "icd_gen.h"
#include "util/ring_buffer.h"

/** Entrées nécessaires à la construction d'un heartbeat. */
typedef struct {
    uint8_t  node_id;
    uint8_t  current_mode;       /**< mode de test courant (cf. BENCH_CFG.mode) */
    bool     fault_mode_active;
    bool     silent_mode;
    /**
     * Vrai si le nœud tourne sur HSI. La tolérance du HSI (±1 %) dépasse plus du
     * double la tolérance admissible à 500 kbit/s (0,485 %) : aucun verdict de
     * réussite ne doit être prononcé tant que ce drapeau est levé.
     */
    bool clock_not_qualified;
} bench_heartbeat_inputs_t;

/** État du cadenceur de heartbeat. */
typedef struct {
    uint16_t period_ms;
    uint32_t next_due_ms;
    bool     suspended;  /**< levé pendant un test d'arbitrage */
    /**
     * Faux tant qu'aucune échéance n'a été posée. Sans ce drapeau, un cadenceur
     * initialisé alors que le compteur de millisecondes est déjà élevé
     * comparerait sa première échéance à zéro et resterait muet.
     */
    bool started;
} bench_heartbeat_sched_t;

/** @brief Initialise le cadenceur avec une période en millisecondes. */
void bench_heartbeat_init(bench_heartbeat_sched_t *hb, uint16_t period_ms);

/** @brief Change la période ; 0 laisse la période courante inchangée. */
void bench_heartbeat_set_period(bench_heartbeat_sched_t *hb, uint16_t period_ms);

/** @brief Suspend ou reprend l'émission (suspendue pendant un test d'arbitrage). */
void bench_heartbeat_suspend(bench_heartbeat_sched_t *hb, bool suspended);

/**
 * @brief Indique si un heartbeat doit être émis à l'instant @p now_ms.
 *
 * Avance l'échéance lorsqu'elle est atteinte. Renvoie toujours false tant que
 * l'émission est suspendue, sans accumuler de retard à rattraper.
 */
bool bench_heartbeat_due(bench_heartbeat_sched_t *hb, uint32_t now_ms);

/** @brief Identifiant du heartbeat d'un nœud, dans le profil par défaut. */
uint16_t bench_heartbeat_id(uint8_t node_id);

/**
 * @brief Construit la charge utile du heartbeat.
 *
 * @param inputs état applicatif du nœud
 * @param status compteurs lus dans le contrôleur
 * @param ring   tampon circulaire de réception, pour ses débordements
 * @param data   tampon de 8 octets recevant la trame encodée
 */
void bench_heartbeat_pack_frame(const bench_heartbeat_inputs_t *inputs,
                                const bench_can_status_t *status, const bench_ring_t *ring,
                                uint8_t *data);

#endif /* BENCH_HEARTBEAT_H */
