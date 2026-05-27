"""Tile pipeline models — enums and Pydantic request/response schemas.

Three pipelines: structure, object, terrain. Each mirrors the leader
pipeline pattern: constrained enum vocabularies the client picks from,
with rich field descriptions so clients know exactly what to send.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ===========================================================================
#  Structure enums
# ===========================================================================

class StructureCategory:
    FORTIFICATION = "fortification"
    PRODUCTION    = "production"
    HOUSING       = "housing"
    SACRED        = "sacred"
    ALL = {FORTIFICATION, PRODUCTION, HOUSING, SACRED}


class StructureStyle:
    NORDIC_WOODEN      = "nordic_wooden"
    ANGLO_SAXON_STONE  = "anglo_saxon_stone"
    NORMAN_ROMANESQUE  = "norman_romanesque"
    GOTHIC             = "gothic"
    MEDITERRANEAN      = "mediterranean"
    SLAVIC_TIMBER      = "slavic_timber"
    MOORISH            = "moorish"
    ALL = {
        NORDIC_WOODEN, ANGLO_SAXON_STONE, NORMAN_ROMANESQUE,
        GOTHIC, MEDITERRANEAN, SLAVIC_TIMBER, MOORISH,
    }


class StructureCondition:
    PRISTINE            = "pristine"
    WEATHERED           = "weathered"
    RUINED              = "ruined"
    UNDER_CONSTRUCTION  = "under_construction"
    FORTIFIED           = "fortified"
    ALL = {PRISTINE, WEATHERED, RUINED, UNDER_CONSTRUCTION, FORTIFIED}


class StructureScale:
    SMALL  = "small"
    MEDIUM = "medium"
    LARGE  = "large"
    ALL = {SMALL, MEDIUM, LARGE}


# ===========================================================================
#  Object enums
# ===========================================================================

class ObjectCategory:
    VEGETATION   = "vegetation"
    GEOLOGICAL   = "geological"
    RURAL_PROPS  = "rural_props"
    URBAN_PROPS  = "urban_props"
    DEBRIS       = "debris"
    ALL = {VEGETATION, GEOLOGICAL, RURAL_PROPS, URBAN_PROPS, DEBRIS}


class Biome:
    TEMPERATE_FOREST = "temperate_forest"
    TAIGA            = "taiga"
    DESERT           = "desert"
    SWAMP            = "swamp"
    MOUNTAIN         = "mountain"
    COASTAL          = "coastal"
    GRASSLAND        = "grassland"
    ALL = {
        TEMPERATE_FOREST, TAIGA, DESERT, SWAMP, MOUNTAIN,
        COASTAL, GRASSLAND,
    }


class Season:
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"
    ALL = {SPRING, SUMMER, AUTUMN, WINTER}


# ===========================================================================
#  Terrain enums
# ===========================================================================

class TerrainCategory:
    HILL       = "hill"
    SLOPE      = "slope"
    CLIFF      = "cliff"
    RIDGE      = "ridge"
    DEPRESSION = "depression"
    ALL = {HILL, SLOPE, CLIFF, RIDGE, DEPRESSION}


class TerrainScale:
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"
    ALL = {LOW, MEDIUM, HIGH}


class TerrainMaterial:
    EARTHEN = "earthen"
    SANDY   = "sandy"
    ROCKY   = "rocky"
    SNOWY   = "snowy"
    MUDDY   = "muddy"
    ALL = {EARTHEN, SANDY, ROCKY, SNOWY, MUDDY}


# ===========================================================================
#  Request models
# ===========================================================================

class StructureRequest(BaseModel):
    category: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(StructureCategory.ALL))}",
    )
    style: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(StructureStyle.ALL))}",
    )
    condition: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(StructureCondition.ALL))}",
    )
    scale: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(StructureScale.ALL))}",
    )
    description: str = Field(
        ...,
        min_length=20,
        max_length=400,
        description=(
            "Free-form specifics: roof material and shape, number of stories, "
            "one distinctive feature (bell tower, chimney smoke, signboard, "
            "stained glass window, portcullis, water wheel), what's around "
            "the entrance, visible activity. No camera directions or style words."
        ),
    )
    seed: Optional[int] = None


class ObjectRequest(BaseModel):
    category: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(ObjectCategory.ALL))}",
    )
    biome: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(Biome.ALL))}",
    )
    season: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(Season.ALL))}",
    )
    description: str = Field(
        ...,
        min_length=20,
        max_length=400,
        description=(
            "Free-form specifics: exact object type, material and texture cues, "
            "size relative to a person, one distinctive feature (hollow trunk, "
            "broken spoke, moss covering, carved initials, rusted metal). "
            "No camera directions or style words."
        ),
    )
    seed: Optional[int] = None


class TerrainRequest(BaseModel):
    category: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(TerrainCategory.ALL))}",
    )
    scale: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(TerrainScale.ALL))}",
    )
    material: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(TerrainMaterial.ALL))}",
    )
    description: str = Field(
        ...,
        min_length=20,
        max_length=400,
        description=(
            "Free-form specifics: shape and contour (rounded, jagged, stepped, "
            "smooth), which edges rise/fall, surface details (small rocks on "
            "top, grass tufts, snow cap), what background tile it's meant to "
            "sit on. No camera directions or style words."
        ),
    )
    seed: Optional[int] = None


# ===========================================================================
#  Response models
# ===========================================================================

class StructureResponse(BaseModel):
    url: str                                          # "/assets/{uuid}.png"
    asset_type: str = "structure"
    asset_id: str                                     # "struct_fortification_a1b2c3"
    category: str
    style: str
    condition: str
    scale: str
    seed: int
    generation_mode: str
    status: str = "completed"
    prompt_used: Optional[str] = None
    resolution: Optional[str] = None                  # "512x512"
    generation_time_ms: Optional[int] = None


class ObjectResponse(BaseModel):
    url: str
    asset_type: str = "object"
    asset_id: str                                     # "object_vegetation_a1b2c3"
    category: str
    biome: str
    season: str
    seed: int
    generation_mode: str
    status: str = "completed"
    prompt_used: Optional[str] = None
    resolution: Optional[str] = None
    generation_time_ms: Optional[int] = None


class TerrainResponse(BaseModel):
    url: str
    asset_type: str = "terrain"
    asset_id: str                                     # "terrain_hill_a1b2c3"
    category: str
    scale: str
    material: str
    seed: int
    generation_mode: str
    status: str = "completed"
    prompt_used: Optional[str] = None
    resolution: Optional[str] = None
    generation_time_ms: Optional[int] = None


# ===========================================================================
#  Catalog response models
# ===========================================================================

class StructureCatalog(BaseModel):
    categories: list[str]
    styles: list[str]
    conditions: list[str]
    scales: list[str]


class ObjectCatalog(BaseModel):
    categories: list[str]
    biomes: list[str]
    seasons: list[str]


class TerrainCatalog(BaseModel):
    categories: list[str]
    scales: list[str]
    materials: list[str]
