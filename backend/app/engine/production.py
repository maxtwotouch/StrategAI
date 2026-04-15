"""City production and growth. Pure — returns new GameState each tick."""

from __future__ import annotations

from dataclasses import replace

from app.engine.hex import hex_neighbors
from app.engine.models import (
    City,
    GameState,
    UNIT_BUILD_COST,
    UNIT_STATS,
    Unit,
    UnitType,
)
from app.engine.terrain import is_passable, yields_for

# Base yields a city produces beyond its terrain (keeps new cities viable).
CITY_BASE_FOOD = 2
CITY_BASE_PRODUCTION = 1
# Food consumed per population unit per turn.
FOOD_UPKEEP_PER_POP = 1


def _next_unit_id(state: GameState) -> int:
    return max((u.id for u in state.units), default=0) + 1


def _occupied(state: GameState, coord) -> bool:  # type: ignore[no-untyped-def]
    return any(u.location == coord for u in state.units)


def _spawn_location(state: GameState, city: City):  # type: ignore[no-untyped-def]
    if not _occupied(state, city.location):
        return city.location
    for neighbor in hex_neighbors(city.location):
        tile = state.map.get(neighbor)
        if tile is None or not is_passable(tile.terrain):
            continue
        if not _occupied(state, neighbor):
            return neighbor
    return None


def _city_tile_yields(state: GameState, city: City) -> tuple[int, int]:
    tile = state.map.get(city.location)
    if tile is None:
        return (CITY_BASE_FOOD, CITY_BASE_PRODUCTION)
    y = yields_for(tile.terrain)
    return (CITY_BASE_FOOD + y.food, CITY_BASE_PRODUCTION + y.production)


def _grow(city: City) -> City:
    food = city.food_stored
    pop = city.population
    threshold = city.growth_threshold()
    if food >= threshold:
        return replace(city, population=pop + 1, food_stored=food - threshold)
    return city


def _tick_city(state: GameState, city: City) -> tuple[GameState, City]:
    food_yield, prod_yield = _city_tile_yields(state, city)
    net_food = food_yield - FOOD_UPKEEP_PER_POP * city.population
    new_food = max(0, city.food_stored + net_food)
    new_prod = city.production_stored + prod_yield

    new_queue = city.production_queue
    working_state = state

    if new_queue:
        head = new_queue[0]
        cost = UNIT_BUILD_COST[head]
        if new_prod >= cost:
            spawn = _spawn_location(working_state, city)
            if spawn is not None:
                stats = UNIT_STATS[head]
                unit = Unit(
                    id=_next_unit_id(working_state),
                    owner=city.owner,
                    type=head,
                    location=spawn,
                    health=stats.max_health,
                    moves_remaining=stats.moves,
                )
                working_state = replace(
                    working_state, units=working_state.units + (unit,)
                )
                new_prod -= cost
                new_queue = new_queue[1:]

    updated = replace(
        city,
        food_stored=new_food,
        production_stored=new_prod,
        production_queue=new_queue,
    )
    updated = _grow(updated)
    return working_state, updated


def process_cities(state: GameState) -> GameState:
    new_cities: list[City] = []
    working = state
    for city in state.cities:
        working, updated = _tick_city(working, city)
        new_cities.append(updated)
    return replace(working, cities=tuple(new_cities))
