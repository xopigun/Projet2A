"""Interface python-can pour l'adaptateur ZLG USBCAN-UC12, sans pilote ZLG.

L'adaptateur est piloté par :mod:`canbench.zlg_usbcan` (protocole reconstitué,
transport WinUSB), ce qui le rend utilisable avec l'intégrité de la mémoire de
Windows activée. Cette classe l'expose comme n'importe quel bus python-can, et
ajoute ce que l'adaptateur sait dire de la **qualité** du bus :

- compteurs d'erreurs REC/TEC du contrôleur, relevés toutes les 0,5 s ;
- événements du contrôleur (avertissement, erreur passive, perte d'arbitrage,
  erreur de bus, débordement), remontés aussi comme trames d'erreur python-can ;
- trames émises mais non acquittées (l'adaptateur abandonne après ~1,7 s) ;
- horodatage matériel à 0,1 ms, converti en temps hôte, pour mesurer la gigue.

Limite connue : le registre ECC reste figé, le *type* d'erreur CAN (bourrage,
CRC…) n'est donc pas disponible (voir ``zlg_usbcan/PROTOCOLE.md``).
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import Counter, deque

import can

log = logging.getLogger(__name__)

#: Période de relevé des compteurs d'erreurs, en secondes.
POLL_PERIOD = 0.5

#: Seuils de la norme CAN (ISO 11898-1) pour l'état du contrôleur.
WARNING_LIMIT, PASSIVE_LIMIT, BUS_OFF_LIMIT = 96, 128, 256

#: Pas de l'horodatage matériel, en secondes (vérifié contre l'horloge du PC).
TICK = 1e-4
_WRAP = 1 << 32


def controller_state(rec: int | None, tec: int | None) -> str:
    """État du contrôleur déduit des compteurs, selon les seuils de la norme."""
    if rec is None or tec is None:
        return "inconnu"
    if tec >= BUS_OFF_LIMIT:
        return "bus-off"
    worst = max(rec, tec)
    if worst >= PASSIVE_LIMIT:
        return "passif"
    if worst >= WARNING_LIMIT:
        return "avertissement"
    return "actif"


class HardwareClock:
    """Convertit l'horodatage matériel (uint32, 0,1 ms) en temps hôte (s).

    Le premier horodatage est calé sur l'heure du PC à sa réception ; les suivants
    en sont déduits par différence, ce qui garde la précision de l'adaptateur. Le
    compteur 32 bits déborde au bout de ~5 jours : on le déroule.
    """

    def __init__(self) -> None:
        self._origin: float | None = None
        self._first = 0
        self._last = 0
        self._wraps = 0

    def convert(self, ticks: int, now: float | None = None) -> float:
        if self._origin is None:
            self._origin = time.time() if now is None else now
            self._first = self._last = ticks
        elif ticks < self._last and self._last - ticks > _WRAP // 2:
            self._wraps += 1
        self._last = ticks
        elapsed = ticks + self._wraps * _WRAP - self._first
        return self._origin + elapsed * TICK


class ZlgBus(can.BusABC):
    """Bus python-can sur l'adaptateur ZLG USBCAN-UC12 (canal 0 par défaut)."""

    def __init__(
        self,
        channel: int | str | None = 0,
        bitrate: int = 500_000,
        listen_only: bool = False,
        device=None,
        poll: bool = True,
        **kwargs,
    ) -> None:
        from .zlg_usbcan import BITRATES

        if bitrate not in BITRATES:
            raise ValueError(
                f"débit {bitrate} bit/s non pris en charge par l'adaptateur ZLG "
                f"(possibles : {', '.join(str(b) for b in sorted(BITRATES))})"
            )
        self.zlg_channel = int(channel or 0)
        self.listen_only = listen_only
        if device is None:
            from .zlg_usbcan import ZlgUsbCan

            device = ZlgUsbCan()
        self.dev = device
        self.channel_info = f"ZLG USBCAN-UC12 canal {self.zlg_channel}"
        self._clock = HardwareClock()
        self._lock = threading.Lock()
        self.event_counts: Counter[str] = Counter()
        self.recent_events: deque[dict] = deque(maxlen=20)
        self.tx_ok = 0
        self.tx_failed = 0
        self.rec: int | None = None
        self.tec: int | None = None
        self.peak_rec = 0
        self.peak_tec = 0
        self._stop = threading.Event()
        try:
            self.info = self.dev.board_info()
            self.dev.init(bitrate, self.zlg_channel, listen_only=listen_only)
            if self.dev.start(self.zlg_channel) is None:
                raise can.CanInitializationError("l'adaptateur ZLG n'a pas démarré le canal")
        except Exception:
            self.dev.close()
            raise
        super().__init__(channel=self.zlg_channel, **kwargs)
        self._poller: threading.Thread | None = None
        if poll:
            self._poller = threading.Thread(target=self._poll, name="zlg-erreurs", daemon=True)
            self._poller.start()

    # -- réception ------------------------------------------------------------

    def _recv_internal(self, timeout: float | None) -> tuple[can.Message | None, bool]:
        try:
            record = self.dev.rx.get(timeout=timeout) if timeout != 0 else self.dev.rx.get_nowait()
        except queue.Empty:
            return None, False
        stamp = self._clock.convert(record.timestamp)
        if record.is_event:
            text = record.describe_event()
            with self._lock:
                self.event_counts[_event_name(record.status)] += 1
                self.recent_events.appendleft({"t": stamp, "code": record.status, "text": text})
                if record.status == 0xE3:  # l'événement porte REC et TEC
                    self._set_counters(record.raw[8], record.raw[9])
            message = can.Message(
                timestamp=stamp,
                arbitration_id=record.status,
                is_error_frame=True,
                is_extended_id=False,
                data=record.raw[7:10],
                channel=self.zlg_channel,
            )
            return message, False
        message = can.Message(
            timestamp=stamp,
            arbitration_id=record.can_id,
            is_extended_id=record.extended,
            is_remote_frame=record.remote,
            dlc=len(record.data),
            data=record.data,
            channel=record.channel,
        )
        return message, False

    # -- émission -------------------------------------------------------------

    def send(self, msg: can.Message, timeout: float | None = None) -> None:
        """Émet une trame et attend l'acquittement de l'adaptateur.

        Une trame que personne n'acquitte n'est **pas** une exception : elle est
        comptée dans ``tx_failed`` et affichée comme indicateur de qualité.
        """
        from .zlg_usbcan import Frame

        if self.listen_only:
            raise can.CanOperationError("adaptateur ZLG ouvert en écoute seule")
        frame = Frame(
            can_id=msg.arbitration_id,
            data=bytes(msg.data or b"")[:8],
            extended=bool(msg.is_extended_id),
            remote=bool(msg.is_remote_frame),
            channel=self.zlg_channel,
        )
        accepted = self.dev.send([frame], channel=self.zlg_channel)
        with self._lock:
            if accepted:
                self.tx_ok += 1
            else:
                self.tx_failed += 1
        if not accepted:
            log.warning("trame 0x%X non acquittée (aucun nœud sur le bus ?)", msg.arbitration_id)

    # -- qualité --------------------------------------------------------------

    def _set_counters(self, rec: int | None, tec: int | None) -> None:
        self.rec, self.tec = rec, tec
        if rec is not None:
            self.peak_rec = max(self.peak_rec, rec)
        if tec is not None:
            self.peak_tec = max(self.peak_tec, tec)

    def _poll(self) -> None:
        from .zlg_usbcan.driver import REG_RXERR, REG_TXERR

        while not self._stop.wait(POLL_PERIOD):
            try:
                rec = self.dev.read_register(REG_RXERR, self.zlg_channel)
                tec = self.dev.read_register(REG_TXERR, self.zlg_channel)
            except Exception as error:  # noqa: BLE001 — adaptateur débranché, etc.
                log.debug("relevé REC/TEC impossible : %s", error)
                continue
            if rec is not None and tec is not None:
                with self._lock:
                    self._set_counters(rec, tec)

    def quality(self) -> dict:
        """Indicateurs de qualité propres à l'adaptateur, pour l'affichage."""
        with self._lock:
            return {
                "adapter": "ZLG USBCAN-UC12",
                "firmware": self.info.get("firmware"),
                "serial": self.info.get("serie"),
                "rec": self.rec,
                "tec": self.tec,
                "peak_rec": self.peak_rec,
                "peak_tec": self.peak_tec,
                "state": controller_state(self.rec, self.tec),
                "events": dict(self.event_counts),
                "recent_events": list(self.recent_events),
                "tx_ok": self.tx_ok,
                "tx_failed": self.tx_failed,
                "error_type_available": False,
            }

    # -- cycle de vie -----------------------------------------------------------

    def shutdown(self) -> None:
        if self._is_shutdown:
            return
        self._stop.set()
        if self._poller is not None:
            self._poller.join(timeout=1.0)
        try:
            self.dev.close()
        finally:
            super().shutdown()


def _event_name(status: int) -> str:
    from .zlg_usbcan.driver import STATUS_EVENTS

    return STATUS_EVENTS.get(status, f"état 0x{status:02X}")


__all__ = ["HardwareClock", "ZlgBus", "controller_state"]
