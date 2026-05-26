"""City borders, tile ownership, and worked-tile assignment.

Each city claims tiles within its border_radius (Chebyshev distance on the
square grid). When two cities' claim discs overlap, the closer city wins;
ties are broken by lower city_id. The city center is always claimed by its
city.

Workers are assigned greedily by yield score, capped at the city's
population. The center tile is always counted in `worked_tiles`. Yield score
is the sum of food + production + gold from `tile_yields(tile)` (which already
folds in feature, resource, and river bonuses).

All functions are pure: `(state, ...) -> GameState` or a derived value.
"""

from __future__ import annotations

from dataclasses import replace

from app.engine.hex import Hex, hex_distance, hex_range
from app.engine.models import City, GameState
from app.engine.terrain import Yields, tile_yields

# Culture thresholds for border growth.
CULTURE_RADIUS_2 = 10
CULTURE_RADIUS_3 = 30
MAX_BORDER_RADIUS = 3


def claimed_tiles(state: GameState, city: City) -> set[Hex]:
    """Tiles currently owned by *city* per state.tile_owner."""
    return {coord for coord, owner in state.tile_owner.items() if owner == city.id}


def potential_claim(city: City) -> list[Hex]:
    """Tiles a city would claim absent any conflict."""
    return hex_range(city.location, city.border_radius)


def recompute_claims(state: GameState) -> GameState:
    """Rebuild `state.tile_owner` from current city positions and radii.

    Conflict rule: closer city wins; tie → lower city_id wins. The center of
    a city is always owned by that city.
    """
    claims: dict[Hex, tuple[int, int]] = {}  # hex → (city_id, distance)
    for city in state.cities:
        for coord in potential_claim(city):
            if coord not in state.map:
                continue
            dist = hex_distance(city.location, coord)
            existing = claims.get(coord)
            if existing is None:
                claims[coord] = (city.id, dist)
                continue
            existing_id, existing_dist = existing
            if dist < existing_dist or (dist == existing_dist and city.id < existing_id):
                claims[coord] = (city.id, dist)
    new_owner = {coord: city_id for coord, (city_id, _) in claims.items()}
    return replace(state, tile_owner=new_owner)


def grow_borders(state: GameState) -> GameState:
    """Promote each city's `border_radius` based on its `culture_stored`.

    Thresholds are checked monotonically; a city never loses radius.
    """
    new_cities: list[City] = []
    changed = False
    for city in state.cities:
        new_radius = city.border_radius
        if new_radius < 2 and city.culture_stored >= CULTURE_RADIUS_2:
            new_radius = 2
        if new_radius < 3 and city.culture_stored >= CULTURE_RADIUS_3:
            new_radius = 3
        if new_radius > MAX_BORDER_RADIUS:
            new_radius = MAX_BORDER_RADIUS
        if new_radius != city.border_radius:
            changed = True
            new_cities.append(replace(city, border_radius=new_radius))
        else:
            new_cities.append(city)
    state = replace(state, cities=tuple(new_cities))
    if changed:
        state = recompute_claims(state)
    return state


def _tile_score(state: GameState, coord: Hex) -> tuple[int, int, int]:
    """Sort key for greedy worker assignment. Higher is better."""
    tile = state.map.get(coord)
    if tile is None:
        return (-1, 0, 0)
    y = tile_yields(tile)
    # Primary: total yield. Secondary: food (early game priority). Tie:
    # negative (q, r) to break deterministically.
    total = y.food + y.production + y.gold
    return (total, y.food, 0)


def auto_assign_workers(state: GameState) -> GameState:
    """For each city, set worked_tiles to {center} ∪ top-yield claimed tiles.

    Cap: at most `population` tiles total (center included). Deterministic
    tiebreak by (q, r).
    """
    new_cities: list[City] = []
    for city in state.cities:
        owned = claimed_tiles(state, city)
        # Center is always worked even if it failed to land in tile_owner
        # (defensive: recompute_claims should have placed it).
        candidates = sorted(
            (c for c in owned if c != city.location),
            key=lambda c: (_tile_score(state, c), -c.q, -c.r),
            reverse=True,
        )
        cap = max(0, city.population - 1)
        extra = frozenset(candidates[:cap])
        worked = extra | {city.location}
        if worked != city.worked_tiles:
            new_cities.append(replace(city, worked_tiles=worked))
        else:
            new_cities.append(city)
    return replace(state, cities=tuple(new_cities))


def working_yields(state: GameState, city: City) -> Yields:
    """Sum tile_yields() over the city's worked_tiles (center auto-included)."""
    total = Yields()
    coords = set(city.worked_tiles)
    coords.add(city.location)
    for coord in coords:
        tile = state.map.get(coord)
        if tile is None:
            continue
        total = total + tile_yields(tile)
    return total
