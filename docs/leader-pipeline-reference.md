# Leader Pipeline: Implementation Reference

> **Status:** Implemented  
> **Date:** May 2026  
> **See also:** [`architecture.md`](./architecture.md) for system overview, [`leader-prompt-guide.md`](./leader-prompt-guide.md) for API consumers.

---

## Table of Contents

1. [Design Philosophy & Deviation from Guide](#1-design-philosophy--deviation-from-guide)
2. [Phase 0: File Change Inventory](#2-phase-0-file-change-inventory)
3. [Phase 1: Foundation — Models, Config, Database](#3-phase-1-foundation--models-config-database)
4. [Phase 2: Prompt Engine](#4-phase-2-prompt-engine)
5. [Phase 3: Leader Registry (SQLite-backed)](#5-phase-3-leader-registry-sqlite-backed)
6. [Phase 4: Workflow JSON Templates](#6-phase-4-workflow-json-templates)
7. [Phase 5: ComfyUI Client Extensions](#7-phase-5-comfyui-client-extensions)
8. [Phase 6: Leader Engine (Orchestrator)](#8-phase-6-leader-engine-orchestrator)
9. [Phase 7: API Endpoints in main.py](#9-phase-7-api-endpoints-in-mainpy)
10. [Phase 8: Production Polish](#10-phase-8-production-polish)
11. [Phase 9: Integration Tests](#11-phase-9-integration-tests)
12. [Phase 10: Documentation & Final Checklist](#12-phase-10-documentation--final-checklist)
13. [Complete API Contract](#13-complete-api-contract)
14. [Final File System Layout](#14-final-file-system-layout)

---

## 1. Design Philosophy & Deviation from Guide

### What we keep from the guide

| Concept | Rationale |
|---------|-----------|
| Three-stage pipeline (splash → profile → action) | Splash establishes canonical visual identity; profile/action use img2img to preserve character consistency |
| Structured enum → prompt injection | Archetype, Culture, TimeOfDay, Mood, ActionCategory as discrete enums mapping to hand-crafted prose. Guarantees quality and consistency across all leaders |
| Single reference image as canonical identity | Splash copied to `ref_{leader_id}.png`, re-uploaded before each profile/action generation |
| Prompt engine builds prompts server-side | Clients never write raw prompts; they pick structured enums |
| Seed persistence | Canonical splash seed stored for profile/action regeneration consistency |

### Redundancy Audit: Workflow JSON as Source of Truth

**Principle:** If a parameter never changes for a given `asset_type`, it belongs in the workflow JSON — not in config.py or the engine's `extra_overrides`. The engine should only inject what changes per-request. Only parameters that are **shared across all three workflows** and we expect to **iterate on frequently** (without re-exporting from ComfyUI each time) belong in config.py.

| Parameter | Original location | **Final location** | Why |
|-----------|-------------------|---------------------|-----|
| Resolution (width/height) | config.py + engine `width=`/`height=` params | **Workflow JSON** (`EmptyLatentImage` inputs) | Per-workflow, never changes for a given asset_type |
| Denoise (1.0 / 0.30 / 0.60) | config.py + engine `extra_overrides` | **Workflow JSON** (`KSampler.denoise`) | Per-workflow, tuned once in ComfyUI |
| Steps (8) | config.py + engine `extra_overrides` | **Workflow JSON** (`KSampler.steps`) | Per-workflow |
| CFG (1.8) | config.py + engine `extra_overrides` | **Workflow JSON** (`KSampler.cfg`) | Per-workflow |
| Sampler (euler) | config.py | **Workflow JSON** (`KSampler.sampler_name`) | Per-workflow |
| Scheduler (beta) | config.py | **Workflow JSON** (`KSampler.scheduler`) | Per-workflow |
| SaveImage filename_prefix | engine `extra_overrides` | **Workflow JSON** | Per-workflow, never changes |
| LoRA strength (0.75) | config.py | **Workflow JSON** (`LoraLoaderModelOnly.strength`) | Model configuration |
| Model filenames | config.py | **Workflow JSON** (loaders) | ComfyUI model paths |
| **Negative prompt** | config.py + engine parameter | **config.py** `leader_negative_prompt` | **Shared across all three workflows.** One edit affects all. Keeping in JSON means re-exporting three workflows for every prompt tweak — unacceptable friction during iteration. |
| Positive prompt | Engine (per-request) | **Engine** | Changes every request — different leader, different enums |
| Seed | Engine (per-request) | **Engine** | Changes per request |
| LoadImage filename (`ref_{id}.png`) | Engine (per-leader) | **Engine** | Per-leader |
| Uploaded image bytes | Engine (per-request) | **Engine** | The actual PNG data |

**Net reduction in config.py:** 14 settings → 3 settings. **Net reduction in engine `generate()` parameters:** `width`, `height`, and all `extra_overrides` (denoise, steps, cfg, filename_prefix) eliminated. **Net reduction in `_patch_workflow()` changes needed:** the planned denoise/steps/cfg/SaveImage override logic is NOT needed — undo that part of the plan.

### What the engine actually injects per request

```
Splash:             positive_prompt + seed
Profile:            positive_prompt + seed + negative_prompt (from config) + ref image upload + LoadImage filename
Action (single):    positive_prompt + seed + negative_prompt (from config) + ref image upload + LoadImage filename
Action (multi):     positive_prompt + seed + negative_prompt (from config)   [txt2img — no ref image]
```

Multi-leader action scenes run as **txt2img** because ComfyUI can only accept one reference image for img2img, but the scene must depict multiple distinct leaders. Character consistency is achieved by weaving all leader descriptions (from their splash records) into a single composite prompt via `build_multi_action_prompt()`.

Everything else — resolution, denoise, steps, cfg, sampler, scheduler, model paths, LoRA strength, output prefix — is baked into the workflow JSONs, tested in ComfyUI, and version-controlled.

### Where we deviate

| Guide Says | We Do | Why |
|------------|-------|-----|
| Separate `/opt/civ-leader-api/` FastAPI app | Integrate into existing server in `src/` | One operational surface, reuses AssetStore, SQLite, CORS, error handling |
| One monolithic workflow JSON with disconnected nodes | Three clean, separate workflow JSONs | No brittle link surgery at runtime; each workflow is independently testable in ComfyUI |
| JSON file `leaders.json` for registry | SQLite `leader_records` table + SQLAlchemy | No file-write race conditions; queryable; joins with `asset_records` |
| FLUX.1-dev as the only model | Model-agnostic; SDXL Turbo default, FLUX configurable via workflow JSON | Your existing workflows use SDXL Turbo (4-8 steps, 8GB VRAM). FLUX is ~18GB. Support both |
| Blocking `requests` + `websocket` | Existing blocking client already works; async variant planned for Phase 8 | Thread pool handles blocking calls today; no need to break existing patterns |
| Hardcoded `/opt/comfyui/output` paths | Use existing `AssetStore` and `settings` | All images flow through the same cache + disk pipeline as tiles |
| No leader_id in response until splash completes | `leader_id` is deterministic: `leader_{slugified_name}_{short_uuid}` | Client can know the ID before splash completes; useful for UI pre-allocation |
| 120s timeout | Configurable `comfyui_timeout` (default 300s) | Matches existing config pattern |

### API design: compatibility with existing surface

The existing API has these conventions we must follow:

| Convention | Example |
|------------|---------|
| Terse, verb-free paths | `POST /generate`, `POST /splash`, `GET /catalog` |
| Flat request models (no deep nesting) | `GenerationRequest` with optional fields gated by `asset_family` |
| Responses always include `status: "completed"` | `GenerationResponse`, `SplashResponse` |
| Asset URLs are relative paths | `"/assets/{uuid}.png"` |
| `GET /assets/{filename}` serves all families | Single endpoint for all images |
| `HTTPException(code, detail_string)` for errors | `raise HTTPException(400, "tile_type is required")` |
| Blocking generation in `ThreadPoolExecutor` | `await loop.run_in_executor(_executor, generator.generate, request)` |
| Every generated image gets an `AssetRecord` row | SQLite tracking |
| `GET /health` returns system state | `{status, comfyui_connected, modes: {...}}` |

Our leader endpoints are:

| Endpoint | Parallels | Purpose |
|----------|-----------|---------|
| `POST /leader` | `POST /generate`, `POST /splash` | Generate leader asset |
| `GET /leader` | `GET /catalog` | List all registered leaders |
| `GET /leader/{leader_id}` | `GET /assets/{filename}` | Get one leader's info |
| `DELETE /leader/{leader_id}` | *(new pattern)* | Remove leader + all assets |

The `LeaderRequest` is deliberately **flat** (matching `GenerationRequest` and `SplashRequest`). The key design choice: `asset_type` (splash/profile/action) is NOT the same as `asset_family` (structure/nature_object/background_tile/…). A leader is a person crossing three pipeline stages; a tile is a thing in one category. These are orthogonal concepts, so they get different field names.

---

## 2. Phase 0: File Change Inventory

| File | Action | Phase |
|------|--------|-------|
| `src/leader_models.py` | **New** | 1 |
| `src/leader_prompts.py` | **New** | 2 |
| `src/leader_registry.py` | **New** | 3 |
| `src/leader_engine.py` | **New** | 6 |
| `workflows/leader/leader_splash.json` | **New** | 4 |
| `workflows/leader/leader_profile.json` | **New** | 4 |
| `workflows/leader/leader_action.json` | **New** | 4 |
| `tests/test_leader_pipeline.py` | **New** | 9 |
| `src/config.py` | **Edit** | 1 |
| `src/database.py` | **Edit** | 1 |
| `src/comfyui_client.py` | **Edit** | 5 |
| `src/main.py` | **Edit** | 7 |
| `docs/leader-pipeline-reference.md` | **New** (this file) | 0 |

**Untouched files:** `src/generators.py`, `src/storage.py`, `src/inpainting.py`, `src/static_catalog.py`, `src/__init__.py`, `requirements.txt`, `workflows/txt2img.json`, `workflows/inpaint.json`, `workflows/story.json`, `workflows/splash.json`, `static_tiles/`, `generated_assets/`, `splash_assets/`, `mock_assets/`.

The leader pipeline is a **parallel feature** that reuses the same `ComfyUIClient`, `AssetStore`, `SessionLocal`, and `ThreadPoolExecutor` infrastructure. No existing behaviour changes.

---

## 3. Phase 1: Foundation — Models, Config, Database

### 3.1 `src/leader_models.py` (NEW)

```python
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
        description="Required for profile and single-leader action. The leader_id from a previous splash generation. Ignored if leader_ids is provided.",
    )
    leader_ids: Optional[list[str]] = Field(
        default=None,
        description="Required for multi-leader action scenes. List of leader_ids to include in the scene. "
                    "When provided for asset_type='action', leader_id is ignored and the engine generates "
                    "a txt2img composite scene depicting all listed leaders.",
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
```

### 3.2 `src/config.py` (EDIT)

Add the leader settings block. Existing settings remain untouched.

```python
# --- Leader generation ---
leader_workflow_dir: str = os.path.join(os.path.dirname(__file__), "workflows", "leader")
leader_reference_dir: str = os.path.join(BASE_DIR, "leader_references")

# Prompt components (overridable via .env for rapid iteration)
leader_negative_prompt: str = (
    "blurry, low quality, distorted, ugly, deformed face, bad hands, "
    "missing fingers, text, watermark, signature, logo, cartoon, 3D render, "
    "photograph, selfie, modern clothing, jeans, t-shirt, plastic, "
    "oversaturated colors, bad anatomy, extra limbs, cloned face, disfigured, "
    "jpeg artifacts"
)
```

Add directory creation in the existing `os.makedirs` block:

```python
os.makedirs(settings.leader_workflow_dir, exist_ok=True)
os.makedirs(settings.leader_reference_dir, exist_ok=True)
```

**Removed from config (now in workflow JSONs):**
`leader_splash_width/height`, `leader_profile_width/height`, `leader_action_width/height`,
`leader_denoise_splash/profile/action`, `leader_steps`, `leader_cfg`, `leader_sampler`,
`leader_scheduler`, `leader_lora_strength` — all baked into workflow JSONs. See redundancy audit above.

### 3.3 `src/database.py` (EDIT)

Add `LeaderRecord` table alongside existing `AssetRecord`:

```python
class LeaderRecord(Base):
    __tablename__ = "leader_records"

    leader_id = Column(String, primary_key=True, index=True)
    leader_name = Column(String, nullable=False)
    archetype = Column(String, nullable=False)
    culture = Column(String, nullable=False)
    time_of_day = Column(String, nullable=False)
    mood = Column(String, nullable=False)

    # Canonical identity
    splash_image_id = Column(String, nullable=False)         # FK → asset_records.id
    splash_seed = Column(Integer, nullable=False)            # canonical seed for profile/action consistency
    splash_prompt = Column(String, nullable=False)           # debug / reproducibility

    # Subsequent generations
    profile_image_id = Column(String, nullable=True)
    action_image_ids = Column(JSON, nullable=True)           # list of asset IDs

    # Reference image
    reference_filename = Column(String, nullable=False)      # "ref_{leader_id}.png"

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

**No migration needed** — `Base.metadata.create_all()` handles this on next startup.

---

## 4. Phase 2: Prompt Engine

### 4.1 `src/leader_prompts.py` (NEW)

"""Assembles final prompts from request fields and enum injection maps.

The client never writes raw prompts. The server builds them from structured
enums (archetype, culture, time_of_day, mood, action_category) plus the
leader_description and action_description prose fields.
"""

from .config import settings
from .leader_models import LeaderRequest

# ---------------------------------------------------------------------------
# Enum injection maps  (hand-crafted, rich prose per value)
# ---------------------------------------------------------------------------

ARCHETYPE = {
    "warrior_queen": (
        "standing proudly, martial bearing, armor and weapons prominent, "
        "battle-hardened confidence"
    ),
    "warrior_king": (
        "commanding presence, battle-scarred dignity, weapon in hand, "
        "military authority"
    ),
    "philosopher_king": (
        "seated or standing in contemplation, scrolls or scientific instruments "
        "nearby, learned wisdom"
    ),
    "merchant_prince": (
        "calculating gaze, surrounded by symbols of wealth and trade, "
        "shrewd intelligence"
    ),
    "spiritual_leader": (
        "mystical aura, religious or natural symbols, ceremonial pose, "
        "transcendent connection"
    ),
    "diplomat": (
        "open posture, formal court or negotiating setting, measured diplomacy"
    ),
    "tyrant": (
        "imposing dominance, deep shadows, iron grip on throne or weapon, "
        "intimidating power"
    ),
    "visionary": (
        "gazing toward horizon, plans or blueprints in hand, forward-looking ambition"
    ),
}

CULTURE = {
    "ancient_egyptian": (
        "a vast sandstone temple with towering hieroglyph-carved pillars, "
        "gold and lapis lazuli accents, bronze braziers burning incense, "
        "desert beyond colonnades"
    ),
    "classical_greek": (
        "a marble temple with corinthian columns, olive groves on the hillside, "
        "Aegean blue sea in the distance, white stone catching golden light"
    ),
    "roman_imperial": (
        "a grand travertine forum with domes and aqueducts, crimson banners "
        "with gold eagles, paved stone plaza, imperial majesty"
    ),
    "medieval_european": (
        "a stone castle great hall with oak beams, heraldic tapestries, iron "
        "chandeliers, stained glass catching colored light through tall windows"
    ),
    "east_asian_imperial": (
        "a magnificent jade and red lacquer palace interior, silk screens with "
        "landscape paintings, cherry blossoms visible through moon gates, misty "
        "mountains beyond"
    ),
    "mesopotamian": (
        "a mud-brick ziggurat temple complex, bronze and lapis lazuli ornamentation, "
        "reed marshes and twin rivers visible in the distance"
    ),
    "mesoamerican": (
        "a stone step pyramid amid dense jungle, obsidian mirrors, jade ornaments "
        "and quetzal feather adornments, carved stone stelae in the foreground"
    ),
    "nordic_viking": (
        "a timber longhouse with carved dragon posts, fur-draped walls, iron "
        "braziers casting warm light, fjord waters and northern lights through "
        "the smoke hole above"
    ),
    "persian": (
        "a blue-tiled palace overlooking cypress gardens and reflecting pools, "
        "silk curtains billowing in mountain breeze, snow-capped peaks in the distance"
    ),
    "sub_saharan_african": (
        "a grand mud-brick structure with carved wooden beams, gold and ivory "
        "ornaments, baobab trees on the savanna horizon, richly woven textile hangings"
    ),
    "south_asian": (
        "a sandstone temple complex with intricate carvings, lotus ponds reflecting "
        "the architecture, gold jewelry catching warm sunlight, monsoon clouds "
        "gathering dramatically"
    ),
    "islamic_golden_age": (
        "a domed observatory with intricate geometric tile patterns, brass "
        "astrolabes on pedestals, parchment manuscripts on shelves, arabesque "
        "arches framing a star-filled desert sky"
    ),
}

TIME_OF_DAY = {
    "dawn": (
        "first light of dawn breaking over the horizon, cool blue shadows "
        "giving way to warm gold, mist rising from the ground"
    ),
    "golden_hour": (
        "low golden sunlight casting long dramatic shadows, warm amber glow "
        "suffusing everything, dust motes dancing in light beams"
    ),
    "midday": (
        "harsh clear sunlight from overhead, strong contrast with deep black "
        "shadows, bright cloudless sky"
    ),
    "twilight": (
        "purple and orange sky at the boundary of day and night, torches and "
        "braziers being lit, the first stars appearing"
    ),
    "night": (
        "deep night with moonlight streaming through openings, warm firelight "
        "from torches and braziers, stars visible overhead"
    ),
    "storm": (
        "dark brooding storm clouds massing overhead, dramatic lightning "
        "illuminating the scene in flashes, wind whipping through"
    ),
}

MOOD = {
    "triumphant": (
        "expression of hard-won victory, proud celebratory atmosphere, head held high"
    ),
    "wise_serene": (
        "expression of profound calm wisdom, peaceful dignified atmosphere, "
        "gentle knowing gaze"
    ),
    "grim_determined": (
        "expression of steely unbreakable resolve, tense charged atmosphere, "
        "jaw set firm"
    ),
    "mystical": (
        "expression of spiritual transcendence, ethereal otherworldly atmosphere, "
        "eyes seeing beyond the visible"
    ),
    "melancholic": (
        "expression of bittersweet reflection, quiet somber atmosphere, heavy "
        "with history and memory"
    ),
    "menacing": (
        "expression of cold calculated power, oppressive intimidating atmosphere, "
        "danger crackling in the air"
    ),
    "hopeful": (
        "expression of optimistic vision, bright aspirational atmosphere, looking "
        "toward possibility"
    ),
    "contemplative": (
        "expression of deep thought, quiet introspective atmosphere, weighing "
        "profound decisions"
    ),
}

ACTION_CATEGORY = {
    "military": (
        "dynamic action composition, weapons drawn, battlefield context with "
        "smoke and banners, cavalry and infantry in motion"
    ),
    "diplomatic": (
        "formal court or neutral meeting ground, treaty documents on the table, "
        "multiple parties present, ceremonial exchange unfolding"
    ),
    "construction": (
        "monument or great building in progress, workers on scaffolding, stone "
        "blocks being lifted by cranes, immense civic scale"
    ),
    "scientific": (
        "instruments and scrolls in an observatory or study, moment of breakthrough "
        "discovery, intellectual excitement in the air"
    ),
    "cultural": (
        "ceremony or festival with rich ritual elements, artistic performance "
        "in progress, gathered audience, cultural pageantry"
    ),
    "exploration": (
        "newly discovered territory unfolding before them, map unfurled on a "
        "stone table, scouts pointing ahead, vista of unknown lands"
    ),
    "crisis": (
        "imminent threat approaching, the leader responding to emergency, tense "
        "urgent body language, decisive action required"
    ),
}

# ---------------------------------------------------------------------------
# Style tails  (appended to every prompt — never exposed to client)
# ---------------------------------------------------------------------------

SPLASH_TAIL = (
    "civilization leader splash screen art, rich painterly oil style, "
    "masterpiece composition, dramatic lighting, by Craig Mullins and "
    "Greg Rutkowski, 8K, highly detailed, 16:9 cinematic aspect ratio"
)

PROFILE_TAIL = (
    "civilization leader profile picture, sharp focus on eyes, Rembrandt "
    "lighting, portrait lens 85mm f/1.4, very shallow depth of field, bokeh "
    "background, highly detailed skin texture and pores, 8K, square format"
)

ACTION_TAIL = (
    "civilization game event art, rich painterly oil style, dramatic composition, "
    "consistent character design, highly detailed, 8K, 16:9 cinematic aspect ratio"
)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_splash_prompt(req: LeaderRequest) -> str:
    parts = [
        f"epic cinematic wide composition of {req.leader_description.strip()},",
        ARCHETYPE[req.archetype],
        f"in {CULTURE[req.culture]}",
        TIME_OF_DAY[req.time_of_day],
        MOOD[req.mood],
        SPLASH_TAIL,
    ]
    return ", ".join(parts)


def build_profile_prompt(req: LeaderRequest) -> str:
    parts = [
        f"professional close-up portrait of {req.leader_description.strip()},",
        "face filling the frame",
        "headpiece and collar visible at the edges of the frame",
        MOOD[req.mood],
        PROFILE_TAIL,
    ]
    return ", ".join(parts)


def build_action_prompt(req: LeaderRequest) -> str:
    parts = [
        f"epic cinematic scene depicting {req.leader_description.strip()}",
        req.action_description.strip(),
        f"in {CULTURE[req.culture]}",
        TIME_OF_DAY[req.time_of_day],
        MOOD[req.mood],
        ACTION_CATEGORY[req.action_category],
        ACTION_TAIL,
    ]
    return ", ".join(parts)


def build_multi_action_prompt(
    req: LeaderRequest,
    leader_descriptions: list[str],
    leader_names: list[str],
) -> str:
    """Build a prompt for a multi-leader action scene.

    Composes all leader descriptions into a single prompt describing
    their interaction within the action scene. Handles 1, 2, or 3+
    leaders with appropriate natural-language phrasing.
    """
    if len(leader_descriptions) == 1:
        char_part = f"epic cinematic scene depicting {leader_descriptions[0].strip()}"
    elif len(leader_descriptions) == 2:
        char_part = (
            f"epic cinematic scene depicting two leaders interacting: "
            f"{leader_names[0]}, {leader_descriptions[0].strip()}, "
            f"and {leader_names[1]}, {leader_descriptions[1].strip()}"
        )
    else:
        named = ", ".join(
            f"{name}, {desc.strip()}"
            for name, desc in zip(leader_names, leader_descriptions)
        )
        char_part = f"epic cinematic scene depicting multiple leaders: {named}"

    parts = [
        char_part,
        req.action_description.strip(),
        f"in {CULTURE[req.culture]}",
        TIME_OF_DAY[req.time_of_day],
        MOOD[req.mood],
        ACTION_CATEGORY[req.action_category],
        ACTION_TAIL,
    ]
    return ", ".join(parts)


def build_prompt(req: LeaderRequest) -> str:
    """Route to the correct builder based on asset_type."""
    builders = {
        "splash":  build_splash_prompt,
        "profile": build_profile_prompt,
        "action":  build_action_prompt,
    }
    return builders[req.asset_type](req)
```

---

## 5. Phase 3: Leader Registry (SQLite-backed)

### 5.1 `src/leader_registry.py` (NEW)

"""Leader registry backed by SQLite via SQLAlchemy.

Replaces the guide's JSON-file approach. Thread-safe, queryable,
and integrated with the existing database infrastructure.
"""

import logging
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from .config import settings
from .database import SessionLocal, LeaderRecord

logger = logging.getLogger(__name__)


class LeaderRegistry:
    """CRUD operations for leader records. Uses SQLAlchemy sessions."""

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    @staticmethod
    def register(
        leader_id: str,
        leader_name: str,
        archetype: str,
        culture: str,
        time_of_day: str,
        mood: str,
        splash_image_filename: str,
        splash_seed: int,
        splash_prompt: str,
    ) -> str:
        """Register a new leader after splash generation.

        Copies the splash image to the reference directory as ref_{leader_id}.png
        and inserts a LeaderRecord.

        Returns the reference filename.
        """
        ref_name = f"ref_{leader_id}.png"

        # Copy splash → reference directory
        src = Path(settings.output_dir) / splash_image_filename
        dst = Path(settings.leader_reference_dir) / ref_name
        shutil.copy2(src, dst)
        logger.info("Copied splash → reference image: %s", ref_name)

        with SessionLocal() as db:
            record = LeaderRecord(
                leader_id=leader_id,
                leader_name=leader_name,
                archetype=archetype,
                culture=culture,
                time_of_day=time_of_day,
                mood=mood,
                splash_image_id=splash_image_filename,
                splash_seed=splash_seed,
                splash_prompt=splash_prompt,
                reference_filename=ref_name,
                profile_image_id=None,
                action_image_ids=None,
            )
            db.add(record)
            db.commit()
            logger.info("Leader registered: %s (%s)", leader_name, leader_id)

        return ref_name

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    def get(leader_id: str) -> Optional[LeaderRecord]:
        """Return a LeaderRecord or None."""
        with SessionLocal() as db:
            return db.query(LeaderRecord).filter(
                LeaderRecord.leader_id == leader_id
            ).first()

    @staticmethod
    def exists(leader_id: str) -> bool:
        """Check if a leader_id is registered."""
        with SessionLocal() as db:
            return db.query(LeaderRecord).filter(
                LeaderRecord.leader_id == leader_id
            ).first() is not None

    @staticmethod
    def list_all() -> list[LeaderRecord]:
        """Return all registered leaders, most recent first."""
        with SessionLocal() as db:
            return db.query(LeaderRecord).order_by(
                LeaderRecord.created_at.desc()
            ).all()

    @staticmethod
    def get_reference_filename(leader_id: str) -> Optional[str]:
        """Return the reference image filename or None."""
        leader = LeaderRegistry.get(leader_id)
        return leader.reference_filename if leader else None

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    @staticmethod
    def record_profile(leader_id: str, image_filename: str) -> None:
        """Record a profile image for an existing leader."""
        with SessionLocal() as db:
            leader = db.query(LeaderRecord).filter(
                LeaderRecord.leader_id == leader_id
            ).first()
            if leader:
                leader.profile_image_id = image_filename
                db.commit()
                logger.info("Profile recorded for leader: %s", leader_id)

    @staticmethod
    def record_action(leader_id: str, image_filename: str) -> None:
        """Append an action image to the leader's action_image_ids list."""
        with SessionLocal() as db:
            leader = db.query(LeaderRecord).filter(
                LeaderRecord.leader_id == leader_id
            ).first()
            if leader:
                ids = leader.action_image_ids or []
                ids.append(image_filename)
                leader.action_image_ids = ids
                db.commit()
                logger.info("Action recorded for leader: %s", leader_id)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    @staticmethod
    def delete(leader_id: str) -> bool:
        """Remove a leader and clean up their reference image.

        Returns True if a leader was deleted, False if not found.
        """
        # Clean up reference image
        ref_name = f"ref_{leader_id}.png"
        ref_path = Path(settings.leader_reference_dir) / ref_name
        if ref_path.exists():
            ref_path.unlink()

        with SessionLocal() as db:
            leader = db.query(LeaderRecord).filter(
                LeaderRecord.leader_id == leader_id
            ).first()
            if leader:
                db.delete(leader)
                db.commit()
                logger.info("Leader deleted: %s", leader_id)
                return True
        return False


# ---------------------------------------------------------------------------
# Leader ID generator
# ---------------------------------------------------------------------------

def generate_leader_id(leader_name: str) -> str:
    """Generate a deterministic, URL-safe leader ID.

    Format: leader_{slugified_name}_{short_uuid}
    Example: leader_cleopatra_vii_a1b2c3
    """
    import re
    slug = re.sub(r'[^a-z0-9]+', '_', leader_name.lower()).strip('_')[:40]
    return f"leader_{slug}_{uuid.uuid4().hex[:6]}"
```

---

## 6. Phase 4: Workflow JSON Templates

Three independent workflow JSONs. Each is self-contained — no disconnected nodes, no link surgery at runtime. Exported from ComfyUI in "Save (API Format)" mode.

### 6.1 `workflows/leader/leader_splash.json` (NEW)

**Purpose:** txt2img canonical splash art.

**Required nodes (by `_meta.title`):**

| Title | class_type | Purpose |
|-------|-----------|---------|
| `Load Checkpoint` | `CheckpointLoaderSimple` | SDXL Turbo checkpoint |
| `CLIP Text Encode (Positive)` | `CLIPTextEncode` | Patched with splash prompt |
| `CLIP Text Encode (Negative)` | `CLIPTextEncode` | Patched with negative prompt |
| `Empty Latent Image` | `EmptyLatentImage` | Patched to 1920×1088 |
| `KSampler` | `KSampler` | Seed patched, denoise=1.0, steps=8, cfg=1.8, euler/beta |
| `VAE Decode` | `VAEDecode` | Decode latent |
| `Save Image` | `SaveImage` | filename_prefix patched to "leader_splash" |

**No LoadImage or VAEEncode nodes.** This is pure txt2img.

### 6.2 `workflows/leader/leader_profile.json` (NEW)

**Purpose:** img2img profile portrait (uses splash reference, denoise=0.30).

**Required nodes (by `_meta.title`):**

| Title | class_type | Purpose |
|-------|-----------|---------|
| `Load Checkpoint` | `CheckpointLoaderSimple` | |
| `CLIP Text Encode (Positive)` | `CLIPTextEncode` | Patched with profile prompt |
| `CLIP Text Encode (Negative)` | `CLIPTextEncode` | Patched with negative prompt |
| `Load Reference Image` | `LoadImage` | Patched with `ref_{leader_id}.png` filename |
| `VAE Encode` | `VAEEncode` | Encode reference → latent |
| `KSampler` | `KSampler` | latent_image ← VAEEncode output. Denoise patched to 0.30. |
| `VAE Decode` | `VAEDecode` | |
| `Save Image` | `SaveImage` | filename_prefix patched to "leader_profile" |

**Permanently connected chain:** LoadImage → VAEEncode → KSampler.latent_image. No dynamic link surgery.

### 6.3 `workflows/leader/leader_action.json` (NEW)

**Purpose:** img2img action scene (uses splash reference, denoise=0.60).

**Same node structure as `leader_profile.json`** except:
- `SaveImage` prefix → `"leader_action"`
- KSampler denoise → 0.60
- EmptyLatentImage resolution → 1920×1088 (even though img2img path is used, the node provides context)

**Note:** The guide's workflow uses `EmptyFluxLatentImage` but we keep SDXL Turbo compatibility with `EmptyLatentImage`. The workflow exported from ComfyUI determines which latent node type is used. The engine does not care — it patches by `_meta.title`, not by `class_type`.

### How the engine patches these workflows

The existing `_patch_workflow()` in `comfyui_client.py` already handles everything we need:
- `CLIPTextEncode` by `_meta.title` (positive/negative prompt injection)
- `KSampler` seed injection
- `EmptyLatentImage` width/height injection
- `LoadImage` filename injection (for `ref_{leader_id}.png`)

**No additional patches needed.** Resolution, denoise, steps, cfg, sampler, scheduler, model paths, LoRA strength, and SaveImage prefix are all baked into the workflow JSONs. The engine only injects `positive_prompt`, `seed`, `negative_prompt`, and on profile/action: the reference image filename and uploaded image bytes.

---

## 7. Phase 5: ComfyUI Client Extensions

### 7.1 `src/comfyui_client.py` (EDIT)

Additions to the existing `ComfyUIClient` class. No existing methods change. **No `_patch_workflow()` changes needed** — all KSampler/SaveImage params are baked into the workflow JSONs.

```python
def upload_reference_image(self, pil_image: Image.Image, filename: str) -> str:
    """Upload a reference image to ComfyUI's input/ folder.

    Different from upload_image(): this always overwrites and is intended
    for reference images that persist across multiple generations.
    Returns the stored filename.
    """
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    buf.seek(0)

    resp = requests.post(
        f"{self.base_url}/upload/image",
        files={"image": (filename, buf, "image/png")},
        data={"overwrite": "true", "type": "input"},
        timeout=30,
    )
    resp.raise_for_status()
    logger.info("Uploaded reference image: %s", filename)
    return filename


def cancel_prompt(self, prompt_id: str) -> bool:
    """Cancel a queued or running prompt. Returns True if successful."""
    try:
        resp = requests.post(
            f"{self.base_url}/queue",
            json={"delete": [prompt_id]},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False
```

---

## 8. Phase 6: Leader Engine (Orchestrator)

### 8.1 `src/leader_engine.py` (NEW)

"""Leader generation orchestrator.

Routes splash/profile/action requests through the ComfyUI pipeline,
maintains character consistency via img2img reference images,
and persists everything through LeaderRegistry + AssetStore + AssetRecord.

Resolution, denoise, steps, cfg, sampler, scheduler, model paths, LoRA
strength, and SaveImage prefix are all baked into the workflow JSONs.
The engine only injects: positive_prompt, seed, negative_prompt, and
(for profile/action) the reference image + LoadImage filename.
"""

import json
import logging
import random
import time
import uuid
from pathlib import Path
from typing import Optional

from PIL import Image

from .comfyui_client import ComfyUIClient
from .config import settings
from .database import SessionLocal, AssetRecord
from .leader_models import LeaderRequest, LeaderResponse
from .leader_prompts import build_prompt, build_multi_action_prompt
from .leader_registry import LeaderRegistry, generate_leader_id
from .storage import store

logger = logging.getLogger(__name__)


class LeaderEngine:
    """Orchestrates the splash → profile → action pipeline."""

    def __init__(self, client: ComfyUIClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate(self, request: LeaderRequest) -> LeaderResponse:
        """Route to the correct handler based on asset_type."""
        handlers = {
            "splash":  self._generate_splash,
            "profile": self._generate_profile,
            "action":  self._generate_action,
        }
        return handlers[request.asset_type](request)

    # ------------------------------------------------------------------
    # Splash
    # ------------------------------------------------------------------

    def _generate_splash(self, req: LeaderRequest) -> LeaderResponse:
        # 1. Build prompt
        prompt = build_prompt(req)

        # 2. Generate leader_id
        leader_id = generate_leader_id(req.leader_name)

        # 3. Seed
        seed = req.seed or random.randint(10**14, 10**15 - 1)

        # 4. Workflow path
        wf_path = str(Path(settings.leader_workflow_dir) / "leader_splash.json")

        # 5. Run — only inject what changes per request
        start = time.time()
        img = self._client.generate(
            wf_path,
            positive_prompt=prompt,
            negative_prompt=settings.leader_negative_prompt,
            seed=seed,
            # width, height, denoise, steps, cfg, sampler, scheduler,
            # model paths, LoRA strength, SaveImage prefix — all in workflow JSON
        )

        # 6. Save to AssetStore
        filename = f"{leader_id}_splash.png"
        store.save_image(filename, img)

        # 7. Persist AssetRecord
        with SessionLocal() as db:
            db.add(AssetRecord(
                id=filename,
                asset_family="leader_splash",
                character_name=req.leader_name,
                generation_mode="comfyui",
            ))
            db.commit()

        # 8. Register leader (copies splash → reference dir)
        LeaderRegistry.register(
            leader_id=leader_id,
            leader_name=req.leader_name,
            archetype=req.archetype,
            culture=req.culture,
            time_of_day=req.time_of_day,
            mood=req.mood,
            splash_image_filename=filename,
            splash_seed=seed,
            splash_prompt=prompt,
        )

        elapsed = int((time.time() - start) * 1000)

        return LeaderResponse(
            url=f"/assets/{filename}",
            asset_type="splash",
            leader_name=req.leader_name,
            leader_id=leader_id,
            seed=seed,
            generation_mode="comfyui",
            prompt_used=prompt,
            resolution=None,  # read from workflow JSON if needed for response
            generation_time_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    def _generate_profile(self, req: LeaderRequest) -> LeaderResponse:
        # 1. Validate
        if not req.leader_id:
            raise ValueError("leader_id is required for profile assets")
        leader = LeaderRegistry.get(req.leader_id)
        if not leader:
            raise ValueError(f"Leader '{req.leader_id}' not found. Generate a splash first.")

        # 2. Seed: use canonical unless overridden
        seed = req.seed or leader.splash_seed

        # 3. Upload reference image
        ref_path = Path(settings.leader_reference_dir) / leader.reference_filename
        if not ref_path.exists():
            raise RuntimeError(f"Reference image missing: {ref_path}")
        ref_img = Image.open(ref_path).convert("RGBA")
        self._client.upload_reference_image(ref_img, leader.reference_filename)

        # 4. Build prompt
        prompt = build_prompt(req)

        # 5. Workflow path
        wf_path = str(Path(settings.leader_workflow_dir) / "leader_profile.json")

        # 6. Find LoadImage node (for filename injection)
        load_nid = self._find_load_image_node_file(wf_path)

        # 7. Run — inject prompt, seed, negative prompt, and reference image
        start = time.time()
        img = self._client.generate(
            wf_path,
            positive_prompt=prompt,
            negative_prompt=settings.leader_negative_prompt,
            seed=seed,
            input_images={load_nid: ref_img} if load_nid else None,
            # width, height, denoise, etc. — in workflow JSON
        )

        # 8. Save
        filename = f"{req.leader_id}_profile.png"
        store.save_image(filename, img)

        # 9. Persist AssetRecord
        with SessionLocal() as db:
            db.add(AssetRecord(
                id=filename,
                asset_family="leader_profile",
                base_image_id=leader.splash_image_id,
                character_name=req.leader_name,
                generation_mode="comfyui",
            ))
            db.commit()

        # 10. Update registry
        LeaderRegistry.record_profile(req.leader_id, filename)

        elapsed = int((time.time() - start) * 1000)

        return LeaderResponse(
            url=f"/assets/{filename}",
            asset_type="profile",
            leader_name=req.leader_name,
            leader_id=req.leader_id,
            seed=seed,
            generation_mode="comfyui",
            prompt_used=prompt,
            resolution=None,
            generation_time_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------

    def _generate_action(self, req: LeaderRequest) -> LeaderResponse:
        # 1. Validate
        if not req.leader_id:
            raise ValueError("leader_id is required for action assets")
        if not req.action_category:
            raise ValueError("action_category is required for action assets")
        if not req.action_description:
            raise ValueError("action_description is required for action assets")

        leader = LeaderRegistry.get(req.leader_id)
        if not leader:
            raise ValueError(f"Leader '{req.leader_id}' not found. Generate a splash first.")

        # 2. Seed
        seed = req.seed or leader.splash_seed

        # 3. Upload reference image
        ref_path = Path(settings.leader_reference_dir) / leader.reference_filename
        if not ref_path.exists():
            raise RuntimeError(f"Reference image missing: {ref_path}")
        ref_img = Image.open(ref_path).convert("RGBA")
        self._client.upload_reference_image(ref_img, leader.reference_filename)

        # 4. Build prompt
        prompt = build_prompt(req)

        # 5. Workflow path
        wf_path = str(Path(settings.leader_workflow_dir) / "leader_action.json")

        # 6. Find LoadImage node
        load_nid = self._find_load_image_node_file(wf_path)

        # 7. Run
        start = time.time()
        img = self._client.generate(
            wf_path,
            positive_prompt=prompt,
            negative_prompt=settings.leader_negative_prompt,
            seed=seed,
            input_images={load_nid: ref_img} if load_nid else None,
            # width, height, denoise, etc. — in workflow JSON
        )

        # 8. Save
        filename = f"{req.leader_id}_action_{uuid.uuid4().hex[:6]}.png"
        store.save_image(filename, img)

        # 9. Persist AssetRecord
        with SessionLocal() as db:
            db.add(AssetRecord(
                id=filename,
                asset_family="leader_action",
                base_image_id=leader.splash_image_id,
                character_name=req.leader_name,
                generation_mode="comfyui",
            ))
            db.commit()

        # 10. Update registry
        LeaderRegistry.record_action(req.leader_id, filename)

        elapsed = int((time.time() - start) * 1000)

        return LeaderResponse(
            url=f"/assets/{filename}",
            asset_type="action",
            leader_name=req.leader_name,
            leader_id=req.leader_id,
            seed=seed,
            generation_mode="comfyui",
            prompt_used=prompt,
            resolution=None,
            generation_time_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # Multi-leader action (txt2img — no reference image)
    # ------------------------------------------------------------------

    def generate_multi_action(
        self,
        req: LeaderRequest,
        leader_ids: list[str],
    ) -> LeaderResponse:
        """Generate a multi-leader action scene via txt2img.

        Loads all leader records from the registry, builds a composite
        prompt from their descriptions and names, and generates a single
        action image without img2img (since ComfyUI can only accept one
        reference image but the scene must depict multiple distinct faces).
        """
        t0 = time.time()

        # Load all leader records
        leader_names = []
        leader_descriptions = []
        for lid in leader_ids:
            leader = LeaderRegistry.get(lid)
            if not leader:
                raise ValueError(
                    f"Leader '{lid}' not found. Generate a splash first."
                )
            leader_names.append(leader.leader_name)
            leader_descriptions.append(leader.leader_description)

        # Build composite prompt
        prompt = build_multi_action_prompt(req, leader_descriptions, leader_names)

        # Workflow path — same action workflow, but no reference image
        wf_path = str(Path(settings.leader_workflow_dir) / "leader_action.json")

        # Run as txt2img
        img = self._client.generate(
            wf_path,
            positive_prompt=prompt,
            negative_prompt=settings.leader_negative_prompt,
            seed=req.seed or random.randint(10**14, 10**15 - 1),
        )

        # Save
        asset_id = str(uuid.uuid4())
        filename = f"leader_multi_{asset_id}_action.png"
        store.save_image(filename, img)

        # Persist AssetRecord
        with SessionLocal() as db:
            db.add(AssetRecord(
                id=filename,
                asset_family="leader_action",
                character_name=", ".join(leader_names),
                generation_mode="comfyui",
            ))
            db.commit()

        elapsed = int((time.time() - t0) * 1000)

        return LeaderResponse(
            url=f"/assets/{filename}",
            asset_type="action",
            leader_name=", ".join(leader_names),
            leader_id=asset_id,
            leader_ids=leader_ids,
            leader_names=leader_names,
            seed=req.seed or 0,
            generation_mode="comfyui",
            prompt_used=prompt,
            resolution=None,
            generation_time_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_load_image_node_file(wf_path: str) -> str | None:
        """Read the workflow JSON and find the first LoadImage node ID."""
        with open(wf_path) as f:
            wf = json.load(f)
        for nid, node in wf.items():
            if node.get("class_type") == "LoadImage":
                return nid
        return None
```

---

## 9. Phase 7: API Endpoints in main.py

### 9.1 `src/main.py` (EDIT)

Add these at module level (alongside existing `mutator`, `comfyui`, `registry`):

```python
from .leader_models import LeaderRequest, LeaderResponse, LeaderInfo
from .leader_engine import LeaderEngine
from .leader_registry import LeaderRegistry

# ...existing singletons...

leader_engine: LeaderEngine | None = None
```

Initialize in lifespan:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ...existing startup...
    global leader_engine
    client = _get_comfyui_client()
    if client:
        leader_engine = LeaderEngine(client)
        logger.info("Leader engine initialized")
    yield
    # ...existing shutdown...
```

### 9.2 New endpoints

```python
# ---------------------------------------------------------------------------
#  Leader pipeline
# ---------------------------------------------------------------------------


@app.post("/leader", response_model=LeaderResponse)
async def generate_leader(request: LeaderRequest):
    """Generate a leader asset: splash, profile, or action scene.

    Pipeline order:
      1. POST /leader {asset_type: "splash", ...}     → returns leader_id
      2. POST /leader {asset_type: "profile", leader_id: "...", ...}
      3. POST /leader {asset_type: "action", leader_id: "...", action_category: "...", ...}
    """
    logger.info("Received leader request for type: %s", request.asset_type)

    if leader_engine is None:
        raise HTTPException(503, "Leader generation not available (ComfyUI unreachable)")

    try:
        loop = __import__("asyncio").get_event_loop()
        response: LeaderResponse = await loop.run_in_executor(
            _executor, leader_engine.generate, request
        )
        logger.info(
            "Leader %s generated: %s (%.1fs)",
            response.leader_name,
            response.asset_type,
            (response.generation_time_ms or 0) / 1000,
        )
        return response

    except ValueError as e:
        logger.warning("Leader validation error: %s", e)
        raise HTTPException(400, detail=str(e))
    except RuntimeError as e:
        logger.error("Leader runtime error: %s", e)
        raise HTTPException(503, detail=str(e))
    except Exception as e:
        logger.error("Leader generation error: %s", e)
        raise HTTPException(500, detail=str(e))


@app.get("/leader", response_model=list[LeaderInfo])
async def list_leaders():
    """Return all registered leaders. Parallels GET /catalog."""
    records = LeaderRegistry.list_all()
    return [
        LeaderInfo(
            leader_id=r.leader_id,
            leader_name=r.leader_name,
            archetype=r.archetype,
            culture=r.culture,
            splash_url=f"/assets/{r.splash_image_id}" if r.splash_image_id else None,
            profile_url=f"/assets/{r.profile_image_id}" if r.profile_image_id else None,
            action_urls=[f"/assets/{aid}" for aid in (r.action_image_ids or [])],
            splash_seed=r.splash_seed,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in records
    ]


@app.get("/leader/{leader_id}", response_model=LeaderInfo)
async def get_leader(leader_id: str):
    """Get a specific leader's info + asset URLs."""
    leader = LeaderRegistry.get(leader_id)
    if not leader:
        raise HTTPException(404, f"Leader '{leader_id}' not found")
    return LeaderInfo(
        leader_id=leader.leader_id,
        leader_name=leader.leader_name,
        archetype=leader.archetype,
        culture=leader.culture,
        splash_url=f"/assets/{leader.splash_image_id}" if leader.splash_image_id else None,
        profile_url=f"/assets/{leader.profile_image_id}" if leader.profile_image_id else None,
        action_urls=[f"/assets/{aid}" for aid in (leader.action_image_ids or [])],
        splash_seed=leader.splash_seed,
        created_at=leader.created_at.isoformat() if leader.created_at else None,
    )


@app.delete("/leader/{leader_id}")
async def delete_leader(leader_id: str):
    """Remove a leader and their reference image. Generated assets remain on disk."""
    deleted = LeaderRegistry.delete(leader_id)
    if not deleted:
        raise HTTPException(404, f"Leader '{leader_id}' not found")
    return {"status": "deleted", "leader_id": leader_id}
```

### 9.3 Health endpoint extension

Add to existing `GET /health`:

```python
return {
    # ...existing fields...
    "leaders_registered": len(LeaderRegistry.list_all()),
}
```

---

## 10. Phase 8: Production Polish

### 10.1 Job status pattern (async generation)

Current design blocks until generation completes. For action scenes that may take 60-120s on FLUX, add optional async mode:

```python
# POST /leader returns immediately with job_id
# GET /leader/job/{job_id} polls status

@app.post("/leader/async", response_model=LeaderJobResponse)
async def generate_leader_async(request: LeaderRequest):
    """Queue a leader generation and return immediately with a job_id."""
    ...

@app.get("/leader/job/{job_id}", response_model=LeaderJobResponse)
async def get_leader_job(job_id: str):
    """Poll for job completion."""
    ...
```

**Defer to Phase 8.** The synchronous `/leader` endpoint works for MVP.

### 10.2 Async ComfyUI client

Replace `requests` + `websocket` with `httpx` + `websockets` for true async. The current blocking client in a thread pool works, but at high concurrency the thread pool saturates.

**Defer to Phase 8.** Not needed for single-leader-at-a-time usage.

### 10.3 Reference image TTL

Add a startup cleanup task:

```python
def cleanup_stale_references():
    """Remove ref_*.png files for leaders that no longer exist in the DB."""
    existing_ids = {r.leader_id for r in LeaderRegistry.list_all()}
    for ref_file in Path(settings.leader_reference_dir).glob("ref_*.png"):
        leader_id = ref_file.stem.replace("ref_", "")
        if leader_id not in existing_ids:
            ref_file.unlink()
            logger.info("Cleaned up stale reference: %s", ref_file.name)
```

### 10.4 Exponential backoff on timeout

```python
def _generate_with_retry(self, wf_path, **kwargs):
    """Retry once with 2x timeout on first failure (for FLUX models)."""
    try:
        return self._client.generate(wf_path, **kwargs)
    except TimeoutError:
        logger.warning("First attempt timed out; retrying with extended timeout")
        # Re-create client with doubled timeout
        ...
```

### 10.5 Prompt validation

```python
FORBIDDEN_PROMPT_WORDS = {
    "8K", "8k", "masterpiece", "beautiful", "stunning",
    "close-up", "closeup", "wide shot", "wide-shot",
    "cinematic", "epic",  # these are injected server-side
}

def validate_description(desc: str) -> str:
    """Strip forbidden style words from client descriptions."""
    # Warn but don't reject — strip and continue
    ...
```

### 10.6 Watermark/preview endpoint

```python
@app.get("/leader/{leader_id}/preview")
async def get_leader_preview(leader_id: str):
    """Return a 512px thumbnail of the splash art for gallery UIs."""
    ...
```

### 10.7 Batch generation

```python
@app.post("/leader/batch", response_model=list[LeaderResponse])
async def generate_leader_batch(request: LeaderBatchRequest):
    """Generate multiple assets for one leader in one call."""
    ...
```

---

## 11. Phase 9: Integration Tests

### 11.1 `tests/test_leader_pipeline.py` (NEW)

"""Integration tests for the leader pipeline.

Requires a running ComfyUI instance for full tests.
Mock-mode tests use a mock ComfyUIClient.
"""

import pytest
from src.leader.models import LeaderRequest
from src.leader.prompts import build_splash_prompt, build_profile_prompt, build_action_prompt
from src.leader.registry import LeaderRegistry, generate_leader_id


class TestPromptEngine:
    """Unit tests for prompt builders."""

    def test_splash_prompt_includes_all_fields(self):
        req = LeaderRequest(
            asset_type="splash",
            leader_name="Test Queen",
            leader_description="a tall warrior queen with bronze skin and sharp amber eyes, long black hair in tight braids bound with gold rings, wearing engraved bronze scale armor over a crimson linen tunic, a lion-pelt cape fastened at her left shoulder, a healed slash scar across her right cheekbone, expression of calm authority",
            archetype="warrior_queen",
            culture="ancient_egyptian",
            time_of_day="golden_hour",
            mood="triumphant",
        )
        prompt = build_splash_prompt(req)
        assert "bronze skin" in prompt
        assert "warrior_queen" not in prompt  # enum value not in output
        assert "martial bearing" in prompt     # archetype injection
        assert "sandstone temple" in prompt     # culture injection
        assert "golden sunlight" in prompt      # time_of_day injection
        assert "hard-won victory" in prompt     # mood injection
        assert "16:9 cinematic" in prompt       # style tail

    def test_profile_prompt_focuses_on_face(self):
        req = LeaderRequest(
            asset_type="profile",
            leader_name="Test Queen",
            leader_description="bronze skin, amber eyes, braided hair",
            archetype="warrior_queen",
            culture="ancient_egyptian",
            time_of_day="night",
            mood="wise_serene",
            leader_id="leader_test_abc123",
        )
        prompt = build_profile_prompt(req)
        assert "close-up" in prompt
        assert "face filling the frame" in prompt
        assert "85mm" in prompt               # portrait tail
        assert "Rembrandt" in prompt

    def test_action_prompt_includes_scene(self):
        req = LeaderRequest(
            asset_type="action",
            leader_name="Test Queen",
            leader_description="bronze skin, scale armor",
            archetype="warrior_queen",
            culture="ancient_egyptian",
            time_of_day="twilight",
            mood="grim_determined",
            leader_id="leader_test_abc123",
            action_category="military",
            action_description="standing on horseback watching enemy banners lowered",
        )
        prompt = build_action_prompt(req)
        assert "enemy banners" in prompt
        assert "battlefield" in prompt         # military category injection
        assert "cavalry" in prompt


class TestLeaderRegistry:
    """Integration tests for SQLite-backed registry."""

    def test_generate_leader_id_format(self):
        lid = generate_leader_id("Cleopatra VII")
        assert lid.startswith("leader_cleopatra_vii_")
        assert len(lid) < 80

    def test_register_and_retrieve(self):
        # Requires test database setup
        ...

    def test_record_profile_appends(self):
        ...

    def test_record_action_appends_multiple(self):
        ...

    def test_delete_cleans_reference(self):
        ...


class TestLeaderEngine:
    """End-to-end tests with mock ComfyUI client."""

    def test_full_pipeline_splash_profile_action(self):
        """Simulate the complete pipeline."""
        ...

    def test_profile_requires_leader_id(self):
        ...

    def test_action_requires_category_and_description(self):
        ...

    def test_seed_consistency(self):
        """Profile/action default to splash seed."""
        ...
```

---

## 12. Phase 10: Documentation & Final Checklist

### 12.1 Update `docs/architecture.md`

Add leader pipeline section after "Component Architecture > D. Feature Engineering":

```markdown
### E. Leader Pipeline (`leader_engine.py`, `leader_models.py`, `leader_prompts.py`, `leader_registry.py`)

- **Three-stage generation**: splash (txt2img, establishes canonical visual identity) → profile (img2img, close-crop portrait using splash as reference, denoise=0.30) → action (img2img, new scene preserving character, denoise=0.60)
- **Structured prompt injection**: clients select from enum values (archetype, culture, time_of_day, mood, action_category). The server maps these to rich, hand-crafted prose via `leader_prompts.py`
- **Seed anchoring**: splash seed is stored in `leader_records` and re-used for profile/action to maximize img2img consistency
- **Reference image**: splash art is copied to `leader_references/ref_{leader_id}.png` and re-uploaded to ComfyUI before each profile/action generation
- **SQLite-backed**: `LeaderRecord` table tracks all leaders alongside `AssetRecord`
```

### 12.2 Implementation checklist

```
Phase 1 — Foundation
□ src/leader_models.py created (enums + Pydantic schemas)
□ src/config.py updated (leader settings block + directory creation)
□ src/database.py updated (LeaderRecord table)
□ leader_references/ directory created

Phase 2 — Prompt Engine
□ src/leader_prompts.py created (enum injection maps + builders)

Phase 3 — Leader Registry
□ src/leader_registry.py created (SQLite-backed CRUD + generate_leader_id)

Phase 4 — Workflow JSONs
□ workflows/leader/leader_splash.json exported from ComfyUI
□ workflows/leader/leader_profile.json exported from ComfyUI
□ workflows/leader/leader_action.json exported from ComfyUI
```

---

## 13. Complete API Contract

### `POST /leader`

**Request:**

```json
{
  "asset_type": "splash",
  "leader_name": "Cleopatra VII",
  "leader_description": "a tall warrior queen with bronze skin and sharp amber eyes, long black hair in tight braids bound with gold rings, wearing engraved bronze scale armor over a crimson linen tunic, a lion-pelt cape fastened at her left shoulder, a healed slash scar across her right cheekbone, expression of calm authority",
  "archetype": "warrior_queen",
  "culture": "ancient_egyptian",
  "time_of_day": "golden_hour",
  "mood": "triumphant"
}
```

**Response (splash):**

```json
{
  "url": "/assets/leader_cleopatra_vii_a1b2c3_splash.png",
  "asset_type": "splash",
  "leader_name": "Cleopatra VII",
  "leader_id": "leader_cleopatra_vii_a1b2c3",
  "seed": 847291034857201,
  "generation_mode": "comfyui",
  "status": "completed",
  "prompt_used": "epic cinematic wide composition of a tall warrior queen..., ...",
  "resolution": "1920x1088",
  "generation_time_ms": 45230
}
```

**Response (profile):**

```json
{
  "url": "/assets/leader_cleopatra_vii_a1b2c3_profile.png",
  "asset_type": "profile",
  "leader_name": "Cleopatra VII",
  "leader_id": "leader_cleopatra_vii_a1b2c3",
  "seed": 847291034857201,
  "generation_mode": "comfyui",
  "status": "completed",
  "prompt_used": "professional close-up portrait of a tall warrior queen..., ...",
  "resolution": "1024x1024",
  "generation_time_ms": 32100
}
```

**Response (action):**

```json
{
  "url": "/assets/leader_cleopatra_vii_a1b2c3_action_d4e5f6.png",
  "asset_type": "action",
  "leader_name": "Cleopatra VII",
  "leader_id": "leader_cleopatra_vii_a1b2c3",
  "seed": 847291034857201,
  "generation_mode": "comfyui",
  "status": "completed",
  "prompt_used": "epic cinematic scene depicting a tall warrior queen..., ...",
  "resolution": "1920x1088",
  "generation_time_ms": 67800
}
```

### `GET /leader`

```json
[
  {
    "leader_id": "leader_cleopatra_vii_a1b2c3",
    "leader_name": "Cleopatra VII",
    "archetype": "warrior_queen",
    "culture": "ancient_egyptian",
    "splash_url": "/assets/leader_cleopatra_vii_a1b2c3_splash.png",
    "profile_url": "/assets/leader_cleopatra_vii_a1b2c3_profile.png",
    "action_urls": [
      "/assets/leader_cleopatra_vii_a1b2c3_action_d4e5f6.png"
    ],
    "splash_seed": 847291034857201,
    "created_at": "2026-05-27T14:30:00Z"
  }
]
```

### `GET /leader/{leader_id}`

Same shape as a single element from the list above.

### `DELETE /leader/{leader_id}`

```json
{
  "status": "deleted",
  "leader_id": "leader_cleopatra_vii_a1b2c3"
}
```

### `GET /health` (extended)

```json
{
  "status": "ok",
  "comfyui_connected": true,
  "modes": { /* ...existing... */ },
  "leaders_registered": 3
}
```

### Error responses

| Scenario | HTTP | Detail |
|----------|------|--------|
| `leader_id` missing for profile/action | 400 | `"leader_id is required for profile assets"` |
| `leader_id` not found | 404 | `"Leader 'X' not found. Generate a splash first."` |
| `action_category` missing for action | 400 | `"action_category is required for action assets"` |
| `action_description` missing for action | 400 | `"action_description is required for action assets"` |
| `leader_description` < 50 chars | 422 | Pydantic validation |
| ComfyUI unreachable | 503 | `"Leader generation not available (ComfyUI unreachable)"` |
| Generation timeout | 503 | `"ComfyUI prompt did not complete successfully"` |
| Reference image missing from disk | 500 | `"Reference image missing: /path/to/ref_{id}.png"` |

---

## 14. Final File System Layout

```
TopDownMedievalPixelArt-Prod/
├── src/
│   ├── __init__.py
│   ├── main.py                         # EDIT: add /leader/* endpoints
│   ├── models.py                       # UNCHANGED
│   ├── config.py                       # EDIT: add leader settings
│   ├── database.py                     # EDIT: add LeaderRecord table
│   ├── generators.py                   # UNCHANGED
│   ├── comfyui_client.py              # EDIT: add upload_reference_image, cancel, patch extensions
│   ├── storage.py                      # UNCHANGED
│   ├── inpainting.py                   # UNCHANGED
│   ├── static_catalog.py              # UNCHANGED
│   ├── leader_models.py               # NEW: enums + Pydantic schemas
│   ├── leader_prompts.py              # NEW: enum injection maps + builders
│   ├── leader_registry.py             # NEW: SQLite-backed CRUD
│   ├── leader_engine.py               # NEW: pipeline orchestrator
├── workflows/
│   ├── txt2img.json                # UNCHANGED
│   ├── inpaint.json                # UNCHANGED
│   ├── story.json                  # UNCHANGED
│   ├── splash.json                 # UNCHANGED (existing tile splash)
│   └── leader/                     # NEW directory
│       ├── leader_splash.json      # NEW: txt2img 1920×1088
│       ├── leader_profile.json     # NEW: img2img 1024×1024, denoise 0.30
│       └── leader_action.json      # NEW: img2img 1920×1088, denoise 0.60
├── tests/
│   └── test_leader_pipeline.py         # NEW
├── leader_references/                  # NEW directory (runtime)
│   └── ref_leader_*.png               # (runtime, gitignored)
├── generated_assets/                   # UNCHANGED
│   └── leader_*_splash.png            # (runtime)
│   └── leader_*_profile.png           # (runtime)
│   └── leader_*_action_*.png          # (runtime)
├── static_tiles/                       # UNCHANGED
├── splash_assets/                      # UNCHANGED
├── mock_assets/                        # UNCHANGED
├── tilemap.db                          # Runtime (now includes leader_records table)
├── .env
├── requirements.txt                    # UNCHANGED
├── docs/
│   ├── architecture.md                 # System architecture reference
│   ├── leader-pipeline-reference.md    # THIS DOCUMENT
│   ├── leader-prompt-guide.md          # Client-facing prompt writing guide
│   ├── tile-prompt-guide.md            # Client-facing tile prompt guide
│   ├── unit-prompt-guide.md            # Client-facing unit prompt guide
│   ├── testing-plan.md                 # Test case checklist
│   ├── next_steps.md                   # Roadmap
└── README.md
```

---

*End of reference.*
