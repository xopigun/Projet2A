"""Schéma de câblage du banc : 4 Nucleo-G431KB + 4 TJA1051T/3 sur adaptateur SOP8, ZLG, PC.

    python generate_cablage.py

Écrit cablage_bus_can.kicad_sch (A3), puis cablage_bus_can.pdf avec kicad-cli. C'est un
schéma de câblage entre modules, pas une carte à fabriquer : les cartes du commerce sont
dessinées comme des blocs, avec les broches réellement utilisées. Les transceivers, leurs
condensateurs et la terminaison sont les vrais symboles de la bibliothèque KiCad.

Matériel : bon de commande BC-2026-G69-001 du 6 octobre 2026 (2 NUCLEO-G431KB commandées
+ 2 du stock ENSEA ; TJA1051T/3/1J en SO8, Farnell 2574963 ; adaptateurs SOP8 vers DIP8,
Gotronic ; hub USB alimenté Velleman HQM121C ; résistances 120 Ω et 100 nF du stock ENSEA).

Sources :
- NUCLEO-G431KB : UM2397 Rev 2, §6.4 (alimentation) et Table 11 (connecteurs CN3/CN4) ;
- TJA1051T/3 : datasheet NXP TJA1051 (brochage SO8, VCC 4,5 à 5,5 V, VIO, broche S) ;
- ZLG USBCAN-UC12 (vendu comme MyActuator USBCAN-Z) : marquage du boîtier (CAN-L, CAN-H,
  CAN-G, interrupteur 120 Ω), énumération USB relevée sur le banc (VID 0471 PID 1200) ;
- docs/pinout.md : FDCAN1 (PA12 TX, PA11 RX), HW1, §5 transceiver, §6 terminaisons ;
- docs/bringup.md, étape 4 : câblage Nucleo -> TJA1051T/3.
"""

import subprocess
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "adaptateur_usb_can"))
import kisym  # noqa: E402

NAME = "cablage_bus_can"
ROOT = "3b7d2c10-8e4f-4a55-9c21-6a0f5e7b9d42"
CLI = r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"
FONT = "(effects (font (size 1.27 1.27)))"
HIDDEN = "(effects (font (size 1.27 1.27)) (hide yes))"

_n = 0


def uid(tag=None):
    global _n
    _n += 1
    return str(uuid.uuid5(uuid.UUID(ROOT), tag or f"item:{_n}"))


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


# --- symboles des modules --------------------------------------------------------
# Broche : (nom, numéro, x, y, angle[, type]) en coordonnées de bibliothèque (y vers le
# haut) ; (x, y) est l'extrémité de connexion, l'angle la direction vers le corps.

VALUE_AT = {}  # position du nom du module dans son cadre, reprise à chaque pose


def pin_length(rect, x, y, a):
    """Longueur de broche jusqu'au bord du cadre, du côté où elle sort."""
    (x0, y0), (x1, y1) = rect
    return {270: y - y0, 90: y1 - y, 180: x - x1, 0: x0 - x}[a]


def module_symbol(name, rect, pins, ref, value_at, show_numbers=True, extra=""):
    (x0, y0), (x1, y1) = rect
    VALUE_AT[name] = value_at
    body = "".join(
        f"(pin {p[5] if len(p) > 5 else 'passive'} line (at {f(p[2])} {f(p[3])} {p[4]}) "
        f"(length {f(pin_length(rect, p[2], p[3], p[4]))}) "
        f"(name {q(p[0])} {FONT}) (number {q(p[1])} {FONT}))"
        for p in pins)
    return (
        f"(symbol {q('banc:' + name)} (pin_names (offset 1.016)) "
        + ("" if show_numbers else "(pin_numbers (hide yes)) ")
        + "(exclude_from_sim yes) (in_bom no) (on_board no) "
        f"(property \"Reference\" {q(ref)} (at {f(x0)} {f(y0 + 1.27)} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) "
        f"(property \"Value\" {q(name)} (at {f(value_at[0])} {f(value_at[1])} 0) (effects (font (size 1.524 1.524) (bold yes)))) "
        f"(property \"Footprint\" \"\" (at 0 0 0) {HIDDEN}) "
        f"(property \"Datasheet\" \"\" (at 0 0 0) {HIDDEN}) "
        f"(symbol {q(name + '_0_1')} (rectangle (start {f(x0)} {f(y0)}) (end {f(x1)} {f(y1)}) "
        f"(stroke (width 0.254) (type default)) (fill (type background))) {extra})"
        f"(symbol {q(name + '_1_1')} {body}))"
    )


NUC = "NUCLEO-G431KB"
# Broches du haut dans l'ordre des fils qui montent vers le transceiver (aucun croisement
# côté gauche) ; 3V3 à droite, sous la broche 5 (VIO).
NUC_PINS = [
    ("TX/PA12/D2", "CN4-5", -26.67, 20.32, 270),
    ("GND", "CN4-4", -21.59, 20.32, 270),
    ("5V", "CN3-4", -16.51, 20.32, 270),
    ("RX/PA11/D10", "CN4-13", -11.43, 20.32, 270),
    ("3V3", "CN3-14", 26.67, 20.32, 270),
    ("USB/ST-LINK", "CN1", 19.05, -20.32, 90),
]
# TJA1051T/3 soudé sur l'adaptateur SOP8 -> DIP8, vu de dessus : broches 1 à 4 à
# gauche (de haut en bas), 5 à 8 à droite (de bas en haut) ; 1 fait face à 8, 4 à 5.
# Pas de 7,62 mm : un condensateur tient exactement entre deux broches voisines.
TRX = "TJA1051T-3_SOP8"
TRX_PINS = [
    ("TXD", "1", -12.7, 11.43, 0), ("GND", "2", -12.7, 3.81, 0),
    ("VCC", "3", -12.7, -3.81, 0), ("RXD", "4", -12.7, -11.43, 0),
    ("VIO", "5", 12.7, -11.43, 180), ("CANL", "6", 12.7, -3.81, 180),
    ("CANH", "7", 12.7, 3.81, 180), ("S", "8", 12.7, 11.43, 180),
]
PIN1_DOT = ("(circle (center -5.08 12.7) (radius 0.635) (stroke (width 0.254) (type default)) "
            "(fill (type outline)))")
ZLG = "ZLG USBCAN-UC12"
ZLG_PINS = [("CAN-H", "H", 17.78, 7.62, 180), ("CAN-L", "L", 17.78, 0, 180),
            ("CAN-G", "G", 17.78, -7.62, 180), ("USB", "USB", 0, -15.24, 90)]
PC = "PC + hub USB alimenté (Velleman HQM121C)"

# --- implantation ----------------------------------------------------------------

Y_H, Y_L, Y_G = 45.72, 53.34, 60.96        # lignes du bus
Y_TRX, Y_NUC, Y_PC = 96.52, 144.78, 182.88  # transceivers, Nucleo, PC
UX = 40.64                                 # ZLG, à gauche du bus (extrémité 1)
TRX_X = [99.06 + 83.82 * i for i in range(4)]  # transceivers U1..U4
NUC_DX = -11.43                            # Nucleo, décalée à gauche de son transceiver
PC_X0, PC_HALF = 195.58, 170.18
PC_PINS = [("USB", str(i + 1), x - PC_X0, 12.7, 270)
           for i, x in enumerate([UX] + [tx + NUC_DX + 19.05 for tx in TRX_X])]

LIB = [
    module_symbol(NUC, ((-31.75, 12.7), (31.75, -12.7)), NUC_PINS, "N", (0, -3.81)),
    module_symbol(TRX, ((-7.62, 15.24), (7.62, -15.24)), TRX_PINS, "U", (0, 19.05),
                  extra=PIN1_DOT),
    module_symbol(ZLG, ((-22.86, 10.16), (12.7, -10.16)), ZLG_PINS, "J", (-5.08, 3.81),
                  show_numbers=False),
    module_symbol(PC, ((-PC_HALF, 7.62), (PC_HALF, -7.62)), PC_PINS, "PC", (0, -2.54),
                  show_numbers=False),
]

TWO_PINS = {"1": (0, 3.81), "2": (0, -3.81)}  # Device:C et Device:R, verticaux

# --- instances, fils, textes -----------------------------------------------------

items = []
junctions = set()


def instance(lib_id, ref, x, y, pin_numbers, props, in_bom):
    pins_s = "".join(f"(pin {q(num)} (uuid {q(uid(f'{ref}:pin:{num}'))}))" for num in pin_numbers)
    bom = "yes" if in_bom else "no"
    items.append(
        f"(symbol (lib_id {q(lib_id)}) (at {f(x)} {f(y)} 0) (unit 1) (exclude_from_sim yes) "
        f"(in_bom {bom}) (on_board {bom}) (dnp no) (uuid {q(uid('symbol:' + ref))}) {props}{pins_s} "
        f"(instances (project {q(NAME)} (path {q('/' + ROOT)} (reference {q(ref)}) (unit 1)))))")


def place(lib, ref, x, y, pins, fields=(), ref_at=None, value=None):
    """Pose un module ; renvoie {numéro de broche: (x, y) sur la feuille}."""
    rx, ry = ref_at or (x, y)
    vx, vy = VALUE_AT[lib]
    props = (f"(property \"Reference\" {q(ref)} (at {f(rx)} {f(ry)} 0) (effects (font (size 1.524 1.524) (bold yes)) (justify left bottom))) "
             f"(property \"Value\" {q(value or lib)} (at {f(x + vx)} {f(y - vy)} 0) (effects (font (size 1.524 1.524) (bold yes)))) "
             f"(property \"Footprint\" \"\" (at {f(x)} {f(y)} 0) {HIDDEN}) "
             f"(property \"Datasheet\" \"\" (at {f(x)} {f(y)} 0) {HIDDEN}) ")
    for name, val, fx, fy, *centre in fields:
        just = "" if centre else " (justify left bottom)"
        props += f"(property {q(name)} {q(val)} (at {f(fx)} {f(fy)} 0) (effects (font (size 1.27 1.27)){just})) "
    instance("banc:" + lib, ref, x, y, [p[1] for p in pins], props, in_bom=False)
    return {p[1]: (round(x + p[2], 2), round(y - p[3], 2)) for p in pins}


def place_part(lib_id, ref, value, x, y, texts, fields=()):
    """Pose un condensateur ou une résistance verticale ; @p texts = positions (x, y)
    de la référence et de la valeur, justifiées à gauche."""
    (rx, ry), (vx, vy) = texts
    left = "(effects (font (size 1.27 1.27)) (justify left))"
    props = (f"(property \"Reference\" {q(ref)} (at {f(rx)} {f(ry)} 0) {left}) "
             f"(property \"Value\" {q(value)} (at {f(vx)} {f(vy)} 0) {left}) "
             f"(property \"Footprint\" \"\" (at {f(x)} {f(y)} 0) {HIDDEN}) "
             f"(property \"Datasheet\" \"\" (at {f(x)} {f(y)} 0) {HIDDEN}) ")
    for name, val, fx, fy in fields:
        props += f"(property {q(name)} {q(val)} (at {f(fx)} {f(fy)} 0) {left}) "
    instance(lib_id, ref, x, y, list(TWO_PINS), props, in_bom=True)


def lib_text(lib_id):
    return kisym.dump(kisym.load(lib_id))


def wire(*pts, width=0):
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        items.append(f"(wire (pts (xy {f(x0)} {f(y0)}) (xy {f(x1)} {f(y1)})) "
                     f"(stroke (width {width}) (type default)) (uuid {q(uid())}))")


def line(y, xs, width=0):
    """Ligne horizontale coupée à chaque dérivation, avec un point de jonction."""
    xs = sorted(set(xs))
    for a, b in zip(xs, xs[1:]):
        wire((a, y), (b, y), width=width)
    for x in xs[1:-1]:
        junctions.add((x, y))


def vline(x, ys):
    """Ligne verticale coupée à chaque dérivation, avec un point de jonction."""
    ys = sorted(set(ys))
    for a, b in zip(ys, ys[1:]):
        wire((x, a), (x, b))
    for y in ys[1:-1]:
        junctions.add((x, y))


def label(s, x, y, size=1.524, bold=True):
    b = " (bold yes)" if bold else ""
    items.append(f"(label {q(s)} (at {f(x)} {f(y)} 0) (effects (font (size {size} {size}){b}) "
                 f"(justify left bottom)) (uuid {q(uid())}))")


def text(s, x, y, size=1.27, bold=False):
    b = " (bold yes)" if bold else ""
    items.append(f"(text {q(s)} (exclude_from_sim no) (at {f(x)} {f(y)} 0) "
                 f"(effects (font (size {size} {size}){b}) (justify left bottom)) (uuid {q(uid())}))")


zlg = place(ZLG, "J1", UX, Y_L, ZLG_PINS,
            fields=[("Vendu comme", "(vendu comme MyActuator USBCAN-Z)", UX - 22.86, Y_L - 15.24),
                    ("Terminaison", "Term. 120 Ω : ON", UX - 22.86, Y_L + 16.51)],
            ref_at=(UX - 22.86, Y_L - 11.43))
pc = place(PC, "PC", PC_X0, Y_PC, PC_PINS, ref_at=(PC_X0 - PC_HALF, Y_PC - 8.89))

# Tous les liens sont des fils : aucun symbole de masse ni étiquette de raccourci. La
# masse de chaque nœud rejoint le conducteur GND du bus, commun avec le CAN-G du ZLG.
taps = {"H": [zlg["H"][0]], "L": [zlg["L"][0]], "G": [zlg["G"][0]]}
for i, tx in enumerate(TRX_X):
    n = i + 1
    ty = Y_TRX
    nx = tx + NUC_DX

    trx = place(TRX, f"U{n}", tx, ty, TRX_PINS, value="TJA1051T/3",
                fields=[("Montage", "SOP8-DIP8, vue de dessus", tx - 7.62, ty - 16.51)],
                ref_at=(tx - 7.62, ty - 21.59))
    nuc = place(NUC, f"N{n}", nx, Y_NUC, NUC_PINS,
                fields=[("Firmware", f"firmware : preset n{n}" if n < 4 else
                         "firmware : preset n4 à créer", nx, Y_NUC + 7.62, "centre"),
                        ("HW1", "HW1 retiré", nx, Y_NUC + 10.16, "centre")],
                ref_at=(nx - 37.47, Y_NUC - 13.97))
    xl_pin, r1 = trx["1"]
    r2, r3, r4 = trx["2"][1], trx["3"][1], trx["4"][1]
    xr_pin = trx["8"][0]
    y_top = nuc["CN4-5"][1]              # extrémité des broches du haut de la Nucleo

    # --- côté 1-4 : vers la Nucleo, sans croisement ---------------------------------
    a1, a2, a3, a4 = (nuc[k][0] for k in ("CN4-5", "CN4-4", "CN3-4", "CN4-13"))
    c23 = xl_pin - 5.08                  # condensateur entre 2 (GND) et 3 (VCC)
    wire((xl_pin, r1), (a1, r1), (a1, y_top))           # 1 TXD <- PA12
    line(r2, [a2, c23, xl_pin])                         # 2 GND
    vline(a2, [Y_G, r2, y_top])                         #   -> GND Nucleo et GND du bus
    line(r3, [a3, c23, xl_pin])                         # 3 VCC <- 5V
    wire((a3, r3), (a3, y_top))
    wire((xl_pin, r4), (a4, r4), (a4, y_top))           # 4 RXD -> PA11
    place_part("Device:C", f"C{2 * n - 1}", "100nF", c23, ty,
               texts=((c23 + 2.54, ty - 1.27), (c23 + 2.54, ty + 1.27)))
    taps["G"].append(a2)

    # --- côté 5-8 : bus, VIO et condensateur 5-8 -------------------------------------
    a5 = nuc["CN3-14"][0]                # 3V3, juste sous la broche 5
    xh, xlo = xr_pin + 10.16, xr_pin + 15.24
    c58 = xr_pin + 20.32                 # condensateur entre 5 (VIO) et 8 (S)
    line(r1, [xr_pin, c58])                             # 8 S
    vline(c58, [Y_G, r1, r2])                           #   -> GND du bus et C 5-8
    vline(c58, [r3, r4])
    line(r4, [xr_pin, a5, c58])                         # 5 VIO <- 3V3
    wire((a5, r4), (a5, y_top))
    place_part("Device:C", f"C{2 * n}", "100nF", c58, ty,
               texts=((c58 + 2.54, ty - 1.27), (c58 + 2.54, ty + 1.27)))
    taps["G"].append(c58)
    if n == 4:
        # Un des adaptateurs porte une 120 Ω entre 6 et 7 : monté sur N4, il termine
        # la ligne (extrémité 2).
        xr = xr_pin + 5.08
        line(r2, [xr_pin, xr, xh])                      # 7 CANH
        line(r3, [xr_pin, xr, xlo])                     # 6 CANL
        place_part("Device:R", "R1", "120R", xr, ty,
                   texts=((a5 + 3.81, r4 + 3.81), (a5 + 3.81, r4 + 6.35)),
                   fields=[("Montage", "soudée sur l'adaptateur U4", a5 + 3.81, r4 + 8.89),
                           ("Rôle", "terminaison fin de ligne", a5 + 3.81, r4 + 11.43)])
    else:
        wire((xr_pin, r2), (xh, r2))                    # 7 CANH
        wire((xr_pin, r3), (xlo, r3))                   # 6 CANL
    wire((xh, r2), (xh, Y_H))
    wire((xlo, r3), (xlo, Y_L))
    taps["H"].append(xh)
    taps["L"].append(xlo)

    # Nucleo -> PC
    wire(nuc["CN1"], pc[str(n + 1)])

# Bus : trois lignes, plus épaisses
for pin, y in (("H", Y_H), ("L", Y_L), ("G", Y_G)):
    line(y, taps[pin], width=0.4)
label("CAN_H", zlg["H"][0] + 2.54, Y_H)
label("CAN_L", zlg["L"][0] + 2.54, Y_L)
text("GND (masse commune du bus)", zlg["G"][0] + 12.7, Y_G - 0.8, 1.27, True)

# ZLG vers le PC
wire(zlg["USB"], pc["1"])

# --- textes ------------------------------------------------------------------------

text("G69 - CABLAGE DU BUS CAN : 4 NUCLEO-G431KB + 4 TJA1051T/3 SUR ADAPTATEUR SOP8, "
     "ZLG USBCAN-UC12, PC", 20.32, 22.86, 2.0, True)
text("Bus réel à 500 kbit/s : paire torsadée CAN_H / CAN_L + masse commune. Ordre physique "
     "sur la ligne : ZLG (120 Ω) - N1 - N2 - N3 - N4 (adaptateur avec 120 Ω).", 20.32, 27.94)
text("Dérivation de chaque nœud vers la ligne : la plus courte possible (≤ 0,3 m). "
     "Terminaisons aux deux extrémités seulement.", 20.32, 31.75)

columns = [
    (20.32, [
        ("AVANT LA PREMIÈRE MISE SOUS TENSION", True),
        ("1. Sur chaque Nucleo, retirer le cavalier HW1 (CN4-4 / CN4-5) :", False),
        ("   PA12 = FDCAN1_TX, laissé à la masse il bloque le bus en dominant.", False),
        ("2. Programmer les presets normaux n1 à n4 (TX push-pull).", False),
        ("   JAMAIS les presets *-direct quand un transceiver est câblé.", False),
        ("3. Ponts SB9/SB10 non soudés : compiler en HSI, aucun verdict.", False),
        ("4. Hors tension, entre CAN_H et CAN_L : mesurer environ 60 Ω.", False),
        ("   120 Ω : une terminaison manque ; < 40 Ω : une de trop.", False),
        ("5. VCC de chaque TJA1051T/3 sur 5 V (CN3-4), PAS sur 3V3.", False),
        ("", False),
        ("TERMINAISONS", True),
        ("ZLG : interrupteur 120 Ω sur ON (extrémité 1).", False),
        ("L'adaptateur SOP8 qui porte une 120 Ω (entre 6 et 7) va sur N4,", False),
        ("branché tout au bout de la ligne (extrémité 2). Aucune autre.", False),
    ]),
    (142.24, [
        ("TJA1051T/3 SUR ADAPTATEUR SOP8 - DIP8", True),
        ("TJA1051T/3/1J en SO8 (Farnell 2574963), soudé sur un adaptateur", False),
        ("SOP8 -> DIP8 (Gotronic) : broche n du DIP = broche n du SO8.", False),
        ("Dessin = adaptateur vu de dessus : 1 en face de 8, 4 en face de 5.", False),
        ("1 TXD <- PA12 | 2 GND | 3 VCC <- 5V | 4 RXD -> PA11", False),
        ("5 VIO <- 3V3 | 6 CANL | 7 CANH | 8 S -> GND (mode normal)", False),
        ("100 nF sur l'adaptateur, entre 2-3 (VCC) et entre 5-8 (VIO) :", False),
        ("8 (S) doit donc être relié à 2 (GND). CANH = 7 (voisine de 8).", False),
        ("Bon de commande : 3 adaptateurs pour 4 nœuds -> 1 de plus à prévoir.", False),
        ("", False),
        ("ALIMENTATION", True),
        ("Chaque Nucleo par son USB, via le hub alimenté HQM121C (bloc", False),
        ("PSS6EMV29). VIN non câblé. 5V (CN3-4) et 3V3 (CN3-14) de la", False),
        ("carte alimentent SON transceiver ; ne jamais relier les 5 V de", False),
        ("deux Nucleo entre eux.", False),
    ]),
    (264.16, [
        ("ZLG USBCAN-UC12 (USB 0471:1200)", True),
        ("Pilote WinUSB + pilote libre du dépôt (tools/zlg_usbcan) :", False),
        ("fonctionne avec l'intégrité de la mémoire activée.", False),
        ("Ne pas installer le pilote ZLG (usbcan.sys, refusé par Windows).", False),
    ]),
]
for x, notes in columns:
    for k, (s, bold) in enumerate(notes):
        if s:
            text(s, x, 210.82 + 3.81 * k, 1.27, bold)

text("Sources : bon de commande BC-2026-G69-001 ; UM2397 Rev 2 §6.4, Table 11 ; datasheet NXP "
     "TJA1051 ; docs/pinout.md §1, §5, §6 ; docs/bringup.md étape 4.", 20.32, 270.51)

# --- écriture ------------------------------------------------------------------------


def main():
    for x, y in sorted(junctions):
        items.append(f"(junction (at {f(x)} {f(y)}) (diameter 0) (color 0 0 0 0) (uuid {q(uid(f'j:{x}:{y}'))}))")
    lib = " ".join(LIB + [lib_text("Device:C"), lib_text("Device:R")])
    sch = (f"(kicad_sch (version 20250114) (generator \"eeschema\") (generator_version \"9.0\") "
           f"(uuid {q(ROOT)}) (paper \"A3\") "
           f"(title_block (title \"Câblage du bus CAN - banc G69\") (rev \"0.2\") (company \"ENSEA - Projet 2A\") "
           f"(comment 1 \"Généré par generate_cablage.py\") "
           f"(comment 2 \"4 Nucleo-G431KB, 4 TJA1051T/3 sur adaptateur SOP8, ZLG USBCAN-UC12\")) "
           f"(lib_symbols {lib}) {' '.join(items)} "
           f"(sheet_instances (path \"/\" (page \"1\"))) (embedded_fonts no))")
    out = HERE / f"{NAME}.kicad_sch"
    out.write_text(sch, encoding="utf-8")
    # Bibliothèque du projet : les mêmes blocs, pour éditer le schéma dans KiCad
    syms = " ".join(s.replace('(symbol "banc:', '(symbol "', 1) for s in LIB)
    (HERE / "banc.kicad_sym").write_text(
        f'(kicad_symbol_lib (version 20241209) (generator "generate_cablage") (generator_version "9.0") {syms})',
        encoding="utf-8")
    (HERE / "sym-lib-table").write_text(
        '(sym_lib_table (version 7)\n'
        '  (lib (name "banc")(type "KiCad")(uri "${KIPRJMOD}/banc.kicad_sym")(options "")'
        '(descr "Modules du banc CAN G69"))\n)\n',
        encoding="utf-8")
    pro = HERE / f"{NAME}.kicad_pro"
    if not pro.exists():
        pro.write_text('{"meta": {"filename": "%s.kicad_pro", "version": 3}}\n' % NAME, encoding="utf-8")
    subprocess.run([CLI, "sch", "export", "pdf", "-o", str(HERE / f"{NAME}.pdf"), str(out)], check=True,
                   capture_output=True)
    print(out.name, f"{NAME}.pdf")


if __name__ == "__main__":
    main()
