"""Génération du fichier DBC, pour SavvyCAN et cantools.

Le DBC sert à deux choses : ouvrir les enregistrements dans SavvyCAN, et donner
une troisième implémentation indépendante de l'encodage (celle de cantools), que
les tests utilisent pour contrôler la nôtre.

Conventions DBC utilisées :
  - ``@1`` little-endian (Intel), ``@0`` big-endian (Motorola) ;
  - ``+`` non signé, ``-`` signé ;
  - le bit de départ est le bit de poids faible en Intel, de poids fort en Motorola,
    ce qui correspond exactement à la convention de l'ICD.
"""

from __future__ import annotations

from .model import Icd, Message


def _senders(icd: Icd) -> list[str]:
    names = {node.name for node in icd.nodes}
    names.add("PC")
    return sorted(names)


def _sender_of(message: Message, known: list[str]) -> str:
    return message.sender if message.sender in known else "Vector__XXX"


def _receivers_of(message: Message, known: list[str]) -> str:
    receivers = [r for r in message.receivers if r in known]
    return ",".join(receivers) if receivers else "Vector__XXX"


def generate(icd: Icd) -> str:
    known = _senders(icd)
    profile = icd.default

    out = [
        'VERSION ""',
        "",
        "",
        "NS_ :",
        "\tCM_",
        "\tBA_DEF_",
        "\tBA_",
        "\tVAL_",
        "\tBA_DEF_DEF_",
        "",
        "BS_:",
        "",
        "BU_: " + " ".join(known),
        "",
    ]

    for message in profile.messages:
        out.append(
            f"BO_ {message.can_id} {message.name}: {message.dlc} "
            f"{_sender_of(message, known)}"
        )
        for signal in message.signals:
            order = "1" if signal.byte_order == "little_endian" else "0"
            sign = "-" if signal.signed else "+"
            out.append(
                f' SG_ {signal.name} : {signal.start_position}|{signal.length}@{order}{sign}'
                f' ({signal.factor:g},{signal.offset:g})'
                f' [{signal.minimum:g}|{signal.maximum:g}]'
                f' "{signal.unit}" {_receivers_of(message, known)}'
            )
        out.append("")

    # --- commentaires ------------------------------------------------------
    for message in profile.messages:
        if message.comment:
            out.append(f'CM_ BO_ {message.can_id} "{_escape(message.comment)}";')
        for signal in message.signals:
            if signal.comment:
                out.append(
                    f'CM_ SG_ {message.can_id} {signal.name} "{_escape(signal.comment)}";'
                )

    # --- périodes d'émission ----------------------------------------------
    out += [
        "",
        'BA_DEF_ BO_  "GenMsgCycleTime" INT 0 65535;',
        'BA_DEF_DEF_  "GenMsgCycleTime" 0;',
    ]
    for message in profile.messages:
        if message.period_ms:
            out.append(f'BA_ "GenMsgCycleTime" BO_ {message.can_id} {message.period_ms};')

    out.append("")
    return "\n".join(out)


def _escape(text: str) -> str:
    return text.replace('"', "'")
