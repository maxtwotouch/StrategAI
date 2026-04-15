from dataclasses import replace

from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import (
    City,
    Civilization,
    GameMap,
    GameState,
    Tile,
    UNIT_BUILD_COST,
    UnitType,
)
from app.engine.production import process_cities
from app.engine.terrain import Terrain


def _base_state(city: City, tile_terrain: Terrain = Terrain.GRASSLAND) -> GameState:
    game_map = generate_map(3, seed=0)
    tiles = dict(game_map.tiles)
    tiles[city.location] = Tile(coord=city.location, terrain=tile_terrain)
    game_map = GameMap(radius=game_map.radius, tiles=tiles)
    civ = Civilization(id=0, name="A", leader_name="L", is_human=True)
    return GameState(turn=1, map=game_map, civs=(civ,), cities=(city,), units=())


def test_city_accumulates_food_and_production():
    city = City(id=1, owner=0, name="X", location=Hex(0, 0))
    state = _base_state(city)
    new_state = process_cities(state)
    new_city = new_state.cities[0]
    # Grassland: food=2. base food=2. upkeep 1*pop(1)=1. net food +3 → 3.
    # Grassland: production=0. base production=1. net prod +1 → 1.
    assert new_city.food_stored == 3
    assert new_city.production_stored == 1


def test_city_grows_when_food_reaches_threshold():
    city = City(id=1, owner=0, name="X", location=Hex(0, 0), food_stored=9)
    state = _base_state(city)
    new_state = process_cities(state)
    new_city = new_state.cities[0]
    # food goes from 9 -> 12, threshold 10 -> pop 2, food_stored = 2
    assert new_city.population == 2
    assert new_city.food_stored == 2


def test_city_completes_unit_production_and_spawns_adjacent_or_on_tile():
    cost = UNIT_BUILD_COST[UnitType.WARRIOR]
    city = City(
        id=1,
        owner=0,
        name="X",
        location=Hex(0, 0),
        production_stored=cost - 1,
        production_queue=(UnitType.WARRIOR,),
    )
    state = _base_state(city)
    new_state = process_cities(state)
    assert len(new_state.units) == 1
    spawned = new_state.units[0]
    assert spawned.type == UnitType.WARRIOR
    assert spawned.owner == 0
    # Production carries over: had cost-1 + 1 from grassland = cost, consumed → 0
    assert new_state.cities[0].production_stored == 0
    assert new_state.cities[0].production_queue == ()


def test_city_does_not_spawn_if_production_insufficient():
    city = City(
        id=1,
        owner=0,
        name="X",
        location=Hex(0, 0),
        production_stored=0,
        production_queue=(UnitType.WARRIOR,),
    )
    state = _base_state(city)
    new_state = process_cities(state)
    assert new_state.units == ()
    assert new_state.cities[0].production_queue == (UnitType.WARRIOR,)


def test_process_cities_is_immutable():
    city = City(id=1, owner=0, name="X", location=Hex(0, 0))
    state = _base_state(city)
    process_cities(state)
    assert state.cities[0].food_stored == 0
    assert state.cities[0].production_stored == 0
