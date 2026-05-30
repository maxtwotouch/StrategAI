"""Tile pipeline models — enums and Pydantic request/response schemas.

Three pipelines: structure, object, terrain. Each mirrors the leader
pipeline pattern: constrained enum vocabularies the client picks from,
with rich field descriptions so clients know exactly what to send.
"""

from enum import Enum
from pydantic import BaseModel, Field, field_validator
from typing import Optional


# ===========================================================================
#  Structure enums
# ===========================================================================

class StructureCategory(str, Enum):
    FORTIFICATION = "fortification"
    PRODUCTION    = "production"
    HOUSING       = "housing"
    SACRED        = "sacred"


class StructureStyle(str, Enum):
    NORDIC_WOODEN      = "nordic_wooden"
    ANGLO_SAXON_STONE  = "anglo_saxon_stone"
    NORMAN_ROMANESQUE  = "norman_romanesque"
    GOTHIC             = "gothic"
    MEDITERRANEAN      = "mediterranean"
    SLAVIC_TIMBER      = "slavic_timber"
    MOORISH            = "moorish"


class StructureCondition(str, Enum):
    PRISTINE            = "pristine"
    WEATHERED           = "weathered"
    RUINED              = "ruined"
    UNDER_CONSTRUCTION  = "under_construction"
    FORTIFIED           = "fortified"


class StructureScale(str, Enum):
    SMALL  = "small"
    MEDIUM = "medium"
    LARGE  = "large"


# ===========================================================================
#  Object enums
# ===========================================================================

class ObjectCategory(str, Enum):
    VEGETATION   = "vegetation"
    GEOLOGICAL   = "geological"
    RURAL_PROPS  = "rural_props"
    URBAN_PROPS  = "urban_props"
    DEBRIS       = "debris"


class Biome(str, Enum):
    TEMPERATE_FOREST = "temperate_forest"
    TAIGA            = "taiga"
    DESERT           = "desert"
    SWAMP            = "swamp"
    MOUNTAIN         = "mountain"
    COASTAL          = "coastal"
    GRASSLAND        = "grassland"


class Season(str, Enum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


# ===========================================================================
#  Terrain enums
# ===========================================================================

class TerrainCategory(str, Enum):
    HILL       = "hill"
    SLOPE      = "slope"
    CLIFF      = "cliff"
    RIDGE      = "ridge"
    DEPRESSION = "depression"


class TerrainScale(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class TerrainMaterial(str, Enum):
    EARTHEN = "earthen"
    SANDY   = "sandy"
    ROCKY   = "rocky"
    SNOWY   = "snowy"
    MUDDY   = "muddy"


# ===========================================================================
#  Request models
# ===========================================================================

class StructureRequest(BaseModel):
    category: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(e.value for e in StructureCategory))}",
    )
    style: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(e.value for e in StructureStyle))}",
    )
    condition: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(e.value for e in StructureCondition))}",
    )
    scale: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(e.value for e in StructureScale))}",
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

    @field_validator("category")
    @classmethod
    def _check_category(cls, v: str) -> str:
        valid = {e.value for e in StructureCategory}
        if v not in valid:
            raise ValueError(f"Unknown category '{v}'. Must be one of: {', '.join(sorted(valid))}")
        return v

    @field_validator("style")
    @classmethod
    def _check_style(cls, v: str) -> str:
        valid = {e.value for e in StructureStyle}
        if v not in valid:
            raise ValueError(f"Unknown style '{v}'. Must be one of: {', '.join(sorted(valid))}")
        return v

    @field_validator("condition")
    @classmethod
    def _check_condition(cls, v: str) -> str:
        valid = {e.value for e in StructureCondition}
        if v not in valid:
            raise ValueError(f"Unknown condition '{v}'. Must be one of: {', '.join(sorted(valid))}")
        return v

    @field_validator("scale")
    @classmethod
    def _check_scale(cls, v: str) -> str:
        valid = {e.value for e in StructureScale}
        if v not in valid:
            raise ValueError(f"Unknown scale '{v}'. Must be one of: {', '.join(sorted(valid))}")
        return v

    @field_validator("description")
    @classmethod
    def _strip_description(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 20:
            raise ValueError("description must be at least 20 characters after stripping whitespace")
        return stripped


class ObjectRequest(BaseModel):
    category: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(e.value for e in ObjectCategory))}",
    )
    biome: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(e.value for e in Biome))}",
    )
    season: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(e.value for e in Season))}",
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

    @field_validator("category")
    @classmethod
    def _check_category(cls, v: str) -> str:
        valid = {e.value for e in ObjectCategory}
        if v not in valid:
            raise ValueError(f"Unknown category '{v}'. Must be one of: {', '.join(sorted(valid))}")
        return v

    @field_validator("biome")
    @classmethod
    def _check_biome(cls, v: str) -> str:
        valid = {e.value for e in Biome}
        if v not in valid:
            raise ValueError(f"Unknown biome '{v}'. Must be one of: {', '.join(sorted(valid))}")
        return v

    @field_validator("season")
    @classmethod
    def _check_season(cls, v: str) -> str:
        valid = {e.value for e in Season}
        if v not in valid:
            raise ValueError(f"Unknown season '{v}'. Must be one of: {', '.join(sorted(valid))}")
        return v

    @field_validator("description")
    @classmethod
    def _strip_description(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 20:
            raise ValueError("description must be at least 20 characters after stripping whitespace")
        return stripped


class TerrainRequest(BaseModel):
    category: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(e.value for e in TerrainCategory))}",
    )
    scale: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(e.value for e in TerrainScale))}",
    )
    material: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(e.value for e in TerrainMaterial))}",
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

    @field_validator("category")
    @classmethod
    def _check_category(cls, v: str) -> str:
        valid = {e.value for e in TerrainCategory}
        if v not in valid:
            raise ValueError(f"Unknown category '{v}'. Must be one of: {', '.join(sorted(valid))}")
        return v

    @field_validator("scale")
    @classmethod
    def _check_scale(cls, v: str) -> str:
        valid = {e.value for e in TerrainScale}
        if v not in valid:
            raise ValueError(f"Unknown scale '{v}'. Must be one of: {', '.join(sorted(valid))}")
        return v

    @field_validator("material")
    @classmethod
    def _check_material(cls, v: str) -> str:
        valid = {e.value for e in TerrainMaterial}
        if v not in valid:
            raise ValueError(f"Unknown material '{v}'. Must be one of: {', '.join(sorted(valid))}")
        return v

    @field_validator("description")
    @classmethod
    def _strip_description(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 20:
            raise ValueError("description must be at least 20 characters after stripping whitespace")
        return stripped


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
    description: str = ""                             # the description that was submitted
    seed: int
    generation_mode: str
    status: str = "completed"
    prompt_used: Optional[str] = None
    resolution: Optional[str] = None                  # "128x128"
    generation_time_ms: Optional[int] = None


class ObjectResponse(BaseModel):
    url: str
    asset_type: str = "object"
    asset_id: str                                     # "object_vegetation_a1b2c3"
    category: str
    biome: str
    season: str
    description: str = ""                             # the description that was submitted
    seed: int
    generation_mode: str
    status: str = "completed"
    prompt_used: Optional[str] = None
    resolution: Optional[str] = None                  # "128x128"
    generation_time_ms: Optional[int] = None


class TerrainResponse(BaseModel):
    url: str
    asset_type: str = "terrain"
    asset_id: str                                     # "terrain_hill_a1b2c3"
    category: str
    scale: str
    material: str
    description: str = ""                             # the description that was submitted
    seed: int
    generation_mode: str
    status: str = "completed"
    prompt_used: Optional[str] = None
    resolution: Optional[str] = None                  # "128x128"
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