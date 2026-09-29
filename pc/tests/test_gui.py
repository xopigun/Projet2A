"""Tests de l'interface graphique : service, API HTTP et page."""

from __future__ import annotations

import json
import threading
import time
import urllib.request
import uuid
from http.server import ThreadingHTTPServer

import pytest

from canbench.gui.server import BenchService, make_handler


@pytest.fixture
def service():
    # Canal virtuel propre au test : aucune interférence avec les autres tests.
    svc = BenchService(interface="virtual", channel=f"gui-{uuid.uuid4().hex}", simulate=True)
    yield svc
    svc.close()


def _wait(predicate, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("délai dépassé")


def test_etat_reflete_les_noeuds_simules(service: BenchService) -> None:
    _wait(lambda: all(n["online"] for n in service.state()["nodes"]))
    state = service.state()

    assert state["virtual"] and state["simulated"]
    assert [n["name"] for n in state["nodes"]] == ["N1", "N2", "N3", "N4"]
    assert state["total"] > 0
    assert state["frames"], "aucune trame décodée"
    assert all(n["heartbeat"]["state"] == 0 for n in state["nodes"])


def test_arbitrage_lance_depuis_l_interface(service: BenchService) -> None:
    assert service.run_test("arbitration", {"cycles": 20})
    assert not service.run_test("encoding", {}), "un seul test à la fois"
    _wait(lambda: service.busy is None)

    result = service.last_result
    assert result["test"] == "T3"
    assert result["passed"], result["text"]
    # Bus virtuel : jamais de réussite affichée comme preuve.
    assert result["verdict"] == "NON CONCLUANT"
    assert [row["expected_rank"] for row in result["details"]["rows"]] == [1, 2, 3]
    assert all(row["ok"] for row in result["details"]["rows"])


def test_injection_d_une_faute_attribuee_au_noeud(service: BenchService) -> None:
    _wait(lambda: service.state()["total"] > 0)
    service.inject(node=4, mode=1, duration_ms=800, param=0x400)
    _wait(lambda: any(f["id"] == "0x400" for f in service.state()["frames"]))

    frame = next(f for f in service.state()["frames"] if f["id"] == "0x400")
    assert frame["sender"] == "N4"
    service.inject(node=4, mode=0, duration_ms=0, param=0)


def test_api_http_et_page(service: BenchService) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        page = urllib.request.urlopen(f"{base}/").read().decode("utf-8")
        assert "Banc de test CAN" in page

        state = json.loads(urllib.request.urlopen(f"{base}/api/state").read())
        assert state["bitrate"] == 500000

        icd = json.loads(urllib.request.urlopen(f"{base}/api/icd").read())
        assert icd["modes"]["1"] == "babbling idiot"
    finally:
        server.shutdown()
        server.server_close()
