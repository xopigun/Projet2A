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

# Contour (mm) : 60 x 30 mm. La fiche USB-A déborde à gauche comme une clé (seule sa base est sur la
# carte), le bornier CAN à droite (entrées des fils vers l'extérieur).
X0, Y0, X1, Y1 = 100.0, 100.0, 160.0, 130.0

# Référence : (x, y, rotation en degrés, face). Face avant « F » : connecteurs, circuits
# intégrés, boutons, LED. Face arrière « B » : régulateur, protection USB, quartz, passifs.
PLACEMENT = {
    # Face avant. Chaque composant est placé du côté du STM32 où se trouve sa broche :
    # quartz, NRST et UART à gauche (broches 1 à 8), LED, VDDA et CAN_S en bas (9 à 16),
    # CAN et SWD à droite (17 à 24), BOOT0 en haut (31).
    "J1": (96.2, 115.0, 180, "F"),     # fiche USB-A mâle : repère « PCB Edge » sur le bord
    "U2": (115.0, 115.0, 0, "F"),      # CH340C
    "U1": (130.0, 115.0, 0, "F"),      # STM32G431KBT6
    # Bornier : broche 1 (GND) en bas, de haut en bas H, L, G comme l'USBCAN-Z.
    "J2": (156.3, 120.08, 90, "F"),
    "J3": (140.0, 109.92, 0, "F"),     # SWD
    "JP1": (144.0, 105.0, 0, "F"),     # terminaison 120 ohms
    "D2": (129.6, 126.4, 90, "F"),     # RX
    "D3": (134.4, 126.4, 90, "F"),     # TX
    "SW1": (121.8, 126.0, 0, "F"),     # RESET
    "SW2": (133.0, 104.0, 0, "F"),     # BOOT0
    "D1": (137.0, 104.5, 90, "F"),     # PWR
    # Face arrière. Rien sous les rangées de broches des circuits de la face avant, et des
    # couloirs entre composants pour les vias de masse.
    "U4": (115.0, 105.5, 0, "B"),      # régulateur, au-dessus du CH340C
    "C1": (109.3, 104.0, 90, "B"),
    "C2": (120.6, 105.0, 90, "B"),
    "F1": (107.6, 122.8, 0, "B"),     # fusible, près de VBUS
    "U5": (105.5, 115.0, 90, "B"),     # protection USB, sous la fiche
    "C4": (109.8, 111.5, 90, "B"),     # entre l'USB et le CH340C
    "R2": (109.8, 118.5, 90, "B"),
    "C3": (120.2, 111.2, 90, "B"),     # entre le CH340C et le STM32
    "C5": (122.8, 110.0, 90, "B"),
    "C12": (120.2, 117.0, 90, "B"),
    "R4": (129.6, 122.6, 90, "F"),     # LED sous le STM32 (PA7, PB0)
    "R5": (134.4, 122.6, 90, "F"),
    "Y1": (124.5, 106.5, 180, "F"),    # quartz : broche 1 à droite, sans croisement
    "C10": (128.6, 106.5, 90, "F"),
    "C11": (120.4, 106.5, 90, "F"),
    "R3": (133.0, 107.8, 0, "B"),
    "R1": (139.5, 103.0, 0, "B"),
    "C6": (136.4, 118.0, 90, "B"),     # VDD broche 17
    "C9": (127.0, 122.4, 0, "B"),      # sous le STM32
    "C7": (132.6, 122.4, 0, "B"),      # 10 nF de VDDA au plus près de la broche 15
    "C8": (132.6, 126.0, 0, "B"),
    "R6": (127.0, 126.0, 0, "B"),
    "U3": (151.8, 115.0, 90, "B"),     # transceiver, sous le bornier
    "C13": (147.4, 112.0, 90, "B"),
    "C14": (147.4, 118.5, 90, "B"),
    "R7": (151.8, 106.5, 0, "B"),
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
        x, y, rot, face = PLACEMENT[ref]
        fp.SetPosition(point(x, y))
        fp.SetOrientationDegrees(rot)
        if face == "B":  # après Add : Flip a besoin de la carte pour ses couches
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        for pad in fp.Pads():
            net = pads.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(nets[net])

    corners = [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        segment(board, pcbnew.Edge_Cuts, a, b)

    # Plan de masse sur les deux faces : des composants sont soudés de chaque côté.
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

    # Bande de 0,6 mm le long des bords, interdite aux pistes et aux vias : Freerouting
    # ne connaît pas l'isolation de 0,5 mm au contour demandée par la factory.
    def interdire(rect, couches, vias):
        lset = pcbnew.LSET()
        for c in couches:
            lset.AddLayer(c)
        x0, y0, x1, y1 = rect
        keep = pcbnew.ZONE(board)
        keep.SetIsRuleArea(True)
        keep.SetLayerSet(lset)
        keep.SetDoNotAllowTracks(True)
        keep.SetDoNotAllowVias(vias)
        keep.SetDoNotAllowPads(False)
        keep.SetDoNotAllowFootprints(False)
        keep.SetDoNotAllowCopperPour(False)
        ko = keep.Outline()
        ko.NewOutline()
        for cx, cy in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ko.Append(mm(cx), mm(cy))
        board.Add(keep)

    deux = (pcbnew.F_Cu, pcbnew.B_Cu)
    b = 0.6
    for rect in ((X0, Y0, X1, Y0 + b), (X0, Y1 - b, X1, Y1),
                 (X0, Y0, X0 + b, Y1), (X1 - b, Y0, X1, Y1)):
        interdire(rect, deux, vias=True)
    # Sous le STM32 : centre réservé au plan de masse, sans piste, sur les deux faces (aide au
    # routage, retirée une fois la carte terminée). Ses
    # broches de masse (14, 16, 32) et les pastilles de masse des découplages, tournées vers
    # le centre, s'y raccordent ; des vias de couture relient les deux faces.
    ux, uy = PLACEMENT["U1"][:2]
    interdire((ux - 2.9, uy - 3.4, ux + 2.9, uy + 3.4), (pcbnew.F_Cu,), vias=False)
    interdire((ux - 2.9, uy - 5.5, ux + 2.9, uy + 6.0), (pcbnew.B_Cu,), vias=False)

    label = pcbnew.PCB_TEXT(board)
    label.SetText("G69 v0.2")
    label.SetLayer(pcbnew.F_SilkS)
    label.SetPosition(point(115.0, 103.0))
    label.SetTextSize(pcbnew.VECTOR2I(mm(0.9), mm(0.9)))
    label.SetTextThickness(mm(0.15))
    board.Add(label)

    # Repères des bornes du bus, à gauche du bornier.
    for txt, y in (("H", 109.92), ("L", 115.0), ("G", 120.08)):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(txt)
        t.SetLayer(pcbnew.F_SilkS)
        t.SetPosition(point(149.3, y))
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
