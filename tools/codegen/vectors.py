"""Vecteurs de référence pour la parité C <-> Python.

Le générateur produit un fichier JSON contenant, pour chaque trame, une série de
cas « valeurs physiques -> octets attendus ». Ce même fichier est lu par le test
C natif et par le test Python : si les deux implémentations reproduisent les
mêmes octets, elles sont équivalentes.

C'est plus robuste qu'un appel du C depuis Python via ``ctypes`` : le test tourne
à l'identique sous Windows, Linux et en CI, et le fichier est lisible par un
humain lors d'un écart.

Les cas couvrent, pour chaque signal :
  - la valeur par défaut ;
  - les deux bornes du champ brut (valeurs extrêmes codables) ;
  - zéro, et les valeurs ± 1 pas autour de zéro ;
  - un motif « en damier » qui met des bits à 1 dans tous les signaux à la fois,
    ce qui fait ressortir les chevauchements et les erreurs de décalage.
"""

from __future__ import annotations

import json

from .encoding import pack, unpack_raw
from .model import Icd, Message, Signal


def _interesting_values(signal: Signal) -> list[float]:
    """Valeurs physiques à éprouver pour un signal donné."""
    raws = {
        signal.raw_minimum,
        signal.raw_maximum,
        0,
        1,
        -1,
        signal.raw_minimum + 1,
        signal.raw_maximum - 1,
    }
    raws = {r for r in raws if signal.raw_minimum <= r <= signal.raw_maximum}
    values = [signal.decode(r) for r in sorted(raws)]
    if signal.is_exactly_representable(signal.default):
        values.append(signal.default)
    return values


def _cases_for(message: Message) -> list[dict]:
    cases: list[dict] = []

    # 1. tout à la valeur par défaut
    cases.append({"label": "valeurs par défaut", "values": {}})

    # 2. un signal à la fois sur chacune de ses valeurs remarquables
    for signal in message.signals:
        for value in _interesting_values(signal):
            cases.append(
                {
                    "label": f"{signal.name} = {value:g}",
                    "values": {signal.name: value},
                }
            )

    # 3. tous les signaux simultanément à leur maximum, puis à leur minimum
    if message.signals:
        cases.append(
            {
                "label": "tous les signaux au maximum",
                "values": {s.name: s.decode(s.raw_maximum) for s in message.signals},
            }
        )
        cases.append(
            {
                "label": "tous les signaux au minimum",
                "values": {s.name: s.decode(s.raw_minimum) for s in message.signals},
            }
        )
        # motif alterné : un signal sur deux au maximum, l'autre au minimum
        cases.append(
            {
                "label": "motif alterné min/max",
                "values": {
                    s.name: s.decode(s.raw_maximum if i % 2 == 0 else s.raw_minimum)
                    for i, s in enumerate(message.signals)
                },
            }
        )
    return cases


def build(icd: Icd) -> dict:
    """Construit la structure des vecteurs de référence."""
    profile = icd.default
    out: dict = {
        "_comment": (
            "FICHIER GÉNÉRÉ — produit par tools/codegen à partir de icd/bench_icd.yaml. "
            "Lu par les tests C natifs et par les tests Python pour vérifier que les deux "
            "implémentations de l'encodage produisent les mêmes octets."
        ),
        "profile": profile.name,
        "bitrate": icd.bus["bitrate"],
        "frames": [],
    }

    emitted: set[str] = set()
    for message in profile.messages:
        base = message.name if message.node_id is None else message.name.rsplit("_", 1)[0]
        if base in emitted:
            continue
        emitted.add(base)

        entry = {
            "name": base,
            "can_id": message.can_id,
            "dlc": message.dlc,
            "cases": [],
        }
        for case in _cases_for(message):
            data = pack(message, case["values"])
            entry["cases"].append(
                {
                    "label": case["label"],
                    "values": {k: float(v) for k, v in case["values"].items()},
                    "data": list(data),
                    "raw": unpack_raw(message, data),
                }
            )
        out["frames"].append(entry)

    out["case_count"] = sum(len(f["cases"]) for f in out["frames"])
    return out


def render(icd: Icd) -> str:
    return json.dumps(build(icd), indent=2, ensure_ascii=False) + "\n"
