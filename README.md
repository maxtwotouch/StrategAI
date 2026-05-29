# Medieval Pixel Art Image Service

An on-demand generative AI microservice that produces pixel-art game assets for a top-down medieval game. Built with **FastAPI** and **ComfyUI** as the inference backend. Generation modes are configurable per asset family in `config.yaml` — no code changes needed.

**Zero-dependency testing mode available** — run the full API with procedural placeholders, no GPU or ComfyUI required.

---

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Run (placeholder mode — no GPU needed)
uvicorn src.main:app --host 0.0.0.0 --port 8000

# Verify
curl http://localhost:8000/health
curl http://localhost:8000/catalog
```

---

## Asset Families

| Family | Endpoint Prefix | Description |
|--------|----------------|-------------|
| `leader` | `/leader` | Leader portraits: splash → profile → action pipeline with img2img consistency |
| `structure` | `/structure` | Buildings: fortification, production, housing, sacred |
| `object` | `/object` | Nature objects and world props: vegetation, geological, rural/urban |
| `terrain` | `/terrain` | Elevation features: hill, cliff, slope, ridge, depression |
| `unit` | `/unit` | Top-down character sprites: archer, scout, settler, warrior |
| `background_tile` | `/background_tile` | Repeatable terrain tiles: water, grass, sand, stone, dirt |

Every family supports full CRUD: `POST` (generate), `GET` (list), `GET /{id}` (get one), `DELETE /{id}`.

---

## API Reference

### Health & Discovery

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service status, ComfyUI connectivity, registered asset counts, active modes |
| `GET` | `/modes` | Active generation mode per asset family (`comfyui`/`static`/`placeholder`) |
| `GET` | `/catalog` | Available enum values for all asset families (tile types, subtypes, unit types) |

### Assets

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/assets/{filename}` | Download a generated PNG by filename |

### Leader Pipeline

**Workflow:** Splash → Profile → Action (img2img reference image maintains character consistency)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/leader` | Generate a leader asset (`asset_type`: `splash`, `profile`, or `action`) |
| `GET` | `/leader` | List all registered leaders with asset URLs |
| `GET` | `/leader/{leader_id}` | Get a specific leader's info and asset URLs |
| `DELETE` | `/leader/{leader_id}` | Remove a leader and their reference image |

**Example — Full leader pipeline:**

```bash
# Step 1: Generate splash (creates leader identity)
curl -X POST http://localhost:8000/leader \
  -H "Content-Type: application/json" \
  -d '{
    "asset_type": "splash",
    "leader_name": "Queen Isabella",
    "leader_description": "A tall woman in her thirties with sharp features, olive skin, dark braided hair, piercing green eyes. Wears a crimson velvet gown with gold embroidery and a silver crown.",
    "archetype": "monarch",
    "culture": "medieval_european",
    "time_of_day": "golden_hour",
    "mood": "commanding"
  }'

# Step 2: Generate profile (uses splash as reference)
curl -X POST http://localhost:8000/leader \
  -H "Content-Type: application/json" \
  -d '{
    "asset_type": "profile",
    "leader_id": "<leader_id_from_step_1>",
    "leader_name": "Queen Isabella",
    "leader_description": "...",
    "archetype": "monarch",
    "culture": "medieval_european",
    "time_of_day": "golden_hour",
    "mood": "commanding"
  }'

# Step 3: Generate action scene
curl -X POST http://localhost:8000/leader \
  -H "Content-Type: application/json" \
  -d '{
    "asset_type": "action",
    "leader_id": "<leader_id_from_step_1>",
    "leader_name": "Queen Isabella",
    "leader_description": "...",
    "archetype": "monarch",
    "culture": "medieval_european",
    "time_of_day": "golden_hour",
    "mood": "commanding",
    "action_category": "leading_troops",
    "action_description": "The queen stands on a hilltop addressing her army, sword raised high."
  }'

# Multi-leader action scene
curl -X POST http://localhost:8000/leader \
  -H "Content-Type: application/json" \
  -d '{
    "asset_type": "action",
    "leader_ids": ["<leader_id_1>", "<leader_id_2>"],
    "leader_name": "Alliance Scene",
    "leader_description": "...",
    "archetype": "monarch",
    "culture": "medieval_european",
    "time_of_day": "golden_hour",
    "mood": "commanding",
    "action_category": "diplomacy",
    "action_description": "Two rulers meet at a grand oak table to sign a peace treaty."
  }'
```

### Structure Tiles

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/structure` | Generate a structure tile |
| `GET` | `/structure` | List all generated structures |
| `GET` | `/structure/catalog` | Available enum values (categories, styles, conditions, scales) |
| `GET` | `/structure/{structure_id}` | Get a specific structure |
| `DELETE` | `/structure/{structure_id}` | Remove a structure record |

**Request fields:** `category` (fortification/production/housing/sacred), `style`, `condition`, `scale`, `description`, `seed` (optional)

### Object Tiles

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/object` | Generate an object tile |
| `GET` | `/object` | List all generated objects |
| `GET` | `/object/catalog` | Available enum values (categories, biomes, seasons) |
| `GET` | `/object/{object_id}` | Get a specific object |
| `DELETE` | `/object/{object_id}` | Remove an object record |

**Request fields:** `category` (vegetation/geological/rural_prop/urban_prop/debris), `biome`, `season`, `description`, `seed` (optional)

### Terrain Tiles

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/terrain` | Generate a terrain tile |
| `GET` | `/terrain` | List all generated terrains |
| `GET` | `/terrain/catalog` | Available enum values (categories, scales, materials) |
| `GET` | `/terrain/{terrain_id}` | Get a specific terrain |
| `DELETE` | `/terrain/{terrain_id}` | Remove a terrain record |

**Request fields:** `category` (hill/slope/cliff/ridge/depression), `scale`, `material`, `description`, `seed` (optional)

### Unit Sprites

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/unit` | Generate a unit sprite (south-facing front view) |
| `GET` | `/unit` | List all generated units |
| `GET` | `/unit/catalog` | Available unit types (archer, scout, settler, warrior) |
| `GET` | `/unit/{unit_id}` | Get a specific unit |
| `DELETE` | `/unit/{unit_id}` | Remove a unit record |

**Request fields:** `unit_type` (archer/scout/settler/warrior), `description` (20-400 chars, clothing/weapon/posture details), `seed` (optional)

### Background Tiles

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/background_tile` | Generate a seamless background tile |
| `GET` | `/background_tile` | List all generated background tiles |
| `GET` | `/background_tile/catalog` | Available tile types |
| `GET` | `/background_tile/{tile_id}` | Get a specific background tile |
| `DELETE` | `/background_tile/{tile_id}` | Remove a background tile record |

**Request fields:** `tile_type` (water/grass/sand/stone/dirt), `seed` (optional)

### Response Format

All POST endpoints return a consistent structure:

```json
{
  "url": "/assets/abc123.png",
  "asset_id": "struct_fortification_a1b2c3",
  "seed": 123456789,
  "generation_mode": "comfyui",
  "status": "completed",
  "prompt_used": "<full rendered prompt>",
  "resolution": "128x128",
  "generation_time_ms": 5234
}
```

Leader responses use `leader_id` instead of `asset_id`. Unit responses use `unit_id` and include the submitted `description`.

### Error Responses

| Code | Meaning |
|------|---------|
| `400` | Invalid request (bad enum value, missing required field, validation error) |
| `404` | Asset or record not found |
| `411` | Missing Content-Length header on POST/PUT/PATCH requests |
| `413` | Request body exceeds configured size limit |
| `503` | ComfyUI unavailable (engine not initialized) |
| `500` | Internal server error |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  FastAPI (src/main.py)                                  │
│  Endpoints: /leader, /structure, /object, /terrain,     │
│             /unit, /background_tile, /assets, /health   │
├──────────────────┬──────────────────┬───────────────────┤
│  Leader Engine   │  Tile Engine     │  Unit Engine      │
│  (leader/)       │  (tile/)         │  (unit/)          │
│  ├ LeaderEngine  │  ├ TileEngine    │  ├ UnitEngine     │
│  ├ StaticLeader  │  ├ StaticTile    │  ├ StaticUnit     │
│  └ Models/Reg    │  └ Background    │  └ Models/Reg     │
├──────────────────┴──────────────────┴───────────────────┤
│  ComfyUIClient (comfyui_client.py)                      │
│  Async HTTP+WS: httpx + websockets                      │
│  Workflow validation, patching, queueing, result download│
├─────────────────────────────────────────────────────────┤
│  ComfyUILoadBalancer (comfyui_loadbalancer.py)          │
│  Multi-node: health checks, queue-depth routing          │
├─────────────────────────────────────────────────────────┤
│  AssetStore (storage.py)                                │
│  In-memory LRU cache + disk persistence                  │
├─────────────────────────────────────────────────────────┤
│  SQLite DB (database.py)                                │
│  LeaderRecord, StructureRecord, ObjectRecord,           │
│  TerrainRecord, UnitRecord, AssetRecord                 │
└─────────────────────────────────────────────────────────┘
```

### Generation Modes

Each asset family can be independently configured:

| Mode | Behaviour |
|------|-----------|
| `comfyui` | Delegates to an external ComfyUI server via HTTP+WebSocket |
| `static` | Serves pre-made PNGs from `static_tiles/` directory |
| `placeholder` | Returns a procedural coloured placeholder (zero dependencies) |

Set in `config.yaml` under `generation.modes`:

```yaml
generation:
  default_mode: "comfyui"
  modes:
    structure: "comfyui"
    object: "comfyui"
    terrain: "comfyui"
    background_tile: "static"
    leader: "comfyui"
    unit: "static"
```

---

## Project Structure

```
.
├── src/
│   ├── main.py                  # FastAPI app, endpoints, CORS, middleware, lifespan
│   ├── config.py                # Pydantic Settings (modes, paths, ComfyUI URL)
│   ├── database.py              # SQLAlchemy ORM + SQLite (6 record types)
│   ├── storage.py               # AssetStore: in-memory LRU cache + disk I/O
│   ├── comfyui_client.py        # Async HTTP+WebSocket client for ComfyUI
│   ├── comfyui_loadbalancer.py  # Multi-node queue-depth routing + health checks
│   ├── static_catalog.py        # Scans static_tiles/ for available PNGs
│   ├── font_utils.py            # Font loading for placeholder renderers
│   ├── prompt_templates.py      # JSON template loader (prefix/suffix wrapping)
│   ├── leader/
│   │   ├── engine.py            # Splash → profile → action orchestrator
│   │   ├── models.py            # Enums + Pydantic request/response schemas
│   │   ├── prompts.py           # Enum injection maps + prompt builders
│   │   └── registry.py          # SQLite-backed leader CRUD
│   ├── tile/
│   │   ├── engine.py            # Structure/Object/Terrain generation
│   │   ├── background_engine.py # Background tile generation
│   │   ├── models.py            # Tile enums + Pydantic schemas
│   │   ├── background_models.py # Background tile models
│   │   ├── prompts.py           # Tile prompt builders
│   │   └── registry.py          # Structure/Object/Terrain CRUD
│   └── unit/
│       ├── engine.py            # Unit sprite generation
│       ├── models.py            # Unit enums + Pydantic schemas
│       ├── prompts.py           # Unit prompt builders
│       └── registry.py          # SQLite-backed unit CRUD
├── workflows/                   # ComfyUI workflow JSON templates
│   ├── txt2img.json             # SDXL txt2img (used by tile + unit engines)
│   ├── background_tile.json     # Seamless texture workflow
│   └── leader/
│       ├── leader_splash.json   # Splash generation (txt2img)
│       ├── leader_profile.json  # Profile generation (img2img with reference)
│       └── leader_action.json   # Action scene generation
├── static_tiles/                # Pre-made PNGs (used in static mode)
├── leader_references/           # Runtime reference images for leader pipeline
├── generated_assets/            # Output directory (runtime)
├── config.yaml                  # Version-controlled config
├── pyproject.toml               # Package metadata + dependencies
├── pytest.ini                   # Test configuration
└── docs/                        # Architecture docs, prompt guides, plans
```

---

## Configuration

All settings live in `config.yaml` (version-controlled). Deployment-specific overrides go in `.env`.

### Load order (later sources win)

1. Pydantic defaults (in `src/config.py`)
2. `config.yaml` — primary source of truth, committed to git
3. Environment variables (e.g., `COMFYUI__BASE_URL`)
4. `.env` file — deployment-specific overrides (highest priority)

Use `__` (double underscore) as the nesting delimiter:

```bash
# .env — only what changes per deployment
COMFYUI__BASE_URL=http://10.0.0.5:8188
HOST=0.0.0.0
PORT=8000
SERVER__MAX_REQUEST_BODY_MB=20
```

---

## Running

### Prerequisites
- Python 3.10+
- ComfyUI server (for `comfyui` mode only)

### Install
```bash
pip install -e ".[dev]"
```

### Run (placeholder mode — no GPU)
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```
All endpoints work with procedural placeholders.

### Run (comfyui mode)
```bash
echo 'COMFYUI__BASE_URL=http://your-comfyui:8188' > .env
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### Run Tests
```bash
python -m pytest tests/ -v
```

---

## ComfyUI Requirements

The service expects the following on your ComfyUI server:

- **Base**: ComfyUI with standard nodes (KSampler, CLIPTextEncode, VAEDecode, SaveImage)
- **Flux2 Klein workflows**: `SamplerCustomAdvanced`, `EmptyFlux2LatentImage` (if using Flux2)
- **Models**: SDXL or Flux2 checkpoints, VAE, LoRAs as configured in workflow JSONs
- **Custom nodes**: As specified in individual workflow files

The service validates workflow structure before queueing (checks for `SaveImage` nodes and prompt-injectable `CLIPTextEncode` nodes) and fails fast on missing requirements.

---

## Error Handling

- **Workflow validation**: Checked before queueing — catches missing output nodes or malformed prompt injection targets
- **ComfyUI connection**: Health-checked at startup; unreachable nodes return 503 at the API
- **Queue failures**: Uploaded images are cleaned up from ComfyUI's `input/` folder on failure
- **Disk errors**: Write failures are caught with clear error messages; in-memory cache is not corrupted
- **Polling resilience**: WebSocket preferred with automatic fallback to HTTP polling; polling failures logged at DEBUG level
