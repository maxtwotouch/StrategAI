"""OpenAI tool-use GoalSource — lets an LLM play the game via tool calls.

Each civ gets its own `OpenAIGoalSource` instance carrying a persona prompt
(leader name, personality, victory style).  The LLM receives the fog-filtered
local_view JSON plus its inbox and current stances, then calls tools to:

* issue unit goals    (move_to, found_city_near, attack_unit)
* send diplomatic messages (send_message)
* change stances (set_stance)

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
from app.engine.models import DiplomaticStance
from app.engine.playthrough import Decisions

logger = logging.getLogger(__name__)

load_dotenv()

# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling schema)
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "move_to",
            "description": (
                "Move a unit toward a target hex.  The tactical layer handles "
                "pathfinding and move-budget automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_id": {"type": "integer"},
                    "target_q": {"type": "integer"},
                    "target_r": {"type": "integer"},
                },
                "required": ["unit_id", "target_q", "target_r"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "found_city_near",
            "description": (
                "Send a settler to a target hex and found a city there. "
                "The unit must be a settler."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_id": {"type": "integer"},
                    "target_q": {"type": "integer"},
                    "target_r": {"type": "integer"},
                    "name": {"type": "string"},
                },
                "required": ["unit_id", "target_q", "target_r", "name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "attack_unit",
            "description": (
                "Attack an enemy unit with one of your units.  You must be at "
                "war with the target's civilization."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "attacker_id": {"type": "integer"},
                    "target_id": {"type": "integer"},
                },
                "required": ["attacker_id", "target_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": (
                "Send a diplomatic message to another leader.  Speak in your "
                "leader's voice.  declare_war and accept_alliance also change "
                "stance automatically."
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
            "name": "set_stance",
            "description": (
                "Directly set diplomatic stance with another civilization.  "
                "Prefer send_message for narrative flavor; use this only for "
                "unilateral changes."
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
plus an inbox of recent diplomatic messages and your current stances with
known civilizations.  Issue your turn by calling tools.  You may call several
tools per turn — both unit goals and diplomatic actions.

Key view fields:
- "your_civ_id": YOUR civilization id.  Never use it as a message recipient
  or stance target — that is yourself.
- "self": your civilization (gold, science, culture, techs)
- "visible_units" / "visible_cities": entities you can see
- "visible_tiles": currently-visible terrain
- "known_civs": leaders you have met
- "inbox": diplomatic messages addressed to you
- "diplomatic_stances": current stance (peace/war/alliance) per known civ
- "last_turn_feedback": engine rejection reasons from your previous turn
- "turn": current turn number

ID namespaces are separate.  unit_id and civ_id are unrelated — a unit with
unit_id 2 has nothing to do with civ_id 2.  When attacking, attacker_id and
target_id both refer to UNIT ids, never civ ids.

Respond to messages in character.  React to insults, threats, and offers
according to your persona.  Be decisive — issue at least one tool call.\
"""


def build_system_prompt(persona: str | None = None) -> str:
    """Concatenate the base prompt with an optional per-leader persona."""
    tactical_rules = """\

Hard gameplay priorities:
- If you have a settler and no city yet, your top priority is to found your first city immediately.
- If you do not control any settler, do not call `found_city_near`.
- Only settlers can found cities. Warriors and scouts cannot found cities.
- Prefer `found_city_near` over `move_to` for settlers when you intend to establish a city.
- Do not repeatedly target occupied or unreachable tiles. Read `last_turn_feedback` and change plan if an action was rejected.
- Only message or change stance with civilizations in `known_civs`.
- Never address a message or stance change to your own civ_id (`your_civ_id`).
- If your `diplomatic_stances` already shows `war` with a target, do NOT call
  `send_message` with kind=`declare_war` again — attack their units instead.
  Re-declaring war is wasted; act on it.
- Read `recent_actions` and `recent_messages` to remember what you and others
  have already done. Avoid repeating the same failed plan two turns in a row.
- Do not spend whole turns only chatting unless you have no useful legal game action available.
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
# Parse tool calls → Goals / DiplomaticActions
# ---------------------------------------------------------------------------

def _parse_tool_call(name: str, args: dict[str, Any]) -> Goal | DiplomaticAction | None:
    if name == "move_to":
        return MoveTo(
            unit_id=args["unit_id"],
            target=Hex(args["target_q"], args["target_r"]),
        )
    if name == "found_city_near":
        return FoundCityNear(
            unit_id=args["unit_id"],
            target=Hex(args["target_q"], args["target_r"]),
            name=args["name"],
        )
    if name == "attack_unit":
        return AttackUnit(
            attacker_id=args["attacker_id"],
            target_id=args["target_id"],
        )
    if name == "send_message":
        try:
            kind = MessageKind(args["kind"])
        except ValueError:
            logger.warning("Invalid message kind: %s", args.get("kind"))
            return None
        return SendMessage(
            to_civ_id=args["to_civ_id"],
            kind=kind,
            text=args["text"],
        )
    if name == "set_stance":
        try:
            stance = DiplomaticStance(args["stance"])
        except ValueError:
            logger.warning("Invalid stance: %s", args.get("stance"))
            return None
        return SetStance(
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
    """GoalSource backed by an OpenAI chat-completions model with tool use.

    Maintains a small per-civ rolling memory of (a) what actions this leader
    issued in recent turns and (b) what diplomatic messages this leader has
    seen.  The memory is injected into the user view as `recent_actions` and
    `recent_messages` so the model has continuity across turns without
    blowing up the prompt.
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
        self._action_log: list[dict[str, Any]] = []
        self._message_log: list[dict[str, Any]] = []
        self._last_seen_message_turn: int = -1

    def _record_actions(
        self,
        turn: int,
        goals: list[Goal],
        diplomacy: list[DiplomaticAction],
    ) -> None:
        for g in goals:
            self._action_log.append({"turn": turn, "type": type(g).__name__, "data": _summarize(g)})
        for d in diplomacy:
            self._action_log.append({"turn": turn, "type": type(d).__name__, "data": _summarize(d)})
        if len(self._action_log) > _MEMORY_ACTIONS:
            del self._action_log[: len(self._action_log) - _MEMORY_ACTIONS]

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
        recent_actions = [a for a in self._action_log if a["turn"] >= cutoff]
        recent_messages = [m for m in self._message_log if m.get("turn", -1) >= cutoff]

        payload = dict(view)
        payload["your_civ_id"] = civ_id
        payload["recent_actions"] = recent_actions
        payload["recent_messages"] = recent_messages
        user_msg = json.dumps(payload, sort_keys=True, default=str)
        logger.info(
            "Requesting LLM turn for civ %d: %d visible units, %d visible cities, %d known civs, %d inbox messages, %d remembered actions",
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
        goals: list[Goal] = []
        diplomacy: list[DiplomaticAction] = []
        for tc in message.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in tool call: %s", tc.function.arguments)
                continue
            parsed = _parse_tool_call(tc.function.name, args)
            if parsed is None:
                continue
            if isinstance(parsed, (MoveTo, FoundCityNear, AttackUnit)):
                goals.append(parsed)
            else:
                diplomacy.append(parsed)
            logger.info(
                "Civ %d → %s(%s)", civ_id, tc.function.name, tc.function.arguments
            )

        self._record_actions(current_turn, goals, diplomacy)
        return Decisions(goals=tuple(goals), diplomacy=tuple(diplomacy))


def _summarize(action: Goal | DiplomaticAction) -> dict[str, Any]:
    """Compact JSON-friendly representation of an issued action for memory."""
    if isinstance(action, MoveTo):
        return {"unit_id": action.unit_id, "target_q": action.target.q, "target_r": action.target.r}
    if isinstance(action, FoundCityNear):
        return {
            "unit_id": action.unit_id,
            "target_q": action.target.q,
            "target_r": action.target.r,
            "name": action.name,
        }
    if isinstance(action, AttackUnit):
        return {"attacker_id": action.attacker_id, "target_id": action.target_id}
    if isinstance(action, SendMessage):
        return {"to_civ_id": action.to_civ_id, "kind": action.kind.value, "text": action.text}
    if isinstance(action, SetStance):
        return {"target_civ_id": action.target_civ_id, "stance": action.stance.value}
    return {}
