"""Tests for extended GameState fields: seed, turn order, diplomacy, visibility."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import (
    Civilization,
    DiplomaticStance,
    GameState,
)


def _bare_state() -> GameState:
    return GameState(
        turn=1,
        map=generate_map(3, seed=0),
        civs=(
            Civilization(id=0, name="Rome", leader_name="Caesar", is_human=True),
            Civilization(id=1, name="Egypt", leader_name="Cleo", is_human=False),
        ),
        cities=(),
        units=(),
    )


@pytest.mark.unit
def test_defaults_backwards_compatible() -> None:
    state = _bare_state()
    assert state.seed == 0
    assert state.current_civ_idx == 0
    assert state.diplomacy == {}
    assert state.visibility == {}


@pytest.mark.unit
def test_state_with_seed_and_diplomacy() -> None:
    state = replace(
        _bare_state(),
        seed=42,
        current_civ_idx=1,
        diplomacy={(0, 1): DiplomaticStance.WAR},
        visibility={0: frozenset({Hex(0, 0)})},
    )
    assert state.seed == 42
    assert state.current_civ_idx == 1
    assert state.diplomacy[(0, 1)] is DiplomaticStance.WAR
    assert Hex(0, 0) in state.visibility[0]


@pytest.mark.unit
def test_civilization_extended_fields() -> None:
    civ = Civilization(
        id=0,
        name="Rome",
        leader_name="Caesar",
        is_human=False,
        starting_position=Hex(1, -1),
        color="#ff0000",
        traits=("expansionist", "militaristic"),
    )
    assert civ.starting_position == Hex(1, -1)
    assert civ.color == "#ff0000"
    assert "expansionist" in civ.traits


@pytest.mark.unit
def test_current_civ_returns_civ_at_idx() -> None:
    state = _bare_state()
    assert state.current_civ().name == "Rome"
    state2 = replace(state, current_civ_idx=1)
    assert state2.current_civ().name == "Egypt"


@pytest.mark.unit
def test_stance_between_symmetric_lookup() -> None:
    state = replace(
        _bare_state(),
        diplomacy={(0, 1): DiplomaticStance.PEACE},
    )
    assert state.stance_between(0, 1) is DiplomaticStance.PEACE
    assert state.stance_between(1, 0) is DiplomaticStance.PEACE
    assert state.stance_between(0, 0) is DiplomaticStance.PEACE
