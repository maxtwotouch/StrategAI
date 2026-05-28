"""Unit pipeline models — enums and Pydantic request/response schemas.

Mirrors the tile pipeline pattern: constrained enum vocabularies the client
picks from, with rich field descriptions so clients know exactly what to send.

Each unit generates a single south-facing (front view) sprite at 512×512.
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


# ===========================================================================
#  Response
# ===========================================================================

class UnitResponse(BaseModel):
    url: str                                          # "/assets/{uuid}.png"
    asset_type: str = "unit"
    unit_id: str                                      # "unit_archer_a1b2c3"
    unit_type: str
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
