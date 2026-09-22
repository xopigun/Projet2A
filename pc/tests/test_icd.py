"""Tests de l'ICD : encodage, validations, parité entre les trois implémentations.

Trois implémentations indépendantes de l'encodage sont confrontées :

1. la référence Python de ``tools/codegen/encoding.py``, qui produit les vecteurs ;
2. le module Python généré ``pc/canbench/icd_gen.py`` ;
3. ``cantools``, qui relit le fichier DBC généré.

Le code C généré est confronté aux mêmes vecteurs par le test natif
``firmware/tests_host/test_icd_vectors.c``.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "pc"))

from tools.codegen import encoding, gen_c, gen_dbc, gen_latex, gen_python, model, vectors  # noqa: E402


@pytest.fixture(scope="module")
def icd() -> model.Icd:
    return model.load()


@pytest.fixture(scope="module")
def reference() -> dict:
    return json.loads((REPO_ROOT / "icd" / "reference_vectors.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def raw_spec() -> dict:
    return yaml.safe_load((REPO_ROOT / "icd" / "bench_icd.yaml").read_text(encoding="utf-8"))


def _load(spec: dict, tmp_path: Path) -> model.Icd:
    """Écrit un ICD modifié dans un fichier temporaire et le charge."""
    path = tmp_path / "icd.yaml"
    path.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")
    return model.load(path)


# ---------------------------------------------------------------------------
#  Le fichier livré est valide
# ---------------------------------------------------------------------------


def test_icd_charge_sans_erreur(icd: model.Icd) -> None:
    assert icd.default.name == "bench"
    assert len(icd.nodes) == 4
    assert len(icd.default.messages) == 11


def test_contrainte_ordre_arm_go(icd: model.Icd) -> None:
    """ARM et GO doivent être plus prioritaires que tous les contendants.

    C'est ce qui garantit le départ simultané : un nœud armé avant l'émission de
    GO perd l'arbitrage contre GO et attend sa fin.
    """
    for profile in icd.profiles.values():
        lowest = min(m.can_id for m in profile.contenders)
        assert profile.services["GO"] < lowest
        assert profile.services["ARM"] < lowest


def test_heartbeat_hors_plage_canopen(icd: model.Icd) -> None:
    """Le heartbeat du banc ne doit pas empiéter sur 0x700-0x77F (CANopen)."""
    for profile in icd.profiles.values():
        for message in profile.messages:
            if message.name.startswith("HEARTBEAT"):
                assert not 0x700 <= message.can_id <= 0x77F
                assert model.canopen_conflict(message.can_id) is None


def test_services_dans_les_plages_reservees(icd: model.Icd) -> None:
    for profile in icd.profiles.values():
        for message in profile.messages:
            inside = any(r.contains(message.can_id) for r in profile.reserved_ranges)
            assert inside == (message.kind == "service"), message.name


def test_aucun_chevauchement_de_signaux(icd: model.Icd) -> None:
    for profile in icd.profiles.values():
        for message in profile.messages:
            occupied: set[int] = set()
            for signal in message.signals:
                positions = signal.occupied_positions()
                assert not (positions & occupied), f"{message.name}.{signal.name}"
                occupied |= positions
                assert max(positions) < message.dlc * 8


# ---------------------------------------------------------------------------
#  Aller-retour d'encodage
# ---------------------------------------------------------------------------


def test_aller_retour_sur_toutes_les_bornes(icd: model.Icd) -> None:
    """Chaque valeur brute extrême doit revenir à l'identique."""
    for message in icd.default.messages:
        for signal in message.signals:
            for raw in (signal.raw_minimum, signal.raw_maximum, 0, 1, -1):
                if not signal.raw_minimum <= raw <= signal.raw_maximum:
                    continue
                physical = signal.decode(raw)
                data = encoding.pack(message, {signal.name: physical})
                assert encoding.unpack_raw(message, data)[signal.name] == raw


def test_saturation_hors_bornes(icd: model.Icd) -> None:
    """Une valeur hors capacité du champ sature au lieu de déborder sur le voisin."""
    for message in icd.default.messages:
        for signal in message.signals:
            trop_grand = signal.decode(signal.raw_maximum) + abs(signal.factor) * 1000
            trop_petit = signal.decode(signal.raw_minimum) - abs(signal.factor) * 1000
            for physical, attendu in ((trop_grand, signal.raw_maximum),
                                      (trop_petit, signal.raw_minimum)):
                data = encoding.pack(message, {signal.name: physical})
                decoded = encoding.unpack_raw(message, data)
                assert decoded[signal.name] == attendu
                # les autres signaux restent à leur valeur par défaut
                for other in message.signals:
                    if other.name != signal.name:
                        assert decoded[other.name] == other.encode(other.default)


def test_signes_negatifs(icd: model.Icd) -> None:
    for message in icd.default.messages:
        for signal in message.signals:
            if not signal.signed:
                continue
            data = encoding.pack(message, {signal.name: signal.decode(-1)})
            assert encoding.unpack_raw(message, data)[signal.name] == -1


def test_arrondi_a_l_oppose_de_zero() -> None:
    """La convention d'arrondi doit être celle de llround, pas celle de round()."""
    assert model.bench_round(0.5) == 1
    assert model.bench_round(1.5) == 2  # round() natif donnerait 2
    assert model.bench_round(2.5) == 3  # round() natif donnerait 2
    assert model.bench_round(-0.5) == -1
    assert model.bench_round(-2.5) == -3


def test_arrondi_sur_un_signal_reel(icd: model.Icd) -> None:
    """Une valeur à un demi-pas s'arrondit en s'éloignant de zéro."""
    message = icd.default.by_name("ENERGY_COMMAND")
    signal = next(s for s in message.signals if s.name == "torque_setpoint")
    assert signal.factor == 0.1
    assert signal.encode(0.05) == 1  # et non 0
    assert signal.encode(-0.05) == -1


# ---------------------------------------------------------------------------
#  Parité entre implémentations
# ---------------------------------------------------------------------------


def test_vecteurs_a_jour(icd: model.Icd, reference: dict) -> None:
    """Le fichier de vecteurs versionné correspond bien à l'ICD courant."""
    assert json.loads(vectors.render(icd)) == reference


def test_parite_module_python_genere(reference: dict) -> None:
    from canbench import icd_gen

    verifies = 0
    for frame in reference["frames"]:
        cls = icd_gen.LAYOUTS.get(frame["name"])
        if cls is None:
            continue
        for case in frame["cases"]:
            expected = bytes(case["data"])
            assert cls.unpack(expected).pack() == expected, f"{frame['name']} / {case['label']}"
            verifies += 1
    assert verifies > 100


def test_parite_cantools_via_dbc(reference: dict) -> None:
    cantools = pytest.importorskip("cantools")
    db = cantools.database.load_file(REPO_ROOT / "icd" / "bench.dbc")

    for frame in reference["frames"]:
        for case in frame["cases"]:
            decoded = db.decode_message(
                frame["can_id"], bytes(case["data"]), decode_choices=False, scaling=False
            )
            assert {k: int(v) for k, v in decoded.items()} == case["raw"], (
                f"{frame['name']} / {case['label']}"
            )


def test_parite_python_genere_contre_reference(icd: model.Icd) -> None:
    """Le module généré et la référence encodent identiquement les simulations."""
    from canbench import icd_gen

    for name, simulation in icd.simulations.items():
        message = icd.default.by_name(name)
        cls = icd_gen.LAYOUTS[name]
        for step in simulation["steps"]:
            attendu = encoding.pack(message, step)
            assert cls(**step).pack() == attendu, f"{name} / {step}"


# ---------------------------------------------------------------------------
#  Le générateur est déterministe et à jour
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("chemin", "rendu"),
    [
        ("firmware/common/icd_gen/icd_gen.h", lambda i: gen_c.generate_header(i)),
        ("firmware/common/icd_gen/icd_gen.c", lambda i: gen_c.generate_source(i)),
        ("pc/canbench/icd_gen.py", lambda i: gen_python.generate(i)),
        ("icd/bench.dbc", lambda i: gen_dbc.generate(i)),
        ("docs/latex/icd_encoding_table.tex", lambda i: gen_latex.generate_encoding_table(i)),
        ("docs/latex/icd_reserved_ids.tex", lambda i: gen_latex.generate_reserved_table(i)),
    ],
)
def test_code_genere_a_jour(icd: model.Icd, chemin: str, rendu) -> None:
    attendu = rendu(icd)
    reel = (REPO_ROOT / chemin).read_text(encoding="utf-8")
    assert reel == attendu, (
        f"{chemin} n'est pas à jour — lancer « python -m tools.codegen »"
    )


# ---------------------------------------------------------------------------
#  Les validations rejettent bien les ICD fautifs
# ---------------------------------------------------------------------------


def test_detecte_collision_d_identifiants(raw_spec: dict, tmp_path: Path) -> None:
    spec = copy.deepcopy(raw_spec)
    spec["messages"][-1]["id"] = spec["messages"][-2]["id"]  # TEMP_BATTERY = IMU_SPEED
    with pytest.raises(model.IcdError, match="collision d'identifiant"):
        _load(spec, tmp_path)


def test_detecte_collision_avec_la_plage_reservee(raw_spec: dict, tmp_path: Path) -> None:
    spec = copy.deepcopy(raw_spec)
    spec["messages"][-1]["id"] = 0x015  # dans 0x010-0x01F, réservé au banc
    with pytest.raises(model.IcdError, match="plage réservée"):
        _load(spec, tmp_path)


def test_detecte_chevauchement_de_signaux(raw_spec: dict, tmp_path: Path) -> None:
    spec = copy.deepcopy(raw_spec)
    message = next(m for m in spec["messages"] if m["name"] == "ENERGY_COMMAND")
    message["signals"][1]["start_byte"] = 1  # empiète sur torque_setpoint (octets 0-1)
    with pytest.raises(model.IcdError, match="[Cc]hevauchement"):
        _load(spec, tmp_path)


def test_detecte_debordement_de_trame(raw_spec: dict, tmp_path: Path) -> None:
    spec = copy.deepcopy(raw_spec)
    message = next(m for m in spec["messages"] if m["name"] == "ENERGY_COMMAND")
    message["signals"][0]["start_byte"] = 7
    message["signals"][0]["length"] = 16  # déborde des 8 octets
    with pytest.raises(model.IcdError, match="déborde"):
        _load(spec, tmp_path)


def test_detecte_violation_de_l_ordre_arm_go(raw_spec: dict, tmp_path: Path) -> None:
    """Un contendant plus prioritaire que GO doit être refusé."""
    spec = copy.deepcopy(raw_spec)
    message = next(m for m in spec["messages"] if m["name"] == "ENERGY_COMMAND")
    message["id"] = 0x005  # plus prioritaire que GO (0x011)
    with pytest.raises(model.IcdError, match="strictement inférieur"):
        _load(spec, tmp_path)


def test_detecte_simulation_non_representable(raw_spec: dict, tmp_path: Path) -> None:
    """Une valeur de simulation non représentable rendrait le test d'encodage faux."""
    spec = copy.deepcopy(raw_spec)
    # 0.03 n'est pas un multiple de 0.0625, le facteur de temperature
    spec["simulations"]["TEMP_BATTERY"]["steps"][0]["temperature"] = 0.03
    with pytest.raises(model.IcdError, match="exactement représentable"):
        _load(spec, tmp_path)


def test_detecte_bornes_incoherentes(raw_spec: dict, tmp_path: Path) -> None:
    spec = copy.deepcopy(raw_spec)
    message = next(m for m in spec["messages"] if m["name"] == "ENERGY_COMMAND")
    message["signals"][0]["max"] = 1e9  # 16 bits signés ne vont pas si haut
    with pytest.raises(model.IcdError, match="hors de ce que"):
        _load(spec, tmp_path)


def test_detecte_id_ref_inconnu(raw_spec: dict, tmp_path: Path) -> None:
    spec = copy.deepcopy(raw_spec)
    next(m for m in spec["messages"] if m["name"] == "ARM")["id_ref"] = "INEXISTANT"
    with pytest.raises(model.IcdError, match="introuvable"):
        _load(spec, tmp_path)
