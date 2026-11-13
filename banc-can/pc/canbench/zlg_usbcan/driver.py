"""Pilote en espace utilisateur pour l'adaptateur ZLG USBCAN-UC12 (USB 0471:1200).

Remplace le couple ZLG ``usbcan.sys`` (pilote noyau de 2017, refusé par l'intégrité
de la mémoire) + ``usbcan.dll``. Le protocole a été reconstitué par analyse statique
de ``usbcan.dll`` (voir PROTOCOLE.md) ; le transport passe par WinUSB, pilote générique
signé par Microsoft, via libusb/pyusb.

Prérequis : WinUSB attaché à l'adaptateur, ``pyusb`` et ``libusb-package``.
"""

from __future__ import annotations

import logging
import queue
import struct
import threading
import time
from dataclasses import dataclass, field

import usb.core
import usb.util

try:  # libusb-1.0.dll embarquée, absente de Windows par défaut
    import libusb_package

    _BACKEND = libusb_package.get_libusb1_backend()
except ImportError:  # pragma: no cover
    _BACKEND = None

log = logging.getLogger("zlg_usbcan")

VID, PID = 0x0471, 0x1200

WRONG_DRIVER = (
    "Adaptateur ZLG trouvé mais inaccessible : il est sans doute encore attaché au "
    "pilote ZLG (usbcan.sys) ou ouvert par un autre logiciel. Dans le Gestionnaire de "
    "périphériques, lui attacher « WinUSB » (Mettre à jour le pilote > Choisir parmi "
    "la liste > Périphérique WinUsb)."
)

# Endpoints, dans l'ordre des tuyaux PIPE00..PIPE03 ouverts par usbcan.dll
EP_RESP_IN = 0x81  # interruption, 16 o : réponses aux commandes
EP_CMD_OUT = 0x01  # interruption, 16 o : commandes
EP_DATA_IN = 0x82  # bulk, 64 o : trames reçues (enregistrements de 19 o)
EP_DATA_OUT = 0x02  # bulk, 64 o : trames à émettre (enregistrements de 19 o)

CMD, RESP = 0x12, 0x13
RECORD = 19
FRAMES_PER_WRITE = 3  # 3 x 19 = 57 o <= 64 o
RX_CHUNK = 64 * RECORD  # 1216 o, comme la DLL (0x4C0)

# Codes de commande (octet 1)
C_BOARD_INFO = 0x01
C_INIT = 0x03
C_FILTER = 0x04
C_STATS = 0x06
C_MEM_READ = 0x07
C_MEM_WRITE = 0x08
C_READ_REG = 0x0D
C_START = 0x0E
C_RESET = 0x0F
C_BOARD_INFO_EXT = (0x12, 0x13, 0x14, 0x15)

# Registres SJA1000 (mode PeliCAN)
REG_MODE, REG_STATUS, REG_ALC, REG_ECC, REG_EWL, REG_RXERR, REG_TXERR = (
    0x00,
    0x02,
    0x0B,
    0x0C,
    0x0D,
    0x0E,
    0x0F,
)

#: Timing0/Timing1 (BTR0/BTR1 du SJA1000, horloge 16 MHz) — table usuelle ZLG.
BITRATES = {
    10_000: (0x31, 0x1C),
    20_000: (0x18, 0x1C),
    50_000: (0x09, 0x1C),
    100_000: (0x04, 0x1C),
    125_000: (0x03, 0x1C),
    250_000: (0x01, 0x1C),
    500_000: (0x00, 0x1C),
    800_000: (0x00, 0x16),
    1_000_000: (0x00, 0x14),
}

#: Octet d'état d'un enregistrement reçu -> événement du contrôleur (cf. usbcan.dll)
STATUS_EVENTS = {
    0xE1: "débordement FIFO",
    0xE2: "avertissement d'erreurs",
    0xE3: "erreur passive",
    0xE4: "perte d'arbitrage",
    0xE5: "erreur de bus",
    0xEF: "débordement FIFO",
}

ECC_TYPES = {0: "bit", 1: "forme", 2: "bourrage", 3: "autre"}
ECC_SEGMENTS = {
    0x03: "SOF",
    0x02: "ID.28-21",
    0x06: "ID.20-18",
    0x04: "SRTR",
    0x05: "IDE",
    0x07: "ID.17-13",
    0x0F: "ID.12-5",
    0x0E: "ID.4-0",
    0x0C: "RTR",
    0x0D: "r1",
    0x09: "r0",
    0x0B: "DLC",
    0x0A: "données",
    0x08: "CRC",
    0x18: "délimiteur CRC",
    0x19: "slot ACK",
    0x1B: "délimiteur ACK",
    0x1A: "EOF",
    0x12: "intermission",
    0x11: "flag d'erreur actif",
    0x16: "flag d'erreur passif",
    0x13: "tolérance bits dominants",
    0x17: "délimiteur d'erreur",
    0x1C: "flag de surcharge",
}


def decode_ecc(ecc: int) -> str:
    """Décode le registre ECC (Error Code Capture) du SJA1000."""
    kind = ECC_TYPES[(ecc >> 6) & 3]
    direction = "réception" if ecc & 0x20 else "émission"
    seg = ECC_SEGMENTS.get(ecc & 0x1F, f"segment 0x{ecc & 0x1F:02X}")
    return f"erreur de {kind} en {direction}, {seg}"


@dataclass
class Frame:
    can_id: int
    data: bytes = b""
    extended: bool = False
    remote: bool = False
    channel: int = 0
    timestamp: int = 0  # unité : 0,1 ms (vérifié)
    status: int = 0  # 0 = trame normale ; 0xE1.. = événement du contrôleur
    raw: bytes = field(default=b"", repr=False)

    @property
    def is_event(self) -> bool:
        return self.status != 0

    def describe_event(self) -> str:
        name = STATUS_EVENTS.get(self.status, f"état 0x{self.status:02X}")
        r = self.raw
        if self.status == 0xE3:  # vérifié : octets 7..9 = ECC, REC, TEC
            return f"{name} : REC={r[8]}, TEC={r[9]} (ECC 0x{r[7]:02X})"
        if self.status == 0xE4:  # ArLost_ErrData = octet 7 (registre ALC)
            return f"{name} : bit {r[7] & 0x1F}"
        return f"{name} (données {r[7:10].hex(' ')})"


def encode_frame(frame: Frame, send_type: int = 0) -> bytes:
    """Enregistrement d'émission de 19 octets (cf. VCI_Transmit)."""
    dlc = min(len(frame.data), 8)
    flags = (
        (0x80 if frame.extended else 0)
        | (0x40 if frame.remote else 0)
        | ((frame.channel & 3) << 4)
        | dlc
    )
    ident = (frame.can_id << 3) if frame.extended else (frame.can_id << 5)
    data = bytes(frame.data[:8]).ljust(8, b"\0")
    # Même disposition qu'en réception : 5 octets réservés (horodatage + état), puis
    # SendType à l'octet 5, drapeaux à l'octet 6, ID aux octets 7-10, données 11-18.
    return bytes(5) + bytes([send_type & 0xFF, flags]) + struct.pack("<I", ident) + data


def decode_record(rec: bytes) -> Frame:
    """Enregistrement de réception de 19 octets (cf. tâche de réception de usbcan.dll)."""
    ts = struct.unpack_from("<I", rec, 0)[0]
    status = rec[4]
    flags = rec[6]
    extended = bool(flags & 0x80)
    ident = struct.unpack_from("<I", rec, 7)[0]
    ident >>= 3 if extended else 5
    dlc = flags & 0x0F
    return Frame(
        can_id=ident,
        data=bytes(rec[11 : 11 + min(dlc, 8)]),
        extended=extended,
        remote=bool(flags & 0x40),
        channel=(flags >> 4) & 3,
        timestamp=ts,
        status=status,
        raw=bytes(rec),
    )


class ZlgUsbCan:
    """Accès direct à l'adaptateur. ``trace=True`` journalise chaque octet échangé."""

    def __init__(self, trace: bool = False, timeout: float = 1.0):
        self.trace = trace
        self.timeout = timeout
        self.dev = usb.core.find(idVendor=VID, idProduct=PID, backend=_BACKEND)
        if self.dev is None:
            raise RuntimeError(
                "Adaptateur ZLG 0471:1200 introuvable par libusb. Est-il branché, "
                "et WinUSB lui est-il attaché (Gestionnaire de périphériques) ?"
            )
        try:
            self.dev.set_configuration()
        except usb.core.USBError as exc:  # WinUSB : configuration déjà active
            log.debug("set_configuration ignoré : %s", exc)
        except NotImplementedError as exc:
            raise RuntimeError(WRONG_DRIVER) from exc
        try:
            usb.util.claim_interface(self.dev, 0)
        except (NotImplementedError, usb.core.USBError) as exc:
            raise RuntimeError(f"{WRONG_DRIVER} ({exc})") from exc
        self._resp: dict[tuple[str, int], bytes] = {}
        self._resp_cv = threading.Condition()
        self._cmd_lock = threading.Lock()
        self.rx: queue.Queue[Frame] = queue.Queue()
        self.fw_version = 0
        self._started: set[int] = set()
        self._running = True
        self._threads = [
            threading.Thread(target=self._resp_loop, daemon=True, name="zlg-resp"),
            threading.Thread(target=self._rx_loop, daemon=True, name="zlg-rx"),
        ]
        for t in self._threads:
            t.start()

    # --- transport -------------------------------------------------------------
    def _t(self, direction: str, ep: int, data: bytes) -> None:
        if self.trace:
            log.info("%s EP%02X %3d o : %s", direction, ep, len(data), data.hex(" "))

    def _resp_loop(self) -> None:
        while self._running:
            try:
                data = bytes(self.dev.read(EP_RESP_IN, 16, timeout=200))
            except usb.core.USBTimeoutError:
                continue
            except usb.core.USBError as exc:
                if self._running:
                    log.error("lecture réponses : %s", exc)
                    time.sleep(0.1)
                continue
            if not data:
                continue
            self._t("<-", EP_RESP_IN, data)
            # Observé sur le firmware 1.02 : les réponses commencent par 0x12 (la DLL de
            # 2017 attendait 0x13) ; on accepte les deux.
            if len(data) < 3 or data[0] not in (CMD, RESP):
                continue
            # Octet 2 >= 0x80 : réponse à la commande data[1] (bits 0-6 = longueur à
            # partir de l'octet 3) ; sinon acquittement d'émission du canal data[1]
            # (data[2] = nombre de trames acceptées).
            key = ("cmd", data[1]) if data[2] >= 0x80 else ("tx", data[1])
            with self._resp_cv:
                self._resp[key] = data
                self._resp_cv.notify_all()

    def _rx_loop(self) -> None:
        pending = b""
        while self._running:
            try:
                chunk = bytes(self.dev.read(EP_DATA_IN, RX_CHUNK, timeout=200))
            except usb.core.USBTimeoutError:
                continue
            except usb.core.USBError as exc:
                if self._running:
                    log.error("lecture trames : %s", exc)
                    time.sleep(0.1)
                continue
            self._t("<-", EP_DATA_IN, chunk)
            pending += chunk
            while len(pending) >= RECORD:
                rec, pending = pending[:RECORD], pending[RECORD:]
                self.rx.put(decode_record(rec))

    def _wait(self, key: tuple[str, int], timeout: float) -> bytes | None:
        deadline = time.monotonic() + timeout
        with self._resp_cv:
            while key not in self._resp:
                left = deadline - time.monotonic()
                if left <= 0:
                    return None
                self._resp_cv.wait(left)
            return self._resp.pop(key)

    def command(
        self, code: int, body: bytes, timeout: float | None = None, length: int | None = None
    ) -> bytes | None:
        """Envoie ``12 <code> <len(body)> <body>`` et attend la réponse ``13 <code> ...``."""
        pkt = bytes([CMD, code, len(body) if length is None else length]) + body
        with self._cmd_lock:
            with self._resp_cv:
                self._resp.pop(("cmd", code), None)
            self._t("->", EP_CMD_OUT, pkt)
            self.dev.write(EP_CMD_OUT, pkt, timeout=int(self.timeout * 1000))
            return self._wait(("cmd", code), timeout or self.timeout)

    # --- API de haut niveau ----------------------------------------------------
    @staticmethod
    def payload(resp: bytes) -> bytes:
        """Charge utile d'une réponse : octets 4.. (l'octet 3 vaut 00)."""
        n = resp[2] & 0x7F
        return bytes(resp[4 : 3 + n])

    def board_info_raw(self) -> dict[int, bytes | None]:
        """Réponses brutes des commandes d'identification (0x01, 0x12..0x15)."""
        return {code: self.command(code, b"\x00") for code in (C_BOARD_INFO, *C_BOARD_INFO_EXT)}

    def board_info(self) -> dict[str, object]:
        """Identification décodée. Observé : 0x01 -> firmware, 0x14 -> n° de série,
        0x15 -> type ; 0x12 et 0x13 restent à interpréter (rendus bruts)."""
        raw = self.board_info_raw()
        p = {code: (self.payload(r) if r else None) for code, r in raw.items()}
        info: dict[str, object] = {}
        if p[C_BOARD_INFO] and len(p[C_BOARD_INFO]) >= 2:
            self.fw_version = struct.unpack_from("<H", p[C_BOARD_INFO])[0]
            info["firmware"] = f"{self.fw_version >> 8}.{self.fw_version & 0xFF:02X}"
        if p[0x12]:
            info["info_0x12"] = p[0x12].hex(" ")
        if p[0x13]:
            info["info_0x13"] = p[0x13].hex(" ")
        if p[0x14]:
            info["serie"] = p[0x14].rstrip(b"\0").decode("ascii", "replace")
        if p[0x15]:
            info["type"] = p[0x15].rstrip(b"\0").decode("ascii", "replace")
        return info

    def init(
        self,
        bitrate: int = 500_000,
        channel: int = 0,
        listen_only: bool = False,
        acc_code: int = 0,
        acc_mask: int = 0xFFFFFFFF,
        filter_mode: int = 1,
    ) -> None:
        t0, t1 = BITRATES[bitrate]
        mode = 1 if listen_only else 0
        r = self.command(C_INIT, bytes([0, ((mode << 3) | channel) << 4, t0, t1]))
        if r is None:
            raise RuntimeError("pas de réponse à l'initialisation (0x03)")
        body = bytes([0, ((filter_mode << 2) | channel) << 4])
        body += acc_code.to_bytes(4, "big") + acc_mask.to_bytes(4, "big")
        if self.command(C_FILTER, body) is None:
            raise RuntimeError("pas de réponse au filtre (0x04)")

    def start(self, channel: int = 0) -> bytes | None:
        r = self.command(C_START, bytes([0, channel << 4]))
        if r is not None:
            self._started.add(channel)
        return r

    def reset(self, channel: int = 0) -> bytes | None:
        # usbcan.dll envoie ici 0x12 en octet 2, et non la longueur : on reproduit.
        return self.command(C_RESET, bytes([0, channel << 4]), length=0x12)

    def read_register(self, reg: int, channel: int = 0) -> int | None:
        r = self.command(C_READ_REG, bytes([0, channel << 4, reg]))
        return None if r is None or len(r) < 5 else r[4]

    def bus_stats(self, channel: int = 0) -> tuple[int, int, int] | None:
        """(octet 4, compteur A, compteur B) ; la DLL en tire A*100/(A+B) %."""
        r = self.command(C_STATS, bytes([0, channel << 4]))
        if r is None:
            return None
        a, b = struct.unpack_from("<II", r, 5)
        return r[4], a, b

    def status(self, channel: int = 0) -> dict[str, int | None]:
        regs = {
            "mode": REG_MODE,
            "status": REG_STATUS,
            "alc": REG_ALC,
            "ecc": REG_ECC,
            "ewl": REG_EWL,
            "rec": REG_RXERR,
            "tec": REG_TXERR,
        }
        return {name: self.read_register(reg, channel) for name, reg in regs.items()}

    def send(self, frames: list[Frame], send_type: int = 0, channel: int = 0) -> int:
        """Émet les trames par paquets de 3 ; renvoie le nombre de trames écrites."""
        sent = 0
        for i in range(0, len(frames), FRAMES_PER_WRITE):
            batch = frames[i : i + FRAMES_PER_WRITE]
            pkt = b"".join(encode_frame(f, send_type) for f in batch)
            with self._resp_cv:
                self._resp.pop(("tx", channel), None)
            self._t("->", EP_DATA_OUT, pkt)
            try:
                self.dev.write(EP_DATA_OUT, pkt, timeout=int(self.timeout * 1000))
            except usb.core.USBTimeoutError:
                # L'adaptateur refuse les données tant que son tampon d'émission est
                # plein (trame en attente d'acquittement, ou canal non démarré).
                log.warning("émission refusée : tampon d'émission de l'adaptateur plein")
                return sent
            if self.fw_version >= 0x102:
                # Acquittement « 13 <canal> <n> » à la fin de l'émission. Sans
                # acquittement CAN, l'adaptateur abandonne après ~1,7 s et renvoie n = 0.
                ack = self._wait(("tx", channel), 2.5)
                sent += ack[2] if ack else 0
            else:
                sent += len(batch)
        return sent

    def close(self) -> None:
        for channel in sorted(self._started):  # ne pas laisser un canal en erreur
            self.reset(channel)
        self._running = False
        for t in self._threads:
            t.join(timeout=1.0)
        usb.util.release_interface(self.dev, 0)
        usb.util.dispose_resources(self.dev)

    def __enter__(self) -> ZlgUsbCan:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
