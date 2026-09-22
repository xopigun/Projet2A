/* ===========================================================================
 *  FICHIER GÉNÉRÉ — NE PAS ÉDITER À LA MAIN
 *
 *  Produit par tools/codegen à partir de icd/bench_icd.yaml.
 *  Toute modification manuelle sera écrasée, et la CI la rejettera.
 *
 *  Regénérer :  python -m tools.codegen
 * ===========================================================================
 */


#ifndef BENCH_ICD_GEN_H
#define BENCH_ICD_GEN_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Débit nominal du bus, en bit/s. */
#define BENCH_BITRATE 500000u

/** Nombre de nœuds déclarés dans l'ICD. */
#define BENCH_NODE_COUNT 4u

/* ---------------------------------------------------------------------
 *  Identifiants, par profil réseau
 * ------------------------------------------------------------------- */

/* Profil « bench » : Profil par défaut du banc. Les identifiants de service y sont déclarés « réservés banc, reconfigurables » dans les ICD partenaires, jamais imposés. */
#define BENCH_BENCH_ID_ARM 0x010u
#define BENCH_BENCH_ID_GO 0x011u
#define BENCH_BENCH_ID_BENCH_CFG 0x012u
#define BENCH_BENCH_ID_BENCH_RESULT 0x013u
#define BENCH_BENCH_ID_HEARTBEAT_N1 0x781u
#define BENCH_BENCH_ID_HEARTBEAT_N2 0x782u
#define BENCH_BENCH_ID_HEARTBEAT_N3 0x783u
#define BENCH_BENCH_ID_HEARTBEAT_N4 0x784u
#define BENCH_BENCH_ID_ENERGY_COMMAND 0x100u
#define BENCH_BENCH_ID_IMU_SPEED 0x200u
#define BENCH_BENCH_ID_TEMP_BATTERY 0x300u
#define BENCH_BENCH_HEARTBEAT_BASE 0x780u

/* Profil « alt_high » : Profil alternatif, services et heartbeat décalés vers le haut. */
#define BENCH_ALT_HIGH_ID_ARM 0x020u
#define BENCH_ALT_HIGH_ID_GO 0x021u
#define BENCH_ALT_HIGH_ID_BENCH_CFG 0x022u
#define BENCH_ALT_HIGH_ID_BENCH_RESULT 0x023u
#define BENCH_ALT_HIGH_ID_HEARTBEAT_N1 0x791u
#define BENCH_ALT_HIGH_ID_HEARTBEAT_N2 0x792u
#define BENCH_ALT_HIGH_ID_HEARTBEAT_N3 0x793u
#define BENCH_ALT_HIGH_ID_HEARTBEAT_N4 0x794u
#define BENCH_ALT_HIGH_ID_ENERGY_COMMAND 0x100u
#define BENCH_ALT_HIGH_ID_IMU_SPEED 0x200u
#define BENCH_ALT_HIGH_ID_TEMP_BATTERY 0x300u
#define BENCH_ALT_HIGH_HEARTBEAT_BASE 0x790u

/* Profil actif par défaut : « bench ». Les constantes sans préfixe de
 * profil ci-dessous renvoient vers lui. */

#define BENCH_ID_ARM BENCH_BENCH_ID_ARM
#define BENCH_ID_GO BENCH_BENCH_ID_GO
#define BENCH_ID_BENCH_CFG BENCH_BENCH_ID_BENCH_CFG
#define BENCH_ID_BENCH_RESULT BENCH_BENCH_ID_BENCH_RESULT
#define BENCH_ID_HEARTBEAT_N1 BENCH_BENCH_ID_HEARTBEAT_N1
#define BENCH_ID_HEARTBEAT_N2 BENCH_BENCH_ID_HEARTBEAT_N2
#define BENCH_ID_HEARTBEAT_N3 BENCH_BENCH_ID_HEARTBEAT_N3
#define BENCH_ID_HEARTBEAT_N4 BENCH_BENCH_ID_HEARTBEAT_N4
#define BENCH_ID_ENERGY_COMMAND BENCH_BENCH_ID_ENERGY_COMMAND
#define BENCH_ID_IMU_SPEED BENCH_BENCH_ID_IMU_SPEED
#define BENCH_ID_TEMP_BATTERY BENCH_BENCH_ID_TEMP_BATTERY
#define BENCH_HEARTBEAT_BASE BENCH_BENCH_HEARTBEAT_BASE

/** Une plage d'identifiants réservée au banc. */
typedef struct {
    uint16_t    first;
    uint16_t    last;
    const char *purpose;
} bench_reserved_range_t;

/** Une trame déclarée dans l'ICD. */
typedef struct {
    uint16_t    can_id;
    uint8_t     dlc;
    bool        is_service;
    bool        is_contender;
    const char *name;
} bench_frame_info_t;

#define BENCH_BENCH_RESERVED_COUNT 2u
#define BENCH_BENCH_FRAME_COUNT 11u
extern const bench_reserved_range_t bench_bench_reserved_ranges[BENCH_BENCH_RESERVED_COUNT];
extern const bench_frame_info_t bench_bench_frames[BENCH_BENCH_FRAME_COUNT];

#define BENCH_ALT_HIGH_RESERVED_COUNT 2u
#define BENCH_ALT_HIGH_FRAME_COUNT 11u
extern const bench_reserved_range_t bench_alt_high_reserved_ranges[BENCH_ALT_HIGH_RESERVED_COUNT];
extern const bench_frame_info_t bench_alt_high_frames[BENCH_ALT_HIGH_FRAME_COUNT];

/**
 * @brief Indique si un identifiant tombe dans une plage réservée au banc.
 *
 * Sert à refuser une trame applicative qui empiéterait sur les services.
 */
bool bench_id_is_reserved(uint16_t can_id);

/**
 * @brief Retrouve la description d'une trame par son identifiant.
 * @return NULL si l'identifiant n'est pas déclaré dans l'ICD.
 */
const bench_frame_info_t *bench_frame_by_id(uint16_t can_id);

/* ---------------------------------------------------------------------
 *  Trames
 * ------------------------------------------------------------------- */

/* --- ARM (DLC 8) ------------------------------ */

/**
 * Ordre d'armement. À sa réception, chaque contendant place sa trame de test dans sa boîte d'émission et incrémente son compteur « ARM reçus ». Contenu nul.
 */
/* ARM ne transporte aucun signal : 8 octets nuls. */
#define BENCH_ARM_DLC 8u

/* --- GO (DLC 8) ------------------------------ */

/**
 * Trame de 8 octets sans contenu utile : elle occupe le bus (environ 250 µs) le temps que tous les contendants aient armé. Contenu nul.
 */
/* GO ne transporte aucun signal : 8 octets nuls. */
#define BENCH_GO_DLC 8u

/* --- BENCH_CFG (DLC 8) ------------------------------ */

/**
 * Commande de configuration d'un nœud pendant un test.
 */
typedef struct {
    uint8_t target_node;
    /**< octet 0, bit 0, 8 bit(s), Intel, non signé. Numéro du nœud visé ; 0 = tous les nœuds. */
    uint8_t mode;
    /**< octet 1, bit 0, 8 bit(s), Intel, non signé. 0 normal, 1 babbling idiot, 2 débit erroné (250 kbit/s), 3 DLC incohérent, 4 silencieux (couvre aussi l'arrêt d'acquittement), 5 bus-off maintenu. */
    uint16_t param_u16;
    /**< octet 2, bit 0, 16 bit(s), Intel, non signé. Paramètre du mode ; pour le babbling idiot, identifiant à inonder. */
    uint16_t duration_ms;
    /**< octet 4, bit 0, 16 bit(s), Intel, non signé [ms]. Durée maximale du mode de faute. Toute faute est bornée dans le temps et révocable ; 0 signifie « révoquer immédiatement ». */
    uint16_t heartbeat_period_ms;
    /**< octet 6, bit 0, 16 bit(s), Intel, non signé [ms]. 0 = ne pas modifier la période courante. */
} bench_bench_cfg_t;

#define BENCH_BENCH_CFG_DLC 8u

/** @brief Encode BENCH_CFG dans @p data (8 octets). */
void bench_bench_cfg_pack(uint8_t *data, const bench_bench_cfg_t *src);

/** @brief Décode BENCH_CFG depuis @p data (8 octets). */
void bench_bench_cfg_unpack(bench_bench_cfg_t *dst, const uint8_t *data);

/* --- BENCH_RESULT (DLC 8) ------------------------------ */

/**
 * Réponse de fin de test émise par le nœud visé.
 */
typedef struct {
    uint8_t node_id;
    /**< octet 0, bit 0, 8 bit(s), Intel, non signé. */
    uint8_t mode;
    /**< octet 1, bit 0, 8 bit(s), Intel, non signé. */
    uint8_t status;
    /**< octet 2, bit 0, 8 bit(s), Intel, non signé. 0 succès, 1 refusé, 2 interrompu, 3 non supporté */
    uint8_t arm_rx;
    /**< octet 3, bit 0, 8 bit(s), Intel, non signé. */
    uint16_t frames_sent;
    /**< octet 4, bit 0, 16 bit(s), Intel, non signé. */
    uint16_t frames_lost;
    /**< octet 6, bit 0, 16 bit(s), Intel, non signé. */
} bench_bench_result_t;

#define BENCH_BENCH_RESULT_DLC 8u

/** @brief Encode BENCH_RESULT dans @p data (8 octets). */
void bench_bench_result_pack(uint8_t *data, const bench_bench_result_t *src);

/** @brief Décode BENCH_RESULT depuis @p data (8 octets). */
void bench_bench_result_unpack(bench_bench_result_t *dst, const uint8_t *data);

/* --- HEARTBEAT (DLC 8) ------------------------------ */

/**
 * État périodique d'un nœud (période par défaut 500 ms, configurable), suspendu pendant un test d'arbitrage. TEC et REC proviennent des registres du contrôleur (FDCAN ECR, bxCAN ESR) : aucun compteur d'erreur n'est réimplémenté en logiciel.
 */
typedef struct {
    uint8_t ctrl_state;
    /**< octet 0, bit 0, 2 bit(s), Intel, non signé. 0 error-active, 1 error-warning, 2 error-passive, 3 bus-off. */
    uint8_t last_error_code;
    /**< octet 0, bit 2, 3 bit(s), Intel, non signé. LEC du contrôleur (FDCAN PSR.LEC / bxCAN ESR.LEC). */
    uint8_t clock_not_qualified;
    /**< octet 0, bit 5, 1 bit(s), Intel, non signé. 1 si le nœud tourne sur HSI : la référence d'horloge n'est pas conforme et aucun verdict de réussite ne doit être prononcé. */
    uint8_t fault_mode_active;
    /**< octet 0, bit 6, 1 bit(s), Intel, non signé. */
    uint8_t silent_mode;
    /**< octet 0, bit 7, 1 bit(s), Intel, non signé. */
    uint8_t tec;
    /**< octet 1, bit 0, 8 bit(s), Intel, non signé. Transmit Error Counter, lu dans le matériel */
    uint8_t rec;
    /**< octet 2, bit 0, 8 bit(s), Intel, non signé. Receive Error Counter, lu dans le matériel */
    uint8_t current_mode;
    /**< octet 3, bit 0, 4 bit(s), Intel, non signé. Mode de test courant ; les modes vont de 0 à 5. */
    uint8_t reserved;
    /**< octet 3, bit 4, 4 bit(s), Intel, non signé. Réservé, doit valoir 0. */
    uint8_t rx_fifo_lost;
    /**< octet 4, bit 0, 8 bit(s), Intel, non signé. Pertes FIFO matérielles (FDCAN RF0L), saturant */
    uint8_t ring_overflow;
    /**< octet 5, bit 0, 8 bit(s), Intel, non signé. Débordements du tampon circulaire logiciel, saturant */
    uint8_t non_classic_rx;
    /**< octet 6, bit 0, 8 bit(s), Intel, non signé. Trames CAN FD signalées par le contrôleur, saturant. Le bus est en CAN 2.0A classic : toute valeur non nulle est une anomalie. */
    uint8_t ext_id_rx;
    /**< octet 7, bit 0, 8 bit(s), Intel, non signé. Trames à identifiant 29 bits reçues, saturant. L'ICD n'utilise que des identifiants 11 bits. */
} bench_heartbeat_t;

#define BENCH_HEARTBEAT_DLC 8u

/** @brief Encode HEARTBEAT dans @p data (8 octets). */
void bench_heartbeat_pack(uint8_t *data, const bench_heartbeat_t *src);

/** @brief Décode HEARTBEAT depuis @p data (8 octets). */
void bench_heartbeat_unpack(bench_heartbeat_t *dst, const uint8_t *data);

/* --- ENERGY_COMMAND (DLC 8) ------------------------------ */

/**
 * Commande énergie émise périodiquement par N1 ; contendant de rang 1 attendu.
 */
typedef struct {
    float torque_setpoint;
    /**< octet 0, bit 0, 16 bit(s), Intel, signé, physique = brut * 0.1 + 0 [N.m]. */
    float speed_setpoint;
    /**< octet 2, bit 0, 16 bit(s), Intel, signé, physique = brut * 0.5 + 0 [rpm]. */
    float current_limit;
    /**< octet 4, bit 0, 12 bit(s), Intel, non signé, physique = brut * 0.05 + 0 [A]. */
    uint8_t enable;
    /**< octet 5, bit 4, 1 bit(s), Intel, non signé. */
    uint8_t direction;
    /**< octet 5, bit 5, 1 bit(s), Intel, non signé. */
    uint8_t command_counter;
    /**< octet 6, bit 0, 8 bit(s), Intel, non signé. Incrémenté à chaque émission ; sert à détecter une trame manquante. */
    uint8_t checksum;
    /**< octet 7, bit 0, 8 bit(s), Intel, non signé. Somme XOR des octets 0 à 6. */
} bench_energy_command_t;

#define BENCH_ENERGY_COMMAND_DLC 8u

/** @brief Encode ENERGY_COMMAND dans @p data (8 octets). */
void bench_energy_command_pack(uint8_t *data, const bench_energy_command_t *src);

/** @brief Décode ENERGY_COMMAND depuis @p data (8 octets). */
void bench_energy_command_unpack(bench_energy_command_t *dst, const uint8_t *data);

/* --- IMU_SPEED (DLC 8) ------------------------------ */

/**
 * IMU et vitesse roue émises par N2 ; contendant de rang 2 attendu. Le capteur MPU-6050 (0x68) est utilisé s'il est détecté, sinon la séquence déterministe déclarée en bas de ce fichier prend le relais.
 */
typedef struct {
    float accel_x;
    /**< octet 0, bit 0, 16 bit(s), Intel, signé, physique = brut * 0.001 + 0 [g]. */
    float accel_y;
    /**< octet 2, bit 0, 16 bit(s), Intel, signé, physique = brut * 0.001 + 0 [g]. */
    float gyro_z;
    /**< octet 4, bit 0, 16 bit(s), Intel, signé, physique = brut * 0.0625 + 0 [deg/s]. */
    float wheel_speed;
    /**< octet 6, bit 0, 12 bit(s), Intel, non signé, physique = brut * 0.25 + 0 [km/h]. Mesurée par capteur à effet Hall. */
    uint8_t sensor_present;
    /**< octet 7, bit 4, 1 bit(s), Intel, non signé. 1 si le capteur réel répond, 0 si la séquence simulée est utilisée. */
    uint8_t frame_counter;
    /**< octet 7, bit 5, 3 bit(s), Intel, non signé. */
} bench_imu_speed_t;

#define BENCH_IMU_SPEED_DLC 8u

/** @brief Encode IMU_SPEED dans @p data (8 octets). */
void bench_imu_speed_pack(uint8_t *data, const bench_imu_speed_t *src);

/** @brief Décode IMU_SPEED depuis @p data (8 octets). */
void bench_imu_speed_unpack(bench_imu_speed_t *dst, const uint8_t *data);

/* --- TEMP_BATTERY (DLC 8) ------------------------------ */

/**
 * Température et état batterie émis par N3 ; contendant de rang 3 attendu. Le DS18B20 est utilisé s'il est détecté, sinon la séquence déterministe.
 */
typedef struct {
    float temperature;
    /**< octet 0, bit 0, 16 bit(s), Intel, signé, physique = brut * 0.0625 + 0 [degC]. Résolution native du DS18B20 (1/16 °C). */
    float pack_voltage;
    /**< octet 2, bit 0, 16 bit(s), Intel, non signé, physique = brut * 0.01 + 0 [V]. */
    float pack_current;
    /**< octet 4, bit 0, 16 bit(s), Intel, signé, physique = brut * 0.01 + 0 [A]. */
    uint8_t state_of_charge;
    /**< octet 6, bit 0, 7 bit(s), Intel, non signé [%]. */
    uint8_t sensor_present;
    /**< octet 6, bit 7, 1 bit(s), Intel, non signé. */
    uint8_t frame_counter;
    /**< octet 7, bit 0, 8 bit(s), Intel, non signé. */
} bench_temp_battery_t;

#define BENCH_TEMP_BATTERY_DLC 8u

/** @brief Encode TEMP_BATTERY dans @p data (8 octets). */
void bench_temp_battery_pack(uint8_t *data, const bench_temp_battery_t *src);

/** @brief Décode TEMP_BATTERY depuis @p data (8 octets). */
void bench_temp_battery_unpack(bench_temp_battery_t *dst, const uint8_t *data);

/* ---------------------------------------------------------------------
 *  Verrouillage CAN 2.0A classic
 *
 *  Le peripherique du G431 s'appelle FDCAN, mais le protocole utilise par
 *  le banc est CAN 2.0A classic : identifiants 11 bits, 8 octets au plus,
 *  pas de commutation de debit. Ces assertions echouent a la compilation
 *  si l'ICD s'en ecarte.
 * ------------------------------------------------------------------- */

/** Charge utile maximale d'une trame CAN 2.0 classic, en octets. */
#define BENCH_CLASSIC_MAX_DLC 8u

/** Plus grand identifiant representable sur 11 bits. */
#define BENCH_CLASSIC_MAX_ID 0x7FFu

_Static_assert(BENCH_ID_ARM <= BENCH_CLASSIC_MAX_ID, "ARM : identifiant hors des 11 bits du CAN 2.0A");
_Static_assert(BENCH_ARM_DLC <= BENCH_CLASSIC_MAX_DLC, "ARM : DLC superieur a 8, impossible en CAN 2.0 classic");
_Static_assert(BENCH_ID_GO <= BENCH_CLASSIC_MAX_ID, "GO : identifiant hors des 11 bits du CAN 2.0A");
_Static_assert(BENCH_GO_DLC <= BENCH_CLASSIC_MAX_DLC, "GO : DLC superieur a 8, impossible en CAN 2.0 classic");
_Static_assert(BENCH_ID_BENCH_CFG <= BENCH_CLASSIC_MAX_ID, "BENCH_CFG : identifiant hors des 11 bits du CAN 2.0A");
_Static_assert(BENCH_BENCH_CFG_DLC <= BENCH_CLASSIC_MAX_DLC, "BENCH_CFG : DLC superieur a 8, impossible en CAN 2.0 classic");
_Static_assert(BENCH_ID_BENCH_RESULT <= BENCH_CLASSIC_MAX_ID, "BENCH_RESULT : identifiant hors des 11 bits du CAN 2.0A");
_Static_assert(BENCH_BENCH_RESULT_DLC <= BENCH_CLASSIC_MAX_DLC, "BENCH_RESULT : DLC superieur a 8, impossible en CAN 2.0 classic");
_Static_assert(BENCH_ID_HEARTBEAT_N1 <= BENCH_CLASSIC_MAX_ID, "HEARTBEAT_N1 : identifiant hors des 11 bits du CAN 2.0A");
_Static_assert(BENCH_HEARTBEAT_DLC <= BENCH_CLASSIC_MAX_DLC, "HEARTBEAT : DLC superieur a 8, impossible en CAN 2.0 classic");
_Static_assert(BENCH_ID_HEARTBEAT_N2 <= BENCH_CLASSIC_MAX_ID, "HEARTBEAT_N2 : identifiant hors des 11 bits du CAN 2.0A");
_Static_assert(BENCH_ID_HEARTBEAT_N3 <= BENCH_CLASSIC_MAX_ID, "HEARTBEAT_N3 : identifiant hors des 11 bits du CAN 2.0A");
_Static_assert(BENCH_ID_HEARTBEAT_N4 <= BENCH_CLASSIC_MAX_ID, "HEARTBEAT_N4 : identifiant hors des 11 bits du CAN 2.0A");
_Static_assert(BENCH_ID_ENERGY_COMMAND <= BENCH_CLASSIC_MAX_ID, "ENERGY_COMMAND : identifiant hors des 11 bits du CAN 2.0A");
_Static_assert(BENCH_ENERGY_COMMAND_DLC <= BENCH_CLASSIC_MAX_DLC, "ENERGY_COMMAND : DLC superieur a 8, impossible en CAN 2.0 classic");
_Static_assert(BENCH_ID_IMU_SPEED <= BENCH_CLASSIC_MAX_ID, "IMU_SPEED : identifiant hors des 11 bits du CAN 2.0A");
_Static_assert(BENCH_IMU_SPEED_DLC <= BENCH_CLASSIC_MAX_DLC, "IMU_SPEED : DLC superieur a 8, impossible en CAN 2.0 classic");
_Static_assert(BENCH_ID_TEMP_BATTERY <= BENCH_CLASSIC_MAX_ID, "TEMP_BATTERY : identifiant hors des 11 bits du CAN 2.0A");
_Static_assert(BENCH_TEMP_BATTERY_DLC <= BENCH_CLASSIC_MAX_DLC, "TEMP_BATTERY : DLC superieur a 8, impossible en CAN 2.0 classic");

#ifdef __cplusplus
}
#endif

#endif /* BENCH_ICD_GEN_H */
