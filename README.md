# Medieval Pixel Art Image Service

An on-demand generative AI microservice that produces pixel art game assets for a top-down medieval game. Built with **FastAPI** and **ComfyUI** as the inference backend. Generation modes are configurable per asset family in `config.yaml` — no code changes needed.

**Zero-dependency testing mode available** — run the full API with procedural placeholders, no GPU or ComfyUI required.

---

## What It Does

The service accepts structured requests describing *what* to generate and returns a public URL pointing to the finished PNG asset.

| Asset Family | Example | Description |
|---|---|---|
| `structure` | castle, blacksmith | Buildings and constructed objects |
| `nature_object` | tree, boulder | Organic world decorations |
| `background_tile` | grass, dirt, water | Repeatable terrain tiles |
| `character_sprite` | knight, archer | Character sprites |
| `story` | "The dragon attacks" | Epic 16:9 cinematic concept art |
| `splash` | "King Aldric" | Leader portrait / profile card |

It also supports:
- **Copy-on-Write inpainting**: take an existing background tile, specify a bounding box (e.g., a river cutting across the tile), and the service fills only that region — leaving the rest untouched.
- **Leader pipeline**: three-stage generation (splash → profile → action) with img2img character consistency via reference images.

---

## Architecture

```
Game Client
    │
    ▼
┌──────────────────────────────────────────┐
│  FastAPI (main.py)                       │
│  POST /generate   POST /splash           │
│  POST /leader     GET  /assets/...       │
│  GET  /health     GET  /catalog          │
│  GET  /modes                             │
├──────────────────────────────────────────┤
│  Pydantic Models (models.py)             │
│  GenerationRequest, SplashRequest, etc.  │
├──────────────────┬───────────────────────┤
│  Generator       │  Leader Engine        │
│  (generators.py) │  (leader_engine.py)   │
│  ├ ComfyUI       │  ├ Splash (txt2img)   │
│  ├ StaticTile    │  ├ Profile (img2img)  │
│  └ Placeholder   │  └ Action (img2img)   │
├──────────────────┴───────────────────────┤
│  ComfyUIClient (comfyui_client.py)       │
│  Async HTTP+WS: httpx + websockets       │
├──────────────────────────────────────────┤
│  Inpainting Engine (inpainting.py)       │
│  Mask creation + prompt translation      │
├──────────────────────────────────────────┤
│  AssetStore (storage.py)                 │
│  In-memory LRU cache + disk fallback     │
├───────────────────────────────────────��──┤
│  SQLite DB (database.py)                 │
│  AssetRecord + LeaderRecord              │
└──────────────────────────────────────────┘
```

### Generation Modes

Each asset family can be independently configured to one of four modes:

| Mode | Behaviour |
|---|---|
| `comfyui` | Delegates to an external ComfyUI server |
| `static`  | Serves pre-made PNGs from `static_tiles/` directory |
| `placeholder` | Always returns a procedural coloured placeholder (zero dependencies) |
| `random`  | Coin-flip per request between `comfyui` and `static` |

Set in `config.yaml` — no code changes. The game client never knows which mode produced the image.

---

## Project Structure

```
.
├── src/
│   ├── main.py               # FastAPI application, endpoints, CORS, lifecycle
│   ├── models.py             # Pydantic request/response schemas
│   ├── config.py             # Pydantic Settings (modes, paths, ComfyUI URL)
│   ├── generators.py         # ImageGenerator ABC + ComfyUIGenerator + StaticTileGenerator
│   ├── comfyui_client.py    # HTTP + WebSocket client for ComfyUI
│   ├── inpainting.py         # Mask creation, prompt mapping
│   ├── storage.py            # AssetStore: in-memory LRU cache + disk I/O
│   ├── database.py           # SQLAlchemy + SQLite (AssetRecord, LeaderRecord)
│   ├── static_catalog.py     # Scans static_tiles/ for available PNGs
│   ├── leader_models.py      # Leader enums + Pydantic schemas
│   ├── leader_prompts.py     # Enum injection maps + prompt builders
│   ├── leader_registry.py    # SQLite-backed leader CRUD
│   ├── leader_engine.py      # Splash → profile → action orchestrator
│   └── workflows/            # ComfyUI API-format workflow JSONs
│       ├── txt2img.json
│       ├── inpaint.json
│       ├── story.json
│       ├── splash.json
│       └── leader/
│           ���── leader_splash.json
│           ├── leader_profile.json
│           └── leader_action.json
├── static_tiles/             # Pre-made PNG assets (used in static mode)
├── leader_references/        # Runtime reference images for leader pipeline
├── generated_assets/         # Output directory (runtime)
├── splash_assets/            # Splash output directory (runtime)
├── config.yaml              # Version-controlled config (modes, paths, prompts)
├── .env.example              # Deployment-only overrides (ComfyUI IP, host, port)
├── requirements.txt          # Python dependencies
├── tilemap.db                # SQLite database (runtime)
└── docs/                     # Architecture, plans, guides
```

---

## Configuration

All behavioural settings (generation modes, paths, prompt defaults, resolution) live in
**`config.yaml`** and are version-controlled for reproducibility.

The **`.env`** file is kept lean — it only contains deployment-specific overrides
that differ between machines:

```bash
# .env — only what changes per deployment
COMFYUI__BASE_URL=http://10.0.0.5:8188   # ComfyUI server IP
HOST=0.0.0.0                              # bind address
PORT=8000                                 # bind port
```

Use `__` (double underscore) as the nesting delimiter. For example,
`COMFYUI__BASE_URL` overrides `comfyui.base_url` in `config.yaml`.

### Load order (later sources win)

1. Pydantic defaults (in `src/config.py`)
2. **`config.yaml`** — primary source of truth, committed to git
3. `.env` file — deployment-specific
4. Environment variables — highest priority

---

## Getting Started

### Prerequisites

- Python 3.10+
- A running [ComfyUI](https://github.com/comfyanonymous/ComfyUI) instance (for `comfyui` mode)
- (Optional) Pre-made PNGs in `static_tiles/` (for `static` mode)

### Install

```bash
cd TopDownMedievalPixelArt-Prod
pip install -r requirements.txt
```

### Run (Static Mode — No GPU Required)

```bash
# Edit config.yaml: set generation.modes.* to "static"
# Example:
#   generation:
#     modes:
#       background_tile: "static"
#       structure: "static"
#       ...

uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

The service is now live at `http://localhost:8000`. All endpoints work with pre-made static PNGs and procedural placeholders.

### Run (ComfyUI Mode — Requires ComfyUI Server)

```bash
# config.yaml defaults to comfyui for all families — no changes needed.
# Only create .env if your ComfyUI server is not at 127.0.0.1:8188:
echo 'COMFYUI__BASE_URL=http://your-comfyui-host:8188' > .env

uvicorn src.main:app --host 0.0.0.0 --port 8000
```

---

## API Reference

### `GET /health`

Returns service status, generation modes, ComfyUI connectivity, and registered leader count.

```json
{
  "status": "ok",
  "comfyui_connected": true,
  "modes": {
    "background_tile": "comfyui",
    "structure": "static",
    "nature_object": "comfyui",
    "character_sprite": "comfyui",
    "story": "comfyui",
    "splash": "comfyui"
  },
  "leaders_registered": 3
}
```

### `GET /modes`

Returns the active generation mode for every asset family, plus the list of valid modes.

```json
{
  "modes": {
    "background_tile": "comfyui",
    "structure": "static",
    "nature_object": "comfyui",
    "character_sprite": "comfyui",
    "story": "comfyui",
    "splash": "comfyui",
    "leader": "comfyui"
  },
  "valid_modes": ["comfyui", "static", "placeholder", "random"]
}
```

### `GET /catalog`

Returns available tile types and structure subtypes from `static_tiles/`.

```json
{
  "background_tile": { "tile_types": ["water", "grass", "sand", "stone"] },
  "structure": { "subtypes": ["fortification", "production", "civilian", "religious"] },
  "nature_object": { "available": true },
  "character_sprite": { "available": true }
}
```

### `POST /generate`

Generate a new game asset.

**Request:**

```json
{
  "asset_family": "background_tile",
  "tile_type": "water",
  "prompt": null,
  "base_image_id": null,
  "inpaints": [
    {
      "point_a": { "x": 100, "y": 200 },
      "point_b": { "x": 400, "y": 300 },
      "fill_type": "water"
    }
  ],
  "structure_subtype": null
}
```

| Field | Required | Description |
|---|---|---|
| `asset_family` | ✅ | One of: `structure`, `nature_object`, `background_tile`, `character_sprite`, `story`, `splash` |
| `tile_type` | Required for `background_tile` | `"water"`, `"grass"`, `"sand"`, `"stone"` |
| `structure_subtype` | Optional (`structure` only) | `"fortification"`, `"production"`, `"civilian"`, `"religious"` |
| `prompt` | — | Text description for text-to-image generation |
| `base_image_id` | — | UUID of an existing tile for Copy-on-Write inpainting |
| `inpaints` | — | List of bounding-box regions to inpaint with a fill type |

**Fill types:** `water`, `gravel_road`, `grass`, `dirt`, `stone_floor`, `lava`

**Response:**

```json
{
  "url": "/assets/a1b2c3d4-...png",
  "asset_family": "background_tile",
  "tile_type": "water",
  "generation_mode": "comfyui",
  "status": "completed"
}
```

### `POST /splash`

Generate a character portrait / splash art.

**Request:**

```json
{
  "character_name": "King Aldric",
  "title": "King",
  "description": "Grizzled veteran in ornate plate armor",
  "style": "pixel_art",
  "outfit": "ornate golden plate armor with crimson cape",
  "weapon": "flaming longsword",
  "background": "banner"
}
```

**Response:**

```json
{
  "url": "/assets/b2c3d4e5-..._splash.png",
  "character_name": "King Aldric",
  "status": "completed"
}
```

### `POST /leader`

Generate a leader asset through the splash → profile → action pipeline.

**Request (splash):**

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

**Response:**

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

Chain calls using the returned `leader_id`:
1. `POST /leader` with `asset_type: "splash"` → get `leader_id`
2. `POST /leader` with `asset_type: "profile"` + `leader_id`
3. `POST /leader` with `asset_type: "action"` + `leader_id` + `action_category` + `action_description`

### `GET /leader`

List all registered leaders.

### `GET /leader/{leader_id}`

Get a specific leader's info and asset URLs.

### `DELETE /leader/{leader_id}`

Remove a leader and their reference image.

### `GET /assets/{filename}`

Download a previously generated asset. Returns `image/png`.

---

## How Inpainting Works

1. The game client sends a `base_image_id` (an existing tile UUID) plus a list of `inpaints`
2. Each inpaint specifies a bounding box (`point_a` → `point_b`) and a `fill_type` like `"water"`
3. The service loads the base image (Copy-on-Write — the original is never mutated)
4. A binary mask is created from the bounding box (with optional Gaussian blur for softer edges)
5. The `fill_type` is translated to a rich diffusion prompt (e.g., `"water"` → `"sparkling blue pixel art river water texture, seamless, top-down 2d game"`)
6. The base image + mask are uploaded to ComfyUI, which runs the inpainting workflow
7. Each inpaint is applied sequentially to the same canvas
8. The final image is saved and its URL returned

---

## Design Decisions

- **ComfyUI as inference backend**: The FastAPI server never loads model weights — it delegates all generation to an external ComfyUI instance. The web server stays lightweight at ~200MB RAM.
- **Fully async ComfyUI client**: Uses ``httpx`` + ``websockets`` for non-blocking I/O. Generation runs directly on the asyncio event loop — no thread-pool needed, enabling high concurrency without worker saturation.
- **Per-family generation modes**: Each asset family can independently use `comfyui`, `static`, `placeholder`, or `random` mode via `config.yaml`. Ops, not code.
- **YAML-first configuration**: All behavioural settings live in version-controlled `config.yaml`. Only deployment-specific values (ComfyUI IP, bind host/port) go in `.env`, using `__` delimiter for nested overrides.
- **Drop-in static injection**: Adding a new pre-made asset is creating a PNG in the right `static_tiles/` folder and restarting.
- **Workflows as version-controlled assets**: ComfyUI workflow JSONs live in `src/workflows/` alongside code.
- **In-memory caching**: `AssetStore` uses an LRU-backed `OrderedDict` for zero-latency asset serving. Falls back to disk reads transparently.
- **SQLite**: No external database dependency. `AssetRecord` and `LeaderRecord` track every generation.
- **Prompt enrichment happens server-side**: The game client says `"water"`; the service handles making it sound good to the diffusion model.
- **Copy-on-Write**: Inpainting never mutates the original asset, enabling safe concurrent modifications.

---

## Documentation

| File | Purpose |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Full system architecture, component breakdown |
| [`docs/migration_plan.md`](docs/migration_plan.md) | Plan and rationale for ComfyUI migration |
| [`docs/leader_pipeline_plan.md`](docs/leader_pipeline_plan.md) | Leader pipeline implementation plan + checklist |
| [`docs/client-api-leader-guide.md`](docs/client-api-leader-guide.md) | Original leader API design reference (FLUX-focused) |
| [`docs/inpainting_workflow.md`](docs/inpainting_workflow.md) | Inpainting prototyping with ComfyUI vs diffusers |
| [`docs/next_steps.md`](docs/next_steps.md) | Future roadmap items |
