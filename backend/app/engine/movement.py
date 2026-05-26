"""Unit movement validation and application. Pure — returns new GameState."""

from __future__ import annotations

from dataclasses import replace

from app.engine.borders import auto_assign_workers, recompute_claims
from app.engine.hex import Hex, hex_distance
from app.engine.models import City, GameState, Unit
from app.engine.terrain import is_passable


class MoveError(ValueError):
    """Raised when a move is invalid."""


def _find_unit(state: GameState, unit_id: int) -> Unit:
    for u in state.units:
        if u.id == unit_id:
            return u
    raise MoveError(f"unknown unit id {unit_id}")


def _city_at(state: GameState, destination: Hex) -> City | None:
    return next((city for city in state.cities if city.location == destination), None)


def move_unit(state: GameState, unit_id: int, destination: Hex) -> GameState:
    unit = _find_unit(state, unit_id)

    if unit.moves_remaining <= 0:
        raise MoveError(f"unit {unit_id} has no moves remaining")

    if destination not in state.map:
        raise MoveError(f"destination {destination} is off map")

    if hex_distance(unit.location, destination) != 1:
        raise MoveError(
            f"destination {destination} is not adjacent to unit at {unit.location}"
        )

    tile = state.map.get(destination)
    assert tile is not None  # guarded by membership check
    if not is_passable(tile.terrain):
        raise MoveError(f"terrain {tile.terrain.value} is impassable")

    # Block stacking: can't move onto a tile occupied by another unit.
    for other in state.units:
        if other.id != unit_id and other.location == destination:
            raise MoveError(f"destination {destination} is occupied")

    moved = replace(
        unit.with_location(destination).with_moves(unit.moves_remaining - 1),
        acted_this_turn=True,
        work_order=None,
        work_turns_remaining=0,
    )
    new_units = tuple(moved if u.id == unit_id else u for u in state.units)
    city = _city_at(state, destination)
    if city is None or city.owner == unit.owner:
        return replace(state, units=new_units)
    if city.health > 0:
        raise MoveError("enemy city must be reduced to 0 health before capture")

    captured_city = replace(
        city,
        owner=unit.owner,
        health=city.max_health,
        population=max(1, city.population - 1),
        food_stored=0,
        production_stored=0,
        is_capital=False,
        production_queue=(),
        culture_stored=0,
        worked_tiles=frozenset({city.location}),
    )
    replacement_cities = [
        replace(captured_city, is_capital=not any(
            c.owner == unit.owner and c.id != city.id and c.is_capital
            for c in state.cities
        ))
        if existing.id == city.id
        else existing
        for existing in state.cities
    ]

    old_owner_remaining = [c for c in replacement_cities if c.owner == city.owner]
    if old_owner_remaining and not any(c.is_capital for c in old_owner_remaining):
        promote_id = old_owner_remaining[0].id
        replacement_cities = [
            replace(c, is_capital=True) if c.id == promote_id else c
            for c in replacement_cities
        ]
    captured_state = replace(state, units=new_units, cities=tuple(replacement_cities))
    captured_state = recompute_claims(captured_state)
    captured_state = auto_assign_workers(captured_state)
    return captured_state
