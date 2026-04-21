"""Tests for the OpenAI intent goal source (mocked — no real API calls)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.engine.diplomacy import MessageKind
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
    DiplomaticStance,
    GameState,
    Unit,
    UnitType,
    UNIT_STATS,
)
from app.engine.openai_goals import (
    BASE_SYSTEM_PROMPT,
    TOOLS,
    OpenAIGoalSource,
    _parse_tool_call,
    build_system_prompt,
)


# ---------------------------------------------------------------------------
# _parse_tool_call unit tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_parse_expand_with_hint():
    intent = _parse_tool_call("expand", {"target_q": 1, "target_r": -1})
    assert isinstance(intent, Expand)
    assert intent.target == Hex(1, -1)


@pytest.mark.unit
def test_parse_expand_no_hint():
    intent = _parse_tool_call("expand", {})
    assert isinstance(intent, Expand)
    assert intent.target is None


@pytest.mark.unit
def test_parse_engage():
    intent = _parse_tool_call("engage", {"target_civ_id": 2})
    assert isinstance(intent, Engage)
    assert intent.target_civ_id == 2


@pytest.mark.unit
def test_parse_scout_with_hint():
    intent = _parse_tool_call("scout", {"target_q": 0, "target_r": 3})
    assert isinstance(intent, Scout)
    assert intent.target == Hex(0, 3)


@pytest.mark.unit
def test_parse_reinforce_with_city_id():
    intent = _parse_tool_call("reinforce", {"target_city_id": 5})
    assert isinstance(intent, Reinforce)
    assert intent.target_city_id == 5


@pytest.mark.unit
def test_parse_speak():
    intent = _parse_tool_call(
        "speak", {"to_civ_id": 1, "kind": "threat", "text": "Bow before me."}
    )
    assert isinstance(intent, Speak)
    assert intent.to_civ_id == 1
    assert intent.kind is MessageKind.THREAT


@pytest.mark.unit
def test_parse_adjust_stance():
    intent = _parse_tool_call(
        "adjust_stance", {"target_civ_id": 2, "stance": "war"}
    )
    assert isinstance(intent, AdjustStance)
    assert intent.target_civ_id == 2
    assert intent.stance is DiplomaticStance.WAR


@pytest.mark.unit
def test_parse_invalid_message_kind_returns_none():
    assert _parse_tool_call(
        "speak", {"to_civ_id": 1, "kind": "grovel", "text": "please"}
    ) is None


@pytest.mark.unit
def test_parse_unknown_tool():
    assert _parse_tool_call("unknown_tool", {}) is None


# ---------------------------------------------------------------------------
# Tool schema validation
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_tool_definitions_have_required_fields():
    for tool in TOOLS:
        assert tool["type"] == "function"
        func = tool["function"]
        assert "name" in func
        assert "description" in func
        assert "parameters" in func
        params = func["parameters"]
        assert params["type"] == "object"
        assert "required" in params


@pytest.mark.unit
def test_intent_tools_present():
    names = {t["function"]["name"] for t in TOOLS}
    expected = {"expand", "scout", "engage", "reinforce", "speak", "adjust_stance"}
    assert expected.issubset(names)


@pytest.mark.unit
def test_no_tactical_tools_exposed():
    """LLM must not see tactical tools — those leaked unit-id confusion."""
    names = {t["function"]["name"] for t in TOOLS}
    forbidden = {"move_to", "found_city_near", "attack_unit", "send_message", "set_stance"}
    assert names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Persona prompt
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_build_system_prompt_no_persona():
    prompt = build_system_prompt(None)
    assert BASE_SYSTEM_PROMPT in prompt
    assert "Hard gameplay priorities" in prompt

    prompt_empty = build_system_prompt("")
    assert BASE_SYSTEM_PROMPT in prompt_empty


@pytest.mark.unit
def test_build_system_prompt_appends_persona():
    prompt = build_system_prompt("You are Genghis. Vindictive. Never forget insults.")
    assert BASE_SYSTEM_PROMPT in prompt
    assert "Genghis" in prompt
    assert "PERSONA" in prompt


# ---------------------------------------------------------------------------
# OpenAIGoalSource with mocked client + state
# ---------------------------------------------------------------------------

def _mock_response(*tool_calls_data: tuple[str, dict]) -> SimpleNamespace:
    tool_calls = []
    for i, (name, args) in enumerate(tool_calls_data):
        tc = SimpleNamespace(
            id=f"call_{i}",
            type="function",
            function=SimpleNamespace(name=name, arguments=json.dumps(args)),
        )
        tool_calls.append(tc)
    message = SimpleNamespace(
        role="assistant",
        content=None,
        tool_calls=tool_calls if tool_calls else None,
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])


def _make_source(persona: str | None = None) -> OpenAIGoalSource:
    src = OpenAIGoalSource.__new__(OpenAIGoalSource)
    src._model = "gpt-4o-mini"  # falls outside reasoning-model prefix → temperature applied
    src._temperature = 0.7
    src._client = MagicMock()
    src._system_prompt = build_system_prompt(persona)
    src._memory_turns = 8
    src._intent_log = []
    src._message_log = []
    src._last_seen_message_turn = -1
    src._state = None
    return src


def _bound_state(units: tuple[Unit, ...] = ()) -> GameState:
    civs = (
        Civilization(id=0, name="A", leader_name="LeaderA", is_human=False),
        Civilization(id=1, name="B", leader_name="LeaderB", is_human=False),
        Civilization(id=2, name="C", leader_name="LeaderC", is_human=False),
        Civilization(id=3, name="D", leader_name="LeaderD", is_human=False),
    )
    return GameState(
        turn=1,
        map=generate_map(4, seed=0),
        civs=civs,
        cities=(),
        units=units,
    )


def _settler(uid: int, owner: int, loc: Hex) -> Unit:
    stats = UNIT_STATS[UnitType.SETTLER]
    return Unit(
        id=uid, owner=owner, type=UnitType.SETTLER,
        location=loc, health=stats.max_health, moves_remaining=stats.moves,
    )


@pytest.mark.unit
def test_openai_source_resolves_expand_intent_to_goal():
    source = _make_source()
    source.bind_state(_bound_state(units=(_settler(1, 0, Hex(0, 0)),)))
    source._client.chat.completions.create.return_value = _mock_response(
        ("expand", {}),
        ("speak", {"to_civ_id": 1, "kind": "chat", "text": "hi neighbor"}),
    )

    decisions = source.decide({"turn": 1}, civ_id=0)

    # Expand → FoundCityNear goal; speak → SendMessage diplomacy.
    assert any(isinstance(g, FoundCityNear) for g in decisions.goals)
    assert len(decisions.diplomacy) == 1

    call_kwargs = source._client.chat.completions.create.call_args
    assert call_kwargs.kwargs["tools"] == TOOLS


@pytest.mark.unit
def test_openai_source_engage_auto_declares_war():
    """Verify the architectural fix: LLM emits engage(), war is declared automatically."""
    from app.engine.diplomacy import SendMessage

    me = Unit(
        id=1, owner=0, type=UnitType.WARRIOR, location=Hex(0, 0),
        health=20, moves_remaining=2,
    )
    enemy = Unit(
        id=2, owner=1, type=UnitType.WARRIOR, location=Hex(1, 0),
        health=20, moves_remaining=2,
    )
    source = _make_source()
    source.bind_state(_bound_state(units=(me, enemy)))
    source._client.chat.completions.create.return_value = _mock_response(
        ("engage", {"target_civ_id": 1}),
    )

    decisions = source.decide({"turn": 1}, civ_id=0)
    assert any(
        isinstance(d, SendMessage) and d.kind is MessageKind.DECLARE_WAR
        for d in decisions.diplomacy
    )
    assert any(isinstance(g, AttackUnit) for g in decisions.goals)


@pytest.mark.unit
def test_openai_source_persona_in_system_message():
    source = _make_source(persona="You are Cleopatra, cunning and charismatic.")
    source.bind_state(_bound_state())
    source._client.chat.completions.create.return_value = _mock_response()
    source.decide({}, civ_id=0)
    call_kwargs = source._client.chat.completions.create.call_args
    system_msg = call_kwargs.kwargs["messages"][0]
    assert system_msg["role"] == "system"
    assert "Cleopatra" in system_msg["content"]


@pytest.mark.unit
def test_openai_source_handles_no_tool_calls():
    source = _make_source()
    source.bind_state(_bound_state())
    source._client.chat.completions.create.return_value = _mock_response()
    decisions = source.decide({}, civ_id=0)
    assert decisions.goals == ()
    assert decisions.diplomacy == ()


@pytest.mark.unit
def test_openai_source_handles_api_error():
    source = _make_source()
    source.bind_state(_bound_state())
    source._client.chat.completions.create.side_effect = RuntimeError("API down")
    decisions = source.decide({}, civ_id=0)
    assert decisions.goals == ()
    assert decisions.diplomacy == ()


@pytest.mark.unit
def test_openai_source_skips_bad_json():
    source = _make_source()
    source.bind_state(_bound_state(units=(_settler(1, 0, Hex(0, 0)),)))
    good_tc = SimpleNamespace(
        id="call_0", type="function",
        function=SimpleNamespace(name="expand", arguments=json.dumps({})),
    )
    bad_tc = SimpleNamespace(
        id="call_1", type="function",
        function=SimpleNamespace(name="engage", arguments="{broken json"),
    )
    message = SimpleNamespace(role="assistant", content=None, tool_calls=[good_tc, bad_tc])
    source._client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason="stop")]
    )

    decisions = source.decide({}, civ_id=0)
    # Good intent yields a FoundCityNear; bad json is dropped without crashing.
    assert any(isinstance(g, FoundCityNear) for g in decisions.goals)


@pytest.mark.unit
def test_openai_source_injects_your_civ_id():
    source = _make_source()
    source.bind_state(_bound_state())
    source._client.chat.completions.create.return_value = _mock_response()
    source.decide({"turn": 1}, civ_id=3)
    call_kwargs = source._client.chat.completions.create.call_args
    user_msg = call_kwargs.kwargs["messages"][1]
    assert user_msg["role"] == "user"
    payload = json.loads(user_msg["content"])
    assert payload["your_civ_id"] == 3


@pytest.mark.unit
def test_openai_source_remembers_recent_intents_across_turns():
    source = _make_source()
    source.bind_state(_bound_state(units=(_settler(1, 0, Hex(0, 0)),)))
    source._client.chat.completions.create.return_value = _mock_response(
        ("expand", {"target_q": 0, "target_r": 0}),
    )
    source.decide({"turn": 1}, civ_id=0)

    source._client.chat.completions.create.return_value = _mock_response()
    source.decide({"turn": 2}, civ_id=0)

    last_call = source._client.chat.completions.create.call_args
    payload = json.loads(last_call.kwargs["messages"][1]["content"])
    assert payload["recent_actions"], "expected memory of the prior Expand intent"
    assert payload["recent_actions"][0]["type"] == "Expand"


@pytest.mark.unit
def test_openai_source_remembers_inbox_messages():
    source = _make_source()
    source.bind_state(_bound_state())
    source._client.chat.completions.create.return_value = _mock_response()
    inbox_msg = {"turn": 1, "from_civ_id": 1, "to_civ_id": 0,
                 "kind": "threat", "text": "bow"}
    source.decide({"turn": 1, "inbox": [inbox_msg]}, civ_id=0)

    source._client.chat.completions.create.return_value = _mock_response()
    source.decide({"turn": 2, "inbox": []}, civ_id=0)

    last_call = source._client.chat.completions.create.call_args
    payload = json.loads(last_call.kwargs["messages"][1]["content"])
    assert payload["recent_messages"], "expected to remember the prior inbox message"
    assert payload["recent_messages"][0]["text"] == "bow"


@pytest.mark.unit
def test_openai_source_memory_drops_old_turns():
    source = _make_source()
    source._memory_turns = 2
    source.bind_state(_bound_state(units=(_settler(1, 0, Hex(0, 0)),)))
    source._client.chat.completions.create.return_value = _mock_response(
        ("expand", {}),
    )
    source.decide({"turn": 1}, civ_id=0)

    source._client.chat.completions.create.return_value = _mock_response()
    source.decide({"turn": 10}, civ_id=0)

    last_call = source._client.chat.completions.create.call_args
    payload = json.loads(last_call.kwargs["messages"][1]["content"])
    assert payload["recent_actions"] == [], "old intent should have aged out"


@pytest.mark.unit
def test_openai_source_unbound_state_returns_empty_decisions():
    """Defensive: if the loop forgets to bind state, we return empty rather than crash."""
    source = _make_source()
    # Note: NOT calling bind_state.
    source._client.chat.completions.create.return_value = _mock_response(
        ("expand", {}),
    )
    decisions = source.decide({"turn": 1}, civ_id=0)
    assert decisions.goals == ()
    assert decisions.diplomacy == ()


@pytest.mark.unit
def test_openai_source_requires_api_key():
    import os
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            OpenAIGoalSource()
