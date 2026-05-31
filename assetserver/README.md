# Medieval Pixel Art Image Service

An on-demand generative AI microservice that produces pixel-art game assets for a top-down medieval game. Built with **FastAPI** and **ComfyUI** as the inference backend. Generation modes are configurable per asset family in `config.yaml` — no code changes needed.

**Zero-dependency testing mode available** — run the full API with procedural placeholders, no GPU or ComfyUI required.

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[Project Report](docs/project-report.md)** | Full student technical report — design rationale, DiT pipeline, evaluation, limitations |
| **[Image Generation Pipeline](docs/pipeline/image-generation-pipeline.md)** | Deep-dive: DiT mechanics, node-by-node workflow walkthrough, runtime patching |
| **[Asset Family Engines](docs/architecture/asset-family-engines.md)** | Per-family engine architecture — leader 3-stage, tile, unit, background |
| **[Database Schema](docs/architecture/database-schema.md)** | ERD, table reference, FK strategies, query patterns |
| **[Configuration Reference](docs/architecture/configuration-reference.md)** | Every config key explained, .env override syntax |
| **[Architecture Overview](docs/architecture/architecture.md)** | System architecture, middleware stack, component breakdown |
| **[Storage & Caching](docs/architecture/storage-and-caching.md)** | LRU cache, atomic writes, orphan cleanup |
| **[ComfyUI Protocol](docs/architecture/comfyui-protocol.md)** | WebSocket + HTTP communication with ComfyUI |
| **[Load Balancer](docs/architecture/load-balancer.md)** | Multi-node ComfyUI routing, failover |
| **[Static Catalog](docs/architecture/static-catalog.md)** | Static asset resolution system |
| **[Font Utilities](docs/architecture/font-utils.md)** | Cross-platform font resolution |
| **[Workflow Design Justification](docs/pipeline/workflow-design-justification.md)** | Flux2 Klein model selection, node graph rationale |
| **[ComfyUI Setup Guide](docs/architecture/comfyui-setup-guide.md)** | Hardware requirements, install steps, model download |
| **[Testing Plan](docs/architecture/testing-plan.md)** | Test architecture, fixture inventory, coverage |
| **Prompt Writing Guides** | [Leader](docs/guides/leader-prompt-guide.md) · [Tile](docs/guides/tile-prompt-guide.md) · [Unit](docs/guides/unit-prompt-guide.md) |

---

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Run (placeholder mode — no GPU needed)
uvicorn src.main:app --host 127.0.0.1 --port 8000

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
| `GET` | `/health/ready` | Lightweight readiness probe (returns 200 if DB connected, no ComfyUI check) |
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
| `GET` | `/leader/catalog` | Available leader enum values (archetypes, cultures, times of day, moods, action categories) |
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

For curl examples covering all 6 generation endpoints with enum references and troubleshooting, see [docs/guides/api-examples.md](docs/guides/api-examples.md).

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

See [docs/architecture/architecture.md](docs/architecture/architecture.md) for the full system architecture,
component breakdown, workflow templates, and generation mode documentation.

For project structure, see [docs/architecture/architecture.md §4](docs/architecture/architecture.md#4-component-architecture).

---

## Configuration

All settings live in `config.yaml` (version-controlled, source of truth for defaults and structure).
Deployment-specific overrides go in `.env` — only values that differ from the `config.yaml` defaults.

### Config layering principle

| Layer | Source | Purpose |
|-------|--------|---------|
| `config.yaml` | Version-controlled | Defaults and structure — the canonical reference for every setting |
| `.env` | Per-deployment, git-ignored | **Only** values that differ per environment (e.g., ComfyUI URL) |
| `.env.testing` | Drop-in preset | Pre-built config that sets all generation modes to `placeholder` for ComfyUI-free testing |

**Rule of thumb**: If a value in `.env` equals the `config.yaml` default, it doesn't belong in `.env`.

### Load order (later sources win)

1. Pydantic field defaults (in `src/config.py`)
2. OS environment variables (lowest priority — overridden by `config.yaml`)
3. `config.yaml` — primary source of truth, committed to git
4. `.env` file — deployment-specific overrides
5. File secrets (highest priority)

Use `__` (double underscore) as the nesting delimiter for nested keys:

```bash
# .env — minimal production example (only what differs from config.yaml)
COMFYUI__BASE_URL=http://10.0.0.5:8188
```

The `config.yaml` defaults work out of the box for local development — you only need to override `COMFYUI__BASE_URL` to point at your ComfyUI server. For ComfyUI-free testing, copy `.env.testing` to `.env`:

```bash
cp .env.testing .env
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
uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```
All endpoints work with procedural placeholders.

### Run (comfyui mode)
```bash
echo 'COMFYUI__BASE_URL=http://your-comfyui:8188' > .env
uvicorn src.main:app --host 127.0.0.1 --port 8000
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
DATABASE_RESET=true uvicorn src.main:app --host 127.0.0.1 --port 8000
```
This drops and recreates all tables. **Warning: this deletes all data.**

### Production Notes
- **SQLite** is used exclusively. WAL journal mode enables safe concurrent reads and writes. For deployments with multiple worker processes, use a reverse proxy with sticky sessions.
- Multi-worker: run behind `gunicorn` with `uvicorn` workers (not yet configured — see [docs/project/next_steps.md](docs/project/next_steps.md)), or use a process manager.

### Common Issues
| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 503 on all endpoints | ComfyUI unreachable | Check `COMFYUI__BASE_URL`, verify ComfyUI is running |
| "Database schema mismatch" | DB created by older code version | Restart with `DATABASE_RESET=true` |
| WebSocket closure warning | ComfyUI WS closed before completion | Automatic fallback to polling; harmless unless frequent |

---

## Production Deployment

Steps to deploy the service in a production environment:

1. **Set deployment mode**: `DEPLOYMENT_MODE=production` — enables strict safety checks:
   - CORS origins must be explicit (no `*` wildcard)
   - Schema mismatches at startup are fatal (refuse to start)
   - `DATABASE_RESET=true` is blocked (prevents accidental data loss)
   - Missing ComfyUI workflow nodes are fatal errors
2. **Generate a strong API key**: Set `SERVER__API_KEY` to a random 64-char hex string. Without it, the API is open to anyone who can reach the server.
3. **Tighten CORS**: Set `SERVER__CORS_ORIGINS` to your frontend's exact origin (e.g., `'["https://mygame.example.com"]'`). Never use `["*"]` in production.
4. **Put a reverse proxy in front**: Use **nginx** or **Caddy** for:
   - TLS termination (HTTPS)
   - Per-IP rate limiting (the built-in rate limiter is global, not per-IP)
   - Request buffering and connection pooling
   - Static asset caching with `Cache-Control` headers
5. **Harden the host**: Bind to `127.0.0.1` if only the reverse proxy needs access (`SERVER__HOST=127.0.0.1`).
6. **Monitor health**: Poll `GET /health` every 15–30 seconds. A `degraded` status means ComfyUI is unreachable but the API is still serving.

See [DEPLOYMENT.md](DEPLOYMENT.md) for a full step-by-step deployment guide including nginx configuration.

---

## Environment Variables Reference

All configurable environment variables use the `__` (double underscore) delimiter
for nested keys.  Defaults come from `config.yaml`; `.env` overrides them.

| Variable | Default | Notes |
|----------|---------|-------|
| `DEPLOYMENT_MODE` | `development` | `production` enables strict safety checks |
| `SERVER__HOST` | `127.0.0.1` (in config.yaml) | Bind address; use `127.0.0.1` behind a reverse proxy |
| `SERVER__PORT` | `8000` (in config.yaml) | Listening port |
| `SERVER__API_KEY` | `""` (empty) | When non-empty, all requests require `X-API-Key` header (except `/health` and `/assets/`) |
| `SERVER__CORS_ORIGINS` | `["http://localhost:3000"]` | JSON array of allowed origins |
| `SERVER__MAX_REQUEST_BODY_MB` | `10` | Max request body size in MB (1–100) |
| `SERVER__CACHE_MAX_ENTRIES` | `1000` | Max images held in the in-memory LRU cache |
| `SERVER__CACHE_MAX_MB` | `500` | Max memory (MB) for the in-memory image cache |
| `COMFYUI__BASE_URL` | `http://127.0.0.1:8188` | Single ComfyUI node URL |
| `COMFYUI__NODES` | `[]` | List of ComfyUI URLs for load-balanced multi-node mode |
| `COMFYUI__TIMEOUT` | `300` | Per-generation timeout in seconds |
| `COMFYUI__HEALTH_CHECK_INTERVAL` | `30` | Seconds between re-pinging unhealthy nodes |
| `COMFYUI__MAX_RETRIES` | `3` | Max nodes to try per generation before failing |
| `COMFYUI__WARMUP_ENABLED` | `true` | Submit a minimal generation at startup to preload GPU VRAM |
| `COMFYUI__WARMUP_TIMEOUT` | `120` | Max seconds to wait for warmup generation |
| `COMFYUI__WARMUP_WORKFLOW` | `background_tile` | Workflow used for warmup (keep it simple) |
| `DATABASE_URL` | `sqlite:///tilemap.db` | Full database connection URL |
| `DATABASE_RESET` | (not set) | Set to `true` to drop and recreate all tables. **Blocked in production mode.** |
| `RATE_LIMIT__ENABLED` | `true` | Toggle rate limiting on/off |
| `RATE_LIMIT__POST_RPS` | `2.0` | Max POST (generation) requests per second globally |
| `RATE_LIMIT__GET_RPS` | `50.0` | Max GET (read) requests per second globally |
| `RATE_LIMIT__BURST_SIZE` | `5` | Max burst for POST endpoints before throttling |
| `GENERATION__MODES__structure` | `comfyui` | Generation mode for structures |
| `GENERATION__MODES__object` | `comfyui` | Generation mode for objects |
| `GENERATION__MODES__terrain` | `comfyui` | Generation mode for terrain |
| `GENERATION__MODES__background_tile` | `comfyui` | Generation mode for background tiles |
| `GENERATION__MODES__unit` | `comfyui` | Generation mode for units |
| `GENERATION__MODES__leader` | `comfyui` | Generation mode for leaders |
| `GENERATION__DEFAULT_MODE` | `comfyui` | Fallback mode for unlisted families |
| `PATHS__FONT_PATH` | `""` | Optional absolute path to a .ttf/.ttc font for placeholder labels |

**Mode values**: `comfyui` (GPU generation), `static` (pre-made PNGs), `placeholder` (procedural rectangles).

---

## Health Check Interpretation

`GET /health` returns the following JSON structure:

```json
{
  "status": "healthy",
  "components": {
    "database": "ok",
    "comfyui": "ok"
  },
  "comfyui_nodes": 1,
  "modes": {
    "structure": "comfyui",
    "object": "comfyui",
    "terrain": "comfyui",
    "background_tile": "comfyui",
    "unit": "comfyui",
    "leader": "comfyui"
  },
  "registered": {
    "assets": 42,
    "leaders": 3,
    "structures": 12,
    "objects": 8,
    "terrains": 5,
    "units": 7,
    "background_tiles": 7
  }
}
```

### Status Values

| `status` | Meaning | Action |
|----------|---------|--------|
| `healthy` | All components operational | Normal operation |
| `degraded` | ComfyUI unreachable, but API is still serving | Check GPU server; static/placeholder modes still work |
| `unhealthy` | Database connectivity failure | Check `DATABASE_URL`; restart with `DATABASE_RESET=true` in dev |

### Monitoring Usage

- **Load balancer health probe**: Poll `/health` every 15–30s. Route traffic if `status` is `healthy` or `degraded`. Only take the node out of rotation on `unhealthy` or HTTP 5xx.
- **Alerting**: Trigger an alert if `status` stays `degraded` for >5 minutes (prolonged ComfyUI outage). Trigger immediately if `status` is `unhealthy`.
- **Capacity planning**: Track `registered.*` counts over time to estimate storage growth.
- **Mode awareness**: The `modes` field shows which families use GPU (`comfyui`) vs fallbacks (`static`/`placeholder`) — useful for debugging unexpected behavior.
- **Multi-node**: `comfyui_nodes` reflects the number of healthy ComfyUI servers. If this drops to 0, all `comfyui`-mode generations will fail.

---

## Error Handling

- **Workflow validation**: Checked before queueing — catches missing output nodes or malformed prompt injection targets
- **ComfyUI connection**: Health-checked at startup; unreachable nodes return 503 at the API
- **Queue failures**: Uploaded images are cleaned up from ComfyUI's `input/` folder on failure
- **Disk errors**: Write failures are caught with clear error messages; in-memory cache is not corrupted
- **Polling resilience**: WebSocket preferred with automatic fallback to HTTP polling; polling failures logged at DEBUG level
