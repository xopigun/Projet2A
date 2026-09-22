"""Simulateur des nœuds N1 à N4, pour exécuter `canbench` sans matériel.

Il reproduit le comportement attendu des nœuds : réponse à ARM/GO, émission des
trames applicatives selon les séquences déterministes de l'ICD, heartbeat
périodique, et modes de faute pilotés par `BENCH_CFG`.

Ce que ce simulateur prouve, et ne prouve pas
---------------------------------------------

Il sert à **tester l'outillage PC**, pas le protocole CAN.

Le bus ``virtual`` de python-can est une simple diffusion en mémoire : il n'y a
ni arbitrage, ni acquittement, ni erreur de bit. Après GO, le simulateur émet les
trames contendantes **triées par identifiant croissant**, c'est-à-dire qu'il
*reproduit* le résultat qu'un arbitrage réel produirait — il ne le démontre pas.

Autrement dit, un `canbench arbitration` vert sur bus virtuel signifie « la
chaîne de mesure, le comptage des rangs et le rapport fonctionnent », et
strictement rien sur le comportement du bus. Seule l'exécution sur le banc réel,
avec le test T3, démontre l'arbitrage.

La même réserve vaut pour l'encodage : sur bus virtuel, c'est notre propre
encodeur qui alimente notre propre décodeur. La parité avec le code C embarqué
est établie ailleurs, par les vecteurs de référence.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from . import icd_gen
from .bus import Bench


@dataclass
class SimulatedNode:
    """État d'un nœud simulé."""

    node_id: int
    name: str
    contender: bool
    tx_id: int | None

    armed: bool = False
    arm_rx: int = 0
    step: int = 0
    mode: int = 0
    mode_deadline: float = 0.0
    #: Identifiant a inonder en mode « babbling idiot », issu de BENCH_CFG.param_u16.
    #: N4 n'etant pas contendant, il n'a pas de trame applicative propre : c'est ce
    #: parametre qui lui donne quelque chose a emettre.
    fault_param: int = 0
    frames_sent: int = 0

    # Compteurs remontés dans le heartbeat.
    tec: int = 0
    rec: int = 0
    ctrl_state: int = 0
    clock_not_qualified: bool = False
    rx_fifo_lost: int = 0
    ring_overflow: int = 0
    non_classic_rx: int = 0
    ext_id_rx: int = 0


@dataclass
class SimulatorOptions:
    """Réglages du simulateur, pour éprouver les cas dégradés."""

    #: Nœuds qui n'arment pas : reproduit un nœud ayant raté la fenêtre ARM.
    deaf_nodes: tuple[int, ...] = ()
    #: Nœuds signalant une horloge non conforme.
    unqualified_clock_nodes: tuple[int, ...] = ()
    #: Ordre d'émission forcé après GO ; None = ordre des identifiants (nominal).
    forced_order: tuple[int, ...] | None = None
    #: Période du heartbeat, en secondes.
    heartbeat_period: float = 0.5
    #: Période des trames applicatives, en secondes.
    app_period: float = 0.02
    #: Émettre les trames applicatives périodiquement, hors cycles ARM/GO.
    periodic_app: bool = True


class NodeSimulator:
    """Simule N1 à N4 sur un bus donné, dans un fil d'exécution séparé."""

    def __init__(
        self,
        interface: str = "virtual",
        channel: str | None = None,
        profile: str = icd_gen.DEFAULT_PROFILE,
        options: SimulatorOptions | None = None,
    ) -> None:
        self.options = options or SimulatorOptions()
        self.profile = profile
        self.bench = Bench(interface=interface, channel=channel, profile=profile)
        self.ids = self.bench.ids

        self.nodes: dict[int, SimulatedNode] = {}
        for entry in icd_gen.NODES:
            node_id = entry["node_id"]
            self.nodes[node_id] = SimulatedNode(
                node_id=node_id,
                name=entry["name"],
                contender=entry["contender"],
                tx_id=_contender_id(entry["name"]),
                clock_not_qualified=node_id in self.options.unqualified_clock_nodes,
            )

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        # Vrai entre la réception d'ARM et la libération des contendants. Pendant
        # cette fenêtre, ni heartbeat ni trame périodique ne doit s'intercaler :
        # ils fausseraient le comptage du rang. Le firmware fait de même.
        self._arbitration_active = False

    # -- cycle de vie -------------------------------------------------------

    def start(self) -> NodeSimulator:
        self._thread = threading.Thread(target=self._run, name="canbench-sim", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self.bench.close()

    def __enter__(self) -> NodeSimulator:
        return self.start()

    def __exit__(self, *_exc) -> None:
        self.stop()

    # -- boucle principale --------------------------------------------------

    def _run(self) -> None:
        next_heartbeat = time.monotonic() + self.options.heartbeat_period
        next_app = time.monotonic() + self.options.app_period

        while not self._stop.is_set():
            frame = self.bench.recv(timeout=0.005)
            if frame is not None:
                self._on_frame(frame)

            now = time.monotonic()

            # Pendant un cycle d'arbitrage, le bus ne doit porter que GO puis les
            # trames contendantes : tout le reste est suspendu.
            busy = self._arbitration_active

            if now >= next_heartbeat:
                if not busy:
                    self._emit_heartbeats()
                next_heartbeat = now + self.options.heartbeat_period

            if self.options.periodic_app and now >= next_app:
                if not busy:
                    self._emit_application()
                next_app = now + self.options.app_period

            self._expire_modes(now)

    # -- réception ----------------------------------------------------------

    def _on_frame(self, frame) -> None:
        with self._lock:
            if frame.can_id == self.ids["ARM"]:
                self._arbitration_active = True
                for node in self.nodes.values():
                    node.arm_rx += 1
                    if node.contender and node.node_id not in self.options.deaf_nodes:
                        node.armed = True
                return

            if frame.can_id == self.ids["GO"]:
                self._release_contenders()
                self._arbitration_active = False
                return

            if frame.can_id == self.ids["BENCH_CFG"]:
                self._apply_cfg(frame.data)

    def _apply_cfg(self, data: bytes) -> None:
        if len(data) != 8:
            return
        cfg = icd_gen.BenchCfg.unpack(data)
        targets = (
            self.nodes.values()
            if cfg.target_node == 0
            else [n for n in self.nodes.values() if n.node_id == cfg.target_node]
        )
        for node in targets:
            if cfg.duration_ms == 0:
                node.mode = 0
                node.mode_deadline = 0.0
            else:
                node.mode = int(cfg.mode)
                node.fault_param = int(cfg.param_u16)
                node.mode_deadline = time.monotonic() + cfg.duration_ms / 1000.0
            # Accuse réception, comme le ferait un nœud réel.
            result = icd_gen.BenchResult(
                node_id=node.node_id,
                mode=node.mode,
                status=0,
                arm_rx=min(node.arm_rx, 255),
                frames_sent=min(node.frames_sent, 65535),
                frames_lost=0,
            )
            self.bench.send(self.ids["BENCH_RESULT"], result.pack())

    def _expire_modes(self, now: float) -> None:
        with self._lock:
            for node in self.nodes.values():
                if node.mode != 0 and now >= node.mode_deadline:
                    node.mode = 0
                    node.mode_deadline = 0.0

    # -- émission -----------------------------------------------------------

    def _release_contenders(self) -> None:
        """Émet les trames armées dans l'ordre qu'un arbitrage réel produirait.

        Le bus virtuel n'arbitre pas : cet ordre est **reproduit**, pas démontré.
        Voir l'avertissement en tête de module.
        """
        armed = [n for n in self.nodes.values() if n.armed and n.tx_id is not None]
        if not armed:
            return

        if self.options.forced_order is not None:
            order = {node_id: rank for rank, node_id in enumerate(self.options.forced_order)}
            armed.sort(key=lambda n: order.get(n.node_id, 99))
        else:
            armed.sort(key=lambda n: n.tx_id)  # identifiant le plus faible d'abord

        for node in armed:
            self.bench.send(node.tx_id, self._payload_for(node))
            node.armed = False
            node.frames_sent += 1

    def _emit_application(self) -> None:
        with self._lock:
            for node in self.nodes.values():
                if node.mode == 4:  # silencieux : n'emet plus rien
                    continue

                # Identifiant utilise par les modes de faute. N4 n'ayant pas de
                # trame applicative, il se rabat sur le parametre de BENCH_CFG.
                fault_id = node.fault_param or node.tx_id

                if node.mode == 1 and fault_id is not None:  # babbling idiot
                    for _ in range(10):
                        self.bench.send(fault_id, bytes(8))
                        node.frames_sent += 1
                    continue

                if node.mode == 3 and fault_id is not None:  # DLC incoherent
                    self.bench.send(fault_id, bytes(4))
                    node.frames_sent += 1
                    continue

                if node.tx_id is None:
                    continue  # N4 n'emet rien en fonctionnement normal

                self.bench.send(node.tx_id, self._payload_for(node))
                node.frames_sent += 1

    def _payload_for(self, node: SimulatedNode) -> bytes:
        """Charge utile issue de la séquence déterministe déclarée dans l'ICD."""
        meta = icd_gen.FRAMES.get(node.tx_id)
        if meta is None:
            return bytes(8)
        simulation = icd_gen.SIMULATIONS.get(meta["layout"])
        layout = icd_gen.LAYOUTS.get(meta["layout"])
        if simulation is None or layout is None:
            return bytes(meta["dlc"])

        steps = simulation["steps"]
        values = dict(steps[node.step % len(steps)])
        node.step += 1
        return layout(**values).pack()

    def _emit_heartbeats(self) -> None:
        base = icd_gen.PROFILES[self.profile]["heartbeat_base"]
        with self._lock:
            for node in self.nodes.values():
                heartbeat = icd_gen.Heartbeat(
                    ctrl_state=node.ctrl_state,
                    last_error_code=0,
                    clock_not_qualified=int(node.clock_not_qualified),
                    fault_mode_active=int(node.mode != 0),
                    silent_mode=int(node.mode == 4),
                    tec=node.tec,
                    rec=node.rec,
                    current_mode=node.mode,
                    reserved=0,
                    rx_fifo_lost=node.rx_fifo_lost,
                    ring_overflow=node.ring_overflow,
                    non_classic_rx=node.non_classic_rx,
                    ext_id_rx=node.ext_id_rx,
                )
                self.bench.send(base + node.node_id, heartbeat.pack())

    # -- introspection ------------------------------------------------------

    def snapshot(self) -> dict[int, SimulatedNode]:
        with self._lock:
            return {k: SimulatedNode(**vars(v)) for k, v in self.nodes.items()}


def _contender_id(node_name: str) -> int | None:
    """Identifiant de la trame contendante d'un nœud, d'après l'ICD."""
    for contender in icd_gen.CONTENDERS:
        if contender["sender"] == node_name:
            return contender["can_id"]
    return None
