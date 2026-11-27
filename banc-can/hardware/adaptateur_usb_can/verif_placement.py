"""Vérifie le placement produit par generate_pcb.py, avant tout routage.

    "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" verif_placement.py

- les composants figés par le boîtier imprimé (boitier/boitier.scad) et ceux qui ne devaient
  pas bouger sont à leur place, pastilles comprises ;
- chaque pastille dont dépend le routage de router_manuel.py est à l'endroit attendu, avec
  le bon net : c'est ce contrôle qui valide les rotations du tableau PLACEMENT ;
- aucun chevauchement de courtyards sur une même face ;
- les composants de la face arrière restent hors du rebord d'appui du boîtier (1 mm).

Code de retour 0 si tout est bon, 1 sinon.
"""

import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).parent
PCB = HERE / "adaptateur_usb_can.kicad_pcb"
TOL = 0.02  # mm

# Référence -> (face, x, y) du centre : composants qui ne doivent pas bouger.
FIGES = {
    "J1": ("F", 96.2, 115.0), "J2": ("F", 156.3, 120.08), "J3": ("F", 140.0, 109.92),
    "JP1": ("F", 144.0, 105.0), "SW1": ("F", 121.8, 126.0), "SW2": ("F", 133.0, 104.0),
    "D1": ("F", 137.0, 104.5), "D2": ("F", 129.6, 126.4), "D3": ("F", 134.4, 126.4),
    "U1": ("F", 130.0, 115.0), "U2": ("F", 115.0, 115.0), "U4": ("B", 115.0, 105.5),
    "F1": ("B", 107.6, 122.8),
}

# (référence, pastille) -> (net, x, y). Pastilles des connecteurs figés (relevé de la carte
# v0.2) et pastilles dont les coordonnées servent au routage.
PASTILLES = {
    ("J1", "1"): ("/VBUS", 105.85, 118.5), ("J1", "2"): ("USB_DM", 105.85, 116.0),
    ("J1", "3"): ("USB_DP", 105.85, 114.0), ("J1", "4"): ("GND", 105.85, 111.5),
    ("J2", "1"): ("GND", 156.3, 120.08), ("J2", "2"): ("/CANL", 156.3, 115.0),
    ("J2", "3"): ("/CANH", 156.3, 109.92),
    ("J3", "1"): ("SWCLK", 140.0, 109.92), ("J3", "4"): ("+3V3", 140.0, 117.54),
    ("JP1", "1"): ("Net-(JP1-A)", 144.0, 105.0), ("JP1", "2"): ("/CANL", 144.0, 107.54),
    ("SW1", "1"): ("NRST", 120.1, 126.0), ("SW1", "2"): ("GND", 123.5, 126.0),
    ("SW2", "1"): ("+3V3", 131.3, 104.0), ("SW2", "2"): ("/BOOT0", 134.7, 104.0),
    ("D1", "2"): ("Net-(D1-A)", 137.0, 103.475), ("D1", "1"): ("GND", 137.0, 105.525),
    ("U1", "1"): ("+3V3", 125.825, 112.2), ("U1", "2"): ("/OSC_IN", 125.825, 113.0),
    ("U1", "3"): ("/OSC_OUT", 125.825, 113.8), ("U1", "18"): ("LED_ERR", 134.175, 117.0),
    ("U2", "1"): ("GND", 112.525, 110.555), ("U2", "16"): ("+3V3", 117.475, 110.555),
    ("F1", "1"): ("/VBUS", 106.1125, 122.8), ("F1", "2"): ("+5V", 109.0875, 122.8),
    ("C1", "1"): ("+5V", 109.3, 105.0375), ("C2", "1"): ("+3V3", 120.6, 105.3375),
    ("C4", "1"): ("/CH_V3", 109.8, 112.5375), ("U4", "1"): ("GND", 118.15, 103.2),
    ("U4", "3"): ("+5V", 118.15, 107.8), ("U5", "5"): ("/VBUS", 104.2125, 115.0),
    # Protection USB traversée en ligne : D+ au nord, D- au sud, masse à l'est, VBUS à l'ouest.
    ("U5", "1"): ("USB_DP", 106.4875, 114.05), ("U5", "6"): ("USB_DP", 104.2125, 114.05),
    ("U5", "3"): ("USB_DM", 106.4875, 115.95), ("U5", "4"): ("USB_DM", 104.2125, 115.95),
    ("U5", "2"): ("GND", 106.4875, 115.0),
    ("R7", "1"): ("/CANH", 152.8, 106.5), ("R7", "2"): ("Net-(JP1-A)", 150.8, 106.5),
    # Quartz
    ("Y1", "1"): ("/OSC_IN", 122.35, 110.65), ("Y1", "2"): ("/OSC_OUT", 122.35, 114.95),
    ("C10", "1"): ("/OSC_IN", 122.35, 108.1375), ("C10", "2"): ("GND", 122.35, 106.0625),
    ("C11", "1"): ("/OSC_OUT", 121.85, 117.4625), ("C11", "2"): ("GND", 121.85, 119.5375),
    # Découplages et passifs de la face arrière
    ("C5", "1"): ("+3V3", 125.7025, 111.1), ("C5", "2"): ("GND", 127.7775, 111.1),
    ("C3", "1"): ("+3V3", 119.35, 110.1025), ("C3", "2"): ("GND", 119.35, 112.1775),
    ("C12", "1"): ("NRST", 123.6, 121.8625), ("C12", "2"): ("GND", 123.6, 123.9375),
    ("C6", "1"): ("+3V3", 136.4, 119.0375), ("C6", "2"): ("GND", 136.4, 116.9625),
    ("C7", "1"): ("+3V3", 133.4375, 121.5), ("C7", "2"): ("GND", 131.3625, 121.5),
    ("C8", "1"): ("+3V3", 133.4375, 123.6), ("C8", "2"): ("GND", 131.3625, 123.6),
    ("C9", "1"): ("+3V3", 135.6, 121.8625), ("C9", "2"): ("GND", 135.6, 123.9375),
    ("C13", "1"): ("+5V", 150.1625, 120.3), ("C13", "2"): ("GND", 152.2375, 120.3),
    ("C14", "1"): ("+3V3", 146.9, 113.3375), ("C14", "2"): ("GND", 146.9, 111.2625),
    ("R2", "1"): ("+3V3", 111.9, 110.6), ("R2", "2"): ("/CH_V3", 111.9, 112.6),
    ("R3", "1"): ("/BOOT0", 134.0, 107.8), ("R3", "2"): ("GND", 132.0, 107.8),
    # Transceiver décalé de 1 mm vers l'ouest
    ("U3", "1"): ("CAN_TX", 152.705, 117.475), ("U3", "2"): ("GND", 151.435, 117.475),
    ("U3", "3"): ("+5V", 150.165, 117.475), ("U3", "4"): ("CAN_RX", 148.895, 117.475),
    ("U3", "5"): ("+3V3", 148.895, 112.525), ("U3", "6"): ("/CANL", 150.165, 112.525),
    ("U3", "7"): ("/CANH", 151.435, 112.525), ("U3", "8"): ("CAN_S", 152.705, 112.525),
    # Face avant
    ("R1", "2"): ("Net-(D1-A)", 138.95, 103.5), ("R1", "1"): ("+3V3", 140.95, 103.5),
    ("R4", "1"): ("LED_RX", 129.6, 121.6), ("R4", "2"): ("Net-(D2-A)", 129.6, 123.6),
    ("R5", "1"): ("LED_TX", 134.4, 121.6), ("R5", "2"): ("Net-(D3-A)", 134.4, 123.6),
    ("R8", "1"): ("LED_ERR", 139.2, 121.6), ("R8", "2"): ("Net-(D4-A)", 139.2, 123.6),
    ("R6", "1"): ("CAN_S", 142.0, 124.0), ("R6", "2"): ("GND", 144.0, 124.0),
    ("D2", "2"): ("Net-(D2-A)", 128.575, 126.4), ("D2", "1"): ("GND", 130.625, 126.4),
    ("D3", "2"): ("Net-(D3-A)", 133.375, 126.4), ("D3", "1"): ("GND", 135.425, 126.4),
    ("D4", "2"): ("Net-(D4-A)", 138.175, 126.4), ("D4", "1"): ("GND", 140.225, 126.4),
}

# Rebord d'appui du boîtier : bande de 1 mm sans composant au dos de la carte (100..160, 100..130).
DOS = (101.0, 101.0, 159.0, 129.0)


def main():
    board = pcbnew.LoadBoard(str(PCB))
    mm = pcbnew.ToMM
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    erreurs = []

    for ref, (face, x, y) in FIGES.items():
        f = fps[ref]
        pos = (mm(f.GetPosition().x), mm(f.GetPosition().y))
        if ("B" if f.IsFlipped() else "F") != face or abs(pos[0] - x) > TOL or abs(pos[1] - y) > TOL:
            erreurs.append(f"{ref} déplacé : {'B' if f.IsFlipped() else 'F'} {pos}, attendu {face} ({x}, {y})")

    for (ref, num), (net, x, y) in PASTILLES.items():
        pads = [p for p in fps[ref].Pads() if p.GetNumber() == num]
        ok = any(p.GetNetname() == net and abs(mm(p.GetPosition().x) - x) <= TOL
                 and abs(mm(p.GetPosition().y) - y) <= TOL for p in pads)
        if not ok:
            vus = [(p.GetNetname(), round(mm(p.GetPosition().x), 3), round(mm(p.GetPosition().y), 3))
                   for p in pads]
            erreurs.append(f"pastille {ref}.{num} : {vus}, attendu {(net, x, y)}")

    boites = {}
    for ref, f in fps.items():
        couche = pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd
        bb = f.GetCourtyard(couche).BBox()
        boites[ref] = ("B" if f.IsFlipped() else "F", mm(bb.GetLeft()), mm(bb.GetTop()),
                       mm(bb.GetRight()), mm(bb.GetBottom()))
    refs = sorted(boites)
    for i, a in enumerate(refs):
        for b in refs[i + 1:]:
            fa, ax0, ay0, ax1, ay1 = boites[a]
            fb, bx0, by0, bx1, by1 = boites[b]
            if fa == fb and min(ax1, bx1) - max(ax0, bx0) > 0.001 and min(ay1, by1) - max(ay0, by0) > 0.001:
                erreurs.append(f"courtyards de {a} et {b} superposés (face {fa})")
    for ref, (face, x0, y0, x1, y1) in boites.items():
        if face == "B" and (x0 < DOS[0] or y0 < DOS[1] or x1 > DOS[2] or y1 > DOS[3]):
            erreurs.append(f"{ref} (face arrière) déborde sur le rebord du boîtier : "
                           f"x {x0:.2f}..{x1:.2f}, y {y0:.2f}..{y1:.2f}")

    for e in erreurs:
        print("ERREUR", e)
    print(f"placement : {len(fps)} empreintes, {len(FIGES)} positions figées et "
          f"{len(PASTILLES)} pastilles contrôlées, {len(erreurs)} erreur(s)")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
