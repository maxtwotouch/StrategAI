"""Unit pipeline models — enums and Pydantic request/response schemas.

Mirrors the tile pipeline pattern: constrained enum vocabularies the client
picks from, with rich field descriptions so clients know exactly what to send.

Each unit has up to 4 directional facings (s/n/e/w).  The south (front)
facing is canonical; missing directions fall back to the south image.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ===========================================================================
#  Unit type enum
# ===========================================================================

class UnitType:
    ARCHER  = "archer"
    SCOUT   = "scout"
    SETTLER = "settler"
    WARRIOR = "warrior"
    ALL = {ARCHER, SCOUT, SETTLER, WARRIOR}


# ===========================================================================
#  Direction enum
# ===========================================================================

class Direction:
    SOUTH = "s"   # canonical / fallback — character faces camera (front view)
    NORTH = "n"   # character faces away (back view)
    EAST  = "e"   # character faces right
    WEST  = "w"   # character faces left
    ALL = {SOUTH, NORTH, EAST, WEST}


# ===========================================================================
#  Request
# ===========================================================================

class UnitRequest(BaseModel):
    unit_type: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(UnitType.ALL))}",
    )
    description: str = Field(
        ...,
        min_length=20,
        max_length=400,
        description=(
            "Free-form specifics: clothing colour and material, weapon details, "
            "posture and stance, distinctive feature (crest on shield, feathered "
            "cap, hood, scar), build (lean/stocky). No camera directions or style words."
        ),
    )
    seed: Optional[int] = None
    direction: Optional[str] = Field(
        default=None,
        description=(
            "Single direction to generate: 's' (south/front), 'n' (north/back), "
            "'e' (east/right), or 'w' (west/left). When omitted, all 4 directions "
            "are generated.  Use 's' for fast single-face generation."
        ),
    )


# ===========================================================================
#  Response
# ===========================================================================

class UnitDirections(BaseModel):
    """URLs for each cardinal-facing sprite.  n/e/w may be null when only a single
    direction was requested (s is always present)."""
    s: str                                # south / front (always present)
    n: Optional[str] = None               # north / back  (None if not generated)
    e: Optional[str] = None               # east / right  (None if not generated)
    w: Optional[str] = None               # west / left   (None if not generated)


class UnitResponse(BaseModel):
    url: str                                          # "/assets/{uuid}.png"  (south-facing)
    asset_type: str = "unit"
    unit_id: str                                      # "unit_archer_a1b2c3"
    unit_type: str
    directions: UnitDirections
    generated_directions: list[str] = ["s", "n", "e", "w"]   # e.g. ["s"] when only south generated
    seed: int
    generation_mode: str                              # "comfyui" | "static" | "placeholder"
    status: str = "completed"
    prompt_used: Optional[str] = None
    resolution: Optional[str] = None                  # "512x512"
    generation_time_ms: Optional[int] = None


# ===========================================================================
#  Catalog response
# ===========================================================================

class UnitCatalog(BaseModel):
    unit_types: list[str]
    directions: list[str]
