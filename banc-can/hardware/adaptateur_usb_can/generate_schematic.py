"""Génère adaptateur_usb_can.kicad_sch : adaptateur USB-CAN fabricable à la factory ENSEA.

Remplace le CANable 2.0 introuvable (ticket GLPI 0015779). Le LQFP48 au pas de 0,5 mm du
CANable ne respecte pas l'isolation de 0,3 mm de la factory ; on passe donc au LQFP32 au
pas de 0,8 mm. En 32 broches, l'USB et le FDCAN1 se partagent PA11/PA12 (PB9 n'existe
pas), d'où le pont USB-série CH340C et le protocole slcan sur USART2.

Chaque broche reçoit un court fil terminé par une étiquette de net, un symbole
d'alimentation ou une croix de non-connexion : les liaisons se lisent dans la table NETS.

Relancer après modification :  python generate_schematic.py
"""

from pathlib import Path
from uuid import UUID, uuid5

import kisym

OUT = Path(__file__).with_name("adaptateur_usb_can.kicad_sch")
PROJECT = "adaptateur_usb_can"
ROOT = "6f1c2a3e-4b5d-4e6f-8a9b-0c1d2e3f4a5b"
STUB = 2.54
POWER = {"GND": "power:GND", "+3V3": "power:+3V3", "+5V": "power:+5V"}

FP_R = "Resistor_SMD:R_1206_3216Metric_Pad1.30x1.75mm_HandSolder"
FP_C = "Capacitor_SMD:C_1206_3216Metric_Pad1.33x1.80mm_HandSolder"
FP_LED = "LED_SMD:LED_1206_3216Metric_Pad1.42x1.75mm_HandSolder"

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
          gap=1.27, text_at=None):
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
    # KiCad oriente les champs avec le symbole : on compense pour qu'ils restent horizontaux.
    fa = 90 if rot in (90, 270) else 0
    if rot in (90, 180) and just:
        just = {"left": "right", "right": "left"}[just]  # KiCad retourne la justification
    body = [
        prop("Reference", ref, tx, ty1, hidden, just, fa),
        prop("Value", value, tx, ty2, hidden and not lib_id.startswith("power:"), just, fa),
        prop("Footprint", footprint, x, y, True),
        prop("Datasheet", "", x, y, True),
    ]
    body += [prop(k, v, x, y, True) for k, v in props]
    pin_uuids = " ".join(f"(pin {q(n)} (uuid {q(uid())}))" for n in sorted(pts))
    items.append(
        f"(symbol (lib_id {q(lib_id)}) (at {f(x)} {f(y)} {rot}) (unit 1) "
        f"(exclude_from_sim no) (in_bom {'no' if hidden or ref.startswith('H') else 'yes'}) "
        f"(on_board {'no' if hidden else 'yes'}) "
        f"(dnp no) (uuid {q(uid('symbol:' + ref))}) {' '.join(body)} {pin_uuids} "
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


# --- Titre --------------------------------------------------------------------------
text(20.32, 20.32, "G69 - ADAPTATEUR USB-CAN (remplace le CANable 2.0)", 2.0)
text(20.32, 25.4, "USB-B -> CH340C (UART 3,3 V) -> STM32G431KBT6 USART2 / FDCAN1 -> TJA1051T/3 -> bornier CAN_H / CAN_L / GND")
text(20.32, 29.21, "Règles factory ENSEA : 2 couches, piste 0,4 mm, isolation 0,3 mm, vias 0,8/0,4 mm, cuivre nu.")

# --- USB et alimentation ------------------------------------------------------------
text(20.32, 40.64, "1 - USB, PROTECTION ET ALIMENTATION", 1.5)
J1 = part("Connector:USB_B", "J1", "USB_B", 35.56, 63.5,
          {"1": WIRED, "2": "USB_DM", "3": "USB_DP", "4": "GND", "5": WIRED},
          "Connector_USB:USB_B_OST_USB-B1HSxx_Horizontal")
F1 = part("Device:Polyfuse", "F1", "500mA", 53.34, 58.42, {"1": WIRED, "2": WIRED},
          "Fuse:Fuse_1206_3216Metric_Pad1.42x1.75mm_HandSolder", rot=90, text_at=(53.34, 52.07, 54.61))
path(at(J1, "1"), at(F1, "1"))
path(at(J1, "5"), at(J1, "4"))
name("VBUS", *at(J1, "1"))
# Rail +5 V : F1 vers U5 (VBUS), C1 et le régulateur
path(at(F1, "2"), (63.5, 58.42), (68.58, 58.42), (76.2, 58.42), (83.82, 58.42), (91.44, 58.42))
for x in (63.5, 68.58, 76.2, 83.82):
    dot(x, 58.42)
power("+5V", 63.5, 58.42, (0, -1))
flag(83.82, 58.42)
U5 = part("Power_Protection:USBLC6-2SC6", "U5", "USBLC6-2SC6", 68.58, 76.2,
          {"1": "USB_DP", "6": "USB_DP", "3": "USB_DM", "4": "USB_DM", "2": "GND", "5": WIRED},
          "Package_TO_SOT_SMD:SOT-23-6")
path((68.58, 58.42), at(U5, "5"))
c("C1", "10uF", 76.2, 62.23)
part("Regulator_Linear:AMS1117-3.3", "U4", "AMS1117-3.3", 99.06, 58.42,
     {"3": WIRED, "2": WIRED, "1": "GND"}, "Package_TO_SOT_SMD:SOT-223-3_TabPin2")
# Rail +3,3 V : régulateur vers C2 et la LED témoin
path((106.68, 58.42), (114.3, 58.42), (121.92, 58.42), (129.54, 58.42))
dot(114.3, 58.42)
dot(121.92, 58.42)
power("+3V3", 121.92, 58.42, (0, -1))
# Datasheet AMS1117 (« Stability ») : 22 µF tantale solide en sortie pour la stabilité.
part("Device:C_Polarized", "C2", "22uF", 114.3, 62.23, {"1": WIRED, "2": "GND"},
     "Capacitor_Tantalum_SMD:CP_EIA-3216-18_Kemet-A_HandSolder", text_side="right")
R1 = r("R1", "1k", 129.54, 62.23)
D1 = part("Device:LED", "D1", "PWR vert", 129.54, 72.39, {"2": WIRED, "1": "GND"}, FP_LED, rot=90,
          text_side="right", gap=3.81)
path(at(R1, "2"), at(D1, "2"))

# --- Pont USB-série -----------------------------------------------------------------
text(20.32, 106.68, "2 - PONT USB-SÉRIE CH340C (mode 3,3 V : V3 relié à VCC par R2)", 1.5)
U2 = part("Interface_USB:CH340C", "U2", "CH340C", 63.5, 157.48,
          {"1": "GND", "2": "UART_RX", "3": "UART_TX", "4": WIRED, "5": "USB_DP", "6": "USB_DM",
           "7": None, "8": None, "9": None, "10": None, "11": None, "12": None, "13": None,
           "14": None, "15": None, "16": WIRED},
          "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm")
path((45.72, 121.92), (53.34, 121.92), (60.96, 121.92), (68.58, 121.92))
dot(53.34, 121.92)
dot(60.96, 121.92)
power("+3V3", 45.72, 121.92, (0, -1))
c("C3", "100nF", 53.34, 125.73)
path((60.96, 121.92), at(U2, "16"))
R2 = r("R2", "0R", 68.58, 125.73)
path(at(R2, "2"), (68.58, 132.08), (93.98, 132.08))
path((68.58, 132.08), (63.5, 132.08), at(U2, "4"))
dot(68.58, 132.08)
name("CH_V3", 68.58, 132.08)
c("C4", "100nF", 93.98, 135.89)

# --- Microcontrôleur ----------------------------------------------------------------
text(147.32, 40.64, "3 - STM32G431KBT6 (LQFP32, pas 0,8 mm)", 1.5)
U1 = part("MCU_ST_STM32G4:STM32G431KBTx", "U1", "STM32G431KBT6", 190.5, 114.3,
          {"1": WIRED, "17": WIRED, "15": WIRED, "14": WIRED, "16": "GND", "32": WIRED,
           "2": WIRED, "3": WIRED, "4": WIRED, "31": WIRED, "9": WIRED,
           "5": "LED_RX", "6": "LED_TX", "7": "UART_TX", "8": "UART_RX",
           "21": "CAN_RX", "22": "CAN_TX", "23": "SWDIO", "24": "SWCLK",
           "10": None, "11": None, "12": None, "13": None, "18": None, "19": None, "20": None,
           "25": None, "26": None, "27": None, "28": None, "29": None, "30": None},
          "Package_QFP:LQFP-32_7x7mm_P0.8mm",
          # La bibliothèque déclare toutes les E/S bidirectionnelles : sens réel du firmware.
          dirs={"5": "output", "6": "output", "7": "output", "8": "input",
                "21": "input", "22": "output", "24": "input"})
path(at(U1, "14"), at(U1, "16"))  # VSSA rejoint VSS (16 et 32 sont superposées)
# Rail +3,3 V au-dessus du MCU, découplage au plus près des broches d'alimentation
rail = [152.4, 162.56, 172.72, 187.96, 190.5, 193.04, 203.2, 213.36, 223.52]
path(*[(x, 76.2) for x in rail])
for x in rail[1:-1]:
    dot(x, 76.2)
power("+3V3", 152.4, 76.2, (0, -1))
for num in ("1", "17", "15"):
    path((at(U1, num)[0], 76.2), at(U1, num))
for ref, value, x in (("C5", "100nF", 162.56), ("C6", "100nF", 172.72), ("C7", "10nF", 203.2),
                      ("C8", "1uF", 213.36), ("C9", "4.7uF", 223.52)):
    c(ref, value, x, 80.01)
text(147.32, 66.04, "DS12589 fig. 16 : VDD n x 100 nF + 4,7 uF (C5, C6, C9) ; VDDA 10 nF + 1 uF (C7, C8)")

# Reset : C12 et SW1 sur NRST, repris par le connecteur SWD
path(at(U1, "4"), (144.78, 93.98), (132.08, 93.98), (127.0, 93.98))
dot(144.78, 93.98)
dot(132.08, 93.98)
glabel("NRST", 127.0, 93.98, 180, "bidirectional")
c("C12", "100nF", 144.78, 97.79)
part("Switch:SW_Push", "SW1", "RESET", 132.08, 99.06, {"1": WIRED, "2": "GND"},
     "Button_Switch_THT:SW_PUSH_6mm", rot=270, text_side="right", gap=2.54)

# Quartz et capacités de charge
Y1 = part("Device:Crystal", "Y1", "8MHz", 160.02, 111.76, {"1": WIRED, "2": WIRED},
          "Crystal:Crystal_HC49-U_Vertical", text_at=(160.02, 104.14, 106.68))
path(at(U1, "2"), (156.21, 99.06), at(Y1, "1"), (151.13, 111.76))
name("OSC_IN", 156.21, 99.06)
path(at(U1, "3"), (163.83, 101.6), at(Y1, "2"), (168.91, 111.76))
name("OSC_OUT", 163.83, 101.6)
dot(*at(Y1, "1"))
dot(*at(Y1, "2"))
c("C10", "22pF", 151.13, 115.57)
c("C11", "22pF", 168.91, 115.57)

# BOOT0 : rappel à la masse R3, bouton SW2 vers 3,3 V
path(at(U1, "31"), (172.72, 121.92), (172.72, 137.16), (152.4, 137.16), (144.78, 137.16))
dot(152.4, 137.16)
name("BOOT0", 152.4, 137.16)
r("R3", "10k", 152.4, 140.97, bottom="GND")
part("Switch:SW_Push", "SW2", "BOOT0", 144.78, 132.08, {"1": "+3V3", "2": WIRED},
     "Button_Switch_THT:SW_PUSH_6mm", rot=270, text_side="right", gap=2.54)
text(129.54, 190.5, "Quartz 8 MHz propre à l'adaptateur, distinct des 24 MHz des Nucleo :")
text(129.54, 194.31, "référence d'horloge indépendante (bringup étape 6 bis). C10/C11 selon la CL du quartz.")
text(129.54, 203.2, "BOOT0 maintenu + RESET : chargeur ST sur USART2 (PA2/PA3),")
text(129.54, 207.01, "programmation par le CH340 sans sonde (à confirmer dans AN2606).")

# Mode silencieux du transceiver : R6 tient S à 0 (mode normal) tant que PA4 ne force rien
path(at(U1, "9"), (208.28, 104.14), (210.82, 104.14))
dot(208.28, 104.14)
glabel("CAN_S", 210.82, 104.14, 0, "output")
r("R6", "10k", 208.28, 107.95, bottom="GND")

# LED d'activité
for ref_r, ref_d, value, net, x in (("R4", "D2", "RX vert", "LED_RX", 226.06),
                                    ("R5", "D3", "TX jaune", "LED_TX", 241.3)):
    R = r(ref_r, "1k", x, 140.97, top=net)
    D = part("Device:LED", ref_d, value, x, 151.13, {"2": WIRED, "1": "GND"}, FP_LED, rot=90,
             text_side="right", gap=3.81)
    path(at(R, "2"), at(D, "2"))

part("Connector_Generic:Conn_01x05", "J3", "SWD", 269.24, 165.1,
     {"1": "+3V3", "2": "SWCLK", "3": "GND", "4": "SWDIO", "5": "NRST"},
     "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical")
text(256.54, 186.69, "SWD : 3V3, SWCLK, GND, SWDIO, NRST")

# --- Bus CAN ------------------------------------------------------------------------
text(281.94, 40.64, "4 - TRANSCEIVER ET CONNECTEUR CAN", 1.5)
U3 = part("Interface_CAN_LIN:TJA1051T-3", "U3", "TJA1051T/3", 309.88, 114.3,
          {"1": "CAN_TX", "4": "CAN_RX", "5": WIRED, "8": WIRED, "3": WIRED, "2": "GND",
           "7": WIRED, "6": WIRED},
          "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm")
path(at(U3, "3"), (309.88, 91.44), (325.12, 91.44))
dot(309.88, 91.44)
power("+5V", 309.88, 91.44, (0, -1))
c("C13", "100nF", 325.12, 95.25)
path(at(U3, "5"), (287.02, 116.84), (281.94, 116.84))
dot(287.02, 116.84)
power("+3V3", 281.94, 116.84, (-1, 0))
c("C14", "100nF", 287.02, 120.65)
path(at(U3, "8"), (294.64, 119.38), (294.64, 134.62))
glabel("CAN_S", 294.64, 134.62, 180, "input")

# Bus : bornier à vis 3 points et terminaison commutable R7 + JP1 entre CANH et CANL
path(at(U3, "7"), (337.82, 111.76))
name("CANH", *at(U3, "7"))
path(at(U3, "6"), (327.66, 116.84), (327.66, 129.54), (337.82, 129.54))
name("CANL", 327.66, 129.54)
# Broche 1 en bas sur la carte : de haut en bas H, L, G, comme le bornier de l'USBCAN-Z.
J2 = part("Connector:Screw_Terminal_01x03", "J2", "Bornier CAN", 375.92, 121.92,
          {"1": "GND", "2": WIRED, "3": WIRED},
          "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal",
          text_side="right", gap=8.89)
for net, num in (("CANL", "2"), ("CANH", "3")):
    x, y = at(J2, num)
    path((x - 15.24, y), (x, y))
    name(net, x - 15.24, y, angle=180)
r("R7", "120R", 337.82, 115.57)
part("Jumper:Jumper_2_Open", "JP1", "TERM", 337.82, 124.46, {"1": WIRED, "2": WIRED},
     "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", rot=270, text_side="right",
     gap=2.54)
text(281.94, 142.24, "R6 (près du MCU) : S à la masse = mode normal ; PA4 à 1 = mode silencieux.")
text(320.04, 147.32, "JP1 fermé = terminaison 120 ohms (adaptateur en bout de bus).")
text(320.04, 151.13, "J2 : bornier à vis 3 points, pas 5,08 mm. 1 GND, 2 CAN_L, 3 CAN_H.")
text(320.04, 154.94, "Sur la carte, de haut en bas : H, L, G, comme le bornier de l'USBCAN-Z.")

# --- Fixations ----------------------------------------------------------------------
place("Mechanical:MountingHole", "H1", "M3", 304.8, 177.8, "MountingHole:MountingHole_3.2mm_M3")
place("Mechanical:MountingHole", "H2", "M3", 320.04, 177.8, "MountingHole:MountingHole_3.2mm_M3")
text(294.64, 198.12, "Trous de fixation 3,2 mm (règle factory).")

lib = " ".join(kisym.dump(kisym.load(l)) for l in sorted(lib_ids))
OUT.write_text(
    "(kicad_sch (version 20250114) (generator \"eeschema\") (generator_version \"9.0\") "
    f"(uuid {q(ROOT)}) (paper \"A3\") "
    "(title_block (title \"Adaptateur USB-CAN - banc CAN G69\") (rev \"0.1\") "
    "(company \"ENSEA - Projet 2A\") (comment 1 \"Généré par generate_schematic.py\")) "
    f"(lib_symbols {lib}) {' '.join(items)} "
    "(sheet_instances (path \"/\" (page \"1\"))) (embedded_fonts no))\n",
    encoding="utf-8",
)
print(f"{OUT.name} : {len(items)} éléments")
