"""Test d'arbitrage ARM/GO — test T3 du protocole de validation.

Le PC émet `ARM` puis `GO`. Les contendants arment leur émission pendant que `GO`
occupe le bus ; l'arbitrage qui suit départage réellement.

Métrique
--------
Le **rang** d'un contendant vaut 1 + le nombre de trames contendantes observées
entre la fin de `GO` et sa propre émission. Attendu : N1 → 1, N2 → 2, N3 → 3.

Les colonnes `gagnés` / `perdus` du tableau 7 du dossier sont également produites,
`perdus` étant défini sans ambiguïté comme le **nombre de cycles** où le nœud a
perdu au moins un arbitrage — et non le nombre d'arbitrages perdus, qui vaut 2
par cycle pour N3.

Prérequis sur les nœuds
-----------------------
Pendant un cycle, le bus ne doit porter que `GO` puis les trames contendantes.
Les nœuds **suspendent donc leur heartbeat et leur émission périodique** entre la
réception d'`ARM` et la fin de leur propre émission. Sans cela, une trame
périodique arrivant juste après `GO` serait comptée comme contendante et
fausserait le rang — au point qu'une rafale périodique peut, par coïncidence,
reproduire l'ordre attendu et faire passer un test qui aurait dû échouer.

Validité
--------
Un cycle est invalide si un contendant manque à l'appel, si l'ordre n'est pas
celui des identifiants, ou si les `ARM reçus` divergent entre nœuds. Un nœud qui
rate la fenêtre d'armement émettrait seul juste après et apparaîtrait vainqueur
sans avoir affronté personne : c'est précisément ce que ce contrôle empêche.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import icd_gen
from .bus import Bench, Frame


@dataclass
class Cycle:
    """Un cycle ARM/GO observé."""

    index: int
    order: list[int] = field(default_factory=list)  # identifiants, dans l'ordre observé
    timestamps: list[float] = field(default_factory=list)
    valid: bool = True
    reason: str = ""

    def rank_of(self, can_id: int) -> int | None:
        return self.order.index(can_id) + 1 if can_id in self.order else None

    @property
    def gaps_us(self) -> list[float]:
        """Écarts entre trames successives, en microsecondes."""
        return [(b - a) * 1e6 for a, b in zip(self.timestamps, self.timestamps[1:], strict=False)]


@dataclass
class ArbitrationResult:
    cycles: list[Cycle]
    contenders: list[dict]
    expected_order: list[int]
    heartbeats: dict[int, dict] = field(default_factory=dict)
    max_gap_us: float = 0.0

    # -- agrégats ----------------------------------------------------------

    @property
    def valid_cycles(self) -> list[Cycle]:
        return [c for c in self.cycles if c.valid]

    @property
    def invalid_count(self) -> int:
        return len(self.cycles) - len(self.valid_cycles)

    def histogram(self, can_id: int) -> dict[int, int]:
        histogram: dict[int, int] = {}
        for cycle in self.valid_cycles:
            rank = cycle.rank_of(can_id)
            if rank is not None:
                histogram[rank] = histogram.get(rank, 0) + 1
        return histogram

    def stats(self) -> list[dict]:
        rows = []
        for position, contender in enumerate(
            sorted(self.contenders, key=lambda c: c["can_id"]), start=1
        ):
            can_id = contender["can_id"]
            histogram = self.histogram(can_id)
            total = sum(histogram.values())
            won = histogram.get(1, 0)
            rows.append(
                {
                    "name": contender["name"],
                    "sender": contender["sender"],
                    "can_id": can_id,
                    "expected_rank": position,
                    "cycles": total,
                    "won": won,
                    "lost": total - won,
                    "histogram": histogram,
                    "always_expected": total > 0 and histogram.get(position, 0) == total,
                }
            )
        return rows

    @property
    def passed(self) -> bool:
        """Verdict : tous les cycles valides, chacun au rang attendu."""
        if not self.cycles or self.invalid_count:
            return False
        if any(not row["always_expected"] for row in self.stats()):
            return False
        return not self.clock_warnings

    @property
    def clock_warnings(self) -> list[str]:
        """Nœuds dont la référence d'horloge n'est pas conforme."""
        return [
            f"N{node_id}"
            for node_id, beat in self.heartbeats.items()
            if beat.get("clock_not_qualified")
        ]

    @property
    def loss_warnings(self) -> list[str]:
        warnings = []
        for node_id, beat in self.heartbeats.items():
            for key in ("rx_fifo_lost", "ring_overflow", "non_classic_rx", "ext_id_rx"):
                if beat.get(key):
                    warnings.append(f"N{node_id} : {key} = {beat[key]}")
        return warnings


def run(
    bench: Bench,
    cycles: int = 1000,
    cycle_timeout: float = 0.05,
    settle: float = 0.002,
) -> ArbitrationResult:
    """Exécute @p cycles cycles ARM/GO et mesure les rangs."""
    contenders = list(icd_gen.CONTENDERS)
    expected_ids = sorted(c["can_id"] for c in contenders)
    contender_ids = set(expected_ids)

    heartbeat_base = icd_gen.PROFILES[bench.profile]["heartbeat_base"]
    heartbeats: dict[int, dict] = {}

    observed: list[Cycle] = []
    max_gap_us = 0.0

    bench.drain()

    for index in range(cycles):
        bench.send_named("ARM")
        time.sleep(settle)
        bench.send_named("GO")

        cycle = Cycle(index=index)
        deadline = time.monotonic() + cycle_timeout
        seen: set[int] = set()

        while time.monotonic() < deadline and seen != contender_ids:
            frame = bench.recv(timeout=max(0.0, deadline - time.monotonic()))
            if frame is None:
                break
            _note_heartbeat(frame, heartbeat_base, heartbeats)
            if frame.can_id in contender_ids and frame.can_id not in seen:
                seen.add(frame.can_id)
                cycle.order.append(frame.can_id)
                cycle.timestamps.append(frame.timestamp)

        _validate(cycle, expected_ids)
        if cycle.gaps_us:
            max_gap_us = max(max_gap_us, max(cycle.gaps_us))
        observed.append(cycle)

    # Laisse passer un heartbeat pour relever l'état final des nœuds.
    for frame in bench.collect(0.6):
        _note_heartbeat(frame, heartbeat_base, heartbeats)

    return ArbitrationResult(
        cycles=observed,
        contenders=contenders,
        expected_order=expected_ids,
        heartbeats=heartbeats,
        max_gap_us=max_gap_us,
    )


def _validate(cycle: Cycle, expected_ids: list[int]) -> None:
    if len(cycle.order) != len(expected_ids):
        missing = [f"0x{i:03X}" for i in expected_ids if i not in cycle.order]
        cycle.valid = False
        cycle.reason = f"contendant(s) absent(s) : {', '.join(missing) or 'aucun'}"
        return
    if cycle.order != expected_ids:
        cycle.valid = False
        cycle.reason = (
            "ordre inattendu : "
            + " ".join(f"0x{i:03X}" for i in cycle.order)
            + " au lieu de "
            + " ".join(f"0x{i:03X}" for i in expected_ids)
        )


def _note_heartbeat(frame: Frame, base: int, store: dict[int, dict]) -> None:
    node_id = frame.can_id - base
    if not 1 <= node_id <= 15 or len(frame.data) != 8:
        return
    beat = icd_gen.Heartbeat.unpack(frame.data)
    store[node_id] = {
        "ctrl_state": beat.ctrl_state,
        "tec": beat.tec,
        "rec": beat.rec,
        "clock_not_qualified": bool(beat.clock_not_qualified),
        "rx_fifo_lost": beat.rx_fifo_lost,
        "ring_overflow": beat.ring_overflow,
        "non_classic_rx": beat.non_classic_rx,
        "ext_id_rx": beat.ext_id_rx,
    }


# ---------------------------------------------------------------------------
#  Rendu
# ---------------------------------------------------------------------------

STATES = ("error-active", "error-warning", "error-passive", "BUS-OFF")


def render(result: ArbitrationResult, *, virtual: bool = False) -> str:
    lines: list[str] = []
    lines.append("Test T3 — arbitrage ARM/GO")
    lines.append("=" * 68)
    lines.append(f"Cycles exécutés : {len(result.cycles)}")
    lines.append(f"Cycles valides  : {len(result.valid_cycles)}")
    if result.invalid_count:
        lines.append(f"Cycles invalides: {result.invalid_count}")
        for cycle in result.cycles:
            if not cycle.valid:
                lines.append(f"    cycle {cycle.index} : {cycle.reason}")
                if len([c for c in result.cycles if not c.valid]) > 5:
                    lines.append("    ...")
                    break
    lines.append("")

    header = f"{'Nœud':<6}{'Trame':<18}{'ID':<8}{'Rang':<6}{'Gagnés':<9}{'Perdus':<9}Histogramme"
    lines.append(header)
    lines.append("-" * len(header))
    for row in result.stats():
        histogram = " ".join(f"{k}:{v}" for k, v in sorted(row["histogram"].items()))
        mark = "" if row["always_expected"] else "  <-- ECART"
        lines.append(
            f"{row['sender']:<6}{row['name']:<18}0x{row['can_id']:03X}   "
            f"{row['expected_rank']:<6}{row['won']:<9}{row['lost']:<9}{histogram}{mark}"
        )

    lines.append("")
    lines.append(f"Écart maximal entre trames successives : {result.max_gap_us:.1f} µs")

    if result.heartbeats:
        lines.append("")
        lines.append("État des nœuds (heartbeat) :")
        for node_id in sorted(result.heartbeats):
            beat = result.heartbeats[node_id]
            lines.append(
                f"  N{node_id}  {STATES[beat['ctrl_state']]:<14} "
                f"TEC={beat['tec']:<4} REC={beat['rec']:<4} "
                f"fifo={beat['rx_fifo_lost']} tampon={beat['ring_overflow']} "
                f"fd={beat['non_classic_rx']} ext={beat['ext_id_rx']}"
            )

    for warning in result.loss_warnings:
        lines.append(f"ATTENTION : {warning}")
    if result.clock_warnings:
        lines.append(
            "ATTENTION : horloge non conforme sur "
            + ", ".join(result.clock_warnings)
            + " — aucun verdict de réussite ne peut être prononcé."
        )

    lines.append("")
    lines.append(f"VERDICT : {'REUSSITE' if result.passed else 'ECHEC'}")

    if virtual:
        lines.append("")
        lines.append(
            "NOTE : exécuté sur le bus virtuel. Le simulateur reproduit l'ordre qu'un\n"
            "       arbitrage réel produirait, il ne le démontre pas. Ce résultat valide\n"
            "       la chaîne de mesure, pas le comportement du bus. Seule l'exécution\n"
            "       sur le banc réel vaut pour T3."
        )
    return "\n".join(lines)
