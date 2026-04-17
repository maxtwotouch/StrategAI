"""Tests for the OpenAI goal source (mocked — no real API calls)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.engine.diplomacy import MessageKind, SendMessage, SetStance
from app.engine.executor import AttackUnit, FoundCityNear, MoveTo
from app.engine.hex import Hex
from app.engine.models import DiplomaticStance
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
def test_parse_move_to():
    goal = _parse_tool_call("move_to", {"unit_id": 1, "target_q": 3, "target_r": -1})
    assert isinstance(goal, MoveTo)
    assert goal.unit_id == 1
    assert goal.target == Hex(3, -1)


@pytest.mark.unit
def test_parse_found_city_near():
    goal = _parse_tool_call(
        "found_city_near",
        {"unit_id": 2, "target_q": 0, "target_r": 0, "name": "MyCity"},
    )
    assert isinstance(goal, FoundCityNear)
    assert goal.name == "MyCity"


@pytest.mark.unit
def test_parse_attack_unit():
    goal = _parse_tool_call("attack_unit", {"attacker_id": 5, "target_id": 8})
    assert isinstance(goal, AttackUnit)
    assert goal.attacker_id == 5
    assert goal.target_id == 8


@pytest.mark.unit
def test_parse_send_message():
    action = _parse_tool_call(
        "send_message",
        {"to_civ_id": 1, "kind": "threat", "text": "Bow before me."},
    )
    assert isinstance(action, SendMessage)
    assert action.to_civ_id == 1
    assert action.kind is MessageKind.THREAT


@pytest.mark.unit
def test_parse_set_stance():
    action = _parse_tool_call(
        "set_stance",
        {"target_civ_id": 2, "stance": "war"},
    )
    assert isinstance(action, SetStance)
    assert action.target_civ_id == 2
    assert action.stance is DiplomaticStance.WAR


@pytest.mark.unit
def test_parse_invalid_message_kind_returns_none():
    assert _parse_tool_call(
        "send_message",
        {"to_civ_id": 1, "kind": "grovel", "text": "please"},
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
        assert len(params["required"]) > 0


@pytest.mark.unit
def test_diplomacy_tools_present():
    names = {t["function"]["name"] for t in TOOLS}
    assert "send_message" in names
    assert "set_stance" in names


# ---------------------------------------------------------------------------
# Persona prompt
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_build_system_prompt_no_persona():
    assert build_system_prompt(None) == BASE_SYSTEM_PROMPT
    assert build_system_prompt("") == BASE_SYSTEM_PROMPT


@pytest.mark.unit
def test_build_system_prompt_appends_persona():
    prompt = build_system_prompt("You are Genghis. Vindictive. Never forget insults.")
    assert BASE_SYSTEM_PROMPT in prompt
    assert "Genghis" in prompt
    assert "PERSONA" in prompt


# ---------------------------------------------------------------------------
# OpenAIGoalSource with mocked client
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
    src._model = "gpt-4o-mini"
    src._temperature = 0.7
    src._client = MagicMock()
    src._system_prompt = build_system_prompt(persona)
    return src


@pytest.mark.unit
def test_openai_source_splits_goals_and_diplomacy():
    source = _make_source()
    source._client.chat.completions.create.return_value = _mock_response(
        ("move_to", {"unit_id": 1, "target_q": 2, "target_r": -1}),
        ("send_message", {"to_civ_id": 1, "kind": "chat", "text": "hi neighbor"}),
        ("found_city_near", {"unit_id": 3, "target_q": 0, "target_r": 0, "name": "Rome"}),
        ("set_stance", {"target_civ_id": 2, "stance": "war"}),
    )

    decisions = source.decide({"turn": 1}, civ_id=0)

    assert len(decisions.goals) == 2
    assert isinstance(decisions.goals[0], MoveTo)
    assert isinstance(decisions.goals[1], FoundCityNear)
    assert len(decisions.diplomacy) == 2
    assert isinstance(decisions.diplomacy[0], SendMessage)
    assert isinstance(decisions.diplomacy[1], SetStance)

    # Verify the API was called with all 5 tools.
    call_kwargs = source._client.chat.completions.create.call_args
    assert call_kwargs.kwargs["tools"] == TOOLS


@pytest.mark.unit
def test_openai_source_persona_in_system_message():
    source = _make_source(persona="You are Cleopatra, cunning and charismatic.")
    source._client.chat.completions.create.return_value = _mock_response()
    source.decide({}, civ_id=0)
    call_kwargs = source._client.chat.completions.create.call_args
    system_msg = call_kwargs.kwargs["messages"][0]
    assert system_msg["role"] == "system"
    assert "Cleopatra" in system_msg["content"]


@pytest.mark.unit
def test_openai_source_handles_no_tool_calls():
    source = _make_source()
    source._client.chat.completions.create.return_value = _mock_response()
    decisions = source.decide({}, civ_id=0)
    assert decisions.goals == ()
    assert decisions.diplomacy == ()


@pytest.mark.unit
def test_openai_source_handles_api_error():
    source = _make_source()
    source._client.chat.completions.create.side_effect = RuntimeError("API down")
    decisions = source.decide({}, civ_id=0)
    assert decisions.goals == ()
    assert decisions.diplomacy == ()


@pytest.mark.unit
def test_openai_source_skips_bad_json():
    source = _make_source()
    good_tc = SimpleNamespace(
        id="call_0", type="function",
        function=SimpleNamespace(
            name="move_to",
            arguments=json.dumps({"unit_id": 1, "target_q": 0, "target_r": 0}),
        ),
    )
    bad_tc = SimpleNamespace(
        id="call_1", type="function",
        function=SimpleNamespace(name="attack_unit", arguments="{broken json"),
    )
    message = SimpleNamespace(role="assistant", content=None, tool_calls=[good_tc, bad_tc])
    source._client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason="stop")]
    )

    decisions = source.decide({}, civ_id=0)
    assert len(decisions.goals) == 1
    assert isinstance(decisions.goals[0], MoveTo)


@pytest.mark.unit
def test_openai_source_requires_api_key():
    import os
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            OpenAIGoalSource()
