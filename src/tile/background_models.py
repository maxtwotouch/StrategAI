"""Background tile models — Pydantic request/response schemas.

Background tiles are seamless repeating ground textures (water, grass, sand,
stone, dirt).  Unlike structure/object/terrain tiles, background tiles fill
the entire frame with no white background isolation and use a separate
ComfyUI workflow (``background_tile.json``) without the top-down LoRA.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional

# ===========================================================================
#  Valid tile types
# ===========================================================================

VALID_TILE_TYPES = {"water", "grass", "sand", "stone", "dirt"}


# ===========================================================================
#  Request
# ===========================================================================

class BackgroundTileRequest(BaseModel):
    tile_type: str = Field(
        ...,
        description=f"Ground texture type. One of: {', '.join(sorted(VALID_TILE_TYPES))}",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Deterministic seed for reproducibility. Random if omitted.",
    )

    @field_validator("tile_type")
    @classmethod
    def validate_tile_type(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_TILE_TYPES:
            raise ValueError(
                f"Unknown tile_type '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_TILE_TYPES))}"
            )
        return v


# ===========================================================================
#  Response
# ===========================================================================

class BackgroundTileResponse(BaseModel):
    url: str                                          # "/assets/{uuid}.png"
    asset_type: str = "background_tile"
    background_tile_id: str                           # UUID-based ID
    tile_type: str
    seed: int
    generation_mode: str                              # "comfyui" | "static" | "placeholder"
    status: str = "completed"
    prompt_used: Optional[str] = None
    resolution: Optional[str] = None                  # "128x128"
    generation_time_ms: Optional[int] = None


# ===========================================================================
#  Catalog response
# ===========================================================================

class BackgroundTileCatalog(BaseModel):
    tile_types: list[str]
