/**
 * @file slcan.c
 * @brief Protocole slcan côté adaptateur. Voir slcan.h.
 */

#include "slcan.h"

static int hex_value(char c) {
    if (c >= '0' && c <= '9') {
        return c - '0';
    }
    if (c >= 'A' && c <= 'F') {
        return c - 'A' + 10;
    }
    if (c >= 'a' && c <= 'f') {
        return c - 'a' + 10;
    }
    return -1;
}

void bench_slcan_parser_init(bench_slcan_parser_t *parser) {
    parser->length = 0u;
    parser->overflow = false;
}

uint32_t bench_slcan_bitrate_of_code(char code) {
    switch (code) {
    case '0': return 10000u;
    case '1': return 20000u;
    case '2': return 50000u;
    case '3': return 100000u;
    case '4': return 125000u;
    case '5': return 250000u;
    case '6': return 500000u;
    case '8': return 1000000u;
    default:  return 0u;  /* S7 (750 k) et S9 (83,3 k) : pas de diviseur entier */
    }
}

/** Analyse « tIIILDD… » ; false si la ligne est mal formée ou hors CAN 2.0A. */
static bool parse_standard_frame(const char *line, uint32_t length, bench_can_frame_t *frame) {
    if (length < 5u) {
        return false;
    }

    uint32_t id = 0u;
    for (uint32_t i = 1u; i <= 3u; i++) {
        const int digit = hex_value(line[i]);
        if (digit < 0) {
            return false;
        }
        id = (id << 4) | (uint32_t)digit;
    }
    if (id > 0x7FFu) {
        return false;  /* identifiant de plus de 11 bits */
    }

    const char dlc_char = line[4];
    if (dlc_char < '0' || dlc_char > '8') {
        return false;  /* CAN 2.0 : 8 octets au plus */
    }
    const uint32_t dlc = (uint32_t)(dlc_char - '0');
    if (length != 5u + 2u * dlc) {
        return false;
    }

    *frame = (bench_can_frame_t){0};
    frame->id = (uint16_t)id;
    frame->dlc = (uint8_t)dlc;
    for (uint32_t i = 0u; i < dlc; i++) {
        const int high = hex_value(line[5u + 2u * i]);
        const int low = hex_value(line[6u + 2u * i]);
        if (high < 0 || low < 0) {
            return false;
        }
        frame->data[i] = (uint8_t)((high << 4) | low);
    }
    return true;
}

static void parse_line(const bench_slcan_parser_t *parser, bench_slcan_cmd_t *cmd) {
    const char    *line = parser->line;
    const uint32_t length = parser->length;

    *cmd = (bench_slcan_cmd_t){0};
    cmd->type = BENCH_SLCAN_INVALID;

    if (parser->overflow) {
        return;
    }
    if (length == 0u) {
        cmd->type = BENCH_SLCAN_NONE;
        return;
    }

    switch (line[0]) {
    case 'O': if (length == 1u) { cmd->type = BENCH_SLCAN_OPEN; }    break;
    case 'L': if (length == 1u) { cmd->type = BENCH_SLCAN_LISTEN; }  break;
    case 'C': if (length == 1u) { cmd->type = BENCH_SLCAN_CLOSE; }   break;
    case 'V': if (length == 1u) { cmd->type = BENCH_SLCAN_VERSION; } break;
    case 'N': if (length == 1u) { cmd->type = BENCH_SLCAN_SERIAL; }  break;
    case 'F': if (length == 1u) { cmd->type = BENCH_SLCAN_FLAGS; }   break;
    case 'S':
        if (length == 2u) {
            cmd->bitrate_bps = bench_slcan_bitrate_of_code(line[1]);
            if (cmd->bitrate_bps != 0u) {
                cmd->type = BENCH_SLCAN_BITRATE;
            }
        }
        break;
    case 'Z':
        /* Horodatage par l'adaptateur : non fourni, seul « désactivé » est vrai. */
        if (length == 2u && line[1] == '0') {
            cmd->type = BENCH_SLCAN_ACCEPT;
        }
        break;
    case 'M':
    case 'm':
        /* Filtres d'acceptation : le pont laisse tout passer, c'est ce qu'un
         * outil de mesure doit faire. La commande est acquittée sans effet. */
        cmd->type = BENCH_SLCAN_ACCEPT;
        break;
    case 't':
        if (parse_standard_frame(line, length, &cmd->frame)) {
            cmd->type = BENCH_SLCAN_SEND;
        }
        break;
    default:
        break;  /* 'T', 'r', 'R', 'd', 'D', 'b', 'B' : hors CAN 2.0A standard */
    }
}

bool bench_slcan_feed(bench_slcan_parser_t *parser, uint8_t byte, bench_slcan_cmd_t *cmd) {
    if (byte == '\n') {
        return false;  /* fin de ligne CRLF d'un terminal : ignorée */
    }
    if (byte == '\r') {
        parse_line(parser, cmd);
        bench_slcan_parser_init(parser);
        return true;
    }
    if (parser->length < BENCH_SLCAN_LINE_MAX) {
        parser->line[parser->length++] = (char)byte;
    } else {
        parser->overflow = true;
    }
    return false;
}

size_t bench_slcan_format_frame(const bench_can_frame_t *frame, char *out, size_t capacity) {
    static const char hex[] = "0123456789ABCDEF";
    const size_t need = 5u + 2u * frame->dlc + 1u;

    if (frame->dlc > 8u || frame->id > 0x7FFu || capacity < need) {
        return 0u;
    }

    size_t n = 0u;
    out[n++] = 't';
    out[n++] = hex[(frame->id >> 8) & 0xFu];
    out[n++] = hex[(frame->id >> 4) & 0xFu];
    out[n++] = hex[frame->id & 0xFu];
    out[n++] = (char)('0' + frame->dlc);
    for (uint8_t i = 0u; i < frame->dlc; i++) {
        out[n++] = hex[frame->data[i] >> 4];
        out[n++] = hex[frame->data[i] & 0xFu];
    }
    out[n++] = BENCH_SLCAN_OK;
    return n;
}

uint8_t bench_slcan_status_flags(const bench_can_status_t *status, bool rx_overflow) {
    uint8_t flags = 0u;

    if (status->state == BENCH_CAN_ERROR_WARNING) {
        flags |= 1u << 2;
    }
    if (rx_overflow || status->rx_fifo_lost != 0u) {
        flags |= 1u << 3;
    }
    if (status->state == BENCH_CAN_ERROR_PASSIVE) {
        flags |= 1u << 5;
    }
    if (status->state == BENCH_CAN_BUS_OFF) {
        flags |= 1u << 7;
    }
    return flags;
}
