/**
 * @file rx_quality.h
 * @brief Note de qualité que le récepteur donne à chaque trame reçue.
 *
 * Chaque trame applicative (ENERGY_COMMAND, IMU_SPEED, TEMP_BATTERY) et chaque
 * heartbeat d'un autre nœud reçoit une note de 0 à 100 :
 *
 * | Contrôle                        | Effet sur la note                              |
 * |---------------------------------|------------------------------------------------|
 * | DLC différent de l'ICD          | note 0, trame abîmée                           |
 * | somme de contrôle fausse        | note 0, trame abîmée (ENERGY_COMMAND)          |
 * | compteur répété                 | −50, trame abîmée                              |
 * | trames manquées (saut compteur) | −20 par trame manquée, au plus −60             |
 * | contenu hors séquence de l'ICD  | −40, trame abîmée ; −20 si le pas est décalé   |
 * | écart à la période de l'ICD     | gratuit jusqu'à max(2 ms, 10 %), puis jusqu'à −30 |
 *
 * Les heartbeats n'ont pas de compteur : leurs pertes se déduisent de l'intervalle
 * (un intervalle de 3 périodes compte 2 trames manquées).
 *
 * Les notes sont moyennées sur une fenêtre de @ref BENCH_RXQ_WINDOW_MS ; le nœud les
 * envoie au PC dans sa trame QUALITY et les affiche sur son écran. Un cycle
 * d'arbitrage (ARM) suspend le jugement de la ponctualité pendant deux trames :
 * l'émission périodique y est interrompue volontairement.
 *
 * Aucune dépendance HAL : testé nativement (tests_host/test_rx_quality.c).
 */

#ifndef BENCH_RX_QUALITY_H
#define BENCH_RX_QUALITY_H

#include <stdbool.h>
#include <stdint.h>

#include "app/traffic.h"
#include "can_if.h"
#include "icd_gen.h"

/** Fenêtre de moyenne, égale à la période de la trame QUALITY. */
#define BENCH_RXQ_WINDOW_MS 500u

/** Note signifiant « aucune trame reçue sur la fenêtre ». */
#define BENCH_RXQ_NONE 255u

/** Suivi d'une source (un identifiant). */
typedef struct {
    bool     seen;          /**< au moins une trame reçue depuis le démarrage */
    bool     timing_ref;    /**< last_us est une référence valable pour la ponctualité */
    uint8_t  skip_timing;   /**< trames dont la ponctualité n'est pas jugée */
    uint32_t last_us;
    uint8_t  last_counter;
    int8_t   last_step;     /**< -1 si inconnu */
    uint32_t sum;           /**< somme des notes de la fenêtre */
    uint16_t count;         /**< trames de la fenêtre */
    uint8_t  last_score;    /**< note de la dernière trame */
} bench_rxq_source_t;

/** Notes d'une fenêtre, telles qu'envoyées dans QUALITY et affichées. */
typedef struct {
    uint8_t score[BENCH_TRAFFIC_KINDS]; /**< ENERGY_COMMAND, IMU_SPEED, TEMP_BATTERY */
    uint8_t score_heartbeat;
    uint8_t lost;
    uint8_t bad;
    uint8_t late;
} bench_rxq_window_t;

/** État complet du suivi de qualité d'un nœud. */
typedef struct {
    uint8_t            node_id;
    bench_rxq_source_t app[BENCH_TRAFFIC_KINDS];
    bench_rxq_source_t hb[BENCH_NODE_COUNT];          /**< indice = node_id - 1 */
    uint16_t           hb_period_ms[BENCH_NODE_COUNT];
    uint8_t            lost, bad, late;                /**< fenêtre en cours, saturants */
    uint8_t            report_counter;
    bench_rxq_window_t last;                           /**< dernière fenêtre close */
    uint32_t           total_frames, total_lost, total_bad, total_late;
} bench_rxq_t;

/** @brief Remet le suivi à zéro pour le nœud @p node_id. */
void bench_rxq_init(bench_rxq_t *q, uint8_t node_id);

/**
 * @brief Note une trame reçue.
 * @return la note (0 à 100), ou BENCH_RXQ_NONE si la trame n'est pas suivie.
 */
uint8_t bench_rxq_on_frame(bench_rxq_t *q, const bench_can_frame_t *frame);

/** @brief Un cycle d'arbitrage commence : la ponctualité est suspendue. */
void bench_rxq_on_arm(bench_rxq_t *q);

/** @brief BENCH_CFG reçu : met à jour la période de heartbeat attendue. */
void bench_rxq_on_cfg(bench_rxq_t *q, const uint8_t *data);

/**
 * @brief Clôt la fenêtre : remplit la trame QUALITY et remet la fenêtre à zéro.
 * @param out charge utile de 8 octets.
 */
void bench_rxq_report(bench_rxq_t *q, uint8_t *out);

#endif /* BENCH_RX_QUALITY_H */
