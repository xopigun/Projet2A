"""Génération du module Python ``pc/canbench/icd_gen.py``.

Le module produit est autonome : il ne dépend ni de ``tools.codegen`` ni de
``pyyaml``, pour que ``canbench`` reste installable sans le générateur.
"""

from __future__ import annotations

from .model import Icd, Message, Signal

BANNER = '''\
"""FICHIER GÉNÉRÉ — NE PAS ÉDITER À LA MAIN.

Produit par tools/codegen à partir de icd/bench_icd.yaml.
Toute modification manuelle sera écrasée, et la CI la rejettera.

Regénérer :  python -m tools.codegen
"""
'''

PREAMBLE = '''
from __future__ import annotations

import math
from dataclasses import dataclass, field


def bench_round(value: float) -> int:
    """Arrondit à l'entier le plus proche, les demis s'éloignant de zéro.

    Convention imposée par ``llround()`` dans le code C généré : ``round()`` de
    Python arrondit au pair et casserait la parité C <-> Python.
    """
    return int(math.floor(value + 0.5)) if value >= 0 else int(math.ceil(value - 0.5))


def _sign_extend(raw: int, length: int) -> int:
    return raw - (1 << length) if raw >= (1 << (length - 1)) else raw


def _clamp(value: int, low: int, high: int) -> int:
    return low if value < low else high if value > high else value
'''


def _pack_body(message: Message) -> list[str]:
    lines = [f"        frame_le = 0", f"        frame_be = 0"]
    for signal in message.signals:
        mask = (1 << signal.length) - 1
        if signal.factor != 1.0 or signal.offset != 0.0:
            raw = (f"bench_round((float(self.{signal.name}) - "
                   f"({signal.offset!r})) / ({signal.factor!r}))")
        else:
            raw = f"int(self.{signal.name})"
        if signal.byte_order == "little_endian":
            shift = signal.start_position
            target = "frame_le"
        else:
            msb = signal.start_byte * 8 + (7 - signal.start_bit)
            shift = message.dlc * 8 - (msb + signal.length)
            target = "frame_be"
        lines += [
            f"        raw = _clamp({raw}, {signal.raw_minimum}, {signal.raw_maximum})",
            f"        {target} |= (raw & 0x{mask:X}) << {shift}",
        ]
    lines += [
        f"        data = bytearray(frame_le.to_bytes({message.dlc}, 'little'))",
        f"        if frame_be:",
        f"            be = frame_be.to_bytes({message.dlc}, 'big')",
        f"            data = bytearray(a | b for a, b in zip(data, be))",
        "        return bytes(data)",
    ]
    return lines


def _unpack_body(message: Message) -> list[str]:
    lines = [
        f"        if len(data) != {message.dlc}:",
        f"            raise ValueError("
        f"f'{message.name} : {{len(data)}} octets reçus, {message.dlc} attendus')",
        "        frame_le = int.from_bytes(data, 'little')",
        "        frame_be = int.from_bytes(data, 'big')",
        "        return cls(",
    ]
    for signal in message.signals:
        mask = (1 << signal.length) - 1
        if signal.byte_order == "little_endian":
            expr = f"(frame_le >> {signal.start_position}) & 0x{mask:X}"
        else:
            msb = signal.start_byte * 8 + (7 - signal.start_bit)
            shift = message.dlc * 8 - (msb + signal.length)
            expr = f"(frame_be >> {shift}) & 0x{mask:X}"
        if signal.signed:
            expr = f"_sign_extend({expr}, {signal.length})"
        if signal.factor != 1.0 or signal.offset != 0.0:
            expr = f"({expr}) * {signal.factor!r} + {signal.offset!r}"
        lines.append(f"            {signal.name}={expr},")
    lines.append("        )")
    return lines


def _signal_meta(signal: Signal) -> str:
    return (
        f"    {{'name': {signal.name!r}, 'start_byte': {signal.start_byte}, "
        f"'start_bit': {signal.start_bit}, 'length': {signal.length}, "
        f"'byte_order': {signal.byte_order!r}, 'signed': {signal.signed}, "
        f"'factor': {signal.factor!r}, 'offset': {signal.offset!r}, "
        f"'unit': {signal.unit!r}, 'min': {signal.minimum!r}, "
        f"'max': {signal.maximum!r}, 'default': {signal.default!r}}},"
    )


def generate(icd: Icd) -> str:
    out = [BANNER, PREAMBLE, ""]

    out += [
        f"BITRATE = {icd.bus['bitrate']}",
        f"DEFAULT_PROFILE = {icd.default_profile!r}",
        "",
        "#: Identifiants par profil réseau : PROFILES[<profil>]['ids'][<trame>].",
        "PROFILES = {",
    ]
    for profile in icd.profiles.values():
        out.append(f"    {profile.name!r}: {{")
        out.append(f"        'description': {profile.description!r},")
        out.append(f"        'heartbeat_base': 0x{profile.heartbeat_base:03X},")
        out.append("        'ids': {")
        for message in profile.messages:
            out.append(f"            {message.name!r}: 0x{message.can_id:03X},")
        out.append("        },")
        out.append("        'reserved_ranges': [")
        for reserved in profile.reserved_ranges:
            out.append(
                f"            (0x{reserved.first:03X}, 0x{reserved.last:03X}, "
                f"{reserved.purpose!r}),"
            )
        out.append("        ],")
        out.append("    },")
    out += ["}", ""]

    default = icd.default
    out += ["#: Raccourcis vers le profil par défaut.", "IDS = PROFILES[DEFAULT_PROFILE]['ids']", ""]

    out += ["#: Description des nœuds déclarés dans l'ICD.", "NODES = ["]
    for node in icd.nodes:
        out.append(
            f"    {{'node_id': {node.node_id}, 'name': {node.name!r}, "
            f"'board': {node.board!r}, 'role': {node.role!r}, "
            f"'contender': {node.contender}}},"
        )
    out += ["]", ""]

    out += ["#: Trames contendantes du test d'arbitrage, par priorité croissante d'identifiant.",
            "CONTENDERS = ["]
    for message in sorted(default.contenders, key=lambda m: m.can_id):
        out.append(
            f"    {{'name': {message.name!r}, 'can_id': 0x{message.can_id:03X}, "
            f"'sender': {message.sender!r}}},"
        )
    out += ["]", ""]

    out += ["#: Métadonnées de chaque trame, utilisées par le décodage générique.", "FRAMES = {"]
    seen: set[str] = set()
    for message in default.messages:
        base = message.name if message.node_id is None else message.name.rsplit("_", 1)[0]
        out.append(f"    0x{message.can_id:03X}: {{")
        out.append(f"        'name': {message.name!r},")
        out.append(f"        'layout': {base!r},")
        out.append(f"        'dlc': {message.dlc},")
        out.append(f"        'kind': {message.kind!r},")
        out.append(f"        'sender': {message.sender!r},")
        out.append(f"        'period_ms': {message.period_ms!r},")
        out.append(f"        'contender': {message.contender},")
        out.append("        'signals': [")
        for signal in message.signals:
            out.append("    " + _signal_meta(signal))
        out.append("        ],")
        out.append("    },")
        seen.add(base)
    out += ["}", ""]

    # --- séquences déterministes des simulateurs --------------------------
    out += ["#: Séquences déterministes des simulateurs de capteurs.", "SIMULATIONS = {"]
    for name, simulation in icd.simulations.items():
        out.append(f"    {name!r}: {{")
        out.append(f"        'period_ms': {simulation.get('period_ms')!r},")
        out.append("        'steps': [")
        for step in simulation.get("steps") or []:
            out.append(f"            {dict(step)!r},")
        out.append("        ],")
        out.append("    },")
    out += ["}", ""]

    # --- classes de trames -------------------------------------------------
    emitted: set[str] = set()
    for message in default.messages:
        base = message.name if message.node_id is None else message.name.rsplit("_", 1)[0]
        if base in emitted or not message.signals:
            emitted.add(base)
            continue
        emitted.add(base)

        out += ["", "@dataclass", f"class {_class_name(base)}:"]
        if message.comment:
            out += ['    """' + message.comment + '"""', ""]
        out.append(f"    DLC = {message.dlc}")
        out.append("")
        for signal in message.signals:
            annotation = "float" if signal.is_float else "int"
            out.append(f"    {signal.name}: {annotation} = {signal.default!r}")
        out += ["", "    def pack(self) -> bytes:"]
        out += _pack_body(message)
        out += ["", "    @classmethod", "    def unpack(cls, data: bytes):"]
        out += _unpack_body(message)

    # --- table de correspondance -------------------------------------------
    out += ["", "", "#: Classe de décodage associée à chaque disposition de trame.", "LAYOUTS = {"]
    for base in sorted(emitted):
        layout_message = next(
            (m for m in default.messages
             if (m.name if m.node_id is None else m.name.rsplit("_", 1)[0]) == base),
            None,
        )
        if layout_message is not None and layout_message.signals:
            out.append(f"    {base!r}: {_class_name(base)},")
    out += ["}", ""]

    return "\n".join(out)


def _class_name(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))
