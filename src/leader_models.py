"""Leader pipeline models — enums and Pydantic request/response schemas."""

from pydantic import BaseModel, Field
from typing import Optional, Literal


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

LeaderAssetType = Literal["splash", "profile", "action"]


class Archetype:
    WARRIOR_QUEEN      = "warrior_queen"
    WARRIOR_KING       = "warrior_king"
    PHILOSOPHER_KING   = "philosopher_king"
    MERCHANT_PRINCE    = "merchant_prince"
    SPIRITUAL_LEADER   = "spiritual_leader"
    DIPLOMAT           = "diplomat"
    TYRANT             = "tyrant"
    VISIONARY          = "visionary"
    ALL = {
        WARRIOR_QUEEN, WARRIOR_KING, PHILOSOPHER_KING, MERCHANT_PRINCE,
        SPIRITUAL_LEADER, DIPLOMAT, TYRANT, VISIONARY,
    }


class Culture:
    ANCIENT_EGYPTIAN      = "ancient_egyptian"
    CLASSICAL_GREEK        = "classical_greek"
    ROMAN_IMPERIAL         = "roman_imperial"
    MEDIEVAL_EUROPEAN      = "medieval_european"
    EAST_ASIAN_IMPERIAL    = "east_asian_imperial"
    MESOPOTAMIAN           = "mesopotamian"
    MESOAMERICAN           = "mesoamerican"
    NORDIC_VIKING          = "nordic_viking"
    PERSIAN                = "persian"
    SUB_SAHARAN_AFRICAN    = "sub_saharan_african"
    SOUTH_ASIAN            = "south_asian"
    ISLAMIC_GOLDEN_AGE     = "islamic_golden_age"
    ALL = {
        ANCIENT_EGYPTIAN, CLASSICAL_GREEK, ROMAN_IMPERIAL, MEDIEVAL_EUROPEAN,
        EAST_ASIAN_IMPERIAL, MESOPOTAMIAN, MESOAMERICAN, NORDIC_VIKING,
        PERSIAN, SUB_SAHARAN_AFRICAN, SOUTH_ASIAN, ISLAMIC_GOLDEN_AGE,
    }


class TimeOfDay:
    DAWN         = "dawn"
    GOLDEN_HOUR  = "golden_hour"
    MIDDAY       = "midday"
    TWILIGHT     = "twilight"
    NIGHT        = "night"
    STORM        = "storm"
    ALL = {DAWN, GOLDEN_HOUR, MIDDAY, TWILIGHT, NIGHT, STORM}


class Mood:
    TRIUMPHANT       = "triumphant"
    WISE_SERENE      = "wise_serene"
    GRIM_DETERMINED  = "grim_determined"
    MYSTICAL         = "mystical"
    MELANCHOLIC      = "melancholic"
    MENACING         = "menacing"
    HOPEFUL          = "hopeful"
    CONTEMPLATIVE    = "contemplative"
    ALL = {
        TRIUMPHANT, WISE_SERENE, GRIM_DETERMINED, MYSTICAL,
        MELANCHOLIC, MENACING, HOPEFUL, CONTEMPLATIVE,
    }


class ActionCategory:
    MILITARY      = "military"
    DIPLOMATIC    = "diplomatic"
    CONSTRUCTION  = "construction"
    SCIENTIFIC    = "scientific"
    CULTURAL      = "cultural"
    EXPLORATION   = "exploration"
    CRISIS        = "crisis"
    ALL = {MILITARY, DIPLOMATIC, CONSTRUCTION, SCIENTIFIC, CULTURAL, EXPLORATION, CRISIS}


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class LeaderRequest(BaseModel):
    """Flat request model matching the style of GenerationRequest and SplashRequest."""

    asset_type: LeaderAssetType = Field(
        ...,
        description="Pipeline stage: 'splash', 'profile', or 'action'",
    )

    # --- Character identity ---
    leader_name: str = Field(
        ...,
        max_length=100,
        description="Human-readable leader name, e.g. 'Cleopatra VII'",
    )
    leader_description: str = Field(
        ...,
        min_length=50,
        max_length=800,
        description=(
            "Physical description: age, build, skin tone, hair, eyes, "
            "distinctive features (scar, tattoo, jewelry), clothing materials "
            "and colors, expression and bearing. No camera directions or style words."
        ),
    )

    # --- Enum-driven prompt parameters ---
    archetype: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(Archetype.ALL))}",
    )
    culture: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(Culture.ALL))}",
    )
    time_of_day: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(TimeOfDay.ALL))}",
    )
    mood: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(Mood.ALL))}",
    )

    # --- Profile/Action only ---
    leader_id: Optional[str] = Field(
        default=None,
        description="Required for profile and action. The leader_id from a previous splash generation.",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Override the canonical splash seed. Defaults to the stored splash seed for profile/action.",
    )

    # --- Action only ---
    action_category: Optional[str] = Field(
        default=None,
        description=f"Required for action. One of: {', '.join(sorted(ActionCategory.ALL))}",
    )
    action_description: Optional[str] = Field(
        default=None,
        max_length=800,
        description="What is happening in this scene. Single moment, single action. Required for action.",
    )


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class LeaderResponse(BaseModel):
    """Flat response matching GenerationResponse and SplashResponse conventions."""

    url: str                                          # "/assets/{uuid}.png"
    asset_type: str                                   # "splash" | "profile" | "action"
    leader_name: str
    leader_id: str                                    # returned so clients can chain calls
    seed: int                                         # actual seed used
    generation_mode: str                              # "comfyui" | "placeholder"
    status: str = "completed"                         # matching existing convention
    prompt_used: Optional[str] = None                 # full rendered prompt (transparency)
    resolution: Optional[str] = None                  # "1920x1088" or "1024x1024"
    generation_time_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Leader summary (for list endpoints)
# ---------------------------------------------------------------------------

class LeaderInfo(BaseModel):
    leader_id: str
    leader_name: str
    archetype: str
    culture: str
    splash_url: Optional[str] = None                  # "/assets/{uuid}.png"
    profile_url: Optional[str] = None                 # "/assets/{uuid}.png"
    action_urls: list[str] = []                       # multiple action scenes
    splash_seed: Optional[int] = None
    created_at: Optional[str] = None
