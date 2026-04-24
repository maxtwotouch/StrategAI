"""Pydantic schemas for API responses. Shape-only — engine stays pure dataclasses."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.engine.diplomacy import DiplomaticMessage, MessageKind, met_civs
from app.engine.fog_of_war import visible_tiles
from app.engine.models import DiplomaticStance
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
    food: int = 0
    production: int = 0
    gold: int = 0


class UnitOut(BaseModel):
    id: int
    owner: int
    type: str
    q: int
    r: int
    health: int
    moves_remaining: int


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
    production_queue: list[str]


class CivOut(BaseModel):
    id: int
    name: str
    leader_name: str
    is_human: bool
    gold: int
    science: int
    culture: int
    known_techs: list[str]
    researching: str | None


class MessageOut(BaseModel):
    from_civ_id: int
    to_civ_id: int
    turn: int
    kind: str
    text: str


class StanceOut(BaseModel):
    other_civ_id: int
    stance: str


class GameStateOut(BaseModel):
    id: int
    turn: int
    current_civ_id: int
    map_radius: int
    tiles: list[TileOut]
    civs: list[CivOut]
    cities: list[CityOut]
    units: list[UnitOut]
    known_civ_ids: list[int]
    messages: list[MessageOut]
    inbox: list[MessageOut]
    stances: list[StanceOut]
    visible_tile_keys: list[str] = Field(default_factory=list)


def tile_to_out(t: Tile) -> TileOut:
    y = tile_yields(t)
    return TileOut(
        q=t.coord.q,
        r=t.coord.r,
        terrain=t.terrain.value,
        resource=t.resource.value if t.resource else None,
        feature=t.feature.value if t.feature else None,
        river=t.river,
        food=y.food,
        production=y.production,
        gold=y.gold,
    )


def unit_to_out(u: Unit) -> UnitOut:
    return UnitOut(
        id=u.id,
        owner=u.owner,
        type=u.type.value,
        q=u.location.q,
        r=u.location.r,
        health=u.health,
        moves_remaining=u.moves_remaining,
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
        production_queue=[item.id for item in c.production_queue],
    )


def civ_to_out(civ: Civilization) -> CivOut:
    return CivOut(
        id=civ.id,
        name=civ.name,
        leader_name=civ.leader_name,
        is_human=civ.is_human,
        gold=civ.gold,
        science=civ.science,
        culture=civ.culture,
        known_techs=sorted(civ.known_techs),
        researching=civ.researching,
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
    inbox = [
        message_to_out(message)
        for message in state.messages
        if human_civ is not None and message.to_civ_id == human_civ.id
    ]
    stances: list[StanceOut] = []
    if human_civ is not None:
        for civ in state.civs:
            if civ.id == human_civ.id or civ.id not in known_ids:
                continue
            stances.append(
                StanceOut(
                    other_civ_id=civ.id,
                    stance=state.stance_between(human_civ.id, civ.id).value,
                )
            )
    if human_civ is not None:
        visible_keys = sorted(
            f"{c.q},{c.r}" for c in visible_tiles(state, human_civ.id)
        )
    else:
        visible_keys = []
    return GameStateOut(
        id=game_id,
        turn=state.turn,
        current_civ_id=state.current_civ().id,
        map_radius=state.map.radius,
        tiles=[tile_to_out(t) for t in state.map.tiles.values()],
        civs=[civ_to_out(c) for c in state.civs],
        cities=[city_to_out(c) for c in state.cities],
        units=[unit_to_out(u) for u in state.units],
        known_civ_ids=known_ids,
        messages=[message_to_out(message) for message in state.messages],
        inbox=inbox,
        stances=stances,
        visible_tile_keys=visible_keys,
    )


class CreateGameRequest(BaseModel):
    radius: int = Field(default=8, ge=1, le=20)
    seed: int = 0
    human_name: str = Field(default="Athens", min_length=1, max_length=40)


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


class MessageRequest(BaseModel):
    from_civ_id: int
    to_civ_id: int
    kind: str = Field(default=MessageKind.CHAT.value)
    text: str
