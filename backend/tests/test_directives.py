"""Tests for the directive layer — city/civ mutations from intents."""

from __future__ import annotations

import pytest

from app.engine.directives import (
    CancelProduction,
    DirectiveError,
    PurchaseStructure,
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
    civ_gold: int = 0,
) -> GameState:
    civs = (
        Civilization(
            id=0,
            name="A",
            leader_name="L",
            is_human=False,
            known_techs=civ_known,
            gold=civ_gold,
        ),
        Civilization(id=1, name="B", leader_name="L", is_human=False),
    )
    tile_owner = {
        Hex(1, 0): city.id
        for city in cities
        if city.location == Hex(0, 0)
    }
    return GameState(
        turn=1,
        map=generate_map(4, seed=0),
        civs=civs,
        cities=cities,
        units=(),
        tile_owner=tile_owner,
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
def test_cancel_production_removes_item_at_index():
    city = City(
        id=1,
        owner=0,
        name="Home",
        location=Hex(0, 0),
        production_queue=(
            BuildItem.unit(UnitType.SCOUT),
            BuildItem.unit(UnitType.WARRIOR),
            BuildItem.unit(UnitType.SETTLER),
        ),
        production_stored=4,
    )
    state = _state(cities=(city,))
    new_state = apply_directive(state, 0, CancelProduction(city_id=1, index=1))
    assert new_state.cities[0].production_queue == (
        BuildItem.unit(UnitType.SCOUT),
        BuildItem.unit(UnitType.SETTLER),
    )
    # Cancelling a non-head item keeps stored production intact.
    assert new_state.cities[0].production_stored == 4


@pytest.mark.unit
def test_cancel_production_head_forfeits_stored_production():
    city = City(
        id=1,
        owner=0,
        name="Home",
        location=Hex(0, 0),
        production_queue=(
            BuildItem.unit(UnitType.WARRIOR),
            BuildItem.unit(UnitType.SCOUT),
        ),
        production_stored=7,
    )
    state = _state(cities=(city,))
    new_state = apply_directive(state, 0, CancelProduction(city_id=1, index=0))
    assert new_state.cities[0].production_queue == (BuildItem.unit(UnitType.SCOUT),)
    assert new_state.cities[0].production_stored == 0


@pytest.mark.unit
def test_cancel_production_rejects_out_of_bounds():
    city = City(
        id=1,
        owner=0,
        name="Home",
        location=Hex(0, 0),
        production_queue=(BuildItem.unit(UnitType.SCOUT),),
    )
    state = _state(cities=(city,))
    with pytest.raises(DirectiveError, match="out of bounds"):
        apply_directive(state, 0, CancelProduction(city_id=1, index=5))


@pytest.mark.unit
def test_cancel_production_rejects_foreign_city():
    foreign = City(
        id=99,
        owner=1,
        name="Other",
        location=Hex(0, 0),
        production_queue=(BuildItem.unit(UnitType.SCOUT),),
    )
    state = _state(cities=(foreign,))
    with pytest.raises(DirectiveError, match="not owned"):
        apply_directive(state, 0, CancelProduction(city_id=99, index=0))


@pytest.mark.unit
def test_purchase_structure_adds_category_and_deducts_gold():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(cities=(city,), civ_gold=100)
    new_state = apply_directive(
        state, 0, PurchaseStructure(city_id=1, category="production", q=1, r=0)
    )
    assert "production" in new_state.cities[0].purchased_structures
    assert new_state.civs[0].gold == 85  # 100 - 15
    assert new_state.structures[0].category == "production"
    assert new_state.structures[0].location == Hex(1, 0)


@pytest.mark.unit
def test_purchase_structure_rejects_insufficient_gold():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(cities=(city,), civ_gold=10)
    with pytest.raises(DirectiveError, match="not enough gold"):
        apply_directive(
            state, 0, PurchaseStructure(city_id=1, category="production", q=1, r=0)
        )


@pytest.mark.unit
def test_purchase_structure_rejects_duplicate_category():
    city = City(
        id=1,
        owner=0,
        name="Home",
        location=Hex(0, 0),
        purchased_structures=frozenset({"production"}),
    )
    state = _state(cities=(city,), civ_gold=200)
    with pytest.raises(DirectiveError, match="already has"):
        apply_directive(
            state, 0, PurchaseStructure(city_id=1, category="production", q=1, r=0)
        )


@pytest.mark.unit
def test_purchase_structure_rejects_unknown_category():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(cities=(city,), civ_gold=200)
    with pytest.raises(DirectiveError, match="unknown structure category"):
        apply_directive(
            state, 0, PurchaseStructure(city_id=1, category="bogus", q=1, r=0)
        )


@pytest.mark.unit
def test_purchase_structure_rejects_tile_outside_city_borders():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(cities=(city,), civ_gold=200)
    with pytest.raises(DirectiveError, match="inside this city's borders"):
        apply_directive(
            state, 0, PurchaseStructure(city_id=1, category="production", q=2, r=0)
        )


@pytest.mark.unit
def test_purchase_structure_increases_production_yield():
    """A purchased structure increases the city's production tile yield."""
    from app.engine.production import _city_tile_yields

    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(cities=(city,), civ_gold=200)
    _, before_prod = _city_tile_yields(state, state.cities[0])
    new_state = apply_directive(
        state, 0, PurchaseStructure(city_id=1, category="production", q=1, r=0)
    )
    _, after_prod = _city_tile_yields(new_state, new_state.cities[0])
    assert after_prod == before_prod + 2


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
