"""Tests for the local_view serializer."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import (
    Civilization,
    GameState,
    Tile,
    Unit,
    UnitType,
    UNIT_STATS,
)
from app.engine.serialize import local_view
from app.engine.terrain import Terrain


def _state() -> GameState:
    game_map = generate_map(4, seed=7)
    tiles = dict(game_map.tiles)
    tiles[Hex(0, 0)] = Tile(coord=Hex(0, 0), terrain=Terrain.GRASSLAND)
    tiles[Hex(3, 0)] = Tile(coord=Hex(3, 0), terrain=Terrain.GRASSLAND)
    game_map = replace(game_map, tiles=tiles)
    civs = (
        Civilization(id=0, name="Rome", leader_name="Caesar", is_human=False, color="#f00"),
        Civilization(id=1, name="Egypt", leader_name="Cleo", is_human=False, color="#0f0"),
    )
    stats = UNIT_STATS[UnitType.SETTLER]
    units = (
        Unit(id=1, owner=0, type=UnitType.SETTLER, location=Hex(0, 0),
             health=stats.max_health, moves_remaining=stats.moves),
        Unit(id=2, owner=1, type=UnitType.SETTLER, location=Hex(3, 0),
             health=stats.max_health, moves_remaining=stats.moves),
    )
    return GameState(
        turn=3,
        map=game_map,
        civs=civs,
        cities=(),
        units=units,
        seed=7,
    )


@pytest.mark.unit
def test_local_view_is_json_serializable() -> None:
    view = local_view(_state(), civ_id=0)
    encoded = json.dumps(view)
    assert json.loads(encoded) == view


@pytest.mark.unit
def test_local_view_hides_enemy_units_outside_sight() -> None:
    view = local_view(_state(), civ_id=0)
    unit_owners = {u["owner"] for u in view["visible_units"]}
    # Enemy at (3,0) is 3 hexes away, settler sight is 2 — should not be visible.
    assert 1 not in unit_owners
    assert 0 in unit_owners


@pytest.mark.unit
def test_local_view_includes_own_civ_summary() -> None:
    view = local_view(_state(), civ_id=0)
    assert view["self"]["id"] == 0
    assert view["self"]["name"] == "Rome"
    assert "gold" in view["self"]


@pytest.mark.unit
def test_local_view_includes_visible_tiles_only() -> None:
    state = _state()
    view = local_view(state, civ_id=0)
    assert len(view["visible_tiles"]) > 0
    for tile in view["visible_tiles"]:
        assert "q" in tile and "r" in tile
        assert "terrain" in tile


@pytest.mark.unit
def test_local_view_turn_and_current_civ() -> None:
    view = local_view(_state(), civ_id=0)
    assert view["turn"] == 3
    assert view["current_civ_id"] == 0


@pytest.mark.unit
def test_local_view_deterministic_ordering() -> None:
    a = local_view(_state(), civ_id=0)
    b = local_view(_state(), civ_id=0)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


@pytest.mark.unit
def test_known_civs_excludes_unmet() -> None:
    view = local_view(_state(), civ_id=0)
    known_ids = {c["id"] for c in view["known_civs"]}
    # Civ 0 sees itself but hasn't met civ 1 yet.
    assert 0 in known_ids
    assert 1 not in known_ids
