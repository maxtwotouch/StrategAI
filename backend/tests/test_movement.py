import pytest

from app.engine.hex import Hex
from app.engine.models import GameState, Unit, UnitType, UNIT_STATS
from app.engine.map_generator import generate_map
from app.engine.movement import MoveError, move_unit
from app.engine.terrain import Terrain


def _state_with_unit(loc: Hex = Hex(0, 0), unit_type: UnitType = UnitType.WARRIOR) -> GameState:
    game_map = generate_map(3, seed=123)
    stats = UNIT_STATS[unit_type]
    unit = Unit(
        id=1,
        owner=0,
        type=unit_type,
        location=loc,
        health=stats.max_health,
        moves_remaining=stats.moves,
    )
    return GameState(turn=1, map=game_map, civs=(), cities=(), units=(unit,))


def _force_terrain(state: GameState, coord: Hex, terrain: Terrain) -> GameState:
    from app.engine.models import GameMap, Tile
    new_tiles = dict(state.map.tiles)
    new_tiles[coord] = Tile(coord=coord, terrain=terrain)
    new_map = GameMap(radius=state.map.radius, tiles=new_tiles)
    from dataclasses import replace
    return replace(state, map=new_map)


def test_move_to_adjacent_passable_tile_succeeds():
    state = _state_with_unit(Hex(0, 0))
    state = _force_terrain(state, Hex(0, 0), Terrain.GRASSLAND)
    state = _force_terrain(state, Hex(1, 0), Terrain.PLAINS)

    new_state = move_unit(state, unit_id=1, destination=Hex(1, 0))

    moved = new_state.units[0]
    assert moved.location == Hex(1, 0)
    assert moved.moves_remaining == UNIT_STATS[UnitType.WARRIOR].moves - 1
    # original state untouched (immutability)
    assert state.units[0].location == Hex(0, 0)


def test_move_to_non_adjacent_tile_raises():
    state = _state_with_unit(Hex(0, 0))
    state = _force_terrain(state, Hex(0, 0), Terrain.GRASSLAND)
    state = _force_terrain(state, Hex(2, 0), Terrain.GRASSLAND)
    with pytest.raises(MoveError, match="not adjacent"):
        move_unit(state, unit_id=1, destination=Hex(2, 0))


def test_move_into_mountain_raises():
    state = _state_with_unit(Hex(0, 0))
    state = _force_terrain(state, Hex(0, 0), Terrain.GRASSLAND)
    state = _force_terrain(state, Hex(1, 0), Terrain.MOUNTAIN)
    with pytest.raises(MoveError, match="impassable"):
        move_unit(state, unit_id=1, destination=Hex(1, 0))


def test_move_off_map_raises():
    state = _state_with_unit(Hex(0, 0))
    with pytest.raises(MoveError, match="off map"):
        move_unit(state, unit_id=1, destination=Hex(99, 99))


def test_move_with_no_moves_remaining_raises():
    state = _state_with_unit(Hex(0, 0))
    state = _force_terrain(state, Hex(0, 0), Terrain.GRASSLAND)
    state = _force_terrain(state, Hex(1, 0), Terrain.GRASSLAND)
    # drain unit moves
    drained = state.units[0].with_moves(0)
    from dataclasses import replace
    state = replace(state, units=(drained,))
    with pytest.raises(MoveError, match="no moves"):
        move_unit(state, unit_id=1, destination=Hex(1, 0))


def test_move_unknown_unit_raises():
    state = _state_with_unit(Hex(0, 0))
    with pytest.raises(MoveError, match="unknown unit"):
        move_unit(state, unit_id=999, destination=Hex(1, 0))
