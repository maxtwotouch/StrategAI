"""Flat per-turn gold income."""

from __future__ import annotations

from app.engine.economy import (
    GOLD_PER_TURN,
    city_gold_income,
    civ_gold_income,
    civ_gold_upkeep,
    tick_economy,
)
from app.engine.hex import Hex
from app.engine.models import Civilization, GameMap, GameState, Tile, UNIT_STATS, Unit, UnitType
from app.engine.terrain import Terrain
from app.engine.turn_resolver import end_turn


def _flat_map(radius: int = 3, terrain: Terrain = Terrain.GRASSLAND) -> GameMap:
    tiles: dict[Hex, Tile] = {}
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            coord = Hex(q, r)
            tiles[coord] = Tile(coord=coord, terrain=terrain)
    return GameMap(radius=radius, tiles=tiles)


def _unit(uid: int, owner: int, loc: Hex, utype: UnitType = UnitType.WARRIOR) -> Unit:
    stats = UNIT_STATS[utype]
    return Unit(
        id=uid,
        owner=owner,
        type=utype,
        location=loc,
        health=stats.max_health,
        moves_remaining=stats.moves,
    )


def _state(*, units=(), gold: int = 20) -> GameState:
    return GameState(
        turn=1,
        map=_flat_map(),
        civs=(
            Civilization(id=0, name="A", leader_name="L", is_human=False, gold=gold),
            Civilization(id=1, name="B", leader_name="M", is_human=False, gold=gold),
        ),
        cities=(),
        units=tuple(units),
    )


def test_city_gold_income_is_not_modeled():
    state = _state()
    assert city_gold_income(state, 1) == 0


def test_civ_gold_income_is_flat():
    state = _state()
    assert civ_gold_income(state, 0) == GOLD_PER_TURN
    assert civ_gold_income(state, 1) == GOLD_PER_TURN


def test_civ_gold_upkeep_is_removed():
    state = _state(
        units=(
            _unit(1, 0, Hex(0, 0), UnitType.WARRIOR),
            _unit(2, 0, Hex(1, 0), UnitType.HORSEMAN),
            _unit(3, 1, Hex(2, 0), UnitType.SCOUT),
        ),
    )
    assert civ_gold_upkeep(state, 0) == 0
    assert civ_gold_upkeep(state, 1) == 0


def test_tick_economy_adds_flat_gold_and_never_disbands():
    units = (
        _unit(1, 0, Hex(0, 0), UnitType.SETTLER),
        _unit(2, 0, Hex(1, 0), UnitType.WARRIOR),
        _unit(3, 0, Hex(2, 0), UnitType.SCOUT),
    )
    state = _state(units=units, gold=0)
    new_state = tick_economy(state)

    assert new_state.civs[0].gold == GOLD_PER_TURN
    assert new_state.units == units


def test_end_turn_runs_flat_gold_income():
    state = _state(gold=10)
    new_state = end_turn(state)
    assert new_state.civs[0].gold == 10 + GOLD_PER_TURN
