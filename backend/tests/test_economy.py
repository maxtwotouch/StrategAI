"""Item 2 — gold income, upkeep, and bankruptcy."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.engine.borders import recompute_claims
from app.engine.economy import (
    city_gold_income,
    civ_gold_income,
    civ_gold_upkeep,
    tick_economy,
)
from app.engine.hex import Hex
from app.engine.models import (
    BuildingType,
    City,
    Civilization,
    GameMap,
    GameState,
    Tile,
    UNIT_STATS,
    Unit,
    UnitType,
)
from app.engine.terrain import Resource, Terrain
from app.engine.turn_resolver import end_turn


def _flat_map(radius: int = 3, terrain: Terrain = Terrain.GRASSLAND) -> GameMap:
    tiles: dict[Hex, Tile] = {}
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            coord = Hex(q, r)
            tiles[coord] = Tile(coord=coord, terrain=terrain)
    return GameMap(radius=radius, tiles=tiles)


def _civs(gold: int = 20) -> tuple[Civilization, ...]:
    return (
        Civilization(id=0, name="A", leader_name="L", is_human=False, gold=gold),
        Civilization(id=1, name="B", leader_name="M", is_human=False, gold=gold),
    )


def _unit(uid: int, owner: int, loc: Hex, utype: UnitType = UnitType.WARRIOR) -> Unit:
    stats = UNIT_STATS[utype]
    return Unit(
        id=uid, owner=owner, type=utype, location=loc,
        health=stats.max_health, moves_remaining=stats.moves,
    )


def _state(*, cities=(), units=(), gold: int = 20) -> GameState:
    state = GameState(
        turn=1,
        map=_flat_map(),
        civs=_civs(gold=gold),
        cities=tuple(cities),
        units=tuple(units),
    )
    return recompute_claims(state)


def _set_tile(state: GameState, coord: Hex, **kwargs) -> GameState:
    tiles = dict(state.map.tiles)
    tiles[coord] = replace(tiles[coord], **kwargs)
    return replace(state, map=GameMap(radius=state.map.radius, tiles=tiles))


# ---------------------------------------------------------------------------
# Income
# ---------------------------------------------------------------------------

def test_river_tile_generates_gold_for_worked_city():
    city = City(id=1, owner=0, name="X", location=Hex(0, 0),
                worked_tiles=frozenset({Hex(0, 0)}))
    state = _state(cities=(city,))
    state = _set_tile(state, Hex(0, 0), river=True)
    # Grassland yields 0 gold, river adds 1.
    assert city_gold_income(state, state.cities[0]) == 1


def test_resource_gold_lands_in_income():
    city = City(id=1, owner=0, name="X", location=Hex(0, 0), population=2,
                worked_tiles=frozenset({Hex(0, 0), Hex(1, 0)}))
    state = _state(cities=(city,))
    state = _set_tile(state, Hex(1, 0), resource=Resource.GEMS, terrain=Terrain.HILLS)
    # Gems on hills: +3 gold.
    assert city_gold_income(state, state.cities[0]) == 3


def test_market_increases_city_income():
    base = City(id=1, owner=0, name="X", location=Hex(0, 0),
                worked_tiles=frozenset({Hex(0, 0)}))
    with_market = replace(base, buildings=frozenset({BuildingType.MARKET}))
    state = _state(cities=(base,))
    state = _set_tile(state, Hex(0, 0), river=True)
    state_market = replace(state, cities=(with_market,))
    assert city_gold_income(state_market, state_market.cities[0]) == (
        city_gold_income(state, state.cities[0]) + 2
    )


def test_multi_city_income_sums():
    a = City(id=1, owner=0, name="A", location=Hex(0, 0),
             worked_tiles=frozenset({Hex(0, 0)}))
    b = City(id=2, owner=0, name="B", location=Hex(2, 0),
             worked_tiles=frozenset({Hex(2, 0)}))
    state = _state(cities=(a, b))
    state = _set_tile(state, Hex(0, 0), river=True)
    state = _set_tile(state, Hex(2, 0), river=True)
    assert civ_gold_income(state, 0) == 2


# ---------------------------------------------------------------------------
# Upkeep
# ---------------------------------------------------------------------------

def test_upkeep_sums_per_unit_type():
    units = (
        _unit(1, 0, Hex(0, 0), UnitType.WARRIOR),    # 1
        _unit(2, 0, Hex(1, 0), UnitType.HORSEMAN),   # 2
        _unit(3, 0, Hex(2, 0), UnitType.SETTLER),    # 1
        _unit(4, 1, Hex(3, 0), UnitType.SCOUT),      # 1 — different owner, excluded
    )
    state = _state(units=units)
    assert civ_gold_upkeep(state, 0) == 4
    assert civ_gold_upkeep(state, 1) == 1


# ---------------------------------------------------------------------------
# tick_economy
# ---------------------------------------------------------------------------

def test_tick_economy_applies_net_delta():
    city = City(id=1, owner=0, name="X", location=Hex(0, 0),
                worked_tiles=frozenset({Hex(0, 0)}))
    warrior = _unit(7, 0, Hex(1, 0), UnitType.WARRIOR)
    state = _state(cities=(city,), units=(warrior,), gold=20)
    state = _set_tile(state, Hex(0, 0), river=True)
    new_state = tick_economy(state)
    # income 1, upkeep 1, delta 0 → gold unchanged.
    assert new_state.civs[0].gold == 20


def test_bankruptcy_disbands_oldest_non_settler():
    settler = _unit(1, 0, Hex(0, 0), UnitType.SETTLER)
    warrior_old = _unit(2, 0, Hex(1, 0), UnitType.WARRIOR)
    warrior_new = _unit(3, 0, Hex(2, 0), UnitType.WARRIOR)
    state = _state(units=(settler, warrior_old, warrior_new), gold=0)
    # No cities → no income. Upkeep = 3. gold goes -3 → bankrupt → drop oldest
    # non-settler = warrior_old (id=2). Gold clamped to 0.
    new_state = tick_economy(state)
    ids = [u.id for u in new_state.units]
    assert 1 in ids
    assert 2 not in ids
    assert 3 in ids
    assert new_state.civs[0].gold == 0


def test_bankruptcy_with_only_settler_keeps_settler():
    settler = _unit(1, 0, Hex(0, 0), UnitType.SETTLER)
    state = _state(units=(settler,), gold=0)
    new_state = tick_economy(state)
    assert any(u.type is UnitType.SETTLER for u in new_state.units)
    assert new_state.civs[0].gold == 0


def test_end_turn_runs_tick_economy():
    city = City(id=1, owner=0, name="X", location=Hex(0, 0),
                worked_tiles=frozenset({Hex(0, 0)}))
    state = _state(cities=(city,), gold=10)
    state = _set_tile(state, Hex(0, 0), river=True)
    new_state = end_turn(state)
    # +1 gold from river income, 0 upkeep.
    assert new_state.civs[0].gold == 11
