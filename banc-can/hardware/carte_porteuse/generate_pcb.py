"""Prépare carte_porteuse.kicad_pcb : contour, empreintes placées, nets, plans de masse.

Première étape de la chaîne : il repart du gabarit ENSEA et écrase la carte, routage compris.
Enchaîner ensuite router_manuel.py (pistes), coudre_gnd.py (vias de masse) et
verifier_criteres.py. Python de KiCad 9 :

    "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" generate_pcb.py
"""

import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import kisym  # noqa: E402  (copie locale de ../adaptateur_usb_can/kisym.py)

SCH = HERE / "carte_porteuse.kicad_sch"
PCB = HERE / "carte_porteuse.kicad_pcb"
TEMPLATE = HERE.parent / "regles_fabrication" / "20260112_ENSEA_2_layers_drc.kicad_pcb"
KICAD = Path(r"C:\Program Files\KiCad\9.0")
FOOTPRINTS = KICAD / "share" / "kicad" / "footprints"

# Contour (mm), en escalier : le cuivre ne couvre que ce qui porte des composants (environ
# 1 830 mm² au lieu de 3 250 pour la v0.1 rectangulaire). Vue de dessus, arrière en haut :
# - bande arrière : bornier du bus à droite (fils vers l'extérieur), fixation H1 au milieu ;
#   son bord gauche s'arrête à la piste +3V3 qui descend vers le MPU-6050 ;
# - colonne centrale : les deux barrettes de la Nucléo, posée dans la profondeur, USB vers
#   l'arrière (câble vers le hub) ; barrette coudée de l'écran OLED au bord avant ;
# - bande gauche : barrette coudée du MPU-6050, au plus près de l'I2C et de INT (CN4) ;
# - bande droite : cavalier TERM et LED, plus étroite que le bornier.
# C'est le contour de la carte routée (v0.3) : le bornier d'entrée de la v0.2 et le coin
# arrière gauche qu'il occupait ont été retirés sans reprendre le routage.
CONTOUR = [(106.8, 100.0), (139.5, 100.0), (139.5, 116.7), (137.0, 116.7), (137.0, 145.0),
           (129.0, 145.0), (129.0, 157.6), (109.4, 157.6), (109.4, 138.8), (97.7, 138.8),
           (97.7, 116.7), (106.8, 116.7)]

# Nucléo-G431KB vue de dessus, USB à l'arrière : CN4 à gauche, CN3 à droite, broche 1 côté
# USB (UM2397 figure 12), rangées à 15,24 mm. Barrettes femelles sur la face avant.
CN4_X = 111.43
CN3_X = CN4_X + 15.24
CN_Y = 115.0          # broche 1 de CN3 et de CN4

# Composants prévus mais non montés : attribut « ne pas monter » et hors nomenclature.
NON_MONTES = {"R8", "R4", "R5"}

# Perçage du bornier J1 : 1,3 mm dans la bibliothèque KiCad, hors du pas de 0,2 mm de la
# factory (0,4 à 2,0 mm), qui l'arrondirait à 1,4 mm. On le fixe donc à 1,4 mm ; la pastille
# de 2,6 mm garde une couronne de 0,6 mm.
PERCAGE_J1 = 1.4

# Têtes des vis M3 (5,5 mm) sur cuivre nu : aucune piste ni via de la face avant à moins de
# 3,5 mm de l'axe de H1 et H2 (0,75 mm de la tête au moins ; le plan de masse, lui, reste).
GARDE_VIS = 3.5

# Repères déplacés (x, y, angle) : à leur place par défaut ils tombent sur une pastille, sur
# le contour d'un voisin ou hors de la carte.
REPERES = {
    "R1": (133.7, 118.5, 90),      # entre le cavalier et R1
    "R2": (129.5, 141.1, 0),       # à gauche de R2 (au-dessus, il tombait sur D2)
    "R5": (120.2, 143.3, 90),      # à gauche de R5
    "R8": (126.0, 105.3, 0),       # au-dessus de R8
    "R10": (123.8, 140.3, 0),      # au-dessus de R10
    "C2": (123.2, 120.8, 0),       # sous C2
}
TAILLE_REPERE = 0.8

# Référence : (x, y, rotation en degrés). Tout est sur la face avant.
PLACEMENT = {
    "J1": (134.3, 113.16, 90),     # bus : H, L, G de l'arrière vers l'avant, fils à droite
    "J4": (CN4_X, CN_Y, 0),        # Nucleo CN4 (D1 ... D12)
    "J3": (CN3_X, CN_Y, 0),        # Nucleo CN3 (VIN ... D13)
    # Fixation arrière sous le bout USB de la Nucléo (la tête de vis reste 6 mm sous elle).
    "H1": (119.05, 106.3, 0),
    # Entre les barrettes, sous la Nucléo (8 mm libres sous elle). Le transceiver est en
    # haut de la colonne, broches CANH/CANL tournées vers le bornier : la paire fait 15 mm
    # sur la face avant, sans via. Aucune piste sur la face arrière à l'est de x = 115,4,
    # sauf le pont +5V de 3 mm sous C2.
    "U1": (120.9, 113.3, 0),       # broches 5 à 8 à l'est (VIO, CANL, CANH, S), 1 à 4 à l'ouest
    # C1 à 0,9 mm des pattes de U1 (0,6 mm ne laissait pas passer le fer entre les deux).
    "C1": (115.8, 113.6, 90),      # VCC 5 V, à l'ouest de U1 (broches 3 et 2)
    "C2": (123.2, 118.1, 270),     # VIO 3,3 V, sous la broche 5
    "R7": (123.7, 107.9, 90),      # S à la masse (monté), au nord de la broche 8
    "R8": (126.0, 107.9, 90),      # S vers PB6 (non monté)
    "R4": (108.9, 112.1, 0),       # tirages I2C (non montés) : SCL, au coin nord-ouest
    "R5": (121.7, 143.6, 270),     # SDA, à côté de R10
    "R9": (114.4, 143.7, 270),     # GND -> OLED broche 1 (monté), au-dessus de J5.1
    "R10": (123.8, 142.9, 270),    # 3V3 -> OLED broche 2 (monté), près de J3.14
    "H2": (119.05, 137.5, 0),
    # Barrettes coudées : le corps est couché sous la Nucléo ou en bord de carte, les modules
    # tiennent debout au-delà du bord (OLED à l'avant, écran vers l'utilisateur ; MPU-6050
    # à gauche).
    "J5": (115.24, 147.5, 90),
    "J6": (107.8, 119.0, 0),
    # Bande droite, accessible Nucléo en place : terminaison et LED.
    "J7": (131.5, 121.54, 180),    # mêmes pastilles qu'en v0.3, CANL sur la broche du nord
    "R1": (135.2, 118.5, 270),     # terminaison 120 ohms, CANH au nord
    "R3": (132.4, 137.0, 0),
    "D2": (132.4, 139.05, 180),    # BUS-OFF jaune
    "R2": (132.4, 141.1, 0),
    "D1": (132.4, 143.15, 180),    # ERR rouge
}


def mm(v):
    return pcbnew.FromMM(v)


def point(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def netlist():
    """Composants {ref: (valeur, empreinte, uuid)} et nets {(ref, pad): net} du schéma."""
    out = Path(tempfile.gettempdir()) / "carte_porteuse.net"
    subprocess.run(
        [str(KICAD / "bin" / "kicad-cli.exe"), "sch", "export", "netlist",
         "--format", "kicadsexpr", "-o", str(out), str(SCH)],
        check=True, capture_output=True,
    )
    tree = kisym.parse(out.read_text(encoding="utf-8"))
    comps = {}
    for comp in kisym.find(kisym.first(tree, "components"), "comp"):
        comps[kisym.first(comp, "ref")[1]] = (
            kisym.first(comp, "value")[1],
            kisym.first(comp, "footprint")[1],
            kisym.first(comp, "tstamps")[1],
        )
    pads = {}
    for net in kisym.find(kisym.first(tree, "nets"), "net"):
        name = kisym.first(net, "name")[1]
        for node in kisym.find(net, "node"):
            pads[(kisym.first(node, "ref")[1], kisym.first(node, "pin")[1])] = name
    return comps, pads


def segment(board, layer, a, b, width=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetLayer(layer)
    s.SetStart(point(*a))
    s.SetEnd(point(*b))
    s.SetWidth(mm(width))
    board.Add(s)


def silk(board, txt, x, y, size=1.0, thick=0.15, layer=pcbnew.F_SilkS, angle=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(layer)
    t.SetPosition(point(x, y))
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(thick))
    if angle:
        t.SetTextAngleDegrees(angle)
    board.Add(t)


def main():
    comps, pads = netlist()
    missing = sorted(set(comps) - set(PLACEMENT))
    assert not missing, f"placement manquant : {missing}"

    board = pcbnew.LoadBoard(str(TEMPLATE))
    nets = {}
    for name in sorted(set(pads.values())):
        nets[name] = pcbnew.NETINFO_ITEM(board, name)
        board.Add(nets[name])

    for ref, (value, footprint, uuid) in sorted(comps.items()):
        lib, name = footprint.split(":")
        fp = pcbnew.FootprintLoad(str(FOOTPRINTS / f"{lib}.pretty"), name)
        fp.SetFPIDAsString(footprint)
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.SetPath(pcbnew.KIID_PATH(f"/{uuid}"))
        fp.SetSheetname("/")
        fp.SetSheetfile(SCH.name)
        board.Add(fp)
        x, y, rot = PLACEMENT[ref]
        fp.SetPosition(point(x, y))
        fp.SetOrientationDegrees(rot)
        if ref in NON_MONTES:
            fp.SetDNP(True)
            fp.SetExcludedFromBOM(True)
        if ref.startswith(("J", "H")) or ref in ("D1", "D2"):
            fp.Reference().SetVisible(False)  # repères remplacés par la sérigraphie ci-dessous
        if ref in REPERES:
            rx, ry, angle = REPERES[ref]
            texte = fp.Reference()
            texte.SetPosition(point(rx, ry))
            texte.SetTextAngleDegrees(angle)
            texte.SetTextSize(pcbnew.VECTOR2I(mm(TAILLE_REPERE), mm(TAILLE_REPERE)))
            texte.SetTextThickness(mm(0.12))
        for pad in fp.Pads():
            if ref == "J1":
                pad.SetDrillSize(pcbnew.VECTOR2I(mm(PERCAGE_J1), mm(PERCAGE_J1)))
            net = pads.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(nets[net])
                # Masse des barrettes des modules : connexion pleine au plan (un frein
                # thermique y garde trop peu de rayons entre les pistes voisines).
                if net == "GND" and ref in ("J1", "J3", "J4", "J5", "J6"):
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

    for a, b in zip(CONTOUR, CONTOUR[1:] + CONTOUR[:1]):
        segment(board, pcbnew.Edge_Cuts, a, b)

    # Plans de masse sur les deux faces.
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(nets["GND"])
        zone.SetLocalClearance(mm(0.5))
        zone.SetMinThickness(mm(0.4))
        zone.SetThermalReliefGap(mm(0.5))
        zone.SetThermalReliefSpokeWidth(mm(0.5))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        outline = zone.Outline()
        outline.NewOutline()
        for c in CONTOUR:
            outline.Append(mm(c[0]), mm(c[1]))
        board.Add(zone)

    # Bande de 0,6 mm le long de tous les bords, interdite aux pistes et aux vias (isolation
    # de 0,5 mm au contour demandée par la factory, que Freerouting ne connaît pas).
    lset = pcbnew.LSET()
    for c in (pcbnew.F_Cu, pcbnew.B_Cu):
        lset.AddLayer(c)
    # Un rectangle par bord (bords tous horizontaux ou verticaux), côté intérieur : le script
    # de routage et Freerouting lisent les zones interdites comme des rectangles.
    aire = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(CONTOUR, CONTOUR[1:] + CONTOUR[:1]))
    sens = 1 if aire > 0 else -1  # aire > 0 : sens horaire à l'écran (Y vers le bas)
    b = 0.6
    for (xa, ya), (xb, yb) in zip(CONTOUR, CONTOUR[1:] + CONTOUR[:1]):
        dx, dy = (xb > xa) - (xb < xa), (yb > ya) - (yb < ya)
        nx, ny = -dy * sens, dx * sens  # normale vers l'intérieur
        xs = (xa, xb, xa + nx * b, xb + nx * b)
        ys = (ya, yb, ya + ny * b, yb + ny * b)
        keep = pcbnew.ZONE(board)
        keep.SetIsRuleArea(True)
        keep.SetLayerSet(lset)
        keep.SetDoNotAllowTracks(True)
        keep.SetDoNotAllowVias(True)
        keep.SetDoNotAllowPads(False)
        keep.SetDoNotAllowFootprints(False)
        keep.SetDoNotAllowCopperPour(False)
        ko = keep.Outline()
        ko.NewOutline()
        for cx, cy in ((min(xs), min(ys)), (max(xs), min(ys)), (max(xs), max(ys)), (min(xs), max(ys))):
            ko.Append(mm(cx), mm(cy))
        board.Add(keep)

    # Têtes de vis : disque interdit aux pistes et aux vias sur la face avant.
    for ref in ("H1", "H2"):
        cx, cy, _ = PLACEMENT[ref]
        keep = pcbnew.ZONE(board)
        keep.SetIsRuleArea(True)
        keep.SetLayer(pcbnew.F_Cu)
        keep.SetZoneName(f"tete_vis_{ref}")
        keep.SetDoNotAllowTracks(True)
        keep.SetDoNotAllowVias(True)
        keep.SetDoNotAllowPads(False)
        keep.SetDoNotAllowFootprints(False)
        keep.SetDoNotAllowCopperPour(False)
        ko = keep.Outline()
        ko.NewOutline()
        for k in range(48):
            a = 2 * math.pi * k / 48
            ko.Append(mm(cx + GARDE_VIS * math.cos(a)), mm(cy + GARDE_VIS * math.sin(a)))
        board.Add(keep)

    # Sérigraphie : sens de la Nucléo (une Nucléo à l'envers mettrait le 5 V sur une
    # broche d'E/S), repères du bus et des modules.
    # Une lettre en face de chaque borne de J1 (H, L, G de l'arrière vers l'avant), contre
    # le dos du bornier : un seul texte « H-L-G » ne disait pas quelle borne est laquelle.
    for lettre, y in (("H", 103.0), ("L", 108.08), ("G", 112.75)):
        silk(board, lettre, 128.3, y, 0.8)
    silk(board, "^ USB", 112.7, 101.5, 0.9)
    silk(board, "N__", 125.5, 101.5, 1.1, 0.18)
    silk(board, "TERM", 132.9, 124.6, 0.8)
    silk(board, "MPU", 101.0, 137.6, 0.8)
    silk(board, "E", 136.05, 143.15, 0.9)
    silk(board, "B", 136.05, 139.05, 0.9)
    silk(board, "G69 v0.4", 119.05, 102.0, 0.8)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(PCB))
    aire = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(CONTOUR, CONTOUR[1:] + CONTOUR[:1])) / 2
    print(f"{PCB.name} : {len(comps)} empreintes, {len(nets)} nets, contour {abs(aire):.0f} mm²")


if __name__ == "__main__":
    os.chdir(HERE)
    main()
