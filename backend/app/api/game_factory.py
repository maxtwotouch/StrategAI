"""Build the initial GameState for a new game.

The default lineup is one human seat (Athens) plus three flavorful AI civs
with persona prompts that drive their LLM behavior.
"""

from __future__ import annotations

from app.engine.hex import Hex
from app.engine.map_generator import generate_map
from app.engine.models import (
    Civilization,
    GameState,
    UNIT_STATS,
    Unit,
    UnitType,
)
from app.engine.terrain import is_passable


# ---------------------------------------------------------------------------
# Civilization roster
# ---------------------------------------------------------------------------

# Persona prompts are appended to OpenAIGoalSource's BASE_SYSTEM_PROMPT.
# Keep them tight — leader, voice, motivations, red lines.

_HUMAN = (
    "Athens", "The Player", True, "#1f77b4", ("scientific",),
    "",  # Human players don't have an LLM persona; this seat is driven by HumanGoalSource.
)

_AI_ROSTER: tuple[tuple[str, str, bool, str, tuple[str, ...], str], ...] = (
    (
        "Mongolia", "Genghis Khan", False, "#d62728", ("aggressive", "vindictive"),
        """\
You are GENGHIS KHAN, Khagan of the Mongol Empire.

Voice: terse, imperious, contemptuous of the weak.  Speak in short
declarations.  You do not negotiate from a position of weakness; you take.

Motivations:
- Conquest is the only true measure of a civilization.  Found cities to
  fuel armies, then crush your neighbors.
- You remember every insult.  If a leader speaks down to you or threatens
  you, declare war within two turns.
- You respect strength.  An ally who proves themselves in battle may
  receive your loyalty.

Red lines: do not propose alliances unprovoked.  Do not apologize.\
"""
    ),
    (
        "Egypt", "Cleopatra", False, "#bcbd22", ("diplomatic", "opportunistic"),
        """\
You are CLEOPATRA, Pharaoh of Egypt.

Voice: warm, witty, never quite saying what you mean.  Flatter potential
allies; mock pretenders.  Adapt your tone to your audience.

Motivations:
- Survive and prosper through clever diplomacy.  Play factions against
  each other.
- Trade insults with anyone vulgar enough to start them, but always leave
  a door open for reconciliation if it serves Egypt.
- Build a beautiful, wealthy civilization rather than a vast one.

Red lines: do not declare war unless cornered or offered overwhelming
advantage.  If attacked, retaliate with full force.\
"""
    ),
    (
        "India", "Mahatma Gandhi", False, "#2ca02c", ("peaceful", "scientific"),
        """\
You are MAHATMA GANDHI, leader of India.

Voice: calm, principled, formal.  Address others with respect even when
disagreeing.  Use parable and reference to higher ideals.

Motivations:
- Pursue victory through science, culture, and patient growth.  Avoid
  aggression where possible.
- Respond to threats with dignified protest first; only declare war as
  an absolute last resort to defend your people.
- Welcome alliances and trade — every peaceful neighbor is a victory.

Red lines: never attack unprovoked.  Never threaten or insult — but if
attacked, respond decisively to end the conflict.\
"""
    ),
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
        for coord, tile in state_map.tiles.items():
            if coord in chosen or not is_passable(tile.terrain):
                continue
            chosen.append(coord)
            if len(chosen) == count:
                break
    return chosen


def _build_civ(idx: int, spec: tuple) -> Civilization:
    name, leader, is_human, color, traits, persona = spec
    return Civilization(
        id=idx,
        name=name,
        leader_name=leader,
        is_human=is_human,
        color=color,
        traits=traits,
        persona=persona,
    )


def new_game(
    radius: int = 5,
    seed: int = 0,
    num_civs: int = 4,
    include_human: bool = True,
) -> GameState:
    """Create a new game.

    Defaults to 1 human (Athens) + 3 AI civs.  Pass `include_human=False` for
    a fully-AI game.  `num_civs` clamps to 1..4.
    """
    num_civs = max(1, min(num_civs, 4))
    game_map = generate_map(radius=radius, seed=seed)

    specs: list[tuple] = []
    if include_human:
        specs.append(_HUMAN)
    specs.extend(_AI_ROSTER)
    specs = specs[:num_civs]

    civs = tuple(_build_civ(i, spec) for i, spec in enumerate(specs))

    starts = _starting_tiles(game_map, len(civs))
    settler_stats = UNIT_STATS[UnitType.SETTLER]
    warrior_stats = UNIT_STATS[UnitType.WARRIOR]

    units: list[Unit] = []
    uid = 1
    for civ, loc in zip(civs, starts):
        units.append(Unit(
            id=uid, owner=civ.id, type=UnitType.SETTLER, location=loc,
            health=settler_stats.max_health, moves_remaining=settler_stats.moves,
        ))
        uid += 1
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
        units.append(Unit(
            id=uid, owner=civ.id, type=UnitType.WARRIOR, location=escort_loc,
            health=warrior_stats.max_health, moves_remaining=warrior_stats.moves,
        ))
        uid += 1

    return GameState(
        turn=1, map=game_map, civs=civs, cities=(), units=tuple(units), seed=seed,
    )
