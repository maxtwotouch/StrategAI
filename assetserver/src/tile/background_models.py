"""Background tile models — Pydantic request/response schemas.

Background tiles are seamless repeating ground textures (water, grass, sand,
stone, dirt).  Unlike structure/object/terrain tiles, background tiles fill
the entire frame with no white background isolation and use a separate
ComfyUI workflow (``background_tile.json``) without the top-down LoRA.
"""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

# ===========================================================================
#  Tile type enum
# ===========================================================================


class TileType(str, Enum):
    WATER = "water"
    GRASS = "grass"
    SAND = "sand"
    STONE = "stone"
    DIRT = "dirt"


# ===========================================================================
#  Request
# ===========================================================================

class BackgroundTileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tile_type: TileType = Field(
        ...,
        description=f"Ground texture type. One of: {', '.join(sorted(e.value for e in TileType))}",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Deterministic seed for reproducibility. Random if omitted.",
    )


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
