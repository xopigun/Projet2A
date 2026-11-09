"""Produit les images de la présentation (images/) depuis les projets KiCad du dépôt.

    python generer_images.py

- rendus 3D de l'adaptateur USB-CAN (dessus, dessous, vue isométrique) par kicad-cli ;
- schéma de l'adaptateur, PCB de l'adaptateur et schéma de câblage du bus en PNG haute
  définition : export SVG par kicad-cli, puis capture par Microsoft Edge en mode headless.

Les captures du moniteur (captures/) et de la simulation 3D se font à la main.
"""

import re
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
HW = HERE.parents[1] / "hardware"
ADAPT = HW / "adaptateur_usb_can" / "adaptateur_usb_can"
CABLAGE = HW / "cablage_bus_can" / "cablage_bus_can"
OUT = HERE / "images"
CLI = r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
LARGEUR = 2400  # pixels de l'image finale


def cli(*args):
    subprocess.run([CLI, *args], check=True, capture_output=True)


def svg_en_png(svg, png, fond="white"):
    """Capture un SVG à LARGEUR pixels de large, hauteur déduite de son viewBox."""
    vb = re.search(r'viewBox="([\d.\s-]+)"', svg.read_text(encoding="utf-8")).group(1)
    _, _, w, h = (float(v) for v in vb.split())
    hauteur = round(LARGEUR * h / w)
    page = svg.with_suffix(".html")
    page.write_text(
        f'<!doctype html><meta charset="utf-8"><style>html,body{{margin:0;background:{fond}}}'
        f'img{{display:block;width:{LARGEUR}px;height:{hauteur}px}}</style>'
        f'<img src="{svg.name}">', encoding="utf-8")
    subprocess.run(
        [EDGE, "--headless", "--disable-gpu", "--hide-scrollbars",
         f"--window-size={LARGEUR},{hauteur}", f"--screenshot={png}", page.as_uri()],
        check=True, capture_output=True)


def schema(sch, png):
    with tempfile.TemporaryDirectory() as tmp:
        cli("sch", "export", "svg", "--exclude-drawing-sheet", "-o", tmp, str(sch))
        svg_en_png(next(Path(tmp).glob("*.svg")), png)


def pcb(png):
    with tempfile.TemporaryDirectory() as tmp:
        svg = Path(tmp) / "pcb.svg"
        cli("pcb", "export", "svg", "--mode-single", "--fit-page-to-board",
            "--exclude-drawing-sheet", "--layers", "B.Cu,F.Cu,F.Silkscreen,Edge.Cuts",
            "-o", str(svg), str(ADAPT.with_suffix(".kicad_pcb")))
        svg_en_png(svg, png)


def rendus_3d():
    board = str(ADAPT.with_suffix(".kicad_pcb"))
    vues = {
        "adaptateur_3d_dessus.png": ["--side", "top"],
        "adaptateur_3d_dessous.png": ["--side", "bottom"],
        # L'espace devant l'angle négatif empêche kicad-cli de le prendre pour une option.
        "adaptateur_3d_iso.png": ["--side", "top", "--rotate", " -40,0,30", "--perspective"],
    }
    for nom, args in vues.items():
        cli("pcb", "render", "--quality", "high", "--width", str(LARGEUR),
            "--height", str(LARGEUR * 9 // 16), "--zoom", "0.9", *args,
            "-o", str(OUT / nom), board)


def main():
    OUT.mkdir(exist_ok=True)
    rendus_3d()
    schema(ADAPT.with_suffix(".kicad_sch"), OUT / "adaptateur_schema.png")
    pcb(OUT / "adaptateur_pcb.png")
    schema(CABLAGE.with_suffix(".kicad_sch"), OUT / "cablage_bus_can.png")
    for f in sorted(OUT.iterdir()):
        print(f.relative_to(HERE))


if __name__ == "__main__":
    main()
