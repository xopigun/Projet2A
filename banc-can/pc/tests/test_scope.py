"""Tests du décodage d'une capture d'oscilloscope (canbench.scope)."""

from __future__ import annotations

import random

import pytest

from canbench import physical, scope


def waveform(
    frames: list[tuple[int, bytes]],
    *,
    bit_s: float = 2e-6,
    sample_s: float = 0.2e-6,
    high: float = 3.3,
    noise: float = 0.0,
    rise_s: float = 0.0,
    gap_bits: int = 30,
    corrupt: tuple[int, int] | None = None,
    acknowledged: bool = True,
    seed: int = 1,
) -> tuple[list[float], list[float]]:
    """Capture synthétique : trames bout à bout, fronts finis, bruit gaussien."""
    rng = random.Random(seed)
    bits: list[int] = [1] * 10
    for frame_number, (can_id, data) in enumerate(frames):
        frame = physical.build_frame(can_id, data, acknowledged=acknowledged)
        values = [b.value for b in frame]
        if corrupt is not None and corrupt[0] == frame_number:
            values[corrupt[1]] ^= 1
        bits.extend(values)
        bits.extend([1] * gap_bits)

    times: list[float] = []
    volts: list[float] = []
    n_samples = int(len(bits) * bit_s / sample_s)
    previous_level = high
    for k in range(n_samples):
        t = k * sample_s
        level = high if bits[min(int(t / bit_s), len(bits) - 1)] else 0.0
        if rise_s > 0.0:
            # Filtre du premier ordre : fronts arrondis, comme les tirages internes.
            alpha = min(1.0, sample_s / rise_s)
            level = previous_level + alpha * (level - previous_level)
            previous_level = level
        times.append(t)
        volts.append(level + rng.gauss(0.0, noise))
    return times, volts


def test_trame_n1_test_est_retrouvee() -> None:
    times, volts = waveform([(0x0F0, b"Test")])
    frames = scope.decode(times, volts)

    assert len(frames) == 1
    f = frames[0]
    assert f.can_id == 0x0F0
    assert f.dlc == 4
    assert f.data == b"Test"
    assert f.text == "Test"
    assert f.crc_ok
    assert f.acked is True
    assert f.bit_time_s == pytest.approx(2e-6, rel=0.05)


def test_deux_trames_n1_puis_n2() -> None:
    times, volts = waveform([(0x0F0, b"Test"), (0x20F, b"Test")])
    frames = scope.decode(times, volts)

    assert [f.can_id for f in frames] == [0x0F0, 0x20F]
    assert all(f.data == b"Test" and f.crc_ok for f in frames)


def test_trame_non_acquittee_est_signalee() -> None:
    times, volts = waveform([(0x0F0, b"Test")], acknowledged=False)
    frames = scope.decode(times, volts)

    assert frames[0].crc_ok
    assert frames[0].acked is False


@pytest.mark.parametrize("drift", [0.98, 0.99, 1.0, 1.01, 1.02])
def test_derive_d_horloge_hsi_n_empeche_pas_le_decodage(drift: float) -> None:
    """±1 % d'écart de débit (HSI) déplace le dernier bit de presque un bit."""
    times, volts = waveform([(0x0F0, b"Test")], bit_s=2e-6 * drift)
    frames = scope.decode(times, volts)

    assert len(frames) == 1
    assert frames[0].data == b"Test"
    assert frames[0].crc_ok


def test_bruit_et_fronts_arrondis() -> None:
    times, volts = waveform([(0x20F, b"Test")], noise=0.08, rise_s=0.3e-6)
    frames = scope.decode(times, volts)

    assert len(frames) == 1
    assert frames[0].data == b"Test"
    assert frames[0].crc_ok


@pytest.mark.parametrize("rise_us", [0.5, 0.8, 1.2])
def test_front_montant_tres_lent_du_bus_direct(rise_us: float) -> None:
    """Capture réelle du banc : retour au 1 par la résistance de tirage (lent).

    Le seuil est franchi en retard : les paliers bas paraissent trop longs et les
    hauts trop courts d'environ un demi-bit. Une capture à -1 V / +2 V, 10 MSa/s,
    déclenchait « aucune trame » avant l'ajustement du décalage des fronts.
    """
    times, volts = waveform(
        [(0x20F, b"Test")], high=3.0, rise_s=rise_us * 1e-6, noise=0.04, sample_s=0.1e-6
    )
    volts = [v - 1.0 for v in volts]  # niveaux -1 V / +2 V
    frames = scope.decode(times, volts)

    assert len(frames) == 1
    assert frames[0].data == b"Test"
    assert frames[0].crc_ok


def test_sonde_x10_reglee_en_1_pour_1_se_decode_quand_meme() -> None:
    """Le seuil se place au milieu de l'excursion : l'échelle n'a pas d'importance."""
    times, volts = waveform([(0x0F0, b"Test")], high=0.33, noise=0.005)
    frames = scope.decode(times, volts)

    assert len(frames) == 1
    assert frames[0].data == b"Test"
    assert frames[0].crc_ok


def test_bit_inverse_fait_echouer_le_crc() -> None:
    # Bit 45 : au milieu des données. Un bit inversé ne doit jamais passer pour valide.
    times, volts = waveform([(0x0F0, b"Test")], corrupt=(0, 45))
    frames = scope.decode(times, volts)

    assert all(not f.crc_ok or f.problem for f in frames)


def test_signal_plat_est_refuse() -> None:
    times = [i * 1e-7 for i in range(1000)]
    volts = [0.001 * (i % 2) for i in range(1000)]
    with pytest.raises(ValueError, match="plat"):
        scope.decode(times, volts)


def test_aucune_trame_dans_du_bruit() -> None:
    rng = random.Random(3)
    times = [i * 1e-7 for i in range(5000)]
    volts = [rng.gauss(0.0, 0.3) for _ in times]
    assert scope.decode(times, volts) == []


def test_lecture_csv_au_format_keysight(tmp_path) -> None:
    times, volts = waveform([(0x0F0, b"Test")], sample_s=0.4e-6)
    path = tmp_path / "scope_1.csv"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x-axis,1\nsecond,Volt\n")
        for t, v in zip(times, volts, strict=True):
            handle.write(f"{t:.9e},{v:.6e}\n")

    t2, v2 = scope.read_csv(path)
    assert len(t2) == len(times)
    frames = scope.decode(t2, v2)
    assert frames[0].data == b"Test"


def test_lecture_csv_separateur_point_virgule_et_virgule_decimale(tmp_path) -> None:
    times, volts = waveform([(0x0F0, b"Test")], sample_s=0.4e-6)
    path = tmp_path / "scope_fr.csv"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("Temps;Voie 1\n")
        for t, v in zip(times, volts, strict=True):
            handle.write(f"{t:.9e}".replace(".", ",") + ";" + f"{v:.6e}".replace(".", ",") + "\n")

    t2, v2 = scope.read_csv(path)
    assert scope.decode(t2, v2)[0].data == b"Test"


def test_cli_affiche_la_trame(tmp_path, capsys) -> None:
    times, volts = waveform([(0x0F0, b"Test")], sample_s=0.4e-6)
    path = tmp_path / "scope_1.csv"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("Time (s),Channel 1 (V)\n")
        for t, v in zip(times, volts, strict=True):
            handle.write(f"{t:.9e},{v:.6e}\n")

    assert scope.main([str(path)]) == 0
    out = capsys.readouterr().out
    assert "id=0x0F0" in out
    assert "« Test »" in out
    assert "CRC ok" in out
