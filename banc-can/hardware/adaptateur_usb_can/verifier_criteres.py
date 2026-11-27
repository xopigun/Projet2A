"""Mesure la carte routée et la compare aux critères tirés des remarques d'électronique (R1 à R7).

    "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" verifier_criteres.py

Chaque ligne donne la mesure, le seuil et OK ou HORS. Rien n'est modifié : la carte est lue,
ses zones sont remplies en mémoire, le DRC et l'ERC sont lancés par kicad-cli.
Code de retour 0 si tous les critères sont tenus, 1 sinon.

R1 vias de masse, R2 découplage du STM32, R3 quartz (ST AN2867), R4 plan de masse de la face
arrière, R5 paires CAN et USB, R6 LED d'erreur, R7 transceiver soudable à la main.
"""

import heapq
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

from generate_pcb import QUARTZ_B, QUARTZ_F

HERE = Path(__file__).parent
PCB = HERE / "adaptateur_usb_can.kicad_pcb"
SCH = HERE / "adaptateur_usb_can.kicad_sch"
CLI = r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"
MM = pcbnew.ToMM
F, B = pcbnew.F_Cu, pcbnew.B_Cu
CARTE = (100.0, 100.0, 160.0, 130.0)
TROU_MAX = 12.0     # mm : plus grande emprise tolérée d'un trou du plan de masse de la face arrière
# Grappes de composants de la face arrière dont les dégagements se soudent en un trou plus grand,
# sans remède à placement constant : nom -> rectangle où se trouve leur centre.
GRAPPES = {"fiche USB (pions de centrage de J1, protection U5, VBUS, fusible F1)": (100.0, 110.0, 108.0, 126.0),
           "régulateur U4, C1, C2, puis R2 et C4 (V3 du CH340C)": (108.0, 100.0, 123.0, 116.0),
           "transceiver U3, C13, C14, R7 et bornes H et L de J2": (145.0, 103.0, 159.0, 125.0)}
COUVERTURE_PAIRE = 85.0     # % mini du trajet d'une paire, hors pastilles, ayant le plan de masse en face

# Condensateur de découplage -> ce qu'il découple. C10 et C11 (charge du quartz) n'en sont pas :
# leur masse est l'îlot du quartz, relié au plan par un seul via (R3).
DECOUPLAGES = {"C1": "entrée du régulateur", "C2": "sortie du régulateur", "C3": "VCC du CH340C",
               "C4": "V3 du CH340C", "C5": "VDD broche 1", "C6": "VDD broche 17",
               "C7": "VDDA broche 15", "C8": "VDDA broche 15", "C9": "réservoir 3,3 V",
               "C12": "NRST", "C13": "VCC du TJA1051", "C14": "VIO du TJA1051"}
# Condensateur du STM32 -> broche d'alimentation qu'il doit toucher (R2).
BROCHES = {"C5": "1", "C6": "17", "C7": "15"}

resultats = []


def critere(nom, mesure, ok, seuil):
    resultats.append(ok)
    print(f"  [{'OK  ' if ok else 'HORS'}] {nom} : {mesure} (critère : {seuil})")


def info(texte):
    print(f"         {texte}")


def P(v):
    return (MM(v.x), MM(v.y))


def dans(p, r, marge=0.0):
    return r[0] - marge <= p[0] <= r[2] + marge and r[1] - marge <= p[1] <= r[3] + marge


def dans_polygone(p, poly):
    """Vrai si le point est dans le polygone (liste de sommets)."""
    r = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > p[1]) != (y2 > p[1]) and p[0] < x1 + (p[1] - y1) * (x2 - x1) / (y2 - y1):
            r = not r
    return r


def boite(bb):
    return (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()))


def ecart_boites(a, b):
    dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2]))
    dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
    return math.hypot(dx, dy)


def point_segment(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    l2 = vx * vx + vy * vy
    t = 0 if l2 == 0 else max(0, min(1, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / l2))
    return math.dist(p, (a[0] + t * vx, a[1] + t * vy))


def points(a, b, pas=0.05):
    """Points du segment a-b, tous les « pas » mm."""
    n = max(1, int(math.dist(a, b) / pas))
    return [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n + 1)]


def segment_dans(a, b, r, marge=0.0):
    return any(dans(q, r, marge) for q in points(a, b))


def cli_json(*args):
    out = Path(tempfile.gettempdir()) / "adaptateur_usb_can_verif.json"
    subprocess.run([CLI, *args, "--format", "json", "-o", str(out)], check=True, capture_output=True)
    return json.loads(out.read_text(encoding="utf-8"))


def main():
    board = pcbnew.LoadBoard(str(PCB))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    fps = {f.GetReference(): f for f in board.GetFootprints()}

    def pad(ref, num):
        return next(p for p in fps[ref].Pads() if p.GetNumber() == num)

    pistes, vias = [], []
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            vias.append((t.GetNetname(), P(t.GetPosition())))
        else:
            pistes.append((t.GetNetname(), t.GetLayer(), P(t.GetStart()), P(t.GetEnd()), MM(t.GetWidth())))
    vias_gnd = [p for n, p in vias if n == "GND"]
    zones = {l: next(z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "GND"
                     and z.IsOnLayer(l)) for l in (F, B)}
    plein = {l: zones[l].GetFilledPolysList(l) for l in (F, B)}

    def longueur(net, couche=None):
        return sum(math.dist(a, b) for n, l, a, b, _ in pistes if n == net and couche in (None, l))

    def chemin(net, depart, arrivee, detail=False):
        """Longueur de cuivre du centre d'une pastille au centre d'une autre, par les pistes.

        Avec detail, renvoie (longueur, [(couche, a, b), ...]) : les segments du trajet.
        """
        segs = [(a, b) for n, _, a, b, _ in pistes if n == net]
        couche = [l for n, l, _, _, _ in pistes if n == net]
        noeuds = [depart, arrivee] + [p for s in segs for p in s]
        dist = {0: 0.0}
        avant = {}
        tas = [(0.0, 0)]
        while tas:
            d, i = heapq.heappop(tas)
            if i == 1:
                if not detail:
                    return d
                trajet = []
                while i in avant:
                    j = avant[i]
                    if i >= 2 and j >= 2 and (i - 2) // 2 == (j - 2) // 2:
                        trajet.append((couche[(i - 2) // 2], noeuds[j], noeuds[i]))
                    i = j
                return d, trajet[::-1]
            if d > dist.get(i, 1e9):
                continue
            for j, q in enumerate(noeuds):
                if j == i:
                    continue
                # même point (à 10 µm près), ou les deux bouts d'un même segment
                pas = None
                if math.dist(noeuds[i], q) < 0.01:
                    pas = 0.0
                elif i >= 2 and j >= 2 and (i - 2) // 2 == (j - 2) // 2:
                    pas = math.dist(noeuds[i], q)
                if pas is not None and d + pas < dist.get(j, 1e9):
                    dist[j] = d + pas
                    avant[j] = i
                    heapq.heappush(tas, (d + pas, j))
        return None

    def trous(couche_, pas=0.1, bord=0.75):
        """Trous du plan de masse : zones sans cuivre GND d'un seul tenant, hors bande de bord.

        Renvoie [(emprise maxi, largeur, hauteur, surface mm2, (x0, y0, x1, y1)), ...], le plus
        étendu d'abord. Les pastilles GND comptent comme du cuivre.
        """
        pads_gnd = [boite(p.GetBoundingBox()) for f in fps.values() for p in f.Pads()
                    if p.GetNetname() == "GND" and p.IsOnLayer(couche_)]
        nx = int(round((CARTE[2] - CARTE[0] - 2 * bord) / pas))
        ny = int(round((CARTE[3] - CARTE[1] - 2 * bord) / pas))
        vide = [[False] * nx for _ in range(ny)]
        for j in range(ny):
            y = CARTE[1] + bord + (j + 0.5) * pas
            for i in range(nx):
                x = CARTE[0] + bord + (i + 0.5) * pas
                vide[j][i] = not (plein[couche_].Contains(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
                                  or any(dans((x, y), b) for b in pads_gnd))
        res = []
        for j0 in range(ny):
            for i0 in range(nx):
                if not vide[j0][i0]:
                    continue
                vide[j0][i0] = False
                pile, n, bb = [(i0, j0)], 0, [i0, j0, i0, j0]
                while pile:
                    i, j = pile.pop()
                    n += 1
                    bb = [min(bb[0], i), min(bb[1], j), max(bb[2], i), max(bb[3], j)]
                    for u, v in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                        if 0 <= u < nx and 0 <= v < ny and vide[v][u]:
                            vide[v][u] = False
                            pile.append((u, v))
                w, h = (bb[2] - bb[0] + 1) * pas, (bb[3] - bb[1] + 1) * pas
                res.append((max(w, h), w, h, n * pas * pas,
                            (CARTE[0] + bord + bb[0] * pas, CARTE[1] + bord + bb[1] * pas,
                             CARTE[0] + bord + (bb[2] + 1) * pas, CARTE[1] + bord + (bb[3] + 1) * pas)))
        return sorted(res, reverse=True)

    def couverture(r, couche):
        """Part de la surface du rectangle couverte par le plan de masse (ou une pastille GND)."""
        pads_gnd = [boite(p.GetBoundingBox()) for f in fps.values() for p in f.Pads()
                    if p.GetNetname() == "GND" and p.IsOnLayer(couche)]
        n = k = 0
        pas = 0.1
        y = r[1] + pas / 2
        while y < r[3]:
            x = r[0] + pas / 2
            while x < r[2]:
                n += 1
                if plein[couche].Contains(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))) or \
                        any(dans((x, y), b) for b in pads_gnd):
                    k += 1
                x += pas
            y += pas
        return 100.0 * k / n

    # ---------------------------------------------------------------------------------- R1
    print("R1 - vias de masse")
    critere("vias GND reliant les deux plans", f"{len(vias_gnd)}", len(vias_gnd) >= 40, ">= 40")
    pire, loin, total = (0.0, None), 0, 0
    x = CARTE[0]
    while x <= CARTE[2]:
        y = CARTE[1]
        while y <= CARTE[3]:
            d = min(math.dist((x, y), v) for v in vias_gnd)
            total += 1
            loin += d > 8.0
            if d > pire[0]:
                pire = (d, (x, y))
            y += 0.5
        x += 0.5
    critere("point de la carte le plus loin d'un via GND", f"{pire[0]:.2f} mm en {pire[1]}",
            pire[0] <= 8.0, "<= 8,0 mm")
    info(f"{100 * loin / total:.1f} % de la carte à plus de 8 mm d'un via GND (grille de 0,5 mm)")
    pire_c = 0.0
    for ref, role in DECOUPLAGES.items():
        g = next(p for p in fps[ref].Pads() if p.GetNetname() == "GND")
        d = min(math.dist(P(g.GetPosition()), v) for v in vias_gnd)
        pire_c = max(pire_c, d)
        info(f"{ref:4s} ({role}) : via GND à {d:.2f} mm du centre de sa pastille GND")
    critere("via GND au plus près de chaque découplage (12 condensateurs)", f"au pire {pire_c:.2f} mm",
            pire_c <= 1.5, "<= 1,5 mm du centre de la pastille GND")

    dans_pastille = sorted({f"{f.GetReference()}.{p.GetNumber()} ({p.GetNetname()})" for f in fps.values()
                            for p in f.Pads() if p.GetNumber() and not p.GetDrillSize().x
                            for n, v in vias if p.HitTest(pcbnew.VECTOR2I(pcbnew.FromMM(v[0]), pcbnew.FromMM(v[1])))})
    info(f"vias posés dans une pastille CMS ({len(dans_pastille)} pastilles) : {', '.join(dans_pastille)}")

    # ---------------------------------------------------------------------------------- R2
    print("R2 - découplage du STM32 (LQFP32 : VDD 1 et 17, VDDA 15 ; ni VREF+ ni VBAT)")
    for ref, broche in BROCHES.items():
        c = next(p for p in fps[ref].Pads() if p.GetNetname() == "+3V3")
        u = pad("U1", broche)
        d = math.dist(P(c.GetPosition()), P(u.GetPosition()))
        e = ecart_boites(boite(c.GetBoundingBox()), boite(u.GetBoundingBox()))
        critere(f"{ref} ({fps[ref].GetValue()}) -> broche {broche} de U1",
                f"{d:.2f} mm centre à centre, {e:.2f} mm bord à bord", d <= 3.0, "<= 3,0 mm")
    for ref in ("C8", "C9"):
        c = next(p for p in fps[ref].Pads() if p.GetNetname() == "+3V3")
        info(f"{ref} ({fps[ref].GetValue()}) : à {math.dist(P(c.GetPosition()), P(pad('U1', '15').GetPosition())):.2f} mm "
             f"de la broche 15, {math.dist(P(c.GetPosition()), P(pad('U1', '17').GetPosition())):.2f} mm de la 17")
    for broche in ("14", "16", "32"):
        d = min(math.dist(P(pad("U1", broche).GetPosition()), v) for v in vias_gnd)
        info(f"broche de masse {broche} : via GND à {d:.2f} mm")

    # ---------------------------------------------------------------------------------- R3
    print("R3 - quartz (ST AN2867)")
    for net in ("/OSC_IN", "/OSC_OUT"):
        nv = sum(1 for n, _ in vias if n == net)
        critere(f"piste {net}", f"{longueur(net):.2f} mm, {nv} via, "
                f"{longueur(net, B):.2f} mm en face arrière", longueur(net) <= 5.0 and nv == 0,
                "<= 5,0 mm, sans via")
    for net, broche, y, c in (("/OSC_IN", "2", "1", "C10"), ("/OSC_OUT", "3", "2", "C11")):
        b_, y_, c_ = (P(pad(*q).GetPosition()) for q in (("U1", broche), ("Y1", y), (c, "1")))
        info(f"{net} de centre à centre : broche {broche} -> Y1.{y} {math.dist(b_, y_):.2f} mm, puis Y1.{y} -> {c}.1 "
             f"{math.dist(y_, c_):.2f} mm, soit {math.dist(b_, y_) + math.dist(y_, c_):.2f} mm jusqu'au condensateur "
             f"(les pistes s'arrêtent dans les pastilles : {longueur(net):.2f} mm de piste)")
    sous = [(n, a, b) for n, l, a, b, _ in pistes if l == B and segment_dans(a, b, QUARTZ_B)]
    critere("pistes en face arrière sous le quartz (zone quartz_B)", f"{len(sous)}", not sous, "0")
    corps = boite(fps["Y1"].GetCourtyard(pcbnew.F_CrtYd).BBox())
    pads_y1 = [boite(p.GetBoundingBox()) for p in fps["Y1"].Pads()]
    entre = (min(b[0] for b in pads_y1), min(b[1] for b in pads_y1), max(b[2] for b in pads_y1),
             max(b[3] for b in pads_y1))
    intrus = sorted({n for n, l, a, b, _ in pistes if n not in ("/OSC_IN", "/OSC_OUT", "GND")
                     and segment_dans(a, b, entre)})
    critere("pistes de signal sous le quartz ou entre ses pastilles (deux faces)",
            f"{len(intrus)} {intrus if intrus else ''}", not intrus, "0")
    # Cellule gardée (zone quartz_F de generate_pcb.py) : quartz, C10, C11, pistes OSC, garde.
    etrangers = sorted({n for n, l, a, b, w in pistes if l == F and n not in ("/OSC_IN", "/OSC_OUT", "GND")
                        and any(dans_polygone(q, list(QUARTZ_F)) for q in points(a, b))})
    critere("pistes d'un autre signal dans la cellule gardée du quartz (zone quartz_F)",
            f"{len(etrangers)} {etrangers if etrangers else ''}", not etrangers, "0")
    # Ce qui reste voisin du quartz : distance bord à bord entre NRST / UART_TX et le cuivre OSC.
    osc = [boite(pad(r, n).GetBoundingBox()) for r, n in (("Y1", "1"), ("Y1", "2"), ("C10", "1"), ("C11", "1"))]
    for voisin in ("NRST", "UART_TX"):
        mini = (99.0, None)
        long_pres = 0.0
        for n, l, a, b, w in pistes:
            if n != voisin or l != F:
                continue
            for q in points(a, b):
                d = min(ecart_boites((q[0], q[1], q[0], q[1]), o) for o in osc) - w / 2
                d = min([d] + [point_segment(q, c, e) - w / 2 - w2 / 2 for m, l2, c, e, w2 in pistes
                               if m in ("/OSC_IN", "/OSC_OUT") and l2 == F])
                mini = min(mini, (d, q))
                long_pres += 0.05 * (d < 0.6)
        info(f"{voisin} : au plus près à {mini[0]:.2f} mm du cuivre de l'oscillateur, en "
             f"({mini[1][0]:.1f}, {mini[1][1]:.1f}) ; {long_pres:.1f} mm de piste à moins de 0,6 mm, sans garde possible")
    garde = [g for g in board.GetDrawings() if g.GetClass() == "PCB_SHAPE" and g.GetLayer() == F
             and g.GetNetname() == "GND"]
    critere("garde de masse entre C11 et NRST (pavé GND de la cellule)", f"{len(garde)} pavé(s)",
            len(garde) >= 1, ">= 1")
    dans_qf = [(n, p) for n, p in vias if dans_polygone(p, list(QUARTZ_F))]
    critere("îlot de masse du quartz relié au plan en un seul point",
            f"{len(dans_qf)} via dans la zone quartz_F : {[(n, (round(p[0], 2), round(p[1], 2))) for n, p in dans_qf]}",
            len(dans_qf) == 1 and dans_qf[0][0] == "GND", "1 via GND")
    if dans_qf:
        info(f"ce via est à {math.dist(dans_qf[0][1], P(pad('U1', '32').GetPosition())):.2f} mm de la broche 32 (VSS)")
        for c in ("C10", "C11"):
            r = chemin("GND", P(pad(c, "2").GetPosition()), dans_qf[0][1])
            info(f"retour de masse de {c} jusqu'à ce via, par l'anneau : " + (f"{r:.1f} mm" if r else "non trouvé"))
    cq = couverture(corps, B)
    critere("plan de masse B.Cu sous le quartz", f"{cq:.0f} %", cq >= 90.0, ">= 90 %")

    # ---------------------------------------------------------------------------------- R4
    print("R4 - plan de masse de la face arrière")
    lf = sum(math.dist(a, b) for _, l, a, b, _ in pistes if l == F)
    lb = sum(math.dist(a, b) for _, l, a, b, _ in pistes if l == B)
    critere("longueur de pistes sur B.Cu", f"{lb:.1f} mm (F.Cu : {lf:.1f} mm)", lb < 120.0, "< 120 mm")
    par_net = {}
    for n, l, a, b, _ in pistes:
        if l == B:
            par_net[n] = par_net.get(n, 0.0) + math.dist(a, b)
    info("par net : " + ", ".join(f"{n} {v:.1f}" for n, v in sorted(par_net.items(), key=lambda kv: -kv[1])))
    plus_longue = max(((math.dist(a, b), n) for n, l, a, b, _ in pistes if l == B), default=(0, ""))
    info(f"plus long segment : {plus_longue[0]:.1f} mm ({plus_longue[1]})")
    nb = plein[B].OutlineCount()
    critere("zone GND B.Cu d'un seul tenant", f"{nb} morceau(x), "
            f"{sum(abs(plein[B].Outline(i).Area()) for i in range(nb)) / 1e12:.0f} mm2 de cuivre",
            nb == 1, "1 morceau")
    info(f"zone GND F.Cu : {plein[F].OutlineCount()} morceau(x)")
    cu = couverture(boite(fps["U1"].GetCourtyard(pcbnew.F_CrtYd).BBox()), B)
    critere("plan de masse B.Cu sous U1", f"{cu:.0f} %", cu >= 90.0, ">= 90 %")
    # Trous du plan : dégagements de pastilles et de pistes soudés entre eux. Trois grappes
    # dépassent TROU_MAX et sont connues (GRAPPES) ; aucune autre ne doit apparaître.
    tr = trous(B)
    grands = [t for t in tr if t[0] > TROU_MAX]
    inconnus = [t for t in grands if not any(dans(((t[4][0] + t[4][2]) / 2, (t[4][1] + t[4][3]) / 2), g)
                                             for g in GRAPPES.values())]
    critere(f"trous du plan B.Cu de plus de {TROU_MAX:.0f} mm d'emprise, hors des {len(GRAPPES)} grappes connues",
            f"{len(inconnus)}", not inconnus, "0")
    for nom, g in GRAPPES.items():
        for t in grands:
            if dans(((t[4][0] + t[4][2]) / 2, (t[4][1] + t[4][3]) / 2), g):
                info(f"grappe {nom} : {t[1]:.1f} x {t[2]:.1f} mm, {t[3]:.0f} mm2 sans cuivre, de "
                     f"({t[4][0]:.1f}, {t[4][1]:.1f}) à ({t[4][2]:.1f}, {t[4][3]:.1f})")
    info("trous suivants : " + " ; ".join(f"{t[1]:.1f} x {t[2]:.1f} mm vers ({(t[4][0] + t[4][2]) / 2:.0f}, "
                                          f"{(t[4][1] + t[4][3]) / 2:.0f})"
                                          for t in [t for t in tr if t[0] <= TROU_MAX][:5]))

    # Paires : trajet utile de pastille à pastille, et sa partie hors des pastilles d'extrémité.
    PAIRES = (("CAN U3 -> J2", ("/CANH", ("U3", "7"), ("J2", "3")), ("/CANL", ("U3", "6"), ("J2", "2")), F,
               "plan F.Cu en face", "des bornes de J2 (face avant) et du via de CAN_TX"),
              ("USB J1 -> U2", ("USB_DP", ("J1", "3"), ("U2", "5")), ("USB_DM", ("J1", "2"), ("U2", "6")), B,
               "plan B.Cu dessous", "des pastilles de la protection U5, sous celles de J1"))
    trajets = {}
    for nom, *deux, autre, texte, cause in PAIRES:
        for net, a_, b_ in deux:
            lg, segs = chemin(net, P(pad(*a_).GetPosition()), P(pad(*b_).GetPosition()), detail=True)
            bouts = [boite(pad(*a_).GetBoundingBox()), boite(pad(*b_).GetBoundingBox())]
            pts = [(q, any(dans(q, bt) for bt in bouts)) for _, c, e in segs for q in points(c, e)]
            trajets[net] = (lg, segs, pts)
        n = k = 0
        for net, _, _ in deux:
            for q, dans_pastille in trajets[net][2]:
                if not dans_pastille:
                    n += 1
                    k += plein[autre].Contains(pcbnew.VECTOR2I(pcbnew.FromMM(q[0]), pcbnew.FromMM(q[1])))
        critere(f"paire {nom} : {texte}, hors pastilles d'extrémité", f"{100.0 * k / max(1, n):.0f} % de la longueur",
                100.0 * k >= COUVERTURE_PAIRE * n, f">= {COUVERTURE_PAIRE:.0f} %")
        info(f"sans plan en face : {0.05 * (n - k) / 2:.2f} mm par piste en moyenne, dans le dégagement de 0,5 mm "
             f"du plan autour {cause}")

    # ---------------------------------------------------------------------------------- R5
    print("R5 - paires différentielles")
    for nom, (n1, a1, b1), (n2, a2, b2), _autre, _texte, _cause in PAIRES:
        (l1, s1, p1), (l2, s2, p2) = trajets[n1], trajets[n2]
        critere(f"écart de longueur {nom}", f"{abs(l1 - l2):.2f} mm ({n1} {l1:.2f}, {n2} {l2:.2f})",
                abs(l1 - l2) <= 1.0, "<= 1,0 mm")
        # Entraxe : distance de chaque point du trajet d'une piste au trajet de l'autre.
        tout, hors = [], []
        for (pa, sb) in ((p1, s2), (p2, s1)):
            for q, dans_pastille in pa:
                e = min(point_segment(q, c, d) for _, c, d in sb)
                tout.append(e)
                if not dans_pastille:
                    hors.append(e)
        part = 100.0 * sum(e <= 1.0 for e in hors) / len(hors)
        critere(f"paire {nom} côte à côte, hors pastilles d'extrémité",
                f"{part:.0f} % de la longueur à 1,0 mm d'entraxe ou moins", part >= 60.0, ">= 60 %")
        tout.sort()
        info(f"pastilles comprises : {100.0 * sum(e <= 1.0 for e in tout) / len(tout):.0f} % à 1,0 mm ou moins ; "
             f"entraxe min {tout[0]:.2f}, médiane {tout[len(tout) // 2]:.2f}, max {tout[-1]:.2f} mm "
             f"(pas des pastilles : {math.dist(P(pad(*a1).GetPosition()), P(pad(*a2).GetPosition())):.2f} mm au départ, "
             f"{math.dist(P(pad(*b1).GetPosition()), P(pad(*b2).GetPosition())):.2f} mm à l'arrivée)")
        info(f"vias : {[(n, round(q[0], 2), round(q[1], 2)) for n, q in vias if n in (n1, n2)]}")

    # ---------------------------------------------------------------------------------- R6
    print("R6 - LED d'erreur")
    ok = ("D4" in fps and "R8" in fps and pad("U1", "18").GetNetname() == "LED_ERR"
          and pad("R8", "1").GetNetname() == "LED_ERR" and pad("R8", "2").GetNetname() == pad("D4", "2").GetNetname()
          and pad("D4", "1").GetNetname() == "GND")
    critere("D4 (rouge, 0805) et R8 sur PA8, broche 18 de U1",
            f"D4 « {fps['D4'].GetValue()} » {fps['D4'].GetFPID().GetLibItemName()}, R8 {fps['R8'].GetValue()}"
            if ok else "absente ou mal câblée", ok, "au schéma, sur la carte et dans la nomenclature")

    # ---------------------------------------------------------------------------------- R7
    print("R7 - transceiver près du bornier, soudable à la main")
    mini = min((ecart_boites(boite(a.GetBoundingBox()), boite(b.GetBoundingBox())), a.GetNumber(), b.GetNumber())
               for a in fps["U3"].Pads() for b in fps["J2"].Pads())
    critere("écart bord à bord entre pastilles de U3 et de J2",
            f"{mini[0]:.2f} mm (U3.{mini[1]} / J2.{mini[2]})", mini[0] >= 2.0 - 1e-6, ">= 2,0 mm")
    for ref, f in fps.items():
        if ref != "U3" and f.IsFlipped():
            e = min(ecart_boites(boite(a.GetBoundingBox()), boite(b.GetBoundingBox()))
                    for a in fps["U3"].Pads() for b in f.Pads())
            if e < 2.0:
                info(f"voisin {ref} : {e:.2f} mm bord à bord d'une pastille de U3")
    info(f"U3 à {math.dist(P(fps['U3'].GetPosition()), (156.3, 115.0)):.1f} mm de la rangée de bornes de J2")

    # ---------------------------------------------------------------------------------- DRC, ERC
    print("DRC (règles ENSEA du projet, parité avec le schéma) et ERC")
    drc = cli_json("pcb", "drc", "--schematic-parity", "--severity-all", str(PCB))
    viol = drc.get("violations", [])
    err = [v for v in viol if v["severity"] == "error"]
    types = {}
    for v in viol:
        types[v["type"]] = types.get(v["type"], 0) + 1
    critere("DRC : erreurs", f"{len(err)}", not err, "0")
    critere("DRC : non connectés", f"{len(drc.get('unconnected_items', []))}",
            not drc.get("unconnected_items"), "0")
    critere("DRC : parité schéma-carte", f"{len(drc.get('schematic_parity', []))}",
            not drc.get("schematic_parity"), "0")
    info(f"avertissements : {len(viol) - len(err)} {types if viol else ''}")
    erc = cli_json("sch", "erc", "--severity-all", str(SCH))
    n_erc = sum(len(s.get("violations", [])) for s in erc.get("sheets", []))
    critere("ERC", f"{n_erc}", n_erc == 0, "0")

    print(f"\n{sum(resultats)} critère(s) tenus sur {len(resultats)}")
    return 0 if all(resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
