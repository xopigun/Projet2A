/**
 * @file slcan.h
 * @brief Protocole slcan (« Lawicel »), côté adaptateur : analyse des commandes
 *        du PC et mise en forme des trames envoyées au PC.
 *
 * Sert au pont CAN-USB du banc (`entry/slcan_bridge.c`) : une carte devient un
 * adaptateur que `canbench --interface slcan` (python-can) pilote comme un
 * CANable. Ce fichier ne dépend d'aucun en-tête HAL, donc il est testé sur
 * l'hôte (`tests_host/test_slcan.c`).
 *
 * Seul le CAN 2.0A classic est pris en charge, comme tout le banc : les trames
 * étendues, distantes ou FD sont refusées par un BEL (`\a`).
 *
 * Réponses de l'adaptateur : `\r` pour « fait », `\a` pour « refusé ». Une
 * trame émise par le PC est acquittée par `z\r`.
 */

#ifndef BENCH_SLCAN_H
#define BENCH_SLCAN_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "can_if.h"

/** Longueur maximale d'une ligne de commande, `\r` exclu : `tIIILDD…` = 21. */
#define BENCH_SLCAN_LINE_MAX 32u

/** Longueur maximale d'une trame mise en forme, `\r` compris. */
#define BENCH_SLCAN_FRAME_MAX 22u

#define BENCH_SLCAN_OK  '\r'
#define BENCH_SLCAN_ERR '\a'

typedef enum {
    BENCH_SLCAN_NONE = 0,   /**< ligne vide : rien à faire, aucune réponse */
    BENCH_SLCAN_INVALID,    /**< commande inconnue ou mal formée : répondre BEL */
    BENCH_SLCAN_OPEN,       /**< `O` : ouvrir le bus, participation normale */
    BENCH_SLCAN_LISTEN,     /**< `L` : ouvrir en écoute seule (n'acquitte pas) */
    BENCH_SLCAN_CLOSE,      /**< `C` */
    BENCH_SLCAN_BITRATE,    /**< `S0` à `S8` : voir bitrate_bps */
    BENCH_SLCAN_SEND,       /**< `tIIILDD…` : émettre @c frame */
    BENCH_SLCAN_VERSION,    /**< `V` */
    BENCH_SLCAN_SERIAL,     /**< `N` */
    BENCH_SLCAN_FLAGS,      /**< `F` */
    BENCH_SLCAN_ACCEPT,     /**< `M…`, `m…`, `Z0` : acceptés et ignorés */
} bench_slcan_cmd_type_t;

typedef struct {
    bench_slcan_cmd_type_t type;
    uint32_t               bitrate_bps;  /**< pour BENCH_SLCAN_BITRATE */
    bench_can_frame_t      frame;        /**< pour BENCH_SLCAN_SEND */
} bench_slcan_cmd_t;

/** Accumulateur de ligne : les octets arrivent un à un depuis le port série. */
typedef struct {
    char     line[BENCH_SLCAN_LINE_MAX];
    uint32_t length;
    bool     overflow;  /**< la ligne courante dépasse le maximum : à rejeter */
} bench_slcan_parser_t;

void bench_slcan_parser_init(bench_slcan_parser_t *parser);

/**
 * @brief Pousse un octet reçu du PC.
 * @return true lorsqu'une ligne est complète : @p cmd est alors renseigné
 *         (éventuellement BENCH_SLCAN_NONE ou BENCH_SLCAN_INVALID).
 */
bool bench_slcan_feed(bench_slcan_parser_t *parser, uint8_t byte, bench_slcan_cmd_t *cmd);

/**
 * @brief Débit en bit/s d'un code `Sn`, ou 0 si le code n'est pas pris en charge.
 *
 * `S9` (83,3 kbit/s) n'est pas reproductible exactement avec une horloge de
 * 80 MHz et 16 quanta : il est refusé plutôt qu'approché.
 */
uint32_t bench_slcan_bitrate_of_code(char code);

/** @brief Met en forme une trame reçue : `tIIILDD…\r`. Retourne la longueur écrite. */
size_t bench_slcan_format_frame(const bench_can_frame_t *frame, char *out, size_t capacity);

/**
 * @brief Octet d'état de la commande `F` (convention Lawicel).
 *
 * Bit 2 : avertissement d'erreur, bit 3 : débordement de réception, bit 5 :
 * error-passive, bit 7 : bus-off (signalé comme erreur de bus).
 */
uint8_t bench_slcan_status_flags(const bench_can_status_t *status, bool rx_overflow);

#endif /* BENCH_SLCAN_H */
