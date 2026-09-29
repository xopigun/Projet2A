/**
 * @file arbitration.h
 * @brief Protocole ARM/GO et mesure du rang d'arbitrage (dossier §4.6).
 *
 * Pourquoi ce protocole
 * ---------------------
 * Trois programmes qui émettent « à peu près en même temps » ne démontrent rien.
 * La synchronisation est obtenue par le bus lui-même, sans signal externe, et
 * elle repose sur **deux** arguments complémentaires :
 *
 * 1. *Armement pendant GO* (argument du dossier). La trame GO occupe le bus
 *    environ 250 µs, soit deux ordres de grandeur de plus que la latence
 *    d'interruption. Tous les contendants ont donc armé leur émission avant que
 *    le bus ne se libère, et le matériel les fait démarrer au même bit.
 *
 * 2. *Armement trop précoce*. Un nœud qui aurait armé avant même le début de GO
 *    ne fausse pas le test : GO porte un identifiant inférieur à celui de tous
 *    les contendants, donc ce nœud perd l'arbitrage contre GO et attend sa fin.
 *
 * Le premier argument couvre l'armement tardif, le second l'armement précoce.
 * Ensemble ils ferment la démonstration. La contrainte
 * @c ID(GO) < min(ID des contendants) dont dépend le point 2 est vérifiée à la
 * génération de l'ICD, pas seulement documentée.
 *
 * Métrique retenue
 * ----------------
 * Le tableau 7 du dossier est ambigu : il annonce « Perdus 1000 » pour N3 alors
 * que N3 perd **deux** arbitrages par cycle (contre N1, puis contre N2). La
 * colonne compte donc des cycles, pas des arbitrages.
 *
 * On conserve ces colonnes pour rester compatible avec le dossier, mais le
 * critère de réussite porte sur une grandeur sans ambiguïté :
 *
 *     rang = 1 + nombre de trames contendantes reçues entre la fin de GO
 *                et la fin de sa propre émission
 *
 * Attendu : N1 → 1, N2 → 2, N3 → 3, à chaque cycle.
 *
 * Validité
 * --------
 * Si un nœud rate la fenêtre d'armement, il émet seul juste après et
 * apparaîtrait comme vainqueur sans avoir affronté personne. La parade est le
 * compteur @c arm_rx : avant de lire un classement, on vérifie que tous les
 * contendants affichent la même valeur.
 */

#ifndef BENCH_ARBITRATION_H
#define BENCH_ARBITRATION_H

#include <stdbool.h>
#include <stdint.h>

#include "can_if.h"

/** Rang maximal suivi ; au-delà, le cycle est comptabilisé comme aberrant. */
#define BENCH_MAX_RANK 8u

/** Phase de la machine d'états d'un nœud contendant. */
typedef enum {
    /** Au repos : aucun ARM reçu depuis le dernier cycle. */
    BENCH_ARB_IDLE = 0,
    /** ARM reçu, trame de test placée dans la boîte d'émission. */
    BENCH_ARB_ARMED,
    /** GO observé sur le bus : le décompte des contendants est ouvert. */
    BENCH_ARB_COUNTING,
    /** Notre trame est partie : le rang du cycle est figé. */
    BENCH_ARB_DONE,
} bench_arb_phase_t;

/** Compteurs cumulés d'un nœud contendant. */
typedef struct {
    uint32_t arm_rx;          /**< ARM reçus ; doit être identique sur tous les nœuds */
    uint32_t cycles;          /**< cycles achevés */
    uint32_t won;             /**< cycles gagnés (rang 1) */
    uint32_t lost;            /**< cycles où le nœud a perdu au moins un arbitrage */
    uint32_t invalid;         /**< cycles abandonnés (GO sans ARM, rang aberrant) */
    /** Histogramme des rangs ; l'indice 0 regroupe les rangs hors plage. */
    uint32_t rank_histogram[BENCH_MAX_RANK + 1u];
} bench_arb_counters_t;

/** État du protocole pour un nœud. */
typedef struct {
    uint16_t self_id;      /**< identifiant de notre trame contendante */
    uint16_t arm_id;
    uint16_t go_id;
    bool     is_contender;

    bench_arb_phase_t    phase;
    uint8_t              seen_contenders;  /**< contendants observés depuis la fin de GO */
    uint8_t              last_rank;
    bench_arb_counters_t counters;
} bench_arb_t;

/**
 * @brief Initialise l'état du protocole.
 *
 * @param self_id identifiant de la trame contendante du nœud ; ignoré si
 *                @p is_contender est faux.
 */
void bench_arb_init(bench_arb_t *arb, uint16_t arm_id, uint16_t go_id, uint16_t self_id,
                    bool is_contender);

/**
 * @brief Traite une trame reçue.
 *
 * À appeler depuis la boucle principale, pour chaque trame sortie du tampon
 * circulaire, dans l'ordre de réception.
 *
 * @param is_contender_frame vrai si la trame appartient à un contendant du test
 *                           (renseigné depuis la table de l'ICD).
 * @return true si la réception de cet ARM impose d'armer notre émission.
 */
bool bench_arb_on_frame(bench_arb_t *arb, const bench_can_frame_t *frame,
                        bool is_contender_frame);

/**
 * @brief Signale que notre propre trame contendante vient d'être émise.
 *
 * À appeler à la **confirmation d'émission** (élément BENCH_FRAME_OWN_TX du
 * tampon), jamais à l'armement : à l'armement, GO n'est pas encore passé et
 * l'appel serait ignoré. Fige le rang du cycle courant.
 *
 * Une confirmation reçue avant GO signifie que la trame est partie seule, sans
 * affronter personne : elle est ignorée, et le cycle finira invalide.
 */
void bench_arb_on_own_tx(bench_arb_t *arb);

/**
 * @brief Abandonne le cycle en cours, compté comme invalide.
 *
 * Appelée quand un cycle n'aboutit pas dans le délai de garde : sans elle, un
 * nœud dont la trame est partie **avant** GO resterait bloqué en phase de
 * comptage — et son heartbeat suspendu — jusqu'au prochain ARM.
 */
void bench_arb_abandon(bench_arb_t *arb);

/** @brief Rang obtenu au dernier cycle achevé ; 0 si aucun cycle n'est terminé. */
uint8_t bench_arb_last_rank(const bench_arb_t *arb);

/** @brief Vrai si tous les cycles achevés ont donné le rang attendu. */
bool bench_arb_all_cycles_at_rank(const bench_arb_t *arb, uint8_t expected_rank);

#endif /* BENCH_ARBITRATION_H */
