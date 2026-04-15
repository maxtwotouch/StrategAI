"""Tests for the layered-noise map generator."""

from __future__ import annotations

import pytest

from app.engine.hex import Hex, hex_distance
from app.engine.map_generator import generate_map
from app.engine.terrain import RESOURCES, Resource, Terrain


@pytest.mark.unit
def test_map_contains_variety_of_terrain() -> None:
    game_map = generate_map(6, seed=1)
    kinds = {t.terrain for t in game_map.tiles.values()}
    # At least 4 distinct terrain types on a radius-6 map.
    assert len(kinds) >= 4


@pytest.mark.unit
def test_land_ratio_reasonable() -> None:
    game_map = generate_map(6, seed=3)
    total = len(game_map.tiles)
    land = sum(
        1
        for t in game_map.tiles.values()
        if t.terrain not in {Terrain.OCEAN, Terrain.COAST}
    )
    ratio = land / total
    assert 0.25 <= ratio <= 0.8


@pytest.mark.unit
def test_tiles_carry_climate_values() -> None:
    game_map = generate_map(4, seed=9)
    # At least one land tile has non-zero elevation/moisture.
    land_tiles = [t for t in game_map.tiles.values() if t.terrain != Terrain.OCEAN]
    assert any(abs(t.elevation) > 0 for t in land_tiles)
    assert any(abs(t.moisture) > 0 for t in land_tiles)


@pytest.mark.unit
def test_poles_are_colder_than_equator() -> None:
    game_map = generate_map(6, seed=2)
    equator = [t for t in game_map.tiles.values() if t.coord.r == 0]
    pole = [
        t
        for t in game_map.tiles.values()
        if abs(t.coord.r) == 6 and t.terrain != Terrain.OCEAN
    ]
    if pole:
        avg_eq = sum(t.temperature for t in equator) / len(equator)
        avg_pole = sum(t.temperature for t in pole) / len(pole)
        assert avg_eq > avg_pole


@pytest.mark.unit
def test_resources_respect_terrain_compatibility() -> None:
    game_map = generate_map(6, seed=5)
    for tile in game_map.tiles.values():
        if tile.resource is not None:
            assert tile.terrain in RESOURCES[tile.resource].allowed_terrain


@pytest.mark.unit
def test_resource_minimum_spacing() -> None:
    game_map = generate_map(6, seed=5)
    resource_coords = [c for c, t in game_map.tiles.items() if t.resource is not None]
    for i, a in enumerate(resource_coords):
        for b in resource_coords[i + 1 :]:
            assert hex_distance(a, b) >= 2


@pytest.mark.unit
def test_determinism_across_attributes() -> None:
    a = generate_map(5, seed=123)
    b = generate_map(5, seed=123)
    for coord, tile_a in a.tiles.items():
        tile_b = b.tiles[coord]
        assert tile_a == tile_b


@pytest.mark.unit
def test_has_some_rivers_on_large_map() -> None:
    game_map = generate_map(8, seed=4)
    river_count = sum(1 for t in game_map.tiles.values() if t.river)
    assert river_count > 0
