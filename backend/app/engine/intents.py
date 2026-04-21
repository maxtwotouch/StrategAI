"""Strategic intents — what the LLM declares it wants to do.

Intents are deliberately semantic and high-level. The LLM never picks unit
ids or war preconditions; the operations layer translates an Intent plus the
current GameState into one or more Goals/DiplomaticActions.

This decouples leader judgment ("I want to expand", "engage Egypt") from
tactical bookkeeping ("settler #3 to (2,-1)", "warrior #5 attack unit #8")
which the deterministic layer handles correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union

from app.engine.diplomacy import MessageKind
from app.engine.hex import Hex
from app.engine.models import DiplomaticStance, UnitType


@dataclass(frozen=True, slots=True)
class Expand:
    """Found a new city. Ops layer picks the settler and the site."""

    target: Hex | None = None  # optional preferred site


@dataclass(frozen=True, slots=True)
class Scout:
    """Send a scout/warrior toward unexplored territory."""

    target: Hex | None = None  # optional direction hint


@dataclass(frozen=True, slots=True)
class Engage:
    """Wage war on another civilization.

    Ops layer auto-declares war if not already at war, picks the closest
    military unit, and picks the closest reachable enemy unit or city.
    """

    target_civ_id: int


@dataclass(frozen=True, slots=True)
class Reinforce:
    """Move a military unit toward a friendly position (a city or a hex)."""

    target: Hex | None = None
    target_city_id: int | None = None


@dataclass(frozen=True, slots=True)
class Speak:
    """Send a diplomatic message to another leader."""

    to_civ_id: int
    kind: MessageKind
    text: str


@dataclass(frozen=True, slots=True)
class AdjustStance:
    """Set diplomatic stance with another civilization."""

    target_civ_id: int
    stance: DiplomaticStance


@dataclass(frozen=True, slots=True)
class Build:
    """Queue a unit at a city. Defaults to first owned city if not specified."""

    unit_type: UnitType
    city_id: int | None = None


@dataclass(frozen=True, slots=True)
class Research:
    """Set the civ's currently-researching tech."""

    tech_id: str


Intent = Union[Expand, Scout, Engage, Reinforce, Speak, AdjustStance, Build, Research]


class IntentKind(str, Enum):
    EXPAND = "expand"
    SCOUT = "scout"
    ENGAGE = "engage"
    REINFORCE = "reinforce"
    SPEAK = "speak"
    ADJUST_STANCE = "adjust_stance"
    BUILD = "build"
    RESEARCH = "research"
