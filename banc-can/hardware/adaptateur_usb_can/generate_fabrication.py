"""Produit le dossier à déposer à la factory ENSEA dans fabrication/.

    python generate_fabrication.py

- gerber/ : cuivre avant et arrière, contour, sérigraphie (Gerber X2), perçages Excellon
  en mm séparés métallisés / non métallisés, plans de perçage PDF ;
- adaptateur_usb_can_gerber.zip : le contenu de gerber/, à joindre au ticket ;
- BOM : nomenclature CSV (Excel) et PDF à imprimer pour le retrait au magasin ;
- schema.pdf et implantation.pdf : aides au câblage et à la soudure.

Le PDF de la nomenclature est imprimé par Microsoft Edge en mode headless.
"""

import csv
import html
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
NAME = "adaptateur_usb_can"
SCH = HERE / f"{NAME}.kicad_sch"
PCB = HERE / f"{NAME}.kicad_pcb"
OUT = HERE / "fabrication"
GERBER = OUT / "gerber"
CLI = r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# Valeur -> (désignation à demander au magasin, remarque)
DESIGNATION = {
    "100nF": ("Condensateur céramique X7R 50 V", "découplage"),
    "10uF": ("Condensateur céramique X5R 16 V", "entrée 5 V du régulateur"),
    "22uF": ("Condensateur céramique X5R 10 V", "sortie 3,3 V, stabilité de l'AMS1117"),
    "1uF": ("Condensateur céramique X7R 16 V", "VDDA"),
    "4.7uF": ("Condensateur céramique X5R 10 V", "réservoir 3,3 V"),
    "22pF": ("Condensateur céramique C0G/NP0 50 V", "à ajuster selon la CL du quartz"),
    "PWR vert": ("LED verte", ""),
    "RX vert": ("LED verte", ""),
    "TX jaune": ("LED jaune", ""),
    "500mA": ("Fusible réarmable PTC, 500 mA maintenu, 6 V mini", ""),
    "USB_B": ("Embase USB type B femelle coudée, traversante", "type OST USB-B1HSW6"),
    "DB9 mâle": ("Embase SUB-D 9 points mâle coudée 90°, pour CI", "brochage CiA 303-1"),
    "SWD": ("Barrette mâle sécable 1 × 5, pas 2,54 mm", ""),
    "TERM": ("Barrette mâle 1 × 2, pas 2,54 mm + cavalier", "terminaison 120 Ω"),
    "1k": ("Résistance 1 %, 1/4 W", ""),
    "0R": ("Résistance 0 Ω (ou strap)", "CH340C en mode 3,3 V"),
    "10k": ("Résistance 1 %, 1/4 W", ""),
    "120R": ("Résistance 1 %, 1/4 W", "terminaison CAN"),
    "RESET": ("Bouton poussoir 6 × 6 mm, traversant", ""),
    "BOOT0": ("Bouton poussoir 6 × 6 mm, traversant", ""),
    "STM32G431KBT6": ("Microcontrôleur STM32G431KBT6, LQFP32", "pas 0,8 mm"),
    "CH340C": ("Pont USB-UART CH340C, SOIC-16", "version C : sans quartz externe"),
    "TJA1051T/3": ("Transceiver CAN TJA1051T/3, SOIC-8", "suffixe /3 : broche VIO"),
    "AMS1117-3.3": ("Régulateur linéaire 3,3 V AMS1117-3.3, SOT-223", ""),
    "USBLC6-2SC6": ("Protection ESD USB USBLC6-2SC6, SOT-23-6", ""),
    "8MHz": ("Quartz 8 MHz HC-49/U, traversant", "noter sa capacité de charge CL"),
}


def cli(*args):
    subprocess.run([CLI, *args], check=True, capture_output=True)


def boitier(footprint):
    name = footprint.split(":")[1]
    for key in ("1206", "LQFP-32", "SOIC-16", "SOIC-8", "SOT-223", "SOT-23-6", "HC49"):
        if key in name:
            return key
    return "traversant"


def bom():
    raw = Path(tempfile.gettempdir()) / f"{NAME}_bom.csv"
    cli("sch", "export", "bom", "--fields", "Reference,Value,Footprint,${QUANTITY}",
        "--group-by", "Value,Footprint", "--ref-range-delimiter", "", "-o", str(raw), str(SCH))
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
<title>Nomenclature adaptateur USB-CAN</title>
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
<h1>Nomenclature — adaptateur USB-CAN (G69, projet 2A banc CAN)</h1>
<p>Carte 2 couches 87,7 × 41 mm, FR4 35 µm. Composants passifs en 1206 (empreintes HandSolder).
{len(rows)} lignes, {total} composants. Fichiers : {NAME}_gerber.zip.</p>
<table><tr>{"".join(f"<th>{h}</th>" for h in head)}<th>Pris</th></tr>{cells}</table>
</html>"""
    print_pdf(page, OUT / f"{NAME}_BOM.pdf")


def print_pdf(page, pdf):
    """Imprime une page HTML en PDF avec Edge headless."""
    page_path = pdf.with_suffix(".html")
    page_path.write_text(page, encoding="utf-8")
    subprocess.run(
        [EDGE, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={pdf}", page_path.as_uri()],
        check=True, capture_output=True,
    )
    page_path.unlink()


def implantation():
    """Plan d'implantation à l'échelle de la page : contours, repères et pastilles numérotées."""
    svg = OUT / "implantation.svg"
    cli("pcb", "export", "svg", "--mode-single", "--fit-page-to-board", "--exclude-drawing-sheet",
        "--black-and-white", "--sketch-pads-on-fab-layers",
        "--layers", "F.Fab,F.Silkscreen,Edge.Cuts", "-o", str(svg), str(PCB))
    page = f"""<!doctype html><html lang="fr"><meta charset="utf-8">
<title>Implantation adaptateur USB-CAN</title>
<style>@page {{ size: A4 landscape; margin: 10mm; }} body {{ font: 10pt Arial, sans-serif; margin: 0; }}
h1 {{ font-size: 13pt; margin: 0 0 4mm; }} img {{ width: 100%; }}</style>
<h1>Implantation, face avant — adaptateur USB-CAN (G69)</h1>
<img src="{svg.name}"></html>"""
    print_pdf(page, OUT / "implantation.pdf")
    svg.unlink()


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
    bom()
    for f in sorted(OUT.rglob("*")):
        if f.is_file():
            print(f.relative_to(HERE))


if __name__ == "__main__":
    main()
