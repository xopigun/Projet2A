"""Vias de couture de la masse : relie les plans GND des deux faces sur toute la carte.

À lancer après router_manuel.py, avec le Python de KiCad 9 :

    "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" coudre_gnd.py [pas en mm, 6 par défaut]

1. Une grille en quinconce au pas donné couvre la carte ; chaque via est posé au plus près
   de sa cible, dans un rayon de 2 mm, hors de l'emprise des composants.
2. Chaque îlot de cuivre GND de la face avant resté sans via en reçoit un, s'il y a la place :
   un îlot relié au reste par une seule pastille ne vaut rien comme plan.
3. Tant qu'un point du cuivre GND est à plus de 7,5 mm d'un via, on en ajoute un. C'est la
   seule étape qui pose des vias sous un corps de composant, et seulement quand il n'y a pas
   d'autre place : le corps de la barrette du MPU-6050 couvre toute l'aile gauche et le bornier
   tout le coin arrière droit. La factory métallise les vias (ils affleurent) ; s'il fallait
   un jour les riveter ou les étamer, ce sont ceux-là qu'il faudrait retirer (liste affichée).
Un emplacement n'est retenu que si le disque du via (plus 0,05 mm) est dans le cuivre GND
rempli des deux faces : le remplissage respecte déjà l'isolation des autres réseaux et la
marge au contour. Il reste en plus à l'écart des pastilles (0,3 mm), des autres vias (0,6 mm),
des bandes de bord et des têtes de vis (4 mm de l'axe de H1 et H2).
Pendant la pose, la zone de la face avant garde ses îlots (sinon les îlots à coudre
n'existent pas) ; celle de la face arrière les supprime, pour qu'aucun via ne tombe dans
un éclat du plan. Le réglage d'origine est rétabli avant l'enregistrement.
"""

import math
import os
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).parent
PCB = HERE / "carte_porteuse.kicad_pcb"
MM, FMM = pcbnew.ToMM, pcbnew.FromMM
DIAM, PERCAGE, RECHERCHE = 0.8, 0.4, 2.0
GARDE_VIS = 4.0     # mm entre l'axe d'un trou de fixation et l'axe d'un via
MARGE_CORPS = 0.5   # mm entre le corps d'un composant et l'axe d'un via
LIMITE = 7.5        # mm : distance maximale d'un point du cuivre GND à un via (critère : 8)


def poly_ilot(polys, i):
    o = pcbnew.SHAPE_POLY_SET()
    o.AddOutline(polys.Outline(i))
    for h in range(polys.HoleCount(i)):
        o.AddHole(polys.Hole(i, h))
    return o


def corps_composants(board):
    """{repère: (x0, y0, x1, y1)} : emprise du corps (tracé F.Fab) de chaque composant."""
    corps = {}
    for fp in board.GetFootprints():
        box = None
        for g in fp.GraphicalItems():
            if g.Type() == pcbnew.PCB_SHAPE_T and g.GetLayer() == pcbnew.F_Fab:
                bb = g.GetBoundingBox()
                v = (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()))
                box = v if box is None else (min(box[0], v[0]), min(box[1], v[1]), max(box[2], v[2]), max(box[3], v[3]))
        if box:
            corps[fp.GetReference()] = box
    return corps


def sous_corps(corps, x, y, marge=MARGE_CORPS):
    return [r for r, (x0, y0, x1, y1) in corps.items() if x0 - marge < x < x1 + marge and y0 - marge < y < y1 + marge]


def main(pas):
    board = pcbnew.LoadBoard(str(PCB))
    zones = [z for z in board.Zones() if z.GetNetname() == "GND" and not z.GetIsRuleArea()]
    modes = [z.GetIslandRemovalMode() for z in zones]
    for z in zones:
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER if z.IsOnLayer(pcbnew.F_Cu)
                               else pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    polys = {c: [z.GetFilledPolysList(c) for z in zones if z.IsOnLayer(c)] for c in (pcbnew.F_Cu, pcbnew.B_Cu)}
    corps = corps_composants(board)

    contour = None
    interdit, pads, trous = [], [], []
    for z in board.Zones():
        if z.GetIsRuleArea():
            if z.GetZoneName().startswith("tete_vis"):
                continue   # disques autour de H1 et H2 : traités par GARDE_VIS
            bb = z.GetBoundingBox()
            interdit.append((MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom())))
        elif z.IsOnLayer(pcbnew.B_Cu) and z.GetNetname() == "GND":
            contour = z.Outline()
    for fp in board.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            pads.append((MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom())))
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                trous.append((MM(p.GetPosition().x), MM(p.GetPosition().y)))
    vias = [(MM(t.GetPosition().x), MM(t.GetPosition().y)) for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    gnd = [(MM(t.GetPosition().x), MM(t.GetPosition().y)) for t in board.GetTracks()
           if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND"]

    def libre(x, y, sous_composant=False):
        if not sous_composant and sous_corps(corps, x, y):
            return False
        if any(x0 - 0.5 < x < x1 + 0.5 and y0 - 0.5 < y < y1 + 0.5 for x0, y0, x1, y1 in interdit):
            return False
        if any(math.dist((x, y), t) < GARDE_VIS for t in trous):
            return False
        m = DIAM / 2 + 0.3
        if any(x0 - m < x < x1 + m and y0 - m < y < y1 + m for x0, y0, x1, y1 in pads):
            return False
        if any(math.dist((x, y), v) < DIAM + 0.6 for v in vias):
            return False
        r = DIAM / 2 + 0.05
        pts = [(x, y)] + [(x + r * math.cos(k * math.pi / 8), y + r * math.sin(k * math.pi / 8)) for k in range(16)]
        for couche in polys:
            for px, py in pts:
                p = pcbnew.VECTOR2I(FMM(px), FMM(py))
                if not any(pl.Contains(p) for pl in polys[couche]):
                    return False
        return True

    def poser(x, y):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(FMM(x), FMM(y)))
        v.SetWidth(FMM(DIAM))
        v.SetDrill(FMM(PERCAGE))
        v.SetNet(board.FindNet("GND"))
        board.Add(v)
        vias.append((x, y))
        gnd.append((x, y))

    # 1. Grille en quinconce sur l'emprise de la carte, hors des corps de composants.
    bb = contour.BBox()
    x0, y0, x1, y1 = MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom())
    cibles, rang, y = [], 0, y0 + pas / 2
    while y < y1:
        x = x0 + pas / 2 + (pas / 2 if rang % 2 else 0)
        while x < x1:
            if contour.Contains(pcbnew.VECTOR2I(FMM(x), FMM(y))):
                cibles.append((x, y))
            x += pas
        y += pas * math.sqrt(3) / 2
        rang += 1
    n = round(RECHERCHE / 0.1)
    decalages = sorted(((i * 0.1, j * 0.1) for i in range(-n, n + 1) for j in range(-n, n + 1)
                        if math.hypot(i, j) * 0.1 <= RECHERCHE), key=lambda d: math.hypot(*d))
    grille = 0
    for cx, cy in cibles:
        pos = next(((cx + dx, cy + dy) for dx, dy in decalages if libre(cx + dx, cy + dy)), None)
        if pos is None:
            continue
        poser(*pos)
        grille += 1

    # 2. Îlots de la face avant restés sans via (hors des corps si possible).
    ilots = 0
    for pl in polys[pcbnew.F_Cu]:
        for i in range(pl.OutlineCount()):
            o = poly_ilot(pl, i)
            if any(o.Collide(pcbnew.VECTOR2I(FMM(x), FMM(y)), FMM(0.35)) for x, y in gnd):
                continue
            b2 = o.BBox()
            cx, cy = MM(b2.GetLeft() + b2.GetRight()) / 2, MM(b2.GetTop() + b2.GetBottom()) / 2
            for sous_composant in (False, True):
                sites = []
                y = MM(b2.GetTop())
                while y <= MM(b2.GetBottom()):
                    x = MM(b2.GetLeft())
                    while x <= MM(b2.GetRight()):
                        if o.Contains(pcbnew.VECTOR2I(FMM(x), FMM(y))) and libre(x, y, sous_composant):
                            sites.append((x, y))
                        x += 0.2
                    y += 0.2
                if sites:
                    poser(*min(sites, key=lambda s: math.dist(s, (cx, cy))))
                    ilots += 1
                    break

    # 3. Couverture : plus aucun point du cuivre GND à plus de LIMITE d'un via.
    points = []
    x = x0
    while x < x1:
        y = y0
        while y < y1:
            p = pcbnew.VECTOR2I(FMM(x), FMM(y))
            if any(pl.Contains(p) for couche in polys for pl in polys[couche]):
                points.append((x, y))
            y += 0.5
        x += 0.5
    couverture = 0
    while True:
        loin = [p for p in points if min(math.dist(p, v) for v in gnd) > LIMITE]
        if not loin:
            break
        pire = max(loin, key=lambda p: min(math.dist(p, v) for v in gnd))
        rayon = LIMITE - 0.3
        k = int(rayon / 0.25)
        autour = [(pire[0] + i * 0.25, pire[1] + j * 0.25) for i in range(-k, k + 1) for j in range(-k, k + 1)
                  if math.hypot(i, j) * 0.25 <= rayon]
        choix = None
        for sous_composant in (False, True):
            sites = [s for s in autour if libre(s[0], s[1], sous_composant)]
            if sites:
                # celui qui ramène le plus de points sous la limite ; à égalité, le plus loin des vias
                choix = max(sites, key=lambda s: (sum(math.dist(s, p) <= rayon for p in loin),
                                                  min(math.dist(s, v) for v in gnd)))
                break
        if choix is None:
            print(f"point ({pire[0]:.1f} ; {pire[1]:.1f}) : aucun emplacement de via à moins de {rayon:.1f} mm")
            points.remove(pire)
            continue
        poser(*choix)
        couverture += 1

    for z, m in zip(zones, modes):
        z.SetIslandRemovalMode(m)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(PCB))
    print(f"{grille} vias sur la grille de {pas:g} mm, {ilots} dans des îlots de la face avant, "
          f"{couverture} pour la couverture ; {len(gnd)} vias GND au total")
    dessous = [(v, sous_corps(corps, *v, marge=DIAM / 2)) for v in gnd]
    dessous = [(v, r) for v, r in dessous if r]
    print(f"{len(dessous)} via(s) GND sous un corps de composant : "
          + ", ".join(f"{'/'.join(r)} ({v[0]:.1f} ; {v[1]:.1f})" for v, r in dessous))


if __name__ == "__main__":
    os.chdir(HERE)
    sys.stdout.reconfigure(encoding="utf-8")
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 6.0)
