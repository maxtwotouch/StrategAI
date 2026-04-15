"""Build the initial GameState for a new game."""

from __future__ import annotations

from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import (
    Civilization,
    GameState,
    Unit,
    UnitType,
    UNIT_STATS,
)
from app.engine.terrain import is_passable


_DEFAULT_CIVS: tuple[tuple[str, str, bool], ...] = (
    ("Athens", "Perikles", True),
    ("Rome", "Caesar", False),
    ("Persia", "Cyrus", False),
    ("Egypt", "Cleopatra", False),
)


def _starting_tiles(state_map, count: int) -> list[Hex]:
    radius = state_map.radius
    candidates = [
        Hex(0, -radius + 2),
        Hex(0, radius - 2),
        Hex(-radius + 2, 0),
        Hex(radius - 2, 0),
    ]
    chosen: list[Hex] = []
    for c in candidates:
        tile = state_map.tiles.get(c)
        if tile and is_passable(tile.terrain):
            chosen.append(c)
        if len(chosen) == count:
            break
    if len(chosen) < count:
        # Fallback: first N passable tiles.
        for coord, tile in state_map.tiles.items():
            if coord in chosen or not is_passable(tile.terrain):
                continue
            chosen.append(coord)
            if len(chosen) == count:
                break
    return chosen


def new_game(radius: int = 5, seed: int = 0, num_civs: int = 2) -> GameState:
    num_civs = max(2, min(num_civs, len(_DEFAULT_CIVS)))
    game_map = generate_map(radius=radius, seed=seed)
    civs = tuple(
        Civilization(id=i, name=name, leader_name=leader, is_human=is_human)
        for i, (name, leader, is_human) in enumerate(_DEFAULT_CIVS[:num_civs])
    )
    starts = _starting_tiles(game_map, num_civs)
    settler_stats = UNIT_STATS[UnitType.SETTLER]
    warrior_stats = UNIT_STATS[UnitType.WARRIOR]

    units: list[Unit] = []
    uid = 1
    for civ, loc in zip(civs, starts):
        units.append(
            Unit(
                id=uid,
                owner=civ.id,
                type=UnitType.SETTLER,
                location=loc,
                health=settler_stats.max_health,
                moves_remaining=settler_stats.moves,
            )
        )
        uid += 1
        # Warrior escort — find a passable neighbor, else stack.
        escort_loc = loc
        for neighbor in (
            Hex(loc.q + 1, loc.r),
            Hex(loc.q + 1, loc.r - 1),
            Hex(loc.q - 1, loc.r + 1),
        ):
            tile = game_map.tiles.get(neighbor)
            if tile and is_passable(tile.terrain):
                escort_loc = neighbor
                break
        units.append(
            Unit(
                id=uid,
                owner=civ.id,
                type=UnitType.WARRIOR,
                location=escort_loc,
                health=warrior_stats.max_health,
                moves_remaining=warrior_stats.moves,
            )
        )
        uid += 1

    return GameState(turn=1, map=game_map, civs=civs, cities=(), units=tuple(units))
