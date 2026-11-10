"""Route adaptateur_usb_can.kicad_pcb avec Freerouting (2 couches, règles ENSEA).

À lancer après generate_pcb.py, avec le Python livré avec KiCad 9 :

    "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" route_freerouting.py <freerouting.jar>

Testé avec Freerouting 2.5.0 (https://github.com/freerouting/freerouting/releases).

Freerouting route les signaux et les alimentations, sans la masse : la carte est dense, et
les 30 liaisons de masse encombreraient le routeur. La masse passe ensuite par les deux plans
de cuivre : chaque pastille CMS de masse reçoit un via voisin relié par une piste courte, puis
des vias de couture relient les deux plans sur toute la carte.

Les plans de masse sont retirés de chaque export puis remplis de nouveau après import ; les
zones interdites le long des bords restent, comme contraintes. Le fanout (un via au pied de
chaque pastille CMS) est activé : des composants sont soudés sur les deux faces. Freerouting
rétrécit parfois des pistes à 0,3 mm malgré --router.automatic_neckdown=false : elles sont
remises à 0,4 mm, la largeur minimale du fichier de règles de la factory.

Sur la carte 60 x 30 mm, Freerouting laisse quelques liaisons autour du STM32 : elles ont
été terminées à la main (pistes et vias posés par script, DRC après chaque étape), et les
zones interdites du centre du STM32, qui ne servent qu'au routage, ont été retirées.

Chaque appel à pcbnew se fait dans un processus neuf : après LoadBoard, les objets renvoyés
par pcbnew perdent parfois leur type (« SwigPyObject ») et le script plante.
"""

import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

PCB = Path(__file__).with_name("adaptateur_usb_can.kicad_pcb")
LARGEUR = 0.4  # mm
CLI = r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"


ESSAIS = 4  # Freerouting donne des résultats différents d'un essai à l'autre


def main(jar):
    work = Path(tempfile.mkdtemp(prefix="freerouting_"))
    dsn = work / "board.dsn"
    etape("--exporter", dsn)
    sans_masse(dsn)
    essais = []
    for i in range(ESSAIS):  # en parallèle, chacun dans son dossier
        d = work / f"essai{i}"
        d.mkdir()
        essais.append((d, subprocess.Popen(
            ["java", "-jar", jar, "-de", str(dsn), "-do", str(d / "board.ses"), "-l", "en",
             "-mt", "2", "--gui.enabled=false", "--api_server.enabled=false",
             "--router.autorouter.max_passes=500",
             "--router.automatic_neckdown=false", "--router.fanout.enabled=true"],
            cwd=d, stdout=open(d / "freerouting.log", "w"), stderr=subprocess.STDOUT)))
    resultats = []
    for d, proc in essais:
        proc.wait()
        log = (d / "freerouting.log").read_text(encoding="utf-8", errors="replace")
        m = re.findall(r"final score: [\d.]+ \((\d+) unrouted", log)
        if (d / "board.ses").exists() and m:
            resultats.append((int(m[-1]), d))
    assert resultats, "aucun essai de Freerouting n'a abouti"
    resultats.sort()
    print("non routées par essai :", [n for n, _ in resultats])
    etape("--importer", resultats[0][1] / "board.ses")
    print(f"meilleur essai : {resultats[0][1]}")
    etape("--masse-pads", PCB)
    etape("--coudre", PCB)
    for _ in range(3):  # un via retiré peut en laisser un autre seul sur sa face
        if not etape_sortie("--nettoyer", PCB):
            break


def etape_sortie(option, fichier):
    """Lance une étape ; renvoie True si elle a modifié la carte (code de sortie 3)."""
    r = subprocess.run([sys.executable, __file__, option, str(fichier)])
    assert r.returncode in (0, 3), f"étape {option} en échec"
    return r.returncode == 3


def etape(option, fichier):
    subprocess.run([sys.executable, __file__, option, str(fichier)], check=True)


def exporter(dsn):
    board = pcbnew.LoadBoard(str(PCB))
    for zone in list(board.Zones()):
        if not zone.GetIsRuleArea():
            board.Remove(zone)
    assert pcbnew.ExportSpecctraDSN(board, str(dsn)), "export DSN impossible"


def sans_masse(dsn):
    """Retire le net GND du DSN."""
    text = dsn.read_text(encoding="utf-8")
    start = text.index("(net GND\n")
    end = text.index(")", text.index("(pins", start)) + 1  # fin de la liste des broches
    end = text.index(")", end) + 1                          # fin du bloc (net GND ...)
    text = text[:start] + text[end:]
    text = re.sub(r"(\(class [^)]*?) GND(?=[ \n)])", r"\1", text)
    dsn.write_text(text, encoding="utf-8")


def importer(ses):
    board = pcbnew.LoadBoard(str(PCB))
    assert pcbnew.ImportSpecctraSES(board, str(ses)), "import SES impossible"
    minimum = pcbnew.FromMM(LARGEUR)
    elargies = 0
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetWidth() < minimum:
            t.SetWidth(minimum)
            elargies += 1
    board.Save(str(PCB))
    subprocess.run([sys.executable, __file__, "--remplir", str(PCB)], check=True)
    print(f"{elargies} pistes remises à {LARGEUR} mm")


def remplir(_):
    board = pcbnew.LoadBoard(str(PCB))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(PCB))
    vias = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_VIA")
    print(f"{PCB.name} : {vias} vias")


def _dist_segment(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    u = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - u * dx, py - ay - u * dy)


def _obstacles(board, ignorer_gnd_pads=False):
    """Cuivre des autres nets que GND : pastilles (rectangles englobants), pistes et vias
    (segments avec demi-largeur), et tous les trous (pour l'écart entre trous)."""
    mm = pcbnew.ToMM
    pads, tracks, holes = [], [], []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.HasHole():
                c = p.GetPosition()
                holes.append((mm(c.x), mm(c.y), mm(p.GetDrillSize().x) / 2))
            if ignorer_gnd_pads and p.GetNetname() == "GND":
                continue
            r = p.GetBoundingBox()
            pads.append((mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())))
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            c = t.GetPosition()
            holes.append((mm(c.x), mm(c.y), mm(t.GetDrillValue()) / 2))
            if t.GetNetname() != "GND":
                tracks.append((mm(c.x), mm(c.y), mm(c.x), mm(c.y), mm(t.GetWidth(pcbnew.F_Cu)) / 2))
        elif t.GetNetname() != "GND":
            s, e = t.GetStart(), t.GetEnd()
            tracks.append((mm(s.x), mm(s.y), mm(e.x), mm(e.y), mm(t.GetWidth()) / 2))
    return pads, tracks, holes


def _interdits(board):
    """Rectangles des zones interdites aux pistes : [(x0, y0, x1, y1, couches, vias_interdits)]."""
    mm = pcbnew.ToMM
    out = []
    for z in board.Zones():
        if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
            r = z.GetBoundingBox()
            couches = {c for c in (pcbnew.F_Cu, pcbnew.B_Cu) if z.IsOnLayer(c)}
            out.append((mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom()),
                        couches, z.GetDoNotAllowVias()))
    return out


def _dans(x, y, marge, rect):
    x0, y0, x1, y1 = rect[:4]
    return x0 - marge < x < x1 + marge and y0 - marge < y < y1 + marge


def _point_libre(x, y, r, pads, tracks):
    for l, t_, rr, b in pads:
        if math.hypot(max(l - x, 0, x - rr), max(t_ - y, 0, y - b)) < r + 0.3:
            return False
    for ax, ay, bx, by, w in tracks:
        if _dist_segment(x, y, ax, ay, bx, by) < r + w + 0.3:
            return False
    return True


def _via(board, net, x, y):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
    v.SetWidth(pcbnew.FromMM(0.8))
    v.SetDrill(pcbnew.FromMM(0.4))
    v.SetNet(net)
    board.Add(v)


def masse_pads(_):
    """Relie chaque pastille CMS de masse à un via posé juste à côté, par une piste courte :
    la pastille rejoint ainsi le plan de masse de l'autre face, même si les pistes voisines
    l'ont isolée du plan de sa propre face."""
    mm = pcbnew.ToMM
    board = pcbnew.LoadBoard(str(PCB))
    gnd = board.FindNet("GND")
    pads, tracks, holes = _obstacles(board, ignorer_gnd_pads=True)
    zones = _interdits(board)
    gnd_pads = []  # pastilles de masse : un via n'y entre pas
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == "GND":
                r = p.GetBoundingBox()
                gnd_pads.append((mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())))
    gnd_vias = [(mm(t.GetPosition().x), mm(t.GetPosition().y)) for t in board.GetTracks()
                if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]

    def chemin_libre(px, py, vx, vy, couche, fin):
        """La piste pastille → via (0,4 mm) respecte isolations et zones interdites ; on ne
        teste qu'à partir de 0,6 mm de la pastille et jusqu'à `fin` mm du via."""
        d = math.hypot(vx - px, vy - py)
        n = max(int(d / 0.1), 1)
        for i in range(n + 1):
            x, y = px + (vx - px) * i / n, py + (vy - py) * i / n
            if any(couche in z[4] and _dans(x, y, 0.2, z) for z in zones):
                return False
            s = d * i / n
            if 0.6 < s < d - fin and not _point_libre(x, y, 0.2, pads, tracks):
                return False
        return True

    deja = {(round(mm(q.x), 3), round(mm(q.y), 3)) for t in board.GetTracks()
            if t.GetClass() == "PCB_TRACK" and t.GetNetname() == "GND"
            for q in (t.GetStart(), t.GetEnd())}
    poses = 0
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != "GND" or p.HasHole():
                continue
            c = p.GetPosition()
            px, py = mm(c.x), mm(c.y)
            if (round(px, 3), round(py, 3)) in deja:  # pastille déjà reliée à un via
                continue
            couche = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            for d in (1.3, 1.6, 2.0, 2.5):
                trouve = None
                for k in range(16):
                    a = k * math.pi / 8
                    vx, vy = px + d * math.cos(a), py + d * math.sin(a)
                    if not _point_libre(vx, vy, 0.4, pads, tracks):
                        continue
                    if any(z[5] and _dans(vx, vy, 0.4, z) for z in zones):
                        continue
                    if any(math.hypot(max(l - vx, 0, vx - r), max(t_ - vy, 0, vy - b)) < 0.5
                           for l, t_, r, b in gnd_pads):
                        continue
                    if any(math.hypot(vx - hx, vy - hy) < 0.2 + hr + 0.8 for hx, hy, hr in holes):
                        continue
                    if chemin_libre(px, py, vx, vy, couche, 0.0):
                        trouve = (vx, vy)
                        break
                if trouve:
                    break
            existant = False
            if not trouve:  # sinon, un via de masse déjà posé, à moins de 3 mm
                for vx, vy in sorted(gnd_vias, key=lambda v: math.hypot(v[0] - px, v[1] - py)):
                    d = math.hypot(vx - px, vy - py)
                    if d > 3.0:
                        break
                    if chemin_libre(px, py, vx, vy, couche, 0.45):
                        trouve, existant = (vx, vy), True
                        break
            if not trouve:
                print(f"  pas de place pour un via près de {fp.GetReference()}-{p.GetNumber()}")
                continue
            vx, vy = trouve
            if not existant:
                _via(board, gnd, vx, vy)
                gnd_vias.append((vx, vy))
            t = pcbnew.PCB_TRACK(board)
            t.SetLayer(couche)
            t.SetWidth(pcbnew.FromMM(LARGEUR))
            t.SetStart(c)
            t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(vx), pcbnew.FromMM(vy)))
            t.SetNet(gnd)
            board.Add(t)
            holes.append((vx, vy, 0.2))
            poses += 1
    board.Save(str(PCB))
    subprocess.run([sys.executable, __file__, "--remplir", str(PCB)], check=True)
    print(f"{poses} pastilles de masse reliées à un via")


def coudre(_):
    """Vias de couture GND : relient les plans de masse des deux faces, dont les îlots isolés
    par les pistes. Posés sur une grille, seulement là où ils respectent toutes les règles
    (isolation 0,3 mm, 0,5 mm entre trou et cuivre, 0,8 mm entre trous, 1,2 mm du bord)."""
    mm = pcbnew.ToMM
    board = pcbnew.LoadBoard(str(PCB))
    gnd = board.FindNet("GND")
    bb = board.GetBoardEdgesBoundingBox()
    x0, y0, x1, y1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
    rv, rt = 0.4, 0.2  # rayon du via, rayon de son trou (0,8/0,4 mm)
    pads, tracks, holes = [], [], []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            r = p.GetBoundingBox()
            pads.append((mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())))
            if p.HasHole():
                c = p.GetPosition()
                holes.append((mm(c.x), mm(c.y), mm(p.GetDrillSize().x) / 2))
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            c = t.GetPosition()
            holes.append((mm(c.x), mm(c.y), mm(t.GetDrillValue()) / 2))
            if t.GetNetname() != "GND":
                tracks.append((mm(c.x), mm(c.y), mm(c.x), mm(c.y), mm(t.GetWidth(pcbnew.F_Cu)) / 2))
        elif t.GetNetname() != "GND":
            s, e = t.GetStart(), t.GetEnd()
            tracks.append((mm(s.x), mm(s.y), mm(e.x), mm(e.y), mm(t.GetWidth()) / 2))

    zones = _interdits(board)

    def libre(x, y):
        if any(z[5] and _dans(x, y, rv, z) for z in zones):
            return False
        for l, t_, r, b in pads:  # pas de via dans ni contre une pastille
            dx, dy = max(l - x, 0, x - r), max(t_ - y, 0, y - b)
            if math.hypot(dx, dy) < rv + 0.3:
                return False
        for ax, ay, bx, by, w in tracks:
            if _dist_segment(x, y, ax, ay, bx, by) < rv + w + 0.3:
                return False
        for hx, hy, hr in holes:
            d = math.hypot(x - hx, y - hy)
            if d < rt + hr + 0.8 or d < hr + rv + 0.5:
                return False
        return True

    poses = 0
    pas = 1.0
    y = y0 + 1.2
    while y <= y1 - 1.2:
        x = x0 + 1.2
        while x <= x1 - 1.2:
            if libre(x, y):
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
                v.SetWidth(pcbnew.FromMM(2 * rv))
                v.SetDrill(pcbnew.FromMM(2 * rt))
                v.SetNet(gnd)
                board.Add(v)
                holes.append((x, y, rt))
                # écart entre vias de couture : 2,5 mm suffisent à relier les îlots
                holes.append((x, y, 1.5))
                poses += 1
            x += pas
        y += pas
    board.Save(str(PCB))
    subprocess.run([sys.executable, __file__, "--remplir", str(PCB)], check=True)
    print(f"{poses} vias de couture posés")


def nettoyer(_):
    """Retire les vias que le DRC déclare reliés d'un seul côté (ou pas du tout)."""
    rpt = PCB.with_suffix(".drc_tmp.rpt")
    subprocess.run([CLI, "pcb", "drc", "--severity-all", "-o", str(rpt), str(PCB)],
                   check=True, capture_output=True)
    text = rpt.read_text(encoding="utf-8")
    rpt.unlink()
    cibles = set(re.findall(r"\[via_dangling\][^\n]*\n[^\n]*\n\s*@\(([\d,]+) mm, ([\d,]+) mm\)",
                            text))
    if not cibles:
        sys.exit(0)
    board = pcbnew.LoadBoard(str(PCB))
    pts = {(round(float(x.replace(",", ".")), 3), round(float(y.replace(",", ".")), 3))
           for x, y in cibles}
    for t in list(board.GetTracks()):
        if t.GetClass() == "PCB_VIA":
            c = t.GetPosition()
            if (round(pcbnew.ToMM(c.x), 3), round(pcbnew.ToMM(c.y), 3)) in pts:
                t.DeleteStructure()
    board.Save(str(PCB))
    subprocess.run([sys.executable, __file__, "--remplir", str(PCB)], check=True)
    print(f"{len(pts)} vias isolés retirés")
    sys.exit(3)


if __name__ == "__main__":
    etapes = {"--exporter": exporter, "--importer": importer, "--remplir": remplir,
              "--masse-pads": masse_pads, "--coudre": coudre, "--nettoyer": nettoyer}
    if sys.argv[1] in etapes:
        etapes[sys.argv[1]](Path(sys.argv[2]))
    else:
        main(sys.argv[1])
