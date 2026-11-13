"""Produit le dossier à déposer à la factory ENSEA dans fabrication/.

    python generate_fabrication.py

- gerber/ : cuivre avant et arrière, contour, sérigraphie, pâte à braser des deux faces
  (F_Paste, B_Paste : pour découper les pochoirs du four) en Gerber X2, perçages Excellon
  en mm séparés métallisés / non métallisés, plans de perçage PDF ;
- adaptateur_usb_can_gerber.zip : le contenu de gerber/, à joindre au ticket ;
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
    "22uF": ("Condensateur tantale solide 22 µF 10 V, boîtier A (3216-18), polarisé",
             "sortie de l'AMS1117 : tantale exigé pour la stabilité"),
    "10nF": ("Condensateur céramique X7R 50 V", "VDDA, avec C8"),
    "1uF": ("Condensateur céramique X7R 16 V", "VDDA"),
    "4.7uF": ("Condensateur céramique X5R 10 V", "réservoir 3,3 V"),
    "22pF": ("Condensateur céramique C0G/NP0 50 V", "à ajuster selon la CL du quartz"),
    "PWR vert": ("LED verte", ""),
    "RX vert": ("LED verte", ""),
    "TX jaune": ("LED jaune", ""),
    "500mA": ("Fusible réarmable PTC, 500 mA maintenu, 6 V mini", ""),
    "USB_A": ("Fiche USB type A mâle coudée, pour CI (CNCTech 1001-011-01101)", "branchement direct sur le PC"),
    "Bornier CAN": ("Bornier à vis 3 points, pas 5,08 mm, pour CI (type Phoenix MKDS 1,5/3-5,08)",
                    "bus CAN : H, L, G"),
    "SWD": ("Barrette mâle sécable 1 × 4, pas 2,54 mm", "SWCLK, SWDIO, GND, 3V3"),
    "TERM": ("Barrette mâle 1 × 2, pas 2,54 mm + cavalier", "terminaison 120 Ω"),
    "1k": ("Résistance 1 %, 1/8 W", ""),
    "0R": ("Résistance 0 Ω (ou strap)", "CH340C en mode 3,3 V"),
    "10k": ("Résistance 1 %, 1/8 W", ""),
    "120R": ("Résistance 1 %, 1/8 W", "terminaison CAN"),
    "RESET": ("Bouton poussoir CMS 3 × 2,5 mm (Omron B3U-1000P)", "face avant"),
    "BOOT0": ("Bouton poussoir CMS 3 × 2,5 mm (Omron B3U-1000P)", "face avant"),
    "STM32G431KBT6": ("Microcontrôleur STM32G431KBT6, LQFP32", "pas 0,8 mm"),
    "CH340C": ("Pont USB-UART CH340C, SOIC-16", "version C : sans quartz externe"),
    "TJA1051T/3": ("Transceiver CAN TJA1051T/3, SOIC-8", "suffixe /3 : broche VIO"),
    "AMS1117-3.3": ("Régulateur linéaire 3,3 V AMS1117-3.3, SOT-223", ""),
    "USBLC6-2SC6": ("Protection ESD USB USBLC6-2SC6, SOT-23-6", ""),
    "8MHz": ("Quartz 8 MHz CMS 5 × 3,2 mm, 2 pastilles", "noter sa capacité de charge CL"),
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
<p>Carte 2 couches 60 × 30 mm, FR4 35 µm, composants sur les deux faces. Passifs en 0805 (empreintes HandSolder).
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
<title>Implantation adaptateur USB-CAN</title>
<style>@page {{ size: A4 landscape; margin: 10mm; }} body {{ font: 10pt Arial, sans-serif; margin: 0; }}
h1 {{ font-size: 13pt; margin: 0 0 4mm; }} img {{ width: 100%; }}</style>
<h1>Implantation, face avant — adaptateur USB-CAN (G69)</h1>
<img src="{svg.name}"></html>"""
    print_pdf(page, OUT / "implantation.pdf")
    svg.unlink()


def echelle_1():
    """PCB à l'échelle 1:1 sur A4 : page 1 face avant, page 2 face arrière vue de dessus.

    À imprimer en « taille réelle » (100 %, sans ajustement à la page) : la carte doit
    alors mesurer 60 × 30 mm, ce qui permet de poser les composants sur le papier.
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
    cli("pcb", "export", "gerbers", "--layers", "F.Cu,B.Cu,Edge.Cuts,F.Silkscreen,F.Paste,B.Paste",
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
