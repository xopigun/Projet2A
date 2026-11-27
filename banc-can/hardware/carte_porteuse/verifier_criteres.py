"""Contrôle de la carte porteuse : ERC, DRC et critères de routage P1 à P4.

    "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" verifier_criteres.py

P1 vias de masse : au moins 30, aucun cuivre GND à plus de 8 mm d'un via, un via à moins de
   2 mm de la pastille GND de C1 et de C2.
P2 plan de masse : zone GND de la face arrière d'un seul tenant, moins de 80 mm de pistes
   sur cette face en ponts de 12 mm au plus, aucune piste arrière sous U1 ni à moins de 1 mm
   de la paire CAN, aucun îlot GND de la face avant sans via.
P3 paire CAN : de U1 au bornier J1, CANH et CANL sur une seule face, sans via, moins de
   25 mm chacune, 1 mm d'écart de longueur au plus (les branches de terminaison vers R1 et
   J7 partent des bornes et ne sont pas comptées).
P4 découplage : C1 et C2 à 3 mm au plus de leur broche (entre centres de pastilles).
Mécanique et factory : aucun cuivre hors masse de la face avant à moins de 1 mm d'une tête de
   vis M3 de 5,5 mm (cuivre nu) ; perçages métallisés de 0,4 à 2,0 mm par pas de 0,2 mm et
   fixations de 3,2 mm ; liste des vias posés sous un corps de composant (pour information).
Code de retour 0 si tout est tenu, 1 sinon.
"""

import heapq
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

HERE = Path(__file__).parent
PCB = HERE / "carte_porteuse.kicad_pcb"
SCH = HERE / "carte_porteuse.kicad_sch"
CLI = r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"
MM, FMM = pcbnew.ToMM, pcbnew.FromMM
TETE_VIS = 5.5   # mm, diamètre de la tête des vis M3 de H1 et H2
echecs = []


def verdict(ok, texte):
    print(("  ok    " if ok else "  ÉCHEC ") + texte)
    if not ok:
        echecs.append(texte)


def pt(x, y):
    return pcbnew.VECTOR2I(FMM(x), FMM(y))


def dist_segment(p, a, b):
    ax, ay, bx, by = *a, *b
    d2 = (bx - ax) ** 2 + (by - ay) ** 2
    t = 0 if d2 == 0 else max(0, min(1, ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / d2))
    return math.dist(p, (ax + t * (bx - ax), ay + t * (by - ay)))


def dist_segments(a, b, c, d):
    return min(dist_segment(a, c, d), dist_segment(b, c, d), dist_segment(c, a, b), dist_segment(d, a, b))


def regles():
    print("ERC et DRC (kicad-cli)")
    tmp = Path(tempfile.gettempdir())
    erc, drc = tmp / "carte_porteuse_erc.json", tmp / "carte_porteuse_drc.json"
    subprocess.run([CLI, "sch", "erc", "--severity-all", "--format", "json", "-o", str(erc), str(SCH)],
                   check=True, capture_output=True)
    subprocess.run([CLI, "pcb", "drc", "--schematic-parity", "--severity-all", "--format", "json",
                    "-o", str(drc), str(PCB)], check=True, capture_output=True)
    e = json.loads(erc.read_text(encoding="utf-8"))
    viol = [v for s in e.get("sheets", []) for v in s.get("violations", [])]
    verdict(not [v for v in viol if v["severity"] == "error"],
            f"ERC : {sum(v['severity'] == 'error' for v in viol)} erreur, {sum(v['severity'] != 'error' for v in viol)} avertissement")
    d = json.loads(drc.read_text(encoding="utf-8"))
    v = d.get("violations", [])
    # Écart voulu avec la bibliothèque : le bornier J1 est percé à 1,4 mm au lieu de 1,3
    # (pas de 0,2 mm de la factory), voir PERCAGE_J1 dans generate_pcb.py.
    voulu = [x for x in v if x["type"] == "lib_footprint_mismatch" and any("J1" in i["description"] for i in x["items"])]
    hors_serig = [x for x in v if not x["type"].startswith("silk") and x not in voulu]
    for x in hors_serig:
        print("        ", x["severity"], x["type"], "|", x["description"][:70], "|",
              " ; ".join(f"{i['description'][:40]} ({i['pos']['x']:.2f} ; {i['pos']['y']:.2f})" for i in x["items"]))
    serig = {}
    for x in v:
        if x["type"].startswith("silk"):
            serig[x["type"]] = serig.get(x["type"], 0) + 1
    verdict(not hors_serig, f"DRC : {len(hors_serig)} violation hors sérigraphie"
            + (" (plus l'écart voulu de J1 avec sa bibliothèque : perçage de 1,4 mm)" if voulu else ""))
    genants = serig.get("silk_overlap", 0) + serig.get("silk_over_copper", 0)
    verdict(genants == 0, f"sérigraphie : {serig.get('silk_overlap', 0)} repère sur un autre tracé, "
            f"{serig.get('silk_over_copper', 0)} sur une pastille ; {serig.get('silk_edge_clearance', 0)} tracés de "
            "connecteurs au bord de la carte (voulus)")
    verdict(not d.get("unconnected_items"), f"DRC : {len(d.get('unconnected_items', []))} liaison manquante")
    verdict(not d.get("schematic_parity"), f"DRC : {len(d.get('schematic_parity', []))} écart avec le schéma")


def main():
    regles()
    board = pcbnew.LoadBoard(str(PCB))
    pistes = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]
    vias = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    gnd = [(MM(v.GetPosition().x), MM(v.GetPosition().y)) for v in vias if v.GetNetname() == "GND"]
    seg = lambda t: ((MM(t.GetStart().x), MM(t.GetStart().y)), (MM(t.GetEnd().x), MM(t.GetEnd().y)))

    def pad(ref, num):
        p = next(p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == num)
        return (MM(p.GetPosition().x), MM(p.GetPosition().y))

    zones = {c: next(z for z in board.Zones() if z.GetNetname() == "GND" and not z.GetIsRuleArea() and z.IsOnLayer(c))
             for c in (pcbnew.F_Cu, pcbnew.B_Cu)}
    cuivre = {c: z.GetFilledPolysList(c) for c, z in zones.items()}

    print("P1 vias de masse")
    verdict(len(gnd) >= 30, f"{len(gnd)} vias GND sur {len(vias)} vias (au moins 30)")
    for c, nom in ((pcbnew.F_Cu, "avant"), (pcbnew.B_Cu, "arrière")):
        bb = cuivre[c].BBox()
        pire, ou, x = 0, None, MM(bb.GetLeft())
        while x < MM(bb.GetRight()):
            y = MM(bb.GetTop())
            while y < MM(bb.GetBottom()):
                if cuivre[c].Contains(pt(x, y)):
                    d = min(math.dist((x, y), v) for v in gnd)
                    if d > pire:
                        pire, ou = d, (round(x, 1), round(y, 1))
                y += 0.5
            x += 0.5
        verdict(pire <= 8, f"face {nom} : cuivre GND le plus loin d'un via à {pire:.1f} mm, en {ou} (8 mm au plus)")
    for ref in ("C1", "C2"):
        d = min(math.dist(pad(ref, "2"), v) for v in gnd)
        verdict(d <= 2, f"{ref} : via GND à {d:.2f} mm de sa pastille de masse (2 mm au plus)")

    print("P2 plan de masse")
    n = cuivre[pcbnew.B_Cu].OutlineCount()
    aire_carte = zones[pcbnew.B_Cu].Outline().Area() / 1e12
    verdict(n == 1, f"face arrière : zone GND en {n} morceau(x), {cuivre[pcbnew.B_Cu].Area() / 1e12:.0f} mm² "
                    f"({100 * cuivre[pcbnew.B_Cu].Area() / 1e12 / aire_carte:.0f} % de la carte)")
    arriere = [t for t in pistes if t.GetLayer() == pcbnew.B_Cu]
    par_net = {}
    for t in arriere:
        par_net[t.GetNetname()] = par_net.get(t.GetNetname(), 0) + MM(t.GetLength())
    total = sum(par_net.values())
    verdict(total < 80, f"face arrière : {total:.1f} mm de pistes (moins de 80) : "
            + ", ".join(f"{k} {v:.1f}" for k, v in sorted(par_net.items(), key=lambda kv: -kv[1])))
    # Ponts : morceaux de piste d'un seul tenant sur la face arrière.
    cle2 = lambda p: (round(p[0], 2), round(p[1], 2))
    ponts = []
    for net in par_net:
        reste = [seg(t) for t in arriere if t.GetNetname() == net]
        while reste:
            a, b = reste.pop()
            noeuds, longueur, encore = {cle2(a), cle2(b)}, math.dist(a, b), True
            while encore:
                encore = False
                for sg in list(reste):
                    if cle2(sg[0]) in noeuds or cle2(sg[1]) in noeuds:
                        noeuds |= {cle2(sg[0]), cle2(sg[1])}
                        longueur += math.dist(*sg)
                        reste.remove(sg)
                        encore = True
            ponts.append((longueur, net))
    ponts.sort(reverse=True)
    verdict(ponts[0][0] <= 12, f"face arrière : {len(ponts)} ponts, le plus long de {ponts[0][0]:.1f} mm ({ponts[0][1]}), 12 mm au plus")
    print(f"        face avant : {sum(MM(t.GetLength()) for t in pistes if t.GetLayer() == pcbnew.F_Cu):.1f} mm de pistes")
    u1 = board.FindFootprintByReference("U1").GetBoundingBox(False, False)
    sous_u1 = [t.GetNetname() for t in arriere if u1.Intersects(t.GetBoundingBox())]
    verdict(not sous_u1, f"face arrière : {len(sous_u1)} piste sous U1 {sorted(set(sous_u1)) if sous_u1 else ''}")
    paire = [seg(t) for t in pistes if t.GetNetname() in ("/CANH", "/CANL")]
    pres = sorted({t.GetNetname() for t in arriere for s in paire
                   if dist_segments(*seg(t), *s) < 1.0 + MM(t.GetWidth()) / 2 + 0.2})
    verdict(not pres, f"face arrière : {len(pres)} net à moins de 1 mm de la paire CAN {pres if pres else ''}")
    sans_via = []
    pl = cuivre[pcbnew.F_Cu]
    for i in range(pl.OutlineCount()):
        o = pcbnew.SHAPE_POLY_SET()
        o.AddOutline(pl.Outline(i))
        for h in range(pl.HoleCount(i)):
            o.AddHole(pl.Hole(i, h))
        if not any(o.Collide(pt(*v), FMM(0.35)) for v in gnd):
            bb = o.BBox()
            sans_via.append(f"{o.Area() / 1e12:.1f} mm² en x {MM(bb.GetLeft()):.1f}-{MM(bb.GetRight()):.1f} "
                            f"y {MM(bb.GetTop()):.1f}-{MM(bb.GetBottom()):.1f}")
    verdict(not sans_via, f"face avant : zone GND en {pl.OutlineCount()} îlots, {pl.Area() / 1e12:.0f} mm², "
                          f"{len(sans_via)} sans via {sans_via if sans_via else ''}")

    print("P3 paire CAN")
    troncs = {}
    for net, a, b in (("/CANH", pad("U1", "7"), pad("J1", "3")), ("/CANL", pad("U1", "6"), pad("J1", "2"))):
        segs = [(seg(t), t.GetLayer()) for t in pistes if t.GetNetname() == net]
        nv = sum(v.GetNetname() == net for v in vias)
        cle = lambda p: (round(p[0], 2), round(p[1], 2))
        graphe = {}
        for (p, q), _ in segs:
            graphe.setdefault(cle(p), []).append((cle(q), math.dist(p, q)))
            graphe.setdefault(cle(q), []).append((cle(p), math.dist(p, q)))
        d, file = {cle(a): 0.0}, [(0.0, cle(a))]
        while file:
            dn, n = heapq.heappop(file)
            if dn > d.get(n, 1e9):
                continue
            for m, l in graphe.get(n, []):
                if dn + l < d.get(m, 1e9):
                    d[m] = dn + l
                    heapq.heappush(file, (dn + l, m))
        troncs[net] = d.get(cle(b))
        faces = {board.GetLayerName(c) for _, c in segs}
        net_entier = sum(math.dist(p, q) for (p, q), _ in segs)
        verdict(troncs[net] is not None and troncs[net] < 25 and nv == 0 and len(faces) == 1,
                f"{net} : tronc U1 -> J1 de {troncs[net]:.2f} mm (moins de 25), {nv} via, face {', '.join(sorted(faces))} ; "
                f"net entier {net_entier:.1f} mm avec la branche de terminaison")
    ecart = abs(troncs["/CANH"] - troncs["/CANL"])
    verdict(ecart <= 1, f"écart de longueur des troncs : {ecart:.2f} mm (1 mm au plus)")
    h = [s for s in paire if any(seg(t) == s and t.GetNetname() == "/CANH" for t in pistes)]
    l = [s for s in paire if s not in h]
    cote = sum(math.dist(*s) for s in l if min(dist_segments(*s, *k) for k in h) < 0.9)
    print(f"        CANL longe CANH à moins de 0,9 mm d'axe en axe sur {cote:.1f} mm")

    print("P4 découplage")
    for c, u in (("C1", "3"), ("C2", "5")):
        d = math.dist(pad(c, "1"), pad("U1", u))
        verdict(d <= 3, f"{c} à {d:.2f} mm de U1.{u} (3 mm au plus)")

    print("Mécanique et factory")
    for ref in ("H1", "H2"):
        c = board.FindFootprintByReference(ref).GetPosition()
        c = (MM(c.x), MM(c.y))
        marges = []
        for t in pistes:
            if t.GetLayer() == pcbnew.F_Cu and t.GetNetname() != "GND":
                marges.append((dist_segment(c, *seg(t)) - MM(t.GetWidth()) / 2 - TETE_VIS / 2, t.GetNetname()))
        for v in vias:
            if v.GetNetname() != "GND":
                p = (MM(v.GetPosition().x), MM(v.GetPosition().y))
                marges.append((math.dist(c, p) - MM(v.GetWidth(pcbnew.F_Cu)) / 2 - TETE_VIS / 2, v.GetNetname() + " (via)"))
        for fp in board.GetFootprints():
            for p in fp.Pads():
                if p.IsOnLayer(pcbnew.F_Cu) and p.GetNetname() not in ("GND", "") and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                    bb = p.GetBoundingBox()
                    dx = max(MM(bb.GetLeft()) - c[0], 0, c[0] - MM(bb.GetRight()))
                    dy = max(MM(bb.GetTop()) - c[1], 0, c[1] - MM(bb.GetBottom()))
                    marges.append((math.hypot(dx, dy) - TETE_VIS / 2, f"{fp.GetReference()}.{p.GetNumber()}"))
        m, quoi = min(marges)
        verdict(m >= 1.0, f"{ref} : cuivre hors masse le plus proche de la tête de vis à {m:.2f} mm ({quoi}), 1 mm au moins")
    percages = {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            d = round(MM(p.GetDrillSize().x), 3)
            if d > 0:
                cle3 = (d, p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH)
                percages[cle3] = percages.get(cle3, 0) + 1
    for v in vias:
        cle3 = (round(MM(v.GetDrill()), 3), False)
        percages[cle3] = percages.get(cle3, 0) + 1
    hors_pas = [d for (d, npth) in percages if not (d == 3.2 or (0.4 <= d <= 2.0 and abs(d * 5 - round(d * 5)) < 1e-6))]
    verdict(not hors_pas, "perçages : " + ", ".join(f"{n} de {d:g} mm{' non métallisés' if npth else ''}"
                                                   for (d, npth), n in sorted(percages.items()))
            + (f" ; hors du pas de la factory : {hors_pas}" if hors_pas else ""))
    corps = {}
    for fp in board.GetFootprints():
        box = None
        for g in fp.GraphicalItems():
            if g.Type() == pcbnew.PCB_SHAPE_T and g.GetLayer() == pcbnew.F_Fab:
                bb = g.GetBoundingBox()
                b4 = (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()))
                box = b4 if box is None else (min(box[0], b4[0]), min(box[1], b4[1]), max(box[2], b4[2]), max(box[3], b4[3]))
        if box:
            corps[fp.GetReference()] = box
    dessous = sorted((r, round(x, 1), round(y, 1)) for x, y in gnd for r, (x0, y0, x1, y1) in corps.items()
                     if x0 - 0.4 < x < x1 + 0.4 and y0 - 0.4 < y < y1 + 0.4)
    print(f"        {len(dessous)} via(s) GND sous un corps de composant : " + ", ".join(f"{r} ({x} ; {y})" for r, x, y in dessous))

    print("\nTous les critères sont tenus." if not echecs else f"\n{len(echecs)} critère(s) non tenu(s).")
    return 1 if echecs else 0


if __name__ == "__main__":
    os.chdir(HERE)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
