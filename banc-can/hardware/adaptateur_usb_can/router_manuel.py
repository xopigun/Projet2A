"""Route adaptateur_usb_can.kicad_pcb à partir de tables : pistes et vias posés par coordonnées.

    "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" router_manuel.py            # tout, DRC à chaque étape
    "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" router_manuel.py --vite     # tout, un seul DRC à la fin

À lancer après generate_pcb.py (placement) et verif_placement.py. Le script efface les pistes
et les vias de la carte, puis repose ceux des tables ETAPES dans l'ordre : quartz, alimentation
du STM32, USB et CH340C, UART et NRST, LED et signaux CAN, transceiver, alimentations longues,
vias de masse des composants. Il termine par la couture de masse (../poser_vias_couture.py),
le placement des repères de sérigraphie hors du cuivre nu, et un DRC complet (kicad-cli,
parité avec le schéma comprise). Le résultat est identique
d'une exécution à l'autre : rien n'est routé automatiquement.

Chaque étape pcbnew tourne dans un processus neuf (objets « SwigPyObject » inutilisables
après un second LoadBoard dans le même processus).

Règles suivies (remarques de l'enseignant d'électronique, voir SOURCES_COMPOSANTS.md) :
- le routage est sur F.Cu ; B.Cu ne porte que des ponts courts, pour garder un plan de masse
  d'un seul tenant sous le quartz, le STM32, la paire USB et la paire CAN ;
- quartz (ST AN2867) : pistes OSC de 4 mm sans via, anneau de garde relié au plan par un
  seul via près de la broche 32, garde entre C11 et NRST, aucune piste dessous ;
- paires CAN et USB : pistes côte à côte à 0,7 mm d'entraxe, plan de masse en face, aucun
  via sous la fiche USB ;
- chaque condensateur de découplage a sa pastille +3V3 contre la broche et un via de masse
  contre sa pastille GND.

Un point d'une piste est soit (x, y) en mm, soit "REF.pastille" (centre de la pastille), soit
(x, None) ou (None, y) pour reprendre l'autre coordonnée du point précédent.
"""

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
PCB = HERE / "adaptateur_usb_can.kicad_pcb"
CLI = r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"
COUTURE = HERE.parent / "poser_vias_couture.py"
LARGEUR = 0.4
VIA, PERCAGE = 0.8, 0.4
F, B = "F", "B"

# Étape -> (pistes, vias) ou (pistes, vias, pavés). Piste : (net, couche, largeur, [points]).
# Via : (net, x, y). Pavé : (net, couche, [sommets]), polygone de cuivre plein relié à son net.
ETAPES = {
    # ------------------------------------------------------------------ quartz (R3)
    "quartz": ([
        ("/OSC_IN", F, 0.4, ["U1.2", (124.2, None), (123.0, 111.8)]),       # dans la pastille de Y1
        ("/OSC_IN", F, 0.4, [(122.35, 109.5), (122.35, 108.6)]),            # Y1 -> C10
        ("/OSC_OUT", F, 0.4, ["U1.3", (124.2, None), (123.35, 114.65)]),
        ("/OSC_OUT", F, 0.4, [(122.2, 116.1), (121.9, 117.0)]),             # Y1 -> C11
        # Anneau de garde. Côté ouest : il réunit les masses de C10 et de C11.
        ("GND", F, 0.5, ["C10.2", (121.0, None), (120.5, 106.5625), (120.5, 119.0375),
                         (121.0, 119.5375), "C11.2"]),
        # Côté est, au nord des broches : entre le quartz et le tronc +3V3, jusqu'au seul via
        # de l'îlot, à 2,9 mm de la broche 32 (VSS).
        ("GND", F, 0.4, ["C10.2", (123.85, None), (124.35, 106.5625), (124.35, 110.9)]),
    ], [
        ("GND", 124.35, 110.9),
    ], [
        # Côté est, au sud des broches : garde de 0,4 mm entre C11 et NRST, de la pastille de
        # masse de C11 jusque sous la pastille sud de Y1 (un pavé : une piste finirait en l'air).
        ("GND", F, [(122.3, 119.35), (122.9, 119.35), (122.9, 116.6), (123.3, 116.6),
                    (123.3, 119.75), (122.3, 119.75)]),
    ]),
    # ------------------------------------------------------------------ alimentation du STM32 (R2)
    "alim_u1": ([
        ("GND", F, 0.4, ["U1.32", (126.7, 109.62)]),
        ("GND", F, 0.4, ["U1.14", (131.2, 116.2)]),
        ("GND", F, 0.4, ["U1.16", (132.8, 118.0), (132.15, 117.35)]),
        ("+3V3", F, 0.5, ["U1.1", (125.825, 111.38), (125.68, 111.24)]),    # via sous C5
        ("+3V3", F, 0.4, ["U1.17", (135.2, None), (135.6, 118.2)]),         # via vers C6
        # VDDA (15) : via vers C7/C8 juste sous la broche, puis lien vers la broche 17.
        ("+3V3", F, 0.4, ["U1.15", (132.0, 120.3), (132.4, 120.7), (133.0, 120.7)]),
        ("+3V3", F, 0.4, [(133.0, 120.7), (134.175, 119.525), "U1.17"]),
        ("GND", B, 0.5, ["C5.2", (127.85, 112.5)]),
        ("+3V3", B, 0.6, ["J3.4", (138.5025, 119.0375), (137.0, 119.0375)]),   # pont sous CAN et LED_ERR
        ("+3V3", B, 0.5, [(135.6, 118.2), "C6.1"]),
        ("GND", B, 0.5, ["C6.2", (136.3, 115.7)]),
        ("+3V3", B, 0.5, [(133.0, 120.7), "C7.1", "C8.1"]),
        ("+3V3", B, 0.5, ["C7.1", "C9.1"]),
        ("GND", B, 0.5, ["C7.2", (131.5, 122.9), "C8.2"]),
    ], [
        ("GND", 126.7, 109.62), ("GND", 131.2, 116.2), ("GND", 132.15, 117.35),
        ("+3V3", 125.68, 111.24), ("+3V3", 135.6, 118.2), ("+3V3", 133.0, 120.7),
        ("GND", 127.85, 112.5), ("GND", 136.3, 115.7), ("GND", 131.5, 122.9),
    ]),
    # ------------------------------------------------------------------ USB, CH340C, entrée 5 V (R5)
    "usb": ([
        # Paire USB en face avant : les deux pistes se resserrent à 0,7 mm d'entraxe dès la
        # sortie des pastilles de J1 et ne se rouvrent que sur les broches 5 et 6 de U2.
        ("USB_DP", F, 0.4, ["J1.3", (106.6, None), (107.25, 114.65), (108.6, None),
                            (109.585, 115.635), "U2.5"]),
        ("USB_DM", F, 0.4, ["J1.2", (106.6, None), (107.25, 115.35), (108.31, None),
                            (109.295, 116.335), (110.7, None), (111.27, 116.905), "U2.6"]),
        # Protection U5, sous les pastilles de J1 : un via dans chaque pastille (2 et 3 de J1 en
        # face avant, 3 et 1 de U5 en face arrière), symétriques, décalés de 0,1 mm vers
        # l'extérieur pour l'isolation avec la pastille de masse de U5. Aucun via ni piste de
        # la face arrière sous la paire, rien sous le corps de la fiche.
        ("USB_DP", B, 0.4, ["U5.1", "U5.6"]),
        ("USB_DM", B, 0.4, ["U5.3", "U5.4"]),
        ("GND", B, 0.4, ["U5.2", (108.4, 115.0)]),                          # masse de U5 : vers le plan, sous la paire
        # VBUS de U5 (broche 5, côté fiche) : rejoint le via VBUS par l'ouest puis le sud, entre
        # les pions de centrage et les pattes de blindage de J1.
        ("/VBUS", B, 0.4, ["U5.5", (101.75, None), (101.75, 118.9), (105.2, 118.9), (106.0, 119.7),
                           (106.0, 120.3)]),
        # Cette piste coupe deux rayons de la patte de blindage sud : la patte rejoint le plan
        # par une piste et un via, au sud.
        ("GND", B, 0.6, [(103.1, 120.7), (103.1, 122.9)]),
        ("/VBUS", F, 0.6, ["J1.1", (106.0, 120.3)]),
        ("/VBUS", B, 0.6, [(106.0, 120.3), "F1.1"]),
        ("GND", F, 0.4, ["U2.1", (113.9, None)]),
        ("+3V3", F, 0.5, ["U2.16", (118.9, None), "C3.1"]),                 # via dans la pastille de C3
        ("/CH_V3", F, 0.4, ["U2.4", (110.9, None)]),
        ("/CH_V3", B, 0.4, [(110.9, 114.365), (110.9, 113.6), "C4.1"]),
        ("/CH_V3", B, 0.4, [(110.9, 113.6), "R2.2"]),
        # +5 V : du fusible (pont sous l'UART) au régulateur par le canal sous le CH340C,
        # puis vers C1 par le nord, en face avant, avec un via contre lui.
        ("+5V", B, 0.6, ["F1.2", (110.7, None), (113.9, None), (116.0, 120.7)]),
        ("+5V", F, 0.5, [(116.0, 120.7), (115.75, 120.45), (115.75, 110.0), (116.68, 109.07),
                         (116.88, 109.07)]),
        ("+5V", B, 0.6, [(116.88, 109.07), "U4.3"]),
        ("+5V", F, 0.5, [(116.88, 109.07), (116.41, 108.6), (109.3, 108.6)]),
        ("+5V", F, 0.5, [(109.3, 108.6), (109.3, 106.1)]),
        ("+5V", B, 0.6, [(109.3, 106.1), "C1.1"]),
        # +3,3 V en face arrière : languette et broche 2 du régulateur, C2, R2.
        # (les ponts de la face arrière s'arrêtent dès qu'ils sont dans la pastille)
        ("+3V3", B, 0.6, [(112.6, 105.5), (117.4, 105.5)]),
        ("+3V3", B, 0.6, [(118.9, 105.4), (120.2, 105.4)]),                 # broche 2 -> C2
        ("+3V3", B, 0.6, [(111.9, 107.1), (111.9, 110.3)]),
        # C3 et le CH340C sont alimentés en face avant depuis le via de C2.
        ("+3V3", F, 0.5, [(120.6, 104.9), (119.6, 105.9), (119.6, 109.6), "C3.1"]),
    ], [
        ("USB_DP", 106.4875, 113.95), ("USB_DM", 106.4875, 116.05), ("/VBUS", 106.0, 120.3),
        ("GND", 103.1, 122.9),
        ("GND", 113.9, 110.555), ("+3V3", "C3.1"), ("/CH_V3", 110.9, 114.365),
        ("+5V", 116.0, 120.7), ("+5V", 116.88, 109.07), ("+5V", 109.3, 106.1),
    ]),
    # ------------------------------------------------------------------ UART et NRST
    "uart": ([
        # Tout sur F.Cu, sans via, par le canal entre les deux rangées de broches du CH340C.
        ("UART_RX", F, 0.4, ["U2.2", (113.75, None), (114.15, 112.225), (114.15, 122.15),
                             (114.55, 122.55), (125.425, 122.55), (125.825, 122.15), "U1.8"]),
        ("UART_TX", F, 0.4, ["U2.3", (110.9, None), (110.9, 109.9), (111.3, 109.5), (114.5, 109.5),
                             (114.9, 109.9), (114.9, 121.4), (115.3, 121.8), (124.1, 121.8),
                             (124.55, 121.35), (124.55, 117.35), (124.9, 117.0), "U1.7"]),
        # NRST descend entre la pastille sud de Y1 et les broches de U1, puis à l'est de la
        # piste de garde de C11.
        ("NRST", F, 0.4, ["U1.4", (124.7, None), (124.3, 115.0), (124.3, 116.6), (123.825, 117.075),
                          (123.825, 120.0), (123.5, 120.325), (123.5, 120.85)]),
        # C12 sert de pont sous les deux pistes UART.
        ("NRST", B, 0.4, [(123.5, 120.85), "C12.1", (122.0, None), (120.1, 123.7625), (120.1, 124.3)]),
        ("NRST", F, 0.4, [(120.1, 124.3), "SW1.1"]),
    ], [
        ("NRST", 123.5, 120.85), ("NRST", 120.1, 124.3),
    ]),
    # ------------------------------------------------------------------ LED, SWD, BOOT0, CAN logique
    "led_can": ([
        ("LED_RX", F, 0.4, ["U1.12", "R4.1"]),
        ("Net-(D2-A)", F, 0.4, ["R4.2", (129.6, 124.9), (128.575, 125.925)]),
        ("LED_TX", F, 0.4, ["U1.13", (130.4, 120.35), (131.8, 121.75), (134.4, 121.75)]),
        ("Net-(D3-A)", F, 0.4, ["R5.2", (134.4, 124.9), (133.375, 125.925)]),
        ("LED_ERR", F, 0.4, ["U1.18", (136.2, None), (136.6, 117.4), (136.6, 121.0), (137.2, 121.6),
                             "R8.1"]),
        ("Net-(D4-A)", F, 0.4, ["R8.2", (139.2, 124.9), (138.175, 125.925)]),
        ("GND", F, 0.5, ["D4.1", (140.225, 125.4)]),                        # cathode : vers son via
        ("GND", B, 0.6, [(138.3, 115.0), "J3.3", (141.7, 115.0)]),          # masse du SWD : deux rayons
        ("Net-(D1-A)", F, 0.4, ["D1.2", "R1.2"]),
        ("SWCLK", F, 0.4, ["U1.24", (134.175, 111.24), (137.32, 111.24), (138.64, 109.92), "J3.1"]),
        ("SWDIO", F, 0.4, ["U1.23", (135.2, None), (135.74, 112.46), "J3.2"]),
        ("/BOOT0", F, 0.4, ["SW2.2", (134.7, 106.9), (134.0, 107.6)]),      # via dans la pastille de R3
        ("/BOOT0", F, 0.4, [(134.0, 107.6), (133.0, 108.6), (128.6, 108.6), (128.0, 109.2), "U1.31"]),
        ("CAN_RX", F, 0.4, ["U1.21", (137.0, None), (137.4, 115.0), (137.4, 119.6), (137.8, 120.0),
                            (148.3, 120.0)]),
        ("CAN_TX", F, 0.4, ["U1.22", (137.8, None), (138.2, 114.2), (138.2, 118.6), (138.6, 119.0),
                            (151.9, 119.0), (152.705, 118.195), (152.705, 116.2)]),
        # CAN_S fait le tour par le sud puis par l'est du bornier et arrive sur la broche 8 de
        # U3 par le nord : il ne passe jamais au-dessus de la paire CAN, dont le plan de
        # masse de la face avant reste entier.
        ("CAN_S", F, 0.4, ["U1.9", (127.2, 127.25), (127.6, 127.65), (141.35, 127.65),
                           (142.0, 127.0), "R6.1", (142.0, 122.0), (142.4, 121.6), (152.75, 121.6),
                           (153.6, 122.45), (157.2, 122.45), (158.5, 121.15), (158.5, 108.7),
                           (157.7, 107.9), (154.6, 107.9), (152.705, 109.795), (152.705, 111.05)]),
    ], [
        ("/BOOT0", 134.0, 107.6), ("CAN_RX", 148.3, 120.0), ("CAN_TX", 152.705, 116.2),
        ("CAN_S", 152.705, 111.05),
    ]),
    # ------------------------------------------------------------------ transceiver et bus (R5, R7)
    "u3": ([
        # Paire CAN en face arrière. Les deux pistes quittent les broches 7 et 6 en biais,
        # courent côte à côte (0,7 mm d'entraxe) sous U3 puis en diagonale jusqu'entre les
        # bornes H et L, et ne se séparent que là. CANL finit en ligne droite : ce raccourci
        # compense son trajet extérieur dans les deux coudes.
        ("/CANH", B, 0.4, ["U3.7", (151.435, 113.5), (151.985, 114.05), (153.2, 114.05),
                           (155.0, 112.25), (156.3, 112.25), "J2.3"]),
        ("/CANL", B, 0.4, ["U3.6", (150.165, 113.5), (151.415, 114.75), (153.49, 114.75),
                           (155.29, 112.95), "J2.2"]),
        # Terminaison : R7 depuis CANH, JP1 depuis CANL (retour en face avant).
        ("/CANH", B, 0.4, [(155.6, 109.3), "R7.1"]),                        # depuis la borne H
        ("/CANL", B, 0.4, ["U3.6", (150.165, 110.5)]),
        ("/CANL", F, 0.4, [(150.165, 110.5), (147.205, 107.54), "JP1.2"]),
        ("Net-(JP1-A)", F, 0.4, ["JP1.1", (145.35, 105.0), (145.73, 105.38), (149.68, 105.38)]),
        ("Net-(JP1-A)", B, 0.4, [(149.68, 105.38), "R7.2"]),
        ("CAN_RX", B, 0.4, [(148.3, 120.0), (148.895, 119.405), "U3.4"]),
        ("CAN_TX", B, 0.4, [(152.705, 116.2), "U3.1"]),
        ("CAN_S", B, 0.4, [(152.705, 111.05), "U3.8"]),
        ("+3V3", B, 0.5, [(148.895, 115.0), (148.895, 113.3375)]),          # VIO
        ("+3V3", B, 0.5, ["C14.1", (148.895, None)]),
        ("+5V", B, 0.6, [(150.165, 122.75), "C13.1", "U3.3"]),
        ("GND", B, 0.5, ["U3.2", (151.435, 119.5), "C13.2"]),               # via dans la pastille de C13
    ], [
        ("/CANL", 150.165, 110.5), ("Net-(JP1-A)", 149.68, 105.38), ("+3V3", 148.895, 115.0),
        ("+5V", 150.165, 122.75), ("GND", "C13.2"),
    ]),
    # ------------------------------------------------------------------ alimentations longues, en face avant
    "alim": ([
        # +3,3 V : de C2 (via dans sa pastille) vers la broche 1 du STM32, puis tronc par le
        # bord nord vers SW2, R1, J3 et VIO du transceiver.
        ("+3V3", F, 0.6, [(120.6, 104.9), (121.3, 104.2), (125.5, 104.2)]),
        ("+3V3", F, 0.6, [(125.5, 104.2), (125.5, 110.9), (125.68, 111.24)]),
        ("+3V3", F, 0.6, [(125.5, 104.2), (125.5, 102.1), (126.1, 101.5), (131.3, 101.5),
                          (141.0, 101.5), (141.6, 102.1), (141.6, 103.5), (141.6, 114.06),
                          (142.54, 115.0)]),
        ("+3V3", F, 0.6, [(131.3, 101.5), "SW2.1"]),
        ("+3V3", F, 0.6, [(141.6, 103.5), "R1.1"]),
        ("+3V3", F, 0.6, [(142.54, 115.0), "J3.4"]),
        ("+3V3", F, 0.6, [(142.54, 115.0), (148.895, 115.0)]),
        # +5 V du transceiver : tronc par le bord sud.
        ("+5V", F, 0.6, [(110.7, 122.8), (110.7, 128.1), (111.2, 128.6), (149.3, 128.6),
                         (150.165, 127.735), (150.165, 122.75)]),
    ], [
        ("+3V3", 120.6, 104.9), ("+5V", 110.7, 122.8),
    ]),
    # ------------------------------------------------------------------ vias de masse des composants (R1)
    # Un via contre la pastille GND de chaque condensateur (C5 à C8 et C13 : étapes ci-dessus),
    # des cathodes de LED, de R3, R6, U4 ; C10 et C11 n'en ont pas, leur masse est l'îlot du
    # quartz. Le via de C12 touche aussi la pastille GND de SW1.
    "masse": ([], [
        ("GND", 109.3, 102.07),      # C1
        ("GND", 121.7, 102.46),      # C2
        ("GND", "C3.2"),             # C3, dans la pastille
        ("GND", 108.78, 110.4625),   # C4
        ("GND", 136.63, 123.9375),   # C9
        ("GND", 123.6, 124.83),      # C12 et SW1
        ("GND", 146.9, 110.37),      # C14
        ("GND", 131.5, 126.4),       # D2
        ("GND", 136.3, 126.4),       # D3
        ("GND", 140.225, 125.4),     # D4
        ("GND", 144.9, 124.0),       # R6
        ("GND", 137.0, 106.4),       # D1
        ("GND", 132.0, 106.8),       # R3
        ("GND", 118.15, 102.15),     # U4
        # Plan de la face avant au sud-est : CAN_S et le tronc +5 V l'entourent. Ce via le relie
        # à la masse (un morceau de plan sans liaison est retiré au remplissage).
        ("GND", 157.0, 126.0),
    ]),
}

# Couture de masse : cibles de ../poser_vias_couture.py, qui pose chaque via au plus près, là
# où le plan est rempli sur les deux faces. La grille de 8 mm est complétée tant qu'un point
# de la carte reste à plus de DISTANCE_MAX d'un via de masse.
GRILLE = [(x, y) for x in (103, 111, 119, 127, 135, 143, 151, 158) for y in (103, 111, 119, 127)]
# Un via de chaque côté de la paire CAN : il coud son plan de référence (face avant) au plan
# de la face arrière.
CIBLES_PAIRES = [(154.2, 111.2), (154.2, 116.2)]
DISTANCE_MAX = 8.0
CARTE = (100.0, 100.0, 160.0, 130.0)


# ------------------------------------------------------------------------------------------
def pcbnew_():
    import pcbnew
    return pcbnew


def poser(noms, effacer):
    """Pose les pistes et vias des étapes nommées, remplit les zones, enregistre."""
    pcbnew = pcbnew_()
    mm = pcbnew.FromMM
    board = pcbnew.LoadBoard(str(PCB))
    # Pastilles relevées en données Python avant tout retrait (et Delete, pas Remove) : sinon pcbnew
    # rend ensuite des « SwigPyObject » inutilisables pour les empreintes, ou plante.
    pads = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            pos = pad.GetPosition()
            pads.setdefault(f"{fp.GetReference()}.{pad.GetNumber()}", []).append(
                (pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y), pad.GetNetname()))
    nets = {n: board.FindNet(n) for etape in ETAPES.values() for n in
            {p[0] for el in etape for p in el}}
    if effacer:
        for t in list(board.GetTracks()):
            board.Delete(t)
        for g in list(board.GetDrawings()):         # pavés d'une exécution précédente
            if g.GetClass() == "PCB_SHAPE" and g.IsOnCopperLayer():
                board.Delete(g)

    def point(p, prec=None):
        if isinstance(p, str):
            assert len(pads[p]) == 1, f"pastille {p} ambiguë ou absente"
            return pads[p][0][:2]
        x, y = p
        return (prec[0] if x is None else x, prec[1] if y is None else y)

    def net(nom, p=None):
        assert nets[nom] is not None, f"net inconnu : {nom}"
        if isinstance(p, str):
            assert pads[p][0][2] == nom, f"{p} est sur {pads[p][0][2]}, pas {nom}"
        return nets[nom]

    couches = {F: pcbnew.F_Cu, B: pcbnew.B_Cu}
    for nom in noms:
        pistes, vias, *reste = ETAPES[nom]
        for netname, couche, sommets in (reste[0] if reste else []):
            g = pcbnew.PCB_SHAPE(board)
            g.SetShape(pcbnew.SHAPE_T_POLY)
            g.SetPolyPoints([pcbnew.VECTOR2I(mm(x), mm(y)) for x, y in sommets])
            g.SetFilled(True)
            g.SetWidth(0)
            g.SetLayer(couches[couche])
            g.SetNet(net(netname))
            board.Add(g)
        for netname, couche, largeur, points in pistes:
            prec = None
            for p in points:
                net(netname, p)
                cur = point(p, prec)
                if prec is not None and math.dist(prec, cur) > 1e-6:
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(pcbnew.VECTOR2I(mm(prec[0]), mm(prec[1])))
                    t.SetEnd(pcbnew.VECTOR2I(mm(cur[0]), mm(cur[1])))
                    t.SetWidth(mm(largeur))
                    t.SetLayer(couches[couche])
                    t.SetNet(net(netname))
                    board.Add(t)
                prec = cur
        for netname, *pos in vias:
            x, y = point(pos[0]) if len(pos) == 1 else pos
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
            v.SetWidth(mm(VIA))
            v.SetDrill(mm(PERCAGE))
            v.SetNet(net(netname, pos[0] if len(pos) == 1 else None))
            board.Add(v)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(PCB))


def vias_masse():
    """Positions (mm) des vias GND et des pastilles traversantes GND de la carte."""
    pcbnew = pcbnew_()
    board = pcbnew.LoadBoard(str(PCB))
    mm = pcbnew.ToMM
    pts = [(mm(t.GetPosition().x), mm(t.GetPosition().y)) for t in board.GetTracks()
           if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND"]
    return pts


def points_loin():
    """Points d'une grille de 0,5 mm à plus de DISTANCE_MAX d'un via GND, le plus loin d'abord."""
    vias = vias_masse()
    x0, y0, x1, y1 = CARTE
    loin = []
    for i in range(int((x1 - x0) / 0.5) + 1):
        for j in range(int((y1 - y0) / 0.5) + 1):
            p = (x0 + i * 0.5, y0 + j * 0.5)
            d = min(math.dist(p, v) for v in vias)
            if d > DISTANCE_MAX:
                loin.append((d, p))
    return sorted(loin, reverse=True)


REPERE_TAILLE, REPERE_TRAIT = 0.8, 0.12    # mm : hauteur mini des textes du projet, 0,8 mm
REPERE_RAYON, REPERE_PAS = 6.0, 0.25       # recherche autour du composant


def reperes():
    """Place les repères de sérigraphie, une fois le routage et la couture terminés.

    Chaque repère va au plus près de son composant, horizontal ou vertical, sans toucher une
    pastille, un via, un trou, le bord ni un autre texte (cuivre nu : il y serait tronqué), et
    si possible hors de tout courtyard, pour rester lisible une fois les composants soudés.
    Aucun repère n'est masqué.
    """
    pcbnew = pcbnew_()
    mm, MM = pcbnew.FromMM, pcbnew.ToMM
    board = pcbnew.LoadBoard(str(PCB))

    def boite(bb, marge=0.0):
        return (MM(bb.GetLeft()) - marge, MM(bb.GetTop()) - marge, MM(bb.GetRight()) + marge, MM(bb.GetBottom()) + marge)

    def touche(a, b):
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    durs = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}     # cuivre nu, trous, textes et traits
    mous = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}     # courtyards
    for fp in board.GetFootprints():
        silk = pcbnew.B_SilkS if fp.IsFlipped() else pcbnew.F_SilkS
        mous[silk].append(boite(fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd).BBox()))
        for pad in fp.Pads():
            for couche, cuivre in ((pcbnew.F_SilkS, pcbnew.F_Cu), (pcbnew.B_SilkS, pcbnew.B_Cu)):
                if pad.IsOnLayer(cuivre) or pad.GetDrillSize().x:
                    durs[couche].append(boite(pad.GetBoundingBox(), 0.15))
        for g in fp.GraphicalItems():
            if g.GetClass() == "PCB_SHAPE" and g.GetLayer() in durs:
                durs[g.GetLayer()].append(boite(g.GetBoundingBox(), 0.1))
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            for couche in durs:
                durs[couche].append(boite(t.GetBoundingBox(), 0.15))
    for g in board.GetDrawings():
        if g.GetClass() == "PCB_TEXT" and g.GetLayer() in durs:
            durs[g.GetLayer()].append(boite(g.GetBoundingBox(), 0.1))
    x0, y0, x1, y1 = CARTE
    bord = 0.6
    pas = [(i * REPERE_PAS, j * REPERE_PAS) for i in range(-int(REPERE_RAYON / REPERE_PAS), int(REPERE_RAYON / REPERE_PAS) + 1)
           for j in range(-int(REPERE_RAYON / REPERE_PAS), int(REPERE_RAYON / REPERE_PAS) + 1)]
    pas.sort(key=lambda d: (math.hypot(*d), d))
    sous_composant = []
    for fp in sorted(board.GetFootprints(), key=lambda f: f.GetReference()):
        ref = fp.Reference()
        silk = ref.GetLayer()
        ref.SetVisible(True)
        ref.SetTextSize(pcbnew.VECTOR2I(mm(REPERE_TAILLE), mm(REPERE_TAILLE)))
        ref.SetTextThickness(mm(REPERE_TRAIT))
        ref.SetTextAngleDegrees(0)
        bb = ref.GetBoundingBox()
        w, h = MM(bb.GetWidth()), MM(bb.GetHeight())
        pads_ = [pad.GetBoundingBox() for pad in fp.Pads()]
        cx = (MM(min(b.GetLeft() for b in pads_)) + MM(max(b.GetRight() for b in pads_))) / 2
        cy = (MM(min(b.GetTop() for b in pads_)) + MM(max(b.GetBottom() for b in pads_))) / 2
        cx, cy = min(max(cx, x0), x1), min(max(cy, y0), y1)
        pres = [o for o in durs[silk] if o[0] < cx + 8 and o[2] > cx - 8 and o[1] < cy + 8 and o[3] > cy - 8]
        secours = None
        choix = None
        for dx, dy in pas:
            for angle, (lw, lh) in ((0, (w, h)), (90, (h, w))):
                r = (cx + dx - lw / 2, cy + dy - lh / 2, cx + dx + lw / 2, cy + dy + lh / 2)
                if r[0] < x0 + bord or r[1] < y0 + bord or r[2] > x1 - bord or r[3] > y1 - bord:
                    continue
                if any(touche(r, o) for o in pres):
                    continue
                if any(touche(r, o) for o in mous[silk]):
                    secours = secours or (dx, dy, angle, r)
                    continue
                choix = (dx, dy, angle, r)
                break
            if choix:
                break
        if choix is None:
            choix = secours
            sous_composant.append(fp.GetReference())
        assert choix, f"pas de place pour le repère {fp.GetReference()}"
        dx, dy, angle, r = choix
        ref.SetTextAngleDegrees(angle)
        ref.SetPosition(pcbnew.VECTOR2I(mm(cx + dx), mm(cy + dy)))
        durs[silk].append((r[0] - 0.1, r[1] - 0.1, r[2] + 0.1, r[3] + 0.1))
    board.Save(str(PCB))
    print(f"   repères de sérigraphie : {len(board.GetFootprints())} placés, tous visibles"
          + (f" ; dans un courtyard faute de place : {sous_composant}" if sous_composant else ""))


def drc(titre, detail=True):
    """Lance le DRC complet (parité comprise) ; renvoie (erreurs, avertissements, non connectés, parité)."""
    out = Path(tempfile.gettempdir()) / "adaptateur_usb_can_drc.json"
    subprocess.run([CLI, "pcb", "drc", "--schematic-parity", "--severity-all", "--format", "json",
                    "-o", str(out), str(PCB)], check=True, capture_output=True)
    r = json.loads(out.read_text(encoding="utf-8"))
    viol = r.get("violations", [])
    err = [v for v in viol if v["severity"] == "error"]
    avert = [v for v in viol if v["severity"] != "error"]
    nc, par = r.get("unconnected_items", []), r.get("schematic_parity", [])
    sys.stdout.flush()
    print(f"== DRC après « {titre} » : {len(err)} erreur(s), {len(avert)} avertissement(s), "
          f"{len(nc)} non connecté(s), parité {len(par)}")
    if detail:
        for v in err + avert + par:
            items = " | ".join(f"{i['description']} @({i['pos']['x']:.2f},{i['pos']['y']:.2f})"
                               for i in v.get("items", []))
            print(f"   {v['severity']:7s} {v['type']:22s} {v['description']} : {items}")
        for v in nc:
            print("   non connecté : " + " | ".join(
                f"{i['description']} @({i['pos']['x']:.2f},{i['pos']['y']:.2f})" for i in v["items"]))
    return len(err), len(avert), len(nc), len(par)


def soi(*args):
    subprocess.run([sys.executable, __file__, *args], check=True)


def couture():
    cibles = CIBLES_PAIRES + GRILLE
    for _ in range(8):
        if cibles:
            sys.stdout.flush()
            subprocess.run([sys.executable, str(COUTURE), str(PCB), *[f"{x},{y}" for x, y in cibles]],
                           check=True)
        loin = json.loads(subprocess.run([sys.executable, __file__, "--loin"], check=True,
                                         capture_output=True, text=True).stdout)
        if not loin:
            break
        cibles = [tuple(loin[0][1])]
        print(f"   {len(loin)} point(s) à plus de {DISTANCE_MAX} mm d'un via GND, le pire à "
              f"{loin[0][0]:.1f} mm en {cibles[0]} : cible ajoutée")


def main(argv):
    if argv[:1] == ["--etapes"]:
        poser(argv[2:], effacer=argv[1] == "1")
    elif argv[:1] == ["--loin"]:
        print(json.dumps(points_loin()))
    elif argv[:1] == ["--reperes"]:
        reperes()
    elif argv[:1] == ["--drc"]:
        drc("carte actuelle")
    else:
        noms = list(ETAPES)
        if "--vite" in argv:
            soi("--etapes", "1", *noms)
        else:
            for i, nom in enumerate(noms):
                soi("--etapes", "1" if i == 0 else "0", nom)
                drc(nom, detail=False)
        if "--sans-couture" not in argv:
            couture()
        soi("--reperes")
        erreurs, _avertissements, non_connectes, parite = drc("routage complet")
        return 0 if (erreurs, non_connectes, parite) == (0, 0, 0) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
