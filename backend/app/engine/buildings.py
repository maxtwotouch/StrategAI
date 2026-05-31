"""Building definitions and city-level effect helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.engine.models import BuildingType, City


@dataclass(frozen=True, slots=True)
class BuildingDef:
    id: BuildingType
    name: str
    cost: int
    prerequisite: str | None = None
    food_bonus: int = 0
    production_bonus: int = 0
    science_bonus: int = 0
    culture_bonus: int = 0
    gold_bonus: int = 0
    trained_unit_health_bonus: int = 0


BUILDINGS: dict[BuildingType, BuildingDef] = {
    b.id: b
    for b in (
        BuildingDef(
            id=BuildingType.GRANARY,
            name="Granary",
            cost=20,
            prerequisite="pottery",
            food_bonus=1,
        ),
        BuildingDef(
            id=BuildingType.MONUMENT,
            name="Monument",
            cost=18,
            culture_bonus=1,
        ),
        BuildingDef(
            id=BuildingType.LIBRARY,
            name="Library",
            cost=24,
            prerequisite="writing",
            science_bonus=2,
        ),
        BuildingDef(
            id=BuildingType.BARRACKS,
            name="Barracks",
            cost=22,
            prerequisite="bronze_working",
            trained_unit_health_bonus=3,
        ),
        BuildingDef(
            id=BuildingType.MARKET,
            name="Market",
            cost=24,
            prerequisite="currency",
            gold_bonus=2,
        ),
    )
}


def city_food_bonus(city: City) -> int:
    return sum(BUILDINGS[b].food_bonus for b in city.buildings if b in BUILDINGS)


def city_production_bonus(city: City) -> int:
    return sum(BUILDINGS[b].production_bonus for b in city.buildings if b in BUILDINGS)


def city_science_bonus(city: City) -> int:
    return sum(BUILDINGS[b].science_bonus for b in city.buildings if b in BUILDINGS)


def city_culture_bonus(city: City) -> int:
    return sum(BUILDINGS[b].culture_bonus for b in city.buildings if b in BUILDINGS)


def city_gold_bonus(city: City) -> int:
    return sum(BUILDINGS[b].gold_bonus for b in city.buildings if b in BUILDINGS)


def trained_unit_health_bonus(city: City) -> int:
    return sum(
        BUILDINGS[b].trained_unit_health_bonus for b in city.buildings if b in BUILDINGS
    )


# ---------------------------------------------------------------------------
# Asset-API structures — gold-purchased buildings keyed by category.
# ---------------------------------------------------------------------------
# Categories mirror the asset service's StructureCategory enum so the frontend
# can render real building art on purchase. Each category, regardless of which
# one is chosen, currently grants the same +production bonus — the asset is
# what differentiates them visually; gameplay-wise they are equivalent for now.

PURCHASABLE_STRUCTURE_CATEGORIES: frozenset[str] = frozenset(
    {"fortification", "production", "housing", "sacred"}
)
STRUCTURE_GOLD_COST: int = 15
STRUCTURE_PRODUCTION_BONUS_PER: int = 2


def city_structure_production_bonus(city: City) -> int:
    """Production yield bonus from gold-purchased structures."""
    return len(city.purchased_structures) * STRUCTURE_PRODUCTION_BONUS_PER
