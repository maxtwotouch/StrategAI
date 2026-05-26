"""Terrain, features, resources, and yield calculations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.models import Tile


class Terrain(str, Enum):
    OCEAN = "ocean"
    COAST = "coast"
    PLAINS = "plains"
    GRASSLAND = "grassland"
    FOREST = "forest"
    HILLS = "hills"
    MOUNTAIN = "mountain"
    DESERT = "desert"
    TUNDRA = "tundra"
    SNOW = "snow"


class Feature(str, Enum):
    FOREST = "forest"
    JUNGLE = "jungle"
    MARSH = "marsh"
    OASIS = "oasis"


class Improvement(str, Enum):
    FARM = "farm"
    MINE = "mine"
    ROAD = "road"


class ResourceCategory(str, Enum):
    STRATEGIC = "strategic"
    LUXURY = "luxury"
    BONUS = "bonus"


class Resource(str, Enum):
    IRON = "iron"
    HORSES = "horses"
    COAL = "coal"
    GEMS = "gems"
    SILK = "silk"
    SPICES = "spices"
    WHEAT = "wheat"
    CATTLE = "cattle"
    FISH = "fish"


@dataclass(frozen=True, slots=True)
class Yields:
    food: int = 0
    production: int = 0
    gold: int = 0

    def __add__(self, other: "Yields") -> "Yields":
        return Yields(
            food=self.food + other.food,
            production=self.production + other.production,
            gold=self.gold + other.gold,
        )


@dataclass(frozen=True, slots=True)
class ResourceInfo:
    category: ResourceCategory
    bonus: Yields
    allowed_terrain: frozenset[Terrain]


TERRAIN_YIELDS: dict[Terrain, Yields] = {
    Terrain.OCEAN: Yields(food=1, gold=1),
    Terrain.COAST: Yields(food=1, gold=2),
    Terrain.PLAINS: Yields(food=1, production=1),
    Terrain.GRASSLAND: Yields(food=2),
    Terrain.FOREST: Yields(food=1, production=2),
    Terrain.HILLS: Yields(production=2),
    Terrain.MOUNTAIN: Yields(),
    Terrain.DESERT: Yields(gold=1),
    Terrain.TUNDRA: Yields(food=1),
    Terrain.SNOW: Yields(),
}


FEATURE_YIELDS: dict[Feature, Yields] = {
    Feature.FOREST: Yields(production=1),
    Feature.JUNGLE: Yields(food=1),
    Feature.MARSH: Yields(food=-1),
    Feature.OASIS: Yields(food=3, gold=1),
}


IMPROVEMENT_YIELDS: dict[Improvement, Yields] = {
    Improvement.FARM: Yields(food=1),
    Improvement.MINE: Yields(production=1),
    Improvement.ROAD: Yields(),  # Movement effects land in Tier 2.
}


# Allowed terrain per improvement type.
IMPROVEMENT_TERRAIN: dict[Improvement, frozenset[Terrain]] = {
    Improvement.FARM: frozenset({Terrain.PLAINS, Terrain.GRASSLAND}),
    Improvement.MINE: frozenset({Terrain.HILLS}),
    Improvement.ROAD: frozenset(),  # populated below
}


# Build turns per improvement.
IMPROVEMENT_TURNS: dict[Improvement, int] = {
    Improvement.FARM: 3,
    Improvement.MINE: 4,
    Improvement.ROAD: 2,
}


RESOURCES: dict[Resource, ResourceInfo] = {
    Resource.IRON: ResourceInfo(
        ResourceCategory.STRATEGIC,
        Yields(production=2),
        frozenset({Terrain.HILLS, Terrain.MOUNTAIN}),
    ),
    Resource.HORSES: ResourceInfo(
        ResourceCategory.STRATEGIC,
        Yields(production=1, food=1),
        frozenset({Terrain.PLAINS, Terrain.GRASSLAND}),
    ),
    Resource.COAL: ResourceInfo(
        ResourceCategory.STRATEGIC,
        Yields(production=2),
        frozenset({Terrain.HILLS, Terrain.FOREST}),
    ),
    Resource.GEMS: ResourceInfo(
        ResourceCategory.LUXURY,
        Yields(gold=3),
        frozenset({Terrain.HILLS, Terrain.MOUNTAIN}),
    ),
    Resource.SILK: ResourceInfo(
        ResourceCategory.LUXURY,
        Yields(gold=2),
        frozenset({Terrain.FOREST, Terrain.GRASSLAND}),
    ),
    Resource.SPICES: ResourceInfo(
        ResourceCategory.LUXURY,
        Yields(gold=2),
        frozenset({Terrain.PLAINS, Terrain.DESERT}),
    ),
    Resource.WHEAT: ResourceInfo(
        ResourceCategory.BONUS,
        Yields(food=2),
        frozenset({Terrain.PLAINS, Terrain.GRASSLAND}),
    ),
    Resource.CATTLE: ResourceInfo(
        ResourceCategory.BONUS,
        Yields(food=1, production=1),
        frozenset({Terrain.GRASSLAND, Terrain.PLAINS}),
    ),
    Resource.FISH: ResourceInfo(
        ResourceCategory.BONUS,
        Yields(food=2),
        frozenset({Terrain.COAST, Terrain.OCEAN}),
    ),
}


IMPASSABLE_TERRAIN: frozenset[Terrain] = frozenset(
    {Terrain.MOUNTAIN, Terrain.OCEAN, Terrain.SNOW}
)

PASSABLE: frozenset[Terrain] = frozenset(t for t in Terrain if t not in IMPASSABLE_TERRAIN)

# Roads may be built on any passable land tile.
IMPROVEMENT_TERRAIN[Improvement.ROAD] = PASSABLE


def yields_for(terrain: Terrain) -> Yields:
    return TERRAIN_YIELDS[terrain]


def is_passable(terrain: Terrain) -> bool:
    return terrain in PASSABLE


def resource_info(resource: Resource) -> ResourceInfo:
    return RESOURCES[resource]


def tile_yields(tile: "Tile") -> Yields:
    total = TERRAIN_YIELDS[tile.terrain]
    if tile.feature is not None:
        total = total + FEATURE_YIELDS[tile.feature]
    if tile.resource is not None:
        total = total + RESOURCES[tile.resource].bonus
    if tile.river:
        total = total + Yields(gold=1)
    if tile.improvement is not None:
        total = total + IMPROVEMENT_YIELDS[tile.improvement]
    return total
