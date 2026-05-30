"""City and civilization directives — production queueing, research selection.

Directives are typed mutations a leader issues each turn that change cities or
civs (rather than units, which goals already cover, or relationships, which
diplomacy covers).  They are pure: `apply_directive` validates legality and
returns a new GameState.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Union

from app.engine.buildings import (
    PURCHASABLE_STRUCTURE_CATEGORIES,
    STRUCTURE_GOLD_COST,
)
from app.engine.models import BuildItem, BuildKind, BuildingType, City, GameState, UnitType
from app.engine.research import (
    ResearchError,
    can_build_building,
    can_build_unit,
    set_research,
)


@dataclass(frozen=True, slots=True)
class QueueProduction:
    """Append a unit to a city's production queue."""

    city_id: int
    item: BuildItem


@dataclass(frozen=True, slots=True)
class CancelProduction:
    """Remove the item at ``index`` from a city's production queue.

    Cancelling the queue head (``index == 0``) forfeits any production_stored
    accumulated for it; cancelling later positions does not alter stored
    production, since that progress was earmarked for the head.
    """

    city_id: int
    index: int


@dataclass(frozen=True, slots=True)
class PurchaseStructure:
    """Spend gold to place an asset-API structure in a city.

    Categories mirror the asset service's StructureCategory enum
    (fortification | production | housing | sacred). One of each per city.
    Every purchase grants the same production bonus regardless of category —
    the choice is a visual / thematic one for now.
    """

    city_id: int
    category: str


@dataclass(frozen=True, slots=True)
class StartResearch:
    """Set the civ's currently-researching tech."""

    tech_id: str


Directive = Union[
    QueueProduction,
    CancelProduction,
    PurchaseStructure,
    StartResearch,
]


class DirectiveError(ValueError):
    """Raised when a directive is invalid."""


def _find_city(state: GameState, city_id: int) -> tuple[int, City]:
    for i, c in enumerate(state.cities):
        if c.id == city_id:
            return i, c
    raise DirectiveError(f"unknown city id {city_id}")


def _queue_production(
    state: GameState, civ_id: int, directive: QueueProduction
) -> GameState:
    idx, city = _find_city(state, directive.city_id)
    if city.owner != civ_id:
        raise DirectiveError(
            f"city {directive.city_id} is not owned by civ {civ_id}"
        )
    civ = next((c for c in state.civs if c.id == civ_id), None)
    if civ is None:
        raise DirectiveError(f"unknown civ id {civ_id}")

    if directive.item.kind is BuildKind.UNIT:
        unit_type = UnitType(directive.item.id)
        if not can_build_unit(civ, unit_type):
            raise DirectiveError(f"unit {unit_type.value} is not unlocked")
    else:
        building_type = BuildingType(directive.item.id)
        if building_type in city.buildings:
            raise DirectiveError(f"building {building_type.value} already built")
        if any(
            item.kind is BuildKind.BUILDING and item.id == building_type.value
            for item in city.production_queue
        ):
            raise DirectiveError(f"building {building_type.value} already queued")
        if not can_build_building(civ, building_type):
            raise DirectiveError(f"building {building_type.value} is not unlocked")

    new_queue = city.production_queue + (directive.item,)
    new_city = replace(city, production_queue=new_queue)
    new_cities = tuple(
        new_city if i == idx else c for i, c in enumerate(state.cities)
    )
    return replace(state, cities=new_cities)


def _cancel_production(
    state: GameState, civ_id: int, directive: CancelProduction
) -> GameState:
    idx, city = _find_city(state, directive.city_id)
    if city.owner != civ_id:
        raise DirectiveError(
            f"city {directive.city_id} is not owned by civ {civ_id}"
        )
    if directive.index < 0 or directive.index >= len(city.production_queue):
        raise DirectiveError(
            f"queue index {directive.index} out of bounds "
            f"(queue size {len(city.production_queue)})"
        )
    new_queue = (
        city.production_queue[: directive.index]
        + city.production_queue[directive.index + 1 :]
    )
    new_production = 0 if directive.index == 0 else city.production_stored
    new_city = replace(
        city, production_queue=new_queue, production_stored=new_production
    )
    new_cities = tuple(
        new_city if i == idx else c for i, c in enumerate(state.cities)
    )
    return replace(state, cities=new_cities)


def _purchase_structure(
    state: GameState, civ_id: int, directive: PurchaseStructure
) -> GameState:
    idx, city = _find_city(state, directive.city_id)
    if city.owner != civ_id:
        raise DirectiveError(
            f"city {directive.city_id} is not owned by civ {civ_id}"
        )
    if directive.category not in PURCHASABLE_STRUCTURE_CATEGORIES:
        raise DirectiveError(
            f"unknown structure category '{directive.category}'. Must be one of: "
            f"{', '.join(sorted(PURCHASABLE_STRUCTURE_CATEGORIES))}"
        )
    if directive.category in city.purchased_structures:
        raise DirectiveError(
            f"city already has a {directive.category} structure"
        )
    civ = next((c for c in state.civs if c.id == civ_id), None)
    if civ is None:
        raise DirectiveError(f"unknown civ id {civ_id}")
    if civ.gold < STRUCTURE_GOLD_COST:
        raise DirectiveError(
            f"not enough gold (need {STRUCTURE_GOLD_COST}, have {civ.gold})"
        )

    new_city = replace(
        city,
        purchased_structures=city.purchased_structures | {directive.category},
    )
    new_cities = tuple(
        new_city if i == idx else c for i, c in enumerate(state.cities)
    )
    new_civ = replace(civ, gold=civ.gold - STRUCTURE_GOLD_COST)
    new_civs = tuple(new_civ if c.id == civ_id else c for c in state.civs)
    return replace(state, cities=new_cities, civs=new_civs)


def _start_research(
    state: GameState, civ_id: int, directive: StartResearch
) -> GameState:
    try:
        return set_research(state, civ_id, directive.tech_id)
    except ResearchError as e:
        raise DirectiveError(str(e)) from e


def apply_directive(
    state: GameState, civ_id: int, directive: Directive
) -> GameState:
    """Validate + apply a single directive. Raises DirectiveError on failure."""
    if isinstance(directive, QueueProduction):
        return _queue_production(state, civ_id, directive)
    if isinstance(directive, CancelProduction):
        return _cancel_production(state, civ_id, directive)
    if isinstance(directive, PurchaseStructure):
        return _purchase_structure(state, civ_id, directive)
    if isinstance(directive, StartResearch):
        return _start_research(state, civ_id, directive)
    raise DirectiveError(f"unknown directive type {type(directive).__name__}")
