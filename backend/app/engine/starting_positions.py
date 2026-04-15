"""Pick fair, spread-out starting tiles for civilizations."""

from __future__ import annotations

from app.engine.hex import Hex, hex_distance, hex_neighbors
from app.engine.models import GameMap
from app.engine.terrain import IMPASSABLE_TERRAIN, Terrain, tile_yields

MIN_START_DISTANCE = 4

_EXCLUDED_TERRAIN: frozenset[Terrain] = frozenset(
    IMPASSABLE_TERRAIN | {Terrain.COAST, Terrain.DESERT, Terrain.TUNDRA}
)


def _local_score(game_map: GameMap, coord: Hex) -> int:
    tile = game_map.tiles[coord]
    y = tile_yields(tile)
    score = y.food * 2 + y.production + y.gold
    for n in hex_neighbors(coord):
        neighbor = game_map.tiles.get(n)
        if neighbor is None:
            continue
        ny = tile_yields(neighbor)
        score += ny.food * 2 + ny.production + ny.gold
    return score


def starting_positions(game_map: GameMap, n: int) -> list[Hex]:
    if n <= 0:
        return []

    candidates = [
        coord
        for coord, tile in game_map.tiles.items()
        if tile.terrain not in _EXCLUDED_TERRAIN
    ]
    if not candidates:
        raise ValueError("no land candidates for starting positions")

    # Deterministic order: score desc, then coord tiebreak.
    scored = sorted(
        candidates,
        key=lambda c: (-_local_score(game_map, c), c.q, c.r),
    )

    chosen: list[Hex] = []
    for coord in scored:
        if all(hex_distance(coord, other) >= MIN_START_DISTANCE for other in chosen):
            chosen.append(coord)
            if len(chosen) == n:
                return chosen

    raise ValueError(
        f"could not place {n} starting positions with min distance "
        f"{MIN_START_DISTANCE} on radius-{game_map.radius} map"
    )
