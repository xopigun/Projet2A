/**
 * @file traffic.h
 * @brief Trames applicatives périodiques de N1 à N3 : contenu et vérification.
 *
 * Chaque contendant émet sa trame de l'ICD toutes les 20 ms (ENERGY_COMMAND pour
 * N1, IMU_SPEED pour N2, TEMP_BATTERY pour N3). Faute de capteur réel, la charge
 * utile suit la séquence déterministe déclarée dans l'ICD (`simulations`), qui
 * boucle. Le compteur de trame avance à chaque émission ; ENERGY_COMMAND porte en
 * plus une somme de contrôle (XOR des octets 0 à 6).
 *
 * Le même module sert au récepteur : il connaît la séquence, les octets qui la
 * portent (masque) et la largeur du compteur de chaque trame. C'est ce qui permet
 * de noter une trame reçue sans connaître l'émetteur autrement que par l'ICD.
 *
 * Aucune dépendance HAL : testé nativement (tests_host/test_traffic.c).
 */

#ifndef BENCH_TRAFFIC_H
#define BENCH_TRAFFIC_H

#include <stdbool.h>
#include <stdint.h>

/** Description d'une trame applicative périodique, côté émetteur et récepteur. */
typedef struct {
    uint16_t can_id;
    uint8_t  dlc;
    uint16_t period_ms;
    uint8_t  steps;          /**< nombre de pas de la séquence déterministe */
    uint8_t  counter_bits;   /**< largeur du compteur de trame */
    bool     has_checksum;   /**< XOR des octets 0 à 6 dans l'octet 7 */
    uint8_t  content_mask[8];/**< bits portant la séquence (hors compteur, somme, capteur) */
    uint8_t  sensor_byte;    /**< position du bit `sensor_present`, 0xFF si absent */
    uint8_t  sensor_bit;
} bench_traffic_desc_t;

/** Trames applicatives connues : ENERGY_COMMAND, IMU_SPEED, TEMP_BATTERY. */
#define BENCH_TRAFFIC_KINDS 3u

/** @brief Description de la trame d'indice @p kind (0 à 2) ; NULL au-delà. */
const bench_traffic_desc_t *bench_traffic_desc(uint8_t kind);

/** @brief Indice de la trame portant @p can_id ; -1 si ce n'est pas une trame applicative. */
int bench_traffic_kind_of(uint16_t can_id);

/** @brief Indice de la trame émise par le nœud @p node_id ; -1 s'il n'en émet pas. */
int bench_traffic_kind_of_node(uint8_t node_id);

/**
 * @brief Construit la charge utile du pas @p step avec le compteur @p counter.
 *
 * Le compteur est tronqué à la largeur du champ ; la somme de contrôle est
 * calculée en dernier. @p data reçoit 8 octets.
 */
void bench_traffic_build(uint8_t kind, uint8_t step, uint8_t counter, uint8_t *data);

/** @brief Lit le compteur de trame d'une charge utile reçue. */
uint8_t bench_traffic_counter(uint8_t kind, const uint8_t *data);

/** @brief Vrai si la somme de contrôle est juste (toujours vrai sans somme). */
bool bench_traffic_checksum_ok(uint8_t kind, const uint8_t *data);

/** @brief Vrai si la trame déclare un capteur réel (contenu libre, non comparé). */
bool bench_traffic_sensor_present(uint8_t kind, const uint8_t *data);

/**
 * @brief Pas de la séquence dont la charge utile correspond à @p data.
 * @return 0 à steps-1, ou -1 si aucun pas ne correspond (contenu altéré).
 */
int bench_traffic_match_step(uint8_t kind, const uint8_t *data);

#endif /* BENCH_TRAFFIC_H */
