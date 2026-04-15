"""Tactical executor: turn high-level goals into validated primitive actions.

The executor is the deterministic "game AI" layer. LLM agents emit Goals
(MoveTo, FoundCityNear, AttackUnit) and the executor produces a sequence of
primitive Actions that respect move-point budgets, hex pathfinding, and
occupancy. The produced actions are still run through the validator by the
caller before being applied to the engine.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, replace
from typing import Union

from app.api.actions import (
    Action,
    AttackAction,
    FoundCityAction,
    MoveAction,
)
from app.engine.hex import Hex, hex_distance, hex_neighbors
from app.engine.models import GameState, Unit, UnitType
from app.engine.terrain import is_passable


@dataclass(frozen=True, slots=True)
class MoveTo:
    unit_id: int
    target: Hex


@dataclass(frozen=True, slots=True)
class FoundCityNear:
    unit_id: int
    target: Hex
    name: str


@dataclass(frozen=True, slots=True)
class AttackUnit:
    attacker_id: int
    target_id: int


Goal = Union[MoveTo, FoundCityNear, AttackUnit]


def _unit(state: GameState, uid: int) -> Unit | None:
    for u in state.units:
        if u.id == uid:
            return u
    return None


def _occupied(state: GameState, coord: Hex, ignore_id: int | None = None) -> bool:
    return any(
        u.location == coord and u.id != ignore_id for u in state.units
    )


def find_path(
    state: GameState, start: Hex, goal: Hex, ignore_unit_id: int | None = None
) -> list[Hex] | None:
    """A* on the hex grid. Returns coords from start to goal inclusive, or None."""
    if start not in state.map or goal not in state.map:
        return None
    if start == goal:
        return [start]

    open_heap: list[tuple[int, int, Hex]] = []
    counter = 0
    heapq.heappush(open_heap, (0, counter, start))
    came_from: dict[Hex, Hex] = {}
    g_score: dict[Hex, int] = {start: 0}

    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        if current == goal:
            path: list[Hex] = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        for neighbor in hex_neighbors(current):
            if neighbor not in state.map:
                continue
            tile = state.map.get(neighbor)
            if tile is None or not is_passable(tile.terrain):
                if neighbor != goal:
                    continue
            if _occupied(state, neighbor, ignore_id=ignore_unit_id) and neighbor != goal:
                continue
            tentative = g_score[current] + 1
            if tentative < g_score.get(neighbor, 1 << 30):
                g_score[neighbor] = tentative
                came_from[neighbor] = current
                f = tentative + hex_distance(neighbor, goal)
                counter += 1
                heapq.heappush(open_heap, (f, counter, neighbor))

    return None


def _walk_budget(
    state: GameState, unit: Unit, target: Hex, max_steps: int
) -> tuple[list[MoveAction], Hex]:
    """Emit MoveActions along the shortest path, up to max_steps.

    Returns (actions, final_location). Simulates occupancy as steps are taken
    so the executor doesn't emit moves that would collide with itself.
    """
    if max_steps <= 0 or unit.location == target:
        return [], unit.location

    path = find_path(state, unit.location, target, ignore_unit_id=unit.id)
    if path is None or len(path) < 2:
        return [], unit.location

    steps = path[1 : 1 + max_steps]
    actions = [MoveAction(unit_id=unit.id, destination=step) for step in steps]
    return actions, steps[-1] if steps else unit.location


def _execute_move_to(state: GameState, goal: MoveTo) -> list[Action]:
    unit = _unit(state, goal.unit_id)
    if unit is None or unit.location == goal.target:
        return []
    actions, _ = _walk_budget(state, unit, goal.target, unit.moves_remaining)
    return list(actions)


def _execute_found_city_near(state: GameState, goal: FoundCityNear) -> list[Action]:
    unit = _unit(state, goal.unit_id)
    if unit is None or unit.type is not UnitType.SETTLER:
        return []

    actions: list[Action] = []
    location = unit.location
    if location != goal.target:
        moves, location = _walk_budget(
            state, unit, goal.target, unit.moves_remaining
        )
        actions.extend(moves)

    if location == goal.target:
        actions.append(FoundCityAction(unit_id=goal.unit_id, name=goal.name))
    return actions


def _execute_attack_unit(state: GameState, goal: AttackUnit) -> list[Action]:
    attacker = _unit(state, goal.attacker_id)
    target = _unit(state, goal.target_id)
    if attacker is None or target is None:
        return []

    actions: list[Action] = []
    if hex_distance(attacker.location, target.location) > 1:
        # Move to any tile adjacent to the target.
        adjacent = [
            n
            for n in hex_neighbors(target.location)
            if n in state.map and not _occupied(state, n, ignore_id=attacker.id)
        ]
        if not adjacent:
            return []
        # Pick the closest adjacent tile.
        approach = min(adjacent, key=lambda h: hex_distance(attacker.location, h))
        moves, final = _walk_budget(
            state, attacker, approach, max(attacker.moves_remaining - 1, 0)
        )
        actions.extend(moves)
        if hex_distance(final, target.location) != 1:
            return actions  # Couldn't get adjacent this turn.

    actions.append(
        AttackAction(attacker_id=goal.attacker_id, target_id=goal.target_id)
    )
    return actions


def execute_goal(state: GameState, civ_id: int, goal: Goal) -> list[Action]:
    """Translate a single goal into primitive actions for the given civ."""
    if isinstance(goal, MoveTo):
        return _execute_move_to(state, goal)
    if isinstance(goal, FoundCityNear):
        return _execute_found_city_near(state, goal)
    if isinstance(goal, AttackUnit):
        return _execute_attack_unit(state, goal)
    return []
