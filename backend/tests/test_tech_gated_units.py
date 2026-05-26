"""Item 4 — tech-gated unit types."""

from __future__ import annotations

import pytest

from app.engine.directives import DirectiveError, QueueProduction, apply_directive
from app.engine.combat import attack
from app.engine.hex import Hex
from app.engine.intents import Build
from app.engine.map_generator import generate_map
from app.engine.models import (
    BuildItem,
    City,
    Civilization,
    GameMap,
    GameState,
    Tile,
    UNIT_BUILD_COST,
    UNIT_STATS,
    Unit,
    UnitType,
)
from app.engine.operations import resolve_intent
from app.engine.serialize import local_view
from app.engine.terrain import Terrain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flat_map(radius: int = 3, terrain: Terrain = Terrain.GRASSLAND) -> GameMap:
    tiles: dict[Hex, Tile] = {}
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            coord = Hex(q, r)
            tiles[coord] = Tile(coord=coord, terrain=terrain)
    return GameMap(radius=radius, tiles=tiles)


def _civs(known: frozenset[str] = frozenset()) -> tuple[Civilization, ...]:
    return (
        Civilization(id=0, name="A", leader_name="L", is_human=False, known_techs=known),
        Civilization(id=1, name="B", leader_name="L", is_human=False),
    )


def _state(*, civ_known: frozenset[str] = frozenset(), cities=(), units=()) -> GameState:
    return GameState(
        turn=1,
        map=_flat_map(),
        civs=_civs(civ_known),
        cities=tuple(cities),
        units=tuple(units),
    )


def _unit(uid: int, owner: int, loc: Hex, utype: UnitType) -> Unit:
    stats = UNIT_STATS[utype]
    return Unit(
        id=uid, owner=owner, type=utype, location=loc,
        health=stats.max_health, moves_remaining=stats.moves,
    )


# ---------------------------------------------------------------------------
# Build-time gating
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_build_archer_without_archery_rejected():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(cities=(city,))
    with pytest.raises(DirectiveError, match="not unlocked"):
        apply_directive(
            state, 0,
            QueueProduction(city_id=1, item=BuildItem.unit(UnitType.ARCHER)),
        )


@pytest.mark.unit
def test_build_archer_after_archery_succeeds():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(civ_known=frozenset({"archery"}), cities=(city,))
    new_state = apply_directive(
        state, 0,
        QueueProduction(city_id=1, item=BuildItem.unit(UnitType.ARCHER)),
    )
    assert new_state.cities[0].production_queue == (BuildItem.unit(UnitType.ARCHER),)


@pytest.mark.unit
def test_build_horseman_requires_horseback_riding():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(cities=(city,))
    with pytest.raises(DirectiveError):
        apply_directive(
            state, 0,
            QueueProduction(city_id=1, item=BuildItem.unit(UnitType.HORSEMAN)),
        )


@pytest.mark.unit
def test_build_swordsman_requires_iron_working():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(cities=(city,))
    with pytest.raises(DirectiveError):
        apply_directive(
            state, 0,
            QueueProduction(city_id=1, item=BuildItem.unit(UnitType.SWORDSMAN)),
        )


# ---------------------------------------------------------------------------
# Stat sanity
# ---------------------------------------------------------------------------

def test_horseman_has_4_moves():
    assert UNIT_STATS[UnitType.HORSEMAN].moves == 4


def test_swordsman_outdamages_warrior():
    a_warrior = _unit(1, 0, Hex(0, 0), UnitType.WARRIOR)
    a_sword = _unit(2, 0, Hex(0, 0), UnitType.SWORDSMAN)
    defender = _unit(3, 1, Hex(1, 0), UnitType.WARRIOR)

    # Warrior vs warrior
    state_w = _state(units=(a_warrior, defender))
    after_w = attack(state_w, 1, 3)
    after_w_def = next(u for u in after_w.units if u.id == 3)

    # Swordsman vs warrior
    a_sword_real = _unit(1, 0, Hex(0, 0), UnitType.SWORDSMAN)
    state_s = _state(units=(a_sword_real, defender))
    after_s = attack(state_s, 1, 3)
    after_s_def = next((u for u in after_s.units if u.id == 3), None)

    # Swordsman either kills the defender or leaves it lower than warrior would.
    if after_s_def is None:
        assert after_w_def.health > 0
    else:
        assert after_s_def.health < after_w_def.health


# ---------------------------------------------------------------------------
# Operations layer drops invalid Build intents silently
# ---------------------------------------------------------------------------

def test_operations_drops_archer_intent_before_archery():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(cities=(city,))
    goals, dipl, dirs = resolve_intent(state, 0, Build(unit_type=UnitType.ARCHER))
    assert goals == [] and dipl == [] and dirs == []


def test_operations_queues_archer_after_archery():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(civ_known=frozenset({"archery"}), cities=(city,))
    goals, dipl, dirs = resolve_intent(state, 0, Build(unit_type=UnitType.ARCHER))
    assert len(dirs) == 1


# ---------------------------------------------------------------------------
# local_view exposes the available unit set
# ---------------------------------------------------------------------------

def test_local_view_lists_unlocked_units_only():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(cities=(city,))
    view = local_view(state, 0)
    available = set(view["available_units"])
    assert "warrior" in available
    assert "scout" in available
    assert "settler" in available
    assert "worker" in available
    assert "archer" not in available
    assert "horseman" not in available
    assert "swordsman" not in available


def test_local_view_lists_archer_after_archery():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    state = _state(civ_known=frozenset({"archery"}), cities=(city,))
    view = local_view(state, 0)
    assert "archer" in view["available_units"]


# ---------------------------------------------------------------------------
# Build costs are populated for new units
# ---------------------------------------------------------------------------

def test_build_costs_populated_for_new_units():
    assert UnitType.ARCHER in UNIT_BUILD_COST
    assert UnitType.HORSEMAN in UNIT_BUILD_COST
    assert UnitType.SWORDSMAN in UNIT_BUILD_COST
    assert UnitType.WORKER in UNIT_BUILD_COST
