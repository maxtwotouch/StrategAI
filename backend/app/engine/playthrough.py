"""Headless playthrough harness.

Wires the full game loop: goal sources emit goals → executor turns them into
primitive actions → validator checks legality → engine applies valid actions →
turn advances → victory checked.  No UI, no network — pure deterministic
simulation that can be driven by any GoalSource (random, scripted, LLM).
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, replace
from typing import Callable, Protocol

from app.api.actions import (
    Action,
    AttackAction,
    EndTurnAction,
    FoundCityAction,
    MoveAction,
    ValidationError,
    ValidationOk,
    validate,
)
from app.engine.city_founding import found_city
from app.engine.combat import attack
from app.engine.diplomacy import (
    DiplomacyError,
    DiplomaticAction,
    apply_diplomatic_action,
)
from app.engine.executor import (
    AttackUnit,
    FoundCityNear,
    Goal,
    MoveTo,
    execute_goal,
)
from app.engine.hex import Hex, hex_neighbors
from app.engine.models import GameState, UnitType
from app.engine.movement import move_unit
from app.engine.serialize import local_view
from app.engine.terrain import is_passable
from app.engine.turn_resolver import end_turn
from app.engine.victory import VictoryResult, check_victory, is_eliminated

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GoalSource protocol
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Decisions:
    """A civ's intent for a single turn: unit goals + diplomatic actions."""
    goals: tuple[Goal, ...] = ()
    diplomacy: tuple[DiplomaticAction, ...] = ()


class GoalSource(Protocol):
    """Produces decisions for a civilization given its local view."""

    def decide(self, view: dict, civ_id: int) -> Decisions: ...


def _describe_goal(goal: Goal) -> str:
    if isinstance(goal, MoveTo):
        return f"MoveTo unit={goal.unit_id} target=({goal.target.q},{goal.target.r})"
    if isinstance(goal, FoundCityNear):
        return (
            f"FoundCityNear unit={goal.unit_id} "
            f"target=({goal.target.q},{goal.target.r}) name={goal.name!r}"
        )
    if isinstance(goal, AttackUnit):
        return f"AttackUnit attacker={goal.attacker_id} target={goal.target_id}"
    return repr(goal)


def _describe_diplomatic_action(action: DiplomaticAction) -> str:
    if hasattr(action, "kind") and hasattr(action, "to_civ_id"):
        text = getattr(action, "text", "")
        return (
            f"{type(action).__name__} to={action.to_civ_id} "
            f"kind={action.kind.value} text={text!r}"
        )
    if hasattr(action, "target_civ_id") and hasattr(action, "stance"):
        return (
            f"{type(action).__name__} target={action.target_civ_id} "
            f"stance={action.stance.value}"
        )
    return repr(action)


def _goal_rejection_reason(state: GameState, civ_id: int, goal: Goal) -> str | None:
    def unit_by_id(unit_id: int):
        return next((unit for unit in state.units if unit.id == unit_id), None)

    if isinstance(goal, MoveTo):
        unit = unit_by_id(goal.unit_id)
        if unit is None:
            return f"unit {goal.unit_id} does not exist"
        if unit.owner != civ_id:
            return f"unit {goal.unit_id} is not owned by civ {civ_id}"
        if unit.location == goal.target:
            return f"unit {goal.unit_id} is already at ({goal.target.q},{goal.target.r})"
        if goal.target not in state.map:
            return f"target ({goal.target.q},{goal.target.r}) is outside the map"
        tile = state.map.get(goal.target)
        if tile is None or not is_passable(tile.terrain):
            return f"target ({goal.target.q},{goal.target.r}) is impassable"
        if any(
            other.location == goal.target and other.id != goal.unit_id
            for other in state.units
        ):
            return f"target ({goal.target.q},{goal.target.r}) is occupied"
        return "no path or no movement available this turn"

    if isinstance(goal, FoundCityNear):
        unit = unit_by_id(goal.unit_id)
        if unit is None:
            return f"unit {goal.unit_id} does not exist"
        if unit.owner != civ_id:
            return f"unit {goal.unit_id} is not owned by civ {civ_id}"
        if unit.type is not UnitType.SETTLER:
            return f"unit {goal.unit_id} is a {unit.type.value}, not a settler"
        if goal.target not in state.map:
            return f"target ({goal.target.q},{goal.target.r}) is outside the map"
        tile = state.map.get(goal.target)
        if tile is None or not is_passable(tile.terrain):
            return f"target ({goal.target.q},{goal.target.r}) is impassable"
        if any(
            other.location == goal.target and other.id != goal.unit_id
            for other in state.units
        ):
            return f"target ({goal.target.q},{goal.target.r}) is occupied"
        if any(city.location == goal.target for city in state.cities):
            return f"target ({goal.target.q},{goal.target.r}) already has a city"
        return "no path or city cannot be founded there this turn"

    if isinstance(goal, AttackUnit):
        attacker = unit_by_id(goal.attacker_id)
        target = unit_by_id(goal.target_id)
        if attacker is None:
            return f"attacker unit {goal.attacker_id} does not exist"
        if attacker.owner != civ_id:
            return f"attacker unit {goal.attacker_id} is not owned by civ {civ_id}"
        if target is None:
            return f"target unit {goal.target_id} does not exist"
        if target.owner == civ_id:
            return f"target unit {goal.target_id} is friendly"
        return "target is unreachable or attack is not legal this turn"

    return "goal could not be executed"


# ---------------------------------------------------------------------------
# Random goal source — useful for smoke-testing the loop
# ---------------------------------------------------------------------------

class RandomGoalSource:
    """Picks random legal-ish goals from the civ's visible units. No diplomacy."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)

    def decide(self, view: dict, civ_id: int) -> Decisions:
        goals: list[Goal] = []
        for u in view.get("visible_units", []):
            if u["owner"] != civ_id:
                continue
            unit_id = u["id"]
            loc = Hex(u["q"], u["r"])
            utype = u["type"]

            if utype == "settler":
                goals.append(FoundCityNear(
                    unit_id=unit_id,
                    target=loc,
                    name=f"City-{unit_id}-{self._rng.randint(0, 999)}",
                ))
            elif utype in ("warrior", "scout"):
                tiles = view.get("visible_tiles", [])
                if tiles:
                    target_tile = self._rng.choice(tiles)
                    target = Hex(target_tile["q"], target_tile["r"])
                    goals.append(MoveTo(unit_id=unit_id, target=target))
        return Decisions(goals=tuple(goals))


# ---------------------------------------------------------------------------
# Scripted goal source — deterministic scenarios for integration tests
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ScriptedGoal:
    """A goal bound to a specific turn and civ."""
    turn: int
    civ_id: int
    goal: Goal


@dataclass(frozen=True, slots=True)
class ScriptedDiplomacy:
    """A diplomatic action bound to a specific turn and civ."""
    turn: int
    civ_id: int
    action: DiplomaticAction


class ScriptedGoalSource:
    """Replays a fixed sequence of goals + diplomacy keyed by (turn, civ_id)."""

    def __init__(
        self,
        script: list[ScriptedGoal],
        diplomacy_script: list[ScriptedDiplomacy] | None = None,
    ) -> None:
        self._goals_by_key: dict[tuple[int, int], list[Goal]] = {}
        for entry in script:
            self._goals_by_key.setdefault((entry.turn, entry.civ_id), []).append(entry.goal)
        self._dipl_by_key: dict[tuple[int, int], list[DiplomaticAction]] = {}
        for entry in (diplomacy_script or []):
            self._dipl_by_key.setdefault((entry.turn, entry.civ_id), []).append(entry.action)
        self._turn = 1

    @property
    def turn(self) -> int:
        return self._turn

    @turn.setter
    def turn(self, value: int) -> None:
        self._turn = value

    def decide(self, view: dict, civ_id: int) -> Decisions:
        return Decisions(
            goals=tuple(self._goals_by_key.get((self._turn, civ_id), [])),
            diplomacy=tuple(self._dipl_by_key.get((self._turn, civ_id), [])),
        )


# ---------------------------------------------------------------------------
# Action applier — dispatches validated actions to engine modules
# ---------------------------------------------------------------------------

def apply_action(state: GameState, action: Action, civ_id: int) -> GameState:
    """Apply a single validated action to the game state."""
    if isinstance(action, MoveAction):
        return move_unit(state, action.unit_id, action.destination)
    if isinstance(action, FoundCityAction):
        return found_city(state, action.unit_id, action.name)
    if isinstance(action, AttackAction):
        return attack(state, action.attacker_id, action.target_id)
    if isinstance(action, EndTurnAction):
        return state  # Handled by the loop's turn-advance step.
    return state


# ---------------------------------------------------------------------------
# Turn stepping
# ---------------------------------------------------------------------------

def _advance_civ(state: GameState) -> GameState:
    """Move to the next alive civilization, or wrap and advance the turn."""
    n = len(state.civs)
    if n == 0:
        return state

    next_idx = (state.current_civ_idx + 1) % n
    if next_idx <= state.current_civ_idx:
        # Wrapped around — all civs have played. Advance the turn.
        state = end_turn(state)
        next_idx = 0

    # Skip eliminated civs.
    for _ in range(n):
        civ = state.civs[next_idx]
        if not is_eliminated(state, civ):
            return replace(state, current_civ_idx=next_idx)
        next_idx = (next_idx + 1) % n
        if next_idx == 0:
            state = end_turn(state)

    return replace(state, current_civ_idx=0)


# ---------------------------------------------------------------------------
# Playthrough result
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PlaythroughResult:
    final_state: GameState
    victory: VictoryResult | None
    turns_played: int
    actions_applied: int
    actions_rejected: int


Observer = Callable[[GameState], None]


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_playthrough(
    initial_state: GameState,
    goal_source: GoalSource | dict[int, GoalSource],
    max_turns: int = 50,
    turn_observer: Observer | None = None,
) -> PlaythroughResult:
    """Execute a headless game from *initial_state* until victory or turn cap.

    *goal_source* may be a single source applied to every civ, or a dict
    mapping `civ_id -> GoalSource` so different civs use different policies
    (e.g. one human, three LLMs).
    """
    state = initial_state
    applied = 0
    rejected = 0
    goal_sources = goal_source
    feedback_by_civ: dict[int, list[str]] = {}

    while state.turn <= max_turns:
        victory = check_victory(state)
        if victory is not None:
            logger.info("Victory: %s by civ %d on turn %d",
                        victory.kind.value, victory.winner_id, state.turn)
            return PlaythroughResult(
                final_state=state,
                victory=victory,
                turns_played=state.turn - initial_state.turn,
                actions_applied=applied,
                actions_rejected=rejected,
            )

        civ = state.current_civ()
        civ_id = civ.id
        source = _resolve_source(goal_sources, civ_id)

        logger.info(
            "Turn %d civ %d (%s of %s): %d cities, %d units",
            state.turn,
            civ_id,
            civ.leader_name,
            civ.name,
            len(state.cities_for(civ_id)),
            len(state.units_for(civ_id)),
        )

        if is_eliminated(state, civ):
            state = _advance_civ(state)
            continue

        # Sync turn for scripted sources.
        if hasattr(source, "turn"):
            source.turn = state.turn  # type: ignore[attr-defined]

        # Bind live state for sources that need it (intent resolvers, etc.).
        if hasattr(source, "bind_state"):
            source.bind_state(state)  # type: ignore[attr-defined]

        view = local_view(state, civ_id)
        if feedback_by_civ.get(civ_id):
            view["last_turn_feedback"] = list(feedback_by_civ[civ_id])
        decisions = source.decide(view, civ_id)
        feedback_for_civ: list[str] = []
        logger.info(
            "Turn %d civ %d decided on %d goals and %d diplomatic actions",
            state.turn,
            civ_id,
            len(decisions.goals),
            len(decisions.diplomacy),
        )
        for goal in decisions.goals:
            logger.info("  goal: %s", _describe_goal(goal))
        for dipl_action in decisions.diplomacy:
            logger.info("  diplomacy: %s", _describe_diplomatic_action(dipl_action))

        # Diplomatic actions first — they may legalize/illegalize subsequent
        # combat actions in the same turn (e.g. a fresh war declaration).
        for dipl_action in decisions.diplomacy:
            try:
                state = apply_diplomatic_action(state, civ_id, dipl_action)
                applied += 1
                logger.info("  applied diplomacy: %s", _describe_diplomatic_action(dipl_action))
            except DiplomacyError as e:
                rejected += 1
                feedback_for_civ.append(
                    f"Diplomatic action rejected: {_describe_diplomatic_action(dipl_action)} -- {e}"
                )
                logger.warning(
                    "  rejected diplomacy: %s -- %s",
                    _describe_diplomatic_action(dipl_action),
                    e,
                )

        for goal in decisions.goals:
            actions = execute_goal(state, civ_id, goal)
            logger.info("  expanded %s into %d actions", _describe_goal(goal), len(actions))
            if not actions:
                reason = _goal_rejection_reason(state, civ_id, goal)
                if reason is not None:
                    rejected += 1
                    feedback_for_civ.append(
                        f"Goal rejected: {_describe_goal(goal)} -- {reason}"
                    )
                    logger.warning("  rejected goal: %s -- %s", _describe_goal(goal), reason)
            for action in actions:
                result = validate(action, state, civ_id)
                if isinstance(result, ValidationOk):
                    state = apply_action(state, action, civ_id)
                    applied += 1
                    logger.info("  applied action: %s", action)
                elif isinstance(result, ValidationError):
                    rejected += 1
                    feedback_for_civ.append(
                        f"Action rejected: {action} -- {result.reason}"
                    )
                    logger.warning("  rejected action: %s -- %s", action, result.reason)

        feedback_by_civ[civ_id] = feedback_for_civ[-8:]
        prev_turn = state.turn
        state = _advance_civ(state)
        if turn_observer is not None and state.turn != prev_turn:
            turn_observer(state)

    return PlaythroughResult(
        final_state=state,
        victory=None,
        turns_played=state.turn - initial_state.turn,
        actions_applied=applied,
        actions_rejected=rejected,
    )


def _resolve_source(
    goal_sources: GoalSource | dict[int, GoalSource], civ_id: int
) -> GoalSource:
    """Per-civ source if a dict was provided, else the single shared source."""
    if isinstance(goal_sources, dict):
        if civ_id not in goal_sources:
            raise KeyError(f"no goal source registered for civ {civ_id}")
        return goal_sources[civ_id]
    return goal_sources
