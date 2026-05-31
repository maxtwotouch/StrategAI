"""Per-turn gold income.

Gold is deliberately simple for the web game: every civilization gains a flat
amount each turn. There is no unit upkeep and no bankruptcy disbanding.
"""

from __future__ import annotations

from dataclasses import replace

from app.engine.models import Civilization, GameState

GOLD_PER_TURN = 5


def city_gold_income(state: GameState, city_id: int) -> int:
    """City-level gold is no longer modeled."""
    return 0


def civ_gold_income(state: GameState, civ_id: int) -> int:
    return GOLD_PER_TURN


def civ_gold_upkeep(state: GameState, civ_id: int) -> int:
    return 0


def tick_economy(state: GameState) -> GameState:
    """Apply flat gold income per civ."""
    new_civs: list[Civilization] = []
    for civ in state.civs:
        new_civs.append(replace(civ, gold=civ.gold + GOLD_PER_TURN))
    return replace(state, civs=tuple(new_civs))
