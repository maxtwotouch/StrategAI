"""Tests for the action validator layer."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.api.actions import (
    AttackAction,
    EndTurnAction,
    FoundCityAction,
    MoveAction,
    ValidationError,
    ValidationOk,
    validate,
)
from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import (
    Civilization,
    GameState,
    Unit,
    UnitType,
    UNIT_STATS,
)
from app.engine.terrain import Terrain


def _state_with_units(*units: Unit) -> GameState:
    game_map = generate_map(5, seed=1)
    # Force origin land.
    from app.engine.models import Tile

    tiles = dict(game_map.tiles)
    tiles[Hex(0, 0)] = Tile(coord=Hex(0, 0), terrain=Terrain.GRASSLAND)
    tiles[Hex(1, 0)] = Tile(coord=Hex(1, 0), terrain=Terrain.GRASSLAND)
    tiles[Hex(1, -1)] = Tile(coord=Hex(1, -1), terrain=Terrain.GRASSLAND)
    game_map = replace(game_map, tiles=tiles)

    civs = (
        Civilization(id=0, name="A", leader_name="x", is_human=False),
        Civilization(id=1, name="B", leader_name="y", is_human=False),
    )
    return GameState(
        turn=1,
        map=game_map,
        civs=civs,
        cities=(),
        units=tuple(units),
        current_civ_idx=0,
    )


def _settler(uid: int, owner: int, loc: Hex) -> Unit:
    stats = UNIT_STATS[UnitType.SETTLER]
    return Unit(
        id=uid,
        owner=owner,
        type=UnitType.SETTLER,
        location=loc,
        health=stats.max_health,
        moves_remaining=stats.moves,
    )


def _warrior(uid: int, owner: int, loc: Hex) -> Unit:
    stats = UNIT_STATS[UnitType.WARRIOR]
    return Unit(
        id=uid,
        owner=owner,
        type=UnitType.WARRIOR,
        location=loc,
        health=stats.max_health,
        moves_remaining=stats.moves,
    )


@pytest.mark.unit
def test_valid_move_returns_ok() -> None:
    state = _state_with_units(_settler(1, 0, Hex(0, 0)))
    result = validate(MoveAction(unit_id=1, destination=Hex(1, 0)), state, civ_id=0)
    assert isinstance(result, ValidationOk)


@pytest.mark.unit
def test_move_wrong_owner_rejected() -> None:
    state = _state_with_units(_settler(1, 0, Hex(0, 0)))
    state = replace(state, current_civ_idx=1)
    result = validate(MoveAction(unit_id=1, destination=Hex(1, 0)), state, civ_id=1)
    assert isinstance(result, ValidationError)
    assert result.code == "not_owner"


@pytest.mark.unit
def test_move_unknown_unit_rejected() -> None:
    state = _state_with_units(_settler(1, 0, Hex(0, 0)))
    result = validate(MoveAction(unit_id=99, destination=Hex(1, 0)), state, civ_id=0)
    assert isinstance(result, ValidationError)


@pytest.mark.unit
def test_move_non_adjacent_rejected() -> None:
    state = _state_with_units(_settler(1, 0, Hex(0, 0)))
    result = validate(MoveAction(unit_id=1, destination=Hex(3, 0)), state, civ_id=0)
    assert isinstance(result, ValidationError)


@pytest.mark.unit
def test_move_not_current_civ_rejected() -> None:
    state = _state_with_units(_settler(1, 1, Hex(0, 0)))
    result = validate(MoveAction(unit_id=1, destination=Hex(1, 0)), state, civ_id=1)
    assert isinstance(result, ValidationError)
    assert "turn" in result.reason.lower()


@pytest.mark.unit
def test_found_city_ok() -> None:
    state = _state_with_units(_settler(1, 0, Hex(0, 0)))
    result = validate(FoundCityAction(unit_id=1, name="Rome"), state, civ_id=0)
    assert isinstance(result, ValidationOk)


@pytest.mark.unit
def test_found_city_non_settler_rejected() -> None:
    state = _state_with_units(_warrior(1, 0, Hex(0, 0)))
    result = validate(FoundCityAction(unit_id=1, name="Rome"), state, civ_id=0)
    assert isinstance(result, ValidationError)


@pytest.mark.unit
def test_attack_non_adjacent_rejected() -> None:
    state = _state_with_units(
        _warrior(1, 0, Hex(0, 0)),
        _warrior(2, 1, Hex(3, 0)),
    )
    result = validate(AttackAction(attacker_id=1, target_id=2), state, civ_id=0)
    assert isinstance(result, ValidationError)


@pytest.mark.unit
def test_attack_at_peace_rejected() -> None:
    state = _state_with_units(
        _warrior(1, 0, Hex(0, 0)),
        _warrior(2, 1, Hex(1, 0)),
    )
    result = validate(AttackAction(attacker_id=1, target_id=2), state, civ_id=0)
    assert isinstance(result, ValidationError)
    assert "peace" in result.reason.lower() or "war" in result.reason.lower()


@pytest.mark.unit
def test_end_turn_always_valid_for_current_civ() -> None:
    state = _state_with_units(_settler(1, 0, Hex(0, 0)))
    result = validate(EndTurnAction(), state, civ_id=0)
    assert isinstance(result, ValidationOk)


@pytest.mark.unit
def test_end_turn_wrong_civ_rejected() -> None:
    state = _state_with_units(_settler(1, 0, Hex(0, 0)))
    result = validate(EndTurnAction(), state, civ_id=1)
    assert isinstance(result, ValidationError)
