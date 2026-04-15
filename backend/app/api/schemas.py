"""Pydantic schemas for API responses. Shape-only — engine stays pure dataclasses."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.engine.models import (
    City,
    Civilization,
    GameState,
    Tile,
    Unit,
)


class HexOut(BaseModel):
    q: int
    r: int


class TileOut(BaseModel):
    q: int
    r: int
    terrain: str


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


class GameStateOut(BaseModel):
    id: int
    turn: int
    map_radius: int
    tiles: list[TileOut]
    civs: list[CivOut]
    cities: list[CityOut]
    units: list[UnitOut]


def tile_to_out(t: Tile) -> TileOut:
    return TileOut(q=t.coord.q, r=t.coord.r, terrain=t.terrain.value)


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
        production_queue=[u.value for u in c.production_queue],
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


def state_to_out(game_id: int, state: GameState) -> GameStateOut:
    return GameStateOut(
        id=game_id,
        turn=state.turn,
        map_radius=state.map.radius,
        tiles=[tile_to_out(t) for t in state.map.tiles.values()],
        civs=[civ_to_out(c) for c in state.civs],
        cities=[city_to_out(c) for c in state.cities],
        units=[unit_to_out(u) for u in state.units],
    )


class CreateGameRequest(BaseModel):
    radius: int = Field(default=5, ge=1, le=12)
    seed: int = 0


class MoveRequest(BaseModel):
    unit_id: int
    q: int
    r: int


class AttackRequest(BaseModel):
    attacker_id: int
    defender_id: int


class FoundCityRequest(BaseModel):
    unit_id: int
    name: str


class ResearchRequest(BaseModel):
    civ_id: int
    tech_id: str
