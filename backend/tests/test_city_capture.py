from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import City, Civilization, GameState, Unit, UnitType, UNIT_STATS
from app.engine.movement import MoveError, move_unit


def _unit(uid: int, owner: int, loc: Hex) -> Unit:
    stats = UNIT_STATS[UnitType.WARRIOR]
    return Unit(
        id=uid,
        owner=owner,
        type=UnitType.WARRIOR,
        location=loc,
        health=stats.max_health,
        moves_remaining=stats.moves,
    )


def _state(city: City, units: tuple[Unit, ...]) -> GameState:
    civs = (
        Civilization(id=0, name="A", leader_name="L", is_human=True),
        Civilization(id=1, name="B", leader_name="M", is_human=False),
    )
    return GameState(
        turn=1,
        map=generate_map(3, seed=0),
        civs=civs,
        cities=(city,),
        units=units,
    )


def test_cannot_enter_enemy_city_until_broken():
    city = City(id=1, owner=1, name="Enemy", location=Hex(1, 0), health=5, is_capital=True)
    attacker = _unit(7, 0, Hex(0, 0))
    state = _state(city, (attacker,))
    try:
        move_unit(state, attacker.id, Hex(1, 0))
    except MoveError as exc:
        assert "0 health" in str(exc)
    else:
        raise AssertionError("expected move into defended city to fail")


def test_move_into_broken_city_captures_it():
    city = City(id=1, owner=1, name="Enemy", location=Hex(1, 0), health=0, is_capital=True)
    attacker = _unit(7, 0, Hex(0, 0))
    state = _state(city, (attacker,))
    new_state = move_unit(state, attacker.id, Hex(1, 0))
    captured = new_state.cities[0]
    moved = new_state.units[0]
    assert captured.owner == 0
    assert captured.health == captured.max_health
    assert captured.population == 1
    assert moved.location == Hex(1, 0)


def test_captured_capital_promotes_remaining_city():
    capital = City(id=1, owner=1, name="Capital", location=Hex(1, 0), health=0, is_capital=True)
    backup = City(id=2, owner=1, name="Backup", location=Hex(2, 0), is_capital=False)
    attacker = _unit(7, 0, Hex(0, 0))
    civs = (
        Civilization(id=0, name="A", leader_name="L", is_human=True),
        Civilization(id=1, name="B", leader_name="M", is_human=False),
    )
    state = GameState(
        turn=1,
        map=generate_map(3, seed=0),
        civs=civs,
        cities=(capital, backup),
        units=(attacker,),
    )
    new_state = move_unit(state, attacker.id, Hex(1, 0))
    remaining = next(city for city in new_state.cities if city.id == 2)
    assert remaining.owner == 1
    assert remaining.is_capital
