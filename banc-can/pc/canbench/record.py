"""Enregistrement et rejeu du trafic, au format ASC lisible par SavvyCAN.

Le format ``.asc`` (Vector) est retenu plutôt que ``.blf`` : il est textuel, donc
lisible et diffable, ce qui compte pour joindre une trace à un rapport de test.
``python-can`` sait écrire les deux ; ``--format blf`` reste disponible.
"""

from __future__ import annotations

import time
from pathlib import Path

import can

from .bus import Bench


def record(bench: Bench, path: Path, duration: float) -> int:
    """Enregistre le trafic pendant @p duration secondes. Renvoie le nombre de trames."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0

    with can.Logger(str(path)) as logger:
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            frame = bench.recv(timeout=min(0.1, max(0.0, deadline - time.monotonic())))
            if frame is None:
                continue
            logger.on_message_received(
                can.Message(
                    timestamp=frame.timestamp,
                    arbitration_id=frame.can_id,
                    data=frame.data,
                    is_extended_id=frame.is_extended,
                    is_fd=frame.is_fd,
                )
            )
            count += 1
    return count


def replay(bench: Bench, path: Path, *, respect_timing: bool = True) -> int:
    """Rejoue un enregistrement sur le bus. Renvoie le nombre de trames émises."""
    count = 0
    previous: float | None = None

    for message in can.LogReader(str(path)):
        if respect_timing and previous is not None:
            delay = message.timestamp - previous
            if 0 < delay < 5.0:
                time.sleep(delay)
        previous = message.timestamp

        if message.is_extended_id or getattr(message, "is_fd", False):
            # Le banc n'émet que du CAN 2.0A classic : une trace contenant autre
            # chose est signalée plutôt que rejouée telle quelle.
            continue

        bench.send(message.arbitration_id, bytes(message.data or b""))
        count += 1

    return count


def count_non_classic(path: Path) -> dict[str, int]:
    """Compte les trames non conformes d'un enregistrement, sans le rejouer."""
    extended = fd = oversized = total = 0
    for message in can.LogReader(str(path)):
        total += 1
        if message.is_extended_id:
            extended += 1
        if getattr(message, "is_fd", False):
            fd += 1
        if len(message.data or b"") > 8:
            oversized += 1
    return {"total": total, "extended": extended, "fd": fd, "oversized": oversized}
