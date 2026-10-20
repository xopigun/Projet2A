/**
 * @file faults.h
 * @brief Exécution des modes de faute commandés par BENCH_CFG.
 *
 * @ref bench_node_t enregistre le mode demandé et son échéance ; ce module le
 * **réalise** sur le contrôleur, à travers l'interface @ref bench_can_t
 * uniquement. Il reste donc testable nativement, et identique sur G431 et F103.
 *
 * Le comportement est calqué sur celui du simulateur (`pc/canbench/simulator.py`),
 * pour que `canbench faults --logical` donne le même verdict en simulation et
 * sur le banc :
 *
 * | Mode | Entrée | À chaque pas | Sortie |
 * |---|---|---|---|
 * | babbling idiot | — | remplit la file d'émission avec l'identifiant de faute | — |
 * | débit erroné | réouverture à 250 kbit/s | — | réouverture au débit nominal |
 * | DLC incohérent | — | émet l'identifiant de faute avec 4 octets au lieu de 8 | — |
 * | silencieux | mode moniteur | — | mode normal |
 * | bus-off maintenu | réouverture sans reprise automatique | — | réouverture nominale |
 *
 * L'identifiant de faute est le paramètre de BENCH_CFG s'il est non nul, sinon
 * la trame applicative du nœud. N4 n'en ayant pas, il n'émet rien sans ce
 * paramètre : c'est voulu, un mode de faute ne doit pas inventer d'identifiant.
 */

#ifndef BENCH_FAULTS_H
#define BENCH_FAULTS_H

#include <stdbool.h>
#include <stdint.h>

#include "app/node.h"
#include "can_if.h"

/** Longueur émise en mode « DLC incohérent » ; l'ICD impose 8 partout. */
#define BENCH_FAULT_BAD_DLC 4u

/** Nombre maximal de trames tentées par pas en mode « babbling idiot ». */
#define BENCH_FAULT_FLOOD_BURST 3u

/** Période d'émission en mode « DLC incohérent », celle du simulateur (app_period). */
#define BENCH_FAULT_BAD_DLC_PERIOD_MS 20u

/** État de l'exécuteur : le mode effectivement appliqué au contrôleur. */
typedef struct {
    bench_can_t        *can;
    bench_can_config_t  nominal;  /**< configuration à restaurer en sortie de faute */
    bench_mode_t        applied;
    uint32_t            next_bad_dlc_ms;
    /** Faux si la dernière reconfiguration du contrôleur a échoué. */
    bool                last_reconfig_ok;
} bench_faults_t;

/** @brief Initialise l'exécuteur avec la configuration nominale du contrôleur. */
void bench_faults_init(bench_faults_t *faults, bench_can_t *can,
                       const bench_can_config_t *nominal);

/**
 * @brief Aligne le contrôleur sur le mode demandé, puis exécute un pas de faute.
 *
 * À appeler à chaque tour de la boucle principale, avec le mode courant du nœud
 * (qui revient de lui-même à normal à l'échéance, voir bench_node_tick()).
 *
 * @param mode      mode demandé
 * @param fault_id  identifiant de faute ; 0 si aucun
 * @param now_ms    date courante, pour cadencer le mode « DLC incohérent »
 * @return nombre de trames acceptées par le contrôleur pendant ce pas
 */
uint32_t bench_faults_step(bench_faults_t *faults, bench_mode_t mode, uint16_t fault_id,
                           uint32_t now_ms);

/** @brief Identifiant de faute d'un nœud : paramètre BENCH_CFG, sinon sa trame. */
uint16_t bench_faults_id(const bench_node_t *node);

#endif /* BENCH_FAULTS_H */
