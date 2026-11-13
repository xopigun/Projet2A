"""Génération de l'extrait LaTeX de la section 6 du dossier (configuration logicielle).

Les valeurs sont **relues dans les `board.h`**, jamais recopiées : c'est la seule
façon de garantir que le tableau du dossier décrit bien le firmware qui tourne.
Les tolérances d'oscillateur sont recalculées par `scripts/bit_timing.py`.

Les quatre nœuds sont des Nucleo-G431KB : une seule colonne. Une valeur
illisible dans le board.h est signalée dans le tableau plutôt qu'omise.
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
    g431 = bt.read_board("nucleo_g431kb")

    def cell(timing, attribute, formatter=str) -> str:
        if timing is None:
            return NOT_PORTED
        return formatter(getattr(timing, attribute))

    out = [
        HEADER,
        r"\begin{table}[H]",
        r"\centering\small",
        r"\begin{tabular}{lc}",
        r"\toprule",
        r"\textbf{Paramètre} & \textbf{N1--N4 (STM32G431)} \\",
        r"\midrule",
        r"Périphérique & FDCAN1, mode \emph{Classic} \\",
        r"Référence d'horloge & HSE \SI{24}{MHz} (quartz, \SI{20}{ppm}) \\",
        rf"Horloge noyau CAN & {_clock(g431)} \\",
        rf"Prescaler & {cell(g431, 'prescaler')} \\",
        rf"Durée du bit & {_nbt(g431)} \\",
        rf"Segments (sync + 1 + 2) & {_segments(g431)} \\",
        rf"SJW & {cell(g431, 'sjw')} \\",
        rf"Point d'échantillonnage & {_sp(g431)} \\",
        rf"Tolérance d'oscillateur & {_tol(g431)} \\",
        r"Débit & \SI{500}{kbit/s} \\",
        r"\midrule",
        r"Filtres d'acceptation & aucun \\",
        r"Retransmission automatique & activée \\",
        r"Reprise après \emph{bus-off} & logicielle (\texttt{CCCR.INIT}) \\",
        r"Mode silencieux & \texttt{CCCR.MON} \\",
        r"Bouclage interne & \texttt{FDCAN\_MODE\_INTERNAL\_LOOPBACK} \\",
        r"\bottomrule",
        r"\end{tabular}",
    ]

    caption = (
        r"Configuration retenue du contrôleur CAN, commune aux quatre nœuds. "
        r"Valeurs relues dans le \texttt{board.h} de la Nucleo-G431KB et vérifiées par "
        r"\texttt{scripts/bit\_timing.py}."
    )

    out += [
        rf"\caption{{{caption}}}",
        r"\label{tab:config-logicielle}",
        r"\end{table}",
        "",
    ]
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
