"""Translate strategic intents into concrete goals + diplomatic actions.

The operations layer is the deterministic bridge between LLM-emitted intents
(Expand, Engage, Speak, ...) and the existing Goal/DiplomaticAction layer
that the playthrough loop already understands.

Design rules:
- Pure functions over GameState. No I/O, no randomness.
- Self-targeted Speak / AdjustStance / Engage are dropped (returns []).
- Engage auto-issues a war declaration if not already at war.
- Unit selection is deterministic (closest-to-target, lowest id as tiebreak).
"""

from __future__ import annotations

from typing import Iterable

from app.engine.diplomacy import (
    DiplomaticAction,
    MessageKind,
    SendMessage,
    SetStance,
    met_civs,
)
from app.engine.city_names import next_city_name
from app.engine.directives import Directive, QueueProduction, StartResearch
from app.engine.executor import (
    AttackUnit,
    BuildImprovementGoal,
    FoundCityNear,
    Goal,
    MoveTo,
)
from app.engine.fog_of_war import visible_tiles
from app.engine.hex import Hex, hex_distance, hex_neighbors, hex_range
from app.engine.improvements import can_improve
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
from app.engine.models import (
    BuildItem,
    City,
    DiplomaticStance,
    GameState,
    Unit,
    UnitType,
)
from app.engine.research import TECHS, can_build_unit
from app.engine.terrain import Improvement as ImprovementKind, is_passable


# ---------------------------------------------------------------------------
# Selectors
# ---------------------------------------------------------------------------

def _settlers(state: GameState, civ_id: int) -> list[Unit]:
    return [u for u in state.units if u.owner == civ_id and u.type is UnitType.SETTLER]


def _military(state: GameState, civ_id: int) -> list[Unit]:
    return [
        u for u in state.units
        if u.owner == civ_id and u.type in (UnitType.WARRIOR, UnitType.SCOUT)
    ]


def _occupied(state: GameState, coord: Hex) -> bool:
    return any(u.location == coord for u in state.units) or any(
        c.location == coord for c in state.cities
    )


def _passable_open(state: GameState, coord: Hex) -> bool:
    if coord not in state.map:
        return False
    tile = state.map.get(coord)
    if tile is None or not is_passable(tile.terrain):
        return False
    return not _occupied(state, coord)


def _closest(units: Iterable[Unit], target: Hex) -> Unit | None:
    candidates = list(units)
    if not candidates:
        return None
    return min(candidates, key=lambda u: (hex_distance(u.location, target), u.id))


def _pick_city_site(state: GameState, settler: Unit, hint: Hex | None) -> Hex | None:
    """Return a legal site near *settler*. Prefer hint if it works, else nearest open tile."""
    if hint is not None and _passable_open(state, hint) and not _has_city(state, hint):
        return hint
    if _passable_open(state, settler.location) and not _has_city(state, settler.location):
        return settler.location
    for radius in range(1, 5):
        ring = [
            settler.location + Hex(dq, dr)
            for dq in range(-radius, radius + 1)
            for dr in range(-radius, radius + 1)
            if max(abs(dq), abs(dr), abs(dq + dr)) == radius
        ]
        for coord in sorted(ring, key=lambda c: (c.q, c.r)):
            if _passable_open(state, coord) and not _has_city(state, coord):
                return coord
    return None


def _has_city(state: GameState, coord: Hex) -> bool:
    return any(c.location == coord for c in state.cities)


def _frontier_target(state: GameState, civ_id: int, scout: Unit) -> Hex | None:
    """Pick a visible-edge tile for exploration."""
    visible = visible_tiles(state, civ_id)
    if not visible:
        return scout.location
    candidates: list[Hex] = []
    for coord in visible:
        for n in hex_neighbors(coord):
            if n in state.map and n not in visible:
                candidates.append(n)
    if not candidates:
        # Fully explored — just push outward.
        outer = [
            c for c in state.map.tiles
            if hex_distance(c, scout.location) <= scout.stats.sight + 4
        ]
        return min(outer, key=lambda c: (-hex_distance(c, scout.location), c.q, c.r)) if outer else None
    return min(candidates, key=lambda c: (hex_distance(c, scout.location), c.q, c.r))


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

class _Out:
    __slots__ = ("goals", "diplomacy", "directives")

    def __init__(self) -> None:
        self.goals: list[Goal] = []
        self.diplomacy: list[DiplomaticAction] = []
        self.directives: list[Directive] = []

    def extend(self, other: "_Out") -> None:
        self.goals.extend(other.goals)
        self.diplomacy.extend(other.diplomacy)
        self.directives.extend(other.directives)


# ---------------------------------------------------------------------------
# Per-intent translators
# ---------------------------------------------------------------------------

def _do_expand(state: GameState, civ_id: int, intent: Expand) -> _Out:
    out = _Out()
    settlers = _settlers(state, civ_id)
    if not settlers:
        return out
    settler = (
        _closest(settlers, intent.target) if intent.target is not None else settlers[0]
    )
    if settler is None:
        return out
    site = _pick_city_site(state, settler, intent.target)
    if site is None:
        return out
    name = next_city_name(state, civ_id)
    out.goals.append(FoundCityNear(unit_id=settler.id, target=site, name=name))
    return out


def _do_scout(state: GameState, civ_id: int, intent: Scout) -> _Out:
    out = _Out()
    units = _military(state, civ_id)
    # Prefer scouts; if none, any military unit.
    scouts = [u for u in units if u.type is UnitType.SCOUT]
    pool = scouts or units
    if not pool:
        return out
    target_hint = intent.target
    if target_hint is None:
        # Pick the unit closest to the frontier and head there.
        unit = pool[0]
        target = _frontier_target(state, civ_id, unit)
    else:
        unit = _closest(pool, target_hint)
        if unit is None:
            return out
        target = target_hint
    if target is None or target == unit.location:
        return out
    out.goals.append(MoveTo(unit_id=unit.id, target=target))
    return out


def _do_reinforce(state: GameState, civ_id: int, intent: Reinforce) -> _Out:
    out = _Out()
    target: Hex | None = intent.target
    if target is None and intent.target_city_id is not None:
        city = next(
            (c for c in state.cities if c.id == intent.target_city_id and c.owner == civ_id),
            None,
        )
        if city is not None:
            target = city.location
    if target is None:
        own_cities = state.cities_for(civ_id)
        if own_cities:
            target = own_cities[0].location
    if target is None:
        return out
    units = _military(state, civ_id)
    unit = _closest(units, target)
    if unit is None or unit.location == target:
        return out
    out.goals.append(MoveTo(unit_id=unit.id, target=target))
    return out


def _do_engage(state: GameState, civ_id: int, intent: Engage) -> _Out:
    out = _Out()
    target_civ = intent.target_civ_id
    if target_civ == civ_id:
        return out
    if not any(c.id == target_civ for c in state.civs):
        return out
    if target_civ not in met_civs(state, civ_id):
        return out

    # Auto-declare war if not already at war.
    current_stance = state.stance_between(civ_id, target_civ)
    if current_stance is not DiplomaticStance.WAR:
        out.diplomacy.append(
            SendMessage(
                to_civ_id=target_civ,
                kind=MessageKind.DECLARE_WAR,
                text="We meet on the field of battle.",
            )
        )

    visible = visible_tiles(state, civ_id)
    enemy_units = [
        u for u in state.units if u.owner == target_civ and u.location in visible
    ]
    enemy_cities = [
        c for c in state.cities if c.owner == target_civ and c.location in visible
    ]

    attackers = _military(state, civ_id)
    if not attackers:
        return out

    if enemy_units:
        # Pair: closest attacker to nearest visible enemy.
        target_unit = min(
            enemy_units,
            key=lambda u: (
                min(hex_distance(u.location, a.location) for a in attackers),
                u.id,
            ),
        )
        attacker = _closest(attackers, target_unit.location)
        if attacker is not None:
            out.goals.append(
                AttackUnit(attacker_id=attacker.id, target_id=target_unit.id)
            )
        return out

    if enemy_cities:
        # No enemy units in sight — march on the closest visible city.
        target_city = min(
            enemy_cities,
            key=lambda c: (
                min(hex_distance(c.location, a.location) for a in attackers),
                c.id,
            ),
        )
        attacker = _closest(attackers, target_city.location)
        if attacker is not None and attacker.location != target_city.location:
            out.goals.append(MoveTo(unit_id=attacker.id, target=target_city.location))
        return out

    # No visible enemy at all — push a scout-like move toward unexplored frontier.
    attacker = attackers[0]
    target = _frontier_target(state, civ_id, attacker)
    if target is not None and target != attacker.location:
        out.goals.append(MoveTo(unit_id=attacker.id, target=target))
    return out


def _do_speak(state: GameState, civ_id: int, intent: Speak) -> _Out:
    out = _Out()
    if intent.to_civ_id == civ_id:
        return out
    if not any(c.id == intent.to_civ_id for c in state.civs):
        return out
    out.diplomacy.append(
        SendMessage(to_civ_id=intent.to_civ_id, kind=intent.kind, text=intent.text)
    )
    return out


def _do_adjust_stance(state: GameState, civ_id: int, intent: AdjustStance) -> _Out:
    out = _Out()
    if intent.target_civ_id == civ_id:
        return out
    if not any(c.id == intent.target_civ_id for c in state.civs):
        return out
    out.diplomacy.append(
        SetStance(target_civ_id=intent.target_civ_id, stance=intent.stance)
    )
    return out


def _do_build(state: GameState, civ_id: int, intent: Build) -> _Out:
    out = _Out()
    cities = state.cities_for(civ_id)
    if not cities:
        return out
    civ = next((c for c in state.civs if c.id == civ_id), None)
    if civ is None or not can_build_unit(civ, intent.unit_type):
        # Tech not researched — drop silently rather than generating rejected
        # directives that pollute the LLM feedback channel.
        return out
    if intent.city_id is not None:
        city = next((c for c in cities if c.id == intent.city_id), None)
        if city is None:
            return out
    else:
        city = cities[0]
    out.directives.append(
        QueueProduction(city_id=city.id, item=BuildItem.unit(intent.unit_type))
    )
    return out


def _workers(state: GameState, civ_id: int) -> list[Unit]:
    return [u for u in state.units if u.owner == civ_id and u.type is UnitType.WORKER]


def _improvable_tile_near(
    state: GameState,
    civ_id: int,
    improvement: ImprovementKind,
    hint: Hex | None,
) -> Hex | None:
    """Pick a tile this civ owns where the improvement is legal.

    Prefers the hint tile if it's legal, otherwise the first legal tile in
    deterministic coordinate order.
    """
    owned_tiles = sorted(
        (coord for coord, city_id in state.tile_owner.items()),
        key=lambda c: (c.q, c.r),
    )
    candidates: list[Hex] = []
    for coord in owned_tiles:
        tile = state.map.get(coord)
        if tile is None:
            continue
        if can_improve(state, tile, improvement, civ_id) is not None:
            continue
        candidates.append(coord)
    if not candidates:
        return None
    if hint is not None and hint in candidates:
        return hint
    if hint is not None:
        return min(candidates, key=lambda c: (hex_distance(c, hint), c.q, c.r))
    return candidates[0]


def _do_improve(state: GameState, civ_id: int, intent: Improve) -> _Out:
    out = _Out()
    workers = [w for w in _workers(state, civ_id) if w.work_order is None]
    if not workers:
        return out
    target = _improvable_tile_near(state, civ_id, intent.kind, intent.target)
    if target is None:
        return out
    worker = _closest(workers, target)
    if worker is None:
        return out
    out.goals.append(
        BuildImprovementGoal(unit_id=worker.id, target=target, improvement=intent.kind)
    )
    return out


def _do_research(state: GameState, civ_id: int, intent: Research) -> _Out:
    out = _Out()
    tech = TECHS.get(intent.tech_id)
    if tech is None:
        return out
    civ = next((c for c in state.civs if c.id == civ_id), None)
    if civ is None:
        return out
    if intent.tech_id in civ.known_techs:
        return out
    if not all(p in civ.known_techs for p in tech.prerequisites):
        return out
    out.directives.append(StartResearch(tech_id=intent.tech_id))
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def resolve_intent(
    state: GameState, civ_id: int, intent: Intent
) -> tuple[list[Goal], list[DiplomaticAction], list[Directive]]:
    """Translate one intent into goals, diplomatic actions, and directives."""
    if isinstance(intent, Expand):
        out = _do_expand(state, civ_id, intent)
    elif isinstance(intent, Scout):
        out = _do_scout(state, civ_id, intent)
    elif isinstance(intent, Engage):
        out = _do_engage(state, civ_id, intent)
    elif isinstance(intent, Reinforce):
        out = _do_reinforce(state, civ_id, intent)
    elif isinstance(intent, Speak):
        out = _do_speak(state, civ_id, intent)
    elif isinstance(intent, AdjustStance):
        out = _do_adjust_stance(state, civ_id, intent)
    elif isinstance(intent, Build):
        out = _do_build(state, civ_id, intent)
    elif isinstance(intent, Research):
        out = _do_research(state, civ_id, intent)
    elif isinstance(intent, Improve):
        out = _do_improve(state, civ_id, intent)
    else:
        out = _Out()
    return out.goals, out.diplomacy, out.directives


def resolve_intents(
    state: GameState, civ_id: int, intents: Iterable[Intent]
) -> tuple[list[Goal], list[DiplomaticAction], list[Directive]]:
    """Resolve a batch of intents. State is NOT advanced between intents —
    callers should keep ordering small (one logical turn per LLM call)."""
    all_goals: list[Goal] = []
    all_dipl: list[DiplomaticAction] = []
    all_dirs: list[Directive] = []
    for intent in intents:
        goals, dipl, dirs = resolve_intent(state, civ_id, intent)
        all_goals.extend(goals)
        all_dipl.extend(dipl)
        all_dirs.extend(dirs)
    return all_goals, all_dipl, all_dirs
