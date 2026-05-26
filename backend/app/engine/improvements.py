"""Worker-driven tile improvements: farms, mines, roads.

A worker starts an improvement on its current tile via `start_improvement`.
Work takes a fixed number of turns (`IMPROVEMENT_TURNS`). `tick_improvements`
decrements `work_turns_remaining` for every worker; when it hits zero the
improvement is committed to the tile and the worker is freed.

Workers may only improve tiles owned by their civilization. Moving cancels
the work order.

All functions are pure: `(state, args) -> GameState`.
"""

from __future__ import annotations

from dataclasses import replace

from app.engine.hex import Hex
from app.engine.models import GameMap, GameState, Tile, Unit, UnitType
from app.engine.terrain import (
    IMPROVEMENT_TERRAIN,
    IMPROVEMENT_TURNS,
    Improvement,
)


class ImprovementError(ValueError):
    """Raised when a build-improvement request is invalid."""


# Machine-readable codes for LLM/UI feedback.
ERR_NOT_WORKER = "not_worker"
ERR_BAD_TERRAIN = "bad_terrain_for_improvement"
ERR_ALREADY_IMPROVED = "tile_already_improved"
ERR_NOT_IN_BORDERS = "not_in_own_borders"
ERR_WORKER_BUSY = "worker_already_busy"


def _find_unit(state: GameState, unit_id: int) -> Unit:
    for u in state.units:
        if u.id == unit_id:
            return u
    raise ImprovementError(f"unknown unit id {unit_id}")


def _find_city_owner(state: GameState, city_id: int) -> int | None:
    for c in state.cities:
        if c.id == city_id:
            return c.owner
    return None


def can_improve(
    state: GameState,
    tile: Tile,
    improvement: Improvement,
    owner_id: int,
) -> str | None:
    """Return `None` if the tile may host *improvement* for *owner_id*, else
    a machine-readable error code."""
    if tile.improvement is not None:
        return ERR_ALREADY_IMPROVED
    if tile.terrain not in IMPROVEMENT_TERRAIN[improvement]:
        return ERR_BAD_TERRAIN
    owning_city_id = state.tile_owner.get(tile.coord)
    if owning_city_id is None:
        return ERR_NOT_IN_BORDERS
    if _find_city_owner(state, owning_city_id) != owner_id:
        return ERR_NOT_IN_BORDERS
    return None


def start_improvement(
    state: GameState, unit_id: int, improvement: Improvement
) -> GameState:
    """Begin building *improvement* on the worker's current tile.

    Raises ImprovementError with a machine-readable code on rejection. The
    worker spends all remaining moves this turn.
    """
    unit = _find_unit(state, unit_id)
    if unit.type is not UnitType.WORKER:
        raise ImprovementError(ERR_NOT_WORKER)
    if unit.work_order is not None:
        raise ImprovementError(ERR_WORKER_BUSY)
    tile = state.map.get(unit.location)
    if tile is None:
        raise ImprovementError(ERR_BAD_TERRAIN)
    err = can_improve(state, tile, improvement, unit.owner)
    if err is not None:
        raise ImprovementError(err)
    updated = replace(
        unit,
        work_order=(unit.location, improvement),
        work_turns_remaining=IMPROVEMENT_TURNS[improvement],
        moves_remaining=0,
        acted_this_turn=True,
    )
    new_units = tuple(updated if u.id == unit_id else u for u in state.units)
    return replace(state, units=new_units)


def cancel_improvement(state: GameState, unit_id: int) -> GameState:
    """Drop the worker's pending work order (e.g., when they move)."""
    unit = _find_unit(state, unit_id)
    if unit.work_order is None:
        return state
    updated = replace(unit, work_order=None, work_turns_remaining=0)
    new_units = tuple(updated if u.id == unit_id else u for u in state.units)
    return replace(state, units=new_units)


def _apply_improvement_to_tile(
    game_map: GameMap, coord: Hex, improvement: Improvement
) -> GameMap:
    tile = game_map.tiles.get(coord)
    if tile is None:
        return game_map
    new_tile = replace(tile, improvement=improvement)
    new_tiles = dict(game_map.tiles)
    new_tiles[coord] = new_tile
    return GameMap(radius=game_map.radius, tiles=new_tiles)


def tick_improvements(state: GameState) -> GameState:
    """Advance every worker's pending order by one turn.

    Completed orders apply their improvement to the tile and clear the order.
    Orders for workers no longer standing on the target tile are cancelled.
    """
    game_map = state.map
    new_units: list[Unit] = []
    for unit in state.units:
        if unit.work_order is None:
            new_units.append(unit)
            continue
        target_hex, improvement = unit.work_order
        if unit.location != target_hex:
            new_units.append(
                replace(unit, work_order=None, work_turns_remaining=0)
            )
            continue
        remaining = unit.work_turns_remaining - 1
        if remaining <= 0:
            game_map = _apply_improvement_to_tile(game_map, target_hex, improvement)
            new_units.append(
                replace(unit, work_order=None, work_turns_remaining=0)
            )
        else:
            new_units.append(replace(unit, work_turns_remaining=remaining))
    return replace(state, map=game_map, units=tuple(new_units))
