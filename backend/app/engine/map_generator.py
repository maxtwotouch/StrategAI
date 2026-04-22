"""Layered-noise deterministic map generator.

Pipeline:
  1. Elevation noise → ocean/coast/land/hills/mountain.
  2. Temperature from latitude minus elevation penalty.
  3. Moisture noise → biome assignment with temperature.
  4. Features (forest/jungle/marsh) placed on compatible biomes.
  5. Resources scattered with minimum spacing, respecting terrain.
  6. Rivers traced downhill from high-elevation land tiles.
"""

from __future__ import annotations

import random
from dataclasses import replace

from opensimplex import OpenSimplex

from math import hypot

from app.engine.hex import Hex, hex_distance, hex_neighbors, hex_range
from app.engine.models import GameMap, Tile
from app.engine.terrain import (
    RESOURCES,
    Feature,
    Resource,
    Terrain,
)


_CONTINENT_FREQ = 0.14
_ELEVATION_FREQ = 0.36
_RIDGE_FREQ = 0.22
_MOISTURE_FREQ = 0.24
_TEMPERATURE_FREQ = 0.18
_SEA_LEVEL = -0.10
_COAST_LEVEL = 0.03
_HILL_LEVEL = 0.46
_MOUNTAIN_LEVEL = 0.74


def _noise(gen: OpenSimplex, q: int, r: int, freq: float) -> float:
    return float(gen.noise2(q * freq, r * freq))


def _continent_elevation(
    continent_gen: OpenSimplex,
    detail_gen: OpenSimplex,
    ridge_gen: OpenSimplex,
    coord: Hex,
    radius: int,
) -> float:
    dist_norm = hypot(coord.q, coord.r) / max(radius, 1)
    radial = max(0.0, 1.0 - dist_norm**1.65)
    continent = _noise(continent_gen, coord.q, coord.r, _CONTINENT_FREQ)
    detail = _noise(detail_gen, coord.q, coord.r, _ELEVATION_FREQ)
    ridge_raw = _noise(ridge_gen, coord.q, coord.r, _RIDGE_FREQ)
    ridge = 1.0 - abs(ridge_raw)

    return (
        radial * 0.62
        + continent * 0.34
        + detail * 0.20
        + ridge * 0.10
        - 0.20
    )


def _base_terrain_from_elevation(elevation: float, temperature: float) -> Terrain:
    if elevation < _SEA_LEVEL:
        return Terrain.OCEAN
    if elevation < _COAST_LEVEL:
        return Terrain.COAST
    if elevation >= _MOUNTAIN_LEVEL:
        return Terrain.MOUNTAIN
    if temperature < 0.15:
        return Terrain.SNOW
    if temperature < 0.30:
        return Terrain.TUNDRA
    if elevation >= _HILL_LEVEL:
        return Terrain.HILLS
    return Terrain.PLAINS  # placeholder, refined by moisture


def _refine_with_moisture(terrain: Terrain, moisture: float, temperature: float) -> Terrain:
    if terrain is not Terrain.PLAINS:
        return terrain
    if moisture < -0.35 and temperature > 0.6:
        return Terrain.DESERT
    if moisture < -0.1:
        return Terrain.PLAINS
    if moisture < 0.3:
        return Terrain.GRASSLAND
    return Terrain.FOREST


def _pick_feature(
    terrain: Terrain, moisture: float, temperature: float, rng: random.Random
) -> Feature | None:
    if terrain is Terrain.GRASSLAND and moisture > 0.4 and rng.random() < 0.35:
        return Feature.FOREST
    if terrain is Terrain.FOREST and temperature > 0.75 and rng.random() < 0.5:
        return Feature.JUNGLE
    if terrain is Terrain.GRASSLAND and moisture > 0.55 and rng.random() < 0.15:
        return Feature.MARSH
    if terrain is Terrain.DESERT and rng.random() < 0.06:
        return Feature.OASIS
    return None


def _place_resources(
    tiles: dict[Hex, Tile], rng: random.Random, min_spacing: int = 2
) -> dict[Hex, Tile]:
    placed: list[Hex] = []
    coords = sorted(tiles.keys(), key=lambda h: (h.q, h.r))
    rng.shuffle(coords)
    out = dict(tiles)
    for coord in coords:
        tile = out[coord]
        candidates = [
            res
            for res, info in RESOURCES.items()
            if tile.terrain in info.allowed_terrain
        ]
        if not candidates:
            continue
        if rng.random() > 0.18:
            continue
        if any(hex_distance(coord, other) < min_spacing for other in placed):
            continue
        resource: Resource = rng.choice(candidates)
        out[coord] = replace(tile, resource=resource)
        placed.append(coord)
    return out


def _carve_rivers(
    tiles: dict[Hex, Tile], rng: random.Random, river_sources: int = 4
) -> dict[Hex, Tile]:
    out = dict(tiles)
    high = sorted(
        (c for c, t in out.items() if t.elevation >= _HILL_LEVEL and t.terrain not in {Terrain.OCEAN, Terrain.COAST}),
        key=lambda c: out[c].elevation,
        reverse=True,
    )
    if not high:
        return out
    chosen = high[: max(river_sources, 1)]
    for source in chosen:
        current = source
        visited: set[Hex] = set()
        for _ in range(20):
            if current in visited:
                break
            visited.add(current)
            tile = out.get(current)
            if tile is None:
                break
            out[current] = replace(tile, river=True)
            if tile.terrain in {Terrain.OCEAN, Terrain.COAST}:
                break
            neighbors = [n for n in hex_neighbors(current) if n in out]
            if not neighbors:
                break
            current = min(neighbors, key=lambda n: out[n].elevation)
    return out


def _smooth_coasts(tiles: dict[Hex, Tile]) -> dict[Hex, Tile]:
    out = dict(tiles)
    for coord, tile in tiles.items():
        if tile.terrain in {Terrain.OCEAN, Terrain.COAST, Terrain.MOUNTAIN}:
            continue
        adjacent_ocean = sum(
            1
            for neighbor in hex_neighbors(coord)
            if tiles.get(neighbor) is not None
            and tiles[neighbor].terrain in {Terrain.OCEAN, Terrain.COAST}
        )
        if adjacent_ocean >= 3 and tile.elevation < _HILL_LEVEL:
            out[coord] = replace(tile, terrain=Terrain.COAST, feature=None)
    return out


def generate_map(radius: int, seed: int = 0) -> GameMap:
    if radius < 0:
        raise ValueError("radius must be non-negative")

    rng = random.Random(seed)
    continent_gen = OpenSimplex(seed=seed)
    elev_gen = OpenSimplex(seed=seed + 101)
    ridge_gen = OpenSimplex(seed=seed + 211)
    moist_gen = OpenSimplex(seed=seed + 1_000_003)
    temp_gen = OpenSimplex(seed=seed + 2_000_003)

    coords = hex_range(Hex(0, 0), radius)
    tiles: dict[Hex, Tile] = {}

    for coord in coords:
        on_edge = max(abs(coord.q), abs(coord.r)) == radius
        if on_edge:
            tiles[coord] = Tile(
                coord=coord,
                terrain=Terrain.OCEAN,
                elevation=-1.0,
                moisture=0.0,
                temperature=0.0,
            )
            continue

        elevation = _continent_elevation(
            continent_gen, elev_gen, ridge_gen, coord, radius
        )

        latitude = abs(coord.r) / max(radius, 1)
        temperature_noise = _noise(temp_gen, coord.q, coord.r, _TEMPERATURE_FREQ)
        temperature = max(
            0.0,
            min(
                1.0,
                1.0
                - latitude * 0.88
                - max(0.0, elevation) * 0.24
                + temperature_noise * 0.08,
            ),
        )

        moisture = _noise(moist_gen, coord.q, coord.r, _MOISTURE_FREQ)

        base = _base_terrain_from_elevation(elevation, temperature)
        terrain = _refine_with_moisture(base, moisture, temperature)

        feature = _pick_feature(terrain, moisture, temperature, rng)

        tiles[coord] = Tile(
            coord=coord,
            terrain=terrain,
            elevation=elevation,
            moisture=moisture,
            temperature=temperature,
            feature=feature,
        )

    tiles = _smooth_coasts(tiles)
    tiles = _place_resources(tiles, rng)
    tiles = _carve_rivers(tiles, rng)

    return GameMap(radius=radius, tiles=tiles)
