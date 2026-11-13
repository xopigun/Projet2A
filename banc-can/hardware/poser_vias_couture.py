"""Pose des vias de couture GND aux endroits indiqués, chacun au plus près de sa cible.

    "C:\Program Files\KiCad\9.0\bin\python.exe" poser_vias_couture.py <carte> x,y [x,y ...]

Un emplacement n'est retenu que si le disque du via (et une marge de 0,05 mm) est entièrement
dans le plan de masse rempli des deux faces : le remplissage respectant déjà l'isolation des
autres réseaux et la marge au contour, le via ne peut rien toucher d'autre et se raccorde aux
deux plans. Il doit aussi rester à l'écart des pastilles et des vias existants.
"""
import math
import sys

import pcbnew

MM, FMM = pcbnew.ToMM, pcbnew.FromMM
DIAM, PERCAGE, RECHERCHE = 0.8, 0.4, 2.5


def dans_plans(zones, x, y):
    r = DIAM / 2 + 0.05
    pts = [(x, y)] + [(x + r * math.cos(a), y + r * math.sin(a)) for a in [k * math.pi / 8 for k in range(16)]]
    for couche in (pcbnew.F_Cu, pcbnew.B_Cu):
        polys = [z.GetFilledPolysList(couche) for z in zones if z.IsOnLayer(couche)]
        for px, py in pts:
            p = pcbnew.VECTOR2I(FMM(px), FMM(py))
            if not any(pl.Contains(p) for pl in polys):
                return False
    return True


def libre(board, x, y):
    p = pcbnew.VECTOR2I(FMM(x), FMM(y))
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            bb.Inflate(FMM(DIAM / 2 + 0.3))
            if bb.Contains(p):
                return False
    for v in board.GetTracks():
        if v.Type() == pcbnew.PCB_VIA_T and math.dist((MM(v.GetPosition().x), MM(v.GetPosition().y)), (x, y)) < DIAM + 0.4:
            return False
    return True


def main(chemin, cibles):
    board = pcbnew.LoadBoard(chemin)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    zones = [z for z in board.Zones() if z.GetNetname() == "GND" and not z.IsTeardropArea()]
    for cx, cy in cibles:
        essais = sorted(((cx + i * 0.1, cy + j * 0.1) for i in range(-25, 26) for j in range(-25, 26)
                         if math.hypot(i, j) * 0.1 <= RECHERCHE), key=lambda q: math.dist(q, (cx, cy)))
        pos = next((q for q in essais if libre(board, *q) and dans_plans(zones, *q)), None)
        if pos is None:
            print(f"cible ({cx}, {cy}) : aucun emplacement libre à moins de {RECHERCHE} mm")
            continue
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(FMM(pos[0]), FMM(pos[1])))
        v.SetWidth(FMM(DIAM)); v.SetDrill(FMM(PERCAGE))
        v.SetNet(board.FindNet("GND"))
        board.Add(v)
        print(f"cible ({cx}, {cy}) : via posé en ({pos[0]:.2f}, {pos[1]:.2f}), à {math.dist(pos, (cx, cy)):.2f} mm")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(chemin)


if __name__ == "__main__":
    main(sys.argv[1], [tuple(map(float, a.split(","))) for a in sys.argv[2:]])
