"""Item 5 — workers, tile improvements, and the Improve intent path."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.api.actions import (
    BuildImprovementAction,
    ValidationError,
    ValidationOk,
    validate,
)
from app.engine.borders import recompute_claims
from app.engine.executor import BuildImprovementGoal, execute_goal
from app.engine.hex import Hex
from app.engine.improvements import (
    ImprovementError,
    can_improve,
    start_improvement,
    tick_improvements,
)
from app.engine.intents import Improve
from app.engine.models import (
    City,
    Civilization,
    GameMap,
    GameState,
    Tile,
    UNIT_STATS,
    Unit,
    UnitType,
)
from app.engine.movement import move_unit
from app.engine.operations import resolve_intent
from app.engine.terrain import (
    IMPROVEMENT_TURNS,
    Improvement,
    Terrain,
    tile_yields,
)
from app.engine.turn_resolver import end_turn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _map(radius: int = 3) -> GameMap:
    tiles: dict[Hex, Tile] = {}
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            tiles[Hex(q, r)] = Tile(coord=Hex(q, r), terrain=Terrain.GRASSLAND)
    return GameMap(radius=radius, tiles=tiles)


def _worker(uid: int, owner: int, loc: Hex) -> Unit:
    stats = UNIT_STATS[UnitType.WORKER]
    return Unit(
        id=uid, owner=owner, type=UnitType.WORKER, location=loc,
        health=stats.max_health, moves_remaining=stats.moves,
    )


def _warrior(uid: int, owner: int, loc: Hex) -> Unit:
    stats = UNIT_STATS[UnitType.WARRIOR]
    return Unit(
        id=uid, owner=owner, type=UnitType.WARRIOR, location=loc,
        health=stats.max_health, moves_remaining=stats.moves,
    )


def _state(*, cities=(), units=(), gold: int = 50) -> GameState:
    civs = (
        Civilization(id=0, name="A", leader_name="L", is_human=False, gold=gold),
        Civilization(id=1, name="B", leader_name="M", is_human=False, gold=gold),
    )
    state = GameState(
        turn=1, map=_map(), civs=civs,
        cities=tuple(cities), units=tuple(units),
    )
    return recompute_claims(state)


def _set_tile(state: GameState, coord: Hex, **kwargs) -> GameState:
    tiles = dict(state.map.tiles)
    tiles[coord] = replace(tiles[coord], **kwargs)
    return replace(state, map=GameMap(radius=state.map.radius, tiles=tiles))


# ---------------------------------------------------------------------------
# Yield extension
# ---------------------------------------------------------------------------

def test_farm_adds_food_to_yields():
    tile = Tile(coord=Hex(0, 0), terrain=Terrain.PLAINS, improvement=Improvement.FARM)
    base = Tile(coord=Hex(0, 0), terrain=Terrain.PLAINS)
    assert tile_yields(tile).food == tile_yields(base).food + 1


def test_mine_adds_production_to_yields():
    tile = Tile(coord=Hex(0, 0), terrain=Terrain.HILLS, improvement=Improvement.MINE)
    base = Tile(coord=Hex(0, 0), terrain=Terrain.HILLS)
    assert tile_yields(tile).production == tile_yields(base).production + 1


# ---------------------------------------------------------------------------
# can_improve
# ---------------------------------------------------------------------------

def test_can_improve_rejects_already_improved():
    state = _state(cities=(City(id=1, owner=0, name="A", location=Hex(0, 0)),))
    state = _set_tile(state, Hex(0, 0), improvement=Improvement.FARM)
    tile = state.map.get(Hex(0, 0))
    assert can_improve(state, tile, Improvement.FARM, 0) == "tile_already_improved"


def test_can_improve_rejects_bad_terrain():
    state = _state(cities=(City(id=1, owner=0, name="A", location=Hex(0, 0)),))
    state = _set_tile(state, Hex(0, 0), terrain=Terrain.HILLS)
    tile = state.map.get(Hex(0, 0))
    # Farm on hills is illegal.
    assert can_improve(state, tile, Improvement.FARM, 0) == "bad_terrain_for_improvement"


def test_can_improve_rejects_unowned_tile():
    # No city anywhere → no tile_owner entries → not in own borders.
    state = _state()
    tile = state.map.get(Hex(0, 0))
    assert can_improve(state, tile, Improvement.FARM, 0) == "not_in_own_borders"


# ---------------------------------------------------------------------------
# start_improvement
# ---------------------------------------------------------------------------

def test_worker_starts_farm_on_plains():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0))
    worker = _worker(7, 0, Hex(1, 0))
    state = _state(cities=(city,), units=(worker,))
    state = _set_tile(state, Hex(1, 0), terrain=Terrain.PLAINS)
    new_state = start_improvement(state, worker.id, Improvement.FARM)
    new_worker = new_state.units[0]
    assert new_worker.work_order == (Hex(1, 0), Improvement.FARM)
    assert new_worker.work_turns_remaining == IMPROVEMENT_TURNS[Improvement.FARM]
    assert new_worker.moves_remaining == 0
    assert new_worker.acted_this_turn is True


def test_warrior_cannot_start_improvement():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0))
    warrior = _warrior(7, 0, Hex(1, 0))
    state = _state(cities=(city,), units=(warrior,))
    state = _set_tile(state, Hex(1, 0), terrain=Terrain.PLAINS)
    with pytest.raises(ImprovementError, match="not_worker"):
        start_improvement(state, warrior.id, Improvement.FARM)


def test_busy_worker_cannot_start_another():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0))
    worker = _worker(7, 0, Hex(1, 0))
    state = _state(cities=(city,), units=(worker,))
    state = _set_tile(state, Hex(1, 0), terrain=Terrain.PLAINS)
    state = start_improvement(state, worker.id, Improvement.FARM)
    with pytest.raises(ImprovementError, match="worker_already_busy"):
        start_improvement(state, worker.id, Improvement.FARM)


def test_worker_cannot_farm_hills():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0))
    worker = _worker(7, 0, Hex(1, 0))
    state = _state(cities=(city,), units=(worker,))
    state = _set_tile(state, Hex(1, 0), terrain=Terrain.HILLS)
    with pytest.raises(ImprovementError, match="bad_terrain_for_improvement"):
        start_improvement(state, worker.id, Improvement.FARM)


def test_worker_cannot_improve_unowned_tile():
    worker = _worker(7, 0, Hex(0, 0))
    state = _state(units=(worker,))
    with pytest.raises(ImprovementError, match="not_in_own_borders"):
        start_improvement(state, worker.id, Improvement.FARM)


# ---------------------------------------------------------------------------
# tick_improvements
# ---------------------------------------------------------------------------

def test_worker_completes_farm_after_n_turns():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0))
    worker = _worker(7, 0, Hex(1, 0))
    state = _state(cities=(city,), units=(worker,))
    state = _set_tile(state, Hex(1, 0), terrain=Terrain.PLAINS)
    state = start_improvement(state, worker.id, Improvement.FARM)
    for _ in range(IMPROVEMENT_TURNS[Improvement.FARM]):
        state = tick_improvements(state)
    assert state.map.get(Hex(1, 0)).improvement is Improvement.FARM
    assert state.units[0].work_order is None
    assert state.units[0].work_turns_remaining == 0


def test_worker_moving_cancels_work_order():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0), border_radius=2)
    worker = _worker(7, 0, Hex(1, 0))
    state = _state(cities=(city,), units=(worker,))
    state = recompute_claims(state)
    state = _set_tile(state, Hex(1, 0), terrain=Terrain.PLAINS)
    state = start_improvement(state, worker.id, Improvement.FARM)
    # Refresh moves so the worker can step away.
    moved_worker = replace(state.units[0], moves_remaining=2)
    state = replace(state, units=(moved_worker,))
    state = move_unit(state, worker.id, Hex(2, 0))
    assert state.units[0].work_order is None


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def test_validator_rejects_non_worker():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0))
    warrior = _warrior(7, 0, Hex(1, 0))
    state = _state(cities=(city,), units=(warrior,))
    state = _set_tile(state, Hex(1, 0), terrain=Terrain.PLAINS)
    result = validate(
        BuildImprovementAction(unit_id=7, improvement=Improvement.FARM),
        state, civ_id=0,
    )
    assert isinstance(result, ValidationError)
    assert result.code == "not_worker"


def test_validator_accepts_valid_request():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0))
    worker = _worker(7, 0, Hex(1, 0))
    state = _state(cities=(city,), units=(worker,))
    state = _set_tile(state, Hex(1, 0), terrain=Terrain.PLAINS)
    result = validate(
        BuildImprovementAction(unit_id=7, improvement=Improvement.FARM),
        state, civ_id=0,
    )
    assert isinstance(result, ValidationOk)


# ---------------------------------------------------------------------------
# Operations layer (Improve intent → goal)
# ---------------------------------------------------------------------------

def test_improve_intent_picks_idle_worker_and_target():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0))
    worker = _worker(7, 0, Hex(0, 0))
    state = _state(cities=(city,), units=(worker,))
    state = _set_tile(state, Hex(0, 0), terrain=Terrain.PLAINS)
    goals, dipl, dirs = resolve_intent(state, 0, Improve(kind=Improvement.FARM))
    assert len(goals) == 1
    assert isinstance(goals[0], BuildImprovementGoal)
    assert goals[0].improvement is Improvement.FARM


def test_improve_intent_drops_when_no_worker():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0))
    state = _state(cities=(city,))
    goals, _, _ = resolve_intent(state, 0, Improve(kind=Improvement.FARM))
    assert goals == []


def test_improve_intent_drops_when_no_legal_tile():
    # Worker exists, city exists, but every nearby tile is HILLS — farm illegal.
    city = City(id=1, owner=0, name="A", location=Hex(0, 0))
    worker = _worker(7, 0, Hex(0, 0))
    state = _state(cities=(city,), units=(worker,))
    # Force every owned tile to hills.
    for coord in list(state.tile_owner.keys()):
        state = _set_tile(state, coord, terrain=Terrain.HILLS)
    goals, _, _ = resolve_intent(state, 0, Improve(kind=Improvement.FARM))
    assert goals == []


# ---------------------------------------------------------------------------
# Executor (BuildImprovementGoal → primitive actions)
# ---------------------------------------------------------------------------

def test_executor_emits_build_action_when_on_target():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0))
    worker = _worker(7, 0, Hex(1, 0))
    state = _state(cities=(city,), units=(worker,))
    state = _set_tile(state, Hex(1, 0), terrain=Terrain.PLAINS)
    actions = execute_goal(state, 0,
        BuildImprovementGoal(unit_id=7, target=Hex(1, 0), improvement=Improvement.FARM)
    )
    assert any(isinstance(a, BuildImprovementAction) for a in actions)


# ---------------------------------------------------------------------------
# End-to-end via end_turn
# ---------------------------------------------------------------------------

def test_end_turn_progresses_work_orders():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0))
    worker = _worker(7, 0, Hex(1, 0))
    state = _state(cities=(city,), units=(worker,))
    state = _set_tile(state, Hex(1, 0), terrain=Terrain.PLAINS)
    state = start_improvement(state, worker.id, Improvement.FARM)
    initial_turns = state.units[0].work_turns_remaining

    state = end_turn(state)
    after_one = state.units[0].work_turns_remaining
    assert after_one == initial_turns - 1
