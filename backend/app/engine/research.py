"""Simplified tech tree. ~20 techs with prerequisites and costs."""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.engine.models import Civilization, GameState


@dataclass(frozen=True, slots=True)
class Tech:
    id: str
    name: str
    cost: int
    prerequisites: tuple[str, ...]


TECHS: dict[str, Tech] = {
    t.id: t
    for t in (
        # Tier 1 — no prereqs
        Tech("agriculture", "Agriculture", 20, ()),
        Tech("pottery", "Pottery", 20, ()),
        Tech("mining", "Mining", 25, ()),
        Tech("fishing", "Fishing", 20, ()),
        Tech("archery", "Archery", 25, ()),
        # Tier 2
        Tech("animal_husbandry", "Animal Husbandry", 35, ("agriculture",)),
        Tech("trapping", "Trapping", 35, ("pottery",)),
        Tech("bronze_working", "Bronze Working", 55, ("mining",)),
        Tech("sailing", "Sailing", 45, ("fishing",)),
        Tech("wheel", "The Wheel", 55, ("animal_husbandry",)),
        Tech("masonry", "Masonry", 55, ("mining",)),
        # Tier 3
        Tech("writing", "Writing", 75, ("pottery",)),
        Tech("horseback_riding", "Horseback Riding", 70, ("animal_husbandry",)),
        Tech("currency", "Currency", 80, ("bronze_working",)),
        Tech("calendar", "Calendar", 70, ("pottery", "agriculture")),
        Tech("iron_working", "Iron Working", 120, ("bronze_working",)),
        # Tier 4
        Tech("mathematics", "Mathematics", 110, ("currency",)),
        Tech("construction", "Construction", 100, ("masonry",)),
        Tech("philosophy", "Philosophy", 120, ("writing",)),
        Tech("astronomy", "Astronomy", 130, ("mathematics", "sailing")),
    )
}


SCIENCE_PER_CITY = 2


class ResearchError(ValueError):
    """Raised when a research action is invalid."""


def _find_civ(state: GameState, civ_id: int) -> tuple[int, Civilization]:
    for i, c in enumerate(state.civs):
        if c.id == civ_id:
            return i, c
    raise ResearchError(f"unknown civ id {civ_id}")


def _prereqs_met(civ: Civilization, tech: Tech) -> bool:
    return all(p in civ.known_techs for p in tech.prerequisites)


def set_research(state: GameState, civ_id: int, tech_id: str) -> GameState:
    idx, civ = _find_civ(state, civ_id)
    if tech_id not in TECHS:
        raise ResearchError(f"unknown tech {tech_id}")
    tech = TECHS[tech_id]
    if tech_id in civ.known_techs:
        raise ResearchError(f"tech {tech_id} already researched")
    if not _prereqs_met(civ, tech):
        raise ResearchError(f"prerequisites not met for {tech_id}")

    updated = replace(civ, researching=tech_id)
    new_civs = tuple(
        updated if i == idx else c for i, c in enumerate(state.civs)
    )
    return replace(state, civs=new_civs)


def _science_income(state: GameState, civ_id: int) -> int:
    return SCIENCE_PER_CITY * len(state.cities_for(civ_id))


def default_tech_for(civ: Civilization) -> str | None:
    """Pick the cheapest unresearched tech whose prereqs are met.

    Ties broken by tech id for determinism. Returns None when nothing is
    available (everything known, or prereqs unsatisfiable).
    """
    candidates = [
        t
        for t in TECHS.values()
        if t.id not in civ.known_techs and _prereqs_met(civ, t)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda t: (t.cost, t.id))
    return candidates[0].id


def tick_research(state: GameState) -> GameState:
    new_civs: list[Civilization] = []
    for civ in state.civs:
        researching = civ.researching
        if researching is None:
            researching = default_tech_for(civ)
            if researching is None:
                new_civs.append(civ)
                continue
            civ = replace(civ, researching=researching)
        tech = TECHS.get(researching)
        if tech is None:
            new_civs.append(replace(civ, researching=None))
            continue
        new_points = civ.science + _science_income(state, civ.id)
        if new_points >= tech.cost:
            known = frozenset(civ.known_techs | {tech.id})
            new_civs.append(
                replace(
                    civ,
                    known_techs=known,
                    science=new_points - tech.cost,
                    researching=None,
                )
            )
        else:
            new_civs.append(replace(civ, science=new_points))
    return replace(state, civs=tuple(new_civs))
