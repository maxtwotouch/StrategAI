"""Tests for QueueHumanSource and CLIHumanSource."""

from __future__ import annotations

import pytest

from app.engine.diplomacy import MessageKind, SendMessage, SetStance
from app.engine.executor import AttackUnit, FoundCityNear, MoveTo
from app.engine.hex import Hex
from app.engine.human_source import CLIHumanSource, QueueHumanSource
from app.engine.models import DiplomaticStance
from app.engine.playthrough import Decisions


# ---------------------------------------------------------------------------
# QueueHumanSource
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_queue_empty_returns_empty_decisions():
    src = QueueHumanSource()
    d = src.decide({}, civ_id=0)
    assert d.goals == ()
    assert d.diplomacy == ()


@pytest.mark.unit
def test_queue_drains_and_merges():
    src = QueueHumanSource()
    src.submit(0, Decisions(goals=(MoveTo(unit_id=1, target=Hex(0, 0)),)))
    src.submit(0, Decisions(diplomacy=(
        SendMessage(to_civ_id=1, kind=MessageKind.CHAT, text="hi"),
    )))
    d = src.decide({}, civ_id=0)
    assert len(d.goals) == 1
    assert len(d.diplomacy) == 1
    # Subsequent call returns empty (queue drained).
    d2 = src.decide({}, civ_id=0)
    assert d2.goals == () and d2.diplomacy == ()


@pytest.mark.unit
def test_queue_per_civ_isolation():
    src = QueueHumanSource()
    src.submit(0, Decisions(goals=(MoveTo(unit_id=1, target=Hex(0, 0)),)))
    src.submit(1, Decisions(goals=(MoveTo(unit_id=2, target=Hex(1, 1)),)))
    d0 = src.decide({}, civ_id=0)
    d1 = src.decide({}, civ_id=1)
    assert d0.goals[0].unit_id == 1
    assert d1.goals[0].unit_id == 2


# ---------------------------------------------------------------------------
# CLIHumanSource
# ---------------------------------------------------------------------------

class _ScriptedIO:
    """Stub stdin/stdout for CLIHumanSource tests."""
    def __init__(self, lines: list[str]) -> None:
        self._lines = list(lines)
        self.printed: list[str] = []

    def input(self, prompt: str = "") -> str:
        if not self._lines:
            raise EOFError
        return self._lines.pop(0)

    def print(self, s: str = "") -> None:
        self.printed.append(s)


@pytest.mark.unit
def test_cli_parses_move_and_end():
    io = _ScriptedIO(["move 7 1 -1", "end"])
    src = CLIHumanSource(input_fn=io.input, print_fn=io.print)
    view = {"turn": 1, "visible_units": [], "visible_cities": [],
            "inbox": [], "diplomatic_stances": []}
    d = src.decide(view, civ_id=0)
    assert len(d.goals) == 1
    g = d.goals[0]
    assert isinstance(g, MoveTo)
    assert g.unit_id == 7 and g.target == Hex(1, -1)


@pytest.mark.unit
def test_cli_parses_message_and_stance():
    io = _ScriptedIO([
        "msg 1 threat back off or else",
        "stance 2 war",
        "end",
    ])
    src = CLIHumanSource(input_fn=io.input, print_fn=io.print)
    view = {"turn": 1, "visible_units": [], "visible_cities": [],
            "inbox": [], "diplomatic_stances": []}
    d = src.decide(view, civ_id=0)
    assert len(d.diplomacy) == 2
    msg, stance = d.diplomacy
    assert isinstance(msg, SendMessage)
    assert msg.to_civ_id == 1 and msg.kind is MessageKind.THREAT
    assert msg.text == "back off or else"
    assert isinstance(stance, SetStance)
    assert stance.target_civ_id == 2 and stance.stance is DiplomaticStance.WAR


@pytest.mark.unit
def test_cli_parses_found_with_multi_word_name():
    io = _ScriptedIO(["found 3 0 0 New Babylon", "end"])
    src = CLIHumanSource(input_fn=io.input, print_fn=io.print)
    view = {"turn": 1, "visible_units": [], "visible_cities": [],
            "inbox": [], "diplomatic_stances": []}
    d = src.decide(view, civ_id=0)
    assert len(d.goals) == 1
    g = d.goals[0]
    assert isinstance(g, FoundCityNear)
    assert g.name == "New Babylon"


@pytest.mark.unit
def test_cli_unknown_command_is_skipped():
    io = _ScriptedIO(["explode all units", "end"])
    src = CLIHumanSource(input_fn=io.input, print_fn=io.print)
    view = {"turn": 1, "visible_units": [], "visible_cities": [],
            "inbox": [], "diplomatic_stances": []}
    d = src.decide(view, civ_id=0)
    assert d.goals == () and d.diplomacy == ()
    # The error should have been printed to the user.
    assert any("unknown command" in p for p in io.printed)


@pytest.mark.unit
def test_cli_invalid_message_kind_skipped():
    io = _ScriptedIO(["msg 1 grovel please dont attack", "end"])
    src = CLIHumanSource(input_fn=io.input, print_fn=io.print)
    view = {"turn": 1, "visible_units": [], "visible_cities": [],
            "inbox": [], "diplomatic_stances": []}
    d = src.decide(view, civ_id=0)
    assert d.diplomacy == ()
    assert any("unknown message kind" in p for p in io.printed)


@pytest.mark.unit
def test_cli_eof_ends_turn_gracefully():
    io = _ScriptedIO([])  # Immediate EOF.
    src = CLIHumanSource(input_fn=io.input, print_fn=io.print)
    view = {"turn": 1, "visible_units": [], "visible_cities": [],
            "inbox": [], "diplomatic_stances": []}
    d = src.decide(view, civ_id=0)
    assert d.goals == () and d.diplomacy == ()
