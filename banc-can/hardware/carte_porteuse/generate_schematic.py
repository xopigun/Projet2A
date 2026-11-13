"""Génère carte_porteuse.kicad_sch : carte porteuse d'un nœud du banc CAN G69.

Une Nucleo-G431KB s'enfiche dessus. La carte porte le transceiver TJA1051T/3 (soudé, SO8)
et ses découplages, deux borniers pour chaîner le bus d'un nœud au suivant, la terminaison
de 120 ohms sur cavalier, les barrettes de l'écran OLED et du MPU-6050, et les LED d'état.
Une seule carte, fabriquée en quatre exemplaires (N1 à N4) : plus aucun fil Dupont.

Brochage de la Nucleo : docs/pinout.md et UM2397 Rev 2, Table 11. Broche 1 de CN3 et de CN4
côté USB.

Relancer après modification :  python generate_schematic.py
"""

import sys
from pathlib import Path
from uuid import UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "adaptateur_usb_can"))
import kisym  # noqa: E402

OUT = Path(__file__).with_name("carte_porteuse.kicad_sch")
PROJECT = "carte_porteuse"
ROOT = "9c2e4f1a-7b3d-4e8a-b6c5-1d2f3a4b5c6e"
STUB = 2.54
POWER = {"GND": "power:GND", "+3V3": "power:+3V3", "+5V": "power:+5V"}

FP_R = "Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder"
FP_C = "Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder"
FP_LED = "LED_SMD:LED_0805_2012Metric_Pad1.15x1.40mm_HandSolder"
FP_SOCK = "Connector_PinSocket_2.54mm:PinSocket_1x{:02d}_P2.54mm_Vertical"
FP_BORNIER = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal"

# Valeur -> (fabricant, référence fabricant, datasheet). Vide : datasheet de la bibliothèque.
# Passifs : références courantes, tout équivalent de même valeur convient.
PIECES = {
    "TJA1051T/3": ("NXP", "TJA1051T/3,118", ""),
    "100nF": ("Samsung", "CL21B104KBCNNNC", ""),
    "120R": ("Yageo", "RC0805FR-07120RL", ""),
    "1k": ("Yageo", "RC0805FR-071KL", ""),
    "4.7k": ("Yageo", "RC0805FR-074K7L", ""),
    "0R": ("Yageo", "RC0805JR-070RL", ""),
    "ERR rouge": ("Würth Elektronik", "150080RS75000", ""),
    "BUS-OFF jaune": ("Würth Elektronik", "150080YS75000", ""),
    "Nucleo CN3": ("au choix", "barrette femelle 1 x 15, pas 2,54 mm", ""),
    "Nucleo CN4": ("au choix", "barrette femelle 1 x 15, pas 2,54 mm", ""),
    "Bus entrée": ("Phoenix Contact", "1729131 (MKDS 1,5/ 3-5,08)", ""),
    "Bus sortie": ("Phoenix Contact", "1729131 (MKDS 1,5/ 3-5,08)", ""),
    "OLED": ("au choix", "barrette femelle 1 x 4, pas 2,54 mm", ""),
    "MPU-6050": ("au choix", "barrette femelle 1 x 8, pas 2,54 mm", ""),
    "TERM": ("Würth Elektronik", "61300211121", ""),
    "Hall": ("au choix", "barrette femelle 1 x 3, pas 2,54 mm", ""),
    "1-Wire": ("au choix", "barrette femelle 1 x 3, pas 2,54 mm", ""),
}

items = []
lib_ids = set()
counters = {"#PWR": 0, "#FLG": 0}

def uid(key=None):
    # UUID déterministes : un symbole garde le sien d'une génération à l'autre, ce qui
    # préserve son lien avec l'empreinte du PCB (chemin /<uuid du symbole>).
    counters["uuid"] = counters.get("uuid", 0) + 1
    return str(uuid5(UUID(ROOT), key or f"item{counters['uuid']}"))


def q(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def f(v):
    return f"{round(v, 4):g}"


def prop(name, value, x, y, hide=False, justify=None, angle=0):
    eff = "(font (size 1.27 1.27))"
    if justify:
        eff += f" (justify {justify})"
    if hide:
        eff += " (hide yes)"
    return f"(property {q(name)} {q(value)} (at {f(x)} {f(y)} {angle}) (effects {eff}))"


def place(lib_id, ref, value, x, y, footprint="", rot=0, text_side="below", props=(),
          gap=1.27, text_at=None, dnp=False):
    """Pose un symbole ; renvoie {numéro: (x, y, direction_sortante)} en coordonnées schéma."""
    lib_ids.add(lib_id)
    sym = kisym.load(lib_id)
    pins = kisym.pins(sym)
    pts = {}
    for num, _name, ptype, px, py, ang in pins:
        # Bibliothèque Y vers le haut, schéma Y vers le bas ; rotation anti-horaire.
        rx, ry, ra = px, py, ang
        for _ in range(rot // 90):
            rx, ry, ra = -ry, rx, (ra + 90) % 360
        out = {0: (-1, 0), 90: (0, 1), 180: (1, 0), 270: (0, -1)}[ra]
        pts[num] = (x + rx, y - ry, out, ptype)
    xs = [p[0] for p in pts.values()] or [x]
    ys = [p[1] for p in pts.values()] or [y]
    hidden = ref.startswith("#")
    if lib_id.startswith("power:"):
        # Tension affichée à l'emplacement prévu par la bibliothèque, tourné avec le symbole.
        at = next(p for p in kisym.find(sym, "property") if p[1] == "Value")
        vx, vy = float(kisym.first(at, "at")[1]), float(kisym.first(at, "at")[2])
        for _ in range(rot // 90):
            vx, vy = -vy, vx
        if rot in (90, 270):
            vx += 2.54 if vx > 0 else -2.54  # symbole couché : texte dégagé de la flèche
        tx, ty1, ty2, just = x + vx, y - vy, y - vy, None
    elif text_at:
        tx, ty1, ty2, just = *text_at, None
    elif text_side == "right":
        # gap : place pour le corps du symbole (flèches d'une LED, bouton) avant le texte.
        tx, ty1, ty2, just = max(xs) + gap, y - 1.27, y + 1.27, "left"
    else:
        # Sous le symbole d'alimentation éventuel (masse) accroché aux broches du bas.
        tx, ty1, ty2, just = x, max(ys) + 10.16, max(ys) + 12.7, None
    fab, mpn, datasheet = "", "", ""
    if not hidden and not lib_id.startswith("power:"):
        fab, mpn, datasheet = PIECES[value]
        if not datasheet:
            lib_ds = next((p[2] for p in kisym.find(sym, "property") if p[1] == "Datasheet"), "")
            datasheet = "" if lib_ds == "~" else lib_ds
    # KiCad oriente les champs avec le symbole : on compense pour qu'ils restent horizontaux.
    fa = 90 if rot in (90, 270) else 0
    if rot in (90, 180) and just:
        just = {"left": "right", "right": "left"}[just]  # KiCad retourne la justification
    body = [
        prop("Reference", ref, tx, ty1, hidden, just, fa),
        prop("Value", value, tx, ty2, hidden and not lib_id.startswith("power:"), just, fa),
        prop("Footprint", footprint, x, y, True),
        prop("Datasheet", datasheet, x, y, True),
    ]
    if fab:
        body += [prop("Manufacturer", fab, x, y, True), prop("MPN", mpn, x, y, True)]
    body += [prop(k, v, x, y, True) for k, v in props]
    pin_uuids = " ".join(f"(pin {q(n)} (uuid {q(uid())}))" for n in sorted(pts))
    items.append(
        f"(symbol (lib_id {q(lib_id)}) (at {f(x)} {f(y)} {rot}) (unit 1) "
        f"(exclude_from_sim no) (in_bom {'no' if hidden or dnp or ref.startswith('H') else 'yes'}) "
        f"(on_board {'no' if hidden else 'yes'}) "
        f"(dnp {'yes' if dnp else 'no'}) (uuid {q(uid('symbol:' + ref))}) {' '.join(body)} {pin_uuids} "
        f"(instances (project {q(PROJECT)} (path {q('/' + ROOT)} (reference {q(ref)}) (unit 1)))))"
    )
    return pts


def wire(x1, y1, x2, y2):
    items.append(
        f"(wire (pts (xy {f(x1)} {f(y1)}) (xy {f(x2)} {f(y2)})) "
        f"(stroke (width 0) (type default)) (uuid {q(uid())}))"
    )


def power(net, x, y, out):
    # Corps du symbole orienté dans le sens du fil sortant.
    if net == "GND":
        rot = {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}[out]
    else:
        rot = {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}[out]
    counters["#PWR"] += 1
    place(POWER[net], f"#PWR{counters['#PWR']:02d}", net, x, y, rot=rot)


# Forme des étiquettes globales selon le type électrique de la broche raccordée.
SHAPE = {"output": "output", "input": "input", "bidirectional": "bidirectional",
         "tri_state": "tri_state"}


WIRED = ""  # broche reliée par un fil tracé à part : ni étiquette ni croix


def glabel(net, x, y, angle, shape):
    just = "right" if angle in (180, 270) else "left"
    items.append(
        f"(global_label {q(net)} (shape {shape}) (at {f(x)} {f(y)} {angle}) "
        f"(fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify {just})) "
        f"(uuid {q(uid())}) (property \"Intersheetrefs\" \"${{INTERSHEET_REFS}}\" "
        f"(at {f(x)} {f(y)} 0) (effects (font (size 1.27 1.27)) (hide yes))))"
    )


def connect(pts, nets, dirs=None):
    for num, net in nets.items():
        x, y, (dx, dy), ptype = pts[num]
        if net == WIRED:
            continue
        if net is None:
            items.append(f"(no_connect (at {f(x)} {f(y)}) (uuid {q(uid())}))")
            continue
        ex, ey = x + dx * STUB, y + dy * STUB
        wire(x, y, ex, ey)
        if net in POWER:
            power(net, ex, ey, (dx, dy))
        else:
            angle = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}[(dx, dy)]
            glabel(net, ex, ey, angle, (dirs or {}).get(num) or SHAPE.get(ptype, "passive"))


def part(lib_id, ref, value, x, y, nets, footprint, dirs=None, **kw):
    pts = place(lib_id, ref, value, x, y, footprint, **kw)
    connect(pts, nets, dirs)
    return pts


def r(ref, value, x, y, top=WIRED, bottom=WIRED, rot=0):
    return part("Device:R", ref, value, x, y, {"1": top, "2": bottom}, FP_R, rot=rot,
                text_side="right")


def c(ref, value, x, y, top=WIRED, bottom="GND"):
    return part("Device:C", ref, value, x, y, {"1": top, "2": bottom}, FP_C, text_side="right")


def at(pts, num):
    return pts[num][:2]


def path(*points):
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        wire(x1, y1, x2, y2)


def dot(x, y):
    items.append(f"(junction (at {f(x)} {f(y)}) (diameter 0) (color 0 0 0 0) (uuid {q(uid())}))")


def name(net, x, y, angle=0):
    """Nom de net posé sur un fil (étiquette locale, simple texte).

    Deux étiquettes locales de même nom sont reliées : angle=180 écrit le nom à gauche du point.
    """
    just = "right" if angle == 180 else "left"
    items.append(
        f"(label {q(net)} (at {f(x)} {f(y)} {angle}) (effects (font (size 1.27 1.27)) "
        f"(justify {just} bottom)) (uuid {q(uid())}))"
    )


def flag(x, y):
    counters["#FLG"] += 1
    place("power:PWR_FLAG", f"#FLG{counters['#FLG']:02d}", "PWR_FLAG", x, y)


def text(x, y, value, size=1.27):
    items.append(
        f"(text {q(value)} (exclude_from_sim no) (at {f(x)} {f(y)} 0) "
        f"(effects (font (size {size} {size})) (justify left bottom)) (uuid {q(uid())}))"
    )



# =====================================================================================
#  Contenu de la carte
# =====================================================================================
text(20.32, 20.32, "G69 - CARTE PORTEUSE D'UN NOEUD DU BANC CAN (N1 a N4)", 2.0)
text(20.32, 25.4, "Nucleo-G431KB enfichee -> TJA1051T/3 -> bus chaine (bornier entree / sortie), "
     "OLED et MPU-6050 en I2C, LED d'etat")
text(20.32, 29.21, "Regles factory ENSEA : 2 couches, piste 0,4 mm, isolation 0,3 mm, vias 0,8/0,4 mm, "
     "cuivre nu. Composants marques DNP : prevus, non montes.")

# --- 1. Barrettes de la Nucleo --------------------------------------------------------
text(20.32, 40.64, "1 - NUCLEO-G431KB (UM2397 Table 11, broche 1 cote USB)", 1.5)
# CN3 : VIN, GND, NRST, +5V, A7..A0, AREF, +3V3, D13. Seules les broches utilisées sont
# reliées ; A4/A5 (CN3-7/8) doublent PA15/PB7 par SB2/SB3 sur la Nucleo : laissées libres.
part("Connector_Generic:Conn_01x15", "J3", "Nucleo CN3", 63.5, 76.2,
     {"1": None, "2": "GND", "3": None, "4": "+5V", "5": None, "6": "ONEWIRE", "7": None,
      "8": None, "9": "HALL", "10": None, "11": "LED_BOFF", "12": "LED_ERR", "13": None,
      "14": "+3V3", "15": None},
     FP_SOCK.format(15), text_side="right")
text(30.48, 101.6, "CN3 : 2 GND, 4 +5V, 6 PA7 (1-Wire), 9 PA4 (Hall), 11 PA1, 12 PA0, 14 +3V3")
# CN4 : D1, D0, NRST, GND, D2..D12.
part("Connector_Generic:Conn_01x15", "J4", "Nucleo CN4", 63.5, 134.62,
     {"1": None, "2": None, "3": None, "4": "GND", "5": "CAN_TX", "6": "MPU_INT",
      "7": "I2C_SDA", "8": "I2C_SCL", "9": "CAN_S", "10": None, "11": None, "12": None,
      "13": "CAN_RX", "14": None, "15": None},
     FP_SOCK.format(15), text_side="right")
text(30.48, 160.02, "CN4 : 4 GND, 5 PA12 TX, 6 PB0 INT, 7 PB7 SDA, 8 PA15 SCL, 9 PB6 S, 13 PA11 RX")
# La Nucleo alimente la carte par ses broches 5V et 3V3 (elle-même sur l'USB du hub).
for i, net in enumerate(("+5V", "+3V3", "GND")):
    x = 30.48 + i * 12.7
    power(net, x, 177.8, (0, -1) if net != "GND" else (0, 1))
    flag(x, 177.8)
text(30.48, 185.42, "Alimentation fournie par la Nucleo (USB du hub) : VIN non cable.")

# --- 2. Transceiver -------------------------------------------------------------------
text(127.0, 40.64, "2 - TRANSCEIVER TJA1051T/3 (SO8 soude)", 1.5)
U1 = part("Interface_CAN_LIN:TJA1051T-3", "U1", "TJA1051T/3", 160.02, 83.82,
          {"1": "CAN_TX", "4": "CAN_RX", "5": WIRED, "8": WIRED, "3": WIRED, "2": "GND",
           "7": WIRED, "6": WIRED},
          "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm")
path(at(U1, "3"), (160.02, 60.96), (175.26, 60.96))
dot(160.02, 60.96)
power("+5V", 160.02, 60.96, (0, -1))
c("C1", "100nF", 175.26, 64.77)
path(at(U1, "5"), (137.16, 86.36), (132.08, 86.36))
dot(137.16, 86.36)
power("+3V3", 132.08, 86.36, (-1, 0))
c("C2", "100nF", 137.16, 90.17)
# Broche S : à la masse par R7 (mode normal, monté) ; R8 la relie à PB6 si l'on veut piloter
# le mode silencieux du transceiver (le firmware utilise le mode moniteur du FDCAN).
path(at(U1, "8"), (144.78, 88.9), (144.78, 99.06))
glabel("TJA_S", 144.78, 99.06, 270, "passive")
r("R7", "0R", 127.0, 104.14, top="TJA_S", bottom="GND")
part("Device:R", "R8", "0R", 137.16, 104.14, {"1": "TJA_S", "2": "CAN_S"}, FP_R,
     text_side="right", dnp=True)
path(at(U1, "7"), (187.96, 81.28))
name("CANH", 187.96, 81.28)
path(at(U1, "6"), (177.8, 86.36), (177.8, 99.06), (187.96, 99.06))
name("CANL", 187.96, 99.06)
text(127.0, 116.84, "R7 monte : S a la masse, mode normal. R8 (DNP) : S sur PB6 a la place.")
text(127.0, 120.65, "C1, C2 : 100 nF au plus pres de VCC (5 V) et de VIO (3,3 V).")

# --- 3. Bus chaîné et terminaison -----------------------------------------------------
text(213.36, 40.64, "3 - BUS CHAINE ET TERMINAISON", 1.5)
for ref, val, y in (("J1", "Bus entrée", 76.2), ("J2", "Bus sortie", 106.68)):
    J = part("Connector:Screw_Terminal_01x03", ref, val, 266.7, y,
             {"1": "GND", "2": WIRED, "3": WIRED}, FP_BORNIER, text_side="right", gap=8.89)
    for net, num in (("CANL", "2"), ("CANH", "3")):
        x, yy = at(J, num)
        path((x - 15.24, yy), (x, yy))
        name(net, x - 15.24, yy, angle=180)
text(213.36, 124.46, "J1 et J2 en parallele : le bus traverse la carte (pas de derivation).")
text(213.36, 128.27, "Bornier : 1 GND, 2 CAN_L, 3 CAN_H ; sur la carte, de haut en bas H, L, G.")
# Terminaison : R1 entre CANH et J7 ; un cavalier sur J7 la relie à CANL. Sur N4, J7 est
# câblé à l'interrupteur SW1 (terminaison commutée R_T2 du dossier).
R1 = r("R1", "120R", 228.6, 147.32, top=WIRED, bottom="TERM_T")
path(at(R1, "1"), (228.6, 140.97))
name("CANH", 228.6, 140.97)
J7 = part("Connector_Generic:Conn_01x02", "J7", "TERM", 254.0, 147.32,
          {"1": "TERM_T", "2": WIRED},
          "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", text_side="right")
_x, _y = at(J7, "2")
path((_x, _y), (_x - 7.62, _y))
name("CANL", _x - 7.62, _y, angle=180)
text(213.36, 167.64, "J7 : cavalier = 120 ohms (noeud en bout de bus). N4 : J7 vers SW1.")

# --- 4. I2C : écran OLED et MPU-6050 --------------------------------------------------
text(127.0, 139.7, "4 - ECRAN OLED SSD1306 ET MPU-6050 (I2C1 : PA15 SCL, PB7 SDA)", 1.5)
part("Connector_Generic:Conn_01x04", "J5", "OLED", 160.02, 167.64,
     {"1": "OLED_1", "2": "OLED_2", "3": "I2C_SCL", "4": "I2C_SDA"}, FP_SOCK.format(4),
     text_side="right")
# Ordre GND / VCC : celui de la plupart des modules 0,96". R9 et R10 le câblent ; si le
# module reçu est en VCC / GND, monter R11 et R12 à la place (jamais les quatre).
r("R9", "0R", 205.74, 152.4, top="GND", bottom="OLED_1")
r("R10", "0R", 215.9, 152.4, top="+3V3", bottom="OLED_2")
part("Device:R", "R11", "0R", 205.74, 175.26, {"1": "+3V3", "2": "OLED_1"}, FP_R,
     text_side="right", dnp=True)
part("Device:R", "R12", "0R", 215.9, 175.26, {"1": "GND", "2": "OLED_2"}, FP_R,
     text_side="right", dnp=True)
part("Connector_Generic:Conn_01x08", "J6", "MPU-6050", 160.02, 200.66,
     {"1": "+3V3", "2": "GND", "3": "I2C_SCL", "4": "I2C_SDA", "5": None, "6": None,
      "7": "GND", "8": "MPU_INT"}, FP_SOCK.format(8), text_side="right")
text(127.0, 220.98, "J6 (GY-521) : VCC GND SCL SDA XDA XCL AD0 INT ; AD0 a la masse = adresse 0x68.")
text(127.0, 224.79, "J5 : OLED 0x3C. Verifier l'ordre GND/VCC du module avant de monter R9-R12.")
# Tirages I2C : les modules OLED et GY-521 ont les leurs. R4 et R5 seulement si besoin.
for ref, net, x in (("R4", "I2C_SCL", 228.6), ("R5", "I2C_SDA", 238.76)):
    part("Device:R", ref, "4.7k", x, 200.66, {"1": "+3V3", "2": net}, FP_R,
         text_side="right", dnp=True)

# --- 5. LED d'état et capteurs reportés -----------------------------------------------
text(20.32, 200.66, "5 - LED D'ETAT ET CAPTEURS (Hall et 1-Wire reportes : non montes)", 1.5)
for ref_r, ref_d, value, net, x in (("R2", "D1", "ERR rouge", "LED_ERR", 30.48),
                                    ("R3", "D2", "BUS-OFF jaune", "LED_BOFF", 55.88)):
    R = r(ref_r, "1k", x, 215.9, top=net)
    D = part("Device:LED", ref_d, value, x, 226.06, {"2": WIRED, "1": "GND"}, FP_LED, rot=90,
             text_side="right", gap=3.81)
    path(at(R, "2"), at(D, "2"))
part("Connector_Generic:Conn_01x03", "J8", "Hall", 91.44, 220.98,
     {"1": "+3V3", "2": "GND", "3": "HALL"}, FP_SOCK.format(3), text_side="right", dnp=True)
part("Connector_Generic:Conn_01x03", "J9", "1-Wire", 91.44, 246.38,
     {"1": "+3V3", "2": "GND", "3": "ONEWIRE"}, FP_SOCK.format(3), text_side="right", dnp=True)
part("Device:R", "R6", "4.7k", 111.76, 246.38, {"1": "+3V3", "2": "ONEWIRE"}, FP_R,
     text_side="right", dnp=True)
text(20.32, 260.35, "J8 : DRV5013, sortie a drain ouvert (tirage interne de PA4). J9 : DS18B20, R6 = tirage 4,7 k.")

lib = " ".join(kisym.dump(kisym.load(l)) for l in sorted(lib_ids))
OUT.write_text(
    "(kicad_sch (version 20250114) (generator \"eeschema\") (generator_version \"9.0\") "
    f"(uuid {q(ROOT)}) (paper \"A3\") "
    "(title_block (title \"Carte porteuse - banc CAN G69\") (rev \"0.1\") "
    "(company \"ENSEA - Projet 2A\") (comment 1 \"Genere par generate_schematic.py\")) "
    f"(lib_symbols {lib}) {' '.join(items)} "
    "(sheet_instances (path \"/\" (page \"1\"))) (embedded_fonts no))\n",
    encoding="utf-8",
)
print(f"{OUT.name} : {len(items)} elements")
