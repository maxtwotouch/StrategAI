from dataclasses import replace

from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.buildings import BUILDINGS
from app.engine.models import (
    BuildItem,
    BuildingType,
    City,
    Civilization,
    GameMap,
    GameState,
    Tile,
    UNIT_BUILD_COST,
    UnitType,
)
from app.engine.models import Unit, UNIT_STATS
from app.engine.production import (
    DEFAULT_SETTLER_CITY_CAP,
    SETTLER_POP_THRESHOLD,
    default_unit_for,
    process_cities,
)
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
    # Grassland: food=2. base food=2. population consumes 1. net food +3 → 3.
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
        production_queue=(BuildItem.unit(UnitType.WARRIOR),),
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
        production_queue=(BuildItem.unit(UnitType.WARRIOR),),
    )
    state = _base_state(city)
    new_state = process_cities(state)
    assert new_state.units == ()
    assert new_state.cities[0].production_queue == (BuildItem.unit(UnitType.WARRIOR),)


def test_process_cities_is_immutable():
    city = City(id=1, owner=0, name="X", location=Hex(0, 0))
    state = _base_state(city)
    process_cities(state)
    assert state.cities[0].food_stored == 0
    assert state.cities[0].production_stored == 0


def _multi_state(
    cities: tuple[City, ...] = (),
    units: tuple[Unit, ...] = (),
) -> GameState:
    game_map = generate_map(3, seed=0)
    civ = Civilization(id=0, name="A", leader_name="L", is_human=False)
    return GameState(
        turn=1,
        map=game_map,
        civs=(civ,),
        cities=cities,
        units=units,
    )


def _unit(uid: int, owner: int, utype: UnitType, loc: Hex) -> Unit:
    stats = UNIT_STATS[utype]
    return Unit(
        id=uid,
        owner=owner,
        type=utype,
        location=loc,
        health=stats.max_health,
        moves_remaining=stats.moves,
    )


def test_default_unit_for_picks_scout_when_none_exist():
    city = City(id=1, owner=0, name="X", location=Hex(0, 0))
    state = _multi_state(cities=(city,))
    assert default_unit_for(state, city) is UnitType.SCOUT


def test_default_unit_for_picks_warrior_when_below_city_count():
    city = City(id=1, owner=0, name="X", location=Hex(0, 0))
    scout = _unit(1, 0, UnitType.SCOUT, Hex(2, 0))
    state = _multi_state(cities=(city,), units=(scout,))
    # has scout, 0 warriors, 1 city → wants warrior
    assert default_unit_for(state, city) is UnitType.WARRIOR


def test_default_unit_for_queues_settler_when_pop_and_cap_allow():
    city = City(
        id=1,
        owner=0,
        name="X",
        location=Hex(0, 0),
        population=SETTLER_POP_THRESHOLD,
    )
    scout = _unit(1, 0, UnitType.SCOUT, Hex(2, 0))
    warrior = _unit(2, 0, UnitType.WARRIOR, Hex(1, 0))
    state = _multi_state(cities=(city,), units=(scout, warrior))
    assert default_unit_for(state, city) is UnitType.SETTLER


def test_default_unit_for_falls_back_to_warrior_at_city_cap():
    cities = tuple(
        City(
            id=i + 1,
            owner=0,
            name=f"C{i}",
            location=Hex(i * 2, 0),
            population=SETTLER_POP_THRESHOLD,
        )
        for i in range(DEFAULT_SETTLER_CITY_CAP)
    )
    units = (
        _unit(100, 0, UnitType.SCOUT, Hex(10, 0)),
        # one warrior per city to clear the warrior gate
        *(
            _unit(200 + i, 0, UnitType.WARRIOR, Hex(0, i + 1))
            for i in range(DEFAULT_SETTLER_CITY_CAP)
        ),
    )
    state = _multi_state(cities=cities, units=units)
    # city cap reached → don't queue settler, just more warriors
    assert default_unit_for(state, cities[0]) is UnitType.WARRIOR


def test_idle_city_auto_queues_default_unit():
    city = City(id=1, owner=0, name="X", location=Hex(0, 0))
    state = _base_state(city)
    new_state = process_cities(state)
    # No scout existed → queue should now hold a SCOUT.
    assert new_state.cities[0].production_queue == (BuildItem.unit(UnitType.SCOUT),)


def test_city_completes_building_and_applies_food_bonus_next_tick():
    cost = BUILDINGS[BuildingType.GRANARY].cost
    city = City(
        id=1,
        owner=0,
        name="X",
        location=Hex(0, 0),
        production_stored=cost - 1,
        production_queue=(BuildItem.building(BuildingType.GRANARY),),
    )
    state = _base_state(city)
    built_state = process_cities(state)
    built_city = built_state.cities[0]
    assert BuildingType.GRANARY in built_city.buildings
    assert built_city.production_queue == ()

    after_bonus = process_cities(built_state)
    assert after_bonus.cities[0].food_stored > built_city.food_stored


def test_city_with_monument_adds_culture_each_tick():
    city = City(
        id=1,
        owner=0,
        name="X",
        location=Hex(0, 0),
        buildings=frozenset({BuildingType.MONUMENT}),
    )
    state = _base_state(city)
    new_state = process_cities(state)
    # Each city contributes a baseline +1 culture; Monument adds +1 more.
    assert new_state.civs[0].culture == 2
    assert new_state.cities[0].culture_stored == 2
