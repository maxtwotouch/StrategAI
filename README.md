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

**Pagination:** All `GET` list endpoints support `?limit=` (1–200, default 50) and `?offset=` (≥0, default 0).

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
    "archetype": "warrior_king",
    "culture": "medieval_european",
    "time_of_day": "golden_hour",
    "mood": "grim_determined"
  }'

# Step 2: Generate profile (uses splash as reference)
curl -X POST http://localhost:8000/leader \
  -H "Content-Type: application/json" \
  -d '{
    "asset_type": "profile",
    "leader_id": "<leader_id_from_step_1>",
    "leader_name": "Queen Isabella",
    "leader_description": "...",
    "archetype": "warrior_king",
    "culture": "medieval_european",
    "time_of_day": "golden_hour",
    "mood": "grim_determined"
  }'

# Step 3: Generate action scene
curl -X POST http://localhost:8000/leader \
  -H "Content-Type: application/json" \
  -d '{
    "asset_type": "action",
    "leader_id": "<leader_id_from_step_1>",
    "leader_name": "Queen Isabella",
    "leader_description": "...",
    "archetype": "warrior_king",
    "culture": "medieval_european",
    "time_of_day": "golden_hour",
    "mood": "grim_determined",
    "action_category": "military",
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
    "archetype": "warrior_king",
    "culture": "medieval_european",
    "time_of_day": "golden_hour",
    "mood": "grim_determined",
    "action_category": "diplomatic",
    "action_description": "Two rulers meet at a grand oak table to sign a peace treaty."
  }'
```

For curl examples covering all 6 generation endpoints with enum references and troubleshooting, see [docs/api-examples.md](docs/api-examples.md).

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

**Request fields:** `category` (vegetation/geological/rural_props/urban_props/debris), `biome`, `season`, `description`, `seed` (optional)

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
| `GET` | `/background_tile/{background_tile_id}` | Get a specific background tile |
| `DELETE` | `/background_tile/{background_tile_id}` | Remove a background tile record |

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

Leader responses use `leader_id` instead of `asset_id`. Unit responses use `unit_id`.
Background tile responses use `background_tile_id`. All responses include the submitted `description` where applicable.

### Error Responses

| Code | Meaning |
|------|---------|
| `400` | Invalid request (bad enum value, missing required field, engine-level validation error) |
| `404` | Asset or record not found |
| `411` | Missing Content-Length header on POST/PUT/PATCH requests |
| `413` | Request body exceeds configured size limit |
| `422` | Pydantic validation error (missing field, too short/long, bad enum) |
| `503` | ComfyUI unavailable (engine not initialized) |
| `500` | Internal server error |

---

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full system architecture,
component breakdown, workflow templates, and generation mode documentation.

For project structure, see [docs/architecture.md §4](docs/architecture.md#4-component-architecture).

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

- **Flux2 Klein native nodes**: `UNETLoader`, `CLIPLoader`, `VAELoader`, `CFGGuider`, `Flux2Scheduler`, `KSamplerSelect`, `SamplerCustomAdvanced`, `EmptyFlux2LatentImage`, `SaveImage`
- **Models**: `flux-2-klein-4b-fp8.safetensors` (UNET), `qwen_3_4b.safetensors` (CLIP), `flux2-vae.safetensors` (VAE)
- **Custom nodes**: As specified in individual workflow JSONs

The service validates workflow structure before queueing and fails fast on missing requirements.

---

## Deployment

### Database Migrations

The service runs **Alembic migrations automatically** at startup (`alembic upgrade head`). No manual migration steps are needed.

If the database schema gets out of sync (e.g., after a rollback), restart with:
```bash
DATABASE_RESET=true uvicorn src.main:app --host 0.0.0.0 --port 8000
```
This drops and recreates all tables. **Warning: this deletes all data.**

### Production Notes
- **SQLite** is used exclusively. WAL journal mode enables safe concurrent reads and writes. For deployments with multiple worker processes, use a reverse proxy with sticky sessions.
- Multi-worker: run behind `gunicorn` with `uvicorn` workers (not yet configured — see [docs/next_steps.md](docs/next_steps.md)), or use a process manager.

### Common Issues
| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 503 on all endpoints | ComfyUI unreachable | Check `COMFYUI__BASE_URL`, verify ComfyUI is running |
| "Database schema mismatch" | DB created by older code version | Restart with `DATABASE_RESET=true` |
| WebSocket closure warning | ComfyUI WS closed before completion | Automatic fallback to polling; harmless unless frequent |

---

## Error Handling

- **Workflow validation**: Checked before queueing — catches missing output nodes or malformed prompt injection targets
- **ComfyUI connection**: Health-checked at startup; unreachable nodes return 503 at the API
- **Queue failures**: Uploaded images are cleaned up from ComfyUI's `input/` folder on failure
- **Disk errors**: Write failures are caught with clear error messages; in-memory cache is not corrupted
- **Polling resilience**: WebSocket preferred with automatic fallback to HTTP polling; polling failures logged at DEBUG level
