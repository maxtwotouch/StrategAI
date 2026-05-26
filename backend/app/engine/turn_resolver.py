"""Turn resolution. End-of-turn bookkeeping + city ticks.

Future: combat, research, victory checks.
"""

from __future__ import annotations

from dataclasses import replace

from app.engine.borders import auto_assign_workers, grow_borders
from app.engine.economy import tick_economy
from app.engine.improvements import tick_improvements
from app.engine.models import GameState, Unit
from app.engine.production import process_cities
from app.engine.research import tick_research

# Heal rates by tile-ownership classification.
HEAL_OWN_TERRITORY = 4
HEAL_UNOWNED = 2
HEAL_ENEMY_TERRITORY = 1


def _territory_classification(state: GameState, unit: Unit) -> str:
    """Return one of 'own', 'unowned', or 'enemy' for the unit's tile."""
    owning_city_id = state.tile_owner.get(unit.location)
    if owning_city_id is None:
        return "unowned"
    owning_city = next((c for c in state.cities if c.id == owning_city_id), None)
    if owning_city is None:
        return "unowned"
    return "own" if owning_city.owner == unit.owner else "enemy"


def _heal_amount(state: GameState, unit: Unit) -> int:
    if unit.acted_this_turn:
        return 0
    bucket = _territory_classification(state, unit)
    if bucket == "own":
        return HEAL_OWN_TERRITORY
    if bucket == "enemy":
        return HEAL_ENEMY_TERRITORY
    return HEAL_UNOWNED


def _heal_units(state: GameState) -> GameState:
    new_units: list[Unit] = []
    for unit in state.units:
        amount = _heal_amount(state, unit)
        if amount <= 0 or unit.health >= unit.stats.max_health:
            new_units.append(unit)
            continue
        new_health = min(unit.stats.max_health, unit.health + amount)
        new_units.append(replace(unit, health=new_health))
    return replace(state, units=tuple(new_units))


def end_turn(state: GameState) -> GameState:
    state = process_cities(state)
    state = tick_improvements(state)
    state = tick_economy(state)
    state = grow_borders(state)
    state = auto_assign_workers(state)
    state = _heal_units(state)
    state = tick_research(state)
    refreshed_units = tuple(
        replace(u.with_moves(u.stats.moves), acted_this_turn=False)
        for u in state.units
    )
    return replace(state, turn=state.turn + 1, units=refreshed_units)
