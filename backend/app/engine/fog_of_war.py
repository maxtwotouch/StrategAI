"""Per-civilization visibility. Pure — returns the set of visible Hex coords."""

from __future__ import annotations

from app.engine.hex import Hex, hex_range
from app.engine.models import GameState

CITY_SIGHT = 2


def visible_tiles(state: GameState, civ_id: int) -> frozenset[Hex]:
    seen: set[Hex] = set()
    for unit in state.units:
        if unit.owner != civ_id:
            continue
        for coord in hex_range(unit.location, unit.stats.sight):
            if coord in state.map:
                seen.add(coord)
    for city in state.cities:
        if city.owner != civ_id:
            continue
        for coord in hex_range(city.location, CITY_SIGHT):
            if coord in state.map:
                seen.add(coord)
    return frozenset(seen)
