# Migration Plan: ComfyUI API + Category Segmentation

> **Status:** Planning  
> **Branch target:** `feature/comfyui-migration`  
> **Date:** May 26, 2026

---

## Table of Contents

1. [Overview](#1-overview)
2. [Design Principles](#2-design-principles)
3. [Server-Side Generation Modes](#3-server-side-generation-modes)
4. [Category Segmentation](#4-category-segmentation)
5. [Static Asset Injection](#5-static-asset-injection)
6. [ComfyUI API Integration](#6-comfyui-api-integration)
7. [Workflow JSON Templates](#7-workflow-json-templates)
8. [Module Change Summary](#8-module-change-summary)
9. [API Contract (Final)](#9-api-contract-final)
10. [File System Layout (Final)](#10-file-system-layout-final)
11. [Database Schema Changes](#11-database-schema-changes)
12. [.env Configuration Reference](#12-env-configuration-reference)
13. [Implementation Phases](#13-implementation-phases)

---

## 1. Overview

**Current state:** The `Medieval Pixel Art Image Service` loads HuggingFace `diffusers` pipelines
in-process and uses a `mock_mode` boolean to switch between procedural placeholders and real models.
All generators live in a single file (`generators.py`) tightly coupled to both PIL and diffusers.

**Target state:** The service becomes a pure **orchestrator**. It never loads a model weight.
All image generation is delegated to an external **ComfyUI** server via its HTTP + WebSocket API.
Static/pre-made assets are served from a folder structure with zero configuration — drop a PNG, restart.

The game client has **zero awareness** of whether an asset came from ComfyUI or a static PNG.
Generation modes are set entirely via environment variables on the asset server.

---

## 2. Design Principles

1. **The client doesn't know how assets are produced.** `POST /generate` returns a URL. Always.
2. **Ops, not code.** Switching between ComfyUI, static PNGs, or a random mix is a `.env` change + restart.
3. **Drop-in injection.** Adding a new static asset is creating a PNG in the right folder.
4. **Workflows as assets.** ComfyUI workflow JSONs are files in `src/workflows/`, version-controlled alongside code.
5. **No model weights in the FastAPI process.** The web server stays lightweight; GPU lives elsewhere.

---

## 3. Server-Side Generation Modes

Each asset family has its own generation mode, controlled by environment variables.
The client never sees or sets this — it's purely server-side.

### 3.1 Per-family env vars

| Env var | Controls | Valid values |
|---|---|---|
| `BACKGROUND_TILE_MODE` | Terrain tiles | `comfyui`, `static`, `random` |
| `STRUCTURE_MODE` | Buildings | `comfyui`, `static`, `random` |
| `NATURE_OBJECT_MODE` | Trees, rocks, etc. | `comfyui`, `static`, `random` |
| `CHARACTER_SPRITE_MODE` | Character sprites | `comfyui`, `static`, `random` |
| `STORY_MODE` | Cinematic concept art | `comfyui`, `static`* |
| `SPLASH_MODE` | Leader portraits | `comfyui`, `static`* |

> \* `story` and `splash` in `static` mode always render procedural placeholders — they don't have static PNG catalogs.

### 3.2 Mode semantics

| Mode | Behaviour |
|---|---|
| `comfyui` | Always calls the ComfyUI server. Times out with an error if unreachable. |
| `static`  | Serves from `static_tiles/` directory. Falls back to procedural placeholder if the folder is empty. |
| `random`  | Coin-flip per request: `comfyui` or `static`. Controlled by `RANDOM_GENERATION_PROBABILITY`. |

### 3.3 Fallback and defaults

```bash
RANDOM_GENERATION_PROBABILITY=0.5   # 0.0 = always static, 1.0 = always comfyui
DEFAULT_GENERATION_MODE=comfyui     # used if a per-family var is unset
```

If `.env` is completely empty or missing, every family defaults to `comfyui`.

### 3.4 Settings class (config.py)

```python
class Settings(BaseSettings):
    # ...existing fields (output_dir, host, port, splash_width, splash_height)...

    # --- ComfyUI ---
    comfyui_base_url: str = "http://127.0.0.1:8188"
    comfyui_timeout: int = 300       # seconds
    workflow_dir: str = os.path.join(os.path.dirname(__file__), "workflows")

    # --- Static assets ---
    static_tiles_dir: str = os.path.join(BASE_DIR, "static_tiles")

    # --- Per-family generation modes ---
    background_tile_mode: str = "comfyui"
    structure_mode: str = "comfyui"
    nature_object_mode: str = "comfyui"
    character_sprite_mode: str = "comfyui"
    story_mode: str = "comfyui"
    splash_mode: str = "comfyui"
    default_generation_mode: str = "comfyui"
    random_generation_probability: float = 0.5

    def get_mode(self, asset_family: str) -> str:
        """Resolve generation mode for a family, falling back to default."""
        attr = f"{asset_family}_mode"
        return getattr(self, attr, self.default_generation_mode)
```

---

## 4. Category Segmentation

### 4.1 Background tiles: `tile_type`

Four terrain types. When the request is `background_tile`, `tile_type` is **required**.

```python
TileType = Literal["water", "grass", "sand", "stone"]
```

| `tile_type` | Description |
|---|---|
| `water` | River, lake, ocean tile |
| `grass` | Plains, meadow, fields |
| `sand` | Desert, beach, dunes |
| `stone` | Rocky terrain, mountain, cave floor |

In `static` mode, the server looks up `static_tiles/background_tile/{tile_type}.png`.
In `comfyui` mode, `tile_type` is translated into the diffusion prompt
(e.g., `"water"` → `"sparkling blue pixel art water texture, seamless, top-down 2d game"`).

### 4.2 Structures: `structure_subtype`

Four medieval structure categories. Optional — if omitted, a random subtype is selected.

```python
StructureSubtype = Literal["fortification", "production", "civilian", "religious"]
```

| Subtype | Examples | Prompt guidance |
|---|---|---|
| `fortification` | Castle, keep, gatehouse, watchtower, stone walls | "defensive fortification, stone battlements" |
| `production` | Blacksmith, mill, tannery, lumber camp, workshop | "medieval industry, workshop with tools" |
| `civilian` | Tavern, market, houses, well, fountain, bridge | "medieval village building, lively" |
| `religious` | Church, monastery, shrine, chapel, graveyard | "medieval religious building, stone" |

In `static` mode, `structure_subtype` picks a random PNG from the matching subfolder.
If `structure_subtype` is absent, a random PNG is selected from **all** structure subfolders.

### 4.3 Other families

| Family | Segmentation | Behaviour when static |
|---|---|---|
| `nature_object` | None | Random PNG from `static_tiles/nature_object/`, else placeholder |
| `character_sprite` | None | Random PNG from `static_tiles/character_sprite/`, else placeholder |
| `story` | None | Always procedural placeholder (solid darkblue rectangle) |
| `splash` | Character name, title, description, outfit, weapon, background | Procedural mock with portrait silhouette + text |

---

## 5. Static Asset Injection

### 5.1 Directory structure

```
static_tiles/
├── background_tile/
│   ├── water.png
│   ├── grass.png
│   ├── sand.png
│   └── stone.png
├── structure/
│   ├── fortification/
│   │   ├── castle.png
│   │   └── watchtower.png
│   ├── production/
│   │   ├── blacksmith.png
│   │   └── mill.png
│   ├── civilian/
│   │   ├── tavern.png
│   │   └── houses.png
│   └── religious/
│       └── church.png
├── nature_object/
│   ├── tree.png
│   └── boulder.png
└── character_sprite/
    └── knight.png
```

### 5.2 Rules

1. **Filename is irrelevant beyond the folder it lives in.** The catalog loads whatever PNGs exist.
2. **To inject a new asset:** drop a `.png` in the correct folder, restart the server.
3. **To remove an asset:** delete the PNG, restart.
4. **Empty folders** → fall back to procedural placeholder (coloured rectangle + label).
5. **Non-PNG files** (`.jpg`, `.gif`, directories) are silently ignored.

### 5.3 StaticCatalog (`src/static_catalog.py`)

```python
class StaticCatalog:
    """Scans static_tiles/ on init and builds an in-memory lookup."""

    def __init__(self, root_dir: str):
        self._tiles: dict[str, dict[str | None, list[str]]] = {}
        # _tiles["background_tile"]["water"] = ["water.png"]
        # _tiles["structure"]["fortification"] = ["castle.png", "watchtower.png"]
        # _tiles["structure"][None] = [all structure PNGs from all subfolders]
        self._scan(root_dir)

    def resolve_tile(self, tile_type: str) -> str | None:
        """Return exact file path for a tile type, or None."""
        ...

    def resolve_random(self, family: str, subtype: str | None = None) -> str | None:
        """Return a random PNG path for a family/subtype, or None."""
        ...

    def list_tile_types(self) -> list[str]:
        """Return ["water", "grass", "sand", "stone"] if they exist."""
        ...

    def list_structure_subtypes(self) -> list[str]:
        """Return ["fortification", "production", ...] for subtypes that have PNGs."""
        ...
```

### 5.4 GET /catalog

Discovery endpoint for the game client. Exposes what's *available*, not how it's produced.

```json
{
  "background_tile": {
    "tile_types": ["water", "grass", "sand", "stone"]
  },
  "structure": {
    "subtypes": ["fortification", "production", "civilian", "religious"]
  },
  "nature_object": {
    "available": true
  },
  "character_sprite": {
    "available": true
  }
}
```

---

## 6. ComfyUI API Integration

### 6.1 Protocol

ComfyUI exposes a REST-ish API on port `8188` by default. The key endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/prompt` | POST | Submit a workflow JSON. Body: `{"prompt": {...}, "client_id": "..."}`. Returns `{"prompt_id": "..."}`. |
| `/history/{prompt_id}` | GET | Poll for results. Returns the full execution output including saved image filenames. |
| `/view` | GET | Fetch raw image bytes. Query params: `filename`, `subfolder`, `type`. |
| `/upload/image` | POST | Upload an image (multipart/form-data) to ComfyUI's `input/` folder. |
| `/ws` | WebSocket | Real-time progress: `execution_start`, `executing`, `progress`, `executed`, `execution_cached`. |
| `/queue` | DELETE | Cancel pending/running prompts. |

### 6.2 Request flow

```
                          FastAPI (our server)
                               │
                               │ 1. Receive GenerationRequest
                               │ 2. Load workflow JSON template
                               │ 3. Upload base image (if CoW inpainting)
                               │ 4. Patch workflow: inject prompt, seed, filenames
                               │
                               ▼
                      POST /prompt ──────►  ComfyUI Server
                               ◄──────  prompt_id
                               │
                               │ 5. Poll GET /history/{id}  (or listen on WS)
                               │    ...wait for completion...
                               │
                               ▼
                      GET /view ──────────►  ComfyUI Server
                               ◄──────  PNG bytes
                               │
                               │ 6. Save to AssetStore
                               │ 7. Write AssetRecord to SQLite
                               │ 8. Return URL to client
                               ▼
                          Game Client
```

### 6.3 ComfyUIClient (`src/comfyui_client.py`)

```python
class ComfyUIClient:
    """Thin HTTP+WS client for a ComfyUI server."""

    def __init__(self, base_url: str, timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def upload_image(self, pil_image: Image.Image, filename: str) -> str:
        """Upload a PIL image. Returns the stored filename on ComfyUI."""
        ...

    async def queue_workflow(self, workflow: dict) -> str:
        """Submit workflow JSON. Returns prompt_id."""
        ...

    async def wait_for_completion(self, prompt_id: str) -> bool:
        """Block until prompt finishes (WS or polling)."""
        ...

    async def get_result(self, prompt_id: str) -> dict:
        """GET /history/{prompt_id} → parsed output dict."""
        ...

    async def download_image(self, filename: str, subfolder: str = "",
                              folder_type: str = "output") -> bytes:
        """GET /view → raw PNG bytes."""
        ...

    async def generate(self, workflow_path: str,
                       inputs: dict[str, str],
                       input_images: dict[str, Image.Image] | None = None
                       ) -> Image.Image:
        """
        High-level convenience:
          1. Upload any input_images
          2. Load & patch workflow JSON
          3. Queue → wait → download → return PIL Image
        """
        ...
```

### 6.4 Error handling

| Failure | Response |
|---|---|
| ComfyUI unreachable at startup | Log warning, service starts in degraded mode (static families work, comfyui families return 503) |
| ComfyUI unreachable mid-request | 503 + `{"detail": "Generation service unavailable"}` |
| Prompt times out | 504 + `{"detail": "Generation timed out after {n}s"}` |
| Workflow returns no images | 500 + `{"detail": "Workflow produced no output"}` |

### 6.5 Startup health check

On app startup (`lifespan`), the service pings `GET /system_stats` on the ComfyUI server.
If reachable, logs "ComfyUI connected". If not, logs a warning but starts anyway —
families set to `comfyui` will return 503s until it comes back.

---

## 7. Workflow JSON Templates

Four ComfyUI workflows, exported from the ComfyUI UI in "Save (API Format)" mode,
stored as version-controlled JSON files.

### 7.1 `txt2img.json`

**Purpose:** `structure`, `nature_object`, `character_sprite` (text-to-image).

**Patchable parameters:**

| Node input | Patching |
|---|---|
| `positive_prompt` text | Injected with rich prompt (family + subtype + pixel art modifiers) |
| `negative_prompt` text | Static: `"blurry, low res, realistic, 3d render, photorealistic"` |
| `KSampler.seed` | Random int per request |
| `EmptyLatentImage.width` | 512 (fixed for these families) |
| `EmptyLatentImage.height` | 512 |
| `CheckpointLoader.ckpt_name` | Configurable via env: `COMFYUI_CHECKPOINT` |

### 7.2 `inpaint.json`

**Purpose:** `background_tile` with optional Copy-on-Write inpainting.

**Patchable parameters:**

| Node input | Patching |
|---|---|
| `LoadImage.image` | Base image filename (uploaded first) |
| `LoadMaskMask` | Generated locally, uploaded, filename injected |
| `positive_prompt` | Translated from `fill_type` via `get_inpaint_prompt()` |
| `negative_prompt` | Static |
| `KSampler.seed` | Random int |
| `KSampler.denoise` | 0.99 (near-full replacement inside mask) |

**CoW inpainting flow:**

1. Client sends `base_image_id` + list of `inpaints[]`
2. Server loads base image from AssetStore
3. For each inpaint patch:
   - Generate mask → upload mask
   - Upload current image → patch workflow → queue → download result
   - Result becomes the new "current image" for the next patch
4. Final image saved

### 7.3 `story.json`

**Purpose:** 16:9 cinematic concept art for story scenes.

**Patchable parameters:**

| Node input | Patching |
|---|---|
| `positive_prompt` | Client prompt + `"Epic cliffhanger concept art, dramatic dynamic lighting, ultra detailed, fantasy style"` prepended, `"--ar 16:9"` appended |
| `EmptyLatentImage.width` | 1024 |
| `EmptyLatentImage.height` | 576 (16:9) |
| `KSampler.seed` | Random int |

### 7.4 `splash.json`

**Purpose:** Character portrait / splash art (256×256 leader profile).

**Patchable parameters:**

| Node input | Patching |
|---|---|
| `positive_prompt` | Built from `style`, `description`, `outfit`, `weapon`, `background` fields |
| `EmptyLatentImage.width` | 512 (generated at 512, resized to 256 after) |
| `EmptyLatentImage.height` | 512 |
| `KSampler.seed` | Random int |

---

## 8. Module Change Summary

| File | Action | Key changes |
|---|---|---|
| **`src/config.py`** | Edit | Add all new settings (section 3.4) |
| **`src/models.py`** | Edit | Add `TileType`, `StructureSubtype`; extend `GenerationRequest` with `tile_type` + `structure_subtype` |
| **`src/comfyui_client.py`** | **New** | `ComfyUIClient` class (section 6.3) |
| **`src/static_catalog.py`** | **New** | `StaticCatalog` class (section 5.3) |
| **`src/workflows/txt2img.json`** | **New** | Text-to-image workflow template |
| **`src/workflows/inpaint.json`** | **New** | Inpainting workflow template |
| **`src/workflows/story.json`** | **New** | Story concept art workflow template |
| **`src/workflows/splash.json`** | **New** | Splash portrait workflow template |
| **`src/generators.py`** | **Rewrite** | Remove `Flux2Generator`, `ZImageTurboGenerator`, `MockGenerator`, diffusers imports, `init_pipelines()`. Add `ComfyUIGenerator` and `StaticTileGenerator`. Rewrite `get_generator()`. |
| **`src/main.py`** | Edit | Add `GET /catalog`. Update lifespan: remove `init_pipelines()`, add catalog init + ComfyUI health check. |
| **`src/database.py`** | Edit | Add `tile_type`, `structure_subtype`, `generation_mode` columns to `AssetRecord` |
| **`src/storage.py`** | Minimal edit | Add `save_from_path()` convenience method for static assets |
| **`src/inpainting.py`** | Retain | `create_inpaint_mask()` and `get_inpaint_prompt()` stay. `apply_inpaint()` (mock colour fill) is removed. |
| **`requirements.txt`** | Edit | **Remove:** `torch`, `torchvision`, `diffusers`, `transformers`, `accelerate`. **Add:** `websocket-client`, `httpx`. |
| **`static_tiles/`** | **New dir** | Static asset tree (section 5.1) |
| **`mock_assets/`** | Retire | No longer used; `static_tiles/` replaces it |
| **`architecture.md`** | Update | Reflect ComfyUI architecture |
| **`next_steps.md`** | Rewrite | New checklist reflecting ComfyUI pivot |

---

## 9. API Contract (Final)

### POST /generate

```json
{
  "asset_family": "background_tile",
  "tile_type": "water",
  "prompt": null,
  "base_image_id": null,
  "inpaints": [],
  "structure_subtype": null
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `asset_family` | `Literal["structure","nature_object","background_tile","character_sprite","story","splash"]` | ✅ | |
| `tile_type` | `Literal["water","grass","sand","stone"]` | Required for `background_tile`, ignored otherwise | |
| `structure_subtype` | `Literal["fortification","production","civilian","religious"]` | Optional (`structure` only) | If absent for structures, random subtype is selected |
| `prompt` | `str` | — | High-level description |
| `base_image_id` | `str` | — | UUID of existing tile for CoW inpainting |
| `inpaints[]` | `[{point_a: {x, y}, point_b: {x, y}, fill_type: str}]` | — | Bounding box inpainting patches |

**Response:**

```json
{
  "url": "/assets/a1b2c3d4-e5f6-...png",
  "asset_family": "background_tile",
  "tile_type": "water",
  "generation_mode": "comfyui",
  "status": "completed"
}
```

> `generation_mode` in the response tells the client how it was produced (`"comfyui"`, `"static"`, or `"placeholder"`). This is purely informational — the image is the same format regardless.

### POST /splash

Unchanged from current. `character_name`, `title`, `description`, `style`, `outfit`, `weapon`, `background`.

### GET /assets/{filename}

Unchanged. Returns `image/png`.

### GET /catalog

```json
{
  "background_tile": {
    "tile_types": ["water", "grass", "sand", "stone"]
  },
  "structure": {
    "subtypes": ["fortification", "production", "civilian", "religious"]
  },
  "nature_object": {
    "available": true
  },
  "character_sprite": {
    "available": false,
    "placeholder": true
  }
}
```

### GET /health

```json
{
  "status": "ok",
  "comfyui_connected": true,
  "modes": {
    "background_tile": "random",
    "structure": "static",
    "nature_object": "comfyui",
    "character_sprite": "comfyui",
    "story": "comfyui",
    "splash": "comfyui"
  }
}
```

---

## 10. File System Layout (Final)

```
TopDownMedievalPixelArt-Prod/
├── src/
│   ├── __init__.py
│   ├── main.py                # FastAPI app, updated endpoints
│   ├── models.py              # Updated Pydantic schemas
│   ├── config.py              # Updated Settings
│   ├── generators.py          # Rewritten: ComfyUIGenerator + StaticTileGenerator
│   ├── comfyui_client.py      # NEW: ComfyUI HTTP+WS client
│   ├── static_catalog.py      # NEW: static PNG catalog scanner
│   ├── inpainting.py          # Retained: mask creation + prompt mapping
│   ├── storage.py             # AssetStore (add save_from_path)
│   ├── database.py            # Updated AssetRecord schema
│   └── workflows/             # NEW: ComfyUI API-format workflow JSONs
│       ├── txt2img.json
│       ├── inpaint.json
│       ├── story.json
│       └── splash.json
├── static_tiles/              # NEW: pre-made PNG assets
│   ├── background_tile/
│   │   ├── water.png
│   │   ├── grass.png
│   │   ├── sand.png
│   │   └── stone.png
│   ├── structure/
│   │   ├── fortification/
│   │   │   ├── castle.png
│   │   │   └── watchtower.png
│   │   ├── production/
│   │   │   ├── blacksmith.png
│   │   │   └── mill.png
│   │   ├── civilian/
│   │   │   ├── tavern.png
│   │   │   └── houses.png
│   │   └── religious/
│   │       └── church.png
│   ├── nature_object/
│   │   ├── tree.png
│   │   └── boulder.png
│   └── character_sprite/
│       └── knight.png
├── generated_assets/          # Output directory (runtime)
├── splash_assets/             # Splash output directory (runtime)
├── tilemap.db                 # SQLite database (runtime)
├── .env                       # Environment configuration
├── requirements.txt           # Updated dependencies
├── architecture.md            # Updated
├── next_steps.md              # Updated
├── inpainting_workflow.md     # Updated for ComfyUI
└── README.md
```

---

## 11. Database Schema Changes

### Updated `AssetRecord`

```python
class AssetRecord(Base):
    __tablename__ = "asset_records"

    id = Column(String, primary_key=True, index=True)
    asset_family = Column(String, index=True, nullable=False)
    base_image_id = Column(String, index=True, nullable=True)
    coords_x = Column(Integer, nullable=True)
    coords_y = Column(Integer, nullable=True)
    inpaints = Column(JSON, nullable=True)
    character_name = Column(String, nullable=True)

    # --- NEW COLUMNS ---
    tile_type = Column(String, nullable=True)              # "water", "grass", "sand", "stone"
    structure_subtype = Column(String, nullable=True)      # "fortification", etc.
    generation_mode = Column(String, nullable=True)        # "comfyui", "static", "placeholder"

    created_at = Column(DateTime, server_default=func.now())
```

---

## 12. .env Configuration Reference

```bash
# === Server ===
HOST=0.0.0.0
PORT=8000

# === ComfyUI ===
COMFYUI_BASE_URL=http://127.0.0.1:8188
COMFYUI_TIMEOUT=300
# COMFYUI_CHECKPOINT=sd_xl_turbo_1.0.safetensors   # optional: override default model

# === Generation modes (per family) ===
# Valid: "comfyui" | "static" | "random"
BACKGROUND_TILE_MODE=comfyui
STRUCTURE_MODE=random
NATURE_OBJECT_MODE=static
CHARACTER_SPRITE_MODE=comfyui
STORY_MODE=comfyui
SPLASH_MODE=comfyui

# === Fallbacks ===
DEFAULT_GENERATION_MODE=comfyui
RANDOM_GENERATION_PROBABILITY=0.5

# === Paths ===
OUTPUT_DIR=./generated_assets
STATIC_TILES_DIR=./static_tiles
WORKFLOW_DIR=./src/workflows
SPLASH_DIR=./splash_assets

# === Splash defaults ===
SPLASH_WIDTH=256
SPLASH_HEIGHT=256

# Example: fully offline development mode -----------------
# BACKGROUND_TILE_MODE=static
# STRUCTURE_MODE=static
# NATURE_OBJECT_MODE=static
# CHARACTER_SPRITE_MODE=static
# STORY_MODE=static
# SPLASH_MODE=static
```

---

## 13. Implementation Phases

### Phase 1: Foundation (no behaviour change to API)

1. **Create `static_tiles/` directory structure** with empty folders.
2. **Add new settings** to `config.py` (generation modes, ComfyUI URL, paths).
3. **Implement `static_catalog.py`** — scans folders, builds in-memory lookup.
4. **Implement `static_tiles/` procedural placeholder fallback** — when a folder is empty, return a coloured rectangle with label.
5. **Update `GeneratingRequest` model** — add `tile_type` and `structure_subtype` fields.
6. **Update `database.py`** — add new columns to `AssetRecord`.

### Phase 2: ComfyUI client

1. **Implement `comfyui_client.py`** — upload, queue, poll/download.
2. **Export the four workflow JSONs** from ComfyUI UI → `src/workflows/`.
3. **Test end-to-end:** `comfyui_client.generate("txt2img.json", {"positive_prompt": "test"})` → returns a PIL Image.

### Phase 3: Replace generators

1. **Implement `ComfyUIGenerator`** — wraps `ComfyUIClient`, patches workflow JSONs.
2. **Implement `StaticTileGenerator`** — wraps `StaticCatalog`, serves PNGs.
3. **Rewrite `get_generator()`** — routes based on `settings.get_mode()`.
4. **Add `GET /catalog` endpoint.**
5. **Update `main.py` lifespan** — init catalog, ComfyUI health check.
6. **Remove old diffusers/torch code:** `Flux2Generator`, `ZImageTurboGenerator`, `init_pipelines()`, old `MockGenerator`.

### Phase 4: Inpainting rewire

1. **Update `ComfyUIClient`** to support img2img/inpainting flow (upload base + mask).
2. **Verify CoW semantics** — multiple sequential inpaints on same canvas.
3. **Remove `apply_inpaint()`** mock function.

### Phase 5: Polish & docs

1. **Update `requirements.txt`** — remove torch family, add httpx + websocket-client.
2. **Update `architecture.md`**, **`next_steps.md`**, **`inpainting_workflow.md`**.
3. **Update `README.md`** to reflect ComfyUI architecture.
4. **Add example `.env.example`** file.
5. **End-to-end smoke tests** — one request per family in each mode.

---

*End of plan.*

