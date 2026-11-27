"""Routage de la carte porteuse, par coordonnées (remplace Freerouting depuis la v0.4).

À lancer sur la carte que vient d'écrire generate_pcb.py (aucune piste), avec le Python de
KiCad 9 :

    "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" router_manuel.py

Principes (remarques du cours d'électronique) :
- la face arrière est le plan de masse : elle ne porte que cinq ponts courts (28 mm en tout),
  aucun sous U1 ni sous la paire CAN. Quatre partent d'une pastille traversante de CN4 ou
  CN3, qui sert de changement de face ; le cinquième fait passer CAN_S (option non montée)
  sous le +3V3 du MPU-6050 et sous CAN_TX ;
- CANH et CANL vont de U1 au bornier côte à côte sur la face avant, sans via, à 0,35 mm
  d'écart ; un palier de 1,07 mm sur CANL, à l'arrivée sur le bornier, égalise les longueurs ;
- le long de CN4, les pistes descendent dans quatre couloirs (x = 112,9 à 115,8) ; devant la
  fixation H2 il n'en reste que trois, à 1,4 mm au moins de la tête de vis (cuivre nu) ;
- aucune piste de masse : le plan et les vias (coudre_gnd.py) suffisent. Seules exceptions,
  six liaisons de moins de 3 mm entre une pastille CMS et son via.
Les croisements imposés par le brochage (CN4 et la barrette du MPU-6050 ont SCL, SDA et INT
dans l'ordre inverse ; CAN_TX, CAN_S et CAN_RX arrivent par le nord, l'I2C repart vers l'OLED
au sud) se font tous sur une pastille traversante ou par un pont de moins de 8 mm.
Les coordonnées sont celles de PLACEMENT dans generate_pcb.py : si un composant bouge,
reprendre les pistes qui y arrivent, puis relancer verifier_criteres.py.
"""

import math
import os
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).parent
PCB = HERE / "carte_porteuse.kicad_pcb"
F, B = "F", "B"

# (net, face, largeur en mm, points)
PISTES = [
    # Paire CAN, de U1 (broches 7 et 6) au bornier J1 (bornes 3 et 2).
    ("/CANH", F, 0.4, [(123.375, 112.665), (124.635, 112.665), (134.3, 103.0)]),
    ("/CANL", F, 0.4, [(123.375, 113.935), (124.42, 113.935), (131.755, 106.6), (132.82, 106.6), (134.3, 108.08)]),
    # Terminaison, prise sur les bornes : CANH - R1 - TERM_T - cavalier J7 - CANL.
    # La branche CANH contourne les bornes L et G par l'est, à 0,8 mm de leurs pastilles.
    ("/CANH", F, 0.4, [(134.3, 103.0), (136.6, 105.3), (136.6, 115.4), (135.2, 116.8), (135.2, 117.5)]),
    ("/CANL", F, 0.4, [(134.3, 108.08), (132.3, 110.08), (132.3, 118.2), (131.5, 119.0)]),
    ("TERM_T", F, 0.4, [(131.5, 121.54), (133.16, 121.54), (135.2, 119.5)]),
    # Broche S : R7 (à la masse, monté), R8 (vers PB6, non monté). CAN_S contourne H1 à 1,5 mm
    # de la tête de vis, passe sous le +3V3 et sous CAN_TX par un pont de 7,9 mm, puis
    # descend le long de CN4 sur la face avant jusqu'à PB6.
    ("TJA_S", F, 0.4, [(123.375, 111.395), (123.7, 111.07), (123.7, 108.9), (126.0, 108.9)]),
    ("CAN_S", F, 0.4, [(126.0, 106.9), (126.0, 102.45), (125.4, 101.85), (115.3, 101.85), (114.6, 102.55), (114.6, 108.9)]),
    ("CAN_S", B, 0.4, [(114.6, 108.9), (114.6, 116.5), (114.8, 116.7)]),
    ("CAN_S", F, 0.4, [(114.8, 116.7), (114.8, 126.2), (113.65, 127.35), (113.65, 133.2), (112.9, 133.95), (112.9, 134.1),
                       (111.9, 135.1), (111.43, 135.32)]),
    # +3V3 : tronc le long de CN3 (0,5 mm : 0,37 mm d'isolation aux pastilles), C2 puis U1.5 ;
    # branche vers le MPU-6050 par le canal de 3 mm sous le boîtier de U1 et le nord de CN4.
    # Elle passe à y = 110,4 pour rester à 1 mm de la tête de vis H1 (cuivre nu).
    ("+3V3", F, 0.5, [(126.67, 148.02), (125.2, 146.55), (125.2, 118.4), (123.86, 117.062), (123.2, 117.062)]),
    ("+3V3", F, 0.6, [(123.2, 117.062), (123.2, 115.205)]),
    ("+3V3", F, 0.6, [(123.2, 117.062), (122.36, 117.062), (121.6, 116.3), (121.6, 111.0), (121.0, 110.4),
                      (109.2, 110.4), (107.9, 111.7), (107.9, 118.4), (107.8, 119.0)]),
    ("+3V3", F, 0.5, [(125.2, 141.9), (123.8, 141.9), (122.6, 141.9), (121.9, 142.6), (121.7, 142.6)]),
    # +5V : pont de 3 mm sous le tronc +3V3, puis le canal sous U1 jusqu'à la broche 3 et C1.
    ("+5V", B, 0.6, [(126.67, 122.62), (123.5, 122.62)]),
    ("+5V", F, 0.6, [(123.5, 122.62), (121.2, 122.62), (120.4, 121.82), (120.4, 113.935), (118.425, 113.935),
                     (117.2, 113.935), (116.5, 114.638), (115.8, 114.638)]),
    # TXD : la pastille de CN4 est derrière le couloir de SCL, on y entre par la face arrière.
    ("CAN_TX", F, 0.4, [(118.425, 111.395), (114.6, 111.395), (113.85, 112.145), (113.85, 125.16)]),
    ("CAN_TX", B, 0.4, [(113.85, 125.16), (111.43, 125.16)]),
    # RXD : face avant de bout en bout.
    ("CAN_RX", F, 0.4, [(118.425, 115.205), (117.6, 115.205), (116.9, 115.905), (116.7, 115.905), (115.8, 116.805),
                        (115.8, 126.4), (114.4, 127.8), (114.4, 133.7), (112.9, 135.2), (112.9, 144.5), (111.92, 145.48),
                        (111.43, 145.48)]),
    # I2C. SCL : MPU-6050 (J6.3) -> nord de CN4 -> couloir le plus proche de CN4 -> CN4.8.
    # SDA : MPU-6050 (J6.4) -> CN4.7 par la face arrière. Les deux repartent de CN4 vers
    # l'OLED par un pont de 3,9 mm sous CAN_S et CAN_RX, puis passent à l'ouest de H2.
    ("I2C_SCL", F, 0.4, [(107.8, 124.08), (109.0, 124.08), (109.62, 123.46), (109.62, 113.4), (109.9, 112.7), (109.9, 112.1)]),
    ("I2C_SCL", F, 0.4, [(109.9, 112.1), (110.9, 113.1), (112.3, 113.1), (112.9, 113.7), (112.9, 131.8), (111.92, 132.78),
                         (111.43, 132.78)]),
    ("I2C_SCL", B, 0.4, [(111.43, 132.78), (115.35, 132.78)]),
    ("I2C_SCL", F, 0.4, [(115.35, 132.78), (115.35, 133.85), (113.65, 135.55), (113.65, 139.65), (120.32, 146.32), (120.32, 147.5)]),
    ("I2C_SDA", B, 0.4, [(107.8, 126.62), (109.0, 126.62), (109.62, 127.24), (109.62, 129.62), (110.24, 130.24), (111.43, 130.24),
                         (115.35, 130.24)]),
    ("I2C_SDA", F, 0.4, [(115.35, 130.24), (116.3, 131.19), (116.3, 134.0), (114.4, 135.9), (114.4, 139.3), (119.7, 144.6),
                         (121.7, 144.6), (122.86, 145.76), (122.86, 147.5)]),
    ("MPU_INT", F, 0.4, [(111.43, 127.70), (110.4, 127.70), (109.62, 128.48), (109.62, 135.9), (108.74, 136.78), (107.8, 136.78)]),
    # Alimentation de l'OLED par R9 (GND) et R10 (+3V3).
    ("OLED_1", F, 0.4, [(114.4, 144.7), (114.4, 146.0), (115.24, 146.84), (115.24, 147.5)]),
    ("OLED_2", F, 0.4, [(123.8, 143.9), (124.3, 144.4), (124.3, 148.9), (123.9, 149.3), (117.78, 149.3), (117.78, 147.5)]),
    # LED d'état.
    ("LED_BOFF", F, 0.4, [(126.67, 140.4), (130.07, 137.0), (131.4, 137.0)]),
    ("LED_ERR", F, 0.4, [(126.67, 142.94), (129.56, 142.94), (131.4, 141.1)]),
    ("Net-(D2-A)", F, 0.4, [(131.375, 139.05), (133.4, 137.025), (133.4, 137.0)]),
    ("Net-(D1-A)", F, 0.4, [(131.375, 143.15), (133.4, 141.125), (133.4, 141.1)]),
    # Masse : pastille CMS -> via au pied. U1.2 et C1.2 partagent un via posé entre eux.
    ("GND", F, 0.5, [(118.425, 112.665), (115.8, 112.665)]),
    ("GND", F, 0.5, [(122.5, 119.138), (122.0, 119.6)]),
    ("GND", F, 0.5, [(123.7, 106.9), (123.7, 105.5)]),
    ("GND", F, 0.5, [(114.4, 142.7), (113.95, 141.45)]),
    ("GND", F, 0.5, [(133.425, 139.05), (134.8, 139.05)]),
    ("GND", F, 0.5, [(133.425, 143.15), (134.8, 143.15)]),
]

# (net, x, y) : vias de 0,8 mm percés à 0,4 mm.
VIAS = [
    ("CAN_S", 114.6, 108.9), ("CAN_S", 114.8, 116.7),   # pont sous le +3V3 et CAN_TX
    ("+5V", 123.5, 122.62),
    ("CAN_TX", 113.85, 125.16),
    ("I2C_SDA", 115.35, 130.24), ("I2C_SCL", 115.35, 132.78),
    ("GND", 116.99, 112.75),   # entre C1.2 et U1.2 : pied de C1 et de la broche GND
    ("GND", 122.0, 119.6),     # pied de C2
    ("GND", 123.7, 105.5),     # R7
    ("GND", 113.95, 141.45),   # R9
    ("GND", 134.8, 139.05),    # cathode de D2
    ("GND", 134.8, 143.15),    # cathode de D1
]


def main():
    board = pcbnew.LoadBoard(str(PCB))
    assert not list(board.GetTracks()), "la carte porte déjà des pistes : relancer generate_pcb.py d'abord"
    mm = pcbnew.FromMM
    longueurs = {}
    for net, face, largeur, pts in PISTES:
        info = board.FindNet(net)
        assert info, net
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1])))
            t.SetEnd(pcbnew.VECTOR2I(mm(b[0]), mm(b[1])))
            t.SetWidth(mm(largeur))
            t.SetLayer(pcbnew.F_Cu if face == F else pcbnew.B_Cu)
            t.SetNet(info)
            board.Add(t)
            longueurs[(net, face)] = longueurs.get((net, face), 0) + math.dist(a, b)
    for net, x, y in VIAS:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        v.SetWidth(mm(0.8))
        v.SetDrill(mm(0.4))
        v.SetNet(board.FindNet(net))
        board.Add(v)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(PCB))
    for face in (F, B):
        total = sum(v for (_, f), v in longueurs.items() if f == face)
        detail = ", ".join(f"{n} {v:.1f}" for (n, f), v in sorted(longueurs.items()) if f == face)
        print(f"{face}.Cu : {total:.1f} mm ({detail})")
    print(f"{PCB.name} : {sum(len(p[3]) - 1 for p in PISTES)} segments, {len(VIAS)} vias")


if __name__ == "__main__":
    os.chdir(HERE)
    sys.stdout.reconfigure(encoding="utf-8")
    main()
