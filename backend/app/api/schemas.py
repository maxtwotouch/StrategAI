"""Pydantic schemas for API responses. Shape-only — engine stays pure dataclasses."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.engine.diplomacy import (
    DiplomaticEvent,
    DiplomaticMessage,
    MessageKind,
    met_civs,
    relationship_between,
    truce_active,
)
from app.engine.economy import civ_gold_income, civ_gold_upkeep
from app.engine.fog_of_war import visible_tiles
from app.engine.models import DiplomaticStance
from app.engine.victory import SCORE_THRESHOLD, civ_score
from app.engine.models import (
    City,
    Civilization,
    GameState,
    Tile,
    Unit,
)
from app.engine.terrain import tile_yields


class HexOut(BaseModel):
    q: int
    r: int


class TileOut(BaseModel):
    q: int
    r: int
    terrain: str
    resource: str | None = None
    feature: str | None = None
    river: bool = False
    improvement: str | None = None
    food: int = 0
    production: int = 0
    gold: int = 0


class WorkOrderOut(BaseModel):
    q: int
    r: int
    improvement: str
    turns_remaining: int


class UnitOut(BaseModel):
    id: int
    owner: int
    type: str
    q: int
    r: int
    health: int
    moves_remaining: int
    work_order: WorkOrderOut | None = None


class CityOut(BaseModel):
    id: int
    owner: int
    name: str
    q: int
    r: int
    population: int
    food_stored: int
    production_stored: int
    health: int
    max_health: int
    is_capital: bool
    buildings: list[str]
    purchased_structures: list[str] = Field(default_factory=list)
    production_queue: list[str]
    border_radius: int
    culture_stored: int
    worked_tiles: list[dict[str, int]] = Field(default_factory=list)


class CityStructureOut(BaseModel):
    city_id: int
    owner: int
    category: str
    q: int
    r: int


class CivOut(BaseModel):
    id: int
    name: str
    leader_name: str
    is_human: bool
    gold: int
    gold_income: int = 0
    gold_upkeep: int = 0
    science: int
    culture: int
    known_techs: list[str]
    researching: str | None
    score: int = 0


class MessageOut(BaseModel):
    from_civ_id: int
    to_civ_id: int
    turn: int
    kind: str
    text: str


class StanceOut(BaseModel):
    other_civ_id: int
    stance: str
    relationship: int = 0
    truce_active: bool = False
    truce_until: int | None = None


class DiplomaticEventOut(BaseModel):
    turn: int
    kind: str
    actor_civ_id: int
    target_civ_id: int
    summary: str
    relationship_delta: int


class StandingOut(BaseModel):
    civ_id: int
    name: str
    score: int


class TileOwnerOut(BaseModel):
    q: int
    r: int
    city_id: int


class CivRosterEntry(BaseModel):
    """Minimal civ identity used for asset pre-generation.

    Includes every civ regardless of whether the human has met them, so the
    frontend can pre-resolve leader / structure / unit art at game start. Does
    not leak any gameplay state — name, leader name, and id only.
    """

    id: int
    name: str
    leader_name: str
    is_human: bool


class GameStateOut(BaseModel):
    id: int
    turn: int
    current_civ_id: int
    map_radius: int
    tiles: list[TileOut]
    civs: list[CivOut]
    civ_roster: list[CivRosterEntry] = Field(default_factory=list)
    cities: list[CityOut]
    structures: list[CityStructureOut] = Field(default_factory=list)
    units: list[UnitOut]
    known_civ_ids: list[int]
    messages: list[MessageOut]
    inbox: list[MessageOut]
    stances: list[StanceOut]
    visible_tile_keys: list[str] = Field(default_factory=list)
    explored_tile_keys: list[str] = Field(default_factory=list)
    tile_owner: list[TileOwnerOut] = Field(default_factory=list)
    diplomatic_events: list[DiplomaticEventOut] = Field(default_factory=list)
    standings: list[StandingOut] = Field(default_factory=list)
    score_threshold: int = 200


def tile_to_out(t: Tile) -> TileOut:
    y = tile_yields(t)
    return TileOut(
        q=t.coord.q,
        r=t.coord.r,
        terrain=t.terrain.value,
        resource=t.resource.value if t.resource else None,
        feature=t.feature.value if t.feature else None,
        river=t.river,
        improvement=t.improvement.value if t.improvement else None,
        food=y.food,
        production=y.production,
        gold=y.gold,
    )


def unit_to_out(u: Unit) -> UnitOut:
    work_order_out: WorkOrderOut | None = None
    if u.work_order is not None:
        coord, improvement = u.work_order
        work_order_out = WorkOrderOut(
            q=coord.q,
            r=coord.r,
            improvement=improvement.value,
            turns_remaining=u.work_turns_remaining,
        )
    return UnitOut(
        id=u.id,
        owner=u.owner,
        type=u.type.value,
        q=u.location.q,
        r=u.location.r,
        health=u.health,
        moves_remaining=u.moves_remaining,
        work_order=work_order_out,
    )


def city_to_out(c: City) -> CityOut:
    return CityOut(
        id=c.id,
        owner=c.owner,
        name=c.name,
        q=c.location.q,
        r=c.location.r,
        population=c.population,
        food_stored=c.food_stored,
        production_stored=c.production_stored,
        health=c.health,
        max_health=c.max_health,
        is_capital=c.is_capital,
        buildings=sorted(b.value for b in c.buildings),
        purchased_structures=sorted(c.purchased_structures),
        production_queue=[item.id for item in c.production_queue],
        border_radius=c.border_radius,
        culture_stored=c.culture_stored,
        worked_tiles=sorted(
            ({"q": h.q, "r": h.r} for h in c.worked_tiles),
            key=lambda d: (d["q"], d["r"]),
        ),
    )


def structure_to_out(s) -> CityStructureOut:
    return CityStructureOut(
        city_id=s.city_id,
        owner=s.owner,
        category=s.category,
        q=s.location.q,
        r=s.location.r,
    )


def civ_to_out(civ: Civilization, state: GameState | None = None) -> CivOut:
    return CivOut(
        id=civ.id,
        name=civ.name,
        leader_name=civ.leader_name,
        is_human=civ.is_human,
        gold=civ.gold,
        gold_income=civ_gold_income(state, civ.id) if state is not None else 0,
        gold_upkeep=civ_gold_upkeep(state, civ.id) if state is not None else 0,
        science=civ.science,
        culture=civ.culture,
        known_techs=sorted(civ.known_techs),
        researching=civ.researching,
        score=civ_score(state, civ) if state is not None else 0,
    )


def diplomatic_event_to_out(event: DiplomaticEvent) -> DiplomaticEventOut:
    return DiplomaticEventOut(
        turn=event.turn,
        kind=event.kind.value,
        actor_civ_id=event.actor_civ_id,
        target_civ_id=event.target_civ_id,
        summary=event.summary,
        relationship_delta=event.relationship_delta,
    )


def message_to_out(message: DiplomaticMessage) -> MessageOut:
    return MessageOut(
        from_civ_id=message.from_civ_id,
        to_civ_id=message.to_civ_id,
        turn=message.turn,
        kind=message.kind.value,
        text=message.text,
    )


def state_to_out(game_id: int, state: GameState) -> GameStateOut:
    human_civ = next((c for c in state.civs if c.is_human), None)
    known_ids = sorted(met_civs(state, human_civ.id) - {human_civ.id}) if human_civ is not None else []
    visible = visible_tiles(state, human_civ.id) if human_civ is not None else frozenset()
    # Explored = ever-seen ∪ currently-visible. Lazy union covers tiles
    # revealed mid-turn before end_turn accumulates them.
    if human_civ is not None:
        explored = state.explored.get(human_civ.id, frozenset()) | visible
    else:
        explored = frozenset(state.map.tiles.keys())
    visible_civ_ids = set(known_ids)
    if human_civ is not None:
        visible_civ_ids.add(human_civ.id)
    inbox = [
        message_to_out(message)
        for message in state.messages
        if human_civ is not None and message.to_civ_id == human_civ.id
    ]
    messages = [
        message_to_out(message)
        for message in state.messages
        if human_civ is not None
        and {message.from_civ_id, message.to_civ_id}.issubset(visible_civ_ids)
        and human_civ.id in (message.from_civ_id, message.to_civ_id)
    ]
    stances: list[StanceOut] = []
    if human_civ is not None:
        for civ in state.civs:
            if civ.id == human_civ.id or civ.id not in known_ids:
                continue
            truce_until = state.truces.get(
                tuple(sorted((human_civ.id, civ.id)))
            )
            stances.append(
                StanceOut(
                    other_civ_id=civ.id,
                    stance=state.stance_between(human_civ.id, civ.id).value,
                    relationship=relationship_between(state, human_civ.id, civ.id),
                    truce_active=truce_active(state, human_civ.id, civ.id),
                    truce_until=truce_until,
                )
            )
    visible_keys = sorted(f"{c.q},{c.r}" for c in visible)
    explored_keys = sorted(f"{c.q},{c.r}" for c in explored)
    tile_owner_list = sorted(
        (
            TileOwnerOut(q=coord.q, r=coord.r, city_id=city_id)
            for coord, city_id in state.tile_owner.items()
            if coord in visible
        ),
        key=lambda t: (t.q, t.r),
    )
    # Recent diplomatic events involving the human civ (last 20).
    if human_civ is not None:
        relevant_events = [
            e for e in state.diplomatic_events
            if e.actor_civ_id == human_civ.id or e.target_civ_id == human_civ.id
        ]
        event_list = [diplomatic_event_to_out(e) for e in relevant_events[-20:]]
    else:
        event_list = []

    standings = sorted(
        (
            StandingOut(civ_id=c.id, name=c.name, score=civ_score(state, c))
            for c in state.civs
            if c.id in visible_civ_ids
        ),
        key=lambda s: (-s.score, s.civ_id),
    )

    return GameStateOut(
        id=game_id,
        turn=state.turn,
        current_civ_id=state.current_civ().id,
        map_radius=state.map.radius,
        tiles=[
            tile_to_out(t)
            for coord, t in state.map.tiles.items()
            if coord in explored
        ],
        civs=[civ_to_out(c, state) for c in state.civs if c.id in visible_civ_ids],
        civ_roster=[
            CivRosterEntry(
                id=c.id,
                name=c.name,
                leader_name=c.leader_name,
                is_human=c.is_human,
            )
            for c in state.civs
        ],
        cities=[
            city_to_out(c)
            for c in state.cities
            if c.owner == human_civ.id or c.location in visible
        ] if human_civ is not None else [city_to_out(c) for c in state.cities],
        structures=[
            structure_to_out(s)
            for s in state.structures
            if human_civ is None or s.owner == human_civ.id or s.location in visible
        ],
        units=[
            unit_to_out(u)
            for u in state.units
            if u.owner == human_civ.id or u.location in visible
        ] if human_civ is not None else [unit_to_out(u) for u in state.units],
        known_civ_ids=known_ids,
        messages=messages,
        inbox=inbox,
        stances=stances,
        visible_tile_keys=visible_keys,
        explored_tile_keys=explored_keys,
        tile_owner=tile_owner_list,
        diplomatic_events=event_list,
        standings=standings,
        score_threshold=SCORE_THRESHOLD,
    )


class CreateGameRequest(BaseModel):
    radius: int = Field(default=8, ge=1, le=20)
    seed: int = 0
    human_name: str = Field(default="Athens", min_length=1, max_length=40)


class IntroNarrationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1200)


class MoveRequest(BaseModel):
    unit_id: int
    q: int
    r: int


class AttackRequest(BaseModel):
    attacker_id: int
    defender_id: int


class AttackCityRequest(BaseModel):
    attacker_id: int
    city_id: int


class FoundCityRequest(BaseModel):
    unit_id: int
    name: str


class ResearchRequest(BaseModel):
    civ_id: int
    tech_id: str


class BuildRequest(BaseModel):
    civ_id: int
    city_id: int
    unit_type: str | None = None
    build_kind: str = Field(default="unit")
    item_id: str | None = None


class CancelBuildRequest(BaseModel):
    civ_id: int
    city_id: int
    index: int


class PurchaseStructureRequest(BaseModel):
    civ_id: int
    city_id: int
    category: str
    q: int
    r: int


class MessageRequest(BaseModel):
    from_civ_id: int
    to_civ_id: int
    kind: str = Field(default=MessageKind.CHAT.value)
    text: str


class BuildImprovementRequest(BaseModel):
    unit_id: int
    improvement: str
