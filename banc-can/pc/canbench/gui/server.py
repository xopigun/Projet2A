"""Serveur local de l'interface graphique.

Architecture
------------
Un seul objet :class:`BenchService` possède la connexion au bus. Un fil
d'écoute lit les trames en continu et tient l'état affiché : trames décodées,
débit, charge, état des nœuds tiré de leurs heartbeats.

Les tests (T3, T4, T6) réutilisent **exactement** les fonctions de la ligne de
commande (`arbitration.run`, `encoding.run`, `faults.run_logical`) : l'interface
n'a aucune logique de test propre, elle ne fait qu'afficher. Pendant un test,
le fil d'écoute s'efface, car une interface réelle (CANable) ne s'ouvre qu'une
fois et le test a besoin de toutes les trames.

Honnêteté des verdicts
----------------------
Sur bus virtuel, la page l'affiche en permanence et chaque verdict porte la
mention « simulation » : le simulateur reproduit le comportement attendu des
nœuds, il ne démontre rien sur le bus (voir `simulator.py`).
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.parse
import webbrowser
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .. import arbitration, decode, encoding, faults, icd_gen, physical, report
from ..bus import Bench
from ..simulator import NodeSimulator

STATIC_DIR = Path(__file__).with_name("static")
DEFAULT_PORT = 8765

#: Fenêtre de calcul du débit et de la charge, en secondes.
RATE_WINDOW = 1.0

ROLES = {
    "energy_command": "Commande énergie",
    "imu_speed": "IMU + vitesse",
    "temp_battery": "Température batterie",
    "faulty": "Nœud fautif",
}
BOARDS = {"nucleo_g431kb": "Nucleo-G431KB", "bluepill_f103": "Blue Pill F103"}


class BenchService:
    """Connexion au bus, simulateur éventuel, état affiché et tests."""

    def __init__(
        self,
        interface: str = "virtual",
        channel: str | None = None,
        bitrate: int = icd_gen.BITRATE,
        profile: str = icd_gen.DEFAULT_PROFILE,
        simulate: bool = True,
    ) -> None:
        self.interface = interface
        self.virtual = interface == "virtual"
        self.bitrate = bitrate
        self.profile = profile
        self.started = time.monotonic()

        self.simulator: NodeSimulator | None = None
        if simulate and self.virtual:
            self.simulator = NodeSimulator(
                interface=interface, channel=channel, profile=profile
            ).start()
            time.sleep(0.15)

        self.bench = Bench(interface=interface, channel=channel, bitrate=bitrate, profile=profile)

        self._bus_lock = threading.Lock()  # un seul utilisateur du bus à la fois
        self._state_lock = threading.Lock()
        self._stop = threading.Event()

        self._frames: deque[dict] = deque(maxlen=60)
        self._window: deque[tuple[float, int]] = deque()  # (instant, dlc)
        self._counts: dict[int, int] = {}
        self._heartbeats: dict[int, dict] = {}
        self._heartbeat_seen: dict[int, float] = {}
        self._last_tx: dict[str, float] = {}
        self._total = 0
        self._load_history: deque[float] = deque(maxlen=120)

        self.busy: str | None = None
        self.last_result: dict | None = None
        self._heartbeat_base = icd_gen.PROFILES[profile]["heartbeat_base"]
        self._senders = {can_id: meta["sender"] for can_id, meta in icd_gen.FRAMES.items()}
        #: Identifiants de faute (hors ICD) et nœud qui les émet, pour l'affichage.
        self._fault_ids: dict[int, str] = {}

        self._listener = threading.Thread(target=self._listen, name="gui-ecoute", daemon=True)
        self._listener.start()
        self._sampler = threading.Thread(target=self._sample, name="gui-charge", daemon=True)
        self._sampler.start()

    # -- cycle de vie -------------------------------------------------------

    def close(self) -> None:
        self._stop.set()
        self._listener.join(timeout=1.0)
        self.bench.close()
        if self.simulator is not None:
            self.simulator.stop()

    # -- écoute -------------------------------------------------------------

    def _listen(self) -> None:
        while not self._stop.is_set():
            if not self._bus_lock.acquire(timeout=0.1):
                continue  # un test occupe le bus
            try:
                frame = self.bench.recv(timeout=0.05)
            finally:
                self._bus_lock.release()
            if frame is not None:
                self._note(frame)

    def _note(self, frame) -> None:
        now = time.monotonic()
        decoded = decode.decode(frame, self.profile)
        sender = self._sender_of(frame.can_id)
        with self._state_lock:
            self._total += 1
            self._counts[frame.can_id] = self._counts.get(frame.can_id, 0) + 1
            self._window.append((now, len(frame.data)))
            if sender:
                self._last_tx[sender] = now
            name = decoded.name
            if not decoded.known and frame.can_id in self._fault_ids:
                name = "faute (hors ICD)"
            self._frames.appendleft(
                {
                    "t": round(now - self.started, 3),
                    "id": f"0x{frame.can_id:03X}",
                    "name": name,
                    "sender": sender or "?",
                    "known": decoded.known,
                    "dlc_ok": decoded.dlc_ok,
                    "classic": frame.is_classic_2a,
                    "data": frame.data.hex(" ").upper(),
                    "signals": {k: _round(v) for k, v in decoded.signals.items()},
                }
            )
            node_id = frame.can_id - self._heartbeat_base
            if 1 <= node_id <= 15 and len(frame.data) == 8:
                beat = icd_gen.Heartbeat.unpack(frame.data)
                self._heartbeats[node_id] = {
                    "state": beat.ctrl_state,
                    "tec": beat.tec,
                    "rec": beat.rec,
                    "lec": beat.last_error_code,
                    "clock_not_qualified": bool(beat.clock_not_qualified),
                    "fault_mode_active": bool(beat.fault_mode_active),
                    "silent_mode": bool(beat.silent_mode),
                    "mode": beat.current_mode,
                    "rx_fifo_lost": beat.rx_fifo_lost,
                    "ring_overflow": beat.ring_overflow,
                    "non_classic_rx": beat.non_classic_rx,
                    "ext_id_rx": beat.ext_id_rx,
                }
                self._heartbeat_seen[node_id] = now

    def _sender_of(self, can_id: int) -> str | None:
        sender = self._senders.get(can_id) or self._fault_ids.get(can_id)
        if sender is not None:
            return sender
        node_id = can_id - self._heartbeat_base
        return f"N{node_id}" if 1 <= node_id <= 15 else None

    def _sample(self) -> None:
        """Relève la charge toutes les 250 ms, pour la courbe de la page."""
        while not self._stop.wait(0.25):
            self._load_history.append(self._rates()["load"])

    def _rates(self) -> dict:
        now = time.monotonic()
        with self._state_lock:
            while self._window and now - self._window[0][0] > RATE_WINDOW:
                self._window.popleft()
            frames = len(self._window)
            bits = sum(decode.frame_bits(dlc) for _, dlc in self._window)
        return {"fps": frames / RATE_WINDOW, "load": bits / RATE_WINDOW / self.bitrate}

    # -- état pour la page ----------------------------------------------------

    def state(self) -> dict:
        now = time.monotonic()
        rates = self._rates()
        with self._state_lock:
            nodes = []
            for entry in icd_gen.NODES:
                node_id = entry["node_id"]
                beat = self._heartbeats.get(node_id)
                seen = self._heartbeat_seen.get(node_id)
                nodes.append(
                    {
                        "id": node_id,
                        "name": entry["name"],
                        "role": ROLES.get(entry["role"], entry["role"]),
                        "board": BOARDS.get(entry["board"], entry["board"]),
                        "contender": entry["contender"],
                        "online": seen is not None and now - seen < 2.0,
                        "heartbeat": beat,
                        "mode_name": faults.MODE_NAMES.get(beat["mode"], "?") if beat else None,
                        "tx_age": round(now - self._last_tx[entry["name"]], 3)
                        if entry["name"] in self._last_tx
                        else None,
                    }
                )
            counts = [
                {
                    "id": f"0x{can_id:03X}",
                    "name": (icd_gen.FRAMES.get(can_id) or {}).get("name", "<inconnu>"),
                    "count": count,
                }
                for can_id, count in sorted(self._counts.items())
            ]
            pc_age = self._last_tx.get("PC")
            return {
                "virtual": self.virtual,
                "simulated": self.simulator is not None,
                "interface": self.interface,
                "bitrate": self.bitrate,
                "profile": self.profile,
                "uptime": round(now - self.started, 1),
                "total": self._total,
                "fps": round(rates["fps"], 1),
                "load": round(rates["load"] * 100, 2),
                "load_history": [round(x * 100, 2) for x in self._load_history],
                "nodes": nodes,
                "pc_tx_age": round(now - pc_age, 3) if pc_age is not None else None,
                "frames": list(self._frames)[:30],
                "counts": counts,
                "non_conformity": self.bench.non_conformity.total,
                "busy": self.busy,
                "has_result": self.last_result is not None,
            }

    # -- tests ----------------------------------------------------------------

    def run_test(self, name: str, params: dict) -> bool:
        """Lance un test en arrière-plan ; faux si un test est déjà en cours."""
        runners = {
            "arbitration": self._run_arbitration,
            "encoding": self._run_encoding,
            "faults": self._run_faults,
        }
        if name not in runners or self.busy is not None:
            return False
        self.busy = name
        threading.Thread(target=self._guarded, args=(runners[name], params), daemon=True).start()
        return True

    def _guarded(self, runner, params: dict) -> None:
        try:
            with self._bus_lock:
                self.last_result = runner(params)
        except Exception as error:  # noqa: BLE001 — l'erreur est affichée telle quelle
            self.last_result = {"test": self.busy, "error": f"{type(error).__name__} : {error}"}
        finally:
            self.busy = None

    def _quiet_simulator(self):
        """Suspend le trafic périodique simulé : un cycle ne doit porter que GO
        puis les contendants, comme sur les nœuds réels (voir arbitration.py)."""
        return _PeriodicPause(self.simulator)

    def _run_arbitration(self, params: dict) -> dict:
        cycles = max(1, min(int(params.get("cycles", 200)), 5000))
        with self._quiet_simulator():
            result = arbitration.run(self.bench, cycles=cycles)
        text = arbitration.render(result, virtual=self.virtual)
        rows = [
            {
                "sender": row["sender"],
                "name": row["name"],
                "id": f"0x{row['can_id']:03X}",
                "expected_rank": row["expected_rank"],
                "won": row["won"],
                "lost": row["lost"],
                "histogram": {str(k): v for k, v in sorted(row["histogram"].items())},
                "ok": row["always_expected"],
            }
            for row in result.stats()
        ]
        invalid = [f"cycle {c.index} : {c.reason}" for c in result.cycles if not c.valid][:5]
        return self._finish(
            "T3",
            "Arbitrage ARM/GO",
            text,
            result.passed,
            clock=result.clock_warnings,
            losses=result.loss_warnings,
            details={
                "cycles": len(result.cycles),
                "valid": len(result.valid_cycles),
                "invalid": invalid,
                "rows": rows,
                "max_gap_us": round(result.max_gap_us, 1),
            },
        )

    def _run_encoding(self, params: dict) -> dict:
        duration = max(0.5, min(float(params.get("duration", 2.0)), 30.0))
        result = encoding.run(self.bench, duration=duration)
        text = encoding.render(result, virtual=self.virtual)
        rows = [
            {
                "name": f.name,
                "id": f"0x{f.can_id:03X}",
                "observed": f.observed,
                "matched": f.matched,
                "dlc_errors": f.dlc_errors,
                "ok": f.passed,
            }
            for f in result.frames
        ]
        return self._finish("T4", "Encodage de l'ICD", text, result.passed, details={"rows": rows})

    def _run_faults(self, params: dict) -> dict:
        node = int(params.get("node", 4))
        self._fault_ids[0x400] = f"N{node}"  # identifiant inondé par run_logical
        result = faults.run_logical(self.bench, target_node=node)
        text = faults.render(result, virtual=self.virtual)
        rows = [
            {
                "name": step.name,
                "before": round(step.before.frames_per_s, 1),
                "after": round(step.after.frames_per_s, 1),
                "ok": step.passed,
                "detail": step.detail,
            }
            for step in result.steps
        ]
        return self._finish(
            "T6",
            f"Fautes logicielles sur N{node}",
            text,
            result.passed,
            details={"rows": rows},
        )

    def _finish(
        self,
        test: str,
        title: str,
        text: str,
        passed: bool,
        *,
        clock: list[str] | None = None,
        losses: list[str] | None = None,
        details: dict | None = None,
    ) -> dict:
        blockers = report.blockers_from(
            virtual=self.virtual, clock_warnings=clock or [], loss_warnings=losses or []
        )
        entry = report.Report(
            test=test, result_text=text, passed=passed, virtual=self.virtual, blockers=blockers
        )
        return {
            "test": test,
            "title": title,
            "passed": passed,
            "verdict": entry.verdict,
            "blockers": blockers,
            "text": text,
            "markdown": entry.markdown(),
            "details": details or {},
            "finished": time.strftime("%H:%M:%S"),
        }

    # -- injection manuelle ---------------------------------------------------

    def inject(self, node: int, mode: int, duration_ms: int, param: int) -> None:
        with self._bus_lock:
            if mode == faults.Mode.NORMAL or duration_ms == 0:
                faults.revoke(self.bench, node)
            else:
                self._fault_ids[param] = f"N{node}"
                faults.send_cfg(self.bench, node, mode, duration_ms=duration_ms, param=param)


class _PeriodicPause:
    """Contexte qui suspend le trafic périodique du simulateur, s'il y en a un."""

    def __init__(self, simulator: NodeSimulator | None) -> None:
        self.simulator = simulator
        self.previous = True

    def __enter__(self) -> None:
        if self.simulator is not None:
            self.previous = self.simulator.options.periodic_app
            self.simulator.options.periodic_app = False
            time.sleep(0.05)

    def __exit__(self, *_exc) -> None:
        if self.simulator is not None:
            self.simulator.options.periodic_app = self.previous


def _round(value):
    return round(value, 4) if isinstance(value, float) else value


# ---------------------------------------------------------------------------
#  Application : connexion courante, changement de connexion, veille
# ---------------------------------------------------------------------------

#: Interfaces proposées dans la fenêtre, avec le module python-can requis.
INTERFACES = {
    "virtual": {"label": "Simulation (aucun matériel)", "module": None, "channel": False},
    "gs_usb": {
        "label": "CANable 2.0 — firmware candleLight (gs_usb)",
        "module": "gs_usb",
        "channel": False,
    },
    "slcan": {"label": "CANable — firmware slcan (port COM)", "module": "serial", "channel": True},
}


def usb_backend():
    """Moteur libusb pour pyusb, ou None.

    gs_usb passe par pyusb, qui n'embarque pas la bibliothèque système libusb :
    sous Windows elle est fournie par le paquet ``libusb-package`` s'il est
    installé. Sans elle, toute ouverture du CANable en candleLight échoue.
    """
    try:
        import usb.backend.libusb1 as libusb1
    except ImportError:
        return None
    try:
        import libusb_package
    except ImportError:
        return libusb1.get_backend()
    # python-can ouvre le CANable par usb.core.find() sans préciser de moteur :
    # pyusb cherche alors libusb dans le PATH. On y ajoute donc le dossier de la
    # bibliothèque fournie par libusb-package.
    library = getattr(libusb_package, "get_library_path", lambda: None)()
    if library is not None:
        folder = str(Path(library).parent)
        if folder not in os.environ.get("PATH", ""):
            os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")
    return libusb1.get_backend(find_library=libusb_package.find_library)


def interface_status(name: str) -> tuple[bool, str]:
    """Disponibilité d'une interface et, sinon, la raison à afficher."""
    module = INTERFACES[name]["module"]
    if module is None:
        return True, ""
    try:
        __import__(module)
    except ImportError:
        return False, "pilote non inclus dans cette version"
    if name == "gs_usb" and usb_backend() is None:
        return False, "bibliothèque libusb absente de ce PC"
    return True, ""


def interface_available(name: str) -> bool:
    """Vrai si le pilote python-can de cette interface est utilisable."""
    return interface_status(name)[0]


def serial_ports() -> list[str]:
    """Ports série présents, pour le CANable en slcan ; vide sans pyserial."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [port.device for port in list_ports.comports()]


class Application:
    """Tient le service courant ; permet d'en changer depuis la fenêtre."""

    def __init__(self, service: BenchService) -> None:
        self.service = service
        self._lock = threading.Lock()
        self.last_poll: float | None = None
        self.connect_error: str | None = None

    def connect(self, interface: str, channel: str | None) -> bool:
        """Ferme la connexion courante et en ouvre une autre.

        En cas d'échec — CANable absent, pilote manquant — on revient à la
        simulation plutôt que de laisser la fenêtre sans rien à afficher, et
        l'erreur est affichée telle quelle.
        """
        if interface not in INTERFACES:
            self.connect_error = f"interface inconnue : {interface}"
            return False
        with self._lock:
            previous = self.service
            if previous.busy is not None:
                self.connect_error = "un test est en cours"
                return False
            previous.close()
            try:
                self.service = BenchService(
                    interface=interface,
                    channel=channel or None,
                    bitrate=previous.bitrate,
                    profile=previous.profile,
                    simulate=interface == "virtual",
                )
                self.connect_error = None
                return True
            except Exception as error:  # noqa: BLE001 — l'erreur est affichée telle quelle
                self.connect_error = f"{type(error).__name__} : {error}"
                self.service = BenchService(
                    bitrate=previous.bitrate, profile=previous.profile, simulate=True
                )
                return False

    def close(self) -> None:
        self.service.close()


# ---------------------------------------------------------------------------
#  HTTP
# ---------------------------------------------------------------------------


def make_handler(target: BenchService | Application):
    app = target if isinstance(target, Application) else Application(target)

    class Handler(BaseHTTPRequestHandler):
        server_version = "canbench-gui"

        def log_message(self, *_args) -> None:  # silence : la console reste lisible
            pass

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload, status: int = HTTPStatus.OK) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            try:
                return json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return {}

        def do_GET(self) -> None:  # noqa: N802 — nom imposé par http.server
            service = app.service
            if self.path in ("/", "/index.html"):
                page = (STATIC_DIR / "index.html").read_bytes()
                self._send(HTTPStatus.OK, page, "text/html; charset=utf-8")
            elif self.path == "/api/state":
                app.last_poll = time.monotonic()
                state = service.state()
                state["connect_error"] = app.connect_error
                self._json(state)
            elif self.path == "/api/result":
                self._json(service.last_result or {})
            elif self.path == "/api/icd":
                self._json(
                    {
                        "modes": {str(k): v for k, v in faults.MODE_NAMES.items()},
                        "contenders": icd_gen.CONTENDERS,
                        "frames": [meta["name"] for _, meta in sorted(icd_gen.FRAMES.items())],
                    }
                )
            elif self.path.startswith("/api/physical"):
                query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                name = (query.get("name") or ["ENERGY_COMMAND"])[0]
                try:
                    self._json(physical.describe(name, service.profile))
                except KeyError:
                    self._json({"error": f"trame inconnue : {name}"}, HTTPStatus.NOT_FOUND)
            elif self.path == "/api/interfaces":
                self._json(
                    {
                        "interfaces": [
                            {
                                "name": name,
                                "label": spec["label"],
                                "channel": spec["channel"],
                                "available": status[0],
                                "reason": status[1],
                            }
                            for name, spec in INTERFACES.items()
                            for status in (interface_status(name),)
                        ],
                        "ports": serial_ports(),
                        "current": service.interface,
                    }
                )
            else:
                self._send(HTTPStatus.NOT_FOUND, b"introuvable", "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            body = self._body()
            service = app.service
            if self.path.startswith("/api/run/"):
                started = service.run_test(self.path.rsplit("/", 1)[-1], body)
                self._json({"started": started}, HTTPStatus.OK if started else HTTPStatus.CONFLICT)
            elif self.path == "/api/fault":
                try:
                    service.inject(
                        node=int(body.get("node", 4)),
                        mode=int(body.get("mode", 0)),
                        duration_ms=int(body.get("duration_ms", 2000)),
                        param=int(body.get("param", 0x400)),
                    )
                except (TypeError, ValueError) as error:
                    self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                    return
                self._json({"ok": True})
            elif self.path == "/api/connect":
                ok = app.connect(str(body.get("interface", "virtual")), body.get("channel"))
                self._json({"ok": ok, "error": app.connect_error})
            else:
                self._send(HTTPStatus.NOT_FOUND, b"introuvable", "text/plain")

    Handler.app = app
    return Handler


class LocalServer(ThreadingHTTPServer):
    """Serveur HTTP qui refuse un port déjà occupé.

    ``http.server`` active ``SO_REUSEADDR`` ; sous Windows, cette option permet à
    un second programme d'écouter sur un port **déjà pris**, et les requêtes vont
    alors à l'un ou l'autre au hasard. Deux instances du logiciel ouvertes en même
    temps se répondraient l'une à la place de l'autre.
    """

    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True


def start_server(
    interface: str = "virtual",
    channel: str | None = None,
    bitrate: int = icd_gen.BITRATE,
    profile: str = icd_gen.DEFAULT_PROFILE,
    simulate: bool = True,
    port: int = DEFAULT_PORT,
) -> tuple[ThreadingHTTPServer, Application]:
    """Crée le service et le serveur HTTP ; le port 0 en choisit un libre."""
    app = Application(BenchService(interface, channel, bitrate, profile, simulate))
    try:
        server = LocalServer(("127.0.0.1", port), make_handler(app))
    except OSError:
        # Port déjà pris (une autre instance ouverte) : on en prend un libre.
        server = LocalServer(("127.0.0.1", 0), make_handler(app))
    return server, app


def serve(
    interface: str = "virtual",
    channel: str | None = None,
    bitrate: int = icd_gen.BITRATE,
    profile: str = icd_gen.DEFAULT_PROFILE,
    simulate: bool = True,
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
) -> None:
    """Démarre le service et le serveur HTTP local, jusqu'à Ctrl-C."""
    server, app = start_server(interface, channel, bitrate, profile, simulate, port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    mode = "SIMULATION (bus virtuel)" if app.service.virtual else f"banc réel ({interface})"
    print(f"Interface du banc CAN : {url}")
    print(f"Mode : {mode}")
    print("Fermer cette fenêtre, ou Ctrl-C, pour arrêter.")
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
    finally:
        server.server_close()
        app.close()


__all__ = ["Application", "BenchService", "serve", "start_server"]
