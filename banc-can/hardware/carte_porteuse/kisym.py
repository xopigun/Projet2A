"""Lecture des bibliothèques de symboles KiCad 9 (.kicad_sym).

Juste ce qu'il faut à generate_schematic.py : lire un symbole, l'aplatir
quand il hérite d'un autre (`extends`), et lister ses broches.
"""

import os
import re
from pathlib import Path

KICAD_SYMBOLS = Path(
    os.environ.get("KICAD9_SYMBOL_DIR", r"C:\Program Files\KiCad\9.0\share\kicad\symbols")
)

_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))')


class Str(str):
    """Chaîne qui était entre guillemets dans le fichier source."""


def parse(text):
    stack, cur, pos = [], [], 0
    while True:
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
        if m.group(1):
            stack.append(cur)
            cur = []
        elif m.group(2):
            done, cur = cur, stack.pop()
            cur.append(done)
        elif m.group(3) is not None:
            cur.append(Str(m.group(3).replace('\\"', '"').replace("\\\\", "\\")))
        else:
            cur.append(m.group(4))
    return cur[0]


def dump(node):
    if isinstance(node, list):
        return "(" + " ".join(dump(n) for n in node) + ")"
    if isinstance(node, Str):
        return '"' + node.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return str(node)


def find(node, key):
    return [n for n in node if isinstance(n, list) and n and n[0] == key]


def first(node, key):
    found = find(node, key)
    return found[0] if found else None


_libs = {}


def _library(lib):
    if lib not in _libs:
        tree = parse((KICAD_SYMBOLS / f"{lib}.kicad_sym").read_text(encoding="utf-8"))
        _libs[lib] = {s[1]: s for s in find(tree, "symbol")}
    return _libs[lib]


def load(lib_id):
    """Symbole aplati, nommé `lib:nom` comme dans lib_symbols d'un schéma."""
    lib, name = lib_id.split(":")
    sym = _library(lib)[name]
    ext = first(sym, "extends")
    if ext:
        parent = load(f"{lib}:{ext[1]}")
        props = {p[1]: p for p in find(sym, "property")}
        merged = [n for n in parent[2:] if not (isinstance(n, list) and n[0] == "property")]
        parent_props = [p for p in find(parent, "property") if p[1] not in props]
        body = parent_props + list(props.values()) + merged
        pname = parent[1].split(":")[1]
        for n in body:
            if isinstance(n, list) and n[0] == "symbol":
                n[1] = Str(n[1].replace(pname, name, 1))
        sym = ["symbol", Str(name)] + body
    sym = [n for n in sym if not (isinstance(n, list) and n[0] == "extends")]
    out = list(sym)
    out[1] = Str(lib_id)
    return out


def pins(sym):
    """Liste (numéro, nom, type, x, y, angle) en coordonnées bibliothèque (Y vers le haut)."""
    result = []
    for unit in find(sym, "symbol"):
        for p in find(unit, "pin"):
            at = first(p, "at")
            result.append(
                (
                    first(p, "number")[1],
                    first(p, "name")[1],
                    p[1],
                    float(at[1]),
                    float(at[2]),
                    int(float(at[3])) if len(at) > 3 else 0,
                )
            )
    return result
