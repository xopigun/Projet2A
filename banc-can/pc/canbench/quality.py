"""Qualité de la réception : régularité des trames et erreurs du bus.

Ces indicateurs valent pour **toutes** les interfaces, simulation comprise : ils ne
reposent que sur l'horodatage des trames reçues. Avec un adaptateur qui horodate
lui-même (ZLG : 0,1 ms), la gigue mesurée est celle du bus ; avec une interface
horodatée par le PC, elle inclut la latence USB et celle du système.

Pour chaque identifiant :

- période moyenne, gigue (écart-type), intervalles minimal et maximal, calculés
  sur les :data:`HISTORY` derniers intervalles ;
- période attendue, tirée de l'ICD (trames applicatives) ; pour les heartbeats,
  500 ms par défaut, ou la valeur ``heartbeat_period_ms`` d'un BENCH_CFG vu passer ;
- trames manquées estimées : un intervalle de 3 fois la cadence observée (intervalle
  médian) compte 2 trames perdues ;
- écart signalé si la période moyenne s'éloigne de plus de :data:`TOLERANCE` de
  l'attendue, ou si une trame a manqué.
"""

from __future__ import annotations

import math
import threading
from collections import deque
from dataclasses import dataclass, field

from . import icd_gen

#: Nombre d'intervalles retenus par identifiant.
HISTORY = 200

#: Écart relatif toléré entre période moyenne mesurée et période attendue.
TOLERANCE = 0.10

#: Un intervalle supérieur à ce multiple de la cadence observée compte des pertes.
MISS_FACTOR = 1.5

#: Intervalles nécessaires avant de prendre la cadence observée comme référence.
MIN_INTERVALS = 5

#: Identifiant de BENCH_CFG, qui peut changer la période de heartbeat d'un nœud.
BENCH_CFG_ID = next(i for i, m in icd_gen.FRAMES.items() if m["name"] == "BENCH_CFG")


@dataclass
class IdTiming:
    """Suivi temporel d'un identifiant."""

    can_id: int
    count: int = 0
    last: float | None = None
    missed: int = 0
    intervals: deque[float] = field(default_factory=lambda: deque(maxlen=HISTORY))

    def add(self, stamp: float, expected: float | None) -> None:
        self.count += 1
        if self.last is not None:
            dt = stamp - self.last
            if dt >= 0:
                cadence = self._cadence(expected)
                # Tant que la cadence n'est pas mesurée, on exige un trou franc.
                factor = MISS_FACTOR if len(self.intervals) >= MIN_INTERVALS else 2.0
                if cadence and dt > factor * cadence:
                    self.missed += max(0, round(dt / cadence) - 1)
                self.intervals.append(dt)
        self.last = stamp

    def _cadence(self, expected: float | None) -> float | None:
        """Cadence de référence pour compter les pertes : l'intervalle médian observé
        dès qu'il y en a assez, sinon la période attendue. Un nœud qui émet trop
        lentement est ainsi signalé par l'écart de période, pas par de fausses pertes."""
        if not expected:
            return None
        if len(self.intervals) < MIN_INTERVALS:
            return expected
        ordered = sorted(self.intervals)
        return ordered[len(ordered) // 2]

    def summary(self, expected: float | None) -> dict:
        values = list(self.intervals)
        mean = sum(values) / len(values) if values else None
        jitter = (
            math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
            if mean is not None
            else None
        )
        deviation = (mean - expected) / expected if mean is not None and expected else None
        alert = bool(self.missed) or (deviation is not None and abs(deviation) > TOLERANCE)
        return {
            "id": f"0x{self.can_id:03X}",
            "name": (icd_gen.FRAMES.get(self.can_id) or {}).get("name", "<inconnu>"),
            "count": self.count,
            "period_ms": _ms(mean),
            "expected_ms": _ms(expected),
            "jitter_ms": _ms(jitter),
            "min_ms": _ms(min(values)) if values else None,
            "max_ms": _ms(max(values)) if values else None,
            "deviation_pct": round(deviation * 100, 1) if deviation is not None else None,
            "missed": self.missed,
            "alert": alert,
        }


class QualityTracker:
    """Indicateurs de qualité calculés à partir des trames reçues."""

    def __init__(self, profile: str = icd_gen.DEFAULT_PROFILE) -> None:
        self.profile = profile
        self._heartbeat_base = icd_gen.PROFILES[profile]["heartbeat_base"]
        self._lock = threading.Lock()
        self._ids: dict[int, IdTiming] = {}
        self._heartbeat_period: dict[int, float] = {}
        self.error_frames = 0

    def expected_period(self, can_id: int) -> float | None:
        """Période attendue en secondes, ou None pour une trame événementielle."""
        period = (icd_gen.FRAMES.get(can_id) or {}).get("period_ms")
        if period:
            return period / 1000
        if 1 <= can_id - self._heartbeat_base <= 15:
            return self._heartbeat_period.get(can_id, _default_heartbeat_ms()) / 1000
        return None

    def note(self, frame) -> None:
        """Prend en compte une trame reçue (:class:`canbench.bus.Frame`)."""
        with self._lock:
            if frame.is_error_frame:
                self.error_frames += 1
                return
            if frame.can_id == BENCH_CFG_ID and len(frame.data) == 8:
                cfg = icd_gen.BenchCfg.unpack(frame.data)
                if cfg.heartbeat_period_ms and 1 <= cfg.target_node <= 15:
                    beat_id = self._heartbeat_base + int(cfg.target_node)
                    self._heartbeat_period[beat_id] = float(cfg.heartbeat_period_ms)
            timing = self._ids.get(frame.can_id)
            if timing is None:
                timing = self._ids[frame.can_id] = IdTiming(frame.can_id)
            timing.add(frame.timestamp, self.expected_period(frame.can_id))

    def restart(self) -> None:
        """Oublie le dernier instant de chaque identifiant, après une interruption
        de l'écoute : l'intervalle qui l'enjambe ne compte ni comme période ni comme perte."""
        with self._lock:
            for timing in self._ids.values():
                timing.last = None

    def summary(self) -> dict:
        with self._lock:
            rows = [
                timing.summary(self.expected_period(can_id))
                for can_id, timing in sorted(self._ids.items())
            ]
            return {
                "ids": rows,
                "error_frames": self.error_frames,
                "missed": sum(row["missed"] for row in rows),
                "alerts": sum(row["alert"] for row in rows),
            }


def _default_heartbeat_ms() -> float:
    return float(icd_gen.BenchCfg().heartbeat_period_ms)


def _ms(seconds: float | None) -> float | None:
    return None if seconds is None else round(seconds * 1000, 3)


__all__ = ["IdTiming", "QualityTracker"]
