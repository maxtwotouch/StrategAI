"""Relationship scoring, diplomatic events, and truces."""

from __future__ import annotations

import pytest

from app.engine.combat import attack
from app.engine.diplomacy import (
    DiplomaticEventKind,
    DiplomaticMessage,
    MessageKind,
    REL_ATTACK,
    REL_DECLARE_WAR,
    REL_OFFER_PEACE,
    REL_ACCEPT_PEACE,
    REL_THREAT,
    SendMessage,
    SetStance,
    TRUCE_DURATION_TURNS,
    DiplomacyError,
    adjust_relationship,
    apply_diplomatic_action,
    relationship_between,
    truce_active,
)
from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import (
    Civilization,
    DiplomaticStance,
    GameState,
    UNIT_STATS,
    Unit,
    UnitType,
)


def _civs(known: set[int] | None = None) -> tuple[Civilization, ...]:
    return (
        Civilization(id=0, name="A", leader_name="L", is_human=False),
        Civilization(id=1, name="B", leader_name="M", is_human=False),
    )


def _state(turn: int = 1, *, units=(), diplomacy=None, relationships=None, truces=None, met: bool = True) -> GameState:
    # Seed a stub historical message so `met_civs` treats 0 and 1 as having met
    # (matches the engine's encounter requirement for diplomatic actions).
    messages: tuple[DiplomaticMessage, ...] = ()
    if met:
        messages = (
            DiplomaticMessage(
                from_civ_id=0, to_civ_id=1, turn=0,
                kind=MessageKind.CHAT, text="(seed)",
            ),
        )
    return GameState(
        turn=turn,
        map=generate_map(3, seed=0),
        civs=_civs(),
        cities=(),
        units=tuple(units),
        diplomacy=diplomacy or {},
        relationships=relationships or {},
        truces=truces or {},
        messages=messages,
    )


def _warrior(uid: int, owner: int, loc: Hex) -> Unit:
    stats = UNIT_STATS[UnitType.WARRIOR]
    return Unit(
        id=uid, owner=owner, type=UnitType.WARRIOR, location=loc,
        health=stats.max_health, moves_remaining=stats.moves,
    )


# ---------------------------------------------------------------------------
# adjust_relationship
# ---------------------------------------------------------------------------

def test_relationship_defaults_to_zero():
    state = _state()
    assert relationship_between(state, 0, 1) == 0


def test_adjust_relationship_is_bounded():
    state = _state()
    state = adjust_relationship(state, 0, 1, -150)
    assert relationship_between(state, 0, 1) == -100
    state = adjust_relationship(state, 0, 1, 500)
    assert relationship_between(state, 0, 1) == 100


def test_adjust_relationship_is_symmetric_via_key():
    state = _state()
    state = adjust_relationship(state, 0, 1, -10)
    # Same pair, different order → same score.
    assert relationship_between(state, 1, 0) == -10


# ---------------------------------------------------------------------------
# Diplomatic messages adjust relationship + log events
# ---------------------------------------------------------------------------

def test_declare_war_drops_relationship_and_logs_event():
    state = _state()
    state = apply_diplomatic_action(
        state, 0,
        SendMessage(to_civ_id=1, kind=MessageKind.DECLARE_WAR, text="war"),
    )
    assert state.stance_between(0, 1) is DiplomaticStance.WAR
    assert relationship_between(state, 0, 1) == REL_DECLARE_WAR
    kinds = [e.kind for e in state.diplomatic_events]
    assert DiplomaticEventKind.WAR_DECLARED in kinds


def test_threat_drops_relationship():
    state = _state()
    state = apply_diplomatic_action(
        state, 0, SendMessage(to_civ_id=1, kind=MessageKind.THREAT, text="bow"),
    )
    assert relationship_between(state, 0, 1) == REL_THREAT


def test_attack_drops_relationship_and_logs_event():
    a = _warrior(1, 0, Hex(0, 0))
    d = _warrior(2, 1, Hex(1, 0))
    state = _state(units=(a, d))
    new_state = attack(state, a.id, d.id)
    assert relationship_between(new_state, 0, 1) == REL_ATTACK
    kinds = [e.kind for e in new_state.diplomatic_events]
    assert DiplomaticEventKind.ATTACK in kinds


# ---------------------------------------------------------------------------
# Truces
# ---------------------------------------------------------------------------

def test_accept_peace_ends_war_and_creates_truce():
    state = _state(diplomacy={(0, 1): DiplomaticStance.WAR})
    state = apply_diplomatic_action(
        state, 1,
        SendMessage(to_civ_id=0, kind=MessageKind.ACCEPT_PEACE, text="peace"),
    )
    assert state.stance_between(0, 1) is DiplomaticStance.PEACE
    assert truce_active(state, 0, 1) is True


def test_truce_blocks_declare_war():
    state = _state(turn=5, truces={(0, 1): 12})
    with pytest.raises(DiplomacyError, match="truce"):
        apply_diplomatic_action(
            state, 0,
            SendMessage(to_civ_id=1, kind=MessageKind.DECLARE_WAR, text="war"),
        )


def test_truce_blocks_setstance_war():
    state = _state(turn=5, truces={(0, 1): 12})
    with pytest.raises(DiplomacyError, match="truce"):
        apply_diplomatic_action(
            state, 0, SetStance(target_civ_id=1, stance=DiplomaticStance.WAR),
        )


def test_expired_truce_allows_war_again():
    state = _state(turn=20, truces={(0, 1): 10})
    state = apply_diplomatic_action(
        state, 0,
        SendMessage(to_civ_id=1, kind=MessageKind.DECLARE_WAR, text="war"),
    )
    assert state.stance_between(0, 1) is DiplomaticStance.WAR


def test_accept_peace_truce_duration_is_constant():
    state = _state(turn=5, diplomacy={(0, 1): DiplomaticStance.WAR})
    state = apply_diplomatic_action(
        state, 1,
        SendMessage(to_civ_id=0, kind=MessageKind.ACCEPT_PEACE, text="peace"),
    )
    assert state.truces[(0, 1)] == 5 + TRUCE_DURATION_TURNS
