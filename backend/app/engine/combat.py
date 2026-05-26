"""Deterministic melee combat. Pure — returns new GameState."""

from __future__ import annotations

from dataclasses import replace

from app.engine.diplomacy import (
    DiplomaticEventKind,
    REL_ATTACK,
    adjust_relationship,
    record_event,
)
from app.engine.hex import hex_distance
from app.engine.models import City, DiplomaticStance, GameState, Unit
from app.engine.terrain import Feature, Terrain

# Stacking multipliers cap to avoid runaway defense on heavy terrain.
MAX_TERRAIN_DEFENSE_MULT = 1.6
TERRAIN_DEFENSE_STEP = 1.25


class CombatError(ValueError):
    """Raised when an attack is invalid."""


def _find(state: GameState, unit_id: int) -> Unit:
    for u in state.units:
        if u.id == unit_id:
            return u
    raise CombatError(f"unknown unit id {unit_id}")


def _ensure_war(state: GameState, attacker_owner: int, defender_owner: int) -> None:
    if state.stance_between(attacker_owner, defender_owner) is not DiplomaticStance.WAR:
        raise CombatError(
            f"civs {attacker_owner} and {defender_owner} are not at war"
        )


def _terrain_defense_multiplier(state: GameState, defender: Unit) -> float:
    """Stacking-but-capped defensive bonus from the defender's tile."""
    tile = state.map.get(defender.location)
    if tile is None:
        return 1.0
    mult = 1.0
    if tile.terrain is Terrain.HILLS:
        mult *= TERRAIN_DEFENSE_STEP
    if tile.terrain is Terrain.FOREST or tile.feature in (
        Feature.FOREST,
        Feature.JUNGLE,
        Feature.MARSH,
    ):
        mult *= TERRAIN_DEFENSE_STEP
    if tile.river:
        mult *= TERRAIN_DEFENSE_STEP
    return min(MAX_TERRAIN_DEFENSE_MULT, mult)


def _effective_defense(state: GameState, defender: Unit) -> int:
    raw = defender.stats.defense * _terrain_defense_multiplier(state, defender)
    return int(round(raw))


def _damage_to_defender(state: GameState, attacker: Unit, defender: Unit) -> int:
    return max(1, 2 * attacker.stats.attack - _effective_defense(state, defender))


def _damage_to_attacker(state: GameState, attacker: Unit, defender: Unit) -> int:
    return max(0, defender.stats.attack - attacker.stats.defense)


def _find_city(state: GameState, city_id: int) -> City:
    for city in state.cities:
        if city.id == city_id:
            return city
    raise CombatError(f"unknown city id {city_id}")


def _city_defense(city: City) -> int:
    return 2 + city.population + len(city.buildings)


def attack_city(state: GameState, attacker_id: int, city_id: int) -> GameState:
    attacker = _find(state, attacker_id)
    city = _find_city(state, city_id)

    if attacker.owner == city.owner:
        raise CombatError("cannot attack own city")
    _ensure_war(state, attacker.owner, city.owner)
    if attacker.moves_remaining <= 0:
        raise CombatError(f"attacker {attacker_id} has no moves")
    if hex_distance(attacker.location, city.location) != 1:
        raise CombatError("target city not adjacent")

    dmg_city = max(1, 2 * attacker.stats.attack - _city_defense(city))
    dmg_attacker = max(0, _city_defense(city) - attacker.stats.defense)
    new_city_health = max(0, city.health - dmg_city)
    new_attacker_health = attacker.health - dmg_attacker

    new_units: list[Unit] = []
    for unit in state.units:
        if unit.id == attacker_id:
            if new_attacker_health > 0:
                new_units.append(
                    replace(
                        unit,
                        health=new_attacker_health,
                        moves_remaining=0,
                        acted_this_turn=True,
                    )
                )
        else:
            new_units.append(unit)

    new_cities = tuple(
        replace(c, health=new_city_health) if c.id == city_id else c
        for c in state.cities
    )
    new_state = replace(state, units=tuple(new_units), cities=new_cities)
    new_state = adjust_relationship(
        new_state, attacker.owner, city.owner, REL_ATTACK
    )
    new_state = record_event(
        new_state,
        DiplomaticEventKind.ATTACK,
        attacker.owner,
        city.owner,
        f"civ {attacker.owner} attacked city of civ {city.owner}",
        REL_ATTACK,
    )
    return new_state


def attack(state: GameState, attacker_id: int, defender_id: int) -> GameState:
    attacker = _find(state, attacker_id)
    defender = _find(state, defender_id)

    if attacker.owner == defender.owner:
        raise CombatError("cannot attack own unit")
    _ensure_war(state, attacker.owner, defender.owner)
    if attacker.moves_remaining <= 0:
        raise CombatError(f"attacker {attacker_id} has no moves")
    if hex_distance(attacker.location, defender.location) != 1:
        raise CombatError("target not adjacent")

    dmg_def = _damage_to_defender(state, attacker, defender)
    dmg_atk = _damage_to_attacker(state, attacker, defender)

    new_def_health = defender.health - dmg_def
    new_atk_health = attacker.health - dmg_atk

    def _rebuild(units: tuple[Unit, ...]) -> tuple[Unit, ...]:
        result: list[Unit] = []
        for u in units:
            if u.id == defender_id:
                if new_def_health > 0:
                    result.append(
                        replace(u, health=new_def_health, acted_this_turn=True)
                    )
                # else: killed, drop
            elif u.id == attacker_id:
                if new_atk_health > 0:
                    # Attacker used up all remaining moves.
                    updated = replace(
                        u,
                        health=new_atk_health,
                        moves_remaining=0,
                        acted_this_turn=True,
                    )
                    # Advance into the defender's tile if defender died.
                    if new_def_health <= 0:
                        updated = updated.with_location(defender.location)
                    result.append(updated)
                # else: attacker killed, drop
            else:
                result.append(u)
        return tuple(result)

    new_state = replace(state, units=_rebuild(state.units))
    # Combat is a relationship hit even if defender survives.
    new_state = adjust_relationship(
        new_state, attacker.owner, defender.owner, REL_ATTACK
    )
    new_state = record_event(
        new_state,
        DiplomaticEventKind.ATTACK,
        attacker.owner,
        defender.owner,
        f"civ {attacker.owner} attacked unit of civ {defender.owner}",
        REL_ATTACK,
    )
    return new_state
