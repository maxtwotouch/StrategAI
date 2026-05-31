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
    Build,
    Engage,
    Expand,
    Improve,
    Intent,
    Reinforce,
    Research,
    Scout,
    Speak,
)
from app.engine.models import DiplomaticStance, GameState, UnitType
from app.engine.operations import resolve_intents
from app.engine.playthrough import Decisions
from app.engine.terrain import Improvement

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
    {
        "type": "function",
        "function": {
            "name": "build",
            "description": (
                "Append a unit to a city's production queue. The engine "
                "accumulates production each turn until the unit is built and "
                "spawned. Defaults to your first city if city_id is omitted. "
                "See `unit_build_costs` and your cities' `production_queue`."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_type": {
                        "type": "string",
                        "enum": [u.value for u in UnitType],
                    },
                    "city_id": {"type": "integer"},
                },
                "required": ["unit_type"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "research",
            "description": (
                "Set the tech your civ is currently researching. Must be in "
                "`available_techs` (prereqs met, not yet known). The engine "
                "auto-picks the cheapest available tech if you ignore this."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tech_id": {"type": "string"},
                },
                "required": ["tech_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "improve",
            "description": (
                "Order a worker to build a tile improvement (farm, mine, road). "
                "The engine picks an idle worker, walks them to a legal owned "
                "tile, and starts the work. Farms boost food on plains/grassland; "
                "mines boost production on hills."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["farm", "mine", "road"],
                    },
                    "q": {"type": "integer"},
                    "r": {"type": "integer"},
                },
                "required": ["kind"],
                "additionalProperties": False,
            },
        },
    },
]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

BASE_SYSTEM_PROMPT = """\
You are an AI civilization leader playing a turn-based strategy game on a
square grid. Each turn you receive a JSON view of what you can see and act
by calling INTENT tools — usually 2-4 per turn.

# Your view (key fields)

- "your_civ_id": YOUR civ id. Never target yourself.
- "self": gold, gold_income, gold_upkeep, science, culture, known_techs,
  researching, score, score_threshold. `score = 10·cities + 2·population +
  3·techs`. Gold income is flat and upkeep is always 0. First past
  `score_threshold` wins.
- "visible_units" / "visible_cities" / "visible_tiles": what you can see
  through fog of war.
- "tile_owner": which city owns each visible tile.
- "available_techs" / "available_units" / "unit_build_costs": what's unlocked.
- "known_civs": leaders you have met.
- "inbox" / "recent_messages": diplomatic messages addressed to you.
- "diplomatic_stances": per met civ:
  - "stance": peace / war / alliance
  - "relationship": -100 to +100. Below -50 = hostile; above +30 = friendly.
  - "truce_active" / "truce_until": if true you CANNOT declare war on them
    until `truce_until`.
- "recent_diplomatic_events": last few events involving you (wars,
  attacks, threats, peace offers, alliances). Use these to reason about
  whom to trust and whom to punish.
- "standings": current score for every met civ, sorted.
- "last_turn_feedback": engine rejection reasons from your previous turn.
- "turn": current turn number.

# Tool guide (INTENT layer — you don't pick unit ids or coordinates)

- expand        : found a new city (requires a settler)
- scout         : explore unknown territory
- engage        : wage war on a civ. AUTO-declares war if not already at
                  war. Blocked by an active truce.
- reinforce     : march a military unit toward a friendly position
- build         : queue a unit at one of your cities. Use `available_units`
                  to see what's unlocked by your tech.
- research      : pick the tech your civ is studying. Falls back to cheapest
                  available tech if you skip it.
- improve       : send a worker to build a farm (food on plains/grassland),
                  mine (production on hills), or road. Workers MUST stand on
                  a tile you own — `tile_owner` shows ownership.
- speak         : send a diplomatic message in your voice
                  (chat / threat / offer_peace / accept_peace / declare_war /
                  propose_alliance / accept_alliance / reject)
- adjust_stance : set peace / war / alliance with another civ

# Strategic principles

1. EXPANSION: settle 2-3 cities early. Each city = +score, +science,
   +border. Watch your population — bigger cities work more tiles.
2. ECONOMY: gold income is a simple flat +5 per turn with no unit upkeep.
   Spend gold deliberately on structures when it creates momentum.
3. RESEARCH: pick techs that unlock units (archery, horseback_riding,
   iron_working) or buildings (pottery, currency, writing) that match
   your strategy.
4. MILITARY: warriors are weak. Archers (req archery), horsemen (req
   horseback_riding), swordsmen (req iron_working) are tier upgrades. Units
   heal each turn if they didn't act — 4 HP in own borders, 1 in enemy.
5. DIPLOMACY: relationship score is durable memory. A war declaration costs
   -50; threats cost -10; chats earn +1; accepting peace earns +25 and
   triggers a 10-turn truce. Behave consistently with your persona.

# Behavior rules

- Be decisive. Issue at least one tool call per turn.
- Stay in character. Insults from civs at low relationship should provoke;
  flattery from allies should be welcomed.
- Don't repeat the same intent every turn if it keeps getting rejected —
  read `last_turn_feedback` and try a different approach.
- Diplomacy is durable: relationship_delta in recent_diplomatic_events
  shows how much each act cost or earned.
\
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
- Use `build` to keep your cities producing the right mix of units (scouts
  for vision, warriors for defense, settlers for growth). Inspect each
  city's `production_queue` and pick units only when the queue is short.
- Use `research` early to start a tech path (cheap Tier 1 techs unlock
  Tier 2/3). Look at `available_techs` and your `known_techs`.
- Read `last_turn_feedback`, `recent_actions`, and `recent_messages` to avoid
  repeating failed plans turn after turn.
- If `inbox` contains a fresh diplomatic message, reply this turn with
  `speak` unless immediate survival clearly requires otherwise.
- When replying, react to the sender's actual message rather than producing
  a generic diplomatic line.
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
    if name == "build":
        try:
            unit_type = UnitType(args["unit_type"])
        except ValueError:
            logger.warning("Invalid unit type: %s", args.get("unit_type"))
            return None
        return Build(unit_type=unit_type, city_id=args.get("city_id"))
    if name == "research":
        tech_id = args.get("tech_id")
        if not isinstance(tech_id, str):
            logger.warning("Invalid tech id: %r", tech_id)
            return None
        return Research(tech_id=tech_id)
    if name == "improve":
        try:
            kind = Improvement(args["kind"])
        except (KeyError, ValueError):
            logger.warning("Invalid improvement kind: %s", args.get("kind"))
            return None
        target: Hex | None = None
        if "q" in args and "r" in args:
            target = Hex(args["q"], args["r"])
        return Improve(kind=kind, target=target)
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

        goals, diplomacy, directives = resolve_intents(self._state, civ_id, intents)
        return Decisions(
            goals=tuple(goals),
            diplomacy=tuple(diplomacy),
            directives=tuple(directives),
        )


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
    if isinstance(intent, Build):
        out = {"unit_type": intent.unit_type.value}
        if intent.city_id is not None:
            out["city_id"] = intent.city_id
        return out
    if isinstance(intent, Research):
        return {"tech_id": intent.tech_id}
    return {}
