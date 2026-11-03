"""Moniteur du bus CAN pour la démonstration « dialogue » (firmware entry/dialogue.c).

    python pc/moniteur_dialogue.py

Lit le bus avec l'adaptateur MyActuator USBCAN-Z (famille ZLG USBCAN-I) et affiche
chaque trame avec son émetteur, son destinataire et la **transcription du texte** :
les messages découpés en morceaux sont recollés. Des boutons envoient l'appel du PC
(0x0B0) à un nœud, qui répond « Ici Nn ».

Prérequis :
- le pilote ZLG USBCAN installé (fourni par MyActuator ou ZLG) ;
- la bibliothèque ZLG 64 bits `zlgcan_x64` (CAN_lib.zip, zlg.cn), dans
  `%USERPROFILE%\\ZLG\\zlgcan_x64` ou dans le dossier donné par la variable
  d'environnement ZLGCAN_DIR ;
- ZCANPRO fermé : un seul programme à la fois peut ouvrir l'adaptateur.

Sur un bus CAN, une trame n'a pas d'« émission » et de « réception » distinctes :
les bits émis par un nœud sont lus par tous les autres au même instant. Chaque
ligne est donc à la fois l'envoi de l'émetteur et la réception des autres ; la
colonne « De → À » dit qui parle à qui, d'après l'identifiant.
"""

from __future__ import annotations

import ctypes as C
import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

# --- Bibliothèque ZLG (zlgcan.h, canframe.h) --------------------------------------

ZCAN_USBCAN1 = 3
TYPE_CAN = 0
STATUS_OK = 1
# Débit 500 kbit/s pour les USBCAN-I/II (registres BTR0/BTR1 d'un SJA1000, horloge 16 MHz)
TIMING0_500K = 0x00
TIMING1_500K = 0x1C


class can_frame(C.Structure):
    _fields_ = [("can_id", C.c_uint32), ("can_dlc", C.c_uint8), ("pad", C.c_uint8),
                ("res0", C.c_uint8), ("res1", C.c_uint8), ("data", C.c_uint8 * 8)]


class ZCAN_Transmit_Data(C.Structure):
    _fields_ = [("frame", can_frame), ("transmit_type", C.c_uint32)]


class ZCAN_Receive_Data(C.Structure):
    _fields_ = [("frame", can_frame), ("timestamp", C.c_uint64)]  # µs, horloge de l'adaptateur


class _CanCfg(C.Structure):
    _fields_ = [("acc_code", C.c_uint32), ("acc_mask", C.c_uint32), ("reserved", C.c_uint32),
                ("filter", C.c_uint8), ("timing0", C.c_uint8), ("timing1", C.c_uint8),
                ("mode", C.c_uint8)]


class _CanFdCfg(C.Structure):
    _fields_ = [("acc_code", C.c_uint32), ("acc_mask", C.c_uint32), ("abit_timing", C.c_uint32),
                ("dbit_timing", C.c_uint32), ("brp", C.c_uint32), ("filter", C.c_uint8),
                ("mode", C.c_uint8), ("pad", C.c_uint16), ("reserved", C.c_uint32)]


class _CfgUnion(C.Union):
    _fields_ = [("can", _CanCfg), ("canfd", _CanFdCfg)]


class ZCAN_CHANNEL_INIT_CONFIG(C.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("can_type", C.c_uint32), ("u", _CfgUnion)]


class ZCAN_CHANNEL_STATUS(C.Structure):
    _fields_ = [("errInterrupt", C.c_uint8), ("regMode", C.c_uint8), ("regStatus", C.c_uint8),
                ("regALCapture", C.c_uint8), ("regECCapture", C.c_uint8), ("regEWLimit", C.c_uint8),
                ("regRECounter", C.c_uint8), ("regTECounter", C.c_uint8), ("Reserved", C.c_uint32)]


class UsbCanZ:
    """Voie 0 d'un USBCAN-I, ouverte à 500 kbit/s en mode normal."""

    def __init__(self, lib_dir: Path):
        dll = lib_dir / "zlgcan.dll"
        if not dll.exists():
            raise FileNotFoundError(f"{dll} introuvable : installer zlgcan_x64 (voir l'en-tête).")
        # zlgcan.dll charge ses sous-bibliothèques (kerneldlls\\USBCAN.dll) depuis son dossier.
        os.add_dll_directory(str(lib_dir))
        cwd = os.getcwd()
        os.chdir(lib_dir)
        try:
            self.lib = C.WinDLL(str(dll))
        finally:
            os.chdir(cwd)
        L = self.lib
        L.ZCAN_OpenDevice.restype = C.c_void_p
        L.ZCAN_OpenDevice.argtypes = [C.c_uint, C.c_uint, C.c_uint]
        L.ZCAN_CloseDevice.argtypes = [C.c_void_p]
        L.ZCAN_InitCAN.restype = C.c_void_p
        L.ZCAN_InitCAN.argtypes = [C.c_void_p, C.c_uint, C.POINTER(ZCAN_CHANNEL_INIT_CONFIG)]
        L.ZCAN_StartCAN.argtypes = [C.c_void_p]
        L.ZCAN_ResetCAN.argtypes = [C.c_void_p]
        L.ZCAN_GetReceiveNum.argtypes = [C.c_void_p, C.c_uint8]
        L.ZCAN_Receive.argtypes = [C.c_void_p, C.POINTER(ZCAN_Receive_Data), C.c_uint, C.c_int]
        L.ZCAN_Transmit.argtypes = [C.c_void_p, C.POINTER(ZCAN_Transmit_Data), C.c_uint]
        L.ZCAN_ReadChannelStatus.argtypes = [C.c_void_p, C.POINTER(ZCAN_CHANNEL_STATUS)]

        cwd = os.getcwd()
        os.chdir(lib_dir)
        try:
            self.dev = L.ZCAN_OpenDevice(ZCAN_USBCAN1, 0, 0)
        finally:
            os.chdir(cwd)
        if not self.dev:
            raise RuntimeError("Adaptateur introuvable ou déjà ouvert (ZCANPRO est-il fermé ?).")
        cfg = ZCAN_CHANNEL_INIT_CONFIG()
        cfg.can_type = TYPE_CAN
        cfg.can.acc_code = 0
        cfg.can.acc_mask = 0xFFFFFFFF  # tout accepter
        cfg.can.filter = 1
        cfg.can.timing0 = TIMING0_500K
        cfg.can.timing1 = TIMING1_500K
        cfg.can.mode = 0  # normal : l'adaptateur acquitte et peut émettre
        self.chn = L.ZCAN_InitCAN(self.dev, 0, C.byref(cfg))
        if not self.chn or L.ZCAN_StartCAN(self.chn) != STATUS_OK:
            L.ZCAN_CloseDevice(self.dev)
            raise RuntimeError("Impossible de démarrer la voie CAN 0 à 500 kbit/s.")

    def receive(self, max_frames: int = 100) -> list[tuple[int, bytes, int]]:
        n = self.lib.ZCAN_GetReceiveNum(self.chn, TYPE_CAN)
        if not n:
            return []
        n = min(n, max_frames)
        buf = (ZCAN_Receive_Data * n)()
        got = self.lib.ZCAN_Receive(self.chn, buf, n, 0)
        out = []
        for r in buf[:got]:
            f = r.frame
            out.append((f.can_id & 0x1FFFFFFF, bytes(f.data[: f.can_dlc]), r.timestamp))
        return out

    def send(self, can_id: int, data: bytes) -> bool:
        tx = ZCAN_Transmit_Data()
        tx.frame.can_id = can_id
        tx.frame.can_dlc = len(data)
        for i, b in enumerate(data):
            tx.frame.data[i] = b
        tx.transmit_type = 0  # émission normale, avec retransmission automatique
        return self.lib.ZCAN_Transmit(self.chn, C.byref(tx), 1) == 1

    def counters(self) -> tuple[int, int] | None:
        st = ZCAN_CHANNEL_STATUS()
        if self.lib.ZCAN_ReadChannelStatus(self.chn, C.byref(st)) != STATUS_OK:
            return None
        return st.regTECounter, st.regRECounter

    def close(self) -> None:
        self.lib.ZCAN_ResetCAN(self.chn)
        self.lib.ZCAN_CloseDevice(self.dev)


# --- Protocole de la démonstration (firmware/entry/dialogue.c) ----------------------

ID_N1, ID_N2, ID_CALL = 0x0A1, 0x0A2, 0x0B0
COLORS = {"N1": "#fff1d6", "N2": "#dff3f6", "N3": "#ece4fb", "PC": "#e3f3dc"}


def who(can_id: int, data: bytes) -> tuple[str, str]:
    """Émetteur et destinataire, d'après l'identifiant."""
    if can_id == ID_N1:
        return "N1", "N2"
    if can_id == ID_N2:
        return "N2", "N1"
    if can_id == ID_CALL:
        target = data[0] if data else 0
        return "PC", "tous" if target == 0 else f"N{target}"
    if ID_CALL < can_id <= ID_CALL + 3:
        return f"N{can_id - ID_CALL}", "PC"
    return "?", "?"


class Reassembler:
    """Recolle les morceaux : octet 0 = (numéro << 4) | nombre, puis 7 caractères au plus."""

    def __init__(self):
        self.parts: dict[int, tuple[int, str]] = {}  # id -> (prochain morceau attendu, texte)

    def feed(self, can_id: int, data: bytes) -> tuple[str, bool]:
        if not data:
            return "", False
        part, total = data[0] >> 4, data[0] & 0x0F
        chunk = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in data[1:])
        if part == 0 or total == 0:
            return chunk, False
        expected, text = self.parts.get(can_id, (1, ""))
        if part == 1:
            expected, text = 1, ""
        if part != expected:
            self.parts.pop(can_id, None)
            return f"{chunk}  (morceau {part}/{total} hors séquence)", False
        text += chunk
        if part == total:
            self.parts.pop(can_id, None)
            return text, True
        self.parts[can_id] = (part + 1, text)
        return f"{chunk}…  (morceau {part}/{total})", False


def transcription(can_id: int, data: bytes, rebuild: Reassembler) -> tuple[str, bool]:
    if can_id == ID_CALL:
        target = data[0] if data else 0
        return ("Appel de tous les nœuds" if target == 0 else f"Appel de N{target}"), True
    if can_id in (ID_N1, ID_N2) or ID_CALL < can_id <= ID_CALL + 3:
        text, complete = rebuild.feed(can_id, data)
        return (f"« {text} »", True) if complete else (text, False)
    return "", False


# --- Fenêtre ----------------------------------------------------------------------

class Moniteur(tk.Tk):
    COLUMNS = (("t", "Temps (s)", 90), ("sens", "Sens", 95), ("deqa", "De → À", 100),
               ("id", "ID", 60), ("dlc", "DLC", 40), ("data", "Données", 210),
               ("texte", "Transcription", 320))

    def __init__(self, can: UsbCanZ):
        super().__init__()
        self.can = can
        self.rebuild = Reassembler()
        self.frames: queue.Queue = queue.Queue()
        self.t0 = time.monotonic()
        self.dev_offset: float | None = None
        self.paused = False
        self.count = 0
        self.title("Moniteur du bus CAN - dialogue N1 / N2 (USBCAN-Z, 500 kbit/s)")
        self.geometry("1000x620")
        self._build()
        self.running = True
        threading.Thread(target=self._reader, daemon=True).start()
        self.after(50, self._drain)
        self.after(1000, self._status)
        self.protocol("WM_DELETE_WINDOW", self._quit)

    def _build(self):
        top = ttk.Frame(self, padding=(8, 6))
        top.pack(fill="x")
        ttk.Label(top, text="Appel du PC (0x0B0) :").pack(side="left")
        for label, target in (("N1", 1), ("N2", 2), ("N3", 3), ("Tous", 0)):
            ttk.Button(top, text=f"Appeler {label}", command=lambda t=target: self.call(t)).pack(
                side="left", padx=3)
        ttk.Button(top, text="Effacer", command=self.clear).pack(side="right", padx=3)
        self.pause_btn = ttk.Button(top, text="Pause", command=self.toggle_pause)
        self.pause_btn.pack(side="right", padx=3)

        ttk.Label(self, padding=(8, 0, 8, 4), foreground="#555",
                  text="Une trame CAN est lue par tous les nœuds au même instant : chaque ligne est "
                       "l'envoi de l'émetteur ET la réception du destinataire.").pack(fill="x")

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=8)
        self.tree = ttk.Treeview(frame, columns=[c for c, _, _ in self.COLUMNS], show="headings")
        for key, title, width in self.COLUMNS:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w", stretch=key == "texte")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for name, color in COLORS.items():
            self.tree.tag_configure(name, background=color)
        self.tree.tag_configure("complet", font=("Segoe UI", 9, "bold"))

        self.status = ttk.Label(self, padding=(8, 4), text="")
        self.status.pack(fill="x")

    # Lecture dans un fil séparé : l'interface reste fluide.
    def _reader(self):
        while self.running:
            try:
                for frame in self.can.receive():
                    self.frames.put(("bus",) + frame)
            except OSError:
                pass
            time.sleep(0.005)

    def _drain(self):
        while not self.frames.empty():
            kind, can_id, data, ts = self.frames.get()
            if kind == "bus":
                if self.dev_offset is None:
                    self.dev_offset = (time.monotonic() - self.t0) - ts / 1e6
                t = ts / 1e6 + self.dev_offset
            else:
                t = ts
            self._add(t, kind, can_id, data)
        if self.running:
            self.after(50, self._drain)

    def _add(self, t, kind, can_id, data):
        self.count += 1
        if self.paused:
            return
        src, dst = who(can_id, data)
        text, complete = transcription(can_id, data, self.rebuild)
        tags = [src] if src in COLORS else []
        if complete:
            tags.append("complet")
        self.tree.insert("", "end", tags=tags, values=(
            f"{t:9.4f}", "émise par le PC" if kind == "pc" else "lue sur le bus",
            f"{src} → {dst}", f"0x{can_id:03X}", len(data),
            " ".join(f"{b:02X}" for b in data), text))
        children = self.tree.get_children()
        if len(children) > 2000:
            self.tree.delete(children[0])
        self.tree.yview_moveto(1.0)

    def call(self, target: int):
        data = bytes([target])
        ok = self.can.send(ID_CALL, data)
        # La trame du PC est affichée tout de suite, avec l'heure d'envoi.
        self.frames.put(("pc", ID_CALL, data, time.monotonic() - self.t0))
        if not ok:
            self.status.configure(text="Envoi refusé par l'adaptateur.")

    def clear(self):
        self.tree.delete(*self.tree.get_children())

    def toggle_pause(self):
        self.paused = not self.paused
        self.pause_btn.configure(text="Reprendre" if self.paused else "Pause")

    def _status(self):
        c = self.can.counters()
        err = f"TEC {c[0]}  REC {c[1]}" if c else "compteurs indisponibles"
        self.status.configure(text=f"{self.count} trames  |  adaptateur : {err}")
        if self.running:
            self.after(1000, self._status)

    def _quit(self):
        self.running = False
        time.sleep(0.05)
        self.can.close()
        self.destroy()


def main():
    lib_dir = Path(os.environ.get("ZLGCAN_DIR", Path.home() / "ZLG" / "zlgcan_x64"))
    try:
        can = UsbCanZ(lib_dir)
    except (OSError, RuntimeError) as e:
        root = tk.Tk()
        root.withdraw()
        from tkinter import messagebox
        messagebox.showerror("Moniteur CAN", str(e))
        return
    Moniteur(can).mainloop()


if __name__ == "__main__":
    main()
