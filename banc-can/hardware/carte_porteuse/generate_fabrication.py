"""Produit le dossier de la carte porteuse à déposer à la factory ENSEA, dans fabrication/.

    python generate_fabrication.py

- gerber/ : cuivre avant et arrière, contour, sérigraphie (Gerber X2), perçages Excellon
  en mm séparés métallisés / non métallisés, plans de perçage PDF ;
- carte_porteuse_gerber.zip : le contenu de gerber/, à joindre au ticket ;
- BOM : nomenclature CSV (Excel) et PDF à imprimer pour le retrait au magasin ;
- schema.pdf et implantation.pdf : aides au câblage et à la soudure ;
- pcb_echelle_1.pdf : PCB à l'échelle 1:1 sur A4, à imprimer en taille réelle.

Le PDF de la nomenclature est imprimé par Microsoft Edge en mode headless.
"""

import csv
import html
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from pypdf import PdfWriter

HERE = Path(__file__).parent
NAME = "carte_porteuse"
SCH = HERE / f"{NAME}.kicad_sch"
PCB = HERE / f"{NAME}.kicad_pcb"
OUT = HERE / "fabrication"
GERBER = OUT / "gerber"
CLI = r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# Valeur -> (désignation à demander au magasin, remarque)
DESIGNATION = {
    "TJA1051T/3": ("Transceiver CAN TJA1051T/3, SOIC-8", "suffixe /3 : broche VIO (3,3 V)"),
    "100nF": ("Condensateur céramique X7R 50 V", "découplage VCC et VIO du transceiver"),
    "120R": ("Résistance 1 %, 1/8 W", "terminaison CAN, active avec un cavalier sur TERM"),
    "1k": ("Résistance 1 %, 1/8 W", "LED"),
    "0R": ("Résistance 0 ohm (ou strap)", "R7 : broche S à la masse ; R9, R10 : ordre GND/VCC de l'OLED"),
    "ERR rouge": ("LED rouge", "error-passive"),
    "BUS-OFF jaune": ("LED jaune", "bus-off"),
    "Nucleo CN3": ("Barrette femelle 1 x 15, pas 2,54 mm", "reçoit la Nucleo-G431KB"),
    "Nucleo CN4": ("Barrette femelle 1 x 15, pas 2,54 mm", "reçoit la Nucleo-G431KB"),
    "Bus entrée": ("Bornier à vis 3 points, pas 5,08 mm (type Phoenix MKDS 1,5/3-5,08)", "bus CAN : H, L, G"),
    "Bus sortie": ("Bornier à vis 3 points, pas 5,08 mm (type Phoenix MKDS 1,5/3-5,08)", "bus CAN : H, L, G"),
    "OLED": ("Barrette femelle 1 x 4, pas 2,54 mm", "écran OLED SSD1306 0,96\" (I2C)"),
    "MPU-6050": ("Barrette femelle 1 x 8, pas 2,54 mm", "module GY-521, sur N2 seulement"),
    "TERM": ("Barrette mâle 1 x 2, pas 2,54 mm + cavalier", "terminaison 120 ohms ; sur N4, câblée vers SW1"),
}


def cli(*args):
    subprocess.run([CLI, *args], check=True, capture_output=True)


def boitier(footprint):
    name = footprint.split(":")[1]
    if "3216-18" in name:
        return "tantale A (3216)"
    for key in ("0805", "1206", "LQFP-32", "SOIC-16", "SOIC-8", "SOT-223", "SOT-23-6", "5032", "B3U"):
        if key in name:
            return key
    return "traversant"


def bom():
    raw = Path(tempfile.gettempdir()) / f"{NAME}_bom.csv"
    cli("sch", "export", "bom", "--fields", "Reference,Value,Footprint,${QUANTITY}",
        "--group-by", "Value,Footprint", "--exclude-dnp", "--ref-range-delimiter", "", "-o", str(raw), str(SCH))
    rows = []
    with raw.open(encoding="utf-8") as fh:
        for ref, value, footprint, qty in list(csv.reader(fh))[1:]:
            desig, remark = DESIGNATION[value]
            rows.append((qty, ref.replace(",", ", "), desig, value, boitier(footprint), remark))
    rows.sort(key=lambda r: (r[1][0], r[1]))
    head = ("Qté", "Repères", "Désignation", "Valeur", "Boîtier", "Remarque")

    with (OUT / f"{NAME}_BOM.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        csv.writer(fh, delimiter=";").writerows([head, *rows])

    cells = "".join(
        "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "<td class=box></td></tr>"
        for r in rows
    )
    total = sum(int(r[0]) for r in rows)
    page = f"""<!doctype html><html lang="fr"><meta charset="utf-8">
<title>Nomenclature carte porteuse</title>
<style>
 @page {{ size: A4 landscape; margin: 12mm; }}
 body {{ font: 10pt Arial, sans-serif; }}
 h1 {{ font-size: 14pt; margin: 0 0 2mm; }}
 p {{ margin: 0 0 4mm; }}
 table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ border: 1px solid #555; padding: 1.5mm 2mm; text-align: left; }}
 th {{ background: #ddd; }}
 td:first-child {{ text-align: center; }}
 .box {{ width: 12mm; }}
</style>
<h1>Nomenclature — carte porteuse d'un nœud (G69, projet 2A banc CAN)</h1>
<p>Carte 2 couches 65 × 50 mm, FR4 35 µm, composants sur la face avant. Passifs en 0805 (empreintes HandSolder). Quantités pour une carte (4 à fabriquer). Composants non montés exclus.
{len(rows)} lignes, {total} composants. Fichiers : {NAME}_gerber.zip.</p>
<table><tr>{"".join(f"<th>{h}</th>" for h in head)}<th>Pris</th></tr>{cells}</table>
</html>"""
    print_pdf(page, OUT / f"{NAME}_BOM.pdf")


def print_pdf(page, pdf):
    """Imprime une page HTML en PDF avec Edge headless."""
    page_path = pdf.with_suffix(".html")
    page_path.write_text(page, encoding="utf-8")
    # Profil temporaire : sinon, si Edge est déjà ouvert, la commande lui est passée et
    # rend la main sans rien imprimer.
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run(
            [EDGE, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--user-data-dir={profile}", f"--print-to-pdf={pdf}", page_path.as_uri()],
            check=True, capture_output=True,
        )
    page_path.unlink()
    assert pdf.exists(), f"{pdf.name} n'a pas été produit par Edge"


def implantation():
    """Plan d'implantation à l'échelle de la page : contours, repères et pastilles numérotées."""
    svg = OUT / "implantation.svg"
    cli("pcb", "export", "svg", "--mode-single", "--fit-page-to-board", "--exclude-drawing-sheet",
        "--black-and-white", "--sketch-pads-on-fab-layers",
        "--layers", "F.Fab,F.Silkscreen,Edge.Cuts", "-o", str(svg), str(PCB))
    page = f"""<!doctype html><html lang="fr"><meta charset="utf-8">
<title>Implantation carte porteuse</title>
<style>@page {{ size: A4 landscape; margin: 10mm; }} body {{ font: 10pt Arial, sans-serif; margin: 0; }}
h1 {{ font-size: 13pt; margin: 0 0 4mm; }} img {{ width: 100%; }}</style>
<h1>Implantation, face avant — carte porteuse (G69)</h1>
<img src="{svg.name}"></html>"""
    print_pdf(page, OUT / "implantation.pdf")
    svg.unlink()


def echelle_1():
    """PCB à l'échelle 1:1 sur A4 : page 1 face avant, page 2 face arrière vue de dessus.

    À imprimer en « taille réelle » (100 %, sans ajustement à la page) : la carte doit
    alors mesurer 65 × 50 mm, ce qui permet de poser les composants sur le papier.
    """
    pages = []
    for i, layers in enumerate(("F.Cu,F.Silkscreen,Edge.Cuts", "B.Cu,Edge.Cuts")):
        page = OUT / f"_page{i}.pdf"
        cli("pcb", "export", "pdf", "--mode-single", "--include-border-title",
            "--layers", layers, "-o", str(page), str(PCB))
        pages.append(page)
    writer = PdfWriter()
    for page in pages:
        writer.append(str(page))
        page.unlink()
    with open(OUT / "pcb_echelle_1.pdf", "wb") as fh:
        writer.write(fh)


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    GERBER.mkdir(parents=True)
    cli("pcb", "export", "gerbers", "--layers", "F.Cu,B.Cu,Edge.Cuts,F.Silkscreen",
        "--no-protel-ext", "-o", f"{GERBER}\\", str(PCB))
    cli("pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm",
        "--excellon-separate-th", "--generate-map", "--map-format", "pdf",
        "-o", f"{GERBER}\\", str(PCB))
    with zipfile.ZipFile(OUT / f"{NAME}_gerber.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(GERBER.iterdir()):
            z.write(f, f.name)
    cli("sch", "export", "pdf", "-o", str(OUT / "schema.pdf"), str(SCH))
    implantation()
    echelle_1()
    bom()
    for f in sorted(OUT.rglob("*")):
        if f.is_file():
            print(f.relative_to(HERE))


if __name__ == "__main__":
    main()
