"""Tests for the intent → goal/diplomacy operations layer."""

from __future__ import annotations

import pytest

from app.engine.diplomacy import MessageKind, SendMessage, SetStance
from app.engine.executor import AttackUnit, FoundCityNear, MoveTo
from app.engine.hex import Hex
from app.engine.intents import (
    AdjustStance,
    Engage,
    Expand,
    Reinforce,
    Scout,
    Speak,
)
from app.engine.map_generator import generate_map
from app.engine.models import (
    Civilization,
    City,
    DiplomaticStance,
    GameState,
    Unit,
    UnitType,
    UNIT_STATS,
)
from app.engine.operations import resolve_intent, resolve_intents


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


def _state(
    units: tuple[Unit, ...] = (),
    cities: tuple[City, ...] = (),
    diplomacy: dict | None = None,
) -> GameState:
    civs = (
        Civilization(id=0, name="A", leader_name="LeaderA", is_human=False),
        Civilization(id=1, name="B", leader_name="LeaderB", is_human=False),
        Civilization(id=2, name="C", leader_name="LeaderC", is_human=False),
    )
    return GameState(
        turn=1,
        map=generate_map(4, seed=0),
        civs=civs,
        cities=cities,
        units=units,
        diplomacy=diplomacy or {},
    )


# ---------------------------------------------------------------------------
# Expand
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_expand_with_settler_emits_found_city_goal():
    settler = _unit(1, 0, UnitType.SETTLER, Hex(0, 0))
    state = _state((settler,))
    goals, dipl = resolve_intent(state, civ_id=0, intent=Expand())
    assert dipl == []
    assert len(goals) == 1
    assert isinstance(goals[0], FoundCityNear)
    assert goals[0].unit_id == 1


@pytest.mark.unit
def test_expand_without_settler_emits_nothing():
    warrior = _unit(1, 0, UnitType.WARRIOR, Hex(0, 0))
    state = _state((warrior,))
    goals, dipl = resolve_intent(state, civ_id=0, intent=Expand())
    assert goals == []
    assert dipl == []


@pytest.mark.unit
def test_expand_falls_back_when_hint_blocked():
    settler = _unit(1, 0, UnitType.SETTLER, Hex(0, 0))
    blocker = _unit(2, 1, UnitType.WARRIOR, Hex(1, 0))  # blocks (1,0) hint
    state = _state((settler, blocker))
    goals, _ = resolve_intent(state, civ_id=0, intent=Expand(target=Hex(1, 0)))
    assert len(goals) == 1
    assert isinstance(goals[0], FoundCityNear)
    # Should pick a different (open) site, not the blocked hint.
    assert goals[0].target != Hex(1, 0)


# ---------------------------------------------------------------------------
# Engage
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_engage_auto_declares_war_when_at_peace():
    me = _unit(1, 0, UnitType.WARRIOR, Hex(0, 0))
    enemy = _unit(2, 1, UnitType.WARRIOR, Hex(1, 0))  # adjacent → visible
    state = _state((me, enemy))
    goals, dipl = resolve_intent(state, 0, Engage(target_civ_id=1))
    assert any(
        isinstance(d, SendMessage) and d.kind is MessageKind.DECLARE_WAR and d.to_civ_id == 1
        for d in dipl
    )
    assert any(isinstance(g, AttackUnit) and g.target_id == 2 for g in goals)


@pytest.mark.unit
def test_engage_skips_war_declaration_when_already_at_war():
    me = _unit(1, 0, UnitType.WARRIOR, Hex(0, 0))
    enemy = _unit(2, 1, UnitType.WARRIOR, Hex(1, 0))
    diplomacy = {(0, 1): DiplomaticStance.WAR}
    state = _state((me, enemy), diplomacy=diplomacy)
    goals, dipl = resolve_intent(state, 0, Engage(target_civ_id=1))
    assert dipl == []
    assert any(isinstance(g, AttackUnit) for g in goals)


@pytest.mark.unit
def test_engage_self_target_is_dropped():
    me = _unit(1, 0, UnitType.WARRIOR, Hex(0, 0))
    state = _state((me,))
    goals, dipl = resolve_intent(state, 0, Engage(target_civ_id=0))
    assert goals == []
    assert dipl == []


@pytest.mark.unit
def test_engage_unknown_civ_is_dropped():
    me = _unit(1, 0, UnitType.WARRIOR, Hex(0, 0))
    state = _state((me,))
    goals, dipl = resolve_intent(state, 0, Engage(target_civ_id=99))
    assert goals == []
    assert dipl == []


@pytest.mark.unit
def test_engage_marches_on_visible_city_when_no_units_visible():
    me = _unit(1, 0, UnitType.WARRIOR, Hex(0, 0))
    enemy_city = City(id=10, owner=1, name="Foo", location=Hex(2, 0))
    state = _state((me,), (enemy_city,))
    goals, dipl = resolve_intent(state, 0, Engage(target_civ_id=1))
    # War still auto-declared.
    assert any(isinstance(d, SendMessage) and d.kind is MessageKind.DECLARE_WAR for d in dipl)
    # Plus a march toward the city.
    assert any(isinstance(g, MoveTo) and g.target == Hex(2, 0) for g in goals)


# ---------------------------------------------------------------------------
# Speak / AdjustStance — self-target dropped
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_speak_self_target_is_dropped():
    state = _state()
    goals, dipl = resolve_intent(
        state, 0, Speak(to_civ_id=0, kind=MessageKind.CHAT, text="hi me")
    )
    assert goals == []
    assert dipl == []


@pytest.mark.unit
def test_speak_emits_send_message():
    state = _state()
    goals, dipl = resolve_intent(
        state, 0, Speak(to_civ_id=1, kind=MessageKind.THREAT, text="bow")
    )
    assert goals == []
    assert len(dipl) == 1
    assert isinstance(dipl[0], SendMessage)
    assert dipl[0].to_civ_id == 1


@pytest.mark.unit
def test_adjust_stance_self_target_is_dropped():
    state = _state()
    _, dipl = resolve_intent(
        state, 0, AdjustStance(target_civ_id=0, stance=DiplomaticStance.WAR)
    )
    assert dipl == []


@pytest.mark.unit
def test_adjust_stance_emits_set_stance():
    state = _state()
    _, dipl = resolve_intent(
        state, 0, AdjustStance(target_civ_id=2, stance=DiplomaticStance.ALLIANCE)
    )
    assert len(dipl) == 1
    assert isinstance(dipl[0], SetStance)
    assert dipl[0].target_civ_id == 2
    assert dipl[0].stance is DiplomaticStance.ALLIANCE


# ---------------------------------------------------------------------------
# Scout / Reinforce
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_scout_with_no_units_emits_nothing():
    state = _state()
    goals, _ = resolve_intent(state, 0, Scout())
    assert goals == []


@pytest.mark.unit
def test_scout_emits_move_to():
    scout = _unit(1, 0, UnitType.SCOUT, Hex(0, 0))
    state = _state((scout,))
    goals, _ = resolve_intent(state, 0, Scout(target=Hex(2, -1)))
    assert len(goals) == 1
    assert isinstance(goals[0], MoveTo)
    assert goals[0].target == Hex(2, -1)


@pytest.mark.unit
def test_reinforce_targets_own_city_by_default():
    warrior = _unit(1, 0, UnitType.WARRIOR, Hex(3, 0))
    city = City(id=5, owner=0, name="Home", location=Hex(0, 0))
    state = _state((warrior,), (city,))
    goals, _ = resolve_intent(state, 0, Reinforce())
    assert len(goals) == 1
    assert isinstance(goals[0], MoveTo)
    assert goals[0].target == Hex(0, 0)


@pytest.mark.unit
def test_reinforce_with_explicit_target():
    warrior = _unit(1, 0, UnitType.WARRIOR, Hex(0, 0))
    state = _state((warrior,))
    goals, _ = resolve_intent(state, 0, Reinforce(target=Hex(2, -1)))
    assert len(goals) == 1
    assert goals[0].target == Hex(2, -1)


# ---------------------------------------------------------------------------
# resolve_intents (batch)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_resolve_intents_concatenates_results():
    settler = _unit(1, 0, UnitType.SETTLER, Hex(0, 0))
    state = _state((settler,))
    goals, dipl = resolve_intents(
        state,
        0,
        [
            Expand(),
            Speak(to_civ_id=1, kind=MessageKind.CHAT, text="hello"),
        ],
    )
    assert len(goals) == 1
    assert len(dipl) == 1
