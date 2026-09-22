"""Génération des extraits LaTeX à inclure dans le dossier et dans les ICD.

Deux fichiers, tous deux destinés à un ``\\input{}`` :

  - ``docs/latex/icd_encoding_table.tex``  : une ligne par signal ;
  - ``docs/latex/icd_reserved_ids.tex``    : les identifiants réservés au banc.

Les deux supposent ``booktabs``, ``longtable`` et ``siunitx``, déjà chargés par le
dossier de définition.
"""

from __future__ import annotations

from .model import Icd, Signal

HEADER = """\
% ===========================================================================
%  FICHIER GÉNÉRÉ — NE PAS ÉDITER À LA MAIN
%  Produit par tools/codegen à partir de icd/bench_icd.yaml.
%  Regénérer :  python -m tools.codegen
% ===========================================================================
"""


def _escape(text: str) -> str:
    """Échappe les caractères spéciaux de LaTeX."""
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def _order(signal: Signal) -> str:
    return "Intel" if signal.byte_order == "little_endian" else "Motorola"


def generate_encoding_table(icd: Icd) -> str:
    profile = icd.default
    out = [
        HEADER,
        r"\begin{longtable}{llrrcccrrl}",
        r"\toprule",
        (
            r"\textbf{Trame} & \textbf{Signal} & \textbf{Oct.} & \textbf{Bit} &"
            r" \textbf{Long.} & \textbf{Ordre} & \textbf{S} &"
            r" \textbf{Facteur} & \textbf{Offset} & \textbf{Unité} \\"
        ),
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        (
            r"\textbf{Trame} & \textbf{Signal} & \textbf{Oct.} & \textbf{Bit} &"
            r" \textbf{Long.} & \textbf{Ordre} & \textbf{S} &"
            r" \textbf{Facteur} & \textbf{Offset} & \textbf{Unité} \\"
        ),
        r"\midrule",
        r"\endhead",
        r"\bottomrule",
        r"\endfoot",
    ]

    emitted: set[str] = set()
    for message in profile.messages:
        base = (
            message.name if message.node_id is None else message.name.rsplit("_", 1)[0]
        )
        if base in emitted:
            continue
        emitted.add(base)

        if not message.signals:
            out.append(
                rf"\texttt{{{_escape(base)}}} & \multicolumn{{9}}{{l}}"
                rf"{{\itshape aucun signal — {message.dlc} octets nuls}} \\"
            )
            continue

        for index, signal in enumerate(message.signals):
            label = rf"\texttt{{{_escape(base)}}}" if index == 0 else ""
            out.append(
                f"{label} & \\texttt{{{_escape(signal.name)}}} & "
                f"{signal.start_byte} & {signal.start_bit} & {signal.length} & "
                f"{_order(signal)} & {'oui' if signal.signed else 'non'} & "
                f"{_number(signal.factor)} & {_number(signal.offset)} & "
                f"{_escape(signal.unit) or '--'} \\\\"
            )
        out.append(r"\addlinespace")

    out += [
        r"\caption{Encodage des signaux de l'ICD du banc, profil « "
        + _escape(profile.name)
        + r" ». Colonne S : signal signé.}",
        r"\label{tab:icd-encodage}",
        r"\end{longtable}",
        "",
    ]
    return "\n".join(out)


def generate_reserved_table(icd: Icd) -> str:
    out = [
        HEADER,
        r"\begin{table}[H]",
        r"\centering\small",
        r"\begin{tabular}{llll}",
        r"\toprule",
        r"\textbf{Identifiant} & \textbf{Nom} & \textbf{Sens} & \textbf{Rôle} \\",
        r"\midrule",
    ]

    profile = icd.default
    for message in profile.messages:
        if message.kind != "service":
            continue
        direction = f"{_escape(message.sender)} $\\rightarrow$ " + _escape(
            ", ".join(message.receivers)
        )
        comment = _escape(message.comment)
        if len(comment) > 110:
            comment = comment[:107] + "..."
        out.append(
            rf"\texttt{{0x{message.can_id:03X}}} & \texttt{{{_escape(message.name)}}} & "
            rf"{direction} & {comment} \\"
        )

    out += [r"\midrule", r"\multicolumn{4}{l}{\textbf{Plages réservées au banc}} \\"]
    for reserved in profile.reserved_ranges:
        out.append(
            rf"\multicolumn{{2}}{{l}}{{\texttt{{0x{reserved.first:03X}--0x{reserved.last:03X}}}}} & "
            rf"\multicolumn{{2}}{{l}}{{{_escape(reserved.purpose)}}} \\"
        )

    out += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\caption{Identifiants réservés au banc (profil « "
        + _escape(profile.name)
        + r" »). Ces identifiants sont à déclarer « réservés banc, reconfigurables » "
        + r"dans les ICD partenaires : ils ne leur sont pas imposés, un profil réseau "
        + r"distinct pouvant les déplacer.}",
        r"\label{tab:icd-reserves}",
        r"\end{table}",
        "",
    ]
    return "\n".join(out)
