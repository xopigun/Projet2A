"""Couche physique du CAN : trame bit par bit et constantes du transceiver.

Sert aux chronogrammes de l'interface graphique. Deux parties :

1. **La trame au niveau du bit**, construite selon ISO 11898-1 : champs d'une
   trame standard de données, CRC-15, bourrage de bits (*bit stuffing*), bit
   d'acquittement. Cette partie est exacte et testée.

2. **Les constantes électriques du TJA1051T/3**, relevées dans sa datasheet
   (NXP, Rev 02, Tables 6 et 7). Les chronogrammes s'en servent pour tracer
   CAN_H, CAN_L et RXD. Le modèle du câble (propagation, arrondi des fronts,
   réflexions, bruit) est en revanche **illustratif** : il montre les bons ordres
   de grandeur et les bons mécanismes, pas une mesure. Seul l'oscilloscope fait
   foi (tests T1 et T2).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from . import icd_gen

#: Polynôme générateur du CRC-15 CAN : x^15 + x^14 + x^10 + x^8 + x^7 + x^4 + x^3 + 1.
CRC15_POLY = 0x4599

#: Constantes du TJA1051T/3 (datasheet NXP Rev 02) : valeurs typiques, plages en commentaire.
TJA1051 = {
    "vcc": 5.0,
    "canh_dom": 3.5,  # 2,75 à 4,5 V (Table 6, VO(dom) CANH)
    "canl_dom": 1.5,  # 0,5 à 2,25 V (Table 6, VO(dom) CANL)
    "rec": 2.5,  # 0,5 × VCC, 2 à 3 V (Table 6, VO(rec))
    "vth_rx": 0.7,  # 0,5 à 0,9 V (Table 6, Vth(RX)dif)
    "vhys_rx": 0.12,  # 50 à 200 mV (Table 6, Vhys(RX)dif)
    "vth_min": 0.5,
    "vth_max": 0.9,
    "td_txd_dom_ns": 65,  # Table 7, td(TXD-busdom)
    "td_txd_rec_ns": 90,  # Table 7, td(TXD-busrec)
    "td_bus_rxd_dom_ns": 60,  # Table 7, td(busdom-RXD)
    "td_bus_rxd_rec_ns": 65,  # Table 7, td(busrec-RXD)
    "tpd_txd_rxd_max_ns": 250,  # Table 7, versions avec VIO
    "vio": 3.3,
}


@dataclass(frozen=True)
class Bit:
    """Un bit sur le bus : valeur logique (0 = dominant), champ, bit de bourrage."""

    value: int
    field: str
    stuff: bool = False
    #: Valeur émise par le transmetteur ; ne diffère de ``value`` que dans le
    #: créneau d'acquittement, où l'émetteur laisse récessif et le récepteur
    #: impose dominant.
    tx_value: int | None = None


def crc15(bits: list[int]) -> int:
    """CRC-15 CAN d'une suite de bits (ISO 11898-1, § 10.4.2.6)."""
    crc = 0
    for bit in bits:
        feedback = bit ^ ((crc >> 14) & 1)
        crc = (crc << 1) & 0x7FFF
        if feedback:
            crc ^= CRC15_POLY
    return crc


def _bits(value: int, width: int) -> list[int]:
    return [(value >> (width - 1 - i)) & 1 for i in range(width)]


def build_frame(can_id: int, data: bytes, *, acknowledged: bool = True) -> list[Bit]:
    """Trame standard de données, bit par bit, telle qu'elle circule sur le bus.

    Le bourrage s'applique du SOF à la fin du CRC : après cinq bits identiques,
    l'émetteur insère un bit de valeur opposée, lui-même compté dans la suite.
    """
    if not 0 <= can_id <= 0x7FF:
        raise ValueError("identifiant hors des 11 bits du CAN 2.0A")
    if len(data) > 8:
        raise ValueError("8 octets au plus en CAN 2.0")

    fields: list[tuple[str, list[int]]] = [
        ("SOF", [0]),
        ("ID", _bits(can_id, 11)),
        ("RTR", [0]),
        ("IDE", [0]),
        ("r0", [0]),
        ("DLC", _bits(len(data), 4)),
    ]
    if data:
        fields.append(("DATA", [b for byte in data for b in _bits(byte, 8)]))
    covered = [b for _, bits in fields for b in bits]
    fields.append(("CRC", _bits(crc15(covered), 15)))

    frame: list[Bit] = []
    run_value, run_length = None, 0
    for name, bits in fields:
        for value in bits:
            frame.append(Bit(value, name))
            if value == run_value:
                run_length += 1
            else:
                run_value, run_length = value, 1
            if run_length == 5:
                stuff = 1 - value
                frame.append(Bit(stuff, name, stuff=True))
                run_value, run_length = stuff, 1

    frame.append(Bit(1, "DEL CRC"))
    frame.append(Bit(0 if acknowledged else 1, "ACK", tx_value=1))
    frame.append(Bit(1, "DEL ACK"))
    frame.extend(Bit(1, "EOF") for _ in range(7))
    frame.extend(Bit(1, "IFS") for _ in range(3))
    return frame


def destuff(frame: list[Bit]) -> list[int]:
    """Bits utiles du SOF à la fin du CRC, bits de bourrage retirés."""
    return [b.value for b in frame if b.field not in _UNSTUFFED and not b.stuff]


_UNSTUFFED = {"DEL CRC", "ACK", "DEL ACK", "EOF", "IFS"}


def sample_payload(name: str) -> bytes:
    """Charge utile d'exemple d'une trame de l'ICD : première étape de sa séquence
    de simulation, ou des zéros si elle n'en a pas (ARM, GO)."""
    for meta in icd_gen.FRAMES.values():
        if meta["name"] != name:
            continue
        simulation = icd_gen.SIMULATIONS.get(meta["layout"])
        layout = icd_gen.LAYOUTS.get(meta["layout"])
        if simulation and layout and simulation.get("steps"):
            return layout(**dict(simulation["steps"][0])).pack()
        return bytes(meta["dlc"])
    raise KeyError(name)


def describe(name: str, profile: str = icd_gen.DEFAULT_PROFILE) -> dict:
    """Trame de l'ICD prête pour les chronogrammes de l'interface."""
    can_id = icd_gen.PROFILES[profile]["ids"][name]
    data = sample_payload(name)
    frame = build_frame(can_id, data)
    return {
        "name": name,
        "id": can_id,
        "data": data.hex(" ").upper(),
        "bits": [asdict(b) for b in frame],
        "stuff_bits": sum(b.stuff for b in frame),
        "bitrate": icd_gen.BITRATE,
        "tja1051": TJA1051,
    }
