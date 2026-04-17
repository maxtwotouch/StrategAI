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
- "self": your civilization (gold, science, culture, techs)
- "visible_units" / "visible_cities": entities you can see
- "visible_tiles": currently-visible terrain
- "known_civs": leaders you have met
- "inbox": diplomatic messages addressed to you
- "diplomatic_stances": current stance (peace/war/alliance) per known civ
- "turn": current turn number

Respond to messages in character.  React to insults, threats, and offers
according to your persona.  Be decisive — issue at least one tool call.\
"""


def build_system_prompt(persona: str | None = None) -> str:
    """Concatenate the base prompt with an optional per-leader persona."""
    if not persona:
        return BASE_SYSTEM_PROMPT
    return BASE_SYSTEM_PROMPT + "\n\n--- YOUR PERSONA ---\n" + persona.strip()


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

class OpenAIGoalSource:
    """GoalSource backed by an OpenAI chat-completions model with tool use."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        temperature: float = 0.7,
        persona: str | None = None,
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

    def decide(self, view: dict, civ_id: int) -> Decisions:
        user_msg = json.dumps(view, sort_keys=True)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=self._temperature,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                tools=TOOLS,
                tool_choice="required",
            )
        except Exception:
            logger.exception("OpenAI API call failed for civ %d", civ_id)
            return Decisions()

        message = response.choices[0].message
        if not message.tool_calls:
            logger.info("LLM returned no tool calls for civ %d", civ_id)
            return Decisions()

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

        return Decisions(goals=tuple(goals), diplomacy=tuple(diplomacy))
