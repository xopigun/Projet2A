"""Retire d'une carte les vias de masse dont elle n'a pas besoin.

    "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" elaguer_vias.py <carte.kicad_pcb>

Sont retirés, s'ils ne servent à aucune liaison :
- les vias de couture (masse, aucune piste) ;
- les vias de masse reliés à des pastilles par des pistes (la pastille touche alors le plan
  de sa propre face), avec les pistes qui ne menaient plus qu'à eux.
Les vias de signal et d'alimentation ne sont jamais touchés.

Contrôle : après chaque retrait, les plans sont remplis de nouveau et les liaisons manquantes
recomptées ; un retrait qui en ajoute est annulé. Les teardrops des vias retirés sont
supprimés avec eux. Les vias de couture se remettent ensuite à la main, aux endroits voulus.
"""

import sys
from pathlib import Path

import pcbnew

MM = pcbnew.ToMM


def manquantes(board):
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    return board.GetConnectivity().GetUnconnectedCount(False)


def cle(p):
    return (round(MM(p.x), 3), round(MM(p.y), 3))


def candidats(board):
    """[(via, [])] pour tous les vias de masse ; leurs pistes sont trouvées au retrait."""
    return [(v, []) for v in board.GetTracks()
            if v.Type() == pcbnew.PCB_VIA_T and v.GetNetname() == "GND"]


def pistes_en_lair(board):
    """Pistes de masse dont un bout ne touche plus rien (ni pastille, ni via, ni piste)."""
    pistes = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T and t.GetNetname() == "GND"]
    vias = {cle(v.GetPosition()) for v in board.GetTracks() if v.Type() == pcbnew.PCB_VIA_T}
    pads = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname() == "GND"]
    bouts = {}
    for t in pistes:
        for q in (t.GetStart(), t.GetEnd()):
            bouts[cle(q)] = bouts.get(cle(q), 0) + 1
    out = []
    for t in pistes:
        for q in (t.GetStart(), t.GetEnd()):
            if bouts[cle(q)] == 1 and cle(q) not in vias and not any(p.HitTest(q) for p in pads):
                out.append(t)
                break
    return out


def retirer_via(board, v):
    """Retire un via et les pistes de masse qui ne menaient plus qu'à lui ; renvoie le tout."""
    board.Remove(v)
    enleves = [v]
    while True:
        orphelines = pistes_en_lair(board)
        if not orphelines:
            return enleves
        for t in orphelines:
            board.Remove(t)
            enleves.append(t)


def retirer(board, groupe):
    for v, ts in groupe:
        for t in ts:
            board.Remove(t)
        board.Remove(v)


def remettre(board, groupe):
    for v, ts in groupe:
        board.Add(v)
        for t in ts:
            board.Add(t)


def main(chemin):
    """Essaie de retirer UN via de masse, puis s'arrête : pcbnew devient instable
    (« SwigPyObject ») quand on remet des objets retirés dans une carte. Si le via est
    nécessaire, la carte n'est simplement pas enregistrée et sa position est notée dans
    <carte>.vias_gardes. Relancer jusqu'à « terminé »."""
    notes = Path(chemin + ".vias_gardes")
    gardes = set(tuple(map(float, l.split())) for l in notes.read_text().splitlines() if l.strip()) if notes.exists() else set()
    board = pcbnew.LoadBoard(chemin)
    base = manquantes(board)
    cand = [v for v, _ in candidats(board) if cle(v.GetPosition()) not in gardes]
    if not cand:
        print("terminé :", sum(1 for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T), "vias")
        return
    v = cand[0]
    pos = cle(v.GetPosition())
    enleves = retirer_via(board, v)
    if manquantes(board) > base:
        gardes.add(pos)
        notes.write_text(chr(10).join(f"{x} {y}" for x, y in sorted(gardes)))
        print(f"gardé {pos} ; {len(cand) - 1} à essayer")
        return
    p = pcbnew.VECTOR2I(pcbnew.FromMM(pos[0]), pcbnew.FromMM(pos[1]))
    for z in list(board.Zones()):  # teardrop orphelin
        if z.IsTeardropArea() and z.GetBoundingBox().Contains(p):
            board.Remove(z)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(chemin)
    print(f"retiré {pos} (+{len(enleves) - 1} pistes) ; {len(cand) - 1} à essayer")


if __name__ == "__main__":
    main(sys.argv[1])
