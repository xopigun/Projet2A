"""Logiciel de bureau « Banc CAN » : serveur local et fenêtre d'application.

C'est le point d'entrée de l'exécutable Windows (``BancCAN.exe``, voir
``pc/build_exe.py``). Il démarre le serveur de l'interface sur un port local,
puis ouvre la page dans une **fenêtre d'application** Microsoft Edge — sans barre
d'adresse ni onglets, avec son propre profil — et s'arrête quand cette fenêtre
est fermée.

Sans Edge, la page s'ouvre dans le navigateur par défaut ; le logiciel s'arrête
alors quand plus aucune page ne l'interroge depuis 15 secondes.

Les erreurs sont écrites dans ``%LOCALAPPDATA%\\BancCAN\\banc_can.log`` : un
exécutable sans console n'a pas d'autre endroit où les montrer.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from .server import DEFAULT_PORT, start_server

#: Délai sans interrogation de la page au-delà duquel on considère la fenêtre fermée.
IDLE_TIMEOUT = 15.0

EDGE_CANDIDATES = (
    Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
    / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
    / "Microsoft/Edge/Application/msedge.exe",
)


def data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    folder = base / "BancCAN"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def find_edge() -> Path | None:
    for candidate in EDGE_CANDIDATES:
        if candidate.exists():
            return candidate
    found = shutil.which("msedge")
    return Path(found) if found else None


def open_window(url: str) -> subprocess.Popen | None:
    """Ouvre la page dans une fenêtre d'application Edge ; None si Edge est absent.

    Le profil dédié (``--user-data-dir``) garantit que la fenêtre est un processus
    à part : sa fin signale la fermeture, même si Edge est déjà ouvert ailleurs.
    """
    edge = find_edge()
    if edge is None:
        return None
    profile = data_dir() / "fenetre"
    return subprocess.Popen(
        [
            str(edge),
            f"--app={url}",
            f"--user-data-dir={profile}",
            "--window-size=1440,920",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=Translate",
        ]
    )


def main() -> int:
    log_file = data_dir() / "banc_can.log"
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    # Exécutable sans console : sys.stdout vaut None, tout print() échouerait.
    if sys.stdout is None or sys.stderr is None:
        stream = open(log_file, "a", encoding="utf-8")  # noqa: SIM115 — vit jusqu'à la fin
        sys.stdout = sys.stdout or stream
        sys.stderr = sys.stderr or stream

    try:
        server, app = start_server(port=DEFAULT_PORT)
    except Exception:
        logging.exception("demarrage impossible")
        return 1

    url = f"http://127.0.0.1:{server.server_address[1]}/"
    logging.info("interface sur %s", url)
    threading.Thread(target=server.serve_forever, name="http", daemon=True).start()

    window = open_window(url)
    if window is None:
        logging.info("Edge introuvable : navigateur par defaut")
        webbrowser.open(url)

    try:
        started = time.monotonic()
        while True:
            time.sleep(0.5)
            if window is not None and window.poll() is not None:
                if time.monotonic() - started < 5.0:
                    # Edge a rendu la main aussitôt : la fenêtre a été confiée à
                    # une instance déjà ouverte. Seule la veille fait alors foi.
                    logging.info("fenetre confiee a une autre instance d'Edge")
                    window = None
                    continue
                logging.info("fenetre fermee")
                break
            # Filet de sécurité, et seul critère sans Edge : plus personne n'écoute.
            last = app.last_poll
            if last is not None and time.monotonic() - last > IDLE_TIMEOUT:
                logging.info("plus aucune page ouverte")
                break
            if last is None and time.monotonic() - started > 60.0:
                logging.info("aucune page ouverte apres 60 s")
                break
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
