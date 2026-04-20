"""Serialize GameState into a fog-filtered, JSON-safe dict per civilization.

This is the single source of truth for both the LLM prompt payload and the
eventual frontend state. A civ only sees tiles currently in its visibility
frontier, units/cities on those tiles, and civs it has encountered.
"""

from __future__ import annotations

from typing import Any

from app.engine.diplomacy import DiplomaticMessage, inbox_for, met_civs
from app.engine.fog_of_war import visible_tiles
from app.engine.hex import Hex
from app.engine.models import City, Civilization, GameState, Tile, Unit


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
    }


def _serialize_unit(unit: Unit) -> dict[str, Any]:
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
    }


def _serialize_city(city: City) -> dict[str, Any]:
    return {
        "id": city.id,
        "owner": city.owner,
        "name": city.name,
        "q": city.location.q,
        "r": city.location.r,
        "population": city.population,
        "food_stored": city.food_stored,
        "production_stored": city.production_stored,
    }


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


def _serialize_self(civ: Civilization) -> dict[str, Any]:
    return {
        "id": civ.id,
        "name": civ.name,
        "leader": civ.leader_name,
        "color": civ.color,
        "traits": list(civ.traits),
        "gold": civ.gold,
        "science": civ.science,
        "culture": civ.culture,
        "known_techs": sorted(civ.known_techs),
        "researching": civ.researching,
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
    cities_out = [_serialize_city(c) for c in visible_cities]

    met_ids = met_civs(state, civ_id)

    known_civs = sorted(
        (_serialize_civ_summary(c) for c in state.civs if c.id in met_ids),
        key=lambda d: d["id"],
    )

    inbox = [_serialize_message(m) for m in inbox_for(state, civ_id)]

    stances: list[dict[str, Any]] = []
    for other_id in sorted(met_ids - {civ_id}):
        stances.append({
            "civ_id": other_id,
            "stance": state.stance_between(civ_id, other_id).value,
        })

    return {
        "turn": state.turn,
        "seed": state.seed,
        "current_civ_id": state.current_civ().id,
        "map_radius": state.map.radius,
        "self": _serialize_self(civ),
        "known_civs": known_civs,
        "visible_tiles": tiles_out,
        "visible_units": units_out,
        "visible_cities": cities_out,
        "inbox": inbox,
        "diplomatic_stances": stances,
    }
