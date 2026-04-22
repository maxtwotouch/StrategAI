from app.engine.hex import Hex, hex_range
from app.engine.map_generator import generate_map
from app.engine.terrain import Terrain

import pytest


def test_generate_map_tile_count_matches_hex_range():
    radius = 4
    game_map = generate_map(radius, seed=1)
    expected = len(hex_range(Hex(0, 0), radius))
    assert len(game_map.tiles) == expected


def test_generate_map_is_deterministic_for_seed():
    a = generate_map(3, seed=42)
    b = generate_map(3, seed=42)
    assert a.tiles == b.tiles


def test_different_seeds_produce_different_maps():
    a = generate_map(5, seed=1)
    b = generate_map(5, seed=2)
    assert a.tiles != b.tiles


def test_outer_ring_is_ocean():
    radius = 3
    game_map = generate_map(radius, seed=7)
    for coord, tile in game_map.tiles.items():
        on_edge = max(abs(coord.q), abs(coord.r)) == radius
        if on_edge:
            assert tile.terrain == Terrain.OCEAN


def test_center_tile_is_not_ocean():
    game_map = generate_map(2, seed=0)
    assert game_map.tiles[Hex(0, 0)].terrain != Terrain.OCEAN


def test_negative_radius_raises():
    with pytest.raises(ValueError):
        generate_map(-1)


def test_map_contains_membership():
    game_map = generate_map(2, seed=0)
    assert Hex(0, 0) in game_map
    assert Hex(99, 99) not in game_map
