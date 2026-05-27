"""Unit prompt builder — direction-aware, enum-driven.

Each unit type + direction produces a distinct pixel-art prompt suitable for
txt2img generation of top-down game sprites.  The prompt is designed to work
with the same txt2img.json workflow used by structure/object/terrain.
"""

from .unit_models import UnitType, Direction


# ===========================================================================
#  Direction prompts — describes how the sprite faces the camera
# ===========================================================================

_DIRECTION_PROMPTS: dict[str, str] = {
    Direction.SOUTH: "facing camera, front view, full frontal, character looks at viewer",
    Direction.NORTH: "facing away from camera, back view, seen from behind",
    Direction.EAST:  "facing right, side profile, walking rightwards",
    Direction.WEST:  "facing left, side profile, walking leftwards",
}


# ===========================================================================
#  Unit type prompts — describes the character archetype
# ===========================================================================

_UNIT_PROMPTS: dict[str, str] = {
    UnitType.ARCHER: (
        "medieval archer, bow in hand, quiver on back, leather armor, "
        "hooded cloak, light build, ranged combat stance"
    ),
    UnitType.SCOUT: (
        "medieval scout, light leather armor, running pose, small dagger at belt, "
        "hood, lean build, fast agile movement, reconnaissance stance"
    ),
    UnitType.SETTLER: (
        "medieval settler, civilian clothes, wool tunic, carrying bundle of "
        "supplies on shoulder, walking stick, non-combatant, humble appearance"
    ),
    UnitType.WARRIOR: (
        "medieval warrior, heavy plate armor, shield on arm, longsword, "
        "helmet with visor or nasal guard, stocky build, battle-ready stance"
    ),
}


# ===========================================================================
#  Public API
# ===========================================================================

def build_unit_prompt(unit_type: str, direction: str, description: str) -> str:
    """Build a rich txt2img prompt from unit type, direction, and free-form description.

    Parameters
    ----------
    unit_type : str
        One of ``UnitType.ALL`` — "archer", "scout", "settler", "warrior".
    direction : str
        One of ``Direction.ALL`` — "s", "n", "e", "w".
    description : str
        Free-form specifics provided by the client (clothing colour, weapon
        details, posture, distinctive features, build, etc.).

    Returns
    -------
    str
        A comma-separated prompt string ready for txt2img injection.
    """
    unit_desc = _UNIT_PROMPTS.get(unit_type, "medieval character sprite")
    dir_desc = _DIRECTION_PROMPTS.get(direction, "front view")

    parts = [
        "pixel art top-down 2d game character sprite",
        unit_desc,
        dir_desc,
        description,
        "isolated on transparent background",
        "crisp pixel edges, no anti-aliasing",
        "centered single sprite, game asset",
    ]

    return ", ".join(p for p in parts if p)
