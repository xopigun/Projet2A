"""Prépare carte_porteuse.kicad_pcb : contour, empreintes placées, nets, plans de masse.

Point de départ du routage (voir route_freerouting.py), pas un générateur à relancer : il
repart du gabarit ENSEA et écrase la carte, routage compris. Python de KiCad 9 :

    "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" generate_pcb.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "adaptateur_usb_can"))
import kisym  # noqa: E402

SCH = HERE / "carte_porteuse.kicad_sch"
PCB = HERE / "carte_porteuse.kicad_pcb"
TEMPLATE = HERE.parent / "regles_fabrication" / "20260112_ENSEA_2_layers_drc.kicad_pcb"
KICAD = Path(r"C:\Program Files\KiCad\9.0")
FOOTPRINTS = KICAD / "share" / "kicad" / "footprints"

# Contour (mm), en escalier : le cuivre ne couvre que ce qui porte des composants (environ
# 2 050 mm² au lieu de 3 250 pour la v0.1 rectangulaire). Vue de dessus, arrière en haut :
# - bande arrière : bornier d'entrée du bus à gauche, de sortie à droite (fils vers
#   l'extérieur), fixation H1 au milieu ; le bus la traverse derrière les barrettes ;
# - colonne centrale : les deux barrettes de la Nucléo, posée dans la profondeur, USB vers
#   l'arrière (câble vers le hub) ; barrette coudée de l'écran OLED au bord avant ;
# - bande gauche : barrette coudée du MPU-6050, au plus près de l'I2C et de INT (CN4) ;
# - bande droite : cavalier TERM, barrette des capteurs (PA4, PA7 sur CN3) et LED.
# Deux angles rentrants seulement, loin des borniers : la carte ne doit pas avoir de point
# faible là où l'on serre les vis des fils.
CONTOUR = [(97.7, 100.0), (139.5, 100.0), (139.5, 145.0), (129.0, 145.0), (129.0, 157.6),
           (109.4, 157.6), (109.4, 138.8), (97.7, 138.8)]

# Nucléo-G431KB vue de dessus, USB à l'arrière : CN4 à gauche, CN3 à droite, broche 1 côté
# USB (UM2397 figure 12), rangées à 15,24 mm. Barrettes femelles sur la face avant.
CN4_X = 111.43
CN3_X = CN4_X + 15.24
CN_Y = 115.0          # broche 1 de CN3 et de CN4

# Référence : (x, y, rotation en degrés). Tout est sur la face avant.
PLACEMENT = {
    "J1": (103.75, 103.0, 270),    # bus entrée : G, L, H de l'arrière vers l'avant, fils à gauche
    "J2": (134.3, 113.16, 90),     # bus sortie : H, L, G de l'arrière vers l'avant, fils à droite
    "J4": (CN4_X, CN_Y, 0),        # Nucleo CN4 (D1 ... D12)
    "J3": (CN3_X, CN_Y, 0),        # Nucleo CN3 (VIN ... D13)
    # Fixation arrière sous le bout USB de la Nucléo (la tête de vis reste 6 mm sous elle).
    "H1": (119.05, 106.3, 0),
    # Entre les barrettes, sous la Nucléo (8 mm libres sous elle), sur 11,6 mm de large :
    # le transceiver, ses découplages et les résistances de choix ou de tirage de part et
    # d'autre, la seconde fixation devant.
    "U1": (119.05, 121.0, 90),     # CANH/CANL et S vers l'arrière (bus), TXD/RXD/VCC devant
    "R7": (114.25, 117.5, 90),     # S à la masse (monté)
    "R8": (114.25, 121.5, 90),     # S vers PB6 (non monté)
    "C2": (123.85, 118.0, 90),     # VIO 3,3 V
    "C1": (119.05, 125.9, 0),      # VCC 5 V
    "R9": (119.05, 128.4, 0),      # GND -> OLED broche 1 (monté)
    "R10": (119.05, 130.7, 0),     # 3V3 -> OLED broche 2 (monté)
    "R4": (114.25, 125.5, 90),     # tirages I2C (non montés)
    "R5": (114.25, 129.5, 90),
    "R11": (123.85, 125.5, 90),    # variante VCC/GND de l'OLED (non montée)
    "R12": (123.85, 129.5, 90),
    "H2": (119.05, 137.5, 0),
    # Barrettes coudées : le corps est couché sous la Nucléo ou en bord de carte, les modules
    # tiennent debout au-delà du bord (OLED à l'avant, écran vers l'utilisateur ; MPU-6050
    # à gauche, sous les fils du bornier d'entrée).
    "J5": (115.24, 147.5, 90),
    "J6": (107.8, 119.0, 0),
    # Bande droite, accessible Nucléo en place : terminaison, capteurs (non montés), LED.
    "J7": (131.5, 119.0, 0),
    "R1": (135.2, 120.3, 90),     # terminaison 120 ohms
    "J8": (131.5, 125.5, 0),
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
        if ref.startswith(("J", "H")) or ref in ("D1", "D2"):
            fp.Reference().SetVisible(False)  # repères remplacés par la sérigraphie ci-dessous
        for pad in fp.Pads():
            net = pads.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(nets[net])
                # Masse des barrettes des modules : connexion pleine au plan (un frein
                # thermique y garde trop peu de rayons entre les pistes voisines).
                if net == "GND" and ref in ("J1", "J2", "J3", "J4", "J5", "J6", "J8"):
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

    # Sérigraphie : sens de la Nucléo (une Nucléo à l'envers mettrait le 5 V sur une
    # broche d'E/S), repères du bus et des modules.
    silk(board, "IN G-L-H", 114.0, 112.0, 0.8)
    silk(board, "H-L-G OUT", 124.2, 112.0, 0.8)
    silk(board, "^ USB", 112.7, 101.5, 0.9)
    silk(board, "N__", 125.5, 101.5, 1.1, 0.18)
    silk(board, "TERM", 134.9, 117.6, 0.8)
    silk(board, "CAPT", 135.6, 133.8, 0.8)
    silk(board, "MPU", 101.0, 137.6, 0.8)
    silk(board, "E", 135.6, 143.15, 0.9)
    silk(board, "B", 135.6, 139.05, 0.9)
    silk(board, "G69 v0.2", 119.05, 102.0, 0.8)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(PCB))
    aire = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(CONTOUR, CONTOUR[1:] + CONTOUR[:1])) / 2
    print(f"{PCB.name} : {len(comps)} empreintes, {len(nets)} nets, contour {abs(aire):.0f} mm²")


if __name__ == "__main__":
    os.chdir(HERE)
    main()
