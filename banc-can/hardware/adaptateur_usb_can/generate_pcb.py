"""Prépare adaptateur_usb_can.kicad_pcb : contour, empreintes placées, nets, plan de masse.

Point de départ du routage, pas un générateur à relancer : il repart du gabarit ENSEA
et écrase la carte, routage compris. À exécuter avec le Python livré avec KiCad 9 :

    "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" generate_pcb.py

Les nets viennent du schéma (netlist exportée par kicad-cli) et chaque empreinte reçoit
le chemin /<uuid du symbole> : « Mettre à jour le PCB depuis le schéma » (F8) la retrouve.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import pcbnew

import kisym

HERE = Path(__file__).parent
SCH = HERE / "adaptateur_usb_can.kicad_sch"
PCB = HERE / "adaptateur_usb_can.kicad_pcb"
TEMPLATE = HERE.parent / "regles_fabrication" / "20260112_ENSEA_2_layers_drc.kicad_pcb"
KICAD = Path(r"C:\Program Files\KiCad\9.0")
FOOTPRINTS = KICAD / "share" / "kicad" / "footprints"

# Contour (mm). L'USB-B déborde à gauche, le bornier CAN à droite (entrées des fils vers
# l'extérieur), comme des connecteurs de façade.
X0, Y0, X1, Y1 = 104.0, 100.0, 191.7, 141.0

# Référence : (x, y, rotation en degrés) de l'origine de l'empreinte, face avant.
PLACEMENT = {
    # USB, protection, alimentation
    "J1": (118.0, 121.0, 180),
    "U5": (126.0, 117.5, 0),
    "F1": (125.0, 108.0, 0),
    "U4": (127.0, 131.0, 0),
    "C1": (126.0, 138.3, 0),
    "C2": (133.5, 129.5, 90),
    # Pont USB-série, broches 1 à 8 en haut
    "U2": (138.0, 122.0, 270),
    "R2": (134.5, 114.5, 0),
    "C4": (140.5, 114.5, 0),
    "C3": (146.0, 125.0, 90),
    # Microcontrôleur
    "U1": (158.0, 121.0, 0),
    "Y1": (150.0, 104.0, 270),
    "C10": (145.5, 104.0, 90),
    "C11": (145.5, 109.5, 90),
    "C5": (153.5, 113.5, 0),
    "R3": (159.5, 112.5, 0),
    "C12": (149.0, 120.5, 90),
    "C6": (165.5, 127.0, 90),
    "C7": (157.5, 129.0, 0),
    "C8": (157.5, 132.3, 0),
    "C9": (164.0, 110.0, 90),
    "SW1": (137.0, 133.0, 0),
    "SW2": (146.5, 133.0, 0),
    "J3": (167.5, 104.0, 0),
    # LED
    "R4": (164.0, 131.5, 0),
    "D2": (164.0, 135.5, 0),
    "R5": (170.0, 131.5, 0),
    "D3": (170.0, 135.5, 0),
    "R1": (176.0, 131.5, 0),
    "D1": (176.0, 135.5, 0),
    # Bus CAN
    "U3": (174.5, 119.0, 0),
    "C13": (172.0, 113.0, 0),
    "C14": (176.0, 124.5, 0),
    "R6": (177.5, 113.0, 90),
    "R7": (179.0, 103.5, 0),
    "JP1": (175.5, 107.5, 90),
    # Bornier : broche 1 (GND) en bas, de haut en bas H, L, G comme l'USBCAN-Z.
    "J2": (188.0, 128.52, 90),
    # Fixations
    "H1": (108.5, 104.5, 0),
    "H2": (108.5, 136.5, 0),
}


def mm(v):
    return pcbnew.FromMM(v)


def point(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def netlist():
    """Composants {ref: (valeur, empreinte, uuid)} et nets {(ref, pad): net} du schéma."""
    out = Path(tempfile.gettempdir()) / "adaptateur_usb_can.net"
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
        for pad in fp.Pads():
            net = pads.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(nets[net])

    corners = [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        segment(board, pcbnew.Edge_Cuts, a, b)

    # Plan de masse en face arrière ; le routage se fait d'abord en face avant.
    zone = pcbnew.ZONE(board)
    zone.SetLayer(pcbnew.B_Cu)
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

    label = pcbnew.PCB_TEXT(board)
    label.SetText("G69 USB-CAN v0.1 - ENSEA 2A")
    label.SetLayer(pcbnew.F_SilkS)
    label.SetPosition(point(150.0, 139.3))
    label.SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
    label.SetTextThickness(mm(0.15))
    board.Add(label)

    # Repères des bornes du bus, à gauche du bornier.
    for txt, y in (("H", 118.36), ("L", 123.44), ("G", 128.52)):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(txt)
        t.SetLayer(pcbnew.F_SilkS)
        t.SetPosition(point(181.0, y))
        t.SetTextSize(pcbnew.VECTOR2I(mm(1.2), mm(1.2)))
        t.SetTextThickness(mm(0.18))
        board.Add(t)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(PCB))
    print(f"{PCB.name} : {len(comps)} empreintes, {len(nets)} nets, carte "
          f"{X1 - X0:.1f} x {Y1 - Y0:.1f} mm")


if __name__ == "__main__":
    os.chdir(HERE)
    main()
