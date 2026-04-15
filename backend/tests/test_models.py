from app.engine.hex import Hex
from app.engine.models import (
    Civilization,
    GameState,
    Unit,
    UnitType,
    UNIT_STATS,
)
from app.engine.map_generator import generate_map


def _unit(uid: int, owner: int, loc: Hex = Hex(0, 0)) -> Unit:
    stats = UNIT_STATS[UnitType.WARRIOR]
    return Unit(
        id=uid,
        owner=owner,
        type=UnitType.WARRIOR,
        location=loc,
        health=stats.max_health,
        moves_remaining=stats.moves,
    )


def test_unit_with_location_is_immutable_copy():
    u = _unit(1, 0, Hex(0, 0))
    moved = u.with_location(Hex(1, -1))
    assert moved.location == Hex(1, -1)
    assert u.location == Hex(0, 0)
    assert moved is not u


def test_unit_with_moves_returns_new_instance():
    u = _unit(1, 0)
    drained = u.with_moves(0)
    assert drained.moves_remaining == 0
    assert u.moves_remaining == UNIT_STATS[UnitType.WARRIOR].moves


def test_unit_stats_lookup():
    u = _unit(1, 0)
    assert u.stats.attack == UNIT_STATS[UnitType.WARRIOR].attack


def test_game_state_filters_by_owner():
    game_map = generate_map(2, seed=0)
    civs = (
        Civilization(id=0, name="Alpha", leader_name="A", is_human=True),
        Civilization(id=1, name="Beta", leader_name="B", is_human=False),
    )
    units = (_unit(1, 0), _unit(2, 0), _unit(3, 1))
    state = GameState(turn=1, map=game_map, civs=civs, cities=(), units=units)
    assert len(state.units_for(0)) == 2
    assert len(state.units_for(1)) == 1
    assert state.cities_for(0) == ()
