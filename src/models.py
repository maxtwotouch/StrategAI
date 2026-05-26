from pydantic import BaseModel, Field
from typing import Optional, List, Literal

AssetFamily = Literal[
    "structure",
    "nature_object",
    "background_tile",
    "character_sprite",
    "story",
    "splash",
]

TileType = Literal["water", "grass", "sand", "stone"]

StructureSubtype = Literal["fortification", "production", "civilian", "religious"]


class Coordinate(BaseModel):
    x: int
    y: int


class InpaintRequest(BaseModel):
    point_a: Coordinate
    point_b: Coordinate
    fill_type: str = Field(..., description="e.g., 'water', 'gravel_road'")


class GenerationRequest(BaseModel):
    asset_family: AssetFamily = Field(
        ...,
        description="Must be one of: 'structure', 'nature_object', 'background_tile', "
                    "'character_sprite', 'story', 'splash'",
    )
    tile_type: Optional[TileType] = Field(
        None,
        description="Required for background_tile. One of: 'water', 'grass', 'sand', 'stone'.",
    )
    structure_subtype: Optional[StructureSubtype] = Field(
        None,
        description="Optional for structure. One of: 'fortification', 'production', "
                    "'civilian', 'religious'. If absent, a random subtype is selected.",
    )
    prompt: Optional[str] = Field(
        None,
        description="High-level description of what to generate. "
                    "Optional if purely doing inpainting on a base file.",
    )
    base_image_id: Optional[str] = Field(
        None,
        description="ID (filename) of the base background tile to use for Copy-on-Write modifications.",
    )
    inpaints: Optional[List[InpaintRequest]] = None


class SplashRequest(BaseModel):
    """Request model for generating a leader splash art (small profile portrait)."""

    character_name: str = Field(..., description="Name of the leader/character")
    title: Optional[str] = Field(None, description="Title or rank, e.g. 'King', 'Warlord'")
    description: Optional[str] = Field(
        None,
        description="Short description of the character's appearance, gear, or personality.",
    )
    style: str = Field(
        "pixel_art",
        description="Art style for the splash. Defaults to 'pixel_art'.",
    )
    outfit: Optional[str] = Field(None, description="Description of outfit/armor.")
    weapon: Optional[str] = Field(None, description="Description of weapon held.")
    background: Optional[str] = Field(
        "solid_dark",
        description="Background style, e.g. 'solid_dark', 'banner', 'landscape'.",
    )


class GenerationResponse(BaseModel):
    url: str
    asset_family: str
    tile_type: Optional[str] = None
    generation_mode: Optional[str] = None
    status: str = "completed"


class SplashResponse(BaseModel):
    url: str
    character_name: str
    status: str = "completed"
