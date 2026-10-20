"""Ouverture du bus et contrôle de conformité CAN 2.0A classic.

Le banc parle **CAN 2.0A classic** : identifiants 11 bits, 8 octets au plus, pas
de commutation de débit. L'interface PC est donc ouverte en classic (`fd=False`),
et toute trame CAN FD ou à identifiant étendu reçue est **comptée et signalée**
plutôt qu'ignorée : c'est exactement le genre d'anomalie que le banc doit mettre
en évidence chez un partenaire.

Trois interfaces sont prévues :

- ``gs_usb``  : CANable 2.0 en firmware candleLight (nécessite ``gs-usb`` et ``pyusb``) ;
- ``slcan``   : CANable en firmware slcan (nécessite ``pyserial``) ;
- ``virtual`` : bus en mémoire de python-can, pour tout exécuter sans matériel.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass, field

import can

from . import icd_gen

#: Débit nominal du banc, en bit/s.
DEFAULT_BITRATE = icd_gen.BITRATE

#: Canal par défaut du bus virtuel ; les tests s'y branchent.
VIRTUAL_CHANNEL = "canbench"


@dataclass(frozen=True)
class Frame:
    """Une trame reçue, horodatée."""

    timestamp: float
    can_id: int
    data: bytes
    is_extended: bool = False
    is_fd: bool = False
    is_error_frame: bool = False

    @property
    def dlc(self) -> int:
        return len(self.data)

    @property
    def is_classic_2a(self) -> bool:
        """Vrai si la trame respecte le standard commun : 11 bits, ≤ 8 octets, non FD."""
        return not self.is_extended and not self.is_fd and self.dlc <= 8

    @classmethod
    def from_message(cls, message: can.Message) -> Frame:
        return cls(
            timestamp=message.timestamp,
            can_id=message.arbitration_id,
            data=bytes(message.data or b""),
            is_extended=bool(message.is_extended_id),
            is_fd=bool(getattr(message, "is_fd", False)),
            is_error_frame=bool(message.is_error_frame),
        )


@dataclass
class NonConformity:
    """Trames reçues qui sortent du standard commun."""

    extended: int = 0
    fd: int = 0
    oversized: int = 0
    samples: list[Frame] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.extended + self.fd + self.oversized

    def record(self, frame: Frame) -> bool:
        """Enregistre la trame si elle n'est pas conforme ; renvoie True dans ce cas."""
        if frame.is_classic_2a:
            return False
        if frame.is_extended:
            self.extended += 1
        if frame.is_fd:
            self.fd += 1
        if frame.dlc > 8:
            self.oversized += 1
        if len(self.samples) < 10:
            self.samples.append(frame)
        return True

    def report(self) -> list[str]:
        if self.total == 0:
            return []
        lines = [f"ATTENTION : {self.total} trame(s) hors du standard commun CAN 2.0A reçue(s)."]
        if self.extended:
            lines.append(f"  - {self.extended} à identifiant 29 bits")
        if self.fd:
            lines.append(f"  - {self.fd} au format CAN FD")
        if self.oversized:
            lines.append(f"  - {self.oversized} de plus de 8 octets")
        for frame in self.samples[:5]:
            lines.append(
                f"    0x{frame.can_id:X} dlc={frame.dlc} "
                f"{'ext ' if frame.is_extended else ''}{'fd' if frame.is_fd else ''}"
            )
        return lines


class Bench:
    """Connexion au bus du banc.

    Enveloppe un bus python-can en imposant le CAN 2.0A classic et en tenant le
    compte des trames non conformes.
    """

    def __init__(
        self,
        interface: str = "virtual",
        channel: str | None = None,
        bitrate: int = DEFAULT_BITRATE,
        profile: str = icd_gen.DEFAULT_PROFILE,
    ) -> None:
        self.interface = interface
        self.bitrate = bitrate
        self.profile = profile
        self.ids = icd_gen.PROFILES[profile]["ids"]
        self.non_conformity = NonConformity()

        kwargs: dict = {"interface": interface}
        if interface == "virtual":
            kwargs["channel"] = channel or VIRTUAL_CHANNEL
        else:
            if channel is not None:
                kwargs["channel"] = channel
            kwargs["bitrate"] = bitrate
            # Ouverture explicite en classic : le banc n'émet ni ne décode de CAN FD.
            kwargs["fd"] = False

        self._bus = can.Bus(**kwargs)

    # -- cycle de vie -------------------------------------------------------

    def __enter__(self) -> Bench:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def close(self) -> None:
        self._bus.shutdown()

    # -- émission -----------------------------------------------------------

    def send(self, can_id: int, data: bytes = b"") -> None:
        """Émet une trame CAN 2.0A classic.

        Refuse tout ce qui sort du standard : le banc ne doit jamais introduire
        lui-même l'anomalie qu'il est censé détecter.
        """
        if can_id > 0x7FF:
            raise ValueError(f"0x{can_id:X} dépasse les 11 bits du CAN 2.0A")
        if len(data) > 8:
            raise ValueError(f"{len(data)} octets : le CAN 2.0 en autorise 8 au plus")

        self._bus.send(
            can.Message(
                arbitration_id=can_id,
                data=data,
                is_extended_id=False,
                is_fd=False,
                bitrate_switch=False,
            )
        )

    def send_named(self, name: str, data: bytes = b"") -> None:
        """Émet une trame désignée par son nom dans le profil actif."""
        self.send(self.ids[name], data)

    # -- réception ----------------------------------------------------------

    def recv(self, timeout: float = 1.0) -> Frame | None:
        message = self._bus.recv(timeout)
        if message is None:
            return None
        frame = Frame.from_message(message)
        self.non_conformity.record(frame)
        return frame

    def collect(self, duration: float, limit: int | None = None) -> list[Frame]:
        """Collecte les trames pendant @p duration secondes."""
        deadline = time.monotonic() + duration
        frames: list[Frame] = []
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            frame = self.recv(timeout=max(0.0, min(0.05, remaining)))
            if frame is not None:
                frames.append(frame)
                if limit is not None and len(frames) >= limit:
                    break
        return frames

    def stream(self, duration: float | None = None) -> Iterator[Frame]:
        """Itère sur les trames reçues, indéfiniment si @p duration est None."""
        deadline = None if duration is None else time.monotonic() + duration
        while deadline is None or time.monotonic() < deadline:
            frame = self.recv(timeout=0.1)
            if frame is not None:
                yield frame

    def drain(self) -> None:
        """Vide les trames en attente, pour repartir d'un état propre."""
        while self._bus.recv(0.0) is not None:
            pass
