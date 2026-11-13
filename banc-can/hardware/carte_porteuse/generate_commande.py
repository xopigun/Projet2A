"""Produit fabrication/carte_porteuse_commande.xlsx : composants et fournisseurs français.

    python generate_commande.py      (après generate_fabrication.py, qui écrit la nomenclature)

Les liens sont des recherches chez chaque distributeur, construites à partir de la référence
fabricant ou, pour les composants génériques, de leur description. Le stock et le prix ne sont
pas vérifiés : ils changent tous les jours.
"""

import csv
from pathlib import Path
from urllib.parse import quote_plus

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = Path(__file__).parent
BOM = HERE / "fabrication" / "carte_porteuse_BOM.csv"
OUT = HERE / "fabrication" / "carte_porteuse_commande.xlsx"

# Valeur -> (fabricant, référence fabricant, recherche à lancer, remarque d'achat)
ACHAT = {
    "TJA1051T/3": ("NXP", "TJA1051T/3", "TJA1051T/3",
                   "6 en stock (10 reçus, 4 sur les adaptateurs SOP8) : rien à commander pour 4 cartes"),
    "Nucleo CN3": ("au choix", "", "barrette femelle 15 points 2.54mm", "ou barrette femelle sécable coupée à 15"),
    "Nucleo CN4": ("au choix", "", "barrette femelle 15 points 2.54mm", "ou barrette femelle sécable coupée à 15"),
    "Bus entrée": ("Phoenix Contact", "MKDS 1,5/ 3-5,08", "bornier a vis 3 points 5.08mm",
                   "tout bornier 3 points au pas de 5,08 mm convient (perçages 1,3 mm)"),
    "Bus sortie": ("Phoenix Contact", "MKDS 1,5/ 3-5,08", "bornier a vis 3 points 5.08mm",
                   "tout bornier 3 points au pas de 5,08 mm convient (perçages 1,3 mm)"),
    "OLED coudé": ("au choix", "", "barrette femelle coudee 4 points 2.54mm", "coudée à 90° : l'écran tient debout"),
    "MPU-6050 coudé": ("au choix", "", "barrette femelle coudee 8 points 2.54mm", "coudée à 90° ; N2 seulement"),
    "TERM": ("au choix", "", "barrette secable male 2.54mm", "+ 1 cavalier 2,54 mm (N4 : câble vers SW1)"),
    "ERR rouge": ("Würth Elektronik", "150080RS75000", "150080RS75000", "ou toute LED rouge 0805"),
    "BUS-OFF jaune": ("Würth Elektronik", "150080YS75000", "150080YS75000", "ou toute LED jaune 0805"),
}
GENERIQUE = {  # recherche pour les passifs, par préfixe de repère
    "C": "condensateur ceramique {v} 0805",
    "R": "resistance {v} 0805",
    "D": "{d} 0805",
}

FOURNISSEURS = [
    ("Farnell France", "https://fr.farnell.com", "https://fr.farnell.com/search?st={q}",
     "distributeur professionnel"),
    ("RS Components France", "https://fr.rs-online.com", "https://fr.rs-online.com/web/c/?searchTerm={q}",
     "distributeur professionnel ; proposé dans le ticket GLPI de commande"),
    ("Mouser France", "https://www.mouser.fr", "https://www.mouser.fr/c/?q={q}",
     "distributeur professionnel"),
    ("DigiKey France", "https://www.digikey.fr", "https://www.digikey.fr/fr/products/result?keywords={q}",
     "distributeur professionnel"),
]
AUTRES = [
    ("Conrad France", "https://www.conrad.fr", "passifs, connecteurs, boutons"),
    ("Gotronic", "https://www.gotronic.fr", "boutique française, composants courants"),
    ("LCSC (Chine)", "https://www.lcsc.com", "fabricant-distributeur du CH340C (réf. C84681), livre en France"),
]

ARIAL = "Arial"
HEAD = PatternFill("solid", fgColor="DDDDDD")
INPUT = PatternFill("solid", fgColor="FFFF00")
THIN = Side(style="thin", color="999999")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def font(**kw):
    return Font(name=ARIAL, size=kw.pop("size", 10), **kw)


def lien(cell, url, texte="Rechercher"):
    cell.value = texte
    cell.hyperlink = url
    cell.font = font(color="0563C1", underline="single")


def composants(ws):
    ws["A1"] = "Carte porteuse G69 : composants à commander"
    ws["A1"].font = font(bold=True, size=13)
    ws["A2"] = "Nombre de cartes à produire"
    ws["A2"].font = font(bold=True)
    ws["D2"] = 4
    ws["D2"].font = font(color="0000FF", bold=True)
    ws["D2"].fill = INPUT
    ws["D2"].comment = Comment("Seule case à modifier : la colonne « Qté à commander » se recalcule.", "G69")
    ws["E2"] = "← case jaune à modifier (les quantités totales en dépendent)"
    ws["E2"].font = font(italic=True, color="666666")

    head = ["Repères", "Qté / carte", "Qté à commander", "Désignation", "Valeur", "Boîtier",
            "Fabricant", "Réf. fabricant", "Remarque"] + [f[0] for f in FOURNISSEURS]
    for col, h in enumerate(head, 1):
        c = ws.cell(row=4, column=col, value=h)
        c.font = font(bold=True)
        c.fill = HEAD
        c.border = BOX
        c.alignment = Alignment(wrap_text=True, vertical="center")

    with BOM.open(encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh, delimiter=";"))[1:]
    r = 5
    for qty, refs, desig, value, boitier, remark in rows:
        fab, mpn, query, achat = ACHAT.get(value) or (
            "au choix", "", GENERIQUE[refs[0]].format(v=value, d=desig), "")
        note = "; ".join(x for x in (remark, achat) if x)
        values = [refs, int(qty), f"=B{r}*$D$2", desig, value, boitier, fab, mpn, note]
        for col, v in enumerate(values, 1):
            c = ws.cell(row=r, column=col, value=v)
            c.font = font(color="000000" if col == 3 else "0000FF" if col == 2 else "000000")
            c.border = BOX
            c.alignment = Alignment(wrap_text=True, vertical="top")
        for i, (_, _, url, _) in enumerate(FOURNISSEURS):
            c = ws.cell(row=r, column=10 + i)
            lien(c, url.format(q=quote_plus(query)))
            c.border = BOX
        r += 1
    last = r - 1
    ws.cell(row=r, column=1, value="Total composants").font = font(bold=True)
    ws.cell(row=r, column=2, value=f"=SUM(B5:B{last})").font = font(bold=True)
    ws.cell(row=r, column=3, value=f"=SUM(C5:C{last})").font = font(bold=True)
    ws.cell(row=r + 2, column=1, value=(
        "Liens « Rechercher » : recherche de la référence fabricant (ou de la description pour les "
        "composants génériques) chez chaque distributeur. Stock et prix non vérifiés. "
        "Le guide factory demande de privilégier les composants disponibles au magasin.")).font = font(
        italic=True, color="666666")

    widths = [22, 9, 11, 40, 14, 11, 20, 16, 42, 12, 12, 12, 12]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "B5"


def fournisseurs(ws):
    ws["A1"] = "Sites français où commander"
    ws["A1"].font = font(bold=True, size=13)
    for col, h in enumerate(["Site", "Adresse", "Usage"], 1):
        c = ws.cell(row=3, column=col, value=h)
        c.font = font(bold=True)
        c.fill = HEAD
        c.border = BOX
    for r, (nom, url, usage) in enumerate([(n, u, x) for n, u, _, x in FOURNISSEURS] + AUTRES, 4):
        ws.cell(row=r, column=1, value=nom).font = font()
        lien(ws.cell(row=r, column=2), url, url)
        ws.cell(row=r, column=3, value=usage).font = font()
        for col in (1, 2, 3):
            ws.cell(row=r, column=col).border = BOX
    ws.cell(row=r + 2, column=1, value=(
        "Rappel : Amazon Business est refusé par l'école pour les articles non vendus par Amazon "
        "(ticket GLPI 0015779).")).font = font(italic=True, color="666666")
    for col, w in zip("ABC", (24, 32, 70)):
        ws.column_dimensions[col].width = w


def main():
    wb = Workbook()
    composants(wb.active)
    wb.active.title = "Composants"
    fournisseurs(wb.create_sheet("Fournisseurs"))
    wb.calculation.fullCalcOnLoad = True  # Excel calcule les quantités à l'ouverture
    wb.save(OUT)
    print(OUT.relative_to(HERE))


if __name__ == "__main__":
    main()
