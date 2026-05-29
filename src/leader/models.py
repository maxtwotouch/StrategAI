"""Leader pipeline models — enums and Pydantic request/response schemas."""

from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Literal


# ---------------------------------------------------------------------------
# Enums (proper str, Enum subclasses so Pydantic can validate)
# ---------------------------------------------------------------------------

LeaderAssetType = Literal["splash", "profile", "action"]


class Archetype(str, Enum):
    WARRIOR_QUEEN      = "warrior_queen"
    WARRIOR_KING       = "warrior_king"
    PHILOSOPHER_KING   = "philosopher_king"
    MERCHANT_PRINCE    = "merchant_prince"
    SPIRITUAL_LEADER   = "spiritual_leader"
    DIPLOMAT           = "diplomat"
    TYRANT             = "tyrant"
    VISIONARY          = "visionary"


class Culture(str, Enum):
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


class TimeOfDay(str, Enum):
    DAWN         = "dawn"
    GOLDEN_HOUR  = "golden_hour"
    MIDDAY       = "midday"
    TWILIGHT     = "twilight"
    NIGHT        = "night"
    STORM        = "storm"


class Mood(str, Enum):
    TRIUMPHANT       = "triumphant"
    WISE_SERENE      = "wise_serene"
    GRIM_DETERMINED  = "grim_determined"
    MYSTICAL         = "mystical"
    MELANCHOLIC      = "melancholic"
    MENACING         = "menacing"
    HOPEFUL          = "hopeful"
    CONTEMPLATIVE    = "contemplative"


class ActionCategory(str, Enum):
    MILITARY      = "military"
    DIPLOMATIC    = "diplomatic"
    CONSTRUCTION  = "construction"
    SCIENTIFIC    = "scientific"
    CULTURAL      = "cultural"
    EXPLORATION   = "exploration"
    CRISIS        = "crisis"


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
        min_length=1,
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
        description=f"One of: {', '.join(sorted(e.value for e in Archetype))}",
    )
    culture: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(e.value for e in Culture))}",
    )
    time_of_day: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(e.value for e in TimeOfDay))}",
    )
    mood: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(e.value for e in Mood))}",
    )

    # --- Profile/Action only ---
    leader_id: Optional[str] = Field(
        default=None,
        description="Required for profile and action. The leader_id from a previous splash generation.",
    )
    leader_ids: Optional[list[str]] = Field(
        default=None,
        description="Required for multi-leader action scenes. List of leader_ids to include in the scene. "
                    "When provided, leader_id is ignored for action generation.",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Override the canonical splash seed. Defaults to the stored splash seed for profile/action.",
    )

    # --- Action only ---
    action_category: Optional[str] = Field(
        default=None,
        description=f"Required for action. One of: {', '.join(sorted(e.value for e in ActionCategory))}",
    )
    action_description: Optional[str] = Field(
        default=None,
        max_length=800,
        description="What is happening in this scene. Single moment, single action. Required for action.",
    )

    # ------------------------------------------------------------------
    #  Validators
    # ------------------------------------------------------------------

    @field_validator("archetype")
    @classmethod
    def _check_archetype(cls, v: str) -> str:
        valid = {e.value for e in Archetype}
        if v not in valid:
            raise ValueError(
                f"Unknown archetype '{v}'. Must be one of: {', '.join(sorted(valid))}"
            )
        return v

    @field_validator("culture")
    @classmethod
    def _check_culture(cls, v: str) -> str:
        valid = {e.value for e in Culture}
        if v not in valid:
            raise ValueError(
                f"Unknown culture '{v}'. Must be one of: {', '.join(sorted(valid))}"
            )
        return v

    @field_validator("time_of_day")
    @classmethod
    def _check_time_of_day(cls, v: str) -> str:
        valid = {e.value for e in TimeOfDay}
        if v not in valid:
            raise ValueError(
                f"Unknown time_of_day '{v}'. Must be one of: {', '.join(sorted(valid))}"
            )
        return v

    @field_validator("mood")
    @classmethod
    def _check_mood(cls, v: str) -> str:
        valid = {e.value for e in Mood}
        if v not in valid:
            raise ValueError(
                f"Unknown mood '{v}'. Must be one of: {', '.join(sorted(valid))}"
            )
        return v

    @field_validator("action_category")
    @classmethod
    def _check_action_category(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid = {e.value for e in ActionCategory}
        if v not in valid:
            raise ValueError(
                f"Unknown action_category '{v}'. Must be one of: {', '.join(sorted(valid))}"
            )
        return v

    @field_validator("leader_name")
    @classmethod
    def _strip_leader_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("leader_name must not be empty or whitespace-only")
        return stripped

    @field_validator("leader_description", "action_description")
    @classmethod
    def _strip_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip()

    @model_validator(mode="after")
    def _validate_action_fields(self) -> "LeaderRequest":
        """Ensure action_category and action_description are present for action assets."""
        if self.asset_type == "action":
            if not self.action_category:
                raise ValueError("action_category is required when asset_type='action'")
            if not self.action_description:
                raise ValueError("action_description is required when asset_type='action'")
            # If using single-leader action (not multi-leader), leader_id is required
            if self.leader_ids is None and not self.leader_id:
                raise ValueError(
                    "leader_id or leader_ids is required when asset_type='action'"
                )
        return self


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class LeaderResponse(BaseModel):
    """Flat response matching GenerationResponse and SplashResponse conventions."""

    url: str                                          # "/assets/{uuid}.png"
    asset_type: str                                   # "splash" | "profile" | "action"
    leader_name: str
    leader_id: str                                    # returned so clients can chain calls
    leader_ids: list[str] = []                        # all leader IDs in this scene (multi-leader action)
    leader_names: list[str] = []                      # all leader names in this scene
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