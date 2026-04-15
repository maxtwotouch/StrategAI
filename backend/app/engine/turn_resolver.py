"""Turn resolution. End-of-turn bookkeeping + city ticks.

Future: combat, research, victory checks.
"""

from __future__ import annotations

from dataclasses import replace

from app.engine.models import GameState
from app.engine.production import process_cities
from app.engine.research import tick_research


def end_turn(state: GameState) -> GameState:
    state = process_cities(state)
    state = tick_research(state)
    refreshed_units = tuple(u.with_moves(u.stats.moves) for u in state.units)
    return replace(state, turn=state.turn + 1, units=refreshed_units)
