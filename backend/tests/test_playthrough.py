"""Tests for the headless playthrough harness."""

from __future__ import annotations

import pytest

from app.api.actions import MoveAction
from app.engine.city_founding import found_city
from app.engine.executor import AttackUnit, FoundCityNear, Goal, MoveTo
from app.engine.hex import Hex, hex_neighbors
from app.engine.models import (
    City,
    Civilization,
    DiplomaticStance,
    GameMap,
    GameState,
    Tile,
    Unit,
    UnitType,
    UNIT_STATS,
)
from app.engine.playthrough import (
    PlaythroughResult,
    RandomGoalSource,
    ScriptedGoal,
    ScriptedGoalSource,
    apply_action,
    run_playthrough,
    _advance_civ,
)
from app.engine.starting_positions import MIN_START_DISTANCE
from app.engine.terrain import Terrain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flat_map(radius: int = 4) -> GameMap:
    """All-grassland map with ocean border."""
    from app.engine.hex import hex_range

    tiles: dict[Hex, Tile] = {}
    for coord in hex_range(Hex(0, 0), radius):
        on_edge = max(abs(coord.q), abs(coord.r)) == radius
        tiles[coord] = Tile(
            coord=coord,
            terrain=Terrain.OCEAN if on_edge else Terrain.GRASSLAND,
        )
    return GameMap(radius=radius, tiles=tiles)


def _two_civ_state(
    radius: int = 4,
    civ0_units: list[Unit] | None = None,
    civ1_units: list[Unit] | None = None,
) -> GameState:
    """Minimal two-civ state on a flat map."""
    gm = _flat_map(radius)
    civs = (
        Civilization(id=0, name="Alpha", leader_name="A", is_human=False, gold=50),
        Civilization(id=1, name="Beta", leader_name="B", is_human=False, gold=50),
    )
    settler_stats = UNIT_STATS[UnitType.SETTLER]
    warrior_stats = UNIT_STATS[UnitType.WARRIOR]
    units = []
    if civ0_units is not None:
        units.extend(civ0_units)
    else:
        units.append(Unit(
            id=1, owner=0, type=UnitType.SETTLER, location=Hex(-2, 0),
            health=settler_stats.max_health, moves_remaining=settler_stats.moves,
        ))
        units.append(Unit(
            id=2, owner=0, type=UnitType.WARRIOR, location=Hex(-1, 0),
            health=warrior_stats.max_health, moves_remaining=warrior_stats.moves,
        ))
    if civ1_units is not None:
        units.extend(civ1_units)
    else:
        units.append(Unit(
            id=3, owner=1, type=UnitType.SETTLER, location=Hex(2, 0),
            health=settler_stats.max_health, moves_remaining=settler_stats.moves,
        ))
        units.append(Unit(
            id=4, owner=1, type=UnitType.WARRIOR, location=Hex(1, 0),
            health=warrior_stats.max_health, moves_remaining=warrior_stats.moves,
        ))
    return GameState(turn=1, map=gm, civs=civs, cities=(), units=tuple(units))


# ---------------------------------------------------------------------------
# apply_action
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_apply_move_action():
    state = _two_civ_state()
    unit = state.units[1]  # warrior at (-1, 0)
    action = MoveAction(unit_id=unit.id, destination=Hex(0, 0))
    new_state = apply_action(state, action, civ_id=0)
    moved = next(u for u in new_state.units if u.id == unit.id)
    assert moved.location == Hex(0, 0)


# ---------------------------------------------------------------------------
# _advance_civ
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_advance_civ_cycles():
    state = _two_civ_state()
    assert state.current_civ_idx == 0
    s2 = _advance_civ(state)
    assert s2.current_civ_idx == 1
    # Next advance wraps and increments turn.
    s3 = _advance_civ(s2)
    assert s3.current_civ_idx == 0
    assert s3.turn == state.turn + 1


@pytest.mark.unit
def test_advance_civ_skips_eliminated():
    """If civ 1 has no units/cities it should be skipped."""
    state = _two_civ_state(civ1_units=[])
    s2 = _advance_civ(state)
    # Civ 1 is eliminated — should wrap back to civ 0 and advance turn.
    assert s2.current_civ_idx == 0
    assert s2.turn == state.turn + 1


# ---------------------------------------------------------------------------
# ScriptedGoalSource
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_scripted_source_returns_goals_for_correct_turn():
    script = [
        ScriptedGoal(turn=1, civ_id=0, goal=FoundCityNear(unit_id=1, target=Hex(-2, 0), name="Alpha-1")),
        ScriptedGoal(turn=2, civ_id=0, goal=MoveTo(unit_id=2, target=Hex(0, 0))),
    ]
    source = ScriptedGoalSource(script)
    source.turn = 1
    decisions_t1 = source.decide({}, civ_id=0)
    assert len(decisions_t1.goals) == 1
    assert isinstance(decisions_t1.goals[0], FoundCityNear)

    source.turn = 2
    decisions_t2 = source.decide({}, civ_id=0)
    assert len(decisions_t2.goals) == 1
    assert isinstance(decisions_t2.goals[0], MoveTo)

    # No goals for civ 1 at turn 1.
    source.turn = 1
    assert source.decide({}, civ_id=1).goals == ()


# ---------------------------------------------------------------------------
# RandomGoalSource
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_random_source_produces_goals():
    source = RandomGoalSource(seed=42)
    view = {
        "visible_units": [
            {"id": 1, "owner": 0, "type": "settler", "q": 0, "r": 0,
             "health": 10, "max_health": 10, "moves_remaining": 2,
             "attack": 0, "defense": 1, "sight": 2},
            {"id": 2, "owner": 0, "type": "warrior", "q": 1, "r": 0,
             "health": 20, "max_health": 20, "moves_remaining": 2,
             "attack": 4, "defense": 3, "sight": 2},
        ],
        "visible_tiles": [
            {"q": 0, "r": 0, "terrain": "grassland"},
            {"q": 1, "r": 0, "terrain": "grassland"},
            {"q": 2, "r": 0, "terrain": "grassland"},
        ],
    }
    decisions = source.decide(view, civ_id=0)
    assert len(decisions.goals) == 2
    assert isinstance(decisions.goals[0], FoundCityNear)
    assert isinstance(decisions.goals[1], MoveTo)


@pytest.mark.unit
def test_random_source_ignores_enemy_units():
    source = RandomGoalSource(seed=0)
    view = {
        "visible_units": [
            {"id": 5, "owner": 1, "type": "warrior", "q": 0, "r": 0,
             "health": 20, "max_health": 20, "moves_remaining": 2,
             "attack": 4, "defense": 3, "sight": 2},
        ],
        "visible_tiles": [],
    }
    decisions = source.decide(view, civ_id=0)
    assert decisions.goals == ()


# ---------------------------------------------------------------------------
# Full playthrough loop
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_scripted_playthrough_founds_city():
    """Settlers found cities on turn 1, then loop runs to max turns."""
    state = _two_civ_state()
    script = [
        ScriptedGoal(turn=1, civ_id=0, goal=FoundCityNear(unit_id=1, target=Hex(-2, 0), name="Alpha-1")),
        ScriptedGoal(turn=1, civ_id=1, goal=FoundCityNear(unit_id=3, target=Hex(2, 0), name="Beta-1")),
    ]
    source = ScriptedGoalSource(script)
    result = run_playthrough(state, source, max_turns=3)

    assert isinstance(result, PlaythroughResult)
    assert result.actions_applied >= 2  # At least the two city foundings.
    assert len(result.final_state.cities) == 2
    # Settlers consumed — units should be only the warriors.
    settlers_left = [u for u in result.final_state.units if u.type is UnitType.SETTLER]
    assert len(settlers_left) == 0


@pytest.mark.integration
def test_random_playthrough_completes():
    """A random playthrough should terminate within max_turns."""
    state = _two_civ_state()
    source = RandomGoalSource(seed=7)
    result = run_playthrough(state, source, max_turns=10)

    assert isinstance(result, PlaythroughResult)
    assert result.final_state.turn <= 11  # started at 1, max 10 turns
    assert result.actions_applied >= 0
    assert result.actions_rejected >= 0


@pytest.mark.integration
def test_playthrough_includes_feedback_and_calls_turn_observer():
    class FeedbackSource:
        def __init__(self) -> None:
            self.turn = 1
            self.feedback_seen: dict[int, list[str]] = {}

        def decide(self, view: dict, civ_id: int):
            if civ_id != 0:
                return type("DecisionsProxy", (), {"goals": (), "diplomacy": (), "directives": ()})()
            feedback = view.get("last_turn_feedback", [])
            self.feedback_seen[self.turn] = list(feedback)
            if self.turn == 1:
                return type(
                    "DecisionsProxy",
                    (),
                    {
                        "goals": (MoveTo(unit_id=2, target=Hex(-2, 0)),),
                        "diplomacy": (),
                        "directives": (),
                    },
                )()
            return type("DecisionsProxy", (), {"goals": (), "diplomacy": (), "directives": ()})()

    state = _two_civ_state()
    source = FeedbackSource()
    observed_turns: list[int] = []

    run_playthrough(
        state,
        {0: source, 1: RandomGoalSource(seed=1)},
        max_turns=2,
        turn_observer=lambda s: observed_turns.append(s.turn),
    )

    assert source.feedback_seen[1] == []
    assert any("occupied" in item for item in source.feedback_seen[2])
    assert observed_turns == [2, 3]


@pytest.mark.integration
def test_playthrough_rejects_found_city_goal_for_non_settler_and_feeds_back_reason():
    class BadFoundingSource:
        def __init__(self) -> None:
            self.turn = 1
            self.feedback_seen: dict[int, list[str]] = {}

        def decide(self, view: dict, civ_id: int):
            if civ_id != 0:
                return type("DecisionsProxy", (), {"goals": (), "diplomacy": (), "directives": ()})()
            self.feedback_seen[self.turn] = list(view.get("last_turn_feedback", []))
            if self.turn == 1:
                return type(
                    "DecisionsProxy",
                    (),
                    {
                        "goals": (
                            FoundCityNear(unit_id=1, target=Hex(-2, 0), name="Alpha-1"),
                        ),
                        "diplomacy": (),
                        "directives": (),
                    },
                )()
            if self.turn == 2:
                return type(
                    "DecisionsProxy",
                    (),
                    {
                        "goals": (
                            FoundCityNear(unit_id=2, target=Hex(-1, 0), name="Alpha-2"),
                        ),
                        "diplomacy": (),
                        "directives": (),
                    },
                )()
            return type("DecisionsProxy", (), {"goals": (), "diplomacy": (), "directives": ()})()

    state = _two_civ_state()
    source = BadFoundingSource()

    result = run_playthrough(
        state,
        {0: source, 1: RandomGoalSource(seed=1)},
        max_turns=3,
    )

    assert result.actions_rejected >= 1
    assert source.feedback_seen[1] == []
    assert any("not a settler" in item for item in source.feedback_seen[3])


@pytest.mark.integration
def test_playthrough_ends_on_domination():
    """If one civ eliminates the other, victory should trigger."""
    warrior_stats = UNIT_STATS[UnitType.WARRIOR]
    # Civ 0 has a warrior, civ 1 has nothing but a city.
    state = _two_civ_state(
        civ0_units=[
            Unit(id=1, owner=0, type=UnitType.WARRIOR, location=Hex(-1, 0),
                 health=warrior_stats.max_health, moves_remaining=warrior_stats.moves),
        ],
        civ1_units=[],
    )
    # Give civ 0 a city so it's alive, civ 1 has nothing → eliminated.
    from dataclasses import replace
    state = replace(state, cities=(
        City(id=1, owner=0, name="Capital", location=Hex(-2, 0)),
    ))

    source = RandomGoalSource(seed=0)
    result = run_playthrough(state, source, max_turns=5)

    assert result.victory is not None
    assert result.victory.winner_id == 0


@pytest.mark.integration
def test_playthrough_with_generated_map():
    """Run a playthrough on a procedurally generated map via game_factory."""
    from app.api.game_factory import new_game

    state = new_game(radius=5, seed=42, num_civs=2)
    source = RandomGoalSource(seed=99)
    result = run_playthrough(state, source, max_turns=15)

    assert isinstance(result, PlaythroughResult)
    # Should have done *something*.
    assert result.actions_applied + result.actions_rejected > 0


@pytest.mark.integration
def test_new_game_assigns_spread_out_starting_positions():
    from app.api.game_factory import new_game
    from app.engine.hex import hex_distance
    from app.engine.terrain import Terrain

    state = new_game(seed=42, num_civs=4, include_human=False)
    starts = [civ.starting_position for civ in state.civs]

    assert all(start is not None for start in starts)
    for i, start in enumerate(starts):
        assert start in state.map
        for other in starts[i + 1:]:
            assert hex_distance(start, other) >= MIN_START_DISTANCE
    for unit in state.units:
        terrain = state.map.tiles[unit.location].terrain
        assert terrain not in {Terrain.OCEAN, Terrain.COAST}
