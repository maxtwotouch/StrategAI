from dataclasses import replace

import pytest

from app.engine.city_founding import FoundError, found_city
from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import (
    Civilization,
    GameMap,
    GameState,
    Tile,
    Unit,
    UnitType,
    UNIT_STATS,
)
from app.engine.terrain import Terrain


def _make_state(unit_type: UnitType = UnitType.SETTLER, loc: Hex = Hex(0, 0)) -> GameState:
    game_map = generate_map(3, seed=0)
    # Force the founding tile to grassland so tests don't depend on rng.
    tiles = dict(game_map.tiles)
    tiles[loc] = Tile(coord=loc, terrain=Terrain.GRASSLAND)
    game_map = GameMap(radius=game_map.radius, tiles=tiles)
    stats = UNIT_STATS[unit_type]
    unit = Unit(
        id=1,
        owner=0,
        type=unit_type,
        location=loc,
        health=stats.max_health,
        moves_remaining=stats.moves,
    )
    civ = Civilization(id=0, name="Alpha", leader_name="A", is_human=True)
    return GameState(turn=1, map=game_map, civs=(civ,), cities=(), units=(unit,))


def test_found_city_creates_city_and_consumes_settler():
    state = _make_state()
    new_state = found_city(state, unit_id=1, name="Athens")

    assert len(new_state.cities) == 1
    city = new_state.cities[0]
    assert city.name == "Athens"
    assert city.owner == 0
    assert city.location == Hex(0, 0)
    assert city.population == 1
    # Settler consumed
    assert len(new_state.units) == 0
    # Original state untouched
    assert len(state.cities) == 0
    assert len(state.units) == 1


def test_found_city_assigns_incremental_ids():
    state = _make_state()
    state = found_city(state, unit_id=1, name="Athens")
    # add a second settler at a different tile
    stats = UNIT_STATS[UnitType.SETTLER]
    second = Unit(
        id=2,
        owner=0,
        type=UnitType.SETTLER,
        location=Hex(1, 0),
        health=stats.max_health,
        moves_remaining=stats.moves,
    )
    tiles = dict(state.map.tiles)
    tiles[Hex(1, 0)] = Tile(coord=Hex(1, 0), terrain=Terrain.GRASSLAND)
    state = replace(
        state,
        map=GameMap(radius=state.map.radius, tiles=tiles),
        units=(second,),
    )
    state = found_city(state, unit_id=2, name="Sparta")
    assert [c.id for c in state.cities] == [1, 2]


def test_found_city_non_settler_raises():
    state = _make_state(unit_type=UnitType.WARRIOR)
    with pytest.raises(FoundError, match="settler"):
        found_city(state, unit_id=1, name="Athens")


def test_found_city_on_ocean_raises():
    state = _make_state()
    # Replace center with ocean
    tiles = dict(state.map.tiles)
    tiles[Hex(0, 0)] = Tile(coord=Hex(0, 0), terrain=Terrain.OCEAN)
    state = replace(state, map=GameMap(radius=state.map.radius, tiles=tiles))
    with pytest.raises(FoundError, match="cannot found"):
        found_city(state, unit_id=1, name="Athens")


def test_found_city_on_existing_city_tile_raises():
    state = _make_state()
    state = found_city(state, unit_id=1, name="Athens")
    # Add new settler on same tile
    stats = UNIT_STATS[UnitType.SETTLER]
    settler = Unit(
        id=2,
        owner=0,
        type=UnitType.SETTLER,
        location=Hex(0, 0),
        health=stats.max_health,
        moves_remaining=stats.moves,
    )
    state = replace(state, units=(settler,))
    with pytest.raises(FoundError, match="already"):
        found_city(state, unit_id=2, name="Athens2")


def test_found_city_unknown_unit_raises():
    state = _make_state()
    with pytest.raises(FoundError, match="unknown unit"):
        found_city(state, unit_id=999, name="Ghost")
