"""Vérifie qu'aucun vecteur d'interruption utilisé ne retombe sur Default_Handler.

Le fichier de démarrage de ST déclare chaque vecteur comme alias faible de
``Default_Handler``, une boucle infinie. Un gestionnaire oublié ne provoque ni
erreur de compilation ni avertissement : le nœud se fige à la première
interruption, en silence. Ce script lit la table des symboles de l'exécutable
et échoue si l'un des vecteurs listés a la même adresse que ``Default_Handler``.

Usage (lancé automatiquement après chaque édition de liens) :

    python scripts/check_vectors.py --nm arm-none-eabi-nm firmware.elf SysTick_Handler ...
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def symbols(nm: str, elf: str) -> dict[str, str]:
    output = subprocess.run(
        [nm, elf], capture_output=True, text=True, check=True
    ).stdout
    table: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 3:
            address, _kind, name = parts
            table[name] = address
    return table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nm", default="arm-none-eabi-nm")
    parser.add_argument("elf")
    parser.add_argument("handlers", nargs="+", help="vecteurs qui doivent être définis")
    args = parser.parse_args(argv)

    table = symbols(args.nm, args.elf)
    default = table.get("Default_Handler")
    if default is None:
        print(f"{args.elf} : Default_Handler introuvable", file=sys.stderr)
        return 1

    missing = [h for h in args.handlers if table.get(h, default) == default]
    if missing:
        print(
            f"ERREUR {args.elf} : vecteur(s) sans gestionnaire, qui boucleraient dans "
            f"Default_Handler : {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    print(f"Vecteurs verifies : {', '.join(args.handlers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
