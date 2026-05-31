# Server API Reference

> 📘 Concise endpoint reference. For detailed request/response examples with curl commands, see [`api-examples.md`](api-examples.md). For the full project report, see [`../project-report.md`](../project-report.md).

## Conventions
- All POST endpoints accept JSON (`Content-Type: application/json`)
- All list endpoints support pagination: `?limit=1-200` (default 50), `?offset=≥0`
- All DELETE endpoints return a `DeleteResponse`: `{"deleted": true, "asset_id": "...", "files_removed": N}`
- Error responses: `{"detail": "..."}` with appropriate HTTP status code
- Successful POST: 200 (generation completed synchronously)
- Successful GET: 200
- Successful DELETE: 200

> **Design Note: Why enums instead of free-form prompts?** This API intentionally restricts clients to structured enum values (`"fortification"`, `"desert"`, `"archer"`) rather than accepting raw diffusion-model prompt strings. The tradeoff: less creative flexibility in exchange for zero prompt-engineering burden and guaranteed style consistency across all generated assets. Game designers describe _what_ they want using game-domain concepts; the server translates these into model-optimised prose using locked prompt templates. For the full rationale, see the [project report §3.8.1](../project-report.md#381-design-rationale-structured-enums-vs-free-form-prompts).

## System Endpoints

| Method | Path | Purpose | Auth Required |
|--------|------|---------|---------------|
| GET | `/health` | Component status (DB, ComfyUI, templates, engines) | No |
| GET | `/health/ready` | Readiness probe (200 after full startup) | No |
| GET | `/modes` | Active generation mode per asset family | No |
| GET | `/catalog` | Available static assets + valid enum values | No |
| GET | `/assets/{filename}` | Download generated PNG | No |

## Leader

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/leader` | Generate leader splash, profile, or action |
| GET | `/leader` | List all leaders (paginated) |
| GET | `/leader/catalog` | Valid enum values for leader generation |
| GET | `/leader/{leader_id}` | Get leader info + asset URLs |
| DELETE | `/leader/{leader_id}` | Remove leader and all associated assets |

**POST body fields:** `asset_type` (required: "splash"/"profile"/"action"), `leader_name`, `leader_description`, `archetype`, `culture`, `time_of_day`, `mood`, `seed` (optional), `leader_ids` (for multi-leader action, exactly 2), `action_category`, `action_description`

## Structure

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/structure` | Generate structure sprite |
| GET | `/structure` | List all structures (paginated) |
| GET | `/structure/catalog` | Valid enum values |
| GET | `/structure/{structure_id}` | Get structure info + asset URL |
| DELETE | `/structure/{structure_id}` | Remove structure and asset |

**POST body fields:** `category`, `style`, `condition`, `scale`, `description`

## Object

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/object` | Generate object sprite |
| GET | `/object` | List all objects (paginated) |
| GET | `/object/catalog` | Valid enum values |
| GET | `/object/{object_id}` | Get object info + asset URL |
| DELETE | `/object/{object_id}` | Remove object and asset |

**POST body fields:** `category`, `biome`, `season`, `description`

## Terrain

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/terrain` | Generate terrain sprite |
| GET | `/terrain` | List all terrain (paginated) |
| GET | `/terrain/catalog` | Valid enum values |
| GET | `/terrain/{terrain_id}` | Get terrain info + asset URL |
| DELETE | `/terrain/{terrain_id}` | Remove terrain and asset |

**POST body fields:** `category`, `scale`, `material`, `description`

## Unit

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/unit` | Generate unit sprite |
| GET | `/unit` | List all units (paginated) |
| GET | `/unit/catalog` | Valid enum values |
| GET | `/unit/{unit_id}` | Get unit info + asset URL |
| DELETE | `/unit/{unit_id}` | Remove unit and asset |

**POST body fields:** `unit_type` (archer/scout/settler/warrior), `description`

## Background Tile

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/background_tile` | Generate seamless ground texture |
| GET | `/background_tile` | List all tiles (paginated) |
| GET | `/background_tile/catalog` | Valid tile types |
| GET | `/background_tile/{background_tile_id}` | Get tile info + asset URL |
| DELETE | `/background_tile/{background_tile_id}` | Remove tile and asset |

**POST body fields:** `tile_type` (water/grass/sand/stone/dirt), `seed` (optional)

## Response Shapes

### POST Response (all families)
```json
{
  "url": "/assets/struct_fortification_a1b2c3.png",
  "asset_id": "struct_fortification_a1b2c3",
  "seed": 1234567890,
  "generation_mode": "comfyui",
  "prompt_used": "<tdp> top-down view...",
  "resolution": "128x128",
  "generation_time_ms": 2340
}
```

Leader responses additionally include: `leader_id`, `leader_ids` (for multi), `leader_names`.

### GET list Response (all families)
```json
{
  "items": [...],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

### GET by ID Response
Returns the full record (varies by family). Always includes `image_id` or `asset_id` pointing to the generated PNG.

### DELETE Response (all families)
```json
{
  "deleted": true,
  "asset_id": "struct_fortification_a1b2c3",
  "files_removed": 1
}
```

### Error Response
```json
{
  "detail": "Validation error: 'category' must be one of: fortification, production, housing, sacred"
}
```

HTTP status codes: 400 (validation), 404 (not found), 413 (body too large), 429 (rate limited), 500 (generation failed).
