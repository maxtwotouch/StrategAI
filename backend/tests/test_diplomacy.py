"""Tests for the diplomacy module."""

from __future__ import annotations

import pytest

from app.engine.diplomacy import (
    DiplomacyError,
    DiplomaticMessage,
    MessageKind,
    SendMessage,
    SetStance,
    apply_diplomatic_action,
    conversation_between,
    inbox_for,
    set_stance,
)
from app.engine.hex import Hex
from app.engine.models import (
    Civilization,
    DiplomaticStance,
    GameMap,
    GameState,
    Tile,
)
from app.engine.terrain import Terrain


def _state(num_civs: int = 3) -> GameState:
    gm = GameMap(radius=1, tiles={Hex(0, 0): Tile(coord=Hex(0, 0), terrain=Terrain.GRASSLAND)})
    civs = tuple(
        Civilization(id=i, name=f"Civ{i}", leader_name=f"L{i}", is_human=False)
        for i in range(num_civs)
    )
    return GameState(turn=5, map=gm, civs=civs, cities=(), units=())


@pytest.mark.unit
def test_send_message_appends_to_log():
    state = _state()
    s2 = apply_diplomatic_action(
        state, 0, SendMessage(to_civ_id=1, kind=MessageKind.CHAT, text="hello")
    )
    assert len(s2.messages) == 1
    msg = s2.messages[0]
    assert msg.from_civ_id == 0 and msg.to_civ_id == 1
    assert msg.turn == 5
    assert msg.text == "hello"


@pytest.mark.unit
def test_declare_war_sets_war_stance():
    state = _state()
    s2 = apply_diplomatic_action(
        state, 0,
        SendMessage(to_civ_id=1, kind=MessageKind.DECLARE_WAR, text="prepare to die"),
    )
    assert s2.stance_between(0, 1) is DiplomaticStance.WAR


@pytest.mark.unit
def test_accept_alliance_sets_alliance_stance():
    state = _state()
    s2 = apply_diplomatic_action(
        state, 0,
        SendMessage(to_civ_id=1, kind=MessageKind.ACCEPT_ALLIANCE, text="agreed"),
    )
    assert s2.stance_between(0, 1) is DiplomaticStance.ALLIANCE


@pytest.mark.unit
def test_offer_peace_does_not_auto_end_war():
    state = _state()
    state = set_stance(state, 0, 1, DiplomaticStance.WAR)
    s2 = apply_diplomatic_action(
        state, 0,
        SendMessage(to_civ_id=1, kind=MessageKind.OFFER_PEACE, text="please stop"),
    )
    # Message logged, but stance unchanged until the other side accepts.
    assert len(s2.messages) == 1
    assert s2.stance_between(0, 1) is DiplomaticStance.WAR


@pytest.mark.unit
def test_set_stance_action():
    state = _state()
    s2 = apply_diplomatic_action(
        state, 0, SetStance(target_civ_id=2, stance=DiplomaticStance.WAR)
    )
    assert s2.stance_between(0, 2) is DiplomaticStance.WAR


@pytest.mark.unit
def test_send_to_self_rejected():
    state = _state()
    with pytest.raises(DiplomacyError):
        apply_diplomatic_action(
            state, 0, SendMessage(to_civ_id=0, kind=MessageKind.CHAT, text="me")
        )


@pytest.mark.unit
def test_send_to_unknown_civ_rejected():
    state = _state()
    with pytest.raises(DiplomacyError):
        apply_diplomatic_action(
            state, 0, SendMessage(to_civ_id=99, kind=MessageKind.CHAT, text="ghost")
        )


@pytest.mark.unit
def test_inbox_filters_recipient_and_turn():
    state = _state()
    state = apply_diplomatic_action(
        state, 0, SendMessage(to_civ_id=1, kind=MessageKind.CHAT, text="t5")
    )
    state = apply_diplomatic_action(
        state, 2, SendMessage(to_civ_id=1, kind=MessageKind.CHAT, text="from 2")
    )
    state = apply_diplomatic_action(
        state, 0, SendMessage(to_civ_id=2, kind=MessageKind.CHAT, text="not for 1")
    )
    inbox = inbox_for(state, civ_id=1)
    assert len(inbox) == 2
    assert {m.from_civ_id for m in inbox} == {0, 2}


@pytest.mark.unit
def test_inbox_since_turn_filter():
    state = _state()
    state = apply_diplomatic_action(
        state, 0, SendMessage(to_civ_id=1, kind=MessageKind.CHAT, text="early")
    )
    from dataclasses import replace
    state = replace(state, turn=10)
    state = apply_diplomatic_action(
        state, 0, SendMessage(to_civ_id=1, kind=MessageKind.CHAT, text="later")
    )
    recent = inbox_for(state, 1, since_turn=10)
    assert len(recent) == 1
    assert recent[0].text == "later"


@pytest.mark.unit
def test_conversation_between_is_chronological_and_filtered():
    state = _state()
    state = apply_diplomatic_action(
        state, 0, SendMessage(to_civ_id=1, kind=MessageKind.CHAT, text="A→B 1")
    )
    state = apply_diplomatic_action(
        state, 1, SendMessage(to_civ_id=0, kind=MessageKind.CHAT, text="B→A 1")
    )
    state = apply_diplomatic_action(
        state, 0, SendMessage(to_civ_id=2, kind=MessageKind.CHAT, text="not in convo")
    )
    convo = conversation_between(state, 0, 1)
    assert len(convo) == 2
    assert [m.text for m in convo] == ["A→B 1", "B→A 1"]


@pytest.mark.unit
def test_conversation_last_n():
    state = _state()
    for i in range(5):
        state = apply_diplomatic_action(
            state, 0, SendMessage(to_civ_id=1, kind=MessageKind.CHAT, text=f"m{i}")
        )
    convo = conversation_between(state, 0, 1, last_n=2)
    assert [m.text for m in convo] == ["m3", "m4"]


@pytest.mark.unit
def test_set_stance_self_rejected():
    state = _state()
    with pytest.raises(DiplomacyError):
        set_stance(state, 0, 0, DiplomaticStance.WAR)
