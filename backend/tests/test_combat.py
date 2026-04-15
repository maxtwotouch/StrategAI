from dataclasses import replace

import pytest

from app.engine.combat import CombatError, attack
from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import (
    Civilization,
    GameState,
    Unit,
    UnitType,
    UNIT_STATS,
)


def _unit(uid: int, owner: int, utype: UnitType, loc: Hex, health: int | None = None) -> Unit:
    stats = UNIT_STATS[utype]
    return Unit(
        id=uid,
        owner=owner,
        type=utype,
        location=loc,
        health=health if health is not None else stats.max_health,
        moves_remaining=stats.moves,
    )


def _state(units: tuple[Unit, ...]) -> GameState:
    civs = (
        Civilization(id=0, name="A", leader_name="L", is_human=True),
        Civilization(id=1, name="B", leader_name="M", is_human=False),
    )
    return GameState(
        turn=1,
        map=generate_map(3, seed=0),
        civs=civs,
        cities=(),
        units=units,
    )


def test_attack_applies_damage_both_sides():
    a = _unit(1, 0, UnitType.WARRIOR, Hex(0, 0))
    d = _unit(2, 1, UnitType.WARRIOR, Hex(1, 0))
    state = _state((a, d))
    new_state = attack(state, attacker_id=1, defender_id=2)
    attacker = next(u for u in new_state.units if u.id == 1)
    defender = next(u for u in new_state.units if u.id == 2)
    # 2*4 - 3 = 5 to defender, 4 - 3 = 1 to attacker
    assert defender.health == UNIT_STATS[UnitType.WARRIOR].max_health - 5
    assert attacker.health == UNIT_STATS[UnitType.WARRIOR].max_health - 1
    assert attacker.moves_remaining == 0


def test_attack_kills_defender_and_advances_attacker():
    d = _unit(2, 1, UnitType.WARRIOR, Hex(1, 0), health=1)
    a = _unit(1, 0, UnitType.WARRIOR, Hex(0, 0))
    state = _state((a, d))
    new_state = attack(state, 1, 2)
    assert len(new_state.units) == 1
    survivor = new_state.units[0]
    assert survivor.id == 1
    assert survivor.location == Hex(1, 0)


def test_attack_kills_both_when_attacker_also_dies():
    # Weak attacker at 1hp vs strong defender
    a = _unit(1, 0, UnitType.SCOUT, Hex(0, 0), health=1)
    d = _unit(2, 1, UnitType.WARRIOR, Hex(1, 0))
    state = _state((a, d))
    new_state = attack(state, 1, 2)
    # scout attack=1 → dmg_def = max(1, 2-3)=1 → def 19
    # warrior attack=4, scout def=1 → dmg_atk = 3 → atk -2 dead
    assert not any(u.id == 1 for u in new_state.units)
    defender = next(u for u in new_state.units if u.id == 2)
    assert defender.health == UNIT_STATS[UnitType.WARRIOR].max_health - 1


def test_attack_own_unit_raises():
    a = _unit(1, 0, UnitType.WARRIOR, Hex(0, 0))
    b = _unit(2, 0, UnitType.WARRIOR, Hex(1, 0))
    state = _state((a, b))
    with pytest.raises(CombatError, match="own unit"):
        attack(state, 1, 2)


def test_attack_non_adjacent_raises():
    a = _unit(1, 0, UnitType.WARRIOR, Hex(0, 0))
    d = _unit(2, 1, UnitType.WARRIOR, Hex(2, 0))
    state = _state((a, d))
    with pytest.raises(CombatError, match="adjacent"):
        attack(state, 1, 2)


def test_attack_with_no_moves_raises():
    a = _unit(1, 0, UnitType.WARRIOR, Hex(0, 0)).with_moves(0)
    d = _unit(2, 1, UnitType.WARRIOR, Hex(1, 0))
    state = _state((a, d))
    with pytest.raises(CombatError, match="no moves"):
        attack(state, 1, 2)


def test_attack_unknown_unit_raises():
    a = _unit(1, 0, UnitType.WARRIOR, Hex(0, 0))
    state = _state((a,))
    with pytest.raises(CombatError, match="unknown unit"):
        attack(state, 1, 999)
