"""Item 3 — unit healing rules and defensive terrain bonuses."""

from __future__ import annotations

from dataclasses import replace

from app.engine.borders import recompute_claims
from app.engine.combat import attack, _terrain_defense_multiplier
from app.engine.hex import Hex
from app.engine.models import (
    City,
    Civilization,
    DiplomaticStance,
    GameMap,
    GameState,
    Tile,
    Unit,
    UNIT_STATS,
    UnitType,
)
from app.engine.terrain import Feature, Terrain
from app.engine.turn_resolver import (
    HEAL_ENEMY_TERRITORY,
    HEAL_OWN_TERRITORY,
    HEAL_UNOWNED,
    end_turn,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flat_map(radius: int = 4, terrain: Terrain = Terrain.GRASSLAND) -> GameMap:
    tiles: dict[Hex, Tile] = {}
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            coord = Hex(q, r)
            tiles[coord] = Tile(coord=coord, terrain=terrain)
    return GameMap(radius=radius, tiles=tiles)


def _unit(uid: int, owner: int, loc: Hex, health: int | None = None, utype: UnitType = UnitType.WARRIOR) -> Unit:
    stats = UNIT_STATS[utype]
    return Unit(
        id=uid,
        owner=owner,
        type=utype,
        location=loc,
        health=health if health is not None else stats.max_health,
        moves_remaining=stats.moves,
    )


def _civs(*ids: int) -> tuple[Civilization, ...]:
    return tuple(
        Civilization(id=i, name=f"C{i}", leader_name=f"L{i}", is_human=(i == 0), gold=20)
        for i in ids
    )


def _state(
    *,
    cities=(),
    units=(),
    terrain: Terrain = Terrain.GRASSLAND,
    radius: int = 4,
    at_war: bool = True,
) -> GameState:
    diplomacy = {(0, 1): DiplomaticStance.WAR} if at_war else {}
    state = GameState(
        turn=1,
        map=_flat_map(radius, terrain),
        civs=_civs(0, 1),
        cities=tuple(cities),
        units=tuple(units),
        diplomacy=diplomacy,
    )
    return recompute_claims(state)


def _set_tile(state: GameState, coord: Hex, **kwargs) -> GameState:
    tiles = dict(state.map.tiles)
    base = tiles[coord]
    tiles[coord] = replace(base, **kwargs)
    return replace(state, map=GameMap(radius=state.map.radius, tiles=tiles))


# ---------------------------------------------------------------------------
# Healing
# ---------------------------------------------------------------------------

def test_heal_in_own_territory_uses_high_rate():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    wounded = _unit(7, 0, Hex(1, 0), health=10)
    state = _state(cities=(city,), units=(wounded,))
    new_state = end_turn(state)
    healed = new_state.units[0]
    assert healed.health == 10 + HEAL_OWN_TERRITORY


def test_heal_in_unowned_territory_uses_medium_rate():
    wounded = _unit(7, 0, Hex(0, 0), health=10)
    state = _state(units=(wounded,))  # no city → no tile_owner entries
    new_state = end_turn(state)
    healed = new_state.units[0]
    assert healed.health == 10 + HEAL_UNOWNED


def test_heal_in_enemy_territory_uses_low_rate():
    enemy_city = City(id=1, owner=1, name="Theirs", location=Hex(0, 0))
    wounded = _unit(7, 0, Hex(1, 0), health=10)
    state = _state(cities=(enemy_city,), units=(wounded,))
    new_state = end_turn(state)
    healed = new_state.units[0]
    assert healed.health == 10 + HEAL_ENEMY_TERRITORY


def test_acted_unit_does_not_heal_that_turn():
    wounded = replace(_unit(7, 0, Hex(0, 0), health=10), acted_this_turn=True)
    state = _state(units=(wounded,))
    new_state = end_turn(state)
    # The unit healed nothing this turn — flag is reset for next turn.
    assert new_state.units[0].health == 10
    assert new_state.units[0].acted_this_turn is False


def test_heal_caps_at_max_health():
    stats = UNIT_STATS[UnitType.WARRIOR]
    wounded = _unit(7, 0, Hex(0, 0), health=stats.max_health - 1)
    state = _state(units=(wounded,))
    new_state = end_turn(state)
    assert new_state.units[0].health == stats.max_health


def test_acted_flag_reset_after_end_turn():
    moved = replace(_unit(7, 0, Hex(0, 0)), acted_this_turn=True)
    state = _state(units=(moved,))
    new_state = end_turn(state)
    assert new_state.units[0].acted_this_turn is False
    assert new_state.units[0].moves_remaining == UNIT_STATS[UnitType.WARRIOR].moves


# ---------------------------------------------------------------------------
# Terrain defense
# ---------------------------------------------------------------------------

def test_terrain_multiplier_plain_is_one():
    defender = _unit(2, 1, Hex(0, 0))
    state = _state(units=(defender,))
    assert _terrain_defense_multiplier(state, defender) == 1.0


def test_terrain_multiplier_forest_is_1_25():
    defender = _unit(2, 1, Hex(0, 0))
    state = _state(units=(defender,))
    state = _set_tile(state, Hex(0, 0), feature=Feature.FOREST)
    assert _terrain_defense_multiplier(state, defender) == 1.25


def test_terrain_multiplier_stacks_but_caps_at_1_6():
    defender = _unit(2, 1, Hex(0, 0))
    state = _state(units=(defender,))
    state = _set_tile(state, Hex(0, 0), terrain=Terrain.HILLS, feature=Feature.FOREST, river=True)
    # 1.25 * 1.25 * 1.25 = 1.953125 → clamped to 1.6.
    assert _terrain_defense_multiplier(state, defender) == 1.6


def test_forest_defender_takes_less_damage_than_open():
    attacker = _unit(1, 0, Hex(0, 0))
    defender_open = _unit(2, 1, Hex(1, 0))
    state_open = _state(units=(attacker, defender_open))
    after_open = attack(state_open, attacker.id, defender_open.id)
    def_after_open = next(u for u in after_open.units if u.id == 2)

    # Same scenario, defender is on a forest tile.
    state_forest = _state(units=(attacker, defender_open))
    state_forest = _set_tile(state_forest, Hex(1, 0), feature=Feature.FOREST)
    after_forest = attack(state_forest, attacker.id, defender_open.id)
    def_after_forest = next(u for u in after_forest.units if u.id == 2)

    assert def_after_forest.health > def_after_open.health


def test_combat_marks_acted_on_both_sides():
    attacker = _unit(1, 0, Hex(0, 0))
    defender = _unit(2, 1, Hex(1, 0))
    state = _state(units=(attacker, defender))
    after = attack(state, attacker.id, defender.id)
    a = next(u for u in after.units if u.id == 1)
    d = next((u for u in after.units if u.id == 2), None)
    assert a.acted_this_turn is True
    # Defender may have died; if alive, also flagged.
    if d is not None:
        assert d.acted_this_turn is True


def test_acted_attacker_does_not_heal_in_own_territory():
    city = City(id=1, owner=0, name="Home", location=Hex(0, 0))
    attacker = _unit(1, 0, Hex(0, 0), health=10)
    defender = _unit(2, 1, Hex(1, 0))
    state = _state(cities=(city,), units=(attacker, defender))
    after_attack = attack(state, attacker.id, defender.id)
    post_combat = next(u for u in after_attack.units if u.id == 1)
    after_turn = end_turn(after_attack)
    new_attacker = next(u for u in after_turn.units if u.id == 1)
    # Healed 0 this turn because acted_this_turn was True at end_turn.
    assert new_attacker.health == post_combat.health
