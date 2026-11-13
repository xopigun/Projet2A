"""Produit les modèles 3D (GLB) des cartes du banc, pour la simulation 3D.

    "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" generate_modeles_3d.py <gltf-transform>

Chaque GLB est aussi écrit en base64 dans un .json de même nom, que lit la page web.
Avec --emballer à la place de <gltf-transform>, seuls ces .json sont réécrits.

<gltf-transform> : chemin de l'outil en ligne de commande @gltf-transform/cli, qui compresse
les GLB (simplification et quantification) ; sans lui, les fichiers pèsent cinq à dix fois plus.

L'adaptateur USB-CAN est exporté depuis son vrai PCB. Les autres cartes (Nucleo-G431KB,
module TJA1051, MPU-6050, LM2596…) n'ont pas de modèle officiel dans KiCad :
elles sont reconstituées ici en plaçant les boîtiers de la bibliothèque KiCad sur un contour
aux dimensions de la carte. Ce sont des maquettes visuelles : l'encombrement et les
connecteurs sont respectés, pas le routage ni la position exacte de chaque composant.
"""

import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

HERE = Path(__file__).parent
OUT = HERE / "modeles"
ADAPTATEUR = HERE.parent / "hardware" / "adaptateur_usb_can" / "adaptateur_usb_can.kicad_pcb"
TEMPLATE = HERE.parent / "hardware" / "regles_fabrication" / "20260112_ENSEA_2_layers_drc.kicad_pcb"
KICAD = Path(r"C:\Program Files\KiCad\9.0")
FOOTPRINTS = KICAD / "share" / "kicad" / "footprints"
CLI = KICAD / "bin" / "kicad-cli.exe"

HDR = "Connector_PinHeader_2.54mm"
# Une carte : (largeur, hauteur) en mm, couleur du vernis, et les empreintes
# (bibliothèque, empreinte, x, y, rotation, face) avec l'origine au centre de la carte.
# Face "B" : composant retourné sous la carte (barrettes mâles pointant vers le bas).
CARTES = {
    # NUCLEO-G431KB (MB1430), format Arduino Nano : deux rangées de 15 broches à 15,24 mm
    "nucleo_g431kb": ((50.8, 18.5), "White", [
        ("Connector_USB", "USB_Micro-B_Molex-105017-0001", -23.2, 0, 270, "F"),
        ("Package_QFP", "LQFP-48_7x7mm_P0.5mm", -13.0, 0, 45, "F"),          # ST-LINK
        ("Crystal", "Crystal_SMD_3225-4Pin_3.2x2.5mm", -6.5, 3.5, 0, "F"),
        ("Package_DFN_QFN", "QFN-32-1EP_5x5mm_P0.5mm_EP3.45x3.45mm", 4.0, 0, 45, "F"),  # G431KB
        ("Crystal", "Crystal_SMD_3225-4Pin_3.2x2.5mm", 10.0, 3.0, 0, "F"),   # 24 MHz
        ("Button_Switch_SMD", "SW_Push_1P1T_NO_CK_KMR2", 15.5, -2.5, 0, "F"),  # RESET
        ("LED_SMD", "LED_0603_1608Metric", -18.0, 4.5, 0, "F"),              # LD1 COM
        ("LED_SMD", "LED_0603_1608Metric", 15.5, 3.2, 0, "F"),               # LD2 utilisateur
        ("LED_SMD", "LED_0603_1608Metric", -18.0, -4.5, 0, "F"),             # LD3 alimentation
        ("Capacitor_SMD", "C_0603_1608Metric", 0.0, -4.0, 0, "F"),
        ("Capacitor_SMD", "C_0603_1608Metric", 0.0, 4.0, 0, "F"),
        ("Capacitor_SMD", "C_0603_1608Metric", 8.0, -3.5, 90, "F"),
        ("Resistor_SMD", "R_0603_1608Metric", -6.5, -3.5, 0, "F"),
        ("Package_TO_SOT_SMD", "SOT-223-3_TabPin2", 4.0, 0, 0, "B"),
        (HDR, "PinHeader_1x15_P2.54mm_Vertical", -17.78, -7.62, 270, "B"),
        (HDR, "PinHeader_1x15_P2.54mm_Vertical", -17.78, 7.62, 270, "B"),
    ]),
    # Module transceiver TJA1051T/3 : broches logiques d'un côté, bornier CAN de l'autre
    "tja1051": ((24.0, 18.0), "Blue", [
        ("Package_SO", "SOIC-8_3.9x4.9mm_P1.27mm", 0.5, 0, 90, "F"),
        ("Capacitor_SMD", "C_0603_1608Metric", -4.0, -4.5, 0, "F"),
        ("Capacitor_SMD", "C_0603_1608Metric", -4.0, 4.5, 0, "F"),
        ("Resistor_SMD", "R_0603_1608Metric", 5.0, -5.0, 90, "F"),          # 120 Ω, à retirer
        ("LED_SMD", "LED_0603_1608Metric", 5.0, 5.0, 0, "F"),
        (HDR, "PinHeader_1x06_P2.54mm_Vertical", -10.0, -6.35, 0, "B"),
        ("TerminalBlock_Phoenix", "TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
         8.0, 2.54, 90, "F"),
    ]),
    # Module GY-521 (MPU-6050), nœud N2
    "gy521": ((21.0, 16.0), "Blue", [
        ("Package_DFN_QFN", "QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", 1.0, -1.5, 0, "F"),
        ("Capacitor_SMD", "C_0603_1608Metric", -4.5, -2.0, 90, "F"),
        ("Capacitor_SMD", "C_0603_1608Metric", 6.0, -2.0, 90, "F"),
        ("Resistor_SMD", "R_0603_1608Metric", -6.5, -2.0, 90, "F"),
        ("LED_SMD", "LED_0603_1608Metric", 7.5, -5.0, 0, "F"),
        (HDR, "PinHeader_1x08_P2.54mm_Vertical", -8.89, 6.0, 90, "B"),
    ]),
    # Module abaisseur LM2596 (12 V → 5 V)
    "lm2596": ((43.0, 21.0), "Blue", [
        ("Package_TO_SOT_SMD", "TO-263-5_TabPin3", -4.0, -2.0, 270, "F"),
        ("Inductor_SMD", "L_12x12mm_H8mm", 9.0, 0, 0, "F"),
        ("Capacitor_THT", "CP_Radial_D8.0mm_P3.50mm", -16.0, -4.5, 0, "F"),
        ("Capacitor_THT", "CP_Radial_D8.0mm_P3.50mm", 19.0, 4.5, 180, "F"),
        ("Potentiometer_THT", "Potentiometer_Bourns_3296W_Vertical", -12.0, 6.5, 0, "F"),
        ("Diode_SMD", "D_SMC", -1.0, 6.5, 0, "F"),
    ]),
    # Carte de raccordement d'un nœud : embase DB9 mâle (CiA 303-1) et bornier 3 points
    "carte_db9": ((32.0, 24.0), "Green", [
        ("Connector_Dsub",
         "DSUB-9_Pins_Horizontal_P2.77x2.84mm_EdgePinOffset7.70mm_Housed_MountingHolesOffset9.12mm",
         -5.54, 4.3, 0, "F"),
        ("TerminalBlock_Phoenix", "TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal",
         -5.08, -7.0, 180, "F"),
    ]),
    # Terminaison 120 Ω sur bornier
    "terminaison": ((26.0, 14.0), "Green", [
        ("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", -9.0, 2.5, 0, "F"),
        ("TerminalBlock_Phoenix", "TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
         7.0, -2.54, 90, "F"),
    ]),
}
# Composants seuls, sans carte : afficheur LCD 16×2 et sonde DS18B20 en TO-92
SEULS = {
    "lcd1602": ("Display", "WC1602A", 0),
    "to92": ("Package_TO_SOT_THT", "TO-92_Inline", 0),
}


def mm(v):
    return pcbnew.FromMM(v)


def nouvelle_carte():
    board = pcbnew.LoadBoard(str(TEMPLATE))
    for item in list(board.GetFootprints()) + list(board.GetDrawings()) + list(board.GetTracks()):
        board.Remove(item)
    return board


def contour(board, w, h):
    pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(pcbnew.VECTOR2I(mm(x0), mm(y0)))
        seg.SetEnd(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(mm(0.1))
        board.Add(seg)


def poser(board, lib, name, x, y, rot, face):
    fp = pcbnew.FootprintLoad(str(FOOTPRINTS / f"{lib}.pretty"), name)
    fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    fp.SetOrientationDegrees(rot)
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    board.Add(fp)
    if face == "B":  # après Add : Flip a besoin de la carte pour ses couches
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)


def colorier(pcb, vernis):
    """Couleur du vernis dans l'empilage, que l'export GLB reprend."""
    text = pcb.read_text(encoding="utf-8")
    for kind in ("Top Solder Mask", "Bottom Solder Mask"):
        text = text.replace(f'(type "{kind}")', f'(type "{kind}")\n\t\t\t\t(color "{vernis}")', 1)
    for kind in ("Top Silk Screen", "Bottom Silk Screen"):
        silk = "Black" if vernis == "White" else "White"
        text = text.replace(f'(type "{kind}")', f'(type "{kind}")\n\t\t\t\t(color "{silk}")', 1)
    pcb.write_text(text, encoding="utf-8")


def exporter(pcb, glb, *options):
    subprocess.run([str(CLI), "pcb", "export", "glb", "-f", *options, "-o", str(glb), str(pcb)],
                   check=True, capture_output=True)


def compresser(tool, brut, glb):
    # Quantification (KHR_mesh_quantization) plutôt que meshopt : Three.js la lit sans
    # décodeur WebAssembly, que la page publiée ne peut pas toujours charger.
    subprocess.run([tool, "optimize", str(brut), str(glb), "--compress", "quantize",
                    "--texture-compress", "false", "--simplify-error", "0.0002"],
                   check=True, capture_output=True, shell=tool.lower().endswith(".cmd"))


def main(tool):
    OUT.mkdir(exist_ok=True)
    build = Path(tempfile.mkdtemp())
    bruts = {}
    for name, ((w, h), vernis, parts) in CARTES.items():
        board = nouvelle_carte()
        contour(board, w, h)
        for part in parts:
            poser(board, *part)
        pcb = build / f"{name}.kicad_pcb"
        board.Save(str(pcb))
        colorier(pcb, vernis)
        bruts[name] = build / f"{name}.glb"
        exporter(pcb, bruts[name], "--include-pads", "--include-soldermask")
    for name, (lib, fp, rot) in SEULS.items():
        board = nouvelle_carte()
        contour(board, 10, 10)
        poser(board, lib, fp, 0, 0, rot, "F")
        pcb = build / f"{name}.kicad_pcb"
        board.Save(str(pcb))
        bruts[name] = build / f"{name}.glb"
        exporter(pcb, bruts[name], "--no-board-body")
    # La vraie carte : cuivre nu (pas de vernis à la factory), sérigraphie comprise
    bruts["adaptateur_usb_can"] = build / "adaptateur_usb_can.glb"
    exporter(ADAPTATEUR, bruts["adaptateur_usb_can"], "--include-tracks", "--include-pads",
             "--include-silkscreen", "--subst-models")

    for name, brut in bruts.items():
        glb = OUT / f"{name}.glb"
        compresser(tool, brut, glb)
        emballer(glb)
        print(f"{glb.relative_to(HERE)}  {glb.stat().st_size // 1024} Ko")


def emballer(glb):
    """Copie du GLB en base64 dans un .json : l'hébergement des artefacts ne sert pas le .glb."""
    data = base64.b64encode(glb.read_bytes()).decode("ascii")
    glb.with_suffix(".json").write_text(json.dumps({"glb": data}), encoding="ascii")


if __name__ == "__main__":
    if sys.argv[1:] == ["--emballer"]:  # seulement réécrire les .json depuis les .glb
        for glb in sorted(OUT.glob("*.glb")):
            emballer(glb)
    else:
        main(sys.argv[1])
