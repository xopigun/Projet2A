"""Production des rapports de test, en Markdown et en LaTeX.

Chaque rapport suit le format demandé par le dossier : **objectif / montage /
procédure / critère de réussite / résultat mesuré / verdict**. Il est daté et
porte le **hash git du firmware testé**, afin qu'un résultat puisse toujours être
rattaché à une version précise du code.

Un verdict de réussite est refusé — quel que soit le résultat brut — si un nœud
signale une horloge non conforme, si un compteur de perte est non nul, ou si le
test a tourné sur le bus virtuel.
"""

from __future__ import annotations

import datetime as dt
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

TESTS = {
    "T1": {
        "titre": "Couche physique",
        "objectif": "Vérifier que la ligne est correctement terminée et que les niveaux "
        "différentiels sont conformes à ISO 11898-2.",
        "montage": "Banc complet, SW1 fermé, SW2 ouvert, SW3 fermé. Multimètre puis "
        "oscilloscope avec sonde différentielle sur CAN_H − CAN_L.",
        "critere": "60 Ω ± 5 % hors tension ; dominant différentiel 1,5 à 3,0 V ; "
        "récessif −50 à +50 mV.",
    },
    "T2": {
        "titre": "Débit et point d'échantillonnage",
        "objectif": "Établir que le débit réel est de 500 kbit/s et que le point "
        "d'échantillonnage est conforme.",
        "montage": "Banc en fonctionnement nominal, CANable raccordé sur J5, "
        "oscilloscope avec sonde différentielle.",
        "critere": "Temps de bit 2,000 µs, bande d'acceptation 1,990 à 2,010 µs "
        "(± 0,485 %) ; point d'échantillonnage 87,5 % ; échange sans erreur "
        "avec le CANable, dont l'oscillateur est indépendant.",
    },
    "T3": {
        "titre": "Arbitrage ARM/GO",
        "objectif": "Démontrer que trois nœuds émettant réellement au même instant sont "
        "départagés par l'arbitrage dans l'ordre des identifiants.",
        "montage": "Banc complet, N1 à N3 en fonctionnement nominal, CANable sur J5.",
        "critere": "N1 au rang 1, N2 au rang 2, N3 au rang 3 sur tous les cycles ; "
        "ARM reçus identiques sur les trois nœuds ; aucun cycle invalide.",
    },
    "T4": {
        "titre": "Encodage de l'ICD",
        "objectif": "Vérifier que l'encodage des signaux est correct de bout en bout.",
        "montage": "Banc complet, capteurs réels débranchés pour que les nœuds émettent "
        "leurs séquences déterministes.",
        "critere": "Aucun écart octet par octet sur l'ensemble des trames de l'ICD.",
    },
    "T5": {
        "titre": "Fautes physiques",
        "objectif": "Vérifier le comportement du bus face aux trois défauts physiques les "
        "plus courants.",
        "montage": "Banc complet, boîtier d'injection de fautes accessible.",
        "critere": "SW1 et SW2 dégradent le bus de façon mesurable et réversible ; "
        "SW3 laisse le reste du bus fonctionner.",
    },
    "T6": {
        "titre": "Fautes logicielles",
        "objectif": "Vérifier que le bus et les nœuds sains résistent aux comportements "
        "fautifs d'un nœud, et que ces comportements sont détectés.",
        "montage": "Banc complet, N4 en place.",
        "critere": "Chaque mode produit l'effet attendu, reste borné dans le temps et est "
        "révocable ; les nœuds sains restent en error-active.",
    },
    "T7": {
        "titre": "Isolation galvanique",
        "objectif": "Vérifier qu'un nœud placé près d'électronique de puissance ne dégrade "
        "pas le bus.",
        "montage": "Variante matérielle à concevoir (ISO1050 ou ADM3053).",
        "critere": "À fixer lors de la conception de la variante.",
    },
}


def git_hash(short: bool = True) -> str:
    """Hash git de l'arbre courant, suffixé `-dirty` si des modifications traînent."""
    try:
        args = ["git", "rev-parse", "--short" if short else "HEAD", "HEAD"]
        if not short:
            args = ["git", "rev-parse", "HEAD"]
        commit = subprocess.run(
            args, cwd=REPO_ROOT, capture_output=True, text=True, timeout=5, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        return f"{commit}-dirty" if dirty else commit
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return "inconnu"


@dataclass
class Report:
    test: str
    result_text: str
    passed: bool
    virtual: bool = False
    blockers: list[str] = field(default_factory=list)
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now())
    firmware_hash: str = field(default_factory=git_hash)

    @property
    def spec(self) -> dict:
        return TESTS.get(
            self.test, {"titre": self.test, "objectif": "", "montage": "", "critere": ""}
        )

    @property
    def verdict(self) -> str:
        """Verdict final, qui tient compte des motifs de disqualification."""
        if self.blockers:
            return "NON CONCLUANT"
        return "REUSSITE" if self.passed else "ECHEC"

    def markdown(self) -> str:
        spec = self.spec
        lines = [
            f"## {self.test} — {spec['titre']}",
            "",
            "| | |",
            "|---|---|",
            f"| **Date** | {self.timestamp:%d/%m/%Y %H:%M} |",
            f"| **Firmware** | `{self.firmware_hash}` |",
            f"| **Bus** | {'virtuel (simulation)' if self.virtual else 'banc réel'} |",
            "",
            f"**Objectif.** {spec['objectif']}",
            "",
            f"**Montage.** {spec['montage']}",
            "",
            f"**Critère de réussite.** {spec['critere']}",
            "",
            "**Résultat mesuré.**",
            "",
            "```",
            self.result_text.rstrip(),
            "```",
            "",
        ]
        if self.blockers:
            lines.append("**Motifs de non-conclusion.**")
            lines.append("")
            for blocker in self.blockers:
                lines.append(f"- {blocker}")
            lines.append("")
        lines.append(f"**Verdict : {self.verdict}**")
        lines.append("")
        return "\n".join(lines)

    def latex(self) -> str:
        spec = self.spec
        out = [
            "% ===========================================================================",
            "%  FICHIER GÉNÉRÉ par canbench report — ne pas éditer à la main.",
            "% ===========================================================================",
            rf"\subsection{{{self.test} — {_tex(spec['titre'])}}}",
            "",
            r"\begin{description}[nosep]",
            rf"  \item[Date] {self.timestamp:%d/%m/%Y %H:%M}",
            rf"  \item[Firmware] \texttt{{{_tex(self.firmware_hash)}}}",
            rf"  \item[Bus] {'virtuel (simulation)' if self.virtual else 'banc réel'}",
            rf"  \item[Objectif] {_tex(spec['objectif'])}",
            rf"  \item[Montage] {_tex(spec['montage'])}",
            rf"  \item[Critère de réussite] {_tex(spec['critere'])}",
            r"\end{description}",
            "",
            r"\begin{verbatim}",
            self.result_text.rstrip(),
            r"\end{verbatim}",
            "",
        ]
        if self.blockers:
            out.append(r"\paragraph{Motifs de non-conclusion.}")
            out.append(r"\begin{itemize}[nosep]")
            out += [rf"  \item {_tex(b)}" for b in self.blockers]
            out.append(r"\end{itemize}")
            out.append("")
        out.append(rf"\paragraph{{Verdict : \textbf{{{self.verdict}}}}}")
        out.append("")
        return "\n".join(out)

    def write(self, directory: Path) -> tuple[Path, Path]:
        directory.mkdir(parents=True, exist_ok=True)
        stamp = self.timestamp.strftime("%Y%m%d-%H%M%S")
        md = directory / f"{self.test}-{stamp}.md"
        tex = directory / f"{self.test}-{stamp}.tex"
        md.write_text(self.markdown(), encoding="utf-8", newline="\n")
        tex.write_text(self.latex(), encoding="utf-8", newline="\n")
        return md, tex


def blockers_from(
    *, virtual: bool, clock_warnings: list[str], loss_warnings: list[str]
) -> list[str]:
    """Motifs qui interdisent de prononcer une réussite."""
    blockers: list[str] = []
    if virtual:
        blockers.append(
            "Exécuté sur le bus virtuel : le simulateur reproduit le comportement attendu, "
            "il ne le démontre pas. Seule l'exécution sur le banc réel fait foi."
        )
    if clock_warnings:
        blockers.append(
            "Référence d'horloge non conforme sur "
            + ", ".join(clock_warnings)
            + " (HSI, ±1 % contre 0,485 % admissibles) : le débit n'est pas établi."
        )
    blockers += [f"Compteur de perte non nul — {w}" for w in loss_warnings]
    return blockers


def _tex(text: str) -> str:
    for old, new in (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ):
        text = text.replace(old, new)
    return text
