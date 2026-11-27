"""Prépare adaptateur_usb_can.kicad_pcb : contour, empreintes placées, nets, plan de masse.

Première étape de la chaîne de la carte (reprise après les remarques d'électronique),
à exécuter avec le Python livré avec KiCad 9 (KPY = "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe") :

    KPY generate_pcb.py         # placement : repart du gabarit ENSEA et écrase la carte
    KPY verif_placement.py      # pastilles attendues, composants figés par le boîtier, courtyards
    KPY router_manuel.py        # pistes, vias, couture de masse, remplissage, DRC
    KPY verifier_criteres.py    # mesures des remarques R1 à R7

Le routage est entièrement décrit par les tables de router_manuel.py, qui le repose à
l'identique : relancer ce script ne fait donc rien perdre.

Il recrée aussi la bibliothèque locale adaptateur_usb_can.pretty (et le fp-lib-table du
projet) : trois empreintes KiCad retouchées pour la factory, voir EMPREINTES_LOCALES.

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
# intégrés, quartz, boutons, LED et leurs résistances. Face arrière « B » : régulateur,
# protection USB, transceiver, découplages.
PLACEMENT = {
    # Figés par le boîtier imprimé (boitier/boitier.scad) : J1, J2, J3, JP1, SW1, SW2 et le
    # centre des LED D1 à D3 (trous du capot). U1, U2, U4 et F1 n'ont pas bougé non plus.
    "J1": (96.2, 115.0, 180, "F"),     # fiche USB-A mâle : repère « PCB Edge » sur le bord
    "U2": (115.0, 115.0, 0, "F"),      # CH340C
    "U1": (130.0, 115.0, 0, "F"),      # STM32G431KBT6
    # Bornier : broche 1 (GND) en bas, de haut en bas H, L, G comme l'USBCAN-Z.
    "J2": (156.3, 120.08, 90, "F"),
    "J3": (140.0, 109.92, 0, "F"),     # SWD
    "JP1": (144.0, 105.0, 0, "F"),     # terminaison 120 ohms
    "SW1": (121.8, 126.0, 0, "F"),     # RESET
    "SW2": (133.0, 104.0, 0, "F"),     # BOOT0
    "D1": (137.0, 104.5, 90, "F"),     # PWR
    # Rangée de LED au pas de 4,8 mm, anode à l'ouest, chacune sous sa résistance.
    "D2": (129.6, 126.4, 180, "F"),    # RX (PA7)
    "D3": (134.4, 126.4, 180, "F"),    # TX (PB0)
    "D4": (139.2, 126.4, 180, "F"),    # ERR rouge (PA8) : pas de trou dans le capot v0.2
    "R4": (129.6, 122.6, 270, "F"),
    "R5": (134.4, 122.6, 270, "F"),
    "R8": (139.2, 122.6, 270, "F"),
    "R1": (139.95, 103.5, 180, "F"),   # LED PWR : sur le tronc +3V3 de la face avant
    "R6": (143.0, 124.0, 0, "F"),      # rappel de CAN_S, sur le trajet de la piste
    # Quartz selon ST AN2867 : Y1 vertical en face des broches 2 et 3 (PF0, PF1), C10
    # au-dessus, C11 en dessous, pistes de 4 mm sans via, rien dessous en face arrière.
    # Les pastilles de Y1 sont allongées de 0,6 mm (voir PASTILLES_Y1) : Y1 est remonté
    # d'autant pour que NRST passe sous sa pastille sud, et C10 / C11 sont écartés.
    "Y1": (122.35, 112.8, 270, "F"),
    "C10": (122.35, 107.1, 90, "F"),
    "C11": (121.85, 118.5, 270, "F"),   # décalé vers l'ouest : place pour la garde côté NRST
    # Face arrière (une rotation r de ce tableau se lit 180 - r dans KiCad, après retournement).
    "U4": (115.0, 105.5, 0, "B"),      # régulateur, au-dessus du CH340C
    "C1": (109.3, 104.0, 90, "B"),
    "C2": (120.6, 103.9, 90, "B"),     # hors de la zone du quartz (C10 est juste au sud)
    "F1": (107.6, 122.8, 180, "B"),    # fusible : pastille VBUS à l'ouest, près de la fiche
    # Protection USB traversée en ligne, sous les pastilles de J1 : D+ sur la rangée nord
    # (broches 1 et 6), D- sur la rangée sud (3 et 4), masse (2) à l'est vers le plan,
    # VBUS (5) à l'ouest. Rien d'elle ne dépasse sous la paire, à l'est des pastilles de J1.
    "U5": (105.35, 115.0, 0, "B"),
    "C4": (109.8, 111.5, 90, "B"),     # V3 du CH340C
    "R2": (111.9, 111.6, 270, "B"),    # V3 = VCC, sous la broche 4 du CH340C
    "C3": (119.35, 111.14, 270, "B"),  # VCC du CH340C : un via dans chacune de ses pastilles
    # Découplage du STM32 : la pastille +3V3 de chaque condensateur est sur le via de la
    # broche qu'il découple, ou à moins de 3 mm d'elle.
    "C5": (126.74, 111.1, 180, "B"),   # VDD broche 1, sous la broche
    "C6": (136.4, 118.0, 90, "B"),     # VDD broche 17
    "C7": (132.4, 121.5, 0, "B"),      # 10 nF de VDDA, broche 15
    "C8": (132.4, 123.6, 0, "B"),      # 1 uF de VDDA
    "C9": (135.6, 122.9, 270, "B"),    # 4,7 uF, entre les broches 15 et 17
    "C12": (123.6, 122.9, 270, "B"),   # NRST : sert de pont sous les pistes UART
    "R3": (133.0, 107.8, 0, "B"),      # rappel de BOOT0
    # Transceiver sous le bornier (voulu), décalé de 1 mm vers l'ouest : ses pastilles sont
    # à 2 mm de celles de J2. Souder la face arrière avant J2 et J3.
    "U3": (150.8, 115.0, 90, "B"),
    "C13": (151.2, 120.3, 180, "B"),   # VCC, entre les broches 3 et 2
    "C14": (146.9, 112.3, 90, "B"),    # VIO
    "R7": (151.8, 106.5, 0, "B"),
}

# Zone du quartz : voir main(). QUARTZ_F est le contour (polygone) de la cellule gardée en
# face avant : quartz, C10, C11, pistes OSC et anneau de garde. À partir de la broche 4 (NRST),
# sa limite est passe juste à l'est de la garde de C11 : NRST et UART_TX restent dehors. Le coin
# nord-ouest est coupé : la piste +3V3 de C2 vers C3 y passe, hors de la cellule.
# QUARTZ_B, (x0, y0, x1, y1), est la zone sans piste de la face arrière.
QUARTZ_F = ((119.9, 106.3), (121.2, 105.0), (124.9, 105.0), (124.9, 114.2), (123.6, 114.2),
            (123.6, 116.5), (123.4, 116.7), (123.4, 120.6), (119.9, 120.6))
QUARTZ_B = (120.6, 106.3, 124.7, 120.4)

# Bibliothèque locale « adaptateur_usb_can » (dossier .pretty et fp-lib-table du projet) : trois
# empreintes de la bibliothèque KiCad retouchées pour la factory. Elle est refaite à chaque
# exécution par bibliotheque_locale() ; le schéma désigne ces empreintes par leur nom local.
NOM_LOCALE = "adaptateur_usb_can"
LOCALE = HERE / f"{NOM_LOCALE}.pretty"
# Empreinte locale -> (empreinte KiCad d'origine, retouches).
#   « pastilles » : pastilles allongées vers l'extérieur (mm). L'empreinte 5032 d'origine ne
#       laisse que 0,35 mm de pastille visible à chaque bout du boîtier, trop peu pour un fer ;
#       avec 0,6 mm de plus il en reste 0,95 mm (la variante « HandSoldering » de KiCad,
#       1,85 mm, ne tient pas entre C10 et C11).
#   « percages » : {perçage d'origine (x, y) : perçage posé}, au pas de la factory (0,4 à
#       2,0 mm par pas de 0,2 mm). Elle arrondit de toute façon au foret supérieur ; les
#       fichiers de perçage le disent ainsi sans ambiguïté.
# Dans les trois, la sérigraphie qui passerait sur une pastille ou hors de la carte est retirée.
EMPREINTES_LOCALES = {
    "Crystal_SMD_5032-2Pin_5.0x3.2mm_Pastilles2.6mm":
        ("Crystal:Crystal_SMD_5032-2Pin_5.0x3.2mm", {"pastilles": 0.6}),
    "USB_A_CNCTech_1001-011-01101_Horizontal_PercagesENSEA":
        ("Connector_USB:USB_A_CNCTech_1001-011-01101_Horizontal",
         {"percages": {(1.1, 1.1): (1.2, 1.2),      # pions de centrage, non métallisés
                       (2.5, 0.9): (2.5, 1.0)}}),   # fentes des pattes de blindage : outil de 1,0 mm
    "TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal_Percage1.4mm":
        ("TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal",
         {"percages": {(1.3, 1.3): (1.4, 1.4)}}),   # broches du bornier
}
SERIGRAPHIE_BORD = 0.3   # mm : la sérigraphie s'arrête à cette distance du bord de carte

VERSION = "v0.3"

# Pastilles de masse que le plan ne peut atteindre que d'un côté (un seul rayon de frein
# thermique, refusé par les règles ENSEA) : elles ne se raccordent pas au plan mais par une
# piste de router_manuel.py, qui joue le rôle du rayon. Les masses de C10 et C11 aussi : elles
# ne doivent rejoindre le plan que par l'anneau de garde du quartz et son via unique.
# Un troisième élément (x, y) désigne une seule des pastilles de même numéro : la patte de
# blindage sud de J1, dont la piste VBUS de U5 coupe les rayons nord et est.
SANS_FREIN = {("U5", "2"), ("U3", "2"), ("D4", "1"), ("J3", "3"), ("C10", "2"), ("C11", "2"),
              ("J1", "5", 103.1, 120.7)}

# Textes des couches Fab (plan d'implantation de generate_fabrication.py) : dans chaque
# composant, son repère et, dessous, sa valeur, en petits caractères horizontaux.
FAB_TAILLE, FAB_TRAIT, FAB_INTERLIGNE = 0.5, 0.08, 0.9


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


def decouper(a, b, rect):
    """Partie du segment a-b (mm) contenue dans le rectangle, ou None (Liang-Barsky)."""
    t0, t1 = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - rect[0]), (dx, rect[2] - a[0]), (-dy, a[1] - rect[1]), (dy, rect[3] - a[1])):
        if abs(p) < 1e-9:
            if q < 0:
                return None
        else:
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
    if t0 >= t1:
        return None
    return (a[0] + t0 * dx, a[1] + t0 * dy), (a[0] + t1 * dx, a[1] + t1 * dy)


def bibliotheque_locale(comps):
    """Recrée le dossier .pretty et le fp-lib-table du projet à partir de la bibliothèque KiCad."""
    LOCALE.mkdir(exist_ok=True)
    for f in LOCALE.glob("*.kicad_mod"):
        f.unlink()
    (HERE / "fp-lib-table").write_text(
        f'(fp_lib_table\n  (version 7)\n  (lib (name "{NOM_LOCALE}")(type "KiCad")'
        f'(uri "${{KIPRJMOD}}/{LOCALE.name}")(options "")'
        '(descr "Empreintes KiCad retouchées pour la factory ENSEA (generate_pcb.py)"))\n)\n',
        encoding="utf-8", newline="\n")
    dedans = (X0 + SERIGRAPHIE_BORD, Y0 + SERIGRAPHIE_BORD, X1 - SERIGRAPHIE_BORD, Y1 - SERIGRAPHIE_BORD)
    for nom, (origine, retouches) in EMPREINTES_LOCALES.items():
        lib, base = origine.split(":")
        fp = pcbnew.FootprintLoad(str(FOOTPRINTS / f"{lib}.pretty"), base)
        d = mm(retouches.get("pastilles", 0.0))
        if d:
            for pad in fp.Pads():
                pos, taille = pad.GetPosition(), pad.GetSize(pcbnew.F_Cu)
                pad.SetPosition(pcbnew.VECTOR2I(pos.x + (d if pos.x > 0 else -d) // 2, pos.y))
                pad.SetSize(pcbnew.F_Cu, pcbnew.VECTOR2I(taille.x + d, taille.y))
            for g in fp.GraphicalItems():
                if g.GetClass() != "PCB_SHAPE":
                    continue
                # Courtyard élargi d'autant ; le trait de sérigraphie du bout (repère de la
                # broche 1) recule devant la pastille.
                if g.GetLayer() == pcbnew.F_CrtYd or \
                        (g.GetLayer() == pcbnew.F_SilkS and min(g.GetStart().x, g.GetEnd().x) < -mm(2.9)):
                    a, b = g.GetStart(), g.GetEnd()
                    g.SetStart(pcbnew.VECTOR2I(a.x + (d if a.x > mm(2.9) else -d if a.x < -mm(2.9) else 0), a.y))
                    g.SetEnd(pcbnew.VECTOR2I(b.x + (d if b.x > mm(2.9) else -d if b.x < -mm(2.9) else 0), b.y))
        for pad in fp.Pads():
            perc = pad.GetDrillSize()
            nouveau = retouches.get("percages", {}).get(
                (round(pcbnew.ToMM(perc.x), 3), round(pcbnew.ToMM(perc.y), 3)))
            if nouveau:
                pad.SetDrillSize(pcbnew.VECTOR2I(mm(nouveau[0]), mm(nouveau[1])))
        # Sérigraphie hors de la carte : l'empreinte est posée à sa place (tous ces composants
        # sont en face avant), ses traits sont coupés au bord, puis elle revient à l'origine.
        refs = [r for r, c in comps.items() if c[1] == f"{NOM_LOCALE}:{nom}"]
        assert len(refs) == 1, f"{nom} : utilisée par {refs}"
        x, y, rot, face = PLACEMENT[refs[0]]
        assert face == "F"
        fp.SetPosition(point(x, y))
        fp.SetOrientationDegrees(rot)
        for g in list(fp.GraphicalItems()):
            if g.GetClass() != "PCB_SHAPE" or g.GetLayer() != pcbnew.F_SilkS:
                continue
            bb = g.GetBoundingBox()
            if all(dedans[0] <= pcbnew.ToMM(vx) <= dedans[2] and dedans[1] <= pcbnew.ToMM(vy) <= dedans[3]
                   for vx, vy in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetBottom()))):
                continue
            reste = None
            if g.GetShape() == pcbnew.SHAPE_T_SEGMENT:
                a, b = g.GetStart(), g.GetEnd()
                reste = decouper((pcbnew.ToMM(a.x), pcbnew.ToMM(a.y)), (pcbnew.ToMM(b.x), pcbnew.ToMM(b.y)), dedans)
            if reste is None:
                fp.Remove(g)
            else:
                g.SetStart(point(*reste[0]))
                g.SetEnd(point(*reste[1]))
        fp.SetOrientationDegrees(0)
        fp.SetPosition(point(0, 0))
        fp.SetFPID(pcbnew.LIB_ID(NOM_LOCALE, nom))
        # (pcbnew.FootprintSave ne reconnaît pas un dossier encore vide : greffon KiCad nommé)
        pcbnew.PCB_IO_MGR.PluginFind(pcbnew.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(LOCALE), fp)


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

    bibliotheque_locale(comps)
    for ref, (value, footprint, uuid) in sorted(comps.items()):
        lib, name = footprint.split(":")
        fp = pcbnew.FootprintLoad(str(LOCALE if lib == NOM_LOCALE else FOOTPRINTS / f"{lib}.pretty"), name)
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
            ici = (round(pcbnew.ToMM(pad.GetPosition().x), 2), round(pcbnew.ToMM(pad.GetPosition().y), 2))
            if (ref, pad.GetNumber()) in SANS_FREIN or (ref, pad.GetNumber(), *ici) in SANS_FREIN:
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_NONE)
        # Plan d'implantation : repère et valeur au milieu des pastilles du composant. (Les
        # repères de sérigraphie sont placés à la fin du routage, par router_manuel.py.)
        boites = [pad.GetBoundingBox() for pad in fp.Pads()]
        cx = (min(b.GetLeft() for b in boites) + max(b.GetRight() for b in boites)) // 2
        cy = (min(b.GetTop() for b in boites) + max(b.GetBottom() for b in boites)) // 2
        fab = pcbnew.B_Fab if face == "B" else pcbnew.F_Fab
        textes = [(g, -1) for g in fp.GraphicalItems()
                  if g.GetClass() == "PCB_TEXT" and g.GetLayer() == fab and "REFERENCE" in g.GetText()]
        for texte, rang in textes + [(fp.Value(), 1)]:
            texte.SetTextSize(pcbnew.VECTOR2I(mm(FAB_TAILLE), mm(FAB_TAILLE)))
            texte.SetTextThickness(mm(FAB_TRAIT))
            texte.SetTextAngleDegrees(0)
            texte.SetPosition(pcbnew.VECTOR2I(cx, cy + rang * mm(FAB_INTERLIGNE) // 2))

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
        # Un morceau de plan que rien ne relie à la masse est retiré au remplissage.
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        outline = zone.Outline()
        outline.NewOutline()
        for c in corners:
            outline.Append(mm(c[0]), mm(c[1]))
        board.Add(zone)

    # Bande de 0,6 mm le long des bords, interdite aux pistes et aux vias : garde-fou pour
    # l'isolation de 0,5 mm au contour demandée par la factory.
    def interdire(contour, couches, vias, pistes=True, cuivre=False, nom=""):
        """Zone de règle : contour = rectangle (x0, y0, x1, y1) ou polygone ((x, y), ...)."""
        lset = pcbnew.LSET()
        for c in couches:
            lset.AddLayer(c)
        if not isinstance(contour[0], tuple):
            x0, y0, x1, y1 = contour
            contour = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
        keep = pcbnew.ZONE(board)
        keep.SetIsRuleArea(True)
        keep.SetLayerSet(lset)
        keep.SetZoneName(nom)
        keep.SetDoNotAllowTracks(pistes)
        keep.SetDoNotAllowVias(vias)
        keep.SetDoNotAllowPads(False)
        keep.SetDoNotAllowFootprints(False)
        keep.SetDoNotAllowCopperPour(cuivre)
        ko = keep.Outline()
        ko.NewOutline()
        for cx, cy in contour:
            ko.Append(mm(cx), mm(cy))
        board.Add(keep)

    deux = (pcbnew.F_Cu, pcbnew.B_Cu)
    b = 0.6
    for rect in ((X0, Y0, X1, Y0 + b), (X0, Y1 - b, X1, Y1),
                 (X0, Y0, X0 + b, Y1), (X1 - b, Y0, X1, Y1)):
        interdire(rect, deux, vias=True)
    # Zone du quartz (ST AN2867). Sur F.Cu le plan général ne remplit pas : l'anneau de garde
    # tracé par router_manuel.py y forme un îlot, relié au plan par un seul via près de la
    # broche 32 (VSS). Sur B.Cu aucune piste : le plan reste plein sous le quartz.
    interdire(QUARTZ_F, (pcbnew.F_Cu,), vias=False, pistes=False, cuivre=True, nom="quartz_F")
    interdire(QUARTZ_B, (pcbnew.B_Cu,), vias=False, pistes=True, nom="quartz_B")

    label = pcbnew.PCB_TEXT(board)
    label.SetText(f"G69 {VERSION}")
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

    cartouche = board.GetTitleBlock()
    cartouche.SetTitle("Adaptateur USB-CAN - banc CAN G69")
    cartouche.SetRevision(VERSION.lstrip("v"))
    cartouche.SetCompany("ENSEA - Projet 2A")
    cartouche.SetComment(0, "Généré par generate_pcb.py, routé par router_manuel.py")

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(PCB))
    print(f"{PCB.name} : {len(comps)} empreintes, {len(nets)} nets, carte "
          f"{X1 - X0:.1f} x {Y1 - Y0:.1f} mm")


if __name__ == "__main__":
    os.chdir(HERE)
    main()
