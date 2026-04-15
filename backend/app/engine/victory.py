"""Victory conditions: domination and score."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.engine.models import Civilization, GameState

SCORE_THRESHOLD = 200


class VictoryKind(str, Enum):
    DOMINATION = "domination"
    SCORE = "score"


@dataclass(frozen=True, slots=True)
class VictoryResult:
    kind: VictoryKind
    winner_id: int


def is_eliminated(state: GameState, civ: Civilization) -> bool:
    return not state.cities_for(civ.id) and not state.units_for(civ.id)


def civ_score(state: GameState, civ: Civilization) -> int:
    cities = state.cities_for(civ.id)
    population = sum(c.population for c in cities)
    return 10 * len(cities) + 2 * population + 3 * len(civ.known_techs)


def check_victory(state: GameState) -> VictoryResult | None:
    if len(state.civs) == 0:
        return None

    alive = [c for c in state.civs if not is_eliminated(state, c)]
    if len(state.civs) >= 2 and len(alive) == 1:
        return VictoryResult(VictoryKind.DOMINATION, alive[0].id)

    # Score victory — highest scorer past threshold wins.
    scored = [(civ, civ_score(state, civ)) for civ in alive]
    qualifying = [(civ, s) for civ, s in scored if s >= SCORE_THRESHOLD]
    if qualifying:
        winner = max(qualifying, key=lambda pair: pair[1])[0]
        return VictoryResult(VictoryKind.SCORE, winner.id)

    return None
