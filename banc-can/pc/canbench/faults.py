"""Injection de fautes — tests T5 (physiques) et T6 (logicielles).

T5 est **semi-automatique** : les fautes physiques passent par les interrupteurs
SW1, SW2 et SW3 du boîtier. L'outil guide l'opérateur, relève les compteurs avant
et après, et rappelle les précautions — notamment que **SW2 ne doit être fermé
que brièvement**, le TJA1051T/3 s'échauffant en court-circuit prolongé.

T6 est automatique : les modes de faute de N4 sont pilotés par `BENCH_CFG`.
Chaque mode est borné dans le temps et révocable.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from . import icd_gen
from .arbitration import STATES, _note_heartbeat
from .bus import Bench


class Mode:
    """Modes de faute, alignés sur le signal `mode` de BENCH_CFG."""

    NORMAL = 0
    BABBLING_IDIOT = 1
    WRONG_BITRATE = 2
    BAD_DLC = 3
    SILENT = 4
    HOLD_BUSOFF = 5


MODE_NAMES = {
    Mode.NORMAL: "normal",
    Mode.BABBLING_IDIOT: "babbling idiot",
    Mode.WRONG_BITRATE: "débit erroné (250 kbit/s)",
    Mode.BAD_DLC: "DLC incohérent",
    Mode.SILENT: "silencieux (couvre l'arrêt d'acquittement)",
    Mode.HOLD_BUSOFF: "bus-off maintenu",
}

#: Durée maximale conseillée de fermeture de SW2, en secondes.
SW2_MAX_SECONDS = 5


@dataclass
class Observation:
    """État du bus relevé sur une fenêtre de temps."""

    label: str
    frames: int
    duration: float
    heartbeats: dict[int, dict] = field(default_factory=dict)

    @property
    def frames_per_s(self) -> float:
        return self.frames / self.duration if self.duration else 0.0

    def worst_state(self) -> int:
        return max((b["ctrl_state"] for b in self.heartbeats.values()), default=0)


@dataclass
class FaultStep:
    name: str
    before: Observation
    after: Observation
    passed: bool
    detail: str = ""


@dataclass
class FaultResult:
    steps: list[FaultStep]
    kind: str  # "physique" ou "logique"

    @property
    def passed(self) -> bool:
        return bool(self.steps) and all(s.passed for s in self.steps)


def observe(bench: Bench, label: str, duration: float = 1.0) -> Observation:
    """Relève le trafic et l'état des nœuds pendant @p duration secondes."""
    base = icd_gen.PROFILES[bench.profile]["heartbeat_base"]
    heartbeats: dict[int, dict] = {}

    start = time.monotonic()
    frames = bench.collect(duration)
    for frame in frames:
        _note_heartbeat(frame, base, heartbeats)

    return Observation(
        label=label,
        frames=len(frames),
        duration=time.monotonic() - start,
        heartbeats=heartbeats,
    )


# ---------------------------------------------------------------------------
#  T6 — fautes logicielles de N4
# ---------------------------------------------------------------------------


def send_cfg(
    bench: Bench,
    target_node: int,
    mode: int,
    duration_ms: int,
    param: int = 0,
    heartbeat_period_ms: int = 0,
) -> None:
    """Émet une commande BENCH_CFG."""
    cfg = icd_gen.BenchCfg(
        target_node=target_node,
        mode=mode,
        param_u16=param,
        duration_ms=duration_ms,
        heartbeat_period_ms=heartbeat_period_ms,
    )
    bench.send_named("BENCH_CFG", cfg.pack())


def revoke(bench: Bench, target_node: int) -> None:
    """Révoque immédiatement le mode de faute d'un nœud (durée nulle)."""
    send_cfg(bench, target_node, Mode.NORMAL, duration_ms=0)


def run_logical(
    bench: Bench,
    target_node: int = 4,
    modes: tuple[int, ...] = (
        Mode.BABBLING_IDIOT,
        Mode.BAD_DLC,
        Mode.SILENT,
    ),
    hold: float = 0.6,
    flood_id: int = 0x400,
) -> FaultResult:
    """Exécute les modes de faute logiciels, chacun borné et révoqué."""
    steps: list[FaultStep] = []

    for mode in modes:
        before = observe(bench, "avant", 0.4)

        send_cfg(bench, target_node, mode, duration_ms=int(hold * 1000), param=flood_id)
        during = observe(bench, "pendant", hold)

        revoke(bench, target_node)
        time.sleep(0.1)
        after = observe(bench, "après révocation", 0.4)

        passed, detail = _judge_logical(mode, before, during, after)
        steps.append(FaultStep(MODE_NAMES[mode], before, during, passed, detail))

        # Le retour à la normale fait partie du critère : une faute doit être
        # révocable, sinon le banc reste inutilisable après le test.
        recovered = after.frames_per_s > 0
        steps.append(
            FaultStep(
                f"{MODE_NAMES[mode]} — retour à la normale",
                during,
                after,
                recovered,
                "trafic rétabli" if recovered else "le bus ne repart pas",
            )
        )

    return FaultResult(steps=steps, kind="logique")


def _judge_logical(
    mode: int, before: Observation, during: Observation, after: Observation
) -> tuple[bool, str]:
    if mode == Mode.BABBLING_IDIOT:
        ok = during.frames_per_s > before.frames_per_s * 1.5
        return ok, (
            f"trafic {before.frames_per_s:.0f} -> {during.frames_per_s:.0f} trames/s"
            + ("" if ok else " (hausse attendue non observée)")
        )
    if mode == Mode.BAD_DLC:
        return True, "trames au DLC incohérent émises ; à confronter au rapport d'encodage"
    if mode == Mode.SILENT:
        return True, "le nœud n'acquitte plus ; effet à relever sur les compteurs des autres"
    if mode == Mode.WRONG_BITRATE:
        ok = during.worst_state() >= 2
        return ok, "passage en error-passive ou bus-off attendu sur le nœud fautif"
    if mode == Mode.HOLD_BUSOFF:
        ok = during.worst_state() == 3
        return ok, "état bus-off attendu"
    return True, ""


# ---------------------------------------------------------------------------
#  T5 — fautes physiques, guidées
# ---------------------------------------------------------------------------


@dataclass
class PhysicalStep:
    switch: str
    fault: str
    nominal: str
    instruction: str
    expected: str
    caution: str = ""


PHYSICAL_STEPS = (
    PhysicalStep(
        switch="SW1",
        fault="Perte de la terminaison R_T2",
        nominal="fermé",
        instruction="OUVRIR SW1 (retire la terminaison R_T2), puis valider.",
        expected="Dégradation du signal, hausse du taux d'erreur, REC qui progresse.",
    ),
    PhysicalStep(
        switch="SW2",
        fault="Court-circuit CAN_H / CAN_L",
        nominal="ouvert",
        instruction="FERMER SW2 BRIÈVEMENT, puis valider dès que possible.",
        expected="Erreurs de bit, passage des nœuds émetteurs en bus-off.",
        caution=(
            f"SW2 ne doit pas rester fermé plus de {SW2_MAX_SECONDS} s : le TJA1051T/3 "
            "limite son courant de court-circuit mais s'échauffe. Ne jamais actionner "
            "SW2 pendant qu'un nœud isolé galvaniquement est sous tension côté puissance."
        ),
    ),
    PhysicalStep(
        switch="SW3",
        fault="Retrait à chaud du nœud N4",
        nominal="fermé",
        instruction="OUVRIR SW3 (déconnecte N4 du bus), puis valider.",
        expected="Le reste du bus continue de fonctionner sans erreur.",
    ),
)


def run_physical(
    bench: Bench,
    prompt: Callable[[str], str],
    echo: Callable[[str], None],
) -> FaultResult:
    """Assistant guidé pour SW1, SW2 et SW3.

    @p prompt reçoit une consigne et rend la main quand l'opérateur a agi ;
    @p echo affiche les messages. Les deux sont injectés pour que la procédure
    reste testable sans interaction.
    """
    steps: list[FaultStep] = []

    for spec in PHYSICAL_STEPS:
        echo("")
        echo(f"--- {spec.switch} : {spec.fault} ---")
        echo(f"Position nominale : {spec.nominal}")
        echo(f"Attendu : {spec.expected}")
        if spec.caution:
            echo(f"PRECAUTION : {spec.caution}")

        before = observe(bench, "avant", 1.0)
        echo(f"Référence : {before.frames_per_s:.0f} trames/s, état {STATES[before.worst_state()]}")

        prompt(spec.instruction)
        started = time.monotonic()
        during = observe(bench, "pendant la faute", 1.0)

        if spec.switch == "SW2":
            elapsed = time.monotonic() - started
            echo(f"SW2 fermé depuis {elapsed:.1f} s — le refermer au plus vite.")

        prompt(f"REMETTRE {spec.switch} en position nominale ({spec.nominal}), puis valider.")
        after = observe(bench, "après rétablissement", 1.0)

        passed, detail = _judge_physical(spec, before, during, after)
        steps.append(FaultStep(f"{spec.switch} — {spec.fault}", before, after, passed, detail))

    return FaultResult(steps=steps, kind="physique")


def _judge_physical(
    spec: PhysicalStep, before: Observation, during: Observation, after: Observation
) -> tuple[bool, str]:
    recovered = after.frames_per_s >= before.frames_per_s * 0.5

    if spec.switch == "SW3":
        # Critère du dossier : le reste du bus continue de fonctionner.
        survived = during.frames_per_s >= before.frames_per_s * 0.5
        return survived and recovered, (
            f"trafic pendant la déconnexion : {during.frames_per_s:.0f} trames/s "
            f"(référence {before.frames_per_s:.0f})"
        )

    degraded = during.frames_per_s < before.frames_per_s or during.worst_state() > 0
    return degraded and recovered, (
        f"{before.frames_per_s:.0f} -> {during.frames_per_s:.0f} trames/s, "
        f"état {STATES[during.worst_state()]} ; "
        + ("bus rétabli" if recovered else "BUS NON RETABLI")
    )


def render(result: FaultResult, *, virtual: bool = False) -> str:
    title = (
        "Test T5 — fautes physiques"
        if result.kind == "physique"
        else ("Test T6 — fautes logicielles")
    )
    lines = [title, "=" * 68]

    for step in result.steps:
        verdict = "ok" if step.passed else "ECHEC"
        lines.append(f"[{verdict:<5}] {step.name}")
        if step.detail:
            lines.append(f"          {step.detail}")

    lines.append("")
    lines.append(f"VERDICT : {'REUSSITE' if result.passed else 'ECHEC'}")

    if virtual:
        lines.append("")
        lines.append(
            "NOTE : sur bus virtuel, les fautes sont simulées par le simulateur de nœuds.\n"
            "       Aucune conclusion sur le comportement électrique du bus ne peut en\n"
            "       être tirée ; seule l'exécution sur le banc réel vaut pour T5 et T6."
        )
    return "\n".join(lines)
