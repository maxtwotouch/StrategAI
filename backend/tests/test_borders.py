"""Tile ownership, border growth, and worker assignment."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.engine.borders import (
    CULTURE_RADIUS_2,
    CULTURE_RADIUS_3,
    auto_assign_workers,
    claimed_tiles,
    grow_borders,
    recompute_claims,
    working_yields,
)
from app.engine.city_founding import found_city
from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import (
    City,
    Civilization,
    GameMap,
    GameState,
    Tile,
    Unit,
    UNIT_STATS,
    UnitType,
)
from app.engine.movement import move_unit
from app.engine.terrain import Terrain
from app.engine.turn_resolver import end_turn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grassland_map(radius: int = 5) -> GameMap:
    """Uniform grassland map — eliminates terrain noise in yield tests."""
    tiles: dict[Hex, Tile] = {}
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            coord = Hex(q, r)
            tiles[coord] = Tile(coord=coord, terrain=Terrain.GRASSLAND)
    return GameMap(radius=radius, tiles=tiles)


def _settler(uid: int, owner: int, loc: Hex) -> Unit:
    stats = UNIT_STATS[UnitType.SETTLER]
    return Unit(
        id=uid,
        owner=owner,
        type=UnitType.SETTLER,
        location=loc,
        health=stats.max_health,
        moves_remaining=stats.moves,
    )


def _warrior(uid: int, owner: int, loc: Hex) -> Unit:
    stats = UNIT_STATS[UnitType.WARRIOR]
    return Unit(
        id=uid,
        owner=owner,
        type=UnitType.WARRIOR,
        location=loc,
        health=stats.max_health,
        moves_remaining=stats.moves,
    )


def _civs(*ids: int) -> tuple[Civilization, ...]:
    return tuple(
        Civilization(id=i, name=f"C{i}", leader_name=f"L{i}", is_human=(i == 0))
        for i in ids
    )


def _state(*, cities=(), units=(), civ_ids=(0, 1), radius: int = 5) -> GameState:
    return GameState(
        turn=1,
        map=_grassland_map(radius),
        civs=_civs(*civ_ids),
        cities=tuple(cities),
        units=tuple(units),
    )


# ---------------------------------------------------------------------------
# recompute_claims
# ---------------------------------------------------------------------------

def test_new_city_claims_its_full_3x3_ring():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0))
    state = _state(cities=(city,))
    state = recompute_claims(state)
    # border_radius=1 on a square grid → 3x3 around center = 9 tiles.
    owned = claimed_tiles(state, city)
    assert len(owned) == 9
    assert Hex(0, 0) in owned
    assert Hex(1, 1) in owned
    assert Hex(-1, -1) in owned


def test_contested_tile_goes_to_closer_city():
    # Two cities 4 apart with radius-2 borders.
    near = City(id=1, owner=0, name="Near", location=Hex(0, 0), border_radius=2)
    far = City(id=2, owner=1, name="Far", location=Hex(4, 0), border_radius=2)
    state = _state(cities=(near, far))
    state = recompute_claims(state)
    # (1,0) is distance 1 from near, 3 from far → near wins.
    assert state.tile_owner[Hex(1, 0)] == near.id
    # (3,0) is distance 3 from near (out of range), 1 from far → far wins.
    assert state.tile_owner[Hex(3, 0)] == far.id
    # (2,0) is distance 2 from both — tie → lower city_id (near) wins.
    assert state.tile_owner[Hex(2, 0)] == near.id


def test_lower_city_id_breaks_distance_ties():
    a = City(id=1, owner=0, name="A", location=Hex(0, 0), border_radius=1)
    b = City(id=2, owner=1, name="B", location=Hex(2, 0), border_radius=1)
    state = _state(cities=(a, b))
    state = recompute_claims(state)
    # Tile (1,0) is distance 1 from both → lower id wins.
    assert state.tile_owner[Hex(1, 0)] == a.id


# ---------------------------------------------------------------------------
# grow_borders
# ---------------------------------------------------------------------------

def test_culture_threshold_grows_radius():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0), culture_stored=CULTURE_RADIUS_2)
    state = _state(cities=(city,))
    state = recompute_claims(state)
    grown = grow_borders(state)
    assert grown.cities[0].border_radius == 2
    # New ring (Chebyshev 2) is now claimed: 5x5 = 25 tiles.
    owned = claimed_tiles(grown, grown.cities[0])
    assert len(owned) == 25


def test_radius_capped_at_three():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0), culture_stored=10_000)
    state = _state(cities=(city,))
    grown = grow_borders(state)
    assert grown.cities[0].border_radius == 3


def test_low_culture_does_not_grow_radius():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0), culture_stored=CULTURE_RADIUS_2 - 1)
    state = _state(cities=(city,))
    grown = grow_borders(state)
    assert grown.cities[0].border_radius == 1


# ---------------------------------------------------------------------------
# found_city integration
# ---------------------------------------------------------------------------

def test_found_city_populates_tile_owner_and_worked_tiles():
    settler = _settler(7, 0, Hex(0, 0))
    state = _state(units=(settler,))
    new_state = found_city(state, settler.id, "First")
    city = new_state.cities[0]
    # tile_owner has at least the city center mapped to it.
    assert new_state.tile_owner[Hex(0, 0)] == city.id
    # New city auto-works its center (population 1 means just center).
    assert city.worked_tiles == frozenset({Hex(0, 0)})


# ---------------------------------------------------------------------------
# auto_assign_workers + working_yields
# ---------------------------------------------------------------------------

def test_workers_picked_by_yield_score():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0), population=2, border_radius=1)
    state = _state(cities=(city,))
    # Replace one neighbor with a high-yield resource tile, another with marsh.
    from app.engine.terrain import Feature, Resource
    tiles = dict(state.map.tiles)
    tiles[Hex(1, 0)] = Tile(coord=Hex(1, 0), terrain=Terrain.GRASSLAND, resource=Resource.WHEAT)
    tiles[Hex(-1, 0)] = Tile(coord=Hex(-1, 0), terrain=Terrain.GRASSLAND, feature=Feature.MARSH)
    state = replace(state, map=GameMap(radius=state.map.radius, tiles=tiles))
    state = recompute_claims(state)
    state = auto_assign_workers(state)

    worked = state.cities[0].worked_tiles
    # pop=2 → center + 1 extra. Wheat tile beats marsh.
    assert Hex(0, 0) in worked
    assert Hex(1, 0) in worked
    assert Hex(-1, 0) not in worked


def test_yields_scale_with_population():
    # A pop=1 city should produce less than a pop=3 city on identical terrain
    # because the larger city works more tiles.
    small = City(id=1, owner=0, name="S", location=Hex(0, 0), population=1, border_radius=1)
    big = City(id=2, owner=1, name="B", location=Hex(10, 0), population=3, border_radius=1)
    state = _state(cities=(small, big), radius=15)
    state = recompute_claims(state)
    state = auto_assign_workers(state)

    small_y = working_yields(state, state.cities[0])
    big_y = working_yields(state, state.cities[1])
    assert big_y.food > small_y.food
    assert len(state.cities[1].worked_tiles) == 3
    assert len(state.cities[0].worked_tiles) == 1


def test_population_caps_worker_count():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0), population=5, border_radius=1)
    state = _state(cities=(city,))
    state = recompute_claims(state)
    state = auto_assign_workers(state)
    # 5 workers requested, 9 claimed tiles available → 5 worked.
    assert len(state.cities[0].worked_tiles) == 5


# ---------------------------------------------------------------------------
# Capture flips ownership
# ---------------------------------------------------------------------------

def test_capture_transfers_tile_ownership():
    # Set up: civ 1 has a city at (1,0) with 0 health (already softened).
    enemy_city = City(id=1, owner=1, name="Enemy", location=Hex(1, 0), health=0, is_capital=True)
    attacker = _warrior(7, 0, Hex(0, 0))
    state = _state(cities=(enemy_city,), units=(attacker,))
    state = recompute_claims(state)
    # Before capture, enemy claims its center tile.
    assert state.tile_owner[Hex(1, 0)] == enemy_city.id

    new_state = move_unit(state, attacker.id, Hex(1, 0))
    # After capture, the (same) city object now belongs to civ 0; tile_owner
    # entry persists but flows through the captured city which is now ours.
    captured = next(c for c in new_state.cities if c.id == enemy_city.id)
    assert captured.owner == 0
    assert new_state.tile_owner[Hex(1, 0)] == captured.id


# ---------------------------------------------------------------------------
# Integration: end_turn drives accumulation & growth
# ---------------------------------------------------------------------------

def test_end_turn_eventually_grows_borders():
    city = City(id=1, owner=0, name="A", location=Hex(0, 0))
    state = _state(cities=(city,))
    state = recompute_claims(state)
    for _ in range(CULTURE_RADIUS_2 + 1):
        state = end_turn(state)
    assert state.cities[0].border_radius >= 2
