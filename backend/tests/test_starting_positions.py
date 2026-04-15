"""Tests for starting position placement."""

from __future__ import annotations

import pytest

from app.engine.hex import hex_distance
from app.engine.map_generator import generate_map
from app.engine.starting_positions import MIN_START_DISTANCE, starting_positions
from app.engine.terrain import IMPASSABLE_TERRAIN, Terrain


@pytest.mark.unit
def test_returns_requested_count() -> None:
    game_map = generate_map(7, seed=11)
    starts = starting_positions(game_map, n=3)
    assert len(starts) == 3


@pytest.mark.unit
def test_all_on_passable_land() -> None:
    game_map = generate_map(7, seed=11)
    starts = starting_positions(game_map, n=4)
    for coord in starts:
        tile = game_map.tiles[coord]
        assert tile.terrain not in IMPASSABLE_TERRAIN
        assert tile.terrain not in {Terrain.OCEAN, Terrain.COAST}


@pytest.mark.unit
def test_min_distance_enforced() -> None:
    game_map = generate_map(8, seed=13)
    starts = starting_positions(game_map, n=4)
    for i, a in enumerate(starts):
        for b in starts[i + 1 :]:
            assert hex_distance(a, b) >= MIN_START_DISTANCE


@pytest.mark.unit
def test_deterministic_for_same_map() -> None:
    game_map = generate_map(6, seed=21)
    a = starting_positions(game_map, n=3)
    b = starting_positions(game_map, n=3)
    assert a == b


@pytest.mark.unit
def test_raises_when_impossible() -> None:
    game_map = generate_map(2, seed=0)
    with pytest.raises(ValueError):
        starting_positions(game_map, n=20)
