from pathlib import Path
from uuid import uuid4


OUT = Path(__file__).with_name("G69_Banc_CAN.kicad_sch")
items = []


def uid():
    return str(uuid4())


def text(x, y, value, size=1.15):
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    items.append(
        f'(text "{value}" (exclude_from_sim no) (at {x} {y} 0) '
        f'(effects (font (size {size} {size})) (justify left bottom)) (uuid "{uid()}"))'
    )


def rect(x1, y1, x2, y2):
    items.append(
        f'(rectangle (start {x1} {y1}) (end {x2} {y2}) '
        f'(stroke (width 0.35) (type default)) (fill (type none)) (uuid "{uid()}"))'
    )


def line(x1, y1, x2, y2):
    items.append(
        f'(polyline (pts (xy {x1} {y1}) (xy {x2} {y2})) '
        f'(stroke (width 0.5) (type default)) (fill (type none)) (uuid "{uid()}"))'
    )


text(12, 12, "G69-BANC-001  |  BANC DE TEST DU BUS CAN", 2.0)
text(12, 18, "Schéma fonctionnel de câblage  ·  CAN 2.0A classique  ·  500 kbit/s  ·  rév. 2026-09-29", 1.3)
line(12, 21, 408, 21)
text(12, 27, "1 — BUS ET NŒUDS  (paire principale, dérivations courtes ≤ 0,3 m ; longueur totale cible ≤ 5 m)", 1.35)

# CAN trunk, two end terminations, five DB9 drops and fault switches.
line(28, 119, 286, 119)
line(28, 133, 286, 133)
text(12, 118, "CAN_H", 1.0)
text(12, 133, "CAN_L", 1.0)
rect(25, 121, 31, 131)
text(25.7, 125, "RT1", 0.9)
text(25.7, 129, "120 Ω", 0.8)
line(28, 119, 28, 121)
line(28, 131, 28, 133)
line(286, 119, 286, 121)
rect(283, 121, 289, 126)
text(283.7, 124, "RT2", 0.8)
line(286, 126, 286, 133)
rect(277, 112, 295, 117)
text(278, 115, "SW1 · SPST", 0.85)
text(277, 108, "commute RT2", 0.8)

xs = [55, 105, 155, 205]
names = ["N1 · Nucleo-G431KB", "N2 · Nucleo-G431KB", "N3 · Nucleo-G431KB", "N4 · Blue Pill F103C8T6"]
maps = ["PA12→TXD · PA11←RXD"] * 3 + ["PB9→TXD · PB8←RXD"]
roles = ["TJA1051T/3 · nœud ARM/GO", "TJA1051T/3 · MPU6050 + Hall*", "TJA1051T/3 · DS18B20*", "TJA1051T/3 · nœud fautes"]
for i, x in enumerate(xs):
    rect(x - 19, 39, x + 19, 103)
    text(x - 17, 44, names[i], 0.96)
    line(x - 17, 47, x + 17, 47)
    text(x - 17, 52, "Carte + contrôleur CAN", 0.95)
    text(x - 17, 57, maps[i], 0.83)
    text(x - 17, 66, roles[i], 0.87)
    text(x - 17, 71, "+5 V → VCC · 3,3 V → VIO", 0.82)
    text(x - 17, 76, "GND commun · 2 × 100 nF", 0.82)
    text(x - 17, 81, "DB9 · 2 CAN_L · 3 GND · 7 CAN_H", 0.76)
    text(x - 17, 86, "LED TX intégrée · 2 LED défauts externes*", 0.76)
    rect(x - 10, 90, x + 10, 100)
    text(x - 8, 94, f"J{i + 1} · DB9", 0.88)
    text(x - 8, 98, "stub CAN", 0.75)
    line(x, 100, x, 119)
    line(x + 1, 100, x + 1, 133)

rect(235, 44, 270, 86)
text(237, 50, "CANable 2.0", 1.1)
text(237, 56, "Interface USB ↔ CAN", 0.88)
text(237, 63, "Capture / référence débit", 0.84)
text(237, 70, "USB vers PC BancCAN", 0.84)
rect(237, 90, 257, 100)
text(239, 94, "J5 · DB9", 0.9)
text(239, 98, "vers bus", 0.75)
line(247, 100, 247, 119)
line(248, 100, 248, 133)

rect(130, 141, 165, 155)
text(132, 146, "SW2 · SPST", 0.9)
text(132, 151, "court H ↔ L*", 0.82)
line(148, 133, 148, 141)
line(149, 133, 149, 141)
rect(180, 141, 226, 155)
text(182, 146, "SW3 · DPST", 0.9)
text(182, 151, "isole N4 sur H + L", 0.82)
text(12, 160, "J1…J5 : broche 2 = CAN_L · 3 = masse de référence · 7 = CAN_H · broche 9 (+5 V) optionnelle, usage à valider.", 0.88)

# PC and instruments.
rect(306, 28, 408, 107)
text(310, 34, "2 — PC, PROGRAMMATION ET MESURE", 1.2)
text(310, 41, "PC Windows · BancCAN / canbench", 0.9)
text(310, 47, "USB → CANable (capture / injection)", 0.86)
text(310, 53, "USB → N1–N3 (ST-LINK / port série)", 0.86)
text(310, 59, "N4 : USB pour alimentation de la carte", 0.86)
text(310, 65, "ST-LINK V2 → SWDIO, SWCLK, GND", 0.86)
text(310, 71, "USB-série 3,3 V : RX ← PA9, GND", 0.86)
text(310, 77, "Oscilloscope + sonde différentielle", 0.86)
text(310, 83, "Sonde entre CAN_H et CAN_L", 0.86)
text(310, 89, "Multimètre : continuité, ≈60 Ω hors tension", 0.86)
text(310, 98, "ST-LINK et USB-série : ne pas injecter leur 3,3 V.", 0.82)

# Power distribution.
rect(12, 177, 295, 240)
text(16, 183, "3 — DISTRIBUTION D’ALIMENTATION PRÉVUE", 1.25)
rect(18, 192, 63, 211)
text(21, 198, "Alimentation labo", 0.9)
text(21, 204, "12 V / 3 A", 0.9)
rect(76, 192, 123, 211)
text(79, 198, "LM2596 DC/DC", 0.9)
text(79, 204, "12 V → 5 V · ≥2 A", 0.82)
line(63, 201, 76, 201)
text(64, 198, "+12 V", 0.72)
rect(134, 194, 145, 209)
text(135, 200, "100 µF", 0.8)
line(123, 199, 134, 199)
line(123, 205, 145, 205)
text(153, 196, "Rail +5 V → VCC des 4 transceivers et VIN des cartes*", 0.88)
line(145, 199, 151, 199)
text(153, 205, "Rail GND commun → cartes, transceivers et DB9-3", 0.88)
line(145, 205, 151, 205)
text(16, 218, "VIO de chaque TJA1051T/3 ← 3,3 V local de sa carte.", 0.88)
text(16, 225, "Découplage par transceiver : 100 nF entre VCC/GND + 100 nF entre VIO/GND.", 0.88)
text(16, 233, "* USB et rail externe ne doivent pas alimenter simultanément une carte sans contrôle des cavaliers.", 0.82)

# BOM and unresolved component choices.
rect(306, 116, 408, 240)
text(310, 122, "4 — COMPOSANTS PRÉVUS / À CONFIRMER", 1.14)
text(310, 130, "4 cartes : 3 × NUCLEO-G431KB + 1 × Blue Pill F103C8T6", 0.82)
text(310, 137, "4 × TJA1051T/3 · vérifier variante et résistances intégrées", 0.82)
text(310, 144, "8 × 100 nF · 2 × 120 Ω · RT1 fixe, RT2 commutée", 0.82)
text(310, 151, "SW1 SPST · SW2 SPST · SW3 DPST", 0.82)
text(310, 158, "5 DB9 + paire torsadée, idéalement blindée", 0.82)
text(310, 165, "Capteurs : MPU-6050 (N2), Hall (N2), DS18B20 (N3)", 0.82)
text(310, 172, "Hall : référence à choisir · DS18B20 : pull-up 4,7 kΩ", 0.82)
text(310, 179, "Mesure batterie N3 : circuit non défini dans les documents", 0.82)
text(310, 186, "4 OLED SSD1306 prévus ; intégration logicielle reportée", 0.82)
text(310, 193, "8 LED défauts + 8 résistances série 330 Ω (prévision dossier)", 0.82)
text(310, 200, "Pull-up I²C 4,7 kΩ si absente des modules OLED/capteur.", 0.82)
text(310, 207, "RT1 et RT2 aux extrémités ; retirer toute terminaison module.", 0.82)
text(310, 214, "N1–N3 : retirer HW1 ; souder SB9/SB10 pour quartz HSE.", 0.82)
text(310, 221, "N4 : vérifier quartz 8 MHz et référence de carte reçue.", 0.82)
text(310, 232, "Pas d’isolation galvanique dans cette configuration.", 0.82)

line(12, 249, 408, 249)
text(12, 256, "Références : banc-can/docs/pinout.md, docs/bringup.md, docs/protocole_validation.md ; dossier initial : Banc de Test/Dossier_Banc_Test_CAN_v0.1.tex.", 0.78)
text(12, 266, "Schéma fonctionnel de câblage : les blocs représentent des cartes et modules, pas des empreintes PCB ni un netlist de fabrication.", 0.82)
text(12, 278, "G69-BANC-001 · Revue de conception · Les éléments marqués * ou « à confirmer » demandent une vérification ou un choix.", 0.82)

root_uuid = uid()
content = f'''(kicad_sch
 (version 20250114)
 (generator "eeschema")
 (generator_version "9.0")
 (uuid "{root_uuid}")
 (paper "A3")
 (title_block (title "G69-BANC-001 — Banc de test CAN") (date "2026-09-29") (rev "0.1") (company "Projet 2A — Groupe 69") (comment 1 "Schéma fonctionnel de câblage — éléments à confirmer explicitement annotés"))
 (lib_symbols)
 {chr(10).join(items)}
 (sheet_instances (path "/" (page "1")))
 (embedded_fonts no)
)
'''
OUT.write_text(content, encoding="utf-8")
print(OUT)
