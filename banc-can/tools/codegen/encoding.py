"""Implémentation de référence de l'encodage des signaux.

C'est ici que la convention d'encodage du banc est définie une fois pour toutes.
Le code C généré et le module Python généré doivent produire exactement les mêmes
octets ; les vecteurs de référence servent à le prouver des deux côtés.

Conventions retenues
--------------------

*Little-endian (Intel)* — ``start_byte``/``start_bit`` désignent le bit de **poids
faible** du signal. Les bits occupent les positions croissantes ``p, p+1, …`` dans
l'entier obtenu en lisant la trame octet 0 en premier, poids faible en premier.

*Big-endian (Motorola)* — ``start_byte``/``start_bit`` désignent le bit de **poids
fort** du signal. On descend dans l'octet courant (bit 7 vers bit 0) puis on
poursuit au bit 7 de l'octet suivant.
"""

from __future__ import annotations

from .model import Message, Signal


def _to_signed(raw: int, length: int) -> int:
    if raw >= (1 << (length - 1)):
        raw -= 1 << length
    return raw


def pack_signal(data: bytearray, signal: Signal, raw: int) -> None:
    """Écrit le champ brut ``raw`` dans ``data`` (modifié sur place)."""
    mask = (1 << signal.length) - 1
    value = raw & mask
    total_bits = len(data) * 8

    if signal.byte_order == "little_endian":
        frame = int.from_bytes(bytes(data), "little")
        frame &= ~(mask << signal.start_position)
        frame |= value << signal.start_position
        data[:] = frame.to_bytes(len(data), "little")
    else:
        msb_index = signal.start_byte * 8 + (7 - signal.start_bit)
        shift = total_bits - (msb_index + signal.length)
        if shift < 0:
            raise ValueError(f"{signal.name} : le signal déborde de la trame")
        frame = int.from_bytes(bytes(data), "big")
        frame &= ~(mask << shift)
        frame |= value << shift
        data[:] = frame.to_bytes(len(data), "big")


def unpack_signal(data: bytes, signal: Signal) -> int:
    """Lit le champ brut de ``signal`` dans ``data`` et applique le signe."""
    mask = (1 << signal.length) - 1
    total_bits = len(data) * 8

    if signal.byte_order == "little_endian":
        frame = int.from_bytes(data, "little")
        raw = (frame >> signal.start_position) & mask
    else:
        msb_index = signal.start_byte * 8 + (7 - signal.start_bit)
        shift = total_bits - (msb_index + signal.length)
        if shift < 0:
            raise ValueError(f"{signal.name} : le signal déborde de la trame")
        frame = int.from_bytes(data, "big")
        raw = (frame >> shift) & mask

    return _to_signed(raw, signal.length) if signal.signed else raw


def pack(message: Message, values: dict[str, float]) -> bytes:
    """Encode des valeurs physiques en une charge utile de ``message.dlc`` octets.

    Les signaux absents de ``values`` prennent leur valeur par défaut.
    """
    data = bytearray(message.dlc)
    for signal in message.signals:
        physical = values.get(signal.name, signal.default)
        pack_signal(data, signal, signal.encode(float(physical)))
    return bytes(data)


def unpack(message: Message, data: bytes) -> dict[str, float]:
    """Décode une charge utile en valeurs physiques."""
    if len(data) != message.dlc:
        raise ValueError(
            f"{message.name} : {len(data)} octets reçus, {message.dlc} attendus"
        )
    return {s.name: s.decode(unpack_signal(data, s)) for s in message.signals}


def unpack_raw(message: Message, data: bytes) -> dict[str, int]:
    """Décode une charge utile en champs bruts, sans facteur ni offset."""
    return {s.name: unpack_signal(data, s) for s in message.signals}
