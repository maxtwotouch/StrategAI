"""Tests for tactical executor: pathfinding + goal -> action translation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.api.actions import FoundCityAction, MoveAction
from app.engine.executor import (
    AttackUnit,
    FoundCityNear,
    MoveTo,
    execute_goal,
    find_path,
)
from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import (
    Civilization,
    GameState,
    Tile,
    Unit,
    UnitType,
    UNIT_STATS,
)
from app.engine.terrain import Terrain


def _open_map(radius: int = 5):
    game_map = generate_map(radius, seed=1)
    tiles: dict[Hex, Tile] = {}
    for coord in game_map.tiles:
        on_edge = max(abs(coord.q), abs(coord.r), abs(coord.s)) == radius
        terrain = Terrain.OCEAN if on_edge else Terrain.GRASSLAND
        tiles[coord] = Tile(coord=coord, terrain=terrain)
    return replace(game_map, tiles=tiles)


def _state(units: tuple[Unit, ...], radius: int = 5) -> GameState:
    game_map = _open_map(radius)
    civs = (
        Civilization(id=0, name="A", leader_name="x", is_human=False),
        Civilization(id=1, name="B", leader_name="y", is_human=False),
    )
    return GameState(
        turn=1,
        map=game_map,
        civs=civs,
        cities=(),
        units=units,
        current_civ_idx=0,
    )


def _settler(uid: int, owner: int, loc: Hex) -> Unit:
    s = UNIT_STATS[UnitType.SETTLER]
    return Unit(id=uid, owner=owner, type=UnitType.SETTLER, location=loc,
                health=s.max_health, moves_remaining=s.moves)


def _warrior(uid: int, owner: int, loc: Hex) -> Unit:
    s = UNIT_STATS[UnitType.WARRIOR]
    return Unit(id=uid, owner=owner, type=UnitType.WARRIOR, location=loc,
                health=s.max_health, moves_remaining=s.moves)


@pytest.mark.unit
def test_find_path_adjacent() -> None:
    state = _state((_warrior(1, 0, Hex(0, 0)),))
    path = find_path(state, Hex(0, 0), Hex(1, 0))
    assert path == [Hex(0, 0), Hex(1, 0)]


@pytest.mark.unit
def test_find_path_longer_route() -> None:
    state = _state((_warrior(1, 0, Hex(0, 0)),))
    path = find_path(state, Hex(0, 0), Hex(3, 0))
    assert path is not None
    assert path[0] == Hex(0, 0)
    assert path[-1] == Hex(3, 0)
    assert len(path) == 4  # 3 steps


@pytest.mark.unit
def test_find_path_unreachable_returns_none() -> None:
    state = _state((_warrior(1, 0, Hex(0, 0)),))
    # Off-map target.
    path = find_path(state, Hex(0, 0), Hex(99, 99))
    assert path is None


@pytest.mark.unit
def test_moveto_emits_moves_within_budget() -> None:
    state = _state((_warrior(1, 0, Hex(0, 0)),))
    actions = execute_goal(state, civ_id=0, goal=MoveTo(unit_id=1, target=Hex(3, 0)))
    # Warrior has 2 moves, should emit 2 MoveActions.
    assert len(actions) == 2
    assert all(isinstance(a, MoveAction) for a in actions)
    assert actions[0].destination == Hex(1, 0)
    assert actions[1].destination == Hex(2, 0)


@pytest.mark.unit
def test_moveto_target_reached_emits_nothing_extra() -> None:
    state = _state((_warrior(1, 0, Hex(0, 0)),))
    actions = execute_goal(state, civ_id=0, goal=MoveTo(unit_id=1, target=Hex(0, 0)))
    assert actions == []


@pytest.mark.unit
def test_found_city_near_walks_then_founds() -> None:
    state = _state((_settler(1, 0, Hex(0, 0)),))
    actions = execute_goal(
        state, civ_id=0, goal=FoundCityNear(unit_id=1, target=Hex(0, 0), name="Rome")
    )
    # Already at target — just founds.
    assert len(actions) == 1
    assert isinstance(actions[0], FoundCityAction)


@pytest.mark.unit
def test_found_city_near_moves_then_founds_when_adjacent_budget() -> None:
    state = _state((_settler(1, 0, Hex(0, 0)),))
    # Settler has 2 moves — move to (1,0) then (2,0), can't found until next turn.
    actions = execute_goal(
        state, civ_id=0, goal=FoundCityNear(unit_id=1, target=Hex(2, 0), name="Rome")
    )
    # Two moves, no found yet (not on target after move budget exhausted? actually 2 moves get us to (2,0))
    assert len(actions) == 3
    assert isinstance(actions[-1], FoundCityAction)


@pytest.mark.unit
def test_attack_unit_moves_adjacent_then_attacks() -> None:
    state = _state((_warrior(1, 0, Hex(0, 0)), _warrior(2, 1, Hex(2, 0))))
    from app.engine.models import DiplomaticStance
    state = replace(state, diplomacy={(0, 1): DiplomaticStance.WAR})
    actions = execute_goal(state, civ_id=0, goal=AttackUnit(attacker_id=1, target_id=2))
    # Move to (1,0), then attack (2,0).
    assert len(actions) >= 2
    last = actions[-1]
    from app.api.actions import AttackAction
    assert isinstance(last, AttackAction)
