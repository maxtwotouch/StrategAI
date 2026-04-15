from app.engine.fog_of_war import CITY_SIGHT, visible_tiles
from app.engine.hex import Hex, hex_range
from app.engine.map_generator import generate_map
from app.engine.models import (
    City,
    Civilization,
    GameState,
    Unit,
    UnitType,
    UNIT_STATS,
)


def _unit(uid: int, owner: int, loc: Hex, utype: UnitType = UnitType.WARRIOR) -> Unit:
    s = UNIT_STATS[utype]
    return Unit(
        id=uid,
        owner=owner,
        type=utype,
        location=loc,
        health=s.max_health,
        moves_remaining=s.moves,
    )


def _state(units: tuple[Unit, ...], cities: tuple[City, ...] = (), radius: int = 4) -> GameState:
    civs = (
        Civilization(id=0, name="A", leader_name="L", is_human=True),
        Civilization(id=1, name="B", leader_name="M", is_human=False),
    )
    return GameState(
        turn=1,
        map=generate_map(radius, seed=0),
        civs=civs,
        cities=cities,
        units=units,
    )


def test_visible_tiles_single_unit_matches_sight_range():
    u = _unit(1, 0, Hex(0, 0), UnitType.WARRIOR)
    state = _state((u,))
    seen = visible_tiles(state, 0)
    expected = {c for c in hex_range(Hex(0, 0), u.stats.sight) if c in state.map}
    assert seen == expected


def test_visible_tiles_ignores_enemy_units():
    friend = _unit(1, 0, Hex(0, 0))
    enemy = _unit(2, 1, Hex(3, 0))
    state = _state((friend, enemy))
    seen = visible_tiles(state, 0)
    assert Hex(0, 0) in seen
    assert Hex(3, 0) not in seen


def test_visible_tiles_includes_city_vision():
    city = City(id=1, owner=0, name="X", location=Hex(2, -1))
    state = _state((), cities=(city,))
    seen = visible_tiles(state, 0)
    for c in hex_range(Hex(2, -1), CITY_SIGHT):
        if c in state.map:
            assert c in seen


def test_visible_tiles_union_of_unit_and_city():
    u = _unit(1, 0, Hex(0, 0))
    city = City(id=1, owner=0, name="X", location=Hex(3, 0))
    state = _state((u,), cities=(city,))
    seen = visible_tiles(state, 0)
    assert Hex(0, 0) in seen
    assert Hex(3, 0) in seen


def test_visible_tiles_clips_to_map_bounds():
    u = _unit(1, 0, Hex(4, 0))  # on edge of radius 4 map
    state = _state((u,), radius=4)
    seen = visible_tiles(state, 0)
    assert all(c in state.map for c in seen)
