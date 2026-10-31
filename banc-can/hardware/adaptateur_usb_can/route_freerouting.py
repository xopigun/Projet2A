"""Route adaptateur_usb_can.kicad_pcb avec Freerouting (2 couches, règles ENSEA).

À lancer après generate_pcb.py, avec le Python livré avec KiCad 9 :

    "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" route_freerouting.py <freerouting.jar>

Testé avec Freerouting 2.5.0 (https://github.com/freerouting/freerouting/releases).
Le plan de masse est retiré de l'export puis rempli de nouveau après import. Le
rétrécissement automatique des pistes (« neckdown ») et le fanout sont désactivés :
le premier descend à 0,3 mm, sous les 0,4 mm de la factory, et le second double le
nombre de vias.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

PCB = Path(__file__).with_name("adaptateur_usb_can.kicad_pcb")


def main(jar):
    work = Path(tempfile.mkdtemp(prefix="freerouting_"))
    dsn, ses = work / "board.dsn", work / "board.ses"

    board = pcbnew.LoadBoard(str(PCB))
    for zone in list(board.Zones()):
        board.Remove(zone)
    assert pcbnew.ExportSpecctraDSN(board, str(dsn)), "export DSN impossible"

    subprocess.run(
        ["java", "-jar", jar, "-de", str(dsn), "-do", str(ses), "-l", "en",
         "--gui.enabled=false", "--api_server.enabled=false",
         "--router.autorouter.max_passes=100",
         "--router.automatic_neckdown=false", "--router.fanout.enabled=false"],
        check=True, cwd=work,
    )

    board = pcbnew.LoadBoard(str(PCB))
    assert pcbnew.ImportSpecctraSES(board, str(ses)), "import SES impossible"
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(PCB))
    vias = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_VIA")
    print(f"{PCB.name} routé : {vias} vias (journal Freerouting dans {work})")


if __name__ == "__main__":
    main(sys.argv[1])
