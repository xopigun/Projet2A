"""Tests de `canbench`, tous exécutés sur le bus virtuel.

Ce que ces tests prouvent
-------------------------
Ils valident **l'outillage PC** : la chaîne de mesure, le comptage des rangs, la
détection des écarts d'encodage, le calcul de charge, les rapports. Ils ne
prouvent rien sur le comportement du bus CAN : le simulateur reproduit l'ordre
qu'un arbitrage réel produirait, il ne le démontre pas.

Chaque test nominal est doublé d'un **cas dégradé** qui doit faire échouer la
mesure — sans quoi un test vert ne vaudrait rien.
"""

from __future__ import annotations

import itertools
import sys
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "pc"))

from canbench import arbitration, decode, encoding, faults, icd_gen, record, report  # noqa: E402
from canbench.bus import Bench, Frame  # noqa: E402
from canbench.cli import main as cli_main  # noqa: E402
from canbench.simulator import NodeSimulator, SimulatorOptions  # noqa: E402

_channels = itertools.count()


@pytest.fixture
def channel() -> str:
    """Canal virtuel distinct par test, pour éviter toute interférence."""
    return f"canbench-test-{next(_channels)}"


def _session(channel: str, options: SimulatorOptions | None = None):
    simulator = NodeSimulator(channel=channel, options=options).start()
    time.sleep(0.15)
    bench = Bench(interface="virtual", channel=channel)
    return simulator, bench


# ---------------------------------------------------------------------------
#  Conformité CAN 2.0A
# ---------------------------------------------------------------------------


def test_le_bus_refuse_un_identifiant_etendu(channel: str) -> None:
    with (
        Bench(interface="virtual", channel=channel) as bench,
        pytest.raises(ValueError, match="11 bits"),
    ):
        bench.send(0x1FFFF)


def test_le_bus_refuse_plus_de_huit_octets(channel: str) -> None:
    with (
        Bench(interface="virtual", channel=channel) as bench,
        pytest.raises(ValueError, match="8 au plus"),
    ):
        bench.send(0x100, bytes(12))


def test_les_trames_non_conformes_sont_signalees(channel: str) -> None:
    """Une trame FD ou étendue reçue doit être comptée, pas ignorée."""
    import can

    with Bench(interface="virtual", channel=channel) as bench:
        intrus = can.Bus(interface="virtual", channel=channel)
        intrus.send(can.Message(arbitration_id=0x12345678, data=bytes(8), is_extended_id=True))
        intrus.send(
            can.Message(arbitration_id=0x123, data=bytes(16), is_extended_id=False, is_fd=True)
        )
        bench.collect(0.3)
        intrus.shutdown()

    assert bench.non_conformity.extended >= 1
    assert bench.non_conformity.fd >= 1
    assert bench.non_conformity.report()


# ---------------------------------------------------------------------------
#  T3 — arbitrage
# ---------------------------------------------------------------------------


def test_arbitrage_nominal(channel: str) -> None:
    # Pas de trafic périodique : pendant un cycle, le bus ne doit porter que GO
    # puis les contendants. Le firmware suspend de même son émission périodique.
    simulator, bench = _session(channel, SimulatorOptions(periodic_app=False))
    try:
        result = arbitration.run(bench, cycles=25)
    finally:
        bench.close()
        simulator.stop()

    assert result.invalid_count == 0
    assert len(result.valid_cycles) == 25

    rows = {row["sender"]: row for row in result.stats()}
    assert rows["N1"]["expected_rank"] == 1
    assert rows["N2"]["expected_rank"] == 2
    assert rows["N3"]["expected_rank"] == 3
    for sender, expected in (("N1", 1), ("N2", 2), ("N3", 3)):
        assert rows[sender]["histogram"] == {expected: 25}, sender
        assert rows[sender]["always_expected"]

    # Colonnes du tableau 7 du dossier : « perdus » compte des cycles.
    assert rows["N1"]["won"] == 25 and rows["N1"]["lost"] == 0
    assert rows["N3"]["won"] == 0 and rows["N3"]["lost"] == 25

    assert result.passed


def test_arbitrage_detecte_un_noeud_qui_rate_l_armement(channel: str) -> None:
    """Un nœud sourd à ARM doit invalider les cycles, pas passer inaperçu."""
    simulator, bench = _session(channel, SimulatorOptions(deaf_nodes=(3,), periodic_app=False))
    try:
        result = arbitration.run(bench, cycles=10, cycle_timeout=0.02)
    finally:
        bench.close()
        simulator.stop()

    assert result.invalid_count == 10
    assert not result.passed
    assert "absent" in result.cycles[0].reason


def test_arbitrage_detecte_un_ordre_incorrect(channel: str) -> None:
    """Si l'ordre n'est pas celui des identifiants, le test doit échouer."""
    simulator, bench = _session(
        channel, SimulatorOptions(forced_order=(3, 2, 1), periodic_app=False)
    )
    try:
        result = arbitration.run(bench, cycles=10)
    finally:
        bench.close()
        simulator.stop()

    assert result.invalid_count == 10
    assert not result.passed
    assert "ordre inattendu" in result.cycles[0].reason


def test_arbitrage_refuse_le_verdict_si_horloge_non_conforme(channel: str) -> None:
    """Un nœud sur HSI interdit de prononcer une réussite."""
    simulator, bench = _session(
        channel, SimulatorOptions(unqualified_clock_nodes=(2,), periodic_app=False)
    )
    try:
        result = arbitration.run(bench, cycles=10)
    finally:
        bench.close()
        simulator.stop()

    assert result.clock_warnings == ["N2"]
    assert not result.passed  # malgré des rangs corrects


# ---------------------------------------------------------------------------
#  T4 — encodage
# ---------------------------------------------------------------------------


def test_encodage_nominal(channel: str) -> None:
    simulator, bench = _session(channel)
    try:
        result = encoding.run(bench, duration=0.8)
    finally:
        bench.close()
        simulator.stop()

    assert result.passed
    assert len(result.frames) == 3
    for frame in result.frames:
        assert frame.observed > 0
        assert frame.matched == frame.observed


def test_encodage_detecte_un_octet_faux(channel: str) -> None:
    """Un octet altéré doit être localisé, avec le signal concerné."""
    import can

    simulator, bench = _session(channel, SimulatorOptions(periodic_app=False))
    intrus = can.Bus(interface="virtual", channel=channel)
    try:
        layout = icd_gen.LAYOUTS["IMU_SPEED"]
        step = dict(icd_gen.SIMULATIONS["IMU_SPEED"]["steps"][0])
        payload = bytearray(layout(**step).pack())
        payload[0] ^= 0xFF  # corrompt accel_x

        # L'émission doit avoir lieu pendant la collecte : encoding.run() purge
        # le bus au démarrage pour repartir d'un état propre.
        def flood() -> None:
            for _ in range(20):
                intrus.send(
                    can.Message(
                        arbitration_id=icd_gen.IDS["IMU_SPEED"],
                        data=bytes(payload),
                        is_extended_id=False,
                    )
                )
                time.sleep(0.01)

        emitter = threading.Thread(target=flood, daemon=True)
        emitter.start()
        result = encoding.run(bench, duration=0.5)
        emitter.join(timeout=1.0)
    finally:
        intrus.shutdown()
        bench.close()
        simulator.stop()

    imu = next(f for f in result.frames if f.name == "IMU_SPEED")
    assert not imu.passed
    assert imu.diffs
    assert imu.diffs[0].index == 0
    assert "accel_x" in imu.diffs[0].signals


def test_encodage_detecte_un_dlc_incoherent(channel: str) -> None:
    import can

    simulator, bench = _session(channel, SimulatorOptions(periodic_app=False))
    intrus = can.Bus(interface="virtual", channel=channel)
    try:

        def flood() -> None:
            for _ in range(20):
                intrus.send(
                    can.Message(
                        arbitration_id=icd_gen.IDS["TEMP_BATTERY"],
                        data=bytes(4),
                        is_extended_id=False,
                    )
                )
                time.sleep(0.01)

        emitter = threading.Thread(target=flood, daemon=True)
        emitter.start()
        result = encoding.run(bench, duration=0.5)
        emitter.join(timeout=1.0)
    finally:
        intrus.shutdown()
        bench.close()
        simulator.stop()

    temp = next(f for f in result.frames if f.name == "TEMP_BATTERY")
    assert temp.dlc_errors >= 3
    assert not temp.passed


# ---------------------------------------------------------------------------
#  T6 — fautes logicielles
# ---------------------------------------------------------------------------


def test_fautes_logiques(channel: str) -> None:
    simulator, bench = _session(channel)
    try:
        result = faults.run_logical(bench, target_node=4, hold=0.4)
    finally:
        bench.close()
        simulator.stop()

    assert result.passed
    noms = [step.name for step in result.steps]
    assert any("babbling" in n for n in noms)
    assert any("retour à la normale" in n for n in noms)


def test_babbling_idiot_augmente_le_trafic(channel: str) -> None:
    simulator, bench = _session(channel)
    try:
        avant = faults.observe(bench, "avant", 0.3)
        faults.send_cfg(bench, 4, faults.Mode.BABBLING_IDIOT, duration_ms=600, param=0x400)
        pendant = faults.observe(bench, "pendant", 0.4)
        faults.revoke(bench, 4)
        time.sleep(0.2)
        bench.drain()
        apres = faults.observe(bench, "après", 0.3)
    finally:
        bench.close()
        simulator.stop()

    assert pendant.frames_per_s > avant.frames_per_s * 1.5
    # La faute est bornée et révocable : le trafic doit redescendre.
    assert apres.frames_per_s < pendant.frames_per_s * 0.8


def test_une_faute_expire_toute_seule(channel: str) -> None:
    """Toute faute est bornée dans le temps, même sans commande de révocation."""
    simulator, bench = _session(channel)
    try:
        faults.send_cfg(bench, 4, faults.Mode.BABBLING_IDIOT, duration_ms=200, param=0x400)
        pendant = faults.observe(bench, "pendant", 0.15)
        time.sleep(0.4)  # au-delà de l'échéance, sans révoquer
        # Purge : le bus virtuel a bufferisé l'inondation ; sans cela on
        # mesurerait la file d'attente et non le trafic courant.
        bench.drain()
        apres = faults.observe(bench, "après échéance", 0.3)
    finally:
        bench.close()
        simulator.stop()

    assert apres.frames_per_s < pendant.frames_per_s * 0.8


# ---------------------------------------------------------------------------
#  Charge du bus
# ---------------------------------------------------------------------------


def test_charge_theorique() -> None:
    theory = decode.theoretical_load()
    # Trois trames de 8 octets toutes les 20 ms.
    assert len(theory["frames"]) == 3
    assert 0.03 < theory["load"] < 0.06
    # Le pire cas avec bit stuffing doit majorer le cas sans stuffing.
    assert theory["load"] > decode.theoretical_load(worst_case=False)["load"]


def test_duree_de_trame_conforme_au_calcul() -> None:
    """Une trame standard de 8 octets fait 108 bits, plus 3 d'intermission."""
    assert decode.frame_bits(8, worst_case=False) == 111
    # 216 µs sans stuffing, jusqu'à ~270 µs au pire cas intermission comprise.
    sans_stuffing = decode.frame_duration(8, worst_case=False)
    assert abs(sans_stuffing - 111 / 500_000) < 1e-9
    assert decode.frame_bits(8, worst_case=True) > decode.frame_bits(8, worst_case=False)


def test_charge_mesuree(channel: str) -> None:
    simulator, bench = _session(channel)
    try:
        started = time.monotonic()
        frames = bench.collect(0.5)
        measured = decode.measured_load(frames, time.monotonic() - started)
    finally:
        bench.close()
        simulator.stop()

    assert measured["frames"] > 0
    assert 0 < measured["load"] < 1
    assert measured["load_worst_case"] >= measured["load"]


# ---------------------------------------------------------------------------
#  Enregistrement et rejeu
# ---------------------------------------------------------------------------


def test_enregistrement_puis_rejeu(channel: str, tmp_path: Path) -> None:
    path = tmp_path / "trace.asc"

    simulator, bench = _session(channel)
    try:
        count = record.record(bench, path, 0.4)
    finally:
        bench.close()
        simulator.stop()

    assert count > 0
    assert path.exists()

    stats = record.count_non_classic(path)
    assert stats["total"] == count
    assert stats["extended"] == 0 and stats["fd"] == 0

    # Rejeu sur un canal vierge : toutes les trames doivent repasser.
    with Bench(interface="virtual", channel=f"{channel}-replay") as replayer:
        replayed = record.replay(replayer, path, respect_timing=False)
    assert replayed == count


# ---------------------------------------------------------------------------
#  Décodage
# ---------------------------------------------------------------------------


def test_decodage_d_une_trame_connue() -> None:
    layout = icd_gen.LAYOUTS["ENERGY_COMMAND"]
    payload = layout(
        torque_setpoint=12.5, speed_setpoint=1500.0, current_limit=10.0, enable=1
    ).pack()
    frame = Frame(timestamp=0.0, can_id=icd_gen.IDS["ENERGY_COMMAND"], data=payload)

    decoded = decode.decode(frame)
    assert decoded.known and decoded.dlc_ok
    assert decoded.signals["torque_setpoint"] == pytest.approx(12.5)
    assert decoded.signals["enable"] == 1
    assert "ENERGY_COMMAND" in decoded.summary()


def test_decodage_d_une_trame_inconnue() -> None:
    """Un identifiant hors ICD n'est pas une erreur : le banc n'a aucun filtre."""
    decoded = decode.decode(Frame(timestamp=0.0, can_id=0x555, data=bytes(8)))
    assert not decoded.known
    assert "inconnu" in decoded.summary()


# ---------------------------------------------------------------------------
#  Rapports
# ---------------------------------------------------------------------------


def test_rapport_markdown_et_latex(tmp_path: Path) -> None:
    entry = report.Report(test="T3", result_text="rang N1=1\nrang N2=2", passed=True)
    md, tex = entry.write(tmp_path)

    markdown = md.read_text(encoding="utf-8")
    assert "T3 — Arbitrage ARM/GO" in markdown
    assert "**Objectif.**" in markdown
    assert "**Critère de réussite.**" in markdown
    assert "Verdict : REUSSITE" in markdown
    assert entry.firmware_hash in markdown  # tracabilité du firmware testé

    latex = tex.read_text(encoding="utf-8")
    assert r"\subsection{T3" in latex
    assert r"\begin{verbatim}" in latex


def test_rapport_sur_bus_virtuel_est_non_concluant(tmp_path: Path) -> None:
    """Un résultat obtenu en simulation ne peut pas valoir réussite."""
    blockers = report.blockers_from(virtual=True, clock_warnings=[], loss_warnings=[])
    entry = report.Report(test="T3", result_text="ok", passed=True, virtual=True, blockers=blockers)
    assert entry.verdict == "NON CONCLUANT"
    assert "virtuel" in entry.markdown()


def test_rapport_refuse_la_reussite_si_horloge_non_conforme() -> None:
    blockers = report.blockers_from(virtual=False, clock_warnings=["N2"], loss_warnings=[])
    entry = report.Report(test="T2", result_text="ok", passed=True, blockers=blockers)
    assert entry.verdict == "NON CONCLUANT"
    assert "N2" in entry.markdown()


def test_rapport_refuse_la_reussite_si_perte_de_trame() -> None:
    blockers = report.blockers_from(
        virtual=False, clock_warnings=[], loss_warnings=["N1 : ring_overflow = 4"]
    )
    entry = report.Report(test="T3", result_text="ok", passed=True, blockers=blockers)
    assert entry.verdict == "NON CONCLUANT"


# ---------------------------------------------------------------------------
#  Ligne de commande
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["--simulate", "arbitration", "--cycles", "5"],
        ["--simulate", "encoding", "--duration", "0.5"],
        ["--simulate", "busload", "--measure", "0.3"],
        ["--simulate", "monitor", "--duration", "0.3", "--quiet"],
    ],
)
def test_cli_bout_en_bout(argv: list[str], channel: str, capsys) -> None:
    """Chaque sous-commande doit tourner de bout en bout sur le bus virtuel."""
    code = cli_main(["--interface", "virtual", "--channel", channel, *argv])
    output = capsys.readouterr().out
    assert code in (0, 1)  # 1 = verdict non prononcé, pas un plantage
    assert output.strip()


def test_cli_ecrit_un_rapport(channel: str, tmp_path: Path, capsys) -> None:
    cli_main(
        [
            "--interface",
            "virtual",
            "--channel",
            channel,
            "--simulate",
            "--report",
            str(tmp_path),
            "arbitration",
            "--cycles",
            "5",
        ]
    )
    capsys.readouterr()
    produits = sorted(tmp_path.glob("T3-*"))
    assert len(produits) == 2  # un .md et un .tex
    assert "NON CONCLUANT" in produits[0].read_text(encoding="utf-8")


def test_cli_refuse_simulate_hors_bus_virtuel() -> None:
    with pytest.raises(SystemExit, match="virtual"):
        cli_main(["--interface", "slcan", "--simulate", "busload"])
