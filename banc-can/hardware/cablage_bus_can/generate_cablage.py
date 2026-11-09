"""Schéma de câblage du banc : 3 Nucleo-G431KB + 3 Adafruit CAN Pal, USBCAN-Z, alimentation.

    python generate_cablage.py

Écrit cablage_bus_can.kicad_sch (A3), puis cablage_bus_can.pdf avec kicad-cli. C'est un
schéma de câblage entre modules, pas une carte à fabriquer : les cartes du commerce sont
dessinées comme des blocs, avec les broches réellement utilisées.

Sources :
- NUCLEO-G431KB : UM2397 Rev 2, §6.4 (alimentation, Table 5 pour VIN, séquence de mise
  sous tension §6.4.1) et Table 11 (connecteurs CN3/CN4) ;
- Adafruit CAN Pal (produit 5708) : learn.adafruit.com/adafruit-can-pal, page « Pinouts »
  (Vcc 3 à 5 V, pompe de charge 5 V intégrée, SLNT haut = silencieux, bornier L/G/H,
  terminaison 2 × 60 Ω commutable) ;
- MyActuator USBCAN-Z : marquage du boîtier (CAN-L, CAN-H, CAN-G, interrupteur 120 Ω) ;
  énumération USB relevée sur le banc (« USBCAN-UC12 », VID 0471 PID 1200, pilote ZLG) ;
- docs/pinout.md : affectation FDCAN1 (PA12 TX, PA11 RX), HW1, topologie et terminaisons.
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
# Broche : (nom, numéro, x, y, angle) en coordonnées de bibliothèque (y vers le haut) ;
# (x, y) est l'extrémité de connexion, l'angle la direction vers le corps.

VALUE_AT = {}  # position du nom du module dans son cadre, reprise à chaque pose


def pin_length(rect, x, y, a):
    """Longueur de broche jusqu'au bord du cadre, du côté où elle sort."""
    (x0, y0), (x1, y1) = rect
    return {270: y - y0, 90: y1 - y, 180: x - x1, 0: x0 - x}[a]


def module_symbol(name, rect, pins, ref, value_at, show_numbers=True, extra=""):
    (x0, y0), (x1, y1) = rect
    VALUE_AT[name] = value_at
    body = "".join(
        f"(pin passive line (at {f(x)} {f(y)} {a}) (length {f(pin_length(rect, x, y, a))}) "
        f"(name {q(n)} {FONT}) (number {q(num)} {FONT}))"
        for n, num, x, y, a in pins)
    return (
        f"(symbol {q('banc:' + name)} (pin_names (offset 1.016)) "
        + ("" if show_numbers else "(pin_numbers (hide yes)) ")
        + "(exclude_from_sim yes) (in_bom no) (on_board no) "
        f"(property \"Reference\" {q(ref)} (at {f(x0)} {f(y0 + 1.27)} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) "
        f"(property \"Value\" {q(name)} (at {f(value_at[0])} {f(value_at[1])} 0) (effects (font (size 1.524 1.524) (bold yes)))) "
        f"(property \"Footprint\" \"\" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes))) "
        f"(property \"Datasheet\" \"\" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes))) "
        f"(symbol {q(name + '_0_1')} (rectangle (start {f(x0)} {f(y0)}) (end {f(x1)} {f(y1)}) "
        f"(stroke (width 0.254) (type default)) (fill (type background))) {extra})"
        f"(symbol {q(name + '_1_1')} {body}))"
    )


NUC = "NUCLEO-G431KB"
NUC_PINS = [
    ("3V3", "CN3-14", -7.62, 25.4, 270),
    ("GND", "CN3-2", -2.54, 25.4, 270),
    ("RX/PA11/D10", "CN4-13", 2.54, 25.4, 270),
    ("TX/PA12/D2", "CN4-5", 7.62, 25.4, 270),
    ("VIN", "CN3-1", -7.62, -25.4, 90),
    ("GND", "CN4-4", -2.54, -25.4, 90),
    ("USB/ST-LINK", "CN1", 7.62, -25.4, 90),
]
PAL = "Adafruit CAN Pal"
PAL_PINS = [(n, str(i + 1), -15.24 + 5.08 * i, -12.7, 90)
            for i, n in enumerate(["Vcc", "GND", "RX", "TX", "SLNT", "CANH", "CANL"])]
PAL_PINS += [("L", "L", -5.08, 12.7, 270), ("G", "G", 0, 12.7, 270), ("H", "H", 5.08, 12.7, 270)]
USBZ = "MyActuator USBCAN-Z"
USBZ_PINS = [("CAN-H", "H", 17.78, 7.62, 180), ("CAN-L", "L", 17.78, 0, 180),
             ("CAN-G", "G", 17.78, -7.62, 180), ("USB", "USB", 0, -15.24, 90)]
PSU = "Alim. FI 1233 - CH1"
PSU_PINS = [("CH1+", "+", -17.78, 5.08, 0), ("CH1-", "-", -17.78, -2.54, 0)]
PC = "PC (ou hub USB alimente)"
PC_X0 = 160.02
UX = 40.64  # USBCAN-Z, à gauche du bus
PC_PINS = [("USB", str(i + 1), x - PC_X0, 12.7, 270) for i, x in enumerate((UX, 114.3, 198.12, 281.94))]

LIB = [
    module_symbol(NUC, ((-15.24, 17.78), (15.24, -17.78)), NUC_PINS, "N", (0, 0)),
    module_symbol(PAL, ((-20.32, 10.16), (20.32, -10.16)), PAL_PINS, "U", (0, 2.54), show_numbers=False),
    module_symbol(USBZ, ((-22.86, 10.16), (12.7, -10.16)), USBZ_PINS, "J", (-5.08, 3.81), show_numbers=False),
    module_symbol(PSU, ((-12.7, 7.62), (20.32, -5.08)), PSU_PINS, "PS", (3.81, 1.27), show_numbers=False),
    module_symbol(PC, ((-139.7, 7.62), (139.7, -7.62)), PC_PINS, "PC", (0, -2.54), show_numbers=False),
]

# --- instances, fils, textes -----------------------------------------------------

items = []
junctions = set()


def place(lib, ref, x, y, pins, fields=(), ref_at=None):
    """Pose un module ; renvoie {nom de broche ou numéro: (x, y) sur la feuille}."""
    rx, ry = ref_at or (x, y)
    vx, vy = VALUE_AT[lib]
    props = (f"(property \"Reference\" {q(ref)} (at {f(rx)} {f(ry)} 0) (effects (font (size 1.524 1.524) (bold yes)) (justify left bottom))) "
             f"(property \"Value\" {q(lib)} (at {f(x + vx)} {f(y - vy)} 0) (effects (font (size 1.524 1.524) (bold yes)))) "
             f"(property \"Footprint\" \"\" (at {f(x)} {f(y)} 0) (effects (font (size 1.27 1.27)) (hide yes))) "
             f"(property \"Datasheet\" \"\" (at {f(x)} {f(y)} 0) (effects (font (size 1.27 1.27)) (hide yes))) ")
    for name, val, fx, fy, *centre in fields:
        just = "" if centre else " (justify left bottom)"
        props += f"(property {q(name)} {q(val)} (at {f(fx)} {f(fy)} 0) (effects (font (size 1.27 1.27)){just})) "
    pins_s = "".join(f"(pin {q(num)} (uuid {q(uid(f'{ref}:pin:{num}'))}))" for _, num, *_ in pins)
    items.append(
        f"(symbol (lib_id {q('banc:' + lib)}) (at {f(x)} {f(y)} 0) (unit 1) (exclude_from_sim yes) "
        f"(in_bom no) (on_board no) (dnp no) (uuid {q(uid('symbol:' + ref))}) {props}{pins_s} "
        f"(instances (project {q(NAME)} (path {q('/' + ROOT)} (reference {q(ref)}) (unit 1)))))")
    out = {}
    for name, num, px, py, _ in pins:
        out[num] = (round(x + px, 2), round(y - py, 2))
    return out


def lib_text(lib_id):
    return kisym.dump(kisym.load(lib_id))


_pwr = 0


def power(lib_id, x, y, value):
    global _pwr
    _pwr += 1
    ref = f"#PWR{_pwr:02d}" if lib_id == "power:GND" else f"#FLG{_pwr:02d}"
    items.append(
        f"(symbol (lib_id {q(lib_id)}) (at {f(x)} {f(y)} 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) "
        f"(uuid {q(uid('pwr:' + ref))}) "
        f"(property \"Reference\" {q(ref)} (at {f(x)} {f(y + 3.81)} 0) (effects (font (size 1.27 1.27)) (hide yes))) "
        f"(property \"Value\" {q(value)} (at {f(x)} {f(y + (3.81 if lib_id == 'power:GND' else -3.81))} 0) {FONT}) "
        f"(property \"Footprint\" \"\" (at {f(x)} {f(y)} 0) (effects (font (size 1.27 1.27)) (hide yes))) "
        f"(property \"Datasheet\" \"\" (at {f(x)} {f(y)} 0) (effects (font (size 1.27 1.27)) (hide yes))) "
        f"(pin \"1\" (uuid {q(uid('pwrpin:' + ref))})) "
        f"(instances (project {q(NAME)} (path {q('/' + ROOT)} (reference {q(ref)}) (unit 1)))))")


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


def junction(x, y):
    junctions.add((x, y))


def no_connect(x, y):
    items.append(f"(no_connect (at {f(x)} {f(y)}) (uuid {q(uid())}))")


def label(text, x, y):
    items.append(f"(label {q(text)} (at {f(x)} {f(y)} 0) (effects (font (size 1.524 1.524) (bold yes)) (justify left bottom)) (uuid {q(uid())}))")


def text(s, x, y, size=1.27, bold=False):
    b = " (bold yes)" if bold else ""
    items.append(f"(text {q(s)} (exclude_from_sim no) (at {f(x)} {f(y)} 0) "
                 f"(effects (font (size {size} {size}){b}) (justify left bottom)) (uuid {q(uid())}))")


# --- implantation ----------------------------------------------------------------

Y_H, Y_L, Y_G = 45.72, 53.34, 60.96       # lignes du bus
Y_PAL, Y_NUC = 88.9, 149.86               # CAN Pal et Nucleo
Y_VIN, Y_GND = 190.5, 198.12              # rails d'alimentation
NODES = [("N1", 106.68, "OFF"), ("N2", 190.5, "OFF"), ("N3", 274.32, "ON (extrémité)")]

usbz = place(USBZ, "J1", UX, 53.34, USBZ_PINS,
             fields=[("Terminaison", "Term. 120 Ω : ON", UX - 22.86, 69.85)],
             ref_at=(UX - 22.86, 41.91))
pc = place(PC, "PC", PC_X0, 241.3, PC_PINS, ref_at=(20.32, 232.41))
psu = place(PSU, "PS1", 355.6, 195.58, PSU_PINS, ref_at=(342.9, 186.69))

taps = {"H": [usbz["H"][0]], "L": [usbz["L"][0]], "G": [usbz["G"][0]]}
vin_x, gnd_x = [], []
for i, (ref, nx, term) in enumerate(NODES):
    px = nx + 7.62
    pal = place(PAL, f"U{i + 1}", px, Y_PAL, PAL_PINS,
                fields=[("Terminaison", f"Terminaison : {term}", px, Y_PAL + 1.27, "centre")],
                ref_at=(px - 20.32, Y_PAL - 11.43))
    nuc = place(NUC, ref, nx, Y_NUC, NUC_PINS,
                fields=[("Firmware", f"firmware : preset n{i + 1}", nx + 16.51, Y_NUC + 2.54),
                        ("HW1", "HW1 retiré", nx + 16.51, Y_NUC + 6.35)],
                ref_at=(nx - 15.24, Y_NUC - 21.59))
    # Nucleo -> CAN Pal : 3V3, GND, RX, TX, fils droits
    for a, b in (("CN3-14", "1"), ("CN3-2", "2"), ("CN4-13", "3"), ("CN4-5", "4")):
        wire(nuc[a], pal[b])
    # SLNT à la masse : mode normal
    sx, sy = pal["5"]
    wire((sx, sy), (sx, sy + 5.08))
    power("power:GND", sx, sy + 5.08, "GND")
    # CANH / CANL de la barrette : déjà reliés au bornier sur la carte
    no_connect(*pal["6"])
    no_connect(*pal["7"])
    # Bornier vers le bus
    for pin, y in (("H", Y_H), ("L", Y_L), ("G", Y_G)):
        x, y0 = pal[pin]
        wire((x, y0), (x, y))
        taps[pin].append(x)
    # Alimentation et USB
    vx, vy = nuc["CN3-1"]
    wire((vx, vy), (vx, Y_VIN))
    vin_x.append(vx)
    gx, gy = nuc["CN4-4"]
    wire((gx, gy), (gx, Y_GND))
    gnd_x.append(gx)
    wire(nuc["CN1"], pc[str(i + 2)])

# Bus : trois lignes, plus épaisses
gx0 = usbz["G"][0] + 7.62
for pin, y in (("H", Y_H), ("L", Y_L)):
    line(y, taps[pin], width=0.4)
line(Y_G, taps["G"] + [gx0], width=0.4)
wire((gx0, Y_G), (gx0, Y_G + 5.08))
power("power:GND", gx0, Y_G + 5.08, "GND")
label("CAN_H", usbz["H"][0] + 2.54, Y_H)
label("CAN_L", usbz["L"][0] + 2.54, Y_L)
text("GND (masse commune du bus)", usbz["G"][0] + 12.7, Y_G - 0.8, 1.27, True)

# USBCAN-Z vers le PC
wire(usbz["USB"], pc["1"])

# Rails VIN et GND depuis l'alimentation (à droite)
line(Y_VIN, vin_x + [psu["+"][0]])
label("VIN_8V", vin_x[0] + 2.54, Y_VIN)
gpx = psu["-"][0] - 7.62
wire((gpx, Y_GND), (gpx, Y_GND + 5.08))
power("power:GND", gpx, Y_GND + 5.08, "GND")
power("power:PWR_FLAG", psu["-"][0] - 2.54, Y_GND, "PWR_FLAG")
junction(psu["-"][0] - 2.54, Y_GND)
line(Y_GND, gnd_x + [gpx, psu["-"][0] - 2.54, psu["-"][0]])

# --- textes ------------------------------------------------------------------------

text("G69 - CABLAGE DU BUS CAN : 3 NUCLEO-G431KB + ADAFRUIT CAN PAL, USBCAN-Z, ALIMENTATION", 20.32, 22.86, 2.0, True)
text("Bus réel à 500 kbit/s : paire torsadée CAN_H / CAN_L + masse commune. Ordre physique sur la ligne : USBCAN-Z - N1 - N2 - N3.", 20.32, 27.94)
text("Dérivation de chaque nœud vers la ligne : la plus courte possible (≤ 0,3 m). Terminaisons aux deux extrémités seulement.", 20.32, 31.75)

notes = [
    ("AVANT LA PREMIÈRE MISE SOUS TENSION", True),
    ("1. Sur chaque Nucleo, retirer le cavalier HW1 (CN4-4 / CN4-5) :", False),
    ("   PA12 = FDCAN1_TX, laissé à la masse il bloque le bus en dominant.", False),
    ("2. Programmer les presets normaux n1, n2, n3 (TX push-pull).", False),
    ("   JAMAIS les presets *-direct quand un transceiver est câblé.", False),
    ("3. Ponts SB9/SB10 non soudés : compiler en HSI, aucun verdict.", False),
    ("4. Hors tension, entre CAN_H et CAN_L : mesurer environ 60 Ω.", False),
    ("   120 Ω : une terminaison manque ; < 40 Ω : une de trop.", False),
    ("", False),
    ("TERMINAISONS (interrupteurs)", True),
    ("USBCAN-Z : ON. CAN Pal de N3 : ON. CAN Pal de N1 et N2 : OFF.", False),
    ("", False),
    ("ALIMENTATION FI 1233", True),
    ("Voie CH1 seule, mode INDEP. Régler 8,0 V et limiter à 1 A,", False),
    ("sortie coupée (OUTPUT OFF) pendant le câblage.", False),
    ("VIN = CN3-1 (7 à 12 V ; 450 mA par carte entre 7 et 9 V).", False),
    ("Ne pas relier la borne verte GND (terre) : CH1- = masse du banc.", False),
    ("Ordre (UM2397 §6.4.1) : OUTPUT ON, vérifier LD4 verte allumée", False),
    ("sur chaque Nucleo, PUIS brancher les câbles USB.", False),
    ("Sans l'alimentation : chaque Nucleo sur son USB, VIN non câblé.", False),
    ("", False),
    ("CAN PAL (Adafruit 5708)", True),
    ("Vcc sur le 3V3 de la Nucleo : la pompe de charge de la carte", False),
    ("fabrique le 5 V du TJA1051T/3. SLNT à GND = mode normal.", False),
    ("CANH/CANL de la barrette = bornier L/H : on câble le bornier.", False),
    ("", False),
    ("USBCAN-Z", True),
    ("Clone ZLG USBCAN-I (USB 0471:1200), pilote propriétaire ZLG :", False),
    ("ZCANPRO ou pc/moniteur_dialogue.py. Ni slcan ni gs_usb.", False),
]
for k, (s, bold) in enumerate(notes):
    if s:
        text(s, 320.04, 45.72 + 3.81 * k, 1.27, bold)

text("Sources : UM2397 Rev 2 §6.4, Tables 5 et 11 ; learn.adafruit.com/adafruit-can-pal ; docs/pinout.md §1, §5, §6.", 20.32, 260.35)

# --- écriture ------------------------------------------------------------------------


def main():
    for x, y in sorted(junctions):
        items.append(f"(junction (at {f(x)} {f(y)}) (diameter 0) (color 0 0 0 0) (uuid {q(uid(f'j:{x}:{y}'))}))")
    lib = " ".join(LIB + [lib_text("power:GND"), lib_text("power:PWR_FLAG")])
    sch = (f"(kicad_sch (version 20250114) (generator \"eeschema\") (generator_version \"9.0\") "
           f"(uuid {q(ROOT)}) (paper \"A3\") "
           f"(title_block (title \"Câblage du bus CAN - banc G69\") (rev \"0.1\") (company \"ENSEA - Projet 2A\") "
           f"(comment 1 \"Généré par generate_cablage.py\")) "
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
