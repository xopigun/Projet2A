"""Test d'encodage de l'ICD — test T4 du protocole de validation.

Chaque nœud dont le capteur réel n'est pas détecté émet la **séquence
déterministe** déclarée dans `icd/bench_icd.yaml`. L'outil collecte le trafic,
retrouve ces séquences et compare **octet par octet** les trames reçues aux
trames attendues.

Un écart est rapporté avec l'octet fautif, sa valeur reçue et sa valeur attendue,
ainsi que le signal concerné : c'est ce qui permet de remonter d'un symptôme à
une erreur d'encodage précise.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import icd_gen
from .bus import Bench, Frame


@dataclass
class ByteDiff:
    index: int
    received: int
    expected: int
    signals: list[str]

    def __str__(self) -> str:
        which = ", ".join(self.signals) or "—"
        return (
            f"octet {self.index} : reçu 0x{self.received:02X}, "
            f"attendu 0x{self.expected:02X}  ({which})"
        )


@dataclass
class FrameReport:
    name: str
    can_id: int
    observed: int = 0
    matched: int = 0
    dlc_errors: int = 0
    diffs: list[ByteDiff] = field(default_factory=list)
    unmatched_payloads: list[bytes] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.observed > 0 and self.matched == self.observed and not self.dlc_errors


@dataclass
class EncodingResult:
    frames: list[FrameReport]
    non_conformity_total: int = 0

    @property
    def passed(self) -> bool:
        return bool(self.frames) and all(f.passed for f in self.frames)


def _signals_at_byte(meta: dict, index: int) -> list[str]:
    """Signaux qui occupent au moins un bit de l'octet @p index."""
    names = []
    for signal in meta["signals"]:
        start = signal["start_byte"] * 8 + signal["start_bit"]
        if signal["byte_order"] == "little_endian":
            positions = range(start, start + signal["length"])
        else:
            positions = []
            byte_index, bit_index = signal["start_byte"], signal["start_bit"]
            for _ in range(signal["length"]):
                positions.append(byte_index * 8 + bit_index)
                if bit_index == 0:
                    byte_index, bit_index = byte_index + 1, 7
                else:
                    bit_index -= 1
        if any(p // 8 == index for p in positions):
            names.append(signal["name"])
    return names


def _expected_payloads(layout_name: str) -> list[bytes]:
    """Toutes les charges utiles de la séquence déterministe d'une trame."""
    simulation = icd_gen.SIMULATIONS.get(layout_name)
    layout = icd_gen.LAYOUTS.get(layout_name)
    if simulation is None or layout is None:
        return []
    return [layout(**dict(step)).pack() for step in simulation["steps"]]


def run(bench: Bench, duration: float = 2.0) -> EncodingResult:
    """Collecte le trafic et confronte chaque trame à sa séquence attendue."""
    targets: dict[int, dict] = {}
    for can_id, meta in icd_gen.FRAMES.items():
        expected = _expected_payloads(meta["layout"])
        if expected:
            targets[can_id] = {"meta": meta, "expected": expected}

    reports = {
        can_id: FrameReport(name=entry["meta"]["name"], can_id=can_id)
        for can_id, entry in targets.items()
    }

    bench.drain()
    for frame in bench.collect(duration):
        entry = targets.get(frame.can_id)
        if entry is None:
            continue
        _compare(frame, entry, reports[frame.can_id])

    return EncodingResult(
        frames=[reports[i] for i in sorted(reports)],
        non_conformity_total=bench.non_conformity.total,
    )


def _compare(frame: Frame, entry: dict, report: FrameReport) -> None:
    meta = entry["meta"]
    report.observed += 1

    if len(frame.data) != meta["dlc"]:
        report.dlc_errors += 1
        return

    # La séquence boucle : une trame est correcte si elle correspond à l'une
    # quelconque de ses étapes. On ne présume pas de la phase du simulateur.
    if frame.data in entry["expected"]:
        report.matched += 1
        return

    # Écart : on le rapporte contre l'étape la plus proche, pour que le
    # diagnostic pointe le moins d'octets possible.
    closest = min(
        entry["expected"],
        key=lambda candidate: sum(a != b for a, b in zip(candidate, frame.data, strict=False)),
    )
    if len(report.diffs) < 20:
        for index, (received, expected) in enumerate(zip(frame.data, closest, strict=False)):
            if received != expected:
                report.diffs.append(
                    ByteDiff(index, received, expected, _signals_at_byte(meta, index))
                )
    if len(report.unmatched_payloads) < 5:
        report.unmatched_payloads.append(frame.data)


def render(result: EncodingResult, *, virtual: bool = False) -> str:
    lines = ["Test T4 — encodage de l'ICD", "=" * 68]

    header = f"{'Trame':<18}{'ID':<8}{'Reçues':<9}{'Conformes':<12}{'Écarts':<9}Verdict"
    lines.append(header)
    lines.append("-" * len(header))
    for report in result.frames:
        verdict = "ok" if report.passed else "ECHEC"
        lines.append(
            f"{report.name:<18}0x{report.can_id:03X}   {report.observed:<9}"
            f"{report.matched:<12}{len(report.diffs):<9}{verdict}"
        )

    for report in result.frames:
        if report.passed:
            continue
        lines.append("")
        lines.append(f"{report.name} (0x{report.can_id:03X}) :")
        if report.observed == 0:
            lines.append("  aucune trame reçue — le nœud émet-il ?")
        if report.dlc_errors:
            lines.append(f"  {report.dlc_errors} trame(s) au DLC incohérent avec l'ICD")
        for diff in report.diffs[:10]:
            lines.append(f"  {diff}")
        for payload in report.unmatched_payloads[:3]:
            lines.append(f"  charge utile reçue : {payload.hex(' ')}")

    if result.non_conformity_total:
        lines.append("")
        lines.append(
            f"ATTENTION : {result.non_conformity_total} trame(s) hors CAN 2.0A classic reçue(s)."
        )

    lines.append("")
    lines.append(f"VERDICT : {'REUSSITE' if result.passed else 'ECHEC'}")

    if virtual:
        lines.append("")
        lines.append(
            "NOTE : sur bus virtuel, c'est notre encodeur qui alimente notre décodeur.\n"
            "       La parité avec le code C embarqué est établie ailleurs, par les\n"
            "       vecteurs de référence. Seule l'exécution sur le banc réel vaut pour T4."
        )
    return "\n".join(lines)
