# Image Diffusion Service: Production Architecture

## 1. System Overview
The Medieval Pixel Art Image Service is a decoupled web service that provides
on-demand generative AI assets for a top-down medieval game.  The web server is
a lightweight orchestrator — it never loads model weights.  All image generation
is delegated to an external **ComfyUI** server via its HTTP + WebSocket API.
Static/pre-made assets are served from a folder structure with zero configuration.
A **placeholder** mode provides always-available procedural fallbacks.

## 2. Core Operational Flow
1. **Request Intake**: `FastAPI` validates incoming payloads (`LeaderRequest`,
   `StructureRequest`, `ObjectRequest`, `TerrainRequest`, `UnitRequest`) using
   strict Pydantic schemas.
2. **Mode Resolution**: Each pipeline engine checks `config.yaml` →
   `generation.modes.{family}` (or `generation.default_mode`) and routes to the
   appropriate generator: `comfyui`, `static`, or `placeholder`.
3. **Asset Processing**:
   - **ComfyUI**: Loads a workflow JSON template, patches in the prompt and seed,
     uploads any input images (for img2img), submits to ComfyUI, polls via
     WebSocket, downloads the result.
   - **Static**: Serves pre-made PNGs from `static_tiles/`. Falls back to
     procedural placeholder if no static PNG is available.
   - **Placeholder**: Always returns a procedural coloured rectangle with text
     label — zero external dependencies.
4. **Caching & Delivery**: The final asset is stored in an in-memory LRU cache
   (thread-safe), persisted to disk, and indexed in SQLite. The asset URL is
   returned to the client.

## 3. Prompt Architecture: Templates > Python

The service follows a strict separation of concerns for prompt assembly:

| Layer | Where | What |
|-------|-------|------|
| **Workflow JSON** | `workflows/*.json` | Model, resolution, sampler, scheduler, steps, CFG, denoise, LoRA nodes, output prefix — everything ComfyUI needs that does NOT vary per request |
| **Prompt templates** | `config/prompt_templates.json` | Prefix + suffix for each asset family. Contains ALL style directives, camera framing, quality tags, LoRA triggers (`<tdp>`), and format constraints. The Python layer never hardcodes prompt prose. |
| **Enum injection maps** | `src/{leader,tile,unit}/prompts.py` | Hand-crafted prose per enum value (archetype, culture, biome, mood, etc.). Structured data mappings — key → rich description. |
| **Assembly logic** | `src/{leader,tile,unit}/prompts.py` | Glue that joins enum prose + user description into the `inner` string, then wraps with template prefix/suffix. No style words. |

**Key principle**: The template JSON is the single source of truth for HOW
something is depicted. The Python layer only contributes WHAT is depicted.

The `<tdp>` LoRA trigger appears in the structure, object, terrain, and unit
templates.  It activates a LoRA that enforces **top-down camera angle** with
medieval pixel-art styling.  Background tiles (seamless ground textures) and
leader portraits use separate templates/workflows without this LoRA.

## 4. Component Architecture

### A. API Layer (`src/main.py` & per-pipeline `models.py`)
- **FastAPI**: Async HTTP server with CORS middleware. Current endpoints:
  `POST /leader`, `GET /leader/{leader_id}`, `DELETE /leader/{leader_id}`,
  `POST /structure`, `GET /structure/{id}`, `DELETE /structure/{id}`,
  `POST /object`, `GET /object/{id}`, `DELETE /object/{id}`,
  `POST /terrain`, `GET /terrain/{id}`, `DELETE /terrain/{id}`,
  `POST /unit`, `GET /unit/{unit_id}`, `DELETE /unit/{unit_id}`,
  `GET /health`, `GET /catalog`, `GET /assets/{filename}`,
  plus `/structure/catalog`, `/object/catalog`, `/terrain/catalog`, `/unit/catalog`.
- **Pydantic**: Typed request/response schemas with enum validation.
- **Fully async**: Generation runs on the asyncio event loop via `httpx` + `websockets`.

### B. Storage Layer (`src/storage.py`)
- **AssetStore**: Thread-safe in-memory LRU cache (OrderedDict + Lock, default
  1000 entries).  Transparent disk fallback for cache misses.  Path traversal
  protection via `os.path.basename()`.

### C. ComfyUI Client (`src/comfyui_client.py`)
- **ComfyUIClient**: Async HTTP + WebSocket client handling the full lifecycle:
  image upload, workflow submission, progress polling, result download, and
  health checks.  Workflow patching targets Flux2 Klein node types
  (SamplerCustomAdvanced, EmptyFlux2LatentImage — no negative prompts).

### D. Static Catalog (`src/static_catalog.py`)
- Scans `static_tiles/` at startup and builds an in-memory lookup by family
  and subtype.  Powers `GET /catalog` and static asset resolution.

### E. Leader Pipeline (`src/leader/`)
- **Three-stage generation**: splash (txt2img, canonical visual identity) →
  profile (img2img, close-crop portrait, denoise=0.30) → action (img2img,
  denoise=0.60).
- **Multi-leader action**: txt2img composite prompt weaving together multiple
  leaders' descriptions. Triggered by `leader_ids` list.
- **Structured prompt injection**: Clients select enum values; server maps to
  rich prose via `src/leader/prompts.py`.
- **Seed anchoring**: Splash seed stored in `LeaderRecord` and re-used for
  profile/action to maximize img2img consistency.
- **SQLite-backed**: `LeaderRecord` table in `src/database.py`.

### F. Tile Pipeline (`src/tile/`)
- **Three families**: structures, objects, terrain. Each request generates one
  128×128 game tile (downscaled from 1024×1024 generation).
- **Enum-driven prompt assembly**: `src/tile/prompts.py` with prose injection maps.
- **Background tiles**: Separate engine (`src/tile/background_engine.py`) and
  workflow (`background_tile.json`) for seamless ground textures — no LoRA,
  no white background isolation.
- **Static fallback**: `StaticTileEngine` resolves from `static_tiles/`.
- **SQLite-backed**: `StructureRecord`, `ObjectRecord`, `TerrainRecord`.

### G. Unit Pipeline (`src/unit/`)
- **Single-sprite generation**: Each unit type (archer, scout, settler, warrior)
  produces one 128×128 south-facing sprite.
- **Enum-driven prompt assembly**: `src/unit/prompts.py` with injection map.
  South-facing direction and front-view framing live in the template.
- **Static fallback**: `StaticUnitEngine` resolves from `static_tiles/`.
- **SQLite-backed**: `UnitRecord`.

### H. Persistence (`src/database.py`)
- **SQLite** via SQLAlchemy. `Base.metadata.create_all()` at startup (dev
  convenience — replace with Alembic for production migrations).
- **AssetRecord**: Tracks every generated asset: id, family, generation mode.
- **LeaderRecord**: Canonical splash image, seed, prompt, profile/action image
  IDs, reference filename.

## 5. Workflow JSON Templates

Live in `workflows/`.  Resolution, steps, CFG, sampler, scheduler, denoise,
LoRA nodes, and output prefix are all baked into the JSONs — Python only
injects prompt text and seed.

| Workflow | Used by | Notes |
|---|---|---|
| `txt2img.json` | Structures, objects, terrain, units | Top-down tile assets. `<tdp>` LoRA trigger in prompt template. |
| `background_tile.json` | Background ground tiles (water, grass, sand, stone, dirt) | Seamless textures — NO `<tdp>` LoRA. |
| `leader/leader_splash.json` | Leader splash (txt2img, 1920×1088) | Establishes canonical visual identity. |
| `leader/leader_profile.json` | Leader profile (img2img, denoise=0.30) | Uses splash as reference image. |
| `leader/leader_action.json` | Leader action (img2img, denoise=0.60 for single; txt2img for multi) | Uses splash as reference (single-leader only). |

## 6. Generation Modes (Per-Family)

| Mode | Behaviour |
|---|---|
| `comfyui` | Always calls ComfyUI. 503 if unreachable. |
| `static` | Serves from `static_tiles/`. Falls back to placeholder. |
| `placeholder` | Procedural coloured placeholder — zero dependencies. |

Controlled via `config.yaml` (version-controlled) with `.env` overrides using
`__` delimiter for nested keys — ops-level control with zero code changes.

## 7. Path to Scaled Execution (Future)

- **Task Queues**: Celery + Redis for non-blocking generation at scale.
- **Object Storage**: S3 / Cloudflare R2 for multi-node asset sharing.
- **GPU Cloud**: Separate web server hosting from GPU inference nodes.
