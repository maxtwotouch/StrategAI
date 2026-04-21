"""OpenAI tool-use GoalSource — lets an LLM play the game via INTENT tools.

Each civ gets its own `OpenAIGoalSource` instance carrying a persona prompt
(leader name, personality, victory style).  The LLM receives the fog-filtered
local_view JSON plus its inbox and current stances, then calls intent tools:

* expand          — found a city (settler & site picked deterministically)
* scout           — explore unknown territory
* engage          — wage war on a target civ (auto-declares war if needed)
* reinforce       — march a military unit toward a friendly position
* speak           — diplomatic message (cannot target self)
* adjust_stance   — set stance with another civ (cannot target self)

The intent layer fans out into Goals + DiplomaticActions via operations.py
before the playthrough loop sees anything. The LLM never picks unit ids,
never has to remember to declare war before attacking, and cannot accidentally
target itself.

Returns a `Decisions` object — both goals and diplomacy in a single API call.

Requires OPENAI_API_KEY in the environment (or `api_key=` argument).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from app.engine.diplomacy import (
    DiplomaticAction,
    MessageKind,
    SendMessage,
    SetStance,
)
from app.engine.executor import AttackUnit, FoundCityNear, Goal, MoveTo
from app.engine.hex import Hex
from app.engine.intents import (
    AdjustStance,
    Engage,
    Expand,
    Intent,
    Reinforce,
    Scout,
    Speak,
)
from app.engine.models import DiplomaticStance, GameState
from app.engine.operations import resolve_intents
from app.engine.playthrough import Decisions

logger = logging.getLogger(__name__)

load_dotenv()

# ---------------------------------------------------------------------------
# Tool definitions (intent-level — no unit ids)
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "expand",
            "description": (
                "Found a new city. The engine picks one of your settlers and "
                "the best legal site. Optionally hint a target hex."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_q": {"type": "integer"},
                    "target_r": {"type": "integer"},
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scout",
            "description": (
                "Send a unit (preferring scouts) toward unexplored territory. "
                "Optionally hint a direction with target_q/r."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_q": {"type": "integer"},
                    "target_r": {"type": "integer"},
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "engage",
            "description": (
                "Wage war on another civilization. The engine auto-declares "
                "war if you are not already at war, then sends your closest "
                "military unit against the closest visible enemy unit or "
                "city. Cannot target yourself."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_civ_id": {"type": "integer"},
                },
                "required": ["target_civ_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reinforce",
            "description": (
                "Move your closest military unit toward a friendly position. "
                "Defaults to your first city if no target is given."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_q": {"type": "integer"},
                    "target_r": {"type": "integer"},
                    "target_city_id": {"type": "integer"},
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "speak",
            "description": (
                "Send a diplomatic message to another leader. Speak in your "
                "leader's voice. Cannot target yourself."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "to_civ_id": {"type": "integer"},
                    "kind": {
                        "type": "string",
                        "enum": [k.value for k in MessageKind],
                    },
                    "text": {"type": "string"},
                },
                "required": ["to_civ_id", "kind", "text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "adjust_stance",
            "description": (
                "Directly set diplomatic stance with another civilization. "
                "Prefer `speak` for narrative; use this for unilateral changes. "
                "Cannot target yourself."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_civ_id": {"type": "integer"},
                    "stance": {
                        "type": "string",
                        "enum": [s.value for s in DiplomaticStance],
                    },
                },
                "required": ["target_civ_id", "stance"],
                "additionalProperties": False,
            },
        },
    },
]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

BASE_SYSTEM_PROMPT = """\
You are an AI civilization leader playing a strategy game on a hex grid.

Each turn you receive a JSON object describing what you can see (fog of war),
your inbox, current stances, and what you and others did recently.  Issue
your turn by calling INTENT tools.  You may call several tools per turn.

Key view fields:
- "your_civ_id": YOUR civilization id. Never use it as a tool target.
- "self": your civilization (gold, science, culture, techs)
- "visible_units" / "visible_cities": entities you can see
- "visible_tiles": currently-visible terrain
- "known_civs": leaders you have met
- "inbox": diplomatic messages addressed to you
- "diplomatic_stances": current stance (peace/war/alliance) per known civ
- "last_turn_feedback": engine rejection reasons from your previous turn
- "recent_actions" / "recent_messages": what you and others recently did
- "turn": current turn number

You do NOT pick unit ids, hex coordinates, or war preconditions.  The engine
handles tactics deterministically.  Your job is to decide WHAT to do this
turn — the engine decides HOW.

Tool guide:
- expand        : found a new city (only if you have a settler)
- scout         : explore unknown territory
- engage        : wage war on a target civ — auto-declares war for you
- reinforce     : march a military unit toward a friendly position
- speak         : send a diplomatic message in your voice
- adjust_stance : peace/war/alliance with another civ

Respond to messages in character. React to insults, threats, and offers
according to your persona. Be decisive — issue at least one tool call.\
"""


def build_system_prompt(persona: str | None = None) -> str:
    """Concatenate the base prompt with an optional per-leader persona."""
    tactical_rules = """\

Hard gameplay priorities:
- If you have a settler and no city yet, your top priority is `expand`.
- Use `engage` (not `speak` with kind=declare_war) to fight — it handles war
  declaration and unit selection in one step.
- Only message or change stance with civilizations in `known_civs`.
- Do not target your own civ_id with any tool.
- Read `last_turn_feedback`, `recent_actions`, and `recent_messages` to avoid
  repeating failed plans turn after turn.
- Do not spend whole turns only chatting unless you have no useful action.
"""
    if not persona:
        return BASE_SYSTEM_PROMPT + tactical_rules
    return (
        BASE_SYSTEM_PROMPT
        + tactical_rules
        + "\n\n--- YOUR PERSONA ---\n"
        + persona.strip()
    )


# ---------------------------------------------------------------------------
# Parse tool calls → Intents
# ---------------------------------------------------------------------------

def _optional_hex(args: dict[str, Any]) -> Hex | None:
    if "target_q" in args and "target_r" in args:
        return Hex(args["target_q"], args["target_r"])
    return None


def _parse_tool_call(name: str, args: dict[str, Any]) -> Intent | None:
    if name == "expand":
        return Expand(target=_optional_hex(args))
    if name == "scout":
        return Scout(target=_optional_hex(args))
    if name == "engage":
        return Engage(target_civ_id=args["target_civ_id"])
    if name == "reinforce":
        return Reinforce(
            target=_optional_hex(args),
            target_city_id=args.get("target_city_id"),
        )
    if name == "speak":
        try:
            kind = MessageKind(args["kind"])
        except ValueError:
            logger.warning("Invalid message kind: %s", args.get("kind"))
            return None
        return Speak(
            to_civ_id=args["to_civ_id"],
            kind=kind,
            text=args["text"],
        )
    if name == "adjust_stance":
        try:
            stance = DiplomaticStance(args["stance"])
        except ValueError:
            logger.warning("Invalid stance: %s", args.get("stance"))
            return None
        return AdjustStance(
            target_civ_id=args["target_civ_id"],
            stance=stance,
        )
    logger.warning("Unknown tool call: %s", name)
    return None


# ---------------------------------------------------------------------------
# OpenAIGoalSource
# ---------------------------------------------------------------------------

_MEMORY_TURNS = 8
_MEMORY_ACTIONS = 32


class OpenAIGoalSource:
    """GoalSource backed by an OpenAI chat-completions model with intent tools.

    Maintains a small per-civ rolling memory of (a) intents this leader issued
    in recent turns and (b) diplomatic messages this leader has seen.  The
    memory is injected into the user view as `recent_actions` and
    `recent_messages` so the model has continuity across turns without
    blowing up the prompt.

    The source needs the live GameState to resolve intents into goals — the
    playthrough loop wires this in via `bind_state`.
    """

    def __init__(
        self,
        model: str = "gpt-5.4-mini",
        api_key: str | None = None,
        temperature: float = 0.7,
        persona: str | None = None,
        memory_turns: int = _MEMORY_TURNS,
    ) -> None:
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError(
                "OPENAI_API_KEY must be set in the environment or passed explicitly"
            )
        self._client = OpenAI(api_key=key)
        self._model = model
        self._temperature = temperature
        self._system_prompt = build_system_prompt(persona)
        self._memory_turns = memory_turns
        self._intent_log: list[dict[str, Any]] = []
        self._message_log: list[dict[str, Any]] = []
        self._last_seen_message_turn: int = -1
        self._state: GameState | None = None

    def bind_state(self, state: GameState) -> None:
        """Playthrough loop calls this each turn so resolve_intents has fresh state."""
        self._state = state

    def _record_intents(self, turn: int, intents: list[Intent]) -> None:
        for intent in intents:
            self._intent_log.append(
                {"turn": turn, "type": type(intent).__name__, "data": _summarize(intent)}
            )
        if len(self._intent_log) > _MEMORY_ACTIONS:
            del self._intent_log[: len(self._intent_log) - _MEMORY_ACTIONS]

    def _ingest_inbox(self, view: dict) -> None:
        for m in view.get("inbox", []):
            turn = m.get("turn", -1)
            if turn <= self._last_seen_message_turn:
                continue
            self._message_log.append(m)
            if turn > self._last_seen_message_turn:
                self._last_seen_message_turn = turn
        if len(self._message_log) > _MEMORY_ACTIONS:
            del self._message_log[: len(self._message_log) - _MEMORY_ACTIONS]

    def decide(self, view: dict, civ_id: int) -> Decisions:
        self._ingest_inbox(view)

        current_turn = view.get("turn", 0)
        cutoff = current_turn - self._memory_turns
        recent_actions = [a for a in self._intent_log if a["turn"] >= cutoff]
        recent_messages = [m for m in self._message_log if m.get("turn", -1) >= cutoff]

        payload = dict(view)
        payload["your_civ_id"] = civ_id
        payload["recent_actions"] = recent_actions
        payload["recent_messages"] = recent_messages
        user_msg = json.dumps(payload, sort_keys=True, default=str)
        logger.info(
            "Requesting LLM turn for civ %d: %d visible units, %d visible cities, %d known civs, %d inbox messages, %d remembered intents",
            civ_id,
            len(view.get("visible_units", [])),
            len(view.get("visible_cities", [])),
            len(view.get("known_civs", [])),
            len(view.get("inbox", [])),
            len(recent_actions),
        )

        request_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_msg},
            ],
            "tools": TOOLS,
            "tool_choice": "required",
        }
        if not self._model.startswith(("gpt-5", "o1", "o3", "o4")):
            request_kwargs["temperature"] = self._temperature

        try:
            response = self._client.chat.completions.create(**request_kwargs)
        except Exception as exc:
            logger.warning("OpenAI API call failed for civ %d: %s", civ_id, exc)
            logger.debug("OpenAI API failure details for civ %d", civ_id, exc_info=True)
            return Decisions()

        message = response.choices[0].message
        if not message.tool_calls:
            logger.info("LLM returned no tool calls for civ %d", civ_id)
            return Decisions()

        logger.info("LLM returned %d tool calls for civ %d", len(message.tool_calls), civ_id)
        intents: list[Intent] = []
        for tc in message.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in tool call: %s", tc.function.arguments)
                continue
            parsed = _parse_tool_call(tc.function.name, args)
            if parsed is None:
                continue
            intents.append(parsed)
            logger.info(
                "Civ %d → %s(%s)", civ_id, tc.function.name, tc.function.arguments
            )

        self._record_intents(current_turn, intents)

        if self._state is None:
            logger.warning(
                "OpenAIGoalSource for civ %d has no bound state — returning empty Decisions",
                civ_id,
            )
            return Decisions()

        goals, diplomacy = resolve_intents(self._state, civ_id, intents)
        return Decisions(goals=tuple(goals), diplomacy=tuple(diplomacy))


def _summarize(intent: Intent) -> dict[str, Any]:
    """Compact JSON-friendly representation of an intent for memory."""
    if isinstance(intent, Expand):
        out: dict[str, Any] = {}
        if intent.target is not None:
            out["target_q"] = intent.target.q
            out["target_r"] = intent.target.r
        return out
    if isinstance(intent, Scout):
        out = {}
        if intent.target is not None:
            out["target_q"] = intent.target.q
            out["target_r"] = intent.target.r
        return out
    if isinstance(intent, Engage):
        return {"target_civ_id": intent.target_civ_id}
    if isinstance(intent, Reinforce):
        out = {}
        if intent.target is not None:
            out["target_q"] = intent.target.q
            out["target_r"] = intent.target.r
        if intent.target_city_id is not None:
            out["target_city_id"] = intent.target_city_id
        return out
    if isinstance(intent, Speak):
        return {
            "to_civ_id": intent.to_civ_id,
            "kind": intent.kind.value,
            "text": intent.text,
        }
    if isinstance(intent, AdjustStance):
        return {
            "target_civ_id": intent.target_civ_id,
            "stance": intent.stance.value,
        }
    return {}
