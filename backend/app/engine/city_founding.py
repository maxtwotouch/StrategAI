"""Settler-based city founding. Pure — returns new GameState."""

from __future__ import annotations

from dataclasses import replace

from app.engine.models import City, GameState, Unit, UnitType
from app.engine.terrain import Terrain

UNFOUNDABLE_TERRAIN: frozenset[Terrain] = frozenset(
    {Terrain.OCEAN, Terrain.MOUNTAIN}
)


class FoundError(ValueError):
    """Raised when a city cannot be founded."""


def _find_unit(state: GameState, unit_id: int) -> Unit:
    for u in state.units:
        if u.id == unit_id:
            return u
    raise FoundError(f"unknown unit id {unit_id}")


def _next_city_id(state: GameState) -> int:
    return max((c.id for c in state.cities), default=0) + 1


def found_city(state: GameState, unit_id: int, name: str) -> GameState:
    unit = _find_unit(state, unit_id)

    if unit.type != UnitType.SETTLER:
        raise FoundError(f"unit {unit_id} is not a settler")

    tile = state.map.get(unit.location)
    if tile is None:
        raise FoundError(f"unit location {unit.location} is off map")
    if tile.terrain in UNFOUNDABLE_TERRAIN:
        raise FoundError(f"cannot found city on {tile.terrain.value}")

    for city in state.cities:
        if city.location == unit.location:
            raise FoundError(f"a city already exists at {unit.location}")

    new_city = City(
        id=_next_city_id(state),
        owner=unit.owner,
        name=name,
        location=unit.location,
        population=1,
    )
    new_cities = state.cities + (new_city,)
    new_units = tuple(u for u in state.units if u.id != unit_id)
    return replace(state, cities=new_cities, units=new_units)
