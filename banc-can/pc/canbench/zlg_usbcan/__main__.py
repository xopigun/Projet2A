"""Outil en ligne de commande pour l'adaptateur ZLG USBCAN-UC12.

    python -m canbench.zlg_usbcan probe     # octets bruts des commandes d'identification
    python -m canbench.zlg_usbcan monitor --bitrate 500000
    python -m canbench.zlg_usbcan send 123 11223344
    python -m canbench.zlg_usbcan status

``--trace`` affiche chaque échange USB.
"""

from __future__ import annotations

import argparse
import logging
import queue
import time

from .driver import BITRATES, Frame, ZlgUsbCan, decode_ecc


def fmt(frame: Frame) -> str:
    if frame.is_event:
        return f"{frame.timestamp:>10}  ** {frame.describe_event()}  [{frame.raw.hex(' ')}]"
    ident = f"{frame.can_id:08X}" if frame.extended else f"{frame.can_id:03X}"
    kind = "RTR" if frame.remote else frame.data.hex(" ").upper()
    return f"{frame.timestamp:>10}  can{frame.channel}  {ident:>8}  [{len(frame.data)}]  {kind}"


def cmd_probe(dev: ZlgUsbCan, _args) -> None:
    for code, resp in dev.board_info_raw().items():
        print(f"commande 0x{code:02X} -> {resp.hex(' ') if resp else 'pas de réponse'}")
    for key, value in dev.board_info().items():
        print(f"{key:>10} : {value}")


def cmd_status(dev: ZlgUsbCan, args) -> None:
    dev.board_info()
    dev.init(args.bitrate, args.channel)
    dev.start(args.channel)
    st = dev.status(args.channel)
    print({k: (None if v is None else f"0x{v:02X}") for k, v in st.items()})
    if st.get("ecc") is not None:
        print("dernière erreur :", decode_ecc(st["ecc"]))
    print("statistiques bus :", dev.bus_stats(args.channel))


def cmd_monitor(dev: ZlgUsbCan, args) -> None:
    dev.board_info()
    dev.init(args.bitrate, args.channel, listen_only=args.listen_only)
    dev.start(args.channel)
    print(f"Écoute à {args.bitrate} bit/s (Ctrl+C pour arrêter)")
    n = 0
    t_end = time.monotonic() + args.duration if args.duration else None
    try:
        while t_end is None or time.monotonic() < t_end:
            try:
                frame = dev.rx.get(timeout=0.2)
            except queue.Empty:
                continue
            print(fmt(frame))
            n += 1
    except KeyboardInterrupt:
        pass
    print(f"{n} enregistrement(s) reçu(s)")


def cmd_send(dev: ZlgUsbCan, args) -> None:
    dev.board_info()
    dev.init(args.bitrate, args.channel)
    dev.start(args.channel)
    ident = int(args.id, 16)
    frame = Frame(
        ident,
        bytes.fromhex(args.data),
        extended=args.extended or ident > 0x7FF,
        channel=args.channel,
    )
    print("trames acceptées :", dev.send([frame] * args.count, channel=args.channel))
    time.sleep(0.2)
    while not dev.rx.empty():
        print(fmt(dev.rx.get()))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m canbench.zlg_usbcan",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--trace", action="store_true", help="journalise chaque échange USB")
    p.add_argument("--bitrate", type=int, default=500_000, choices=sorted(BITRATES))
    p.add_argument("--channel", type=int, default=0)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe")
    sub.add_parser("status")
    m = sub.add_parser("monitor")
    m.add_argument("--listen-only", action="store_true")
    m.add_argument("--duration", type=float, default=0.0)
    s = sub.add_parser("send")
    s.add_argument("id", help="identifiant hexadécimal")
    s.add_argument("data", nargs="?", default="", help="données hexadécimales")
    s.add_argument("--extended", action="store_true")
    s.add_argument("--count", type=int, default=1)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with ZlgUsbCan(trace=args.trace) as dev:
        {"probe": cmd_probe, "status": cmd_status, "monitor": cmd_monitor, "send": cmd_send}[
            args.cmd
        ](dev, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
