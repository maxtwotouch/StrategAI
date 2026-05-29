"""Unit prompt builder — enum-driven.

Each unit type produces a distinct pixel-art prompt suitable for
txt2img generation of top-down game sprites.  The prompt is designed to work
with the same txt2img.json workflow used by structure/object/terrain.

All sprites are south-facing (front view) — the canonical game-facing direction.

Prompt templates (prefix + suffix) live in ``config/prompt_templates.json``.
This module only contributes the enum injection map and assembly logic.
"""

from src.prompt_templates import assemble as _assemble
from .models import UnitType


# ===========================================================================
#  Unit type injection map — describes the character archetype
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

def build_unit_prompt(unit_type: str, description: str) -> str:
    """Build a rich txt2img prompt from unit type and free-form description.

    The template (prefix: <tdp> trigger + style direction, suffix: format
    constraints) is loaded from ``config/prompt_templates.json``.  This
    function only contributes the unit archetype prose and user description.

    Parameters
    ----------
    unit_type : str
        One of the ``UnitType`` enum values — "archer", "scout", "settler", "warrior".
    description : str
        Free-form specifics provided by the client (clothing colour, weapon
        details, posture, distinctive features, build, etc.).

    Returns
    -------
    str
        A complete prompt string ready for txt2img injection.
    """
    unit_desc = _UNIT_PROMPTS.get(unit_type, "medieval character sprite")

    # Inner prose: archetype description + user-provided specifics
    inner = f"{unit_desc}, {description}"

    return _assemble("unit", inner)
