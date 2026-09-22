"""Génération de l'extrait LaTeX de la section 6 du dossier (configuration logicielle).

Les valeurs sont **relues dans les `board.h`**, jamais recopiées : c'est la seule
façon de garantir que le tableau du dossier décrit bien le firmware qui tourne.
Les tolérances d'oscillateur sont recalculées par `scripts/bit_timing.py`.

Une carte absente (le F103, tant que le lot 5 n'est pas fait) est signalée dans
le tableau plutôt que silencieusement omise.
"""

from __future__ import annotations

import importlib.util
import sys

from .model import REPO_ROOT, Icd

HEADER = """\
% ===========================================================================
%  FICHIER GÉNÉRÉ — NE PAS ÉDITER À LA MAIN
%  Produit par tools/codegen à partir des firmware/boards/*/board.h.
%  Regénérer :  python -m tools.codegen
% ===========================================================================
"""


def _bit_timing_module():
    """Charge scripts/bit_timing.py sans en faire un paquet importable."""
    path = REPO_ROOT / "scripts" / "bit_timing.py"
    spec = importlib.util.spec_from_file_location("bench_bit_timing", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("bench_bit_timing", module)
    spec.loader.exec_module(module)
    return module


NOT_PORTED = r"\itshape non porté"


def _num(value: float, decimals: int = 2) -> str:
    """Formate un nombre pour siunitx, qui applique ensuite locale=FR."""
    return f"{value:.{decimals}f}"


def generate(icd: Icd) -> str:
    bt = _bit_timing_module()

    rows: list[tuple[str, object]] = []
    for board_name in bt.BOARDS:
        timing = bt.read_board(board_name)
        rows.append((board_name, timing))

    out = [HEADER, r"\begin{table}[H]", r"\centering\small",
           r"\begin{tabular}{lcc}", r"\toprule",
           r"\textbf{Paramètre} & \textbf{N1--N3 (STM32G431)} & \textbf{N4 (STM32F103)} \\",
           r"\midrule"]

    g431 = dict(rows).get("nucleo_g431kb")
    f103 = dict(rows).get("bluepill_f103")

    def cell(timing, attribute, formatter=str) -> str:
        if timing is None:
            return NOT_PORTED
        return formatter(getattr(timing, attribute))

    out += [
        r"Périphérique & FDCAN1, mode \emph{Classic} & bxCAN \\",
        r"Référence d'horloge & HSE \SI{24}{MHz} (quartz, \SI{20}{ppm}) & "
        r"HSE \SI{8}{MHz} \\",
        rf"Horloge noyau CAN & {_clock(g431)} & {_clock(f103)} \\",
        rf"Prescaler & {cell(g431, 'prescaler')} & {cell(f103, 'prescaler')} \\",
        rf"Durée du bit & {_nbt(g431)} & {_nbt(f103)} \\",
        rf"Segments (sync + 1 + 2) & "
        rf"{_segments(g431)} & {_segments(f103)} \\",
        rf"SJW & {cell(g431, 'sjw')} & {cell(f103, 'sjw')} \\",
        rf"Point d'échantillonnage & {_sp(g431)} & {_sp(f103)} \\",
        rf"Tolérance d'oscillateur & {_tol(g431)} & {_tol(f103)} \\",
        r"Débit & \SI{500}{kbit/s} & \SI{500}{kbit/s} \\",
        r"\midrule",
        r"Filtres d'acceptation & aucun & aucun \\",
        r"Retransmission automatique & activée & activée \\",
        r"Reprise après \emph{bus-off} & logicielle (\texttt{CCCR.INIT}) & "
        r"matérielle (\texttt{ABOM}) \\",
        r"Mode silencieux & \texttt{CCCR.MON} & \texttt{BTR.SILM} \\",
        r"Bouclage interne & \texttt{FDCAN\_MODE\_INTERNAL\_LOOPBACK} & "
        r"\texttt{BTR.LBKM} \\",
        r"\bottomrule",
        r"\end{tabular}",
    ]

    caption = (
        r"Configuration retenue du contrôleur CAN. Le point d'échantillonnage est "
        r"identique sur les deux familles, ce dont dépend la tolérance d'écart "
        r"d'horloge commune. Valeurs relues dans les \texttt{board.h} et vérifiées par "
        r"\texttt{scripts/bit\_timing.py}."
    )
    if f103 is None:
        caption += (
            r" La colonne N4 est calculée mais le port n'est pas encore écrit : il "
            r"attend RM0008, DS5319 et le schéma de la carte."
        )

    out += [rf"\caption{{{caption}}}", r"\label{tab:config-logicielle}", r"\end{table}", ""]
    return "\n".join(out)


def _clock(timing) -> str:
    if timing is None:
        return NOT_PORTED
    return rf"\SI{{{timing.clock_hz // 1000000}}}{{MHz}}"


def _nbt(timing) -> str:
    if timing is None:
        return NOT_PORTED
    return f"{timing.nbt} tq"


def _segments(timing) -> str:
    if timing is None:
        return NOT_PORTED
    return f"1 + {timing.tseg1} + {timing.tseg2}"


def _sp(timing) -> str:
    if timing is None:
        return NOT_PORTED
    return rf"\SI{{{_num(timing.sample_point * 100)}}}{{\percent}}"


def _tol(timing) -> str:
    if timing is None:
        return NOT_PORTED
    return rf"\SI{{{_num(timing.tolerance * 100, 3)}}}{{\percent}}"
