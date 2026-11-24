"""Produit visualisation_3d_banc_CAN.html : le banc complet en 3D, dans une seule page.

    python generer.py

La page obtenue s'ouvre par double-clic (une connexion Internet charge three.js). Elle n'est
pas versionnée : elle pèse une dizaine de Mo et se régénère en quelques secondes.

- gabarit.html : la scène (disposition du banc, câbles, jonction du bus, points de vue) ;
- la carte porteuse est exportée ici depuis son PCB, la page suit donc la carte routée ;
- modeles/ : adaptateur USB-CAN simplifié et boîtier, repris de la page du 13/11/2026 ;
- la Nucleo vient de simulation_3d/modeles/.
"""

import base64
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
BANC = HERE.parent.parent
CLI = r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"
PCB = HERE.parent / "carte_porteuse" / "carte_porteuse.kicad_pcb"
SORTIE = HERE / "visualisation_3d_banc_CAN.html"


def carte_porteuse():
    """GLB de la carte porteuse, origine en (100, 100) mm comme dans le repère de la scène."""
    with tempfile.TemporaryDirectory() as d:
        glb = Path(d) / "carte_porteuse.glb"
        subprocess.run([CLI, "pcb", "export", "glb", "--subst-models", "--user-origin", "100x100mm",
                        "-f", "-o", str(glb), str(PCB)], check=True, capture_output=True)
        return glb.read_bytes()


def main():
    modeles = {
        "carte_porteuse": carte_porteuse(),
        "nucleo_g431kb": (BANC / "simulation_3d" / "modeles" / "nucleo_g431kb.glb").read_bytes(),
        "adaptateur_min": (HERE / "modeles" / "adaptateur_min.glb").read_bytes(),
        "boitier": (HERE / "modeles" / "boitier.stl").read_bytes(),
    }
    page = (HERE / "gabarit.html").read_text(encoding="utf-8")
    for nom, octets in modeles.items():
        marque = f"@@{nom}@@"
        assert page.count(marque) == 1, marque
        page = page.replace(marque, base64.b64encode(octets).decode("ascii"))
    SORTIE.write_text(page, encoding="utf-8", newline="\n")
    print(f"{SORTIE.name} : {SORTIE.stat().st_size / 1e6:.1f} Mo")


if __name__ == "__main__":
    main()
