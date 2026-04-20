"""Diplomatic messages and stance changes between civilizations.

Diplomacy is intentionally separate from goals.  Goals direct units; diplomatic
actions change relationships and exchange information.  Both can be issued by
a single source (LLM or human) per turn.

A `DiplomaticMessage` is an immutable, append-only record stored on
`GameState.messages`.  Stance changes mutate `GameState.diplomacy`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Union

from app.engine.fog_of_war import visible_tiles
from app.engine.models import DiplomaticStance, GameState


class MessageKind(str, Enum):
    """The semantic intent of a diplomatic message.

    The free-form `text` field still carries the actual content; the kind
    just lets the receiver (and the engine) reason about it categorically.
    """
    CHAT = "chat"
    THREAT = "threat"
    OFFER_PEACE = "offer_peace"
    DECLARE_WAR = "declare_war"
    PROPOSE_ALLIANCE = "propose_alliance"
    ACCEPT_ALLIANCE = "accept_alliance"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class DiplomaticMessage:
    from_civ_id: int
    to_civ_id: int
    turn: int
    kind: MessageKind
    text: str


# ---------------------------------------------------------------------------
# Diplomatic actions (issued by goal sources, applied by the engine)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SendMessage:
    to_civ_id: int
    kind: MessageKind
    text: str


@dataclass(frozen=True, slots=True)
class SetStance:
    target_civ_id: int
    stance: DiplomaticStance


DiplomaticAction = Union[SendMessage, SetStance]


class DiplomacyError(ValueError):
    """Raised when a diplomatic action is invalid."""


def met_civs(state: GameState, civ_id: int) -> set[int]:
    """Civilizations this civ has already encountered."""
    met_ids = {civ_id}
    visible = visible_tiles(state, civ_id)

    for unit in state.units:
        if unit.location in visible:
            met_ids.add(unit.owner)
    for city in state.cities:
        if city.location in visible:
            met_ids.add(city.owner)
    for message in state.messages:
        if message.from_civ_id == civ_id:
            met_ids.add(message.to_civ_id)
        if message.to_civ_id == civ_id:
            met_ids.add(message.from_civ_id)

    return met_ids


# ---------------------------------------------------------------------------
# Stance helpers
# ---------------------------------------------------------------------------

def _stance_key(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def set_stance(state: GameState, a: int, b: int, stance: DiplomaticStance) -> GameState:
    """Symmetric stance change between two civilizations."""
    if a == b:
        raise DiplomacyError("cannot change stance with self")
    new_dipl = dict(state.diplomacy)
    new_dipl[_stance_key(a, b)] = stance
    return replace(state, diplomacy=new_dipl)


# ---------------------------------------------------------------------------
# Apply a single diplomatic action
# ---------------------------------------------------------------------------

def apply_diplomatic_action(
    state: GameState, civ_id: int, action: DiplomaticAction
) -> GameState:
    """Apply a single diplomatic action.  Pure — returns new state."""
    if isinstance(action, SendMessage):
        if action.to_civ_id == civ_id:
            raise DiplomacyError("cannot send message to self")
        if not any(c.id == action.to_civ_id for c in state.civs):
            raise DiplomacyError(f"unknown recipient civ {action.to_civ_id}")
        if action.to_civ_id not in met_civs(state, civ_id):
            raise DiplomacyError(f"cannot message unmet civ {action.to_civ_id}")
        msg = DiplomaticMessage(
            from_civ_id=civ_id,
            to_civ_id=action.to_civ_id,
            turn=state.turn,
            kind=action.kind,
            text=action.text,
        )
        new_state = replace(state, messages=state.messages + (msg,))
        # Some message kinds carry implicit stance changes.
        if action.kind is MessageKind.DECLARE_WAR:
            new_state = set_stance(
                new_state, civ_id, action.to_civ_id, DiplomaticStance.WAR
            )
        elif action.kind is MessageKind.OFFER_PEACE:
            # Offer alone doesn't end war — needs the other side to accept.
            pass
        elif action.kind is MessageKind.ACCEPT_ALLIANCE:
            new_state = set_stance(
                new_state, civ_id, action.to_civ_id, DiplomaticStance.ALLIANCE
            )
        return new_state

    if isinstance(action, SetStance):
        if action.target_civ_id not in met_civs(state, civ_id):
            raise DiplomacyError(f"cannot change stance with unmet civ {action.target_civ_id}")
        return set_stance(state, civ_id, action.target_civ_id, action.stance)

    raise DiplomacyError(f"unknown diplomatic action type {type(action).__name__}")


# ---------------------------------------------------------------------------
# Inbox helpers (used by serializer + LLM context building)
# ---------------------------------------------------------------------------

def inbox_for(
    state: GameState, civ_id: int, since_turn: int = 0
) -> list[DiplomaticMessage]:
    """Messages addressed to *civ_id* on/after *since_turn*, oldest first."""
    return [
        m for m in state.messages
        if m.to_civ_id == civ_id and m.turn >= since_turn
    ]


def conversation_between(
    state: GameState, a: int, b: int, last_n: int | None = None
) -> list[DiplomaticMessage]:
    """All messages exchanged between civs a and b, chronological."""
    convo = [
        m for m in state.messages
        if {m.from_civ_id, m.to_civ_id} == {a, b}
    ]
    if last_n is not None:
        convo = convo[-last_n:]
    return convo
