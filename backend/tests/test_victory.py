from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import (
    City,
    Civilization,
    GameState,
    Unit,
    UnitType,
    UNIT_STATS,
)
from app.engine.victory import (
    SCORE_THRESHOLD,
    VictoryKind,
    check_victory,
    civ_score,
    is_eliminated,
)


def _civ(civ_id: int, known: frozenset[str] = frozenset()) -> Civilization:
    return Civilization(
        id=civ_id,
        name=f"Civ{civ_id}",
        leader_name="L",
        is_human=False,
        known_techs=known,
    )


def _unit(uid: int, owner: int, loc: Hex = Hex(0, 0)) -> Unit:
    s = UNIT_STATS[UnitType.WARRIOR]
    return Unit(
        id=uid,
        owner=owner,
        type=UnitType.WARRIOR,
        location=loc,
        health=s.max_health,
        moves_remaining=s.moves,
    )


def _state(
    civs: tuple[Civilization, ...],
    cities: tuple[City, ...] = (),
    units: tuple[Unit, ...] = (),
) -> GameState:
    return GameState(
        turn=1,
        map=generate_map(2, seed=0),
        civs=civs,
        cities=cities,
        units=units,
    )


def test_is_eliminated_no_cities_no_units():
    state = _state((_civ(0),))
    assert is_eliminated(state, state.civs[0])


def test_not_eliminated_with_unit_only():
    units = (_unit(1, 0),)
    state = _state((_civ(0),), units=units)
    assert not is_eliminated(state, state.civs[0])


def test_domination_when_only_one_civ_remains():
    civs = (_civ(0), _civ(1))
    cities = (City(id=1, owner=0, name="A", location=Hex(0, 0)),)
    state = _state(civs, cities=cities)
    result = check_victory(state)
    assert result is not None
    assert result.kind == VictoryKind.DOMINATION
    assert result.winner_id == 0


def test_no_victory_when_multiple_civs_alive():
    civs = (_civ(0), _civ(1))
    cities = (
        City(id=1, owner=0, name="A", location=Hex(0, 0)),
        City(id=2, owner=1, name="B", location=Hex(1, 0)),
    )
    state = _state(civs, cities=cities)
    assert check_victory(state) is None


def test_civ_score_combines_cities_population_and_techs():
    civ = _civ(0, known=frozenset({"agriculture", "pottery"}))
    cities = (
        City(id=1, owner=0, name="A", location=Hex(0, 0), population=3),
        City(id=2, owner=0, name="B", location=Hex(1, 0), population=2),
    )
    state = _state((civ,), cities=cities)
    # 2 cities * 10 + 5 pop * 2 + 2 techs * 3 = 20 + 10 + 6 = 36
    assert civ_score(state, state.civs[0]) == 36


def test_score_victory_triggers_at_threshold():
    # Rig a civ with enough cities to cross SCORE_THRESHOLD.
    cities_needed = SCORE_THRESHOLD // 10 + 1
    cities = tuple(
        City(id=i + 1, owner=0, name=f"C{i}", location=Hex(i, 0))
        for i in range(cities_needed)
    )
    civs = (_civ(0), _civ(1))
    # civ 1 alive so domination doesn't pre-empt score.
    state = _state(civs, cities=cities, units=(_unit(99, 1, Hex(-1, 0)),))
    result = check_victory(state)
    assert result is not None
    assert result.kind == VictoryKind.SCORE
    assert result.winner_id == 0
