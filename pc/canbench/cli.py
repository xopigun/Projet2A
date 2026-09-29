"""Point d'entrée en ligne de commande de `canbench`.

Toutes les sous-commandes fonctionnent sur le bus `virtual`, avec l'option
`--simulate` qui démarre un simulateur reproduisant N1 à N4. C'est ce qui permet
d'exécuter la chaîne complète en intégration continue, sans matériel.

    canbench --interface virtual --simulate arbitration --cycles 100
    canbench --interface gs_usb arbitration --cycles 1000

> **Sur bus virtuel, aucun verdict de réussite n'est prononcé.** Le simulateur
> reproduit le comportement attendu des nœuds ; il ne le démontre pas. Les
> rapports produits portent la mention correspondante.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import arbitration, decode, encoding, faults, icd_gen, record, report
from .bus import Bench
from .simulator import NodeSimulator, SimulatorOptions

# ---------------------------------------------------------------------------
#  Contexte d'exécution
# ---------------------------------------------------------------------------


class Session:
    """Bus, et simulateur optionnel, refermés proprement en sortie."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.virtual = args.interface == "virtual"
        self.simulator: NodeSimulator | None = None

        if args.simulate:
            if not self.virtual:
                raise SystemExit(
                    "--simulate n'a de sens que sur --interface virtual : sur le banc réel, "
                    "ce sont les nœuds qui émettent."
                )
            options = SimulatorOptions(
                periodic_app=not args.no_periodic,
                unqualified_clock_nodes=tuple(args.unqualified_clock or ()),
                deaf_nodes=tuple(args.deaf_node or ()),
            )
            self.simulator = NodeSimulator(
                interface=args.interface,
                channel=args.channel,
                profile=args.profile,
                options=options,
            ).start()
            time.sleep(0.15)  # laisse le simulateur s'installer

        self.bench = Bench(
            interface=args.interface,
            channel=args.channel,
            bitrate=args.bitrate,
            profile=args.profile,
        )

    def __enter__(self) -> Session:
        return self

    def __exit__(self, *_exc) -> None:
        self.bench.close()
        if self.simulator is not None:
            self.simulator.stop()


def _emit(
    text: str,
    args: argparse.Namespace,
    test: str,
    passed: bool,
    clock_warnings: list[str] | None = None,
    loss_warnings: list[str] | None = None,
) -> int:
    """Affiche le résultat et, si demandé, écrit le rapport. Renvoie le code de sortie."""
    print(text)

    blockers = report.blockers_from(
        virtual=args.interface == "virtual",
        clock_warnings=clock_warnings or [],
        loss_warnings=loss_warnings or [],
    )

    if args.report:
        entry = report.Report(
            test=test,
            result_text=text,
            passed=passed,
            virtual=args.interface == "virtual",
            blockers=blockers,
        )
        md, tex = entry.write(Path(args.report))
        print(f"\nRapport écrit : {md}\n                {tex}")

    if blockers:
        print("\nNON CONCLUANT :")
        for blocker in blockers:
            print(f"  - {blocker}")
        return 0 if passed else 1

    return 0 if passed else 1


# ---------------------------------------------------------------------------
#  Sous-commandes
# ---------------------------------------------------------------------------


def cmd_monitor(args: argparse.Namespace) -> int:
    """Affichage live décodé, état des nœuds, charge du bus."""
    with Session(args) as session:
        bench = session.bench
        base = icd_gen.PROFILES[args.profile]["heartbeat_base"]
        heartbeats: dict[int, dict] = {}
        counts: dict[int, int] = {}
        started = time.monotonic()
        frames = []

        print(f"Écoute sur {args.interface} — Ctrl-C pour arrêter.\n")
        try:
            for frame in bench.stream(duration=args.duration):
                frames.append(frame)
                counts[frame.can_id] = counts.get(frame.can_id, 0) + 1
                arbitration._note_heartbeat(frame, base, heartbeats)
                if not args.quiet:
                    print(decode.decode(frame, args.profile).summary())
        except KeyboardInterrupt:
            print()

        elapsed = time.monotonic() - started
        print("\n" + "=" * 68)
        print(f"{len(frames)} trames en {elapsed:.1f} s")

        load = decode.measured_load(frames, elapsed, args.bitrate)
        print(
            f"Charge mesurée : {load['load'] * 100:.2f} % "
            f"(pire cas avec bit stuffing : {load['load_worst_case'] * 100:.2f} %)"
        )

        if counts:
            print("\nTrames vues :")
            for can_id in sorted(counts):
                meta = icd_gen.FRAMES.get(can_id)
                name = meta["name"] if meta else "<inconnu>"
                print(f"  0x{can_id:03X}  {name:<18} {counts[can_id]}")

        if heartbeats:
            print("\nÉtat des nœuds :")
            for node_id in sorted(heartbeats):
                beat = heartbeats[node_id]
                flag = "  HORLOGE NON CONFORME" if beat["clock_not_qualified"] else ""
                print(
                    f"  N{node_id}  {arbitration.STATES[beat['ctrl_state']]:<14} "
                    f"TEC={beat['tec']:<4} REC={beat['rec']:<4} "
                    f"fifo={beat['rx_fifo_lost']} tampon={beat['ring_overflow']} "
                    f"fd={beat['non_classic_rx']} ext={beat['ext_id_rx']}{flag}"
                )

        for line in bench.non_conformity.report():
            print(line)
        return 0


def cmd_arbitration(args: argparse.Namespace) -> int:
    with Session(args) as session:
        result = arbitration.run(session.bench, cycles=args.cycles)
        text = arbitration.render(result, virtual=session.virtual)
        return _emit(text, args, "T3", result.passed, result.clock_warnings, result.loss_warnings)


def cmd_encoding(args: argparse.Namespace) -> int:
    with Session(args) as session:
        result = encoding.run(session.bench, duration=args.duration)
        text = encoding.render(result, virtual=session.virtual)
        return _emit(text, args, "T4", result.passed)


def cmd_faults(args: argparse.Namespace) -> int:
    with Session(args) as session:
        if args.physical:

            def prompt(message: str) -> str:
                return input(f"\n>>> {message}\n    [Entrée pour continuer] ")

            result = faults.run_physical(session.bench, prompt, print)
            test = "T5"
        else:
            result = faults.run_logical(session.bench, target_node=args.node)
            test = "T6"
        text = faults.render(result, virtual=session.virtual)
        return _emit(text, args, test, result.passed)


def cmd_busload(args: argparse.Namespace) -> int:
    with Session(args) as session:
        theory = decode.theoretical_load(args.bitrate, worst_case=True)
        nominal = decode.theoretical_load(args.bitrate, worst_case=False)

        print("Charge du bus")
        print("=" * 68)
        print(f"Débit : {args.bitrate} bit/s\n")
        print(f"{'Trame':<18}{'ID':<8}{'Période':<10}{'Bits':<8}bit/s")
        print("-" * 56)
        for entry in theory["frames"]:
            print(
                f"{entry['name']:<18}0x{entry['can_id']:03X}   "
                f"{entry['period_ms']:<10}{entry['bits']:<8}{entry['bits_per_s']:.0f}"
            )

        print(f"\nThéorique, pire cas (bit stuffing maximal) : {theory['load'] * 100:.2f} %")
        print(f"Théorique, sans bit stuffing               : {nominal['load'] * 100:.2f} %")

        if args.measure > 0:
            print(f"\nMesure sur {args.measure:.1f} s...")
            started = time.monotonic()
            frames = session.bench.collect(args.measure)
            measured = decode.measured_load(frames, time.monotonic() - started, args.bitrate)
            print(
                f"Mesurée : {measured['load'] * 100:.2f} % "
                f"({measured['frames']} trames, "
                f"{measured['frames_per_s']:.0f} trames/s)"
            )
            print(
                f"Mesurée, majorée du bit stuffing pire cas : "
                f"{measured['load_worst_case'] * 100:.2f} %"
            )
        return 0


def cmd_record(args: argparse.Namespace) -> int:
    with Session(args) as session:
        path = Path(args.output)
        print(f"Enregistrement de {args.duration:.1f} s vers {path}...")
        count = record.record(session.bench, path, args.duration)
        print(f"{count} trames enregistrées.")
        return 0


def cmd_replay(args: argparse.Namespace) -> int:
    path = Path(args.input)
    stats = record.count_non_classic(path)
    if stats["extended"] or stats["fd"] or stats["oversized"]:
        print(
            f"ATTENTION : la trace contient {stats['extended']} trame(s) étendue(s), "
            f"{stats['fd']} FD et {stats['oversized']} de plus de 8 octets. "
            "Elles ne seront pas rejouées : le banc n'émet que du CAN 2.0A classic."
        )

    with Session(args) as session:
        count = record.replay(session.bench, path, respect_timing=not args.fast)
        print(f"{count} trames rejouées sur {stats['total']}.")
        return 0


def cmd_gui(args: argparse.Namespace) -> int:
    """Interface graphique : serveur local et page web."""
    from .gui.server import serve

    # En virtuel, le simulateur est démarré d'office : sans lui, la page n'aurait
    # rien à afficher. Sur une interface réelle, --simulate reste refusé.
    serve(
        interface=args.interface,
        channel=args.channel,
        bitrate=args.bitrate,
        profile=args.profile,
        simulate=args.interface == "virtual",
        port=args.port,
        open_browser=not args.no_browser,
    )
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Produit un rapport à partir d'un résultat saisi, pour T1, T2 et T7."""
    text = sys.stdin.read() if args.stdin else (args.result or "")
    if not text.strip():
        print("Aucun résultat fourni : utiliser --result ou --stdin.", file=sys.stderr)
        return 2

    entry = report.Report(
        test=args.test,
        result_text=text,
        passed=args.passed,
        virtual=False,
        blockers=[] if args.passed else [],
    )
    md, tex = entry.write(Path(args.output))
    print(f"Rapport écrit : {md}\n                {tex}")
    return 0


# ---------------------------------------------------------------------------
#  Analyse des arguments
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="canbench",
        description="Outils du banc de test CAN — G69-BANC-001.",
        epilog="Toutes les sous-commandes fonctionnent sur --interface virtual "
        "avec --simulate, sans matériel.",
    )
    parser.add_argument(
        "--interface",
        default="virtual",
        choices=["virtual", "gs_usb", "slcan", "socketcan", "pcan", "kvaser"],
        help="interface python-can (défaut : virtual)",
    )
    parser.add_argument("--channel", default=None, help="canal de l'interface (ex. COM7)")
    parser.add_argument(
        "--bitrate",
        type=int,
        default=icd_gen.BITRATE,
        help=f"débit en bit/s (défaut : {icd_gen.BITRATE})",
    )
    parser.add_argument(
        "--profile",
        default=icd_gen.DEFAULT_PROFILE,
        choices=sorted(icd_gen.PROFILES),
        help="profil réseau, qui fixe les identifiants de service",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="démarre un simulateur de N1 à N4 (bus virtuel uniquement)",
    )
    parser.add_argument(
        "--no-periodic",
        action="store_true",
        help="avec --simulate : pas de trafic applicatif périodique",
    )
    parser.add_argument(
        "--unqualified-clock",
        type=int,
        action="append",
        metavar="N",
        help="avec --simulate : nœud signalant une horloge non conforme",
    )
    parser.add_argument(
        "--deaf-node",
        type=int,
        action="append",
        metavar="N",
        help="avec --simulate : nœud qui rate la fenêtre d'armement",
    )
    parser.add_argument(
        "--report", metavar="DOSSIER", help="écrit le rapport Markdown et LaTeX dans ce dossier"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("monitor", help="affichage live décodé et état des nœuds")
    p.add_argument(
        "--duration",
        type=float,
        default=None,
        help="durée d'écoute en secondes (défaut : jusqu'à Ctrl-C)",
    )
    p.add_argument("--quiet", action="store_true", help="n'affiche que le récapitulatif")
    p.set_defaults(func=cmd_monitor)

    p = sub.add_parser("arbitration", help="test T3 — arbitrage ARM/GO")
    p.add_argument("--cycles", type=int, default=1000, help="nombre de cycles (défaut : 1000)")
    p.set_defaults(func=cmd_arbitration)

    p = sub.add_parser("encoding", help="test T4 — encodage de l'ICD")
    p.add_argument("--duration", type=float, default=2.0, help="durée de collecte")
    p.set_defaults(func=cmd_encoding)

    p = sub.add_parser("faults", help="tests T5 et T6 — injection de fautes")
    p.add_argument(
        "--physical",
        action="store_true",
        help="assistant guidé SW1/SW2/SW3 (T5) au lieu des fautes logicielles",
    )
    p.add_argument("--node", type=int, default=4, help="nœud cible des fautes logicielles")
    p.set_defaults(func=cmd_faults)

    p = sub.add_parser("busload", help="charge du bus, théorique et mesurée")
    p.add_argument(
        "--measure",
        type=float,
        default=0.0,
        help="durée de mesure en secondes (0 = théorique seulement)",
    )
    p.set_defaults(func=cmd_busload)

    p = sub.add_parser("record", help="enregistre le trafic (.asc ou .blf)")
    p.add_argument("output", help="fichier de sortie")
    p.add_argument("--duration", type=float, default=10.0, help="durée en secondes")
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("replay", help="rejoue un enregistrement")
    p.add_argument("input", help="fichier à rejouer")
    p.add_argument("--fast", action="store_true", help="ignore les horodatages")
    p.set_defaults(func=cmd_replay)

    p = sub.add_parser("report", help="produit un rapport pour un test manuel (T1, T2, T7)")
    p.add_argument("--test", required=True, choices=sorted(report.TESTS))
    p.add_argument("--output", default="docs/resultats", help="dossier de sortie")
    p.add_argument("--result", help="texte du résultat mesuré")
    p.add_argument("--stdin", action="store_true", help="lit le résultat sur l'entrée standard")
    p.add_argument("--passed", action="store_true", help="marque le test comme réussi")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("gui", help="interface graphique dans le navigateur")
    p.add_argument("--port", type=int, default=8765, help="port local (défaut : 8765)")
    p.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    p.set_defaults(func=cmd_gui)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrompu.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
