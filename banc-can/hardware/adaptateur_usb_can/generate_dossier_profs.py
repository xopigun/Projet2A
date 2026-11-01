"""Assemble le dossier de vérification destiné aux enseignants, en un .zip.

    python generate_dossier_profs.py <dossier_datasheets> <archive.zip>

Le dossier des datasheets reste hors du dépôt git (documents des fabricants). Le .zip
reprend le dossier factory (fabrication/, à régénérer avant avec generate_fabrication.py),
le projet KiCad, les rapports ERC et DRC, des rendus 3D, les règles de la factory,
SOURCES_COMPOSANTS.md (en .md et en .pdf) et les datasheets.
"""

import html
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
NAME = "adaptateur_usb_can"
RULES = HERE.parent / "regles_fabrication"
CLI = r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

LISEZMOI = """# Adaptateur USB-CAN G69 : dossier de vérification

Carte de remplacement du CANable 2.0, qu'on ne peut pas commander (ticket GLPI 0015779),
conçue pour être fabriquée à la factory ENSEA (2 couches, cuivre nu).

| Fichier | Contenu |
|---|---|
| `SOURCES_COMPOSANTS.pdf` (et `.md`) | pour chaque composant : informations utilisées, page ou tableau de la datasheet, statut de la vérification |
| `schema.pdf` | schéma électrique |
| `implantation.pdf` | implantation de la face avant |
| `adaptateur_usb_can_BOM.pdf` / `.csv` | nomenclature |
| `fabrication/` | Gerber, perçages Excellon et plans de perçage, zip pour le ticket factory |
| `kicad/` | projet KiCad 9 (schéma, PCB, règles ENSEA) |
| `verifications/` | rapports ERC et DRC de kicad-cli, rendus 3D face avant et face arrière |
| `regles_factory/` | guide *PCB @ Factory* et fichier DRC ENSEA 2 couches |
| `datasheets/` | datasheets des composants, citées dans SOURCES_COMPOSANTS |

Les points encore ⚠️ *à confirmer* sont listés à la fin de SOURCES_COMPOSANTS.

Sources et scripts de génération : dépôt github.com/xopigun/Projet2A,
branche `pcb/adaptateur-usb-can`, dossier `banc-can/hardware/adaptateur_usb_can/`.
"""


def md_inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)


def md_to_html(md, title):
    """Markdown réduit à ce qu'utilisent nos documents : titres, listes, tableaux, filets."""
    out, table, items = [], [], []
    prev_blank = True

    def flush():
        if table:
            head, *rows = [r for r in table if not re.fullmatch(r"\|[-| ]+\|", r)]
            cells = lambda r: [c.strip() for c in r.strip("|").split("|")]
            out.append("<table><tr>" + "".join(f"<th>{md_inline(c)}</th>" for c in cells(head))
                       + "</tr>" + "".join("<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in cells(r))
                                           + "</tr>" for r in rows) + "</table>")
            table.clear()
        if items:
            tag = "ol" if items[0][0] == "ol" else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{md_inline(t)}</li>" for _, t in items) + f"</{tag}>")
            items.clear()

    for line in md.splitlines():
        if line.startswith("|"):
            table.append(line)
            continue
        m = re.match(r"\s*(?:([-*])|(\d+)\.)\s+(.*)", line)
        if m:
            items.append(("ol" if m.group(2) else "ul", m.group(3)))
            continue
        if line.startswith("  ") and items:
            items[-1] = (items[-1][0], items[-1][1] + " " + line.strip())
            continue
        flush()
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{level}>{md_inline(line[level:].strip())}</h{level}>")
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.strip():
            if out and out[-1].startswith("<p>") and not prev_blank:
                out[-1] = out[-1][:-4] + " " + md_inline(line) + "</p>"  # suite du paragraphe
            else:
                out.append(f"<p>{md_inline(line)}</p>")
        prev_blank = not line.strip()
    flush()
    return f"""<!doctype html><html lang="fr"><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>@page {{ size: A4; margin: 14mm; }} body {{ font: 9.5pt Arial, sans-serif; }}
h1 {{ font-size: 15pt; }} h2 {{ font-size: 12pt; margin-top: 7mm; }}
table {{ border-collapse: collapse; width: 100%; margin: 2mm 0; page-break-inside: auto; }}
tr {{ page-break-inside: avoid; }} th, td {{ border: 1px solid #888; padding: 1.2mm 1.6mm;
vertical-align: top; text-align: left; }} th {{ background: #e4e4e4; }}
code {{ font-size: 8.5pt; }}</style>{"".join(out)}</html>"""


def print_pdf(page, pdf):
    tmp = pdf.with_suffix(".html")
    tmp.write_text(page, encoding="utf-8")
    subprocess.run([EDGE, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", tmp.as_uri()], check=True, capture_output=True)
    tmp.unlink()


def cli(*args):
    subprocess.run([CLI, *args], capture_output=True)  # ERC/DRC sortent en erreur s'il y a des violations


def main(datasheets, archive):
    root = Path(tempfile.mkdtemp()) / "Dossier_adaptateur_USB-CAN_G69"
    for sub in ("kicad", "verifications", "regles_factory", "datasheets"):
        (root / sub).mkdir(parents=True)

    (root / "LISEZMOI.md").write_text(LISEZMOI, encoding="utf-8")
    sources = (HERE / "SOURCES_COMPOSANTS.md").read_text(encoding="utf-8")
    (root / "SOURCES_COMPOSANTS.md").write_text(sources, encoding="utf-8")
    print_pdf(md_to_html(sources, "Sources et vérifications"), root / "SOURCES_COMPOSANTS.pdf")

    fab = HERE / "fabrication"
    for f in ("schema.pdf", "implantation.pdf", f"{NAME}_BOM.pdf", f"{NAME}_BOM.csv"):
        shutil.copy2(fab / f, root / f)
    shutil.copytree(fab / "gerber", root / "fabrication" / "gerber")
    shutil.copy2(fab / f"{NAME}_gerber.zip", root / "fabrication")

    for ext in ("kicad_pro", "kicad_sch", "kicad_pcb"):
        shutil.copy2(HERE / f"{NAME}.{ext}", root / "kicad")
    ver = root / "verifications"
    cli("sch", "erc", "--severity-all", "-o", str(ver / "rapport_ERC.txt"), str(HERE / f"{NAME}.kicad_sch"))
    cli("pcb", "drc", "--schematic-parity", "-o", str(ver / "rapport_DRC.txt"), str(HERE / f"{NAME}.kicad_pcb"))
    for side in ("top", "bottom"):
        cli("pcb", "render", "--side", side, "--width", "1600", "--height", "900", "--zoom", "1.6",
            "-o", str(ver / f"rendu_3D_{side}.png"), str(HERE / f"{NAME}.kicad_pcb"))

    shutil.copy2(RULES / "ENSEA_PCB_Factory_Design_Guidelines.pdf", root / "regles_factory")
    shutil.copy2(RULES / "20260112_ENSEA_2_layers_drc.kicad_pro", root / "regles_factory")
    for f in sorted(Path(datasheets).iterdir()):
        if f.suffix.lower() == ".pdf":
            shutil.copy2(f, root / "datasheets" / f.name)

    archive = Path(archive)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(root.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(root.parent))
    for f in sorted(root.rglob("*")):
        if f.is_file():
            print(f.relative_to(root))
    print(f"-> {archive} ({archive.stat().st_size // 1024} Ko)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
