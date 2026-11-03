"""Écrit icd.json, l'ICD du banc lue par la simulation 3D (profil par défaut).

    python exporter_icd.py

La source reste icd/bench_icd.yaml : ce fichier passe par pc/canbench/icd_gen.py, déjà
généré par tools/codegen, pour que la simulation encode les trames comme le banc.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "pc"))

from canbench import icd_gen  # noqa: E402


def main():
    profile = icd_gen.PROFILES[icd_gen.DEFAULT_PROFILE]
    icd = {
        "_comment": "FICHIER GÉNÉRÉ par simulation_3d/exporter_icd.py à partir de icd/bench_icd.yaml.",
        "bitrate": icd_gen.BITRATE,
        "profile": icd_gen.DEFAULT_PROFILE,
        "heartbeat_base": profile["heartbeat_base"],
        "ids": profile["ids"],
        "nodes": icd_gen.NODES,
        "frames": {f"0x{can_id:03X}": meta for can_id, meta in icd_gen.FRAMES.items()},
        "simulations": icd_gen.SIMULATIONS,
    }
    out = HERE / "icd.json"
    out.write_text(json.dumps(icd, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out.relative_to(HERE))


if __name__ == "__main__":
    main()
