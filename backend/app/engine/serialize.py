"""Serialize GameState into a fog-filtered, JSON-safe dict per civilization.

This is the single source of truth for both the LLM prompt payload and the
eventual frontend state. A civ only sees tiles currently in its visibility
frontier, units/cities on those tiles, and civs it has encountered.
"""

from __future__ import annotations

from typing import Any

from app.engine.diplomacy import (
    DiplomaticEvent,
    DiplomaticMessage,
    inbox_for,
    met_civs,
    relationship_between,
    truce_active,
)
from app.engine.economy import civ_gold_income, civ_gold_upkeep
from app.engine.fog_of_war import visible_tiles
from app.engine.victory import SCORE_THRESHOLD, civ_score
from app.engine.hex import Hex
from app.engine.models import (
    UNIT_BUILD_COST,
    City,
    Civilization,
    GameState,
    Tile,
    Unit,
    UnitType,
)
from app.engine.research import TECHS, can_build_unit


def _serialize_tile(tile: Tile) -> dict[str, Any]:
    return {
        "q": tile.coord.q,
        "r": tile.coord.r,
        "terrain": tile.terrain.value,
        "elevation": round(tile.elevation, 3),
        "moisture": round(tile.moisture, 3),
        "temperature": round(tile.temperature, 3),
        "resource": tile.resource.value if tile.resource else None,
        "feature": tile.feature.value if tile.feature else None,
        "river": tile.river,
        "improvement": tile.improvement.value if tile.improvement else None,
    }


def _serialize_unit(unit: Unit) -> dict[str, Any]:
    work_order: dict[str, Any] | None = None
    if unit.work_order is not None:
        coord, improvement = unit.work_order
        work_order = {
            "q": coord.q,
            "r": coord.r,
            "improvement": improvement.value,
            "turns_remaining": unit.work_turns_remaining,
        }
    return {
        "id": unit.id,
        "owner": unit.owner,
        "type": unit.type.value,
        "q": unit.location.q,
        "r": unit.location.r,
        "health": unit.health,
        "max_health": unit.stats.max_health,
        "moves_remaining": unit.moves_remaining,
        "attack": unit.stats.attack,
        "defense": unit.stats.defense,
        "sight": unit.stats.sight,
        "acted_this_turn": unit.acted_this_turn,
        "work_order": work_order,
    }


def _serialize_city(city: City, *, owned: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": city.id,
        "owner": city.owner,
        "name": city.name,
        "q": city.location.q,
        "r": city.location.r,
        "population": city.population,
        "food_stored": city.food_stored,
        "production_stored": city.production_stored,
        "health": city.health,
        "max_health": city.max_health,
        "is_capital": city.is_capital,
        "buildings": sorted(b.value for b in city.buildings),
        "purchased_structures": sorted(city.purchased_structures),
        "border_radius": city.border_radius,
        "culture_stored": city.culture_stored,
    }
    if owned:
        out["production_queue"] = [item.id for item in city.production_queue]
        out["worked_tiles"] = sorted(
            [{"q": h.q, "r": h.r} for h in city.worked_tiles],
            key=lambda d: (d["q"], d["r"]),
        )
    return out


def _serialize_civ_summary(civ: Civilization) -> dict[str, Any]:
    return {
        "id": civ.id,
        "name": civ.name,
        "leader": civ.leader_name,
        "color": civ.color,
        "traits": list(civ.traits),
    }


def _serialize_message(m: DiplomaticMessage) -> dict[str, Any]:
    return {
        "from_civ_id": m.from_civ_id,
        "to_civ_id": m.to_civ_id,
        "turn": m.turn,
        "kind": m.kind.value,
        "text": m.text,
    }


def _serialize_self(civ: Civilization, state: GameState) -> dict[str, Any]:
    return {
        "id": civ.id,
        "name": civ.name,
        "leader": civ.leader_name,
        "color": civ.color,
        "traits": list(civ.traits),
        "gold": civ.gold,
        "gold_income": civ_gold_income(state, civ.id),
        "gold_upkeep": civ_gold_upkeep(state, civ.id),
        "science": civ.science,
        "culture": civ.culture,
        "known_techs": sorted(civ.known_techs),
        "researching": civ.researching,
        "score": civ_score(state, civ),
        "score_threshold": SCORE_THRESHOLD,
    }


def _serialize_diplomatic_event(event: DiplomaticEvent) -> dict[str, Any]:
    return {
        "turn": event.turn,
        "kind": event.kind.value,
        "actor_civ_id": event.actor_civ_id,
        "target_civ_id": event.target_civ_id,
        "summary": event.summary,
        "relationship_delta": event.relationship_delta,
    }


def local_view(state: GameState, civ_id: int) -> dict[str, Any]:
    civ = next((c for c in state.civs if c.id == civ_id), None)
    if civ is None:
        raise ValueError(f"unknown civ id {civ_id}")

    visible: frozenset[Hex] = visible_tiles(state, civ_id)

    tiles_sorted = sorted(
        (state.map.tiles[c] for c in visible if c in state.map.tiles),
        key=lambda t: (t.coord.q, t.coord.r),
    )
    tiles_out = [_serialize_tile(t) for t in tiles_sorted]

    visible_units = sorted(
        (u for u in state.units if u.location in visible),
        key=lambda u: u.id,
    )
    units_out = [_serialize_unit(u) for u in visible_units]

    visible_cities = sorted(
        (c for c in state.cities if c.location in visible),
        key=lambda c: c.id,
    )
    cities_out = [_serialize_city(c, owned=(c.owner == civ_id)) for c in visible_cities]

    met_ids = met_civs(state, civ_id)

    known_civs = sorted(
        (_serialize_civ_summary(c) for c in state.civs if c.id in met_ids),
        key=lambda d: d["id"],
    )

    inbox = [_serialize_message(m) for m in inbox_for(state, civ_id)]

    stances: list[dict[str, Any]] = []
    for other_id in sorted(met_ids - {civ_id}):
        truce_until = state.truces.get(
            tuple(sorted((civ_id, other_id)))
        )
        stances.append({
            "civ_id": other_id,
            "stance": state.stance_between(civ_id, other_id).value,
            "relationship": relationship_between(state, civ_id, other_id),
            "truce_active": truce_active(state, civ_id, other_id),
            "truce_until": truce_until,
        })

    # Recent diplomatic events involving this civ (last 12). Filtered so the
    # LLM sees a focused narrative rather than the full append-only log.
    relevant_events = [
        e for e in state.diplomatic_events
        if e.actor_civ_id == civ_id or e.target_civ_id == civ_id
    ]
    recent_events = [
        _serialize_diplomatic_event(e) for e in relevant_events[-12:]
    ]

    # Standings — score for every known civ + self.
    standings_civs = [c for c in state.civs if c.id in met_ids]
    standings = sorted(
        (
            {
                "civ_id": c.id,
                "name": c.name,
                "score": civ_score(state, c),
            }
            for c in standings_civs
        ),
        key=lambda d: (-d["score"], d["civ_id"]),
    )

    available_techs = sorted(
        (
            {
                "id": t.id,
                "name": t.name,
                "cost": t.cost,
                "prerequisites": list(t.prerequisites),
            }
            for t in TECHS.values()
            if t.id not in civ.known_techs
            and all(p in civ.known_techs for p in t.prerequisites)
        ),
        key=lambda d: (d["cost"], d["id"]),
    )

    unit_costs = {ut.value: cost for ut, cost in UNIT_BUILD_COST.items()}
    available_units = sorted(ut.value for ut in UnitType if can_build_unit(civ, ut))

    tile_owner_out = sorted(
        (
            {"q": coord.q, "r": coord.r, "city_id": city_id}
            for coord, city_id in state.tile_owner.items()
            if coord in visible
        ),
        key=lambda d: (d["q"], d["r"]),
    )

    return {
        "turn": state.turn,
        "seed": state.seed,
        "current_civ_id": state.current_civ().id,
        "map_radius": state.map.radius,
        "self": _serialize_self(civ, state),
        "known_civs": known_civs,
        "visible_tiles": tiles_out,
        "visible_units": units_out,
        "visible_cities": cities_out,
        "tile_owner": tile_owner_out,
        "inbox": inbox,
        "diplomatic_stances": stances,
        "available_techs": available_techs,
        "available_units": available_units,
        "unit_build_costs": unit_costs,
        "recent_diplomatic_events": recent_events,
        "standings": standings,
        "score_threshold": SCORE_THRESHOLD,
    }
