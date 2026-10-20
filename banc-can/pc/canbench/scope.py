"""Décodage de trames CAN 2.0A à partir d'une capture d'oscilloscope (CSV).

Quand l'oscilloscope n'a pas l'option de décodage CAN, on enregistre la voie du
bus dans un fichier CSV et on la décode ici : seuillage, durée de chaque palier,
nombre de bits par palier, débourrage, contrôle du CRC-15.

Le décodage se fait **par durée des paliers** et non en échantillonnant à une
cadence fixe : une carte sur horloge HSI (±1 %) dérive d'environ 1,6 µs sur une
trame de 160 µs, soit presque un bit. Un palier de n bits dure n × T à ±1 % près,
donc son nombre de bits se retrouve par arrondi, quelle que soit la dérive. C'est,
en pratique, ce que fait la resynchronisation matérielle du contrôleur à chaque
front.

Le signal est lu en **niveau logique** (bus direct, sans transceiver) : bas = 0 =
dominant. Pour un bus différentiel, enregistrer CAN_H − CAN_L (fonction « Math »
de l'oscilloscope) : le seuil se place alors seul au milieu de l'excursion.

Usage :

    python -m canbench.scope capture.csv
    python -m canbench.scope capture.csv --bitrate 500000
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

from . import physical

#: Écart quadratique moyen toléré entre un palier et un nombre entier de bits. Une vraie
#: capture donne moins de 0,1 ; des paliers aléatoires (bruit) donnent près de 0,29.
_MAX_RESIDUAL_BITS = 0.15

#: Nombre maximal de bits consécutifs de même valeur dans la zone bourrée.
_STUFF_RUN = 5


@dataclass
class DecodedFrame:
    """Une trame standard de données retrouvée dans la capture."""

    start_s: float  #: date du front descendant du SOF
    can_id: int
    dlc: int
    data: bytes
    crc_ok: bool
    acked: bool | None  #: None si la capture s'arrête avant le créneau d'ACK
    bit_time_s: float  #: durée d'un bit mesurée sur cette trame
    problem: str = ""  #: non vide si la trame est invalide (forme, bourrage…)

    @property
    def text(self) -> str:
        """Les données en ASCII, avec « . » pour ce qui n'est pas imprimable."""
        return "".join(chr(b) if 32 <= b < 127 else "." for b in self.data)


# ---------------------------------------------------------------- lecture --


def read_csv(path: str | Path) -> tuple[list[float], list[float]]:
    """Lit (temps, tension) depuis un CSV d'oscilloscope.

    Accepte les en-têtes de texte, les lignes vides et le séparateur « , » ou
    « ; ». Les deux premières colonnes numériques sont prises pour le temps et la
    tension de la voie.
    """
    times: list[float] = []
    volts: list[float] = []
    with open(path, newline="", encoding="utf-8", errors="replace") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        # Une virgule décimale rend les virgules plus nombreuses que les séparateurs :
        # la seule présence d'un « ; » suffit à reconnaître le format européen.
        delimiter = ";" if ";" in sample else ","
        for row in csv.reader(handle, delimiter=delimiter):
            numbers: list[float] = []
            for cell in row:
                text = cell.strip().replace(",", ".") if delimiter == ";" else cell
                try:
                    numbers.append(float(text))
                except ValueError:
                    break
            if len(numbers) >= 2:
                times.append(numbers[0])
                volts.append(numbers[1])
    if len(times) < 10:
        raise ValueError("aucune courbe lisible : moins de 10 lignes (temps, tension)")
    return times, volts


# --------------------------------------------------------------- paliers --


def threshold(volts: list[float]) -> float:
    """Seuil au milieu de l'excursion, robuste aux dépassements aux fronts."""
    ordered = sorted(volts)
    low = ordered[int(0.02 * (len(ordered) - 1))]
    high = ordered[int(0.98 * (len(ordered) - 1))]
    if high - low < 0.05:
        raise ValueError("signal plat : moins de 50 mV d'excursion, rien à décoder")
    return (low + high) / 2.0


def levels(times: list[float], volts: list[float], level: float) -> list[tuple[float, int]]:
    """Fronts du signal seuillé : (date du front, valeur après le front).

    La date est interpolée entre les deux échantillons qui encadrent le seuil.
    Une hystérésis de 10 % de l'excursion écarte le bruit autour du seuil.
    """
    span = max(volts) - min(volts)
    high_level = level + 0.05 * span
    low_level = level - 0.05 * span

    state = 1 if volts[0] > level else 0
    edges: list[tuple[float, int]] = []
    last_index = 0
    for i in range(1, len(volts)):
        v = volts[i]
        if state == 1 and v < low_level:
            new_state = 0
        elif state == 0 and v > high_level:
            new_state = 1
        else:
            continue
        # Interpolation linéaire sur le dernier passage par le seuil.
        j = i
        while j > last_index and ((volts[j - 1] > level) == (new_state == 1)):
            j -= 1
        j = max(j, 1)
        v0, v1 = volts[j - 1], volts[j]
        frac = 0.0 if v1 == v0 else (level - v0) / (v1 - v0)
        frac = min(max(frac, 0.0), 1.0)
        edges.append((times[j - 1] + frac * (times[j] - times[j - 1]), new_state))
        state = new_state
        last_index = i
    return edges


# ----------------------------------------------------------------- trame --


def _destuff(bits: list[int], limit: int) -> tuple[list[int], int, str]:
    """Retire les bits de bourrage jusqu'à @p limit bits utiles.

    Retourne (bits utiles, indice du premier bit brut qui suit, problème). Si le
    dernier bit utile termine une série de cinq bits identiques, le bit de
    bourrage qui le suit est consommé aussi : il fait partie de la zone bourrée.
    """
    out: list[int] = []
    run = 0
    previous = None
    index = 0
    while index < len(bits) and len(out) < limit:
        value = bits[index]
        out.append(value)
        run = run + 1 if value == previous else 1
        previous = value
        index += 1
        if run == _STUFF_RUN:
            if index >= len(bits):
                break
            stuff = bits[index]
            index += 1
            if stuff == value:
                return out, index, "violation du bourrage : six bits identiques"
            previous, run = stuff, 1
    return out, index, ""


def _decode_bits(bits: list[int], start_s: float, bit_time: float) -> DecodedFrame | None:
    """Décode la suite de bits d'une trame, SOF compris (0), jusqu'à la fin connue."""
    header, _, problem = _destuff(bits, 19)
    if len(header) < 19 or header[0] != 0:
        return None

    can_id = int("".join(map(str, header[1:12])), 2)
    rtr, ide = header[12], header[13]
    dlc_raw = int("".join(map(str, header[15:19])), 2)
    if ide != 0:
        return DecodedFrame(
            start_s,
            can_id,
            dlc_raw,
            b"",
            False,
            None,
            bit_time,
            "trame étendue : non prise en charge",
        )
    if rtr != 0:
        return DecodedFrame(
            start_s,
            can_id,
            dlc_raw,
            b"",
            False,
            None,
            bit_time,
            "trame distante (RTR) : non prise en charge",
        )
    dlc = min(dlc_raw, 8)
    need = 19 + 8 * dlc + 15
    payload, after, problem = _destuff(bits, need)
    if len(payload) < need:
        return None

    data = bytes(int("".join(map(str, payload[19 + 8 * i : 27 + 8 * i])), 2) for i in range(dlc))
    # Le CRC recalculé sur SOF…CRC vaut 0 (propriété du CRC, voir physical.py).
    crc_ok = physical.crc15(payload) == 0
    frame = DecodedFrame(start_s, can_id, dlc, data, crc_ok, None, bit_time, problem)
    # Après le CRC : délimiteur (récessif) puis créneau d'acquittement (0 = acquitté).
    if after + 1 < len(bits):
        frame.acked = bits[after + 1] == 0
    return frame


def _fit_timing(runs: list[tuple[int, float]], nominal: float) -> tuple[float, float, float]:
    """Durée d'un bit, décalage des fronts et écart résiduel, ajustés sur la trame.

    En bus direct, le retour au niveau haut passe par une résistance de tirage et
    une capacité : le front montant est lent, donc franchit le seuil en retard. Les
    paliers bas sont mesurés trop longs, les hauts trop courts, d'un même écart
    @c skew. Estimer la durée du bit sur le palier le plus court serait faussé
    (un seul 1 isolé paraît à peine plus long qu'un demi-bit) : on cherche plutôt
    (bit, skew) qui rapproche le mieux chaque palier d'un nombre entier de bits.
    """
    sample = [(level, d) for level, d in runs if d < 7.5 * nominal]
    if not sample:
        return nominal, 0.0, 1.0

    # Le décalage n'est défini qu'à un bit près (décaler tous les paliers d'un bit
    # entier donne la même erreur) : on le borne à +-0,5 bit et, à erreur égale, on
    # garde le plus petit en valeur absolue (balayage par |m| croissant).
    best = (float("inf"), nominal, 0.0)
    offsets = sorted(range(-10, 11), key=abs)
    for k in range(-30, 31):
        bit = nominal * (1.0 + 0.001 * k)  # +-3 % : bien au-dela de la derive du HSI
        for m in offsets:
            skew = nominal * 0.05 * m
            error = 0.0
            for level, d in sample:
                x = (d - skew if level == 0 else d + skew) / bit
                error += (x - round(x)) ** 2
            if error < best[0] - 1e-12:
                best = (error, bit, skew)
    return best[1], best[2], (best[0] / len(sample)) ** 0.5


def decode(
    times: list[float], volts: list[float], bitrate: float = 500_000.0
) -> list[DecodedFrame]:
    """Retrouve toutes les trames standard de données de la capture."""
    nominal = 1.0 / bitrate
    edges = levels(times, volts, threshold(volts))
    frames: list[DecodedFrame] = []

    i = 0
    while i < len(edges):
        t0, value = edges[i]
        # Un SOF est un front descendant précédé d'au moins 7 bits récessifs (EOF/IFS)
        # ou du début de la capture.
        if value != 0:
            i += 1
            continue
        if i > 0 and (t0 - edges[i - 1][0]) < 6.5 * nominal:
            i += 1
            continue

        # Durées des paliers à partir du SOF, jusqu'à un palier récessif d'au moins
        # 10 bits : fin de trame (ACK delimiter + EOF + IFS).
        runs: list[tuple[int, float]] = []
        j = i
        while j + 1 < len(edges):
            duration = edges[j + 1][0] - edges[j][0]
            runs.append((edges[j][1], duration))
            if edges[j][1] == 1 and duration > 9.5 * nominal:
                break
            j += 1
        else:
            runs.append((edges[-1][1], max(times) - edges[-1][0]))

        bit_time, skew, residual = _fit_timing(runs, nominal)
        if residual > _MAX_RESIDUAL_BITS:
            i += 1  # paliers qui ne sont pas des multiples d'un bit : pas du CAN
            continue

        bits: list[int] = []
        for level, duration in runs:
            adjusted = duration - skew if level == 0 else duration + skew
            count = max(1, round(adjusted / bit_time))
            bits.extend([level] * count)

        frame = _decode_bits(bits, t0, bit_time)
        if frame is not None:
            frames.append(frame)
        i = j + 1
    return frames


# ---------------------------------------------------------------- sortie --


def report(frames: list[DecodedFrame]) -> list[str]:
    """Lignes lisibles pour le terminal."""
    if not frames:
        return ["Aucune trame CAN standard retrouvée dans la capture."]
    lines = []
    for n, f in enumerate(frames, 1):
        data = " ".join(f"{b:02X}" for b in f.data)
        ack = {True: "oui", False: "NON", None: "?"}[f.acked]
        verdict = "CRC ok" if f.crc_ok else "CRC FAUX"
        extra = f"  [{f.problem}]" if f.problem else ""
        lines.append(
            f"#{n}  t={f.start_s * 1e6:9.1f} µs  id=0x{f.can_id:03X}  dlc={f.dlc}  "
            f"data={data or '-'}  « {f.text} »  {verdict}  acquittée : {ack}  "
            f"bit={f.bit_time_s * 1e6:.3f} µs{extra}"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", help="capture de l'oscilloscope (temps, tension)")
    parser.add_argument("--bitrate", type=float, default=500_000.0, help="débit nominal en bit/s")
    args = parser.parse_args(argv)

    try:
        times, volts = read_csv(args.csv)
        frames = decode(times, volts, args.bitrate)
    except (OSError, ValueError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 2

    print(f"{len(times)} points, excursion {min(volts):.3f} à {max(volts):.3f} V")
    for line in report(frames):
        print(line)
    return 0 if frames and all(f.crc_ok for f in frames) else 1


if __name__ == "__main__":
    raise SystemExit(main())
