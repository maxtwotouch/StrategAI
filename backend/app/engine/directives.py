"""City and civilization directives — production queueing, research selection.

Directives are typed mutations a leader issues each turn that change cities or
civs (rather than units, which goals already cover, or relationships, which
diplomacy covers).  They are pure: `apply_directive` validates legality and
returns a new GameState.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Union

from app.engine.models import City, GameState, UnitType
from app.engine.research import ResearchError, set_research


@dataclass(frozen=True, slots=True)
class QueueProduction:
    """Append a unit to a city's production queue."""

    city_id: int
    unit_type: UnitType


@dataclass(frozen=True, slots=True)
class StartResearch:
    """Set the civ's currently-researching tech."""

    tech_id: str


Directive = Union[QueueProduction, StartResearch]


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
    new_queue = city.production_queue + (directive.unit_type,)
    new_city = replace(city, production_queue=new_queue)
    new_cities = tuple(
        new_city if i == idx else c for i, c in enumerate(state.cities)
    )
    return replace(state, cities=new_cities)


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
    if isinstance(directive, StartResearch):
        return _start_research(state, civ_id, directive)
    raise DirectiveError(f"unknown directive type {type(directive).__name__}")
