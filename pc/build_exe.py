"""Construit le logiciel Windows ``dist/BancCAN.exe`` avec PyInstaller.

Usage, depuis la racine du dépôt ou depuis ``pc/`` :

    python pc/build_exe.py

Prérequis : ``python -m pip install pyinstaller``. Pour piloter un CANable réel,
installer aussi son pilote python-can **avant** la construction, pour qu'il soit
embarqué : ``python -m pip install -e "pc[slcan]"`` et/ou ``"pc[gs-usb]"``.

L'exécutable est un fichier unique, sans console. Il n'est pas versionné : il se
reconstruit en une minute depuis le dépôt, qui fait seul foi.
"""

from __future__ import annotations

import struct
import subprocess
import sys
import zlib
from pathlib import Path

PC_DIR = Path(__file__).resolve().parent
REPO = PC_DIR.parent
BUILD = REPO / "build" / "exe"
DIST = REPO / "dist"


# ---------------------------------------------------------------------------
#  Icône : dessinée ici, pour ne dépendre d'aucune bibliothèque d'images
# ---------------------------------------------------------------------------


def _png(size: int, pixel) -> bytes:
    rows = []
    for y in range(size):
        row = bytearray([0])  # filtre « aucun »
        for x in range(size):
            row += bytes(pixel(x, y))
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # RVBA 8 bits
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


def _icon_pixel(size: int):
    """Carré bleu arrondi, paire CAN_H / CAN_L et trois nœuds."""
    radius = size * 0.2

    def inside_rounded(x: float, y: float) -> bool:
        cx = min(max(x, radius), size - radius)
        cy = min(max(y, radius), size - radius)
        return (x - cx) ** 2 + (y - cy) ** 2 <= radius**2

    def pixel(x: int, y: int):
        fx, fy = x + 0.5, y + 0.5
        if not inside_rounded(fx, fy):
            return (0, 0, 0, 0)
        u, v = fx / size, fy / size
        if 0.60 <= v <= 0.66 and 0.12 <= u <= 0.88:
            return (255, 110, 110, 255)  # CAN_H
        if 0.72 <= v <= 0.78 and 0.12 <= u <= 0.88:
            return (255, 255, 255, 255)  # CAN_L
        for node in (0.28, 0.5, 0.72):
            if abs(u - node) <= 0.09 and 0.22 <= v <= 0.44:
                return (255, 255, 255, 255)  # nœud
            if abs(u - node) <= 0.018 and 0.44 <= v <= 0.72:
                return (220, 230, 255, 255)  # dérivation
        return (34, 87, 214, 255)

    return pixel


def write_icon(path: Path) -> Path:
    sizes = (16, 32, 48, 256)
    images = [_png(size, _icon_pixel(size)) for size in sizes]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    for size, data in zip(sizes, images, strict=True):
        dim = 0 if size == 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entries + b"".join(images))
    return path


# ---------------------------------------------------------------------------
#  Construction
# ---------------------------------------------------------------------------


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller manque : python -m pip install pyinstaller")
        return 1

    icon = write_icon(BUILD / "BancCAN.ico")
    entry = BUILD / "banc_can.py"
    entry.write_text(
        "from canbench.gui.app import main\n\nraise SystemExit(main())\n", encoding="utf-8"
    )

    static = PC_DIR / "canbench" / "gui" / "static"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "BancCAN",
        "--icon",
        str(icon),
        "--paths",
        str(PC_DIR),
        "--add-data",
        f"{static}{';' if sys.platform == 'win32' else ':'}canbench/gui/static",
        # python-can charge ses interfaces par leur nom, à l'exécution :
        # l'analyse statique de PyInstaller ne les voit pas.
        "--collect-submodules",
        "can.interfaces",
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD / "work"),
        "--specpath",
        str(BUILD),
        str(entry),
    ]
    print(" ".join(command))
    result = subprocess.run(command, cwd=PC_DIR, check=False)
    if result.returncode == 0:
        print(f"\nLogiciel construit : {DIST / 'BancCAN.exe'}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
