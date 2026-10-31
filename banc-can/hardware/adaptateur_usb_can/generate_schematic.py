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
from uuid import uuid4

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


def uid():
    return str(uuid4())


def q(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def f(v):
    return f"{round(v, 4):g}"


def prop(name, value, x, y, hide=False, justify=None):
    eff = "(font (size 1.27 1.27))"
    if justify:
        eff += f" (justify {justify})"
    if hide:
        eff += " (hide yes)"
    return f"(property {q(name)} {q(value)} (at {f(x)} {f(y)} 0) (effects {eff}))"


def place(lib_id, ref, value, x, y, footprint="", rot=0, text_side="below", props=()):
    """Pose un symbole ; renvoie {numéro: (x, y, direction_sortante)} en coordonnées schéma."""
    lib_ids.add(lib_id)
    sym = kisym.load(lib_id)
    pins = kisym.pins(sym)
    pts = {}
    for num, _name, _type, px, py, ang in pins:
        # Bibliothèque Y vers le haut, schéma Y vers le bas ; rotation anti-horaire.
        rx, ry, ra = px, py, ang
        for _ in range(rot // 90):
            rx, ry, ra = -ry, rx, (ra + 90) % 360
        out = {0: (-1, 0), 90: (0, 1), 180: (1, 0), 270: (0, -1)}[ra]
        pts[num] = (x + rx, y - ry, out)
    xs = [p[0] for p in pts.values()] or [x]
    ys = [p[1] for p in pts.values()] or [y]
    hidden = ref.startswith("#")
    if text_side == "right":
        tx, ty1, ty2, just = max(xs) + 1.27, y - 1.27, y + 1.27, "left"
    else:
        tx, ty1, ty2, just = x, max(ys) + 7.62, max(ys) + 10.16, None
    body = [
        prop("Reference", ref, tx, ty1, hidden, just),
        prop("Value", value, tx, ty2, hidden, just),
        prop("Footprint", footprint, x, y, True),
        prop("Datasheet", "", x, y, True),
    ]
    body += [prop(k, v, x, y, True) for k, v in props]
    pin_uuids = " ".join(f"(pin {q(n)} (uuid {q(uid())}))" for n in sorted(pts))
    items.append(
        f"(symbol (lib_id {q(lib_id)}) (at {f(x)} {f(y)} {rot}) (unit 1) "
        f"(exclude_from_sim no) (in_bom {'no' if hidden else 'yes'}) (on_board {'no' if hidden else 'yes'}) "
        f"(dnp no) (uuid {q(uid())}) {' '.join(body)} {pin_uuids} "
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


def connect(pts, nets):
    for num, net in nets.items():
        x, y, (dx, dy) = pts[num]
        if net is None:
            items.append(f"(no_connect (at {f(x)} {f(y)}) (uuid {q(uid())}))")
            continue
        ex, ey = x + dx * STUB, y + dy * STUB
        wire(x, y, ex, ey)
        if net in POWER:
            power(net, ex, ey, (dx, dy))
        else:
            angle = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}[(dx, dy)]
            just = "right" if angle in (180, 270) else "left"
            items.append(
                f"(label {q(net)} (at {f(ex)} {f(ey)} {angle}) "
                f"(effects (font (size 1.27 1.27)) (justify {just} bottom)) (uuid {q(uid())}))"
            )


def part(lib_id, ref, value, x, y, nets, footprint, **kw):
    connect(place(lib_id, ref, value, x, y, footprint, **kw), nets)


def r(ref, value, x, y, top, bottom):
    part("Device:R", ref, value, x, y, {"1": top, "2": bottom}, FP_R, text_side="right")


def c(ref, value, x, y, top, bottom="GND"):
    part("Device:C", ref, value, x, y, {"1": top, "2": bottom}, FP_C, text_side="right")


def pwr_flag(net, x, y):
    counters["#FLG"] += 1
    place("power:PWR_FLAG", f"#FLG{counters['#FLG']:02d}", "PWR_FLAG", x, y)
    wire(x, y, x, y + STUB)
    power(net, x, y + STUB, (0, 1))


def text(x, y, value, size=1.27):
    items.append(
        f"(text {q(value)} (exclude_from_sim no) (at {f(x)} {f(y)} 0) "
        f"(effects (font (size {size} {size})) (justify left bottom)) (uuid {q(uid())}))"
    )


# --- Titre --------------------------------------------------------------------------
text(20.32, 20.32, "G69 - ADAPTATEUR USB-CAN (remplace le CANable 2.0)", 2.0)
text(20.32, 25.4, "USB-B -> CH340C (UART 3,3 V) -> STM32G431KBT6 USART2 / FDCAN1 -> TJA1051T/3 -> DB9 CiA 303-1")
text(20.32, 29.21, "Règles factory ENSEA : 2 couches, piste 0,4 mm, isolation 0,3 mm, vias 0,8/0,4 mm, cuivre nu.")

# --- USB et alimentation ------------------------------------------------------------
text(20.32, 40.64, "1 - USB, PROTECTION ET ALIMENTATION", 1.5)
part("Connector:USB_B", "J1", "USB_B", 38.1, 60.96,
     {"1": "VBUS", "2": "USB_DM", "3": "USB_DP", "4": "GND", "5": "GND"},
     "Connector_USB:USB_B_OST_USB-B1HSxx_Horizontal")
part("Device:Polyfuse", "F1", "500mA", 63.5, 53.34, {"1": "VBUS", "2": "+5V"},
     "Fuse:Fuse_1206_3216Metric_Pad1.42x1.75mm_HandSolder", text_side="right")
part("Power_Protection:USBLC6-2SC6", "U5", "USBLC6-2SC6", 66.04, 83.82,
     {"1": "USB_DP", "6": "USB_DP", "3": "USB_DM", "4": "USB_DM", "2": "GND", "5": "+5V"},
     "Package_TO_SOT_SMD:SOT-23-6")
part("Regulator_Linear:AMS1117-3.3", "U4", "AMS1117-3.3", 106.68, 53.34,
     {"3": "+5V", "2": "+3V3", "1": "GND"}, "Package_TO_SOT_SMD:SOT-223-3_TabPin2")
c("C1", "10uF", 91.44, 71.12, "+5V")
c("C2", "22uF", 124.46, 71.12, "+3V3")
pwr_flag("+5V", 81.28, 45.72)
r("R1", "1k", 139.7, 53.34, "+3V3", "LED_PWR")
part("Device:LED", "D1", "PWR vert", 139.7, 83.82, {"2": "LED_PWR", "1": "GND"}, FP_LED, rot=90,
     text_side="right")

# --- Pont USB-série -----------------------------------------------------------------
text(20.32, 106.68, "2 - PONT USB-SÉRIE CH340C (mode 3,3 V : V3 relié à VCC par R2)", 1.5)
part("Interface_USB:CH340C", "U2", "CH340C", 63.5, 137.16,
     {"1": "GND", "2": "UART_RX", "3": "UART_TX", "4": "CH_V3", "5": "USB_DP", "6": "USB_DM",
      "7": None, "8": None, "9": None, "10": None, "11": None, "12": None, "13": None,
      "14": None, "15": None, "16": "+3V3"},
     "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm")
r("R2", "0R", 99.06, 124.46, "+3V3", "CH_V3")
c("C3", "100nF", 99.06, 147.32, "+3V3")
c("C4", "100nF", 114.3, 147.32, "CH_V3")

# --- Microcontrôleur ----------------------------------------------------------------
text(147.32, 40.64, "3 - STM32G431KBT6 (LQFP32, pas 0,8 mm)", 1.5)
part("MCU_ST_STM32G4:STM32G431KBTx", "U1", "STM32G431KBT6", 190.5, 104.14,
     {"1": "+3V3", "17": "+3V3", "15": "+3V3", "14": "GND", "16": "GND", "32": "GND",
      "2": "OSC_IN", "3": "OSC_OUT", "4": "NRST", "31": "BOOT0",
      "5": "LED_RX", "6": "LED_TX", "7": "UART_TX", "8": "UART_RX", "9": "CAN_S",
      "21": "CAN_RX", "22": "CAN_TX", "23": "SWDIO", "24": "SWCLK",
      "10": None, "11": None, "12": None, "13": None, "18": None, "19": None, "20": None,
      "25": None, "26": None, "27": None, "28": None, "29": None, "30": None},
     "Package_QFP:LQFP-32_7x7mm_P0.8mm")
c("C5", "100nF", 157.48, 63.5, "+3V3")
c("C6", "100nF", 167.64, 63.5, "+3V3")
c("C7", "100nF", 213.36, 63.5, "+3V3")
c("C8", "1uF", 223.52, 63.5, "+3V3")
c("C9", "4.7uF", 233.68, 63.5, "+3V3")
text(152.4, 50.8, "C5, C6 : VDD broches 1 et 17 ; C7, C8 : VDDA broche 15 ; C9 : réservoir 3,3 V")

part("Device:Crystal", "Y1", "8MHz", 149.86, 157.48, {"1": "OSC_IN", "2": "OSC_OUT"},
     "Crystal:Crystal_HC49-U_Vertical", text_side="below")
c("C10", "22pF", 139.7, 172.72, "OSC_IN")
c("C11", "22pF", 160.02, 172.72, "OSC_OUT")
text(129.54, 190.5, "Quartz 8 MHz propre à l'adaptateur, distinct des 24 MHz des Nucleo :")
text(129.54, 194.31, "référence d'horloge indépendante (bringup étape 6 bis). C10/C11 selon la CL du quartz.")

c("C12", "100nF", 182.88, 157.48, "NRST")
part("Switch:SW_Push", "SW1", "RESET", 182.88, 177.8, {"1": "NRST", "2": "GND"},
     "Button_Switch_THT:SW_PUSH_6mm")
r("R3", "10k", 210.82, 157.48, "BOOT0", "GND")
part("Switch:SW_Push", "SW2", "BOOT0", 210.82, 177.8, {"1": "+3V3", "2": "BOOT0"},
     "Button_Switch_THT:SW_PUSH_6mm")
text(129.54, 203.2, "BOOT0 maintenu + RESET : chargeur ST sur USART2 (PA2/PA3),")
text(129.54, 207.01, "programmation par le CH340 sans sonde (à confirmer dans AN2606).")

part("Connector_Generic:Conn_01x05", "J3", "SWD", 254.0, 165.1,
     {"1": "+3V3", "2": "SWCLK", "3": "GND", "4": "SWDIO", "5": "NRST"},
     "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical")
text(243.84, 186.69, "SWD : 3V3, SWCLK, GND, SWDIO, NRST")

r("R4", "1k", 254.0, 116.84, "LED_RX", "LED_RX_A")
part("Device:LED", "D2", "RX vert", 254.0, 147.32, {"2": "LED_RX_A", "1": "GND"}, FP_LED, rot=90,
     text_side="right")
r("R5", "1k", 269.24, 116.84, "LED_TX", "LED_TX_A")
part("Device:LED", "D3", "TX jaune", 269.24, 147.32, {"2": "LED_TX_A", "1": "GND"}, FP_LED, rot=90,
     text_side="right")

# --- Bus CAN ------------------------------------------------------------------------
text(292.1, 40.64, "4 - TRANSCEIVER ET CONNECTEUR CAN", 1.5)
part("Interface_CAN_LIN:TJA1051T-3", "U3", "TJA1051T/3", 325.12, 76.2,
     {"1": "CAN_TX", "4": "CAN_RX", "5": "+3V3", "8": "CAN_S", "3": "+5V", "2": "GND",
      "7": "CANH", "6": "CANL"},
     "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm")
c("C13", "100nF", 302.26, 53.34, "+5V")
c("C14", "100nF", 312.42, 53.34, "+3V3")
r("R6", "10k", 294.64, 101.6, "CAN_S", "GND")
text(279.4, 116.84, "R6 : S à la masse = mode normal ; PA4 à 1 = mode silencieux (écoute seule).")

r("R7", "120R", 360.68, 104.14, "CANH", "TERM")
part("Connector_Generic:Conn_01x02", "JP1", "TERM", 375.92, 121.92, {"1": "TERM", "2": "CANL"},
     "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")
text(330.2, 151.13, "JP1 fermé = terminaison 120 ohms (adaptateur en bout de bus).")

part("Connector:DE9_Pins", "J2", "DB9 mâle", 381.0, 76.2,
     {"2": "CANL", "3": "GND", "7": "CANH",
      "1": None, "4": None, "5": None, "6": None, "8": None, "9": None},
     "Connector_Dsub:DSUB-9_Pins_Horizontal_P2.77x2.84mm_EdgePinOffset7.70mm_Housed_MountingHolesOffset9.12mm")
text(330.2, 147.32, "Brochage CiA 303-1 comme J1 à J5 du banc : 2 CAN_L, 3 GND, 7 CAN_H.")

# --- Fixations ----------------------------------------------------------------------
place("Mechanical:MountingHole", "H1", "M3", 304.8, 177.8, "MountingHole:MountingHole_3.2mm_M3")
place("Mechanical:MountingHole", "H2", "M3", 320.04, 177.8, "MountingHole:MountingHole_3.2mm_M3")
text(294.64, 190.5, "Trous de fixation 3,2 mm (règle factory).")

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
