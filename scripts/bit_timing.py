#!/usr/bin/env python3
"""Calcul et vérification du temps de bit CAN des nœuds du banc.

Sans argument, le script énumère les configurations possibles pour une horloge
noyau donnée. Avec ``--check``, il vérifie que les valeurs effectivement
inscrites dans les ``board.h`` du dépôt sont correctes **et alignées entre
nœuds**, et sort en erreur sinon.

Pourquoi l'alignement compte
----------------------------
Deux nœuds dont les points d'échantillonnage diffèrent ne tolèrent pas le même
écart d'horloge. Le point commun retenu est 87,5 %, recommandation CiA, atteint
exactement par les deux familles :

    G431 : 80 MHz / 10 / 16 tq, segments 1 + 13 + 2, SJW 2
    F103 : 36 MHz /  9 /  8 tq, segments 1 +  6 + 1, SJW 1

Tolérance d'oscillateur
-----------------------
Deux conditions d'ISO 11898-1 ; la plus contraignante est retenue ::

    df <= SJW / (20 * NBT)
    df <= min(PS1, PS2) / (2 * (13 * NBT - PS2))

À point d'échantillonnage égal, la tolérance ne dépend que du **rapport**
SJW/NBT, pas de SJW en valeur absolue : le SJW de 1 du F103 n'est donc pas un
handicap, 1/8 valant exactement 2/16. Sa seule conséquence est la granularité de
resynchronisation, de 12,5 % du temps de bit contre 6,25 % sur le G431.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

TARGET_BITRATE = 500_000
TARGET_SAMPLE_POINT = 0.875

#: Limites des registres de temps de bit, par contrôleur.
#: FDCAN : NBRP 1..512, NTSEG1 1..256, NTSEG2 1..128, NSJW 1..128 (RM0440).
#: bxCAN : BRP 1..1024, TS1 1..16, TS2 1..8, SJW 1..4 (RM0008).
LIMITS = {
    "fdcan": {"brp": 512, "tseg1": 256, "tseg2": 128, "sjw": 128},
    "bxcan": {"brp": 1024, "tseg1": 16, "tseg2": 8, "sjw": 4},
}


@dataclass(frozen=True)
class Timing:
    controller: str
    clock_hz: int
    prescaler: int
    tseg1: int  # hors bit de synchronisation
    tseg2: int
    sjw: int

    @property
    def nbt(self) -> int:
        """Durée totale du bit, en quanta de temps."""
        return 1 + self.tseg1 + self.tseg2

    @property
    def bitrate(self) -> float:
        return self.clock_hz / (self.prescaler * self.nbt)

    @property
    def sample_point(self) -> float:
        return (self.nbt - self.tseg2) / self.nbt

    @property
    def tolerance(self) -> float:
        """Écart d'horloge relatif admissible, en fraction (0,00485 = 0,485 %)."""
        df1 = self.sjw / (20 * self.nbt)
        df2 = min(self.tseg1, self.tseg2) / (2 * (13 * self.nbt - self.tseg2))
        return min(df1, df2)

    def describe(self) -> str:
        return (
            f"{self.controller:6s} {self.clock_hz / 1e6:6.1f} MHz  "
            f"BRP={self.prescaler:<4d} NBT={self.nbt:<4d} "
            f"1+{self.tseg1}+{self.tseg2:<3d} SJW={self.sjw:<3d} "
            f"debit={self.bitrate / 1000:8.3f} kbit/s  "
            f"SP={self.sample_point * 100:6.2f} %  "
            f"tolerance={self.tolerance * 100:.4f} %"
        )


def enumerate_timings(
    controller: str, clock_hz: int, bitrate: int = TARGET_BITRATE
) -> list[Timing]:
    """Toutes les configurations donnant exactement @p bitrate."""
    limits = LIMITS[controller]
    results: list[Timing] = []

    for prescaler in range(1, limits["brp"] + 1):
        if clock_hz % (bitrate * prescaler):
            continue
        nbt = clock_hz // (bitrate * prescaler)
        if not 8 <= nbt <= 81:  # plage utile recommandée par la CiA
            continue
        for tseg2 in range(1, min(limits["tseg2"], nbt - 2) + 1):
            tseg1 = nbt - 1 - tseg2
            if not 1 <= tseg1 <= limits["tseg1"]:
                continue
            sjw = min(limits["sjw"], tseg2)
            results.append(Timing(controller, clock_hz, prescaler, tseg1, tseg2, sjw))

    # Meilleur point d'échantillonnage d'abord, puis meilleure tolérance.
    results.sort(
        key=lambda t: (abs(t.sample_point - TARGET_SAMPLE_POINT), -t.tolerance)
    )
    return results


# ---------------------------------------------------------------------------
#  Lecture des valeurs réellement inscrites dans les board.h
# ---------------------------------------------------------------------------

BOARDS = {
    "nucleo_g431kb": ("fdcan", "BENCH_FDCAN_CLK_HZ"),
    "bluepill_f103": ("bxcan", "BENCH_BXCAN_CLK_HZ"),
}


def _defines(text: str) -> dict[str, int]:
    found: dict[str, int] = {}
    for match in re.finditer(r"^#define\s+(BENCH_\w+)\s+(\d+)u?\b", text, re.MULTILINE):
        found[match.group(1)] = int(match.group(2))
    return found


def read_board(name: str) -> Timing | None:
    """Lit le temps de bit d'un board.h ; renvoie None si la carte n'existe pas."""
    path = REPO_ROOT / "firmware" / "boards" / name / "board.h"
    if not path.exists():
        return None

    controller, clock_key = BOARDS[name]
    values = _defines(path.read_text(encoding="utf-8"))

    required = [
        clock_key,
        "BENCH_CAN_PRESCALER",
        "BENCH_CAN_TSEG1",
        "BENCH_CAN_TSEG2",
        "BENCH_CAN_SJW",
    ]
    missing = [key for key in required if key not in values]
    if missing:
        raise SystemExit(f"{path} : constantes manquantes {missing}")

    return Timing(
        controller=controller,
        clock_hz=values[clock_key],
        prescaler=values["BENCH_CAN_PRESCALER"],
        tseg1=values["BENCH_CAN_TSEG1"],
        tseg2=values["BENCH_CAN_TSEG2"],
        sjw=values["BENCH_CAN_SJW"],
    )


def check() -> int:
    """Vérifie les board.h existants. Renvoie le code de sortie du script."""
    timings: dict[str, Timing] = {}
    problems: list[str] = []

    for name in BOARDS:
        timing = read_board(name)
        if timing is None:
            print(f"  {name:16s} absent, ignore (lot 5)")
            continue
        timings[name] = timing
        print(f"  {name:16s} {timing.describe()}")

        if abs(timing.bitrate - TARGET_BITRATE) > 1e-6:
            problems.append(
                f"{name} : debit {timing.bitrate:.3f} bit/s au lieu de {TARGET_BITRATE}"
            )
        if abs(timing.sample_point - TARGET_SAMPLE_POINT) > 1e-9:
            problems.append(
                f"{name} : point d'echantillonnage {timing.sample_point * 100:.2f} % "
                f"au lieu de {TARGET_SAMPLE_POINT * 100:.2f} %"
            )
        limits = LIMITS[timing.controller]
        if timing.sjw > timing.tseg2 or timing.sjw > limits["sjw"]:
            problems.append(
                f"{name} : SJW {timing.sjw} incompatible avec TSEG2/le controleur"
            )
        if timing.tseg1 > limits["tseg1"] or timing.tseg2 > limits["tseg2"]:
            problems.append(f"{name} : segments hors des limites du controleur")

    # Alignement entre nœuds : c'est le contrôle qui a le plus de valeur.
    if len(timings) >= 2:
        points = {name: round(t.sample_point, 9) for name, t in timings.items()}
        if len(set(points.values())) != 1:
            problems.append(
                "les noeuds n'ont pas le meme point d'echantillonnage : "
                + ", ".join(f"{n} {p * 100:.2f} %" for n, p in points.items())
            )
        tolerances = {name: t.tolerance for name, t in timings.items()}
        worst = min(tolerances.values())
        print(f"\n  Tolerance commune la plus contraignante : {worst * 100:.4f} %")
        print(f"  Quartz 24 MHz a 20 ppm = 0.0020 % -> marge x{worst / 20e-6:.0f}")
        print(
            f"  HSI16 a +/-1 %                     -> {1.0 / (worst * 100):.1f} fois trop imprecis"
        )

    if problems:
        print("\nECHEC :", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("\nTous les temps de bit sont corrects et alignes.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="verifie les board.h du depot et sort en erreur si besoin",
    )
    parser.add_argument(
        "--clock",
        type=float,
        help="horloge noyau en MHz, pour enumerer les configurations",
    )
    parser.add_argument("--controller", choices=sorted(LIMITS), default="fdcan")
    parser.add_argument("--bitrate", type=int, default=TARGET_BITRATE)
    parser.add_argument(
        "--top", type=int, default=10, help="nombre de configurations affichees"
    )
    args = parser.parse_args(argv)

    if args.check:
        print(f"Verification des temps de bit a {args.bitrate} bit/s :\n")
        return check()

    if args.clock is None:
        parser.error("indiquer --check ou --clock")

    clock_hz = round(args.clock * 1e6)
    candidates = enumerate_timings(args.controller, clock_hz, args.bitrate)
    if not candidates:
        print(
            f"Aucune configuration exacte pour {args.clock} MHz a {args.bitrate} bit/s."
        )
        return 1

    print(
        f"Configurations pour {args.controller} a {args.clock} MHz, "
        f"{args.bitrate} bit/s (meilleures d'abord) :\n"
    )
    for timing in candidates[: args.top]:
        marker = " <-" if abs(timing.sample_point - TARGET_SAMPLE_POINT) < 1e-9 else ""
        print(f"  {timing.describe()}{marker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
