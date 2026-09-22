"""Point d'entrée du générateur : YAML -> C, Python, DBC, LaTeX, vecteurs.

    python -m tools.codegen            regénère tous les fichiers
    python -m tools.codegen --check    vérifie qu'ils sont à jour, sans rien écrire
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import (gen_c, gen_config_latex, gen_dbc, gen_latex, gen_python,
               gen_vectors_c, vectors)
from .model import ICD_PATH, REPO_ROOT, Icd, IcdError, load


def _outputs(icd: Icd) -> dict[Path, str]:
    return {
        REPO_ROOT / "firmware" / "common" / "icd_gen" / "icd_gen.h": gen_c.generate_header(icd),
        REPO_ROOT / "firmware" / "common" / "icd_gen" / "icd_gen.c": gen_c.generate_source(icd),
        REPO_ROOT / "pc" / "canbench" / "icd_gen.py": gen_python.generate(icd),
        REPO_ROOT / "icd" / "bench.dbc": gen_dbc.generate(icd),
        REPO_ROOT / "icd" / "reference_vectors.json": vectors.render(icd),
        REPO_ROOT / "firmware" / "tests_host" / "generated" / "icd_vectors.h":
            gen_vectors_c.generate_header(),
        REPO_ROOT / "firmware" / "tests_host" / "generated" / "icd_vectors.c":
            gen_vectors_c.generate_source(icd),
        REPO_ROOT / "docs" / "latex" / "icd_encoding_table.tex":
            gen_latex.generate_encoding_table(icd),
        REPO_ROOT / "docs" / "latex" / "icd_reserved_ids.tex":
            gen_latex.generate_reserved_table(icd),
        REPO_ROOT / "docs" / "latex" / "config_logicielle.tex":
            gen_config_latex.generate(icd),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.codegen",
        description="Génère le code et la documentation à partir de icd/bench_icd.yaml.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="vérifie que les fichiers générés sont à jour, sans rien écrire",
    )
    parser.add_argument("--icd", type=Path, default=ICD_PATH, help="chemin de l'ICD")
    parser.add_argument("--quiet", action="store_true", help="n'affiche que les erreurs")
    args = parser.parse_args(argv)

    try:
        icd = load(args.icd)
    except IcdError as error:
        print(f"erreur : {error}", file=sys.stderr)
        return 2

    for warning in icd.warnings:
        print(f"avertissement : {warning}", file=sys.stderr)

    outputs = _outputs(icd)
    stale: list[Path] = []

    for path, content in outputs.items():
        existing = path.read_text(encoding="utf-8") if path.exists() else None
        if existing == content:
            if not args.quiet and not args.check:
                print(f"  inchangé  {path.relative_to(REPO_ROOT)}")
            continue

        if args.check:
            stale.append(path)
            continue

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        if not args.quiet:
            verb = "créé    " if existing is None else "mis à jour"
            print(f"  {verb}  {path.relative_to(REPO_ROOT)}")

    if args.check and stale:
        print(
            "Le code généré n'est pas à jour. Fichiers concernés :",
            file=sys.stderr,
        )
        for path in stale:
            print(f"  - {path.relative_to(REPO_ROOT)}", file=sys.stderr)
        print("Lancer : python -m tools.codegen", file=sys.stderr)
        return 1

    if not args.quiet:
        total = sum(len(f["cases"]) for f in vectors.build(icd)["frames"])
        print(
            f"{len(outputs)} fichiers, {len(icd.default.messages)} trames, "
            f"{total} vecteurs de référence."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
