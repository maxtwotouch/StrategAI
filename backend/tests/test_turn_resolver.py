from dataclasses import replace

from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import GameState, Unit, UnitType, UNIT_STATS
from app.engine.turn_resolver import end_turn


def _unit(uid: int, moves: int) -> Unit:
    stats = UNIT_STATS[UnitType.WARRIOR]
    return Unit(
        id=uid,
        owner=0,
        type=UnitType.WARRIOR,
        location=Hex(0, 0),
        health=stats.max_health,
        moves_remaining=moves,
    )


def _state(units: tuple[Unit, ...]) -> GameState:
    return GameState(
        turn=1,
        map=generate_map(2, seed=0),
        civs=(),
        cities=(),
        units=units,
    )


def test_end_turn_increments_turn_counter():
    state = _state(())
    new_state = end_turn(state)
    assert new_state.turn == state.turn + 1


def test_end_turn_resets_unit_moves_to_max():
    state = _state((_unit(1, moves=0), _unit(2, moves=1)))
    new_state = end_turn(state)
    expected = UNIT_STATS[UnitType.WARRIOR].moves
    assert all(u.moves_remaining == expected for u in new_state.units)


def test_end_turn_is_immutable():
    state = _state((_unit(1, moves=0),))
    new_state = end_turn(state)
    assert state.turn == 1
    assert state.units[0].moves_remaining == 0
    assert new_state is not state


def test_end_turn_preserves_unit_identity_and_location():
    original = _unit(7, moves=0)
    state = _state((original,))
    new_state = end_turn(state)
    assert new_state.units[0].id == 7
    assert new_state.units[0].location == original.location
