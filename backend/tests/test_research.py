from dataclasses import replace

import pytest

from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import City, Civilization, GameState
from app.engine.research import (
    ResearchError,
    TECHS,
    set_research,
    tick_research,
)


def _civ(civ_id: int = 0, known: frozenset[str] = frozenset(), researching: str | None = None, science: int = 0) -> Civilization:
    return Civilization(
        id=civ_id,
        name=f"Civ{civ_id}",
        leader_name="L",
        is_human=False,
        known_techs=known,
        researching=researching,
        science=science,
    )


def _state(civs: tuple[Civilization, ...], cities: tuple[City, ...] = ()) -> GameState:
    return GameState(
        turn=1,
        map=generate_map(2, seed=0),
        civs=civs,
        cities=cities,
        units=(),
    )


def test_tech_tree_has_twenty_techs():
    assert len(TECHS) == 20


def test_set_research_sets_field():
    state = _state((_civ(),))
    new_state = set_research(state, 0, "agriculture")
    assert new_state.civs[0].researching == "agriculture"


def test_set_research_unknown_tech_raises():
    state = _state((_civ(),))
    with pytest.raises(ResearchError, match="unknown tech"):
        set_research(state, 0, "warp_drive")


def test_set_research_already_known_raises():
    state = _state((_civ(known=frozenset({"agriculture"})),))
    with pytest.raises(ResearchError, match="already"):
        set_research(state, 0, "agriculture")


def test_set_research_missing_prereqs_raises():
    state = _state((_civ(),))
    with pytest.raises(ResearchError, match="prerequisites"):
        set_research(state, 0, "animal_husbandry")


def test_set_research_with_prereqs_met_succeeds():
    state = _state((_civ(known=frozenset({"agriculture"})),))
    new_state = set_research(state, 0, "animal_husbandry")
    assert new_state.civs[0].researching == "animal_husbandry"


def test_tick_research_accumulates_science_per_city():
    civ = _civ(researching="agriculture")
    cities = (
        City(id=1, owner=0, name="A", location=Hex(0, 0)),
        City(id=2, owner=0, name="B", location=Hex(1, 0)),
    )
    state = _state((civ,), cities=cities)
    new_state = tick_research(state)
    # 2 cities * 2 science each = 4
    assert new_state.civs[0].science == 4


def test_tick_research_completes_tech_when_cost_met():
    # agriculture cost 20; stockpile 19, 1 city → +2 → 21, complete, remainder 1
    civ = _civ(researching="agriculture", science=19)
    cities = (City(id=1, owner=0, name="A", location=Hex(0, 0)),)
    state = _state((civ,), cities=cities)
    new_state = tick_research(state)
    new_civ = new_state.civs[0]
    assert "agriculture" in new_civ.known_techs
    assert new_civ.researching is None
    assert new_civ.science == 1


def test_tick_research_idle_civ_unchanged():
    civ = _civ(researching=None, science=5)
    state = _state((civ,))
    new_state = tick_research(state)
    assert new_state.civs[0].science == 5
