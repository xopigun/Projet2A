"""Tests de la trame CAN au niveau du bit (chronogrammes)."""

from __future__ import annotations

import pytest

from canbench import decode, icd_gen, physical


def test_crc15_valeur_de_controle_du_catalogue() -> None:
    """Valeur de contrôle publiée pour CRC-15/CAN : 0x059E sur « 123456789 »."""
    bits = [b for byte in b"123456789" for b in physical._bits(byte, 8)]
    assert physical.crc15(bits) == 0x059E


def test_crc_d_une_trame_valide_se_verifie_a_zero() -> None:
    """Propriété d'un CRC : recalculé sur les données suivies du CRC, il vaut 0."""
    frame = physical.build_frame(0x100, bytes([0x12, 0x34, 0x56]))
    bits = physical.destuff(frame)
    assert physical.crc15(bits) == 0


def test_jamais_six_bits_identiques_dans_la_zone_bourree() -> None:
    frame = physical.build_frame(0x000, bytes(8))  # zéros : bourrage maximal
    zone = [
        b.value for b in frame if b.field in ("SOF", "ID", "RTR", "IDE", "r0", "DLC", "DATA", "CRC")
    ]
    run = longest = 1
    for previous, current in zip(zone, zone[1:], strict=False):
        run = run + 1 if current == previous else 1
        longest = max(longest, run)
    assert longest <= 5
    assert sum(b.stuff for b in frame) > 0


def test_le_bourrage_se_retire_sans_perte() -> None:
    data = bytes([0xFF, 0x00, 0xAA])
    frame = physical.build_frame(0x7FF, data)
    bits = physical.destuff(frame)
    assert bits[1:12] == physical._bits(0x7FF, 11)
    assert bits[19:43] == [b for byte in data for b in physical._bits(byte, 8)]


@pytest.mark.parametrize("dlc", [0, 1, 4, 8])
def test_longueur_dans_la_borne_du_calcul_de_charge(dlc: int) -> None:
    """La trame réelle ne dépasse jamais le pire cas utilisé pour la charge du bus."""
    for can_id in (0x000, 0x100, 0x555, 0x7FF):
        frame = physical.build_frame(can_id, bytes([0x00] * dlc))
        assert len(frame) <= decode.frame_bits(dlc, worst_case=True)
        assert len(frame) >= decode.frame_bits(dlc, worst_case=False)


def test_acquittement_impose_par_le_recepteur() -> None:
    ack = next(b for b in physical.build_frame(0x100, b"\x01") if b.field == "ACK")
    assert ack.value == 0 and ack.tx_value == 1  # l'émetteur laisse récessif
    unacked = next(
        b for b in physical.build_frame(0x100, b"\x01", acknowledged=False) if b.field == "ACK"
    )
    assert unacked.value == 1


def test_description_des_trames_de_l_icd() -> None:
    for meta in icd_gen.FRAMES.values():
        info = physical.describe(meta["name"])
        assert info["bits"][0]["field"] == "SOF"
        assert len(bytes.fromhex(info["data"])) == meta["dlc"]


def test_constantes_du_tja1051_coherentes() -> None:
    t = physical.TJA1051
    assert t["canh_dom"] - t["canl_dom"] == pytest.approx(2.0)  # dans 1,5 à 3 V
    assert t["vth_min"] <= t["vth_rx"] <= t["vth_max"]
