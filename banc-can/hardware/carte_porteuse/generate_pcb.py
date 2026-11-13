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

# Contour (mm) : 65 x 50 mm. Nucléo à gauche (USB vers le bord gauche), borniers du bus sur
# le bord droit (fils vers l'extérieur), écran OLED, MPU-6050 et LED sur le bord avant (bas).
X0, Y0, X1, Y1 = 100.0, 100.0, 165.0, 150.0

# Nucléo-G431KB vue de dessus, USB à gauche : CN3 en haut, CN4 en bas, broche 1 côté USB
# (UM2397 figure 12), rangées à 15,24 mm. Les barrettes femelles sont sur la face avant.
CN_X = 108.0          # broche 1 de CN3 et de CN4
CN3_Y = 108.0
CN4_Y = CN3_Y + 15.24

# Référence : (x, y, rotation en degrés). Tout est sur la face avant.
PLACEMENT = {
    "J3": (CN_X, CN3_Y, 90),      # Nucleo CN3 (VIN ... D13)
    "J4": (CN_X, CN4_Y, 90),      # Nucleo CN4 (D1 ... D12)
    # Sous la Nucléo, entre les deux rangées : transceiver et découplages.
    "U1": (130.0, 115.62, 90),
    "C1": (123.0, 115.62, 90),     # VCC 5 V
    "C2": (137.0, 115.62, 90),     # VIO 3,3 V
    "R7": (124.0, 111.2, 0),       # S à la masse (monté)
    "R8": (124.0, 120.0, 0),       # S vers PB6 (non monté)
    # Bus : borniers entrée (haut) et sortie (bas), broche 1 (GND) en bas de chacun.
    "J1": (161.3, 117.6, 90),
    "J2": (161.3, 138.0, 90),
    "R1": (149.0, 129.5, 90),      # terminaison 120 ohms
    "J7": (149.0, 134.5, 0),       # cavalier TERM (N4 : vers SW1)
    # Bord avant : écran OLED à gauche, MPU-6050 à droite, LED entre les deux.
    "J5": (108.2, 146.0, 90),
    "J6": (137.1, 146.0, 90),
    "R9": (104.0, 140.0, 90),      # GND -> OLED broche 1 (monté)
    "R10": (107.0, 140.0, 90),     # 3V3 -> OLED broche 2 (monté)
    "R11": (110.0, 140.0, 90),     # variante VCC/GND (non monté)
    "R12": (113.0, 140.0, 90),
    # LED sur la bande libre au-dessus de la Nucléo, près de PA1 (CN3-11) et PA0 (CN3-12) :
    # visibles une fois la carte montée, et le bord avant reste libre pour l'I2C.
    "R3": (130.0, 103.2, 0),
    "D2": (134.0, 103.2, 180),     # BUS-OFF jaune
    "R2": (139.0, 103.2, 0),
    "D1": (143.0, 103.2, 180),     # ERR rouge
    "R4": (118.5, 134.5, 90),      # tirages I2C (non montés)
    "R5": (121.5, 134.5, 90),
    # Capteurs reportés (non montés) : Hall et 1-Wire.
    "J8": (104.0, 128.6, 90),
    "J9": (113.5, 128.6, 90),
    "R6": (122.5, 128.6, 90),
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
        if ref.startswith("J") or ref in ("D1", "D2"):
            fp.Reference().SetVisible(False)  # repères remplacés par la sérigraphie ci-dessous
        for pad in fp.Pads():
            net = pads.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(nets[net])
                # Masse des barrettes des modules : connexion pleine au plan (un frein
                # thermique y garde trop peu de rayons entre les pistes voisines).
                if net == "GND" and ref in ("J5", "J6", "J8", "J9"):
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

    corners = [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)]
    for a, b in zip(corners, corners[1:] + corners[:1]):
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
        for c in corners:
            outline.Append(mm(c[0]), mm(c[1]))
        board.Add(zone)

    # Bande de 0,6 mm le long des bords, interdite aux pistes et aux vias (isolation de
    # 0,5 mm au contour demandée par la factory, que Freerouting ne connaît pas).
    lset = pcbnew.LSET()
    for c in (pcbnew.F_Cu, pcbnew.B_Cu):
        lset.AddLayer(c)
    b = 0.6
    for x0, y0, x1, y1 in ((X0, Y0, X1, Y0 + b), (X0, Y1 - b, X1, Y1),
                           (X0, Y0, X0 + b, Y1), (X1 - b, Y0, X1, Y1)):
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
        for cx, cy in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ko.Append(mm(cx), mm(cy))
        board.Add(keep)

    # Sérigraphie : sens de la Nucléo (une Nucléo à l'envers mettrait le 5 V sur une
    # broche d'E/S), repères du bus et des modules.
    silk(board, "<- USB Nucleo", 115.0, 102.2, 1.0)
    silk(board, "CN3", 104.0, CN3_Y, 0.9)
    silk(board, "CN4", 104.0, CN4_Y, 0.9)
    silk(board, "G69 porteuse v0.1", 126.5, 148.8, 0.9)
    silk(board, "N__", 151.0, 102.2, 1.2, 0.2)
    for txt, y in (("H", 107.44), ("L", 112.52), ("G", 117.6),
                   ("H", 127.84), ("L", 132.92), ("G", 138.0)):
        silk(board, txt, 154.2, y, 1.1, 0.18)
    silk(board, "ENTREE", 160.0, 102.2, 0.8)
    silk(board, "SORTIE", 150.5, 122.4, 0.8)
    silk(board, "TERM", 152.5, 135.7, 0.8)
    silk(board, "OLED G V C D", 112.0, 148.8, 0.8)
    silk(board, "MPU-6050", 146.0, 148.8, 0.8)
    silk(board, "ERR", 143.0, 105.4, 0.8)
    silk(board, "BOFF", 134.0, 105.4, 0.8)
    silk(board, "HALL", 106.5, 131.3, 0.8)
    silk(board, "1-WIRE", 116.0, 131.3, 0.8)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(PCB))
    print(f"{PCB.name} : {len(comps)} empreintes, {len(nets)} nets, carte "
          f"{X1 - X0:.1f} x {Y1 - Y0:.1f} mm")


if __name__ == "__main__":
    os.chdir(HERE)
    main()
