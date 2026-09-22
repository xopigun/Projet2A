"""Modèle de l'ICD : chargement, résolution des profils réseau et validations.

Ce module est la référence d'encodage du projet. Le code C généré et le module
Python généré doivent lui être strictement équivalents, ce que vérifient les
vecteurs de référence produits par ``vectors.py``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ICD_PATH = REPO_ROOT / "icd" / "bench_icd.yaml"

C_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: Identifiants prédéfinis de CiA 301 (CANopen), utilisés pour avertir l'utilisateur
#: lorsqu'un identifiant de service risque d'entrer en collision chez un partenaire.
CANOPEN_RANGES: list[tuple[int, int, str]] = [
    (0x000, 0x000, "NMT"),
    (0x080, 0x080, "SYNC"),
    (0x081, 0x0FF, "EMCY"),
    (0x100, 0x100, "TIME"),
    (0x181, 0x57F, "PDO"),
    (0x581, 0x67F, "SDO"),
    (0x701, 0x77F, "NMT error control (heartbeat CANopen)"),
    (0x7E4, 0x7E5, "LSS"),
]


class IcdError(Exception):
    """Erreur bloquante détectée dans l'ICD."""


def bench_round(value: float) -> int:
    """Arrondit à l'entier le plus proche, les demis s'éloignant de zéro.

    C'est la convention d'arrondi du projet. Elle est imposée par ``llround()``,
    utilisé dans le code C généré ; la fonction ``round()`` de Python arrondit au
    pair le plus proche et donnerait des résultats différents sur les valeurs
    exactement à un demi, ce qui casserait la parité C <-> Python.
    """
    return int(math.floor(value + 0.5)) if value >= 0 else int(math.ceil(value - 0.5))


def canopen_conflict(can_id: int) -> str | None:
    """Renvoie le nom du service CANopen occupant ``can_id``, ou ``None``."""
    for first, last, name in CANOPEN_RANGES:
        if first <= can_id <= last:
            return name
    return None


# ---------------------------------------------------------------------------
#  Signaux
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Signal:
    name: str
    start_byte: int
    start_bit: int
    length: int
    byte_order: str
    signed: bool
    factor: float
    offset: float
    unit: str
    minimum: float
    maximum: float
    default: float
    comment: str

    # -- position ----------------------------------------------------------

    @property
    def start_position(self) -> int:
        """Position du bit de départ, en numérotation « octet × 8 + bit »."""
        return self.start_byte * 8 + self.start_bit

    def occupied_positions(self) -> set[int]:
        """Ensemble des positions de bits occupées, en numérotation little-endian.

        Pour un signal big-endian, les positions sont converties dans le même
        repère afin que la détection de chevauchement soit comparable entre
        signaux d'ordres d'octets différents.
        """
        if self.byte_order == "little_endian":
            return set(range(self.start_position, self.start_position + self.length))

        # Motorola : le bit de départ est le MSB, on descend dans l'octet puis on
        # poursuit au bit 7 de l'octet suivant.
        positions: set[int] = set()
        byte_index, bit_index = self.start_byte, self.start_bit
        for _ in range(self.length):
            positions.add(byte_index * 8 + bit_index)
            if bit_index == 0:
                byte_index += 1
                bit_index = 7
            else:
                bit_index -= 1
        return positions

    # -- bornes du champ brut ---------------------------------------------

    @property
    def raw_minimum(self) -> int:
        return -(1 << (self.length - 1)) if self.signed else 0

    @property
    def raw_maximum(self) -> int:
        return (1 << (self.length - 1)) - 1 if self.signed else (1 << self.length) - 1

    @property
    def is_float(self) -> bool:
        """Vrai si la valeur physique n'est pas entière (facteur ou offset non entiers)."""
        return not (float(self.factor).is_integer() and float(self.offset).is_integer())

    @property
    def c_raw_type(self) -> str:
        bits = 8 if self.length <= 8 else 16 if self.length <= 16 else 32 if self.length <= 32 else 64
        return f"{'int' if self.signed else 'uint'}{bits}_t"

    @property
    def c_phys_type(self) -> str:
        return "float" if self.is_float else self.c_raw_type

    # -- conversions -------------------------------------------------------

    def encode(self, physical: float) -> int:
        """Valeur physique -> champ brut, avec saturation sur les bornes du champ."""
        raw = bench_round((physical - self.offset) / self.factor)
        return max(self.raw_minimum, min(self.raw_maximum, raw))

    def decode(self, raw: int) -> float:
        """Champ brut -> valeur physique."""
        return raw * self.factor + self.offset

    def is_exactly_representable(self, physical: float) -> bool:
        """Vrai si ``physical`` se retrouve à l'identique après un aller-retour."""
        raw = bench_round((physical - self.offset) / self.factor)
        if not (self.raw_minimum <= raw <= self.raw_maximum):
            return False
        return abs(self.decode(raw) - physical) <= 1e-9 * max(1.0, abs(physical))


# ---------------------------------------------------------------------------
#  Messages
# ---------------------------------------------------------------------------


@dataclass
class Message:
    name: str
    can_id: int
    dlc: int
    sender: str
    receivers: list[str]
    kind: str
    comment: str
    signals: list[Signal]
    period_ms: int | None = None
    contender: bool = False
    node_id: int | None = None  # renseigné pour les trames « per_node »

    @property
    def c_name(self) -> str:
        return self.name.lower()

    @property
    def struct_name(self) -> str:
        return f"bench_{self.c_name}_t"


@dataclass
class Node:
    node_id: int
    name: str
    board: str
    role: str
    contender: bool


@dataclass
class ReservedRange:
    first: int
    last: int
    purpose: str

    def contains(self, can_id: int) -> bool:
        return self.first <= can_id <= self.last


@dataclass
class Profile:
    """Un profil réseau résolu : les identifiants y sont des entiers."""

    name: str
    description: str
    services: dict[str, int]
    heartbeat_base: int
    reserved_ranges: list[ReservedRange]
    messages: list[Message] = field(default_factory=list)

    @property
    def contenders(self) -> list[Message]:
        return [m for m in self.messages if m.contender]

    def by_name(self, name: str) -> Message:
        for message in self.messages:
            if message.name == name:
                return message
        raise KeyError(name)


@dataclass
class Icd:
    bus: dict
    nodes: list[Node]
    profiles: dict[str, Profile]
    default_profile: str
    simulations: dict[str, dict]
    warnings: list[str] = field(default_factory=list)

    @property
    def default(self) -> Profile:
        return self.profiles[self.default_profile]


# ---------------------------------------------------------------------------
#  Chargement
# ---------------------------------------------------------------------------


def _signal_from_dict(raw: dict, message_name: str) -> Signal:
    missing = {"name", "start_byte", "start_bit", "length"} - raw.keys()
    if missing:
        raise IcdError(f"{message_name}: signal incomplet, champs manquants {sorted(missing)}")
    return Signal(
        name=raw["name"],
        start_byte=int(raw["start_byte"]),
        start_bit=int(raw["start_bit"]),
        length=int(raw["length"]),
        byte_order=raw.get("byte_order", "little_endian"),
        signed=bool(raw.get("signed", False)),
        factor=float(raw.get("factor", 1.0)),
        offset=float(raw.get("offset", 0.0)),
        unit=raw.get("unit", "") or "",
        minimum=float(raw.get("min", 0.0)),
        maximum=float(raw.get("max", 0.0)),
        default=float(raw.get("default", 0.0)),
        comment=" ".join((raw.get("comment") or "").split()),
    )


def _build_messages(spec: dict, profile_name: str, profile_spec: dict, nodes: list[Node]) -> list[Message]:
    services: dict[str, int] = {k: int(v) for k, v in profile_spec["services"].items()}
    heartbeat_base = int(profile_spec["heartbeat_base"])

    messages: list[Message] = []
    for raw in spec["messages"]:
        name = raw["name"]
        signals = [_signal_from_dict(s, name) for s in (raw.get("signals") or [])]
        common = dict(
            dlc=int(raw["dlc"]),
            sender=raw.get("sender", ""),
            receivers=list(raw.get("receivers") or []),
            kind=raw.get("kind", "application"),
            comment=" ".join((raw.get("comment") or "").split()),
            signals=signals,
            period_ms=raw.get("period_ms"),
            contender=bool(raw.get("contender", False)),
        )

        if raw.get("per_node"):
            for node in nodes:
                messages.append(
                    Message(name=f"{name}_{node.name}", can_id=heartbeat_base + node.node_id,
                            node_id=node.node_id, **common)
                )
        elif "id_ref" in raw:
            ref = raw["id_ref"]
            if ref not in services:
                raise IcdError(
                    f"{name}: id_ref « {ref} » introuvable dans les services du profil "
                    f"« {profile_name} » ({sorted(services)})"
                )
            messages.append(Message(name=name, can_id=services[ref], **common))
        elif "id" in raw:
            messages.append(Message(name=name, can_id=int(raw["id"]), **common))
        else:
            raise IcdError(f"{name}: il faut un « id » littéral ou un « id_ref »")
    return messages


def load(path: Path | None = None) -> Icd:
    """Charge l'ICD, résout chaque profil et lance toutes les validations."""
    path = path or ICD_PATH
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))

    nodes = [
        Node(node_id=int(n["node_id"]), name=n["name"], board=n["board"],
             role=n["role"], contender=bool(n.get("contender", False)))
        for n in spec["nodes"]
    ]

    profiles: dict[str, Profile] = {}
    for profile_name, profile_spec in spec["profiles"].items():
        profiles[profile_name] = Profile(
            name=profile_name,
            description=" ".join((profile_spec.get("description") or "").split()),
            services={k: int(v) for k, v in profile_spec["services"].items()},
            heartbeat_base=int(profile_spec["heartbeat_base"]),
            reserved_ranges=[
                ReservedRange(int(r["first"]), int(r["last"]), r.get("purpose", ""))
                for r in (profile_spec.get("reserved_ranges") or [])
            ],
            messages=_build_messages(spec, profile_name, profile_spec, nodes),
        )

    icd = Icd(
        bus=spec["bus"],
        nodes=nodes,
        profiles=profiles,
        default_profile=spec["default_profile"],
        simulations=spec.get("simulations") or {},
    )
    validate(icd)
    return icd


# ---------------------------------------------------------------------------
#  Validations
# ---------------------------------------------------------------------------


def validate(icd: Icd) -> None:
    """Lève ``IcdError`` au premier lot d'erreurs trouvé ; remplit ``icd.warnings``."""
    errors: list[str] = []
    warnings: list[str] = []

    id_bits = int(icd.bus.get("id_bits", 11))
    id_max = (1 << id_bits) - 1

    if icd.default_profile not in icd.profiles:
        errors.append(f"default_profile « {icd.default_profile} » introuvable")

    for profile in icd.profiles.values():
        _validate_profile(profile, id_max, errors, warnings)

    for message_name, simulation in icd.simulations.items():
        _validate_simulation(icd, message_name, simulation, errors)

    if errors:
        raise IcdError(
            "ICD invalide :\n" + "\n".join(f"  - {e}" for e in errors)
        )
    icd.warnings = warnings


def _validate_profile(profile: Profile, id_max: int, errors: list[str], warnings: list[str]) -> None:
    where = f"profil « {profile.name} »"

    # --- collisions d'identifiants ----------------------------------------
    seen: dict[int, str] = {}
    for message in profile.messages:
        if not 0 <= message.can_id <= id_max:
            errors.append(f"{where} : {message.name} a l'identifiant 0x{message.can_id:X} "
                          f"hors de la plage 11 bits")
        if message.can_id in seen:
            errors.append(f"{where} : collision d'identifiant 0x{message.can_id:03X} entre "
                          f"{seen[message.can_id]} et {message.name}")
        seen[message.can_id] = message.name

    # --- cohérence avec les plages réservées ------------------------------
    for message in profile.messages:
        inside = any(r.contains(message.can_id) for r in profile.reserved_ranges)
        if message.kind == "service" and not inside:
            errors.append(f"{where} : {message.name} (0x{message.can_id:03X}) est un service "
                          f"mais tombe hors des plages réservées déclarées")
        if message.kind != "service" and inside:
            errors.append(f"{where} : {message.name} (0x{message.can_id:03X}) est applicatif "
                          f"mais tombe dans une plage réservée au banc")

    # --- contrainte d'ordre ARM/GO ----------------------------------------
    contenders = profile.contenders
    if not contenders:
        errors.append(f"{where} : aucune trame contendante, le test d'arbitrage est impossible")
    else:
        lowest = min(m.can_id for m in contenders)
        lowest_name = next(m.name for m in contenders if m.can_id == lowest)
        for service in ("GO", "ARM"):
            try:
                service_id = profile.services[service]
            except KeyError:
                errors.append(f"{where} : service « {service} » manquant")
                continue
            if service_id >= lowest:
                errors.append(
                    f"{where} : {service} (0x{service_id:03X}) doit avoir un identifiant "
                    f"strictement inférieur à celui de tous les contendants "
                    f"(le plus prioritaire est {lowest_name} à 0x{lowest:03X}). "
                    f"Sans cela le départ simultané de l'arbitrage n'est plus garanti."
                )
        if len({m.can_id for m in contenders}) != len(contenders):
            errors.append(f"{where} : deux contendants partagent le même identifiant")

    # --- avertissements CANopen -------------------------------------------
    for message in profile.messages:
        conflict = canopen_conflict(message.can_id)
        if not conflict:
            continue
        if message.kind == "service":
            warnings.append(
                f"{where} : le service {message.name} (0x{message.can_id:03X}) entre en conflit "
                f"avec « {conflict} » en CANopen. Un partenaire utilisant CANopen devra définir "
                f"son propre profil réseau."
            )
        else:
            warnings.append(
                f"{where} : la trame applicative {message.name} (0x{message.can_id:03X}) occupe "
                f"l'identifiant de « {conflict} » en CANopen. Sans conséquence sur le banc (ce "
                f"n'est qu'un vecteur de test), mais à ne pas reprendre tel quel dans un ICD "
                f"partenaire."
            )

    # --- signaux ----------------------------------------------------------
    for message in profile.messages:
        _validate_signals(profile, message, errors)


def _validate_signals(profile: Profile, message: Message, errors: list[str]) -> None:
    where = f"profil « {profile.name} », {message.name}"

    if not 0 <= message.dlc <= 8:
        errors.append(f"{where} : DLC {message.dlc} hors plage pour du CAN 2.0A")

    names: set[str] = set()
    occupied: dict[int, str] = {}

    for signal in message.signals:
        if not C_IDENTIFIER.match(signal.name):
            errors.append(f"{where} : « {signal.name} » n'est pas un identifiant C valide")
        if signal.name in names:
            errors.append(f"{where} : signal « {signal.name} » déclaré deux fois")
        names.add(signal.name)

        if signal.byte_order not in ("little_endian", "big_endian"):
            errors.append(f"{where}.{signal.name} : byte_order « {signal.byte_order} » inconnu")
            continue
        if not 1 <= signal.length <= 64:
            errors.append(f"{where}.{signal.name} : longueur {signal.length} hors plage 1..64")
            continue
        if not 0 <= signal.start_bit <= 7:
            errors.append(f"{where}.{signal.name} : start_bit {signal.start_bit} hors plage 0..7")
            continue
        if signal.factor == 0:
            errors.append(f"{where}.{signal.name} : facteur nul")
            continue

        positions = signal.occupied_positions()
        if max(positions) >= message.dlc * 8:
            errors.append(
                f"{where}.{signal.name} : déborde de la trame — occupe jusqu'au bit "
                f"{max(positions)} alors que le DLC {message.dlc} n'en offre que "
                f"{message.dlc * 8}"
            )
            continue

        for position in sorted(positions):
            if position in occupied:
                errors.append(
                    f"{where} : chevauchement au bit {position} (octet {position // 8}, "
                    f"bit {position % 8}) entre « {occupied[position]} » et « {signal.name} »"
                )
                break
            occupied[position] = signal.name

        # bornes physiques cohérentes avec la capacité du champ
        span_low = signal.decode(signal.raw_minimum)
        span_high = signal.decode(signal.raw_maximum)
        low, high = min(span_low, span_high), max(span_low, span_high)
        tolerance = abs(signal.factor) / 2
        if signal.minimum < low - tolerance or signal.maximum > high + tolerance:
            errors.append(
                f"{where}.{signal.name} : bornes [{signal.minimum}, {signal.maximum}] "
                f"hors de ce que {signal.length} bits permettent de coder "
                f"([{low}, {high}])"
            )
        if signal.minimum > signal.maximum:
            errors.append(f"{where}.{signal.name} : min > max")
        if not signal.is_exactly_representable(signal.default):
            errors.append(
                f"{where}.{signal.name} : la valeur par défaut {signal.default} n'est pas "
                f"exactement représentable avec le facteur {signal.factor}"
            )


def _validate_simulation(icd: Icd, message_name: str, simulation: dict, errors: list[str]) -> None:
    profile = icd.default
    try:
        message = profile.by_name(message_name)
    except KeyError:
        errors.append(f"simulations : trame « {message_name} » inconnue")
        return

    by_name = {s.name: s for s in message.signals}
    for index, step in enumerate(simulation.get("steps") or []):
        for signal_name, value in step.items():
            signal = by_name.get(signal_name)
            if signal is None:
                errors.append(
                    f"simulations.{message_name}[{index}] : signal « {signal_name} » "
                    f"absent de la trame"
                )
                continue
            if not signal.is_exactly_representable(float(value)):
                errors.append(
                    f"simulations.{message_name}[{index}].{signal_name} : la valeur {value} "
                    f"n'est pas exactement représentable avec le facteur {signal.factor} "
                    f"sur {signal.length} bits — le test d'encodage serait non reproductible"
                )
