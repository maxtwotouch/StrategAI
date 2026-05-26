"""Per-turn gold income, upkeep, and bankruptcy.

Income comes from the gold field of `tile_yields` on each city's worked tiles
plus building gold bonuses (currently just the Market). Upkeep comes from a
per-unit-type table.

If a civ's gold would go below zero after applying delta, the oldest non-settler
unit it owns is disbanded and `gold` is clamped to 0. The bankruptcy event is
not yet surfaced through the turn-report channel (that lands in Tier 5/UX).
"""

from __future__ import annotations

from dataclasses import replace

from app.engine.borders import working_yields
from app.engine.buildings import city_gold_bonus
from app.engine.models import (
    UNIT_UPKEEP,
    City,
    Civilization,
    GameState,
    Unit,
    UnitType,
)


def city_gold_income(state: GameState, city: City) -> int:
    """Gold from worked tiles + building bonuses."""
    return working_yields(state, city).gold + city_gold_bonus(city)


def civ_gold_income(state: GameState, civ_id: int) -> int:
    return sum(city_gold_income(state, c) for c in state.cities_for(civ_id))


def civ_gold_upkeep(state: GameState, civ_id: int) -> int:
    return sum(UNIT_UPKEEP[u.type] for u in state.units_for(civ_id))


def _disband_oldest_non_settler(units: tuple[Unit, ...], civ_id: int) -> tuple[Unit, ...]:
    """Drop the oldest (lowest-id) non-settler unit owned by *civ_id*.

    Returns the original tuple unchanged if no eligible unit exists.
    """
    candidates = sorted(
        (u for u in units if u.owner == civ_id and u.type is not UnitType.SETTLER),
        key=lambda u: u.id,
    )
    if not candidates:
        return units
    victim_id = candidates[0].id
    return tuple(u for u in units if u.id != victim_id)


def tick_economy(state: GameState) -> GameState:
    """Apply gold income/upkeep delta per civ. Disband on bankruptcy."""
    new_units = state.units
    new_civs: list[Civilization] = []
    for civ in state.civs:
        income = civ_gold_income(state, civ.id)
        upkeep = civ_gold_upkeep(state, civ.id) if any(u.owner == civ.id for u in new_units) else 0
        # Recompute upkeep against new_units in case we disbanded for a prior civ
        # (shouldn't happen in current loop order, but defensive).
        upkeep = sum(UNIT_UPKEEP[u.type] for u in new_units if u.owner == civ.id)
        delta = income - upkeep
        gold_after = civ.gold + delta
        if gold_after < 0:
            new_units = _disband_oldest_non_settler(new_units, civ.id)
            gold_after = 0
        new_civs.append(replace(civ, gold=gold_after))
    return replace(state, units=new_units, civs=tuple(new_civs))
