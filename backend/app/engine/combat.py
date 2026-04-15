"""Deterministic melee combat. Pure — returns new GameState."""

from __future__ import annotations

from dataclasses import replace

from app.engine.hex import hex_distance
from app.engine.models import GameState, Unit


class CombatError(ValueError):
    """Raised when an attack is invalid."""


def _find(state: GameState, unit_id: int) -> Unit:
    for u in state.units:
        if u.id == unit_id:
            return u
    raise CombatError(f"unknown unit id {unit_id}")


def _damage_to_defender(attacker: Unit, defender: Unit) -> int:
    return max(1, 2 * attacker.stats.attack - defender.stats.defense)


def _damage_to_attacker(attacker: Unit, defender: Unit) -> int:
    return max(0, defender.stats.attack - attacker.stats.defense)


def attack(state: GameState, attacker_id: int, defender_id: int) -> GameState:
    attacker = _find(state, attacker_id)
    defender = _find(state, defender_id)

    if attacker.owner == defender.owner:
        raise CombatError("cannot attack own unit")
    if attacker.moves_remaining <= 0:
        raise CombatError(f"attacker {attacker_id} has no moves")
    if hex_distance(attacker.location, defender.location) != 1:
        raise CombatError("target not adjacent")

    dmg_def = _damage_to_defender(attacker, defender)
    dmg_atk = _damage_to_attacker(attacker, defender)

    new_def_health = defender.health - dmg_def
    new_atk_health = attacker.health - dmg_atk

    def _rebuild(units: tuple[Unit, ...]) -> tuple[Unit, ...]:
        result: list[Unit] = []
        for u in units:
            if u.id == defender_id:
                if new_def_health > 0:
                    result.append(replace(u, health=new_def_health))
                # else: killed, drop
            elif u.id == attacker_id:
                if new_atk_health > 0:
                    # Attacker used up all remaining moves.
                    updated = replace(u, health=new_atk_health, moves_remaining=0)
                    # Advance into the defender's tile if defender died.
                    if new_def_health <= 0:
                        updated = updated.with_location(defender.location)
                    result.append(updated)
                # else: attacker killed, drop
            else:
                result.append(u)
        return tuple(result)

    return replace(state, units=_rebuild(state.units))
