"""Indicateurs de qualité et interface python-can de l'adaptateur ZLG (sans matériel)."""

from __future__ import annotations

import queue
import struct
import uuid

import pytest

from canbench import icd_gen
from canbench.bus import Frame
from canbench.quality import QualityTracker

zlg = pytest.importorskip("canbench.zlg_usbcan", reason="pyusb absent")
from canbench.zlg_bus import HardwareClock, ZlgBus, controller_state  # noqa: E402

HB_BASE = icd_gen.PROFILES[icd_gen.DEFAULT_PROFILE]["heartbeat_base"]


def _frame(t: float, can_id: int, data: bytes = bytes(8), error: bool = False) -> Frame:
    return Frame(timestamp=t, can_id=can_id, data=data, is_error_frame=error)


# -- régularité des trames ------------------------------------------------------


def test_periode_et_gigue_d_une_trame_reguliere() -> None:
    tracker = QualityTracker()
    for i in range(50):
        tracker.note(_frame(i * 0.020 + (0.0005 if i % 2 else 0), 0x100))
    row = tracker.summary()["ids"][0]
    assert row["name"] == "ENERGY_COMMAND"
    assert row["expected_ms"] == 20
    assert row["period_ms"] == pytest.approx(20, abs=0.05)
    assert row["jitter_ms"] == pytest.approx(0.5, abs=0.01)
    assert row["missed"] == 0 and not row["alert"]


def test_trames_manquees_estimees_et_signalees() -> None:
    tracker = QualityTracker()
    stamps = [0.00, 0.02, 0.04, 0.10, 0.12]  # 0,04 -> 0,10 : deux trames perdues
    for t in stamps:
        tracker.note(_frame(t, 0x200))
    summary = tracker.summary()
    assert summary["ids"][0]["missed"] == 2
    assert summary["missed"] == 2 and summary["alerts"] == 1


def test_noeud_trop_lent_signale_par_la_periode_pas_par_des_pertes() -> None:
    tracker = QualityTracker()
    stamps = [i * 0.031 for i in range(40)]  # 31 ms au lieu de 20 ms
    stamps += [stamps[-1] + 0.062]  # puis une vraie trame perdue
    for t in stamps:
        tracker.note(_frame(t, 0x100))
    row = tracker.summary()["ids"][0]
    assert row["missed"] == 1
    assert row["deviation_pct"] > 50 and row["alert"]


def test_heartbeat_attendu_a_500_ms_et_trame_evenementielle_sans_attente() -> None:
    tracker = QualityTracker()
    for i in range(3):
        tracker.note(_frame(i * 0.5, HB_BASE + 1))
        tracker.note(_frame(i * 0.7, 0x011))  # GO : pas de période attendue
    rows = {row["id"]: row for row in tracker.summary()["ids"]}
    assert rows[f"0x{HB_BASE + 1:03X}"]["expected_ms"] == 500
    assert rows["0x011"]["expected_ms"] is None and not rows["0x011"]["alert"]


def test_trames_d_erreur_comptees_a_part() -> None:
    tracker = QualityTracker()
    tracker.note(_frame(0.0, 0xE3, b"\xc0\x00\x80", error=True))
    summary = tracker.summary()
    assert summary["error_frames"] == 1 and summary["ids"] == []


def test_reprise_apres_interruption_sans_fausse_perte() -> None:
    tracker = QualityTracker()
    tracker.note(_frame(0.00, 0x100))
    tracker.note(_frame(0.02, 0x100))
    tracker.restart()  # un test a lu les trames entre-temps
    tracker.note(_frame(5.00, 0x100))
    assert tracker.summary()["ids"][0]["missed"] == 0


# -- adaptateur ZLG ---------------------------------------------------------------


def test_horloge_materielle_deroule_le_debordement() -> None:
    clock = HardwareClock()
    assert clock.convert(0xFFFF_FF00, now=100.0) == 100.0
    assert clock.convert(0x0000_0100, now=999.0) == pytest.approx(100.0 + 0x200 * 1e-4)


@pytest.mark.parametrize(
    ("rec", "tec", "state"),
    [
        (0, 0, "actif"),
        (96, 0, "avertissement"),
        (0, 128, "passif"),
        (0, 256, "bus-off"),
        (None, 0, "inconnu"),
    ],
)
def test_etat_du_controleur(rec, tec, state) -> None:
    assert controller_state(rec, tec) == state


class FakeZlg:
    """Remplace ZlgUsbCan : même interface, aucun accès USB."""

    def __init__(self, ack: int = 1) -> None:
        self.rx: queue.Queue = queue.Queue()
        self.ack = ack
        self.sent: list = []
        self.closed = False
        self.started: list[int] = []

    def board_info(self) -> dict:
        return {"firmware": "1.02", "serie": "TEST"}

    def init(self, bitrate, channel, listen_only=False) -> None:
        self.bitrate = bitrate

    def start(self, channel) -> bytes:
        self.started.append(channel)
        return b"\x12\x0e\x81\x00"

    def read_register(self, reg, channel=0) -> int:
        return {0x0E: 3, 0x0F: 0}[reg]

    def send(self, frames, channel=0) -> int:
        self.sent += frames
        return self.ack * len(frames)

    def close(self) -> None:
        self.closed = True

    def push(self, ticks: int, status: int, flags: int, ident: int, data: bytes) -> None:
        rec = struct.pack("<IBBBI", ticks, status, 0, flags, ident) + data.ljust(8, b"\0")
        self.rx.put(zlg.decode_record(rec))


def test_zlgbus_trames_horodatees_et_evenements() -> None:
    import can

    fake = FakeZlg()
    bus = ZlgBus(device=fake, poll=False)
    try:
        fake.push(1000, 0, 0x02, 0x123 << 5, b"\xab\xcd")
        fake.push(1200, 0, 0x02, 0x123 << 5, b"\xab\xce")
        fake.push(1300, 0xE3, 0x05, 0x0080_00C0, b"")  # erreur passive, REC=0, TEC=128
        first, second, event = (bus.recv(1.0) for _ in range(3))
        assert first.arbitration_id == 0x123 and bytes(first.data) == b"\xab\xcd"
        assert second.timestamp - first.timestamp == pytest.approx(0.020)
        assert event.is_error_frame and event.arbitration_id == 0xE3
        assert not event.is_extended_id
        quality = bus.quality()
        assert quality["events"] == {"erreur passive": 1}
        assert (quality["rec"], quality["tec"], quality["state"]) == (0, 128, "passif")
        assert quality["serial"] == "TEST"

        bus.send(can.Message(arbitration_id=0x010, data=b"\x01", is_extended_id=False))
        fake.ack = 0
        bus.send(can.Message(arbitration_id=0x010, data=b"\x02", is_extended_id=False))
        assert (bus.quality()["tx_ok"], bus.quality()["tx_failed"]) == (1, 1)
        assert fake.sent[0].can_id == 0x010 and fake.sent[0].data == b"\x01"
    finally:
        bus.shutdown()
    assert fake.closed


def test_bench_expose_la_qualite_de_l_adaptateur(monkeypatch) -> None:
    from canbench import bus as bus_module

    fake = FakeZlg()
    monkeypatch.setattr(zlg, "ZlgUsbCan", lambda: fake)
    with bus_module.Bench(interface="zlg") as bench:
        assert bench.adapter_quality()["adapter"] == "ZLG USBCAN-UC12"
        assert fake.started == [0] and fake.bitrate == 500_000
    assert fake.closed
    with bus_module.Bench(interface="virtual", channel=f"q-{uuid.uuid4().hex}") as bench:
        assert bench.adapter_quality() is None
