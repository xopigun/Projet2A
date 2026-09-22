"""Génération du code C : structures, pack/unpack, constantes d'identifiants."""

from __future__ import annotations

from .model import Icd, Message, Profile, Signal

BANNER = """\
/* ===========================================================================
 *  FICHIER GÉNÉRÉ — NE PAS ÉDITER À LA MAIN
 *
 *  Produit par tools/codegen à partir de icd/bench_icd.yaml.
 *  Toute modification manuelle sera écrasée, et la CI la rejettera.
 *
 *  Regénérer :  python -m tools.codegen
 * ===========================================================================
 */
"""


def _doc(signal: Signal) -> str:
    bits = f"octet {signal.start_byte}, bit {signal.start_bit}, {signal.length} bit(s)"
    scale = ""
    if signal.factor != 1.0 or signal.offset != 0.0:
        scale = f", physique = brut * {signal.factor:g} + {signal.offset:g}"
    unit = f" [{signal.unit}]" if signal.unit else ""
    comment = f" {signal.comment}" if signal.comment else ""
    order = "Intel" if signal.byte_order == "little_endian" else "Motorola"
    sign = "signé" if signal.signed else "non signé"
    return f"    /**< {bits}, {order}, {sign}{scale}{unit}.{comment} */"


# ---------------------------------------------------------------------------
#  En-tête
# ---------------------------------------------------------------------------


def generate_header(icd: Icd) -> str:
    out: list[str] = [BANNER, ""]
    out += [
        "#ifndef BENCH_ICD_GEN_H",
        "#define BENCH_ICD_GEN_H",
        "",
        "#include <stdbool.h>",
        "#include <stddef.h>",
        "#include <stdint.h>",
        "",
        "#ifdef __cplusplus",
        'extern "C" {',
        "#endif",
        "",
        "/** Débit nominal du bus, en bit/s. */",
        f"#define BENCH_BITRATE {icd.bus['bitrate']}u",
        "",
        "/** Nombre de nœuds déclarés dans l'ICD. */",
        f"#define BENCH_NODE_COUNT {len(icd.nodes)}u",
        "",
    ]

    # --- identifiants, par profil -----------------------------------------
    out += [
        "/* ---------------------------------------------------------------------",
        " *  Identifiants, par profil réseau",
        " * ------------------------------------------------------------------- */",
        "",
    ]
    for profile in icd.profiles.values():
        prefix = f"BENCH_{profile.name.upper()}"
        out.append(f"/* Profil « {profile.name} » : {profile.description} */")
        for message in profile.messages:
            out.append(
                f"#define {prefix}_ID_{message.name.upper()} 0x{message.can_id:03X}u"
            )
        out.append(f"#define {prefix}_HEARTBEAT_BASE 0x{profile.heartbeat_base:03X}u")
        out.append("")

    default = icd.default
    out += [
        f"/* Profil actif par défaut : « {default.name} ». Les constantes sans préfixe de",
        " * profil ci-dessous renvoient vers lui. */",
        "",
    ]
    for message in default.messages:
        out.append(
            f"#define BENCH_ID_{message.name.upper()} "
            f"BENCH_{default.name.upper()}_ID_{message.name.upper()}"
        )
    out.append(
        f"#define BENCH_HEARTBEAT_BASE BENCH_{default.name.upper()}_HEARTBEAT_BASE"
    )
    out.append("")

    # --- table des identifiants réservés ----------------------------------
    out += [
        "/** Une plage d'identifiants réservée au banc. */",
        "typedef struct {",
        "    uint16_t    first;",
        "    uint16_t    last;",
        "    const char *purpose;",
        "} bench_reserved_range_t;",
        "",
        "/** Une trame déclarée dans l'ICD. */",
        "typedef struct {",
        "    uint16_t    can_id;",
        "    uint8_t     dlc;",
        "    bool        is_service;",
        "    bool        is_contender;",
        "    const char *name;",
        "} bench_frame_info_t;",
        "",
    ]
    for profile in icd.profiles.values():
        prefix = f"bench_{profile.name}"
        out.append(
            f"#define BENCH_{profile.name.upper()}_RESERVED_COUNT "
            f"{len(profile.reserved_ranges)}u"
        )
        out.append(
            f"#define BENCH_{profile.name.upper()}_FRAME_COUNT {len(profile.messages)}u"
        )
        out.append(
            f"extern const bench_reserved_range_t {prefix}_reserved_ranges"
            f"[BENCH_{profile.name.upper()}_RESERVED_COUNT];"
        )
        out.append(
            f"extern const bench_frame_info_t {prefix}_frames"
            f"[BENCH_{profile.name.upper()}_FRAME_COUNT];"
        )
        out.append("")

    out += [
        "/**",
        " * @brief Indique si un identifiant tombe dans une plage réservée au banc.",
        " *",
        " * Sert à refuser une trame applicative qui empiéterait sur les services.",
        " */",
        "bool bench_id_is_reserved(uint16_t can_id);",
        "",
        "/**",
        " * @brief Retrouve la description d'une trame par son identifiant.",
        " * @return NULL si l'identifiant n'est pas déclaré dans l'ICD.",
        " */",
        "const bench_frame_info_t *bench_frame_by_id(uint16_t can_id);",
        "",
    ]

    # --- structures et prototypes -----------------------------------------
    out += [
        "/* ---------------------------------------------------------------------",
        " *  Trames",
        " * ------------------------------------------------------------------- */",
        "",
    ]
    for message in _unique_layouts(default):
        out += _struct_for(message)

    out += _classic_assertions(icd)
    out += [
        "#ifdef __cplusplus",
        "}",
        "#endif",
        "",
        "#endif /* BENCH_ICD_GEN_H */",
        "",
    ]
    return "\n".join(out)


def _classic_assertions(icd: Icd) -> list[str]:
    """Assertions statiques verrouillant le protocole en CAN 2.0A classic.

    Le périphérique du G431 s'appelle FDCAN, mais le protocole utilisé par le
    banc est **CAN 2.0A classic** : identifiants 11 bits, charge utile de 8
    octets au plus, pas de commutation de débit. Une dérive de l'ICD doit casser
    la compilation, pas se découvrir sur le banc.
    """
    out = [
        "/* ---------------------------------------------------------------------",
        " *  Verrouillage CAN 2.0A classic",
        " *",
        " *  Le peripherique du G431 s'appelle FDCAN, mais le protocole utilise par",
        " *  le banc est CAN 2.0A classic : identifiants 11 bits, 8 octets au plus,",
        " *  pas de commutation de debit. Ces assertions echouent a la compilation",
        " *  si l'ICD s'en ecarte.",
        " * ------------------------------------------------------------------- */",
        "",
        "/** Charge utile maximale d'une trame CAN 2.0 classic, en octets. */",
        "#define BENCH_CLASSIC_MAX_DLC 8u",
        "",
        "/** Plus grand identifiant representable sur 11 bits. */",
        "#define BENCH_CLASSIC_MAX_ID 0x7FFu",
        "",
    ]
    seen: set[str] = set()
    for message in icd.default.messages:
        base = (
            message.name if message.node_id is None else message.name.rsplit("_", 1)[0]
        )
        out.append(
            f"_Static_assert(BENCH_ID_{message.name.upper()} <= BENCH_CLASSIC_MAX_ID,"
            f' "{message.name} : identifiant hors des 11 bits du CAN 2.0A");'
        )
        if base in seen:
            continue
        seen.add(base)
        out.append(
            f"_Static_assert(BENCH_{base.upper()}_DLC <= BENCH_CLASSIC_MAX_DLC,"
            f' "{base} : DLC superieur a 8, impossible en CAN 2.0 classic");'
        )
    out.append("")
    return out


def _unique_layouts(profile: Profile) -> list[Message]:
    """Une seule structure par disposition de signaux.

    Les trames « per_node » (heartbeat) partagent la même disposition : on ne
    génère la structure qu'une fois, sous le nom de base.
    """
    seen: set[str] = set()
    result: list[Message] = []
    for message in profile.messages:
        base = (
            message.name if message.node_id is None else message.name.rsplit("_", 1)[0]
        )
        if base in seen:
            continue
        seen.add(base)
        result.append(message if message.node_id is None else _rename(message, base))
    return result


def _rename(message: Message, name: str) -> Message:
    clone = Message(
        name=name,
        can_id=message.can_id,
        dlc=message.dlc,
        sender=message.sender,
        receivers=message.receivers,
        kind=message.kind,
        comment=message.comment,
        signals=message.signals,
        period_ms=message.period_ms,
        contender=message.contender,
        node_id=None,
    )
    return clone


def _struct_for(message: Message) -> list[str]:
    out = [
        f"/* --- {message.name} (DLC {message.dlc}) ------------------------------ */",
        "",
    ]
    if message.comment:
        out += ["/**", f" * {message.comment}", " */"]

    if not message.signals:
        out += [
            f"/* {message.name} ne transporte aucun signal : {message.dlc} octets nuls. */",
            f"#define BENCH_{message.name.upper()}_DLC {message.dlc}u",
            "",
        ]
        return out

    out.append("typedef struct {")
    for signal in message.signals:
        out.append(f"    {signal.c_phys_type} {signal.name};")
        out.append(_doc(signal))
    out.append(f"}} {message.struct_name};")
    out += [
        "",
        f"#define BENCH_{message.name.upper()}_DLC {message.dlc}u",
        "",
        f"/** @brief Encode {message.name} dans @p data ({message.dlc} octets). */",
        f"void bench_{message.c_name}_pack(uint8_t *data, const {message.struct_name} *src);",
        "",
        f"/** @brief Décode {message.name} depuis @p data ({message.dlc} octets). */",
        f"void bench_{message.c_name}_unpack({message.struct_name} *dst, const uint8_t *data);",
        "",
    ]
    return out


# ---------------------------------------------------------------------------
#  Source
# ---------------------------------------------------------------------------


def generate_source(icd: Icd) -> str:
    out: list[str] = [
        BANNER,
        "",
        '#include "icd_gen.h"',
        "",
        "#include <math.h>",
        "#include <string.h>",
        "",
    ]

    # N'émettre que les fonctions réellement utilisées : une aide inutilisée
    # déclencherait -Wunused-function, et le projet compile sans avertissement.
    layouts = [m for m in _unique_layouts(icd.default) if m.signals]
    all_signals = [s for m in layouts for s in m.signals]
    needs = {
        "le": any(s.byte_order == "little_endian" for s in all_signals),
        "be": any(s.byte_order == "big_endian" for s in all_signals),
        "sign_extend": any(s.signed for s in all_signals),
        "clamp": bool(all_signals),
    }
    out += _helpers(needs)

    for profile in icd.profiles.values():
        prefix = f"bench_{profile.name}"
        upper = profile.name.upper()
        out.append(
            f"const bench_reserved_range_t {prefix}_reserved_ranges"
            f"[BENCH_{upper}_RESERVED_COUNT] = {{"
        )
        for reserved in profile.reserved_ranges:
            out.append(
                f"    {{ 0x{reserved.first:03X}u, 0x{reserved.last:03X}u, "
                f'"{reserved.purpose}" }},'
            )
        out += ["};", ""]

        out.append(
            f"const bench_frame_info_t {prefix}_frames[BENCH_{upper}_FRAME_COUNT] = {{"
        )
        for message in profile.messages:
            out.append(
                f"    {{ 0x{message.can_id:03X}u, {message.dlc}u, "
                f"{'true' if message.kind == 'service' else 'false'}, "
                f'{"true" if message.contender else "false"}, "{message.name}" }},'
            )
        out += ["};", ""]

    default = icd.default
    upper = default.name.upper()
    out += [
        "bool bench_id_is_reserved(uint16_t can_id) {",
        f"    for (size_t i = 0u; i < BENCH_{upper}_RESERVED_COUNT; i++) {{",
        f"        if (can_id >= bench_{default.name}_reserved_ranges[i].first &&",
        f"            can_id <= bench_{default.name}_reserved_ranges[i].last) {{",
        "            return true;",
        "        }",
        "    }",
        "    return false;",
        "}",
        "",
        "const bench_frame_info_t *bench_frame_by_id(uint16_t can_id) {",
        f"    for (size_t i = 0u; i < BENCH_{upper}_FRAME_COUNT; i++) {{",
        f"        if (bench_{default.name}_frames[i].can_id == can_id) {{",
        f"            return &bench_{default.name}_frames[i];",
        "        }",
        "    }",
        "    return NULL;",
        "}",
        "",
    ]

    for message in _unique_layouts(default):
        if message.signals:
            out += _pack_for(message)
            out += _unpack_for(message)

    return "\n".join(out)


def _helpers(needs: dict[str, bool]) -> list[str]:
    out = [
        "/* ---------------------------------------------------------------------",
        " *  Accès aux champs de bits",
        " *",
        " *  Little-endian (Intel) : le bit de départ est le poids faible du signal,",
        " *  les bits occupent les positions croissantes.",
        " *  Big-endian (Motorola) : le bit de départ est le poids fort, on descend",
        " *  dans l'octet puis on poursuit au bit 7 de l'octet suivant.",
        " *",
        "*  Seules les aides utilisées par l'ICD courant sont générées.",
        " * ------------------------------------------------------------------- */",
        "",
    ]
    if needs["le"]:
        out += _helpers_le()
    if needs["be"]:
        out += _helpers_be()
    if needs["sign_extend"]:
        out += [
            "/** Extension de signe d'un champ de @p length bits. */",
            "static int64_t bench_sign_extend(uint64_t raw, unsigned length) {",
            "    const uint64_t sign_bit = (uint64_t)1u << (length - 1u);",
            "    if ((raw & sign_bit) != 0u) {",
            "        return (int64_t)(raw | ~(((uint64_t)1u << length) - 1u));",
            "    }",
            "    return (int64_t)raw;",
            "}",
            "",
        ]
    if needs["clamp"]:
        out += [
            "/** Saturation d'une valeur brute sur les bornes du champ. */",
            "static int64_t bench_clamp(int64_t value, int64_t low, int64_t high) {",
            "    if (value < low) {",
            "        return low;",
            "    }",
            "    if (value > high) {",
            "        return high;",
            "    }",
            "    return value;",
            "}",
            "",
        ]
    return out


def _helpers_le() -> list[str]:
    return [
        "static uint64_t bench_load_le(const uint8_t *data, size_t dlc) {",
        "    uint64_t frame = 0u;",
        "    for (size_t i = 0u; i < dlc; i++) {",
        "        frame |= (uint64_t)data[i] << (8u * i);",
        "    }",
        "    return frame;",
        "}",
        "",
        "static void bench_store_le(uint8_t *data, size_t dlc, uint64_t frame) {",
        "    for (size_t i = 0u; i < dlc; i++) {",
        "        data[i] = (uint8_t)((frame >> (8u * i)) & 0xFFu);",
        "    }",
        "}",
        "",
    ]


def _helpers_be() -> list[str]:
    return [
        "static uint64_t bench_load_be(const uint8_t *data, size_t dlc) {",
        "    uint64_t frame = 0u;",
        "    for (size_t i = 0u; i < dlc; i++) {",
        "        frame |= (uint64_t)data[i] << (8u * (dlc - 1u - i));",
        "    }",
        "    return frame;",
        "}",
        "",
        "static void bench_store_be(uint8_t *data, size_t dlc, uint64_t frame) {",
        "    for (size_t i = 0u; i < dlc; i++) {",
        "        data[i] = (uint8_t)((frame >> (8u * (dlc - 1u - i))) & 0xFFu);",
        "    }",
        "}",
        "",
    ]


def _shift_expr(signal: Signal, dlc: int) -> tuple[str, int]:
    """Renvoie (suffixe le/be, décalage) pour ce signal."""
    if signal.byte_order == "little_endian":
        return "le", signal.start_position
    msb_index = signal.start_byte * 8 + (7 - signal.start_bit)
    return "be", dlc * 8 - (msb_index + signal.length)


def _pack_for(message: Message) -> list[str]:
    out = [
        f"void bench_{message.c_name}_pack(uint8_t *data, const {message.struct_name} *src) {{",
        "    uint64_t frame_le = 0u;",
        "    uint64_t frame_be = 0u;",
        f"    memset(data, 0, {message.dlc}u);",
        "",
    ]
    uses_le = any(s.byte_order == "little_endian" for s in message.signals)
    uses_be = any(s.byte_order == "big_endian" for s in message.signals)

    for signal in message.signals:
        order, shift = _shift_expr(signal, message.dlc)
        mask = (1 << signal.length) - 1
        if signal.factor != 1.0 or signal.offset != 0.0:
            # llround arrondit à l'opposé de zéro, comme bench_round() côté Python.
            expr = (
                f"(int64_t)llround(((double)src->{signal.name} - "
                f"({signal.offset:.17g})) / ({signal.factor:.17g}))"
            )
        else:
            expr = f"(int64_t)src->{signal.name}"

        out += [
            f"    /* {signal.name} */",
            "    {",
            (
                f"        int64_t raw = bench_clamp({expr}, "
                f"INT64_C({signal.raw_minimum}), INT64_C({signal.raw_maximum}));"
            ),
            f"        frame_{order} |= ((uint64_t)raw & UINT64_C(0x{mask:X})) << {shift}u;",
            "    }",
        ]

    out.append("")
    if uses_le and uses_be:
        out += [
            f"    bench_store_le(data, {message.dlc}u, frame_le);",
            "    {",
            f"        uint8_t tmp[{message.dlc}u];",
            f"        bench_store_be(tmp, {message.dlc}u, frame_be);",
            f"        for (size_t i = 0u; i < {message.dlc}u; i++) {{",
            "            data[i] |= tmp[i];",
            "        }",
            "    }",
        ]
    elif uses_be:
        out.append(f"    bench_store_be(data, {message.dlc}u, frame_be);")
        out.append("    (void)frame_le;")
    else:
        out.append(f"    bench_store_le(data, {message.dlc}u, frame_le);")
        out.append("    (void)frame_be;")
    out += ["}", ""]
    return out


def _unpack_for(message: Message) -> list[str]:
    uses_le = any(s.byte_order == "little_endian" for s in message.signals)
    uses_be = any(s.byte_order == "big_endian" for s in message.signals)

    out = [
        f"void bench_{message.c_name}_unpack({message.struct_name} *dst, const uint8_t *data) {{",
    ]
    if uses_le:
        out.append(
            f"    const uint64_t frame_le = bench_load_le(data, {message.dlc}u);"
        )
    if uses_be:
        out.append(
            f"    const uint64_t frame_be = bench_load_be(data, {message.dlc}u);"
        )
    out.append("")

    for signal in message.signals:
        order, shift = _shift_expr(signal, message.dlc)
        mask = (1 << signal.length) - 1
        out += [
            f"    /* {signal.name} */",
            "    {",
            f"        uint64_t raw = (frame_{order} >> {shift}u) & UINT64_C(0x{mask:X});",
        ]
        value = (
            f"bench_sign_extend(raw, {signal.length}u)"
            if signal.signed
            else "(int64_t)raw"
        )
        if signal.factor != 1.0 or signal.offset != 0.0:
            out.append(
                f"        dst->{signal.name} = ({signal.c_phys_type})((double)({value}) * "
                f"{signal.factor:.17g} + {signal.offset:.17g});"
            )
        else:
            out.append(f"        dst->{signal.name} = ({signal.c_phys_type})({value});")
        out.append("    }")
    out += ["}", ""]
    return out
