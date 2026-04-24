"""Tests for the directive layer — city/civ mutations from intents."""

from __future__ import annotations

import pytest

from app.engine.directives import (
    DirectiveError,
    QueueProduction,
    StartResearch,
    apply_directive,
)
from app.engine.models import BuildItem, BuildingType
from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import (
    City,
    Civilization,
    GameState,
    UnitType,
)


def _state(
    cities: tuple[City, ...] = (),
    civ_known: frozenset[str] = frozenset(),
) -> GameState:
    civs = (
        Civilization(
            id=0,
            name="A",
            leader_name="L",
            is_human=False,
            known_techs=civ_known,
        ),
        Civilization(id=1, name="B", leader_name="L", is_human=False),
    )
    return GameState(
        turn=1,
        map=generate_map(4, seed=0),
        civs=civs,
        cities=cities,
        units=(),
    )


@pytest.mark.unit
def test_queue_production_appends_to_queue():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(cities=(city,))
    new_state = apply_directive(
        state, 0, QueueProduction(city_id=1, item=BuildItem.unit(UnitType.WARRIOR))
    )
    assert new_state.cities[0].production_queue == (BuildItem.unit(UnitType.WARRIOR),)


@pytest.mark.unit
def test_queue_production_preserves_existing_queue_order():
    city = City(
        id=1,
        owner=0,
        name="Home",
        location=Hex(0, 0),
        production_queue=(BuildItem.unit(UnitType.SCOUT),),
    )
    state = _state(cities=(city,))
    new_state = apply_directive(
        state, 0, QueueProduction(city_id=1, item=BuildItem.unit(UnitType.WARRIOR))
    )
    assert new_state.cities[0].production_queue == (
        BuildItem.unit(UnitType.SCOUT),
        BuildItem.unit(UnitType.WARRIOR),
    )


@pytest.mark.unit
def test_queue_production_rejects_foreign_city():
    foreign = City(id=99, owner=1, name="Other", location=Hex(0, 0))
    state = _state(cities=(foreign,))
    with pytest.raises(DirectiveError, match="not owned"):
        apply_directive(
            state, 0, QueueProduction(city_id=99, item=BuildItem.unit(UnitType.WARRIOR))
        )


@pytest.mark.unit
def test_queue_production_rejects_unknown_city():
    state = _state()
    with pytest.raises(DirectiveError, match="unknown city"):
        apply_directive(
            state, 0, QueueProduction(city_id=404, item=BuildItem.unit(UnitType.WARRIOR))
        )


@pytest.mark.unit
def test_queue_production_rejects_locked_building():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(cities=(city,))
    with pytest.raises(DirectiveError, match="not unlocked"):
        apply_directive(
            state,
            0,
            QueueProduction(city_id=1, item=BuildItem.building(BuildingType.GRANARY)),
        )


@pytest.mark.unit
def test_queue_production_allows_unlocked_building():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(cities=(city,), civ_known=frozenset({"pottery"}))
    new_state = apply_directive(
        state,
        0,
        QueueProduction(city_id=1, item=BuildItem.building(BuildingType.GRANARY)),
    )
    assert new_state.cities[0].production_queue == (
        BuildItem.building(BuildingType.GRANARY),
    )


@pytest.mark.unit
def test_start_research_sets_field():
    state = _state()
    new_state = apply_directive(state, 0, StartResearch(tech_id="agriculture"))
    assert new_state.civs[0].researching == "agriculture"


@pytest.mark.unit
def test_start_research_rejects_unknown_tech():
    state = _state()
    with pytest.raises(DirectiveError, match="unknown tech"):
        apply_directive(state, 0, StartResearch(tech_id="warp_drive"))


@pytest.mark.unit
def test_start_research_rejects_known_tech():
    state = _state(civ_known=frozenset({"agriculture"}))
    with pytest.raises(DirectiveError, match="already"):
        apply_directive(state, 0, StartResearch(tech_id="agriculture"))


@pytest.mark.unit
def test_start_research_rejects_unmet_prereqs():
    state = _state()
    with pytest.raises(DirectiveError, match="prerequisites"):
        apply_directive(state, 0, StartResearch(tech_id="animal_husbandry"))
