"""Unit movement validation and application. Pure — returns new GameState."""

from __future__ import annotations

from dataclasses import replace

from app.engine.hex import Hex, hex_distance
from app.engine.models import GameState, Unit
from app.engine.terrain import is_passable


class MoveError(ValueError):
    """Raised when a move is invalid."""


def _find_unit(state: GameState, unit_id: int) -> Unit:
    for u in state.units:
        if u.id == unit_id:
            return u
    raise MoveError(f"unknown unit id {unit_id}")


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

    moved = unit.with_location(destination).with_moves(unit.moves_remaining - 1)
    new_units = tuple(moved if u.id == unit_id else u for u in state.units)
    return replace(state, units=new_units)
