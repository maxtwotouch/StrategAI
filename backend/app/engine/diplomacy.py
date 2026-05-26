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
    ACCEPT_PEACE = "accept_peace"
    DECLARE_WAR = "declare_war"
    PROPOSE_ALLIANCE = "propose_alliance"
    ACCEPT_ALLIANCE = "accept_alliance"
    REJECT = "reject"


# ---------------------------------------------------------------------------
# Relationship scoring
# ---------------------------------------------------------------------------

REL_MIN = -100
REL_MAX = 100

# Per-event relationship deltas (applied to the actor→target pair).
REL_DECLARE_WAR = -50
REL_ATTACK = -20
REL_THREAT = -10
REL_REJECT = -5
REL_CHAT = 1
REL_OFFER_PEACE = 8
REL_ACCEPT_PEACE = 25
REL_PROPOSE_ALLIANCE = 15
REL_ACCEPT_ALLIANCE = 30

# Truce duration when peace is accepted (turns).
TRUCE_DURATION_TURNS = 10


class DiplomaticEventKind(str, Enum):
    """Engine-emitted records of relationship-affecting events."""
    WAR_DECLARED = "war_declared"
    ATTACK = "attack"
    THREAT = "threat"
    REJECTED = "rejected"
    CHAT = "chat"
    PEACE_OFFERED = "peace_offered"
    PEACE_ACCEPTED = "peace_accepted"
    ALLIANCE_PROPOSED = "alliance_proposed"
    ALLIANCE_ACCEPTED = "alliance_accepted"


@dataclass(frozen=True, slots=True)
class DiplomaticEvent:
    """A relationship-affecting event recorded on GameState."""
    turn: int
    kind: DiplomaticEventKind
    actor_civ_id: int
    target_civ_id: int
    summary: str
    relationship_delta: int


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


def relationship_between(state: GameState, a: int, b: int) -> int:
    """Symmetric relationship score in [-100, +100]. Default 0."""
    if a == b:
        return REL_MAX
    return state.relationships.get(_stance_key(a, b), 0)


def adjust_relationship(state: GameState, a: int, b: int, delta: int) -> GameState:
    """Bounded relationship update. No-op for self."""
    if a == b or delta == 0:
        return state
    key = _stance_key(a, b)
    new_rels = dict(state.relationships)
    current = new_rels.get(key, 0)
    new_rels[key] = max(REL_MIN, min(REL_MAX, current + delta))
    return replace(state, relationships=new_rels)


def truce_active(state: GameState, a: int, b: int) -> bool:
    """True if a and b are in a binding truce period."""
    if a == b:
        return False
    expires = state.truces.get(_stance_key(a, b))
    return expires is not None and state.turn < expires


def set_truce(state: GameState, a: int, b: int, until_turn: int) -> GameState:
    """Mark a truce between a and b expiring at *until_turn*."""
    if a == b:
        return state
    new_truces = dict(state.truces)
    new_truces[_stance_key(a, b)] = until_turn
    return replace(state, truces=new_truces)


def record_event(
    state: GameState,
    kind: DiplomaticEventKind,
    actor: int,
    target: int,
    summary: str,
    delta: int,
) -> GameState:
    """Append a DiplomaticEvent to GameState.diplomatic_events."""
    event = DiplomaticEvent(
        turn=state.turn,
        kind=kind,
        actor_civ_id=actor,
        target_civ_id=target,
        summary=summary,
        relationship_delta=delta,
    )
    return replace(state, diplomatic_events=state.diplomatic_events + (event,))


# ---------------------------------------------------------------------------
# Apply a single diplomatic action
# ---------------------------------------------------------------------------

_MESSAGE_KIND_TO_EVENT: dict[MessageKind, tuple[DiplomaticEventKind, int]] = {
    MessageKind.CHAT: (DiplomaticEventKind.CHAT, REL_CHAT),
    MessageKind.THREAT: (DiplomaticEventKind.THREAT, REL_THREAT),
    MessageKind.OFFER_PEACE: (DiplomaticEventKind.PEACE_OFFERED, REL_OFFER_PEACE),
    MessageKind.ACCEPT_PEACE: (DiplomaticEventKind.PEACE_ACCEPTED, REL_ACCEPT_PEACE),
    MessageKind.DECLARE_WAR: (DiplomaticEventKind.WAR_DECLARED, REL_DECLARE_WAR),
    MessageKind.PROPOSE_ALLIANCE: (DiplomaticEventKind.ALLIANCE_PROPOSED, REL_PROPOSE_ALLIANCE),
    MessageKind.ACCEPT_ALLIANCE: (DiplomaticEventKind.ALLIANCE_ACCEPTED, REL_ACCEPT_ALLIANCE),
    MessageKind.REJECT: (DiplomaticEventKind.REJECTED, REL_REJECT),
}


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
        # Block hostile escalation during an active truce.
        if (
            action.kind in (MessageKind.DECLARE_WAR, MessageKind.THREAT)
            and truce_active(state, civ_id, action.to_civ_id)
        ):
            raise DiplomacyError(
                f"truce with civ {action.to_civ_id} is still binding"
            )
        msg = DiplomaticMessage(
            from_civ_id=civ_id,
            to_civ_id=action.to_civ_id,
            turn=state.turn,
            kind=action.kind,
            text=action.text,
        )
        new_state = replace(state, messages=state.messages + (msg,))

        # Stance / truce side-effects.
        if action.kind is MessageKind.DECLARE_WAR:
            new_state = set_stance(
                new_state, civ_id, action.to_civ_id, DiplomaticStance.WAR
            )
        elif action.kind is MessageKind.ACCEPT_PEACE:
            new_state = set_stance(
                new_state, civ_id, action.to_civ_id, DiplomaticStance.PEACE
            )
            new_state = set_truce(
                new_state, civ_id, action.to_civ_id,
                new_state.turn + TRUCE_DURATION_TURNS,
            )
        elif action.kind is MessageKind.ACCEPT_ALLIANCE:
            new_state = set_stance(
                new_state, civ_id, action.to_civ_id, DiplomaticStance.ALLIANCE
            )

        # Relationship + event log.
        mapping = _MESSAGE_KIND_TO_EVENT.get(action.kind)
        if mapping is not None:
            event_kind, delta = mapping
            new_state = adjust_relationship(new_state, civ_id, action.to_civ_id, delta)
            summary = f"{action.kind.value} from civ {civ_id} to civ {action.to_civ_id}"
            new_state = record_event(
                new_state, event_kind, civ_id, action.to_civ_id, summary, delta
            )
        return new_state

    if isinstance(action, SetStance):
        if action.target_civ_id not in met_civs(state, civ_id):
            raise DiplomacyError(f"cannot change stance with unmet civ {action.target_civ_id}")
        if action.stance is DiplomaticStance.WAR and truce_active(
            state, civ_id, action.target_civ_id
        ):
            raise DiplomacyError(
                f"truce with civ {action.target_civ_id} is still binding"
            )
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
