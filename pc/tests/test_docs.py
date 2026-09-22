"""Vérifie que la documentation ne dérive pas du code.

Un tableau de brochage recopié à la main finit toujours par mentir. Ces tests
lient `docs/pinout.md` et `docs/config_logicielle.md` aux `board.h`, qui font
autorité, et échouent dès qu'une valeur diverge.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BOARDS = sorted((REPO_ROOT / "firmware" / "boards").glob("*/board.h"))

#: Constantes de board.h qui ne désignent pas une broche exploitable dans la doc.
NOT_A_PIN = {"BENCH_FLOATING_PINS"}


def _defines(text: str) -> dict[str, str]:
    """Extrait les `#define BENCH_*`, commentaire de fin de ligne retiré."""
    found: dict[str, str] = {}
    for match in re.finditer(r"^#define\s+(BENCH_\w+)\s+(.+?)\s*$", text, re.MULTILINE):
        value = re.split(r"/\*|//", match.group(2))[0].strip()
        found[match.group(1)] = value
    return found


def _pins(board_text: str) -> dict[str, str]:
    """Associe chaque constante `*_PIN` au nom de broche STM32 correspondant.

    `BENCH_CAN_TX_PIN GPIO_PIN_12` + `BENCH_CAN_TX_PORT GPIOA` donne « PA12 ».
    """
    defines = _defines(board_text)
    pins: dict[str, str] = {}

    for name, value in defines.items():
        if not name.endswith("_PIN") or name in NOT_A_PIN:
            continue
        match = re.fullmatch(r"GPIO_PIN_(\d+)", value)
        if match is None:
            continue
        port = defines.get(name[: -len("_PIN")] + "_PORT", "")
        port_match = re.fullmatch(r"GPIO([A-G])", port)
        if port_match is None:
            continue
        pins[name] = f"P{port_match.group(1)}{match.group(1)}"
    return pins


@pytest.mark.skipif(not BOARDS, reason="aucun board.h")
@pytest.mark.parametrize("board", BOARDS, ids=lambda p: p.parent.name)
def test_pinout_coherent_avec_board_h(board: Path) -> None:
    """Toute broche déclarée dans un board.h doit figurer dans pinout.md."""
    pinout = (REPO_ROOT / "docs" / "pinout.md").read_text(encoding="utf-8")
    pins = _pins(board.read_text(encoding="utf-8"))

    assert pins, f"aucune broche extraite de {board}"

    manquantes = {name: pin for name, pin in pins.items() if not re.search(rf"\b{pin}\b", pinout)}
    assert not manquantes, (
        f"{board.parent.name} : broches absentes de docs/pinout.md — {manquantes}. "
        "Mettre la documentation a jour, board.h fait autorite."
    )


@pytest.mark.skipif(not BOARDS, reason="aucun board.h")
@pytest.mark.parametrize("board", BOARDS, ids=lambda p: p.parent.name)
def test_bit_timing_documente(board: Path) -> None:
    """Les valeurs de temps de bit de board.h doivent apparaître dans la doc."""
    doc = (REPO_ROOT / "docs" / "config_logicielle.md").read_text(encoding="utf-8")
    defines = _defines(board.read_text(encoding="utf-8"))

    for key in ("BENCH_CAN_PRESCALER", "BENCH_CAN_TSEG1", "BENCH_CAN_TSEG2", "BENCH_CAN_SJW"):
        value = re.match(r"\d+", defines[key])
        assert value is not None, f"{key} n'est pas une valeur numerique : {defines[key]!r}"
        assert re.search(rf"\b{value.group(0)}\b", doc), (
            f"{key} = {value.group(0)} n'apparait pas dans docs/config_logicielle.md"
        )


def test_corrections_dossier_listees() -> None:
    """Chaque écart relevé doit figurer dans la section destinée au dossier v0.2."""
    plan = (REPO_ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    assert "Corrections à reporter dans le dossier v0.2" in plan

    attendus = [
        "PB9",  # broche inexistante sur le boitier
        "BOOT0",  # PB8
        "PA2",  # TX du VCP
        "HW1",  # cavalier a retirer
        "SB9",  # HSE non active par defaut
        "PA5",  # entree flottante
        "23,04",  # duree de rafraichissement OLED
        "tableau 7",  # metrique « Perdus »
        "120",  # terminaisons des modules
        "216",  # duree de GO
    ]
    manquants = [a for a in attendus if a not in plan]
    assert not manquants, f"points absents de PLAN.md : {manquants}"
