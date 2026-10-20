"""Décodage des trames via l'ICD, et calcul de charge du bus."""

from __future__ import annotations

from dataclasses import dataclass

from . import icd_gen
from .bus import Frame


@dataclass
class Decoded:
    """Résultat du décodage d'une trame."""

    name: str
    can_id: int
    known: bool
    signals: dict[str, float]
    dlc_ok: bool
    raw: bytes

    def summary(self) -> str:
        if not self.known:
            return f"0x{self.can_id:03X}  <inconnu>  {self.raw.hex(' ')}"
        if not self.dlc_ok:
            return f"0x{self.can_id:03X}  {self.name}  DLC INCOHERENT ({len(self.raw)})"
        values = "  ".join(f"{k}={_fmt(v)}" for k, v in self.signals.items())
        return f"0x{self.can_id:03X}  {self.name}  {values}"


def _fmt(value: float) -> str:
    if isinstance(value, float) and not value.is_integer():
        return f"{value:.4g}"
    return str(int(value))


def decode(frame: Frame, profile: str = icd_gen.DEFAULT_PROFILE) -> Decoded:
    """Décode une trame selon l'ICD.

    Une trame inconnue n'est pas une erreur : le banc n'applique aucun filtre,
    et voir passer un identifiant inattendu fait partie de ce qu'il doit montrer.
    """
    ids = icd_gen.PROFILES[profile]["ids"]
    by_id = {can_id: name for name, can_id in ids.items()}
    name = by_id.get(frame.can_id)

    if name is None:
        return Decoded("<inconnu>", frame.can_id, False, {}, True, frame.data)

    meta = icd_gen.FRAMES.get(frame.can_id)
    if meta is None:
        return Decoded(name, frame.can_id, True, {}, True, frame.data)

    if len(frame.data) != meta["dlc"]:
        return Decoded(name, frame.can_id, True, {}, False, frame.data)

    layout = icd_gen.LAYOUTS.get(meta["layout"])
    if layout is None:  # ARM et GO ne portent aucun signal
        return Decoded(name, frame.can_id, True, {}, True, frame.data)

    decoded = layout.unpack(frame.data)
    signals = {signal["name"]: getattr(decoded, signal["name"]) for signal in meta["signals"]}
    return Decoded(name, frame.can_id, True, signals, True, frame.data)


# ---------------------------------------------------------------------------
#  Charge du bus
# ---------------------------------------------------------------------------

#: Bits d'une trame standard hors charge utile, avant bit stuffing.
#: SOF 1 + ID 11 + RTR 1 + IDE 1 + r0 1 + DLC 4 + CRC 15 + délimiteur 1
#: + ACK 2 + EOF 7 = 44 bits.
FRAME_OVERHEAD_BITS = 44

#: Intermission : trois bits récessifs séparant deux trames.
INTERMISSION_BITS = 3


def frame_bits(dlc: int, *, worst_case: bool = True) -> int:
    """Nombre de bits occupés par une trame standard de @p dlc octets.

    Le *bit stuffing* insère un bit de polarité inverse après cinq bits
    identiques consécutifs. Il ne s'applique qu'au champ soumis au stuffing —
    du SOF à la fin du CRC — soit 34 + 8·DLC bits ici ; le délimiteur de CRC,
    l'ACK et l'EOF n'y sont pas soumis.

    Au pire cas, le nombre de bits insérés vaut ``(N - 1) // 4`` pour N bits
    soumis au stuffing.
    """
    payload = 8 * dlc
    stuffable = 34 + payload  # SOF+ID+RTR+IDE+r0+DLC+données+CRC
    fixed = FRAME_OVERHEAD_BITS - 34 + INTERMISSION_BITS  # délimiteur, ACK, EOF, intermission

    total = stuffable + fixed
    if worst_case:
        total += (stuffable - 1) // 4
    return total


def frame_duration(dlc: int, bitrate: int = icd_gen.BITRATE, *, worst_case: bool = True) -> float:
    """Durée d'occupation du bus par une trame, en secondes."""
    return frame_bits(dlc, worst_case=worst_case) / bitrate


def theoretical_load(bitrate: int = icd_gen.BITRATE, *, worst_case: bool = True) -> dict:
    """Charge théorique produite par les trames périodiques de l'ICD."""
    total_bps = 0.0
    details = []

    for can_id, meta in icd_gen.FRAMES.items():
        period_ms = meta.get("period_ms")
        if not period_ms:
            continue
        bits = frame_bits(meta["dlc"], worst_case=worst_case)
        bps = bits * 1000.0 / period_ms
        total_bps += bps
        details.append(
            {
                "name": meta["name"],
                "can_id": can_id,
                "period_ms": period_ms,
                "bits": bits,
                "bits_per_s": bps,
            }
        )

    return {
        "bitrate": bitrate,
        "worst_case": worst_case,
        "bits_per_s": total_bps,
        "load": total_bps / bitrate,
        "frames": sorted(details, key=lambda d: d["can_id"]),
    }


def measured_load(frames: list[Frame], duration: float, bitrate: int = icd_gen.BITRATE) -> dict:
    """Charge mesurée à partir des trames effectivement observées."""
    if duration <= 0:
        raise ValueError("durée nulle")

    bits = sum(frame_bits(f.dlc, worst_case=False) for f in frames)
    bits_worst = sum(frame_bits(f.dlc, worst_case=True) for f in frames)
    return {
        "frames": len(frames),
        "duration": duration,
        "bits_per_s": bits / duration,
        "load": bits / duration / bitrate,
        "load_worst_case": bits_worst / duration / bitrate,
        "frames_per_s": len(frames) / duration,
    }
