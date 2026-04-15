"""Action validator — thin layer over engine ops for tool-using agents.

All validation paths return a ValidationResult union instead of raising. The
engine modules remain the canonical source of rule enforcement; this layer
exists so LLM tool-calls receive machine-readable rejection reasons.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from app.engine.hex import Hex, hex_distance
from app.engine.models import (
    DiplomaticStance,
    GameState,
    Unit,
    UnitType,
)
from app.engine.terrain import Terrain, is_passable


@dataclass(frozen=True, slots=True)
class MoveAction:
    unit_id: int
    destination: Hex


@dataclass(frozen=True, slots=True)
class FoundCityAction:
    unit_id: int
    name: str


@dataclass(frozen=True, slots=True)
class BuildAction:
    city_id: int
    unit_type: UnitType


@dataclass(frozen=True, slots=True)
class ResearchAction:
    tech_id: str


@dataclass(frozen=True, slots=True)
class AttackAction:
    attacker_id: int
    target_id: int


@dataclass(frozen=True, slots=True)
class EndTurnAction:
    pass


Action = Union[
    MoveAction,
    FoundCityAction,
    BuildAction,
    ResearchAction,
    AttackAction,
    EndTurnAction,
]


@dataclass(frozen=True, slots=True)
class ValidationOk:
    action: Action


@dataclass(frozen=True, slots=True)
class ValidationError:
    reason: str
    code: str


ValidationResult = Union[ValidationOk, ValidationError]


def _unit(state: GameState, unit_id: int) -> Unit | None:
    for u in state.units:
        if u.id == unit_id:
            return u
    return None


def _check_turn(state: GameState, civ_id: int) -> ValidationError | None:
    if state.current_civ_idx >= len(state.civs):
        return ValidationError("invalid current civ index", "turn_error")
    if state.civs[state.current_civ_idx].id != civ_id:
        return ValidationError(
            f"not civ {civ_id}'s turn (current: {state.current_civ().id})",
            "not_your_turn",
        )
    return None


def _validate_move(state: GameState, civ_id: int, action: MoveAction) -> ValidationResult:
    unit = _unit(state, action.unit_id)
    if unit is None:
        return ValidationError(f"unknown unit id {action.unit_id}", "unknown_unit")
    if unit.owner != civ_id:
        return ValidationError(
            f"unit {action.unit_id} is not owned by civ {civ_id}", "not_owner"
        )
    if unit.moves_remaining <= 0:
        return ValidationError(
            f"unit {action.unit_id} has no moves remaining", "no_moves"
        )
    if action.destination not in state.map:
        return ValidationError(
            f"destination {action.destination} is off map", "off_map"
        )
    if hex_distance(unit.location, action.destination) != 1:
        return ValidationError(
            f"destination {action.destination} is not adjacent to {unit.location}",
            "not_adjacent",
        )
    tile = state.map.get(action.destination)
    assert tile is not None
    if not is_passable(tile.terrain):
        return ValidationError(
            f"terrain {tile.terrain.value} is impassable", "impassable"
        )
    for other in state.units:
        if other.id != action.unit_id and other.location == action.destination:
            return ValidationError(
                f"destination {action.destination} is occupied", "occupied"
            )
    return ValidationOk(action)


def _validate_found_city(
    state: GameState, civ_id: int, action: FoundCityAction
) -> ValidationResult:
    unit = _unit(state, action.unit_id)
    if unit is None:
        return ValidationError(f"unknown unit id {action.unit_id}", "unknown_unit")
    if unit.owner != civ_id:
        return ValidationError(
            f"unit {action.unit_id} is not owned by civ {civ_id}", "not_owner"
        )
    if unit.type is not UnitType.SETTLER:
        return ValidationError(
            f"unit {action.unit_id} is not a settler", "wrong_unit_type"
        )
    tile = state.map.get(unit.location)
    if tile is None:
        return ValidationError("settler location is off map", "off_map")
    if tile.terrain in {Terrain.OCEAN, Terrain.MOUNTAIN, Terrain.SNOW}:
        return ValidationError(
            f"cannot found city on {tile.terrain.value}", "unfoundable_terrain"
        )
    for city in state.cities:
        if city.location == unit.location:
            return ValidationError(
                f"a city already exists at {unit.location}", "city_exists"
            )
    if not action.name.strip():
        return ValidationError("city name cannot be empty", "empty_name")
    return ValidationOk(action)


def _validate_build(
    state: GameState, civ_id: int, action: BuildAction
) -> ValidationResult:
    for city in state.cities:
        if city.id == action.city_id:
            if city.owner != civ_id:
                return ValidationError(
                    f"city {action.city_id} is not owned by civ {civ_id}", "not_owner"
                )
            return ValidationOk(action)
    return ValidationError(f"unknown city id {action.city_id}", "unknown_city")


def _validate_research(
    state: GameState, civ_id: int, action: ResearchAction
) -> ValidationResult:
    civ = next((c for c in state.civs if c.id == civ_id), None)
    if civ is None:
        return ValidationError(f"unknown civ {civ_id}", "unknown_civ")
    if action.tech_id in civ.known_techs:
        return ValidationError(
            f"tech {action.tech_id} already researched", "already_researched"
        )
    if not action.tech_id:
        return ValidationError("tech_id cannot be empty", "empty_tech")
    return ValidationOk(action)


def _validate_attack(
    state: GameState, civ_id: int, action: AttackAction
) -> ValidationResult:
    attacker = _unit(state, action.attacker_id)
    target = _unit(state, action.target_id)
    if attacker is None:
        return ValidationError(
            f"unknown attacker id {action.attacker_id}", "unknown_unit"
        )
    if target is None:
        return ValidationError(
            f"unknown target id {action.target_id}", "unknown_unit"
        )
    if attacker.owner != civ_id:
        return ValidationError(
            f"attacker {action.attacker_id} not owned by civ {civ_id}", "not_owner"
        )
    if target.owner == civ_id:
        return ValidationError("cannot attack own unit", "friendly_fire")
    if attacker.moves_remaining <= 0:
        return ValidationError(
            f"attacker {action.attacker_id} has no moves remaining", "no_moves"
        )
    if hex_distance(attacker.location, target.location) != 1:
        return ValidationError("target is not adjacent", "not_adjacent")
    if state.stance_between(attacker.owner, target.owner) is not DiplomaticStance.WAR:
        return ValidationError(
            f"civs {attacker.owner} and {target.owner} are not at war", "not_at_war"
        )
    return ValidationOk(action)


def _validate_end_turn(
    state: GameState, civ_id: int, action: EndTurnAction
) -> ValidationResult:
    return ValidationOk(action)


def validate(action: Action, state: GameState, civ_id: int) -> ValidationResult:
    turn_err = _check_turn(state, civ_id)
    if turn_err is not None:
        return turn_err

    if isinstance(action, MoveAction):
        return _validate_move(state, civ_id, action)
    if isinstance(action, FoundCityAction):
        return _validate_found_city(state, civ_id, action)
    if isinstance(action, BuildAction):
        return _validate_build(state, civ_id, action)
    if isinstance(action, ResearchAction):
        return _validate_research(state, civ_id, action)
    if isinstance(action, AttackAction):
        return _validate_attack(state, civ_id, action)
    if isinstance(action, EndTurnAction):
        return _validate_end_turn(state, civ_id, action)
    return ValidationError(f"unknown action type {type(action).__name__}", "unknown_action")
