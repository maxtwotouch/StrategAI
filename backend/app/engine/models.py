"""Core game state dataclasses. All frozen — mutations return new instances."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING

from app.engine.hex import Hex
from app.engine.terrain import Feature, Improvement, Resource, Terrain

if TYPE_CHECKING:
    from app.engine.diplomacy import DiplomaticEvent, DiplomaticMessage


class UnitType(str, Enum):
    SETTLER = "settler"
    WARRIOR = "warrior"
    SCOUT = "scout"
    WORKER = "worker"
    ARCHER = "archer"
    HORSEMAN = "horseman"
    SWORDSMAN = "swordsman"


class BuildingType(str, Enum):
    GRANARY = "granary"
    MONUMENT = "monument"
    LIBRARY = "library"
    BARRACKS = "barracks"
    MARKET = "market"


class BuildKind(str, Enum):
    UNIT = "unit"
    BUILDING = "building"


@dataclass(frozen=True, slots=True)
class UnitStats:
    max_health: int
    attack: int
    defense: int
    moves: int
    sight: int


UNIT_STATS: dict[UnitType, UnitStats] = {
    UnitType.SETTLER: UnitStats(max_health=10, attack=0, defense=1, moves=2, sight=2),
    UnitType.WARRIOR: UnitStats(max_health=20, attack=4, defense=3, moves=2, sight=2),
    UnitType.SCOUT: UnitStats(max_health=10, attack=1, defense=1, moves=4, sight=3),
    UnitType.WORKER: UnitStats(max_health=10, attack=0, defense=1, moves=2, sight=1),
    UnitType.ARCHER: UnitStats(max_health=20, attack=5, defense=2, moves=2, sight=2),
    UnitType.HORSEMAN: UnitStats(max_health=20, attack=6, defense=3, moves=4, sight=2),
    UnitType.SWORDSMAN: UnitStats(max_health=25, attack=7, defense=5, moves=2, sight=2),
}


UNIT_BUILD_COST: dict[UnitType, int] = {
    UnitType.SETTLER: 15,
    UnitType.WARRIOR: 10,
    UnitType.SCOUT: 8,
    UnitType.WORKER: 10,
    UnitType.ARCHER: 15,
    UnitType.HORSEMAN: 22,
    UnitType.SWORDSMAN: 30,
}


@dataclass(frozen=True, slots=True)
class BuildItem:
    kind: BuildKind
    id: str

    @classmethod
    def unit(cls, unit_type: UnitType) -> "BuildItem":
        return cls(kind=BuildKind.UNIT, id=unit_type.value)

    @classmethod
    def building(cls, building_type: BuildingType) -> "BuildItem":
        return cls(kind=BuildKind.BUILDING, id=building_type.value)


@dataclass(frozen=True, slots=True)
class Tile:
    coord: Hex
    terrain: Terrain
    elevation: float = 0.0
    moisture: float = 0.0
    temperature: float = 0.0
    resource: Resource | None = None
    feature: Feature | None = None
    river: bool = False
    improvement: Improvement | None = None


@dataclass(frozen=True, slots=True)
class GameMap:
    radius: int
    tiles: dict[Hex, Tile]

    def get(self, coord: Hex) -> Tile | None:
        return self.tiles.get(coord)

    def __contains__(self, coord: object) -> bool:
        return coord in self.tiles


@dataclass(frozen=True, slots=True)
class Unit:
    id: int
    owner: int
    type: UnitType
    location: Hex
    health: int
    moves_remaining: int
    acted_this_turn: bool = False
    work_order: tuple[Hex, Improvement] | None = None
    work_turns_remaining: int = 0

    @property
    def stats(self) -> UnitStats:
        return UNIT_STATS[self.type]

    def with_location(self, loc: Hex) -> "Unit":
        return replace(self, location=loc)

    def with_moves(self, moves: int) -> "Unit":
        return replace(self, moves_remaining=moves)


@dataclass(frozen=True, slots=True)
class City:
    id: int
    owner: int
    name: str
    location: Hex
    population: int = 1
    food_stored: int = 0
    production_stored: int = 0
    health: int = 20
    max_health: int = 20
    is_capital: bool = False
    buildings: frozenset[BuildingType] = field(default_factory=frozenset)
    # Gold-purchased structure categories from the asset API
    # (fortification | production | housing | sacred). One of each per city.
    purchased_structures: frozenset[str] = field(default_factory=frozenset)
    production_queue: tuple[BuildItem, ...] = ()
    border_radius: int = 1
    culture_stored: int = 0
    worked_tiles: frozenset[Hex] = field(default_factory=frozenset)

    def growth_threshold(self) -> int:
        return 10 * self.population


@dataclass(frozen=True, slots=True)
class CityStructure:
    city_id: int
    owner: int
    category: str
    location: Hex


class DiplomaticStance(str, Enum):
    PEACE = "peace"
    WAR = "war"
    ALLIANCE = "alliance"


@dataclass(frozen=True, slots=True)
class Civilization:
    id: int
    name: str
    leader_name: str
    is_human: bool
    gold: int = 0
    science: int = 0
    culture: int = 0
    known_techs: frozenset[str] = field(default_factory=frozenset)
    researching: str | None = None
    starting_position: Hex | None = None
    color: str = "#888888"
    traits: tuple[str, ...] = ()
    persona: str = ""


@dataclass(frozen=True, slots=True)
class GameState:
    turn: int
    map: GameMap
    civs: tuple[Civilization, ...]
    cities: tuple[City, ...]
    units: tuple[Unit, ...]
    structures: tuple[CityStructure, ...] = ()
    seed: int = 0
    current_civ_idx: int = 0
    diplomacy: dict[tuple[int, int], DiplomaticStance] = field(default_factory=dict)
    visibility: dict[int, frozenset[Hex]] = field(default_factory=dict)
    messages: tuple["DiplomaticMessage", ...] = ()
    tile_owner: dict[Hex, int] = field(default_factory=dict)
    relationships: dict[tuple[int, int], int] = field(default_factory=dict)
    truces: dict[tuple[int, int], int] = field(default_factory=dict)
    diplomatic_events: tuple["DiplomaticEvent", ...] = ()
    explored: dict[int, frozenset[Hex]] = field(default_factory=dict)

    def units_for(self, civ_id: int) -> tuple[Unit, ...]:
        return tuple(u for u in self.units if u.owner == civ_id)

    def cities_for(self, civ_id: int) -> tuple[City, ...]:
        return tuple(c for c in self.cities if c.owner == civ_id)

    def current_civ(self) -> Civilization:
        return self.civs[self.current_civ_idx]

    def stance_between(self, a: int, b: int) -> DiplomaticStance:
        if a == b:
            return DiplomaticStance.PEACE
        key = (a, b) if a < b else (b, a)
        return self.diplomacy.get(key, DiplomaticStance.PEACE)
