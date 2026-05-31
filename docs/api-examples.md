# API Examples — Curl Reference

Quick-start curl examples for all 6 POST generation endpoints of the Medieval Pixel Art Image Service.

## Prerequisites

```bash
# Start the server (placeholder mode — no GPU/ComfyUI needed)
cp .env.testing .env
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

**Base URL**: `http://localhost:8000` (adjust host/port if different)

> **Auth**: If `api_key` is configured in `.env`, add `-H "X-API-Key: YOUR_KEY"` to all commands.

## Common Response Fields

All POST endpoints return JSON with these shared fields:

| Field | Type | Description |
|---|---|---|
| `url` | `string` | Relative URL to the generated asset (e.g., `/assets/abc123.png`) |
| `asset_type` | `string` | Asset family (e.g., `"structure"`, `"unit"`, `"leader"`) |
| `seed` | `int` | Seed used for reproducible generation |
| `generation_mode` | `string` | Engine used: `"comfyui"`, `"static"`, or `"placeholder"` |
| `status` | `string` | Always `"completed"` for sync responses |
| `prompt_used` | `string?` | The full prompt sent to the image model |
| `resolution` | `string?` | Output dimensions (e.g., `"128x128"`, `"1920x1088"`) |
| `generation_time_ms` | `int?` | Time taken to generate in milliseconds |

---

## 1. POST `/leader` — Generate a Leader Asset

Generate splash screens, profile portraits, or action scenes for civilization leaders.

### Minimal (Splash Screen)

```bash
curl -s -X POST 'http://localhost:8000/leader' \
  -H 'Content-Type: application/json' \
  -d '{
    "asset_type": "splash",
    "leader_name": "Queen Isabella",
    "leader_description": "Queen Isabella stands proudly on the castle ramparts overlooking her kingdom at dawn.",
    "archetype": "warrior_queen",
    "culture": "medieval_european",
    "time_of_day": "golden_hour",
    "mood": "triumphant"
  }'
```

### Profile (requires `leader_id` from a splash response)

```bash
curl -s -X POST 'http://localhost:8000/leader' \
  -H 'Content-Type: application/json' \
  -d '{
    "asset_type": "profile",
    "leader_name": "Queen Isabella",
    "leader_description": "A regal portrait of Queen Isabella seated in her throne room.",
    "archetype": "warrior_queen",
    "culture": "medieval_european",
    "time_of_day": "midday",
    "mood": "wise_serene",
    "leader_id": "LEADER_ID_FROM_SPLASH"
  }'
```

### Action (Single Leader)

```bash
curl -s -X POST 'http://localhost:8000/leader' \
  -H 'Content-Type: application/json' \
  -d '{
    "asset_type": "action",
    "leader_name": "Queen Isabella",
    "leader_description": "Queen Isabella leads her knights into battle against invading forces.",
    "archetype": "warrior_queen",
    "culture": "medieval_european",
    "time_of_day": "storm",
    "mood": "grim_determined",
    "leader_id": "LEADER_ID_FROM_SPLASH",
    "action_category": "military",
    "action_description": "Leading a cavalry charge across a muddy battlefield in heavy rain."
  }'
```

### Action (Multi-Leader — uses `leader_ids` list)

```bash
curl -s -X POST 'http://localhost:8000/leader' \
  -H 'Content-Type: application/json' \
  -d '{
    "asset_type": "action",
    "leader_name": "Diplomatic Summit",
    "leader_description": "Two rival rulers meet at a grand oak table to negotiate a peace treaty.",
    "archetype": "diplomat",
    "culture": "medieval_european",
    "time_of_day": "twilight",
    "mood": "hopeful",
    "leader_ids": ["LEADER_ID_1", "LEADER_ID_2"],
    "action_category": "diplomatic",
    "action_description": "A tense but hopeful treaty signing ceremony by candlelight."
  }'
```

### Example 200 Response (splash)

```json
{
  "url": "/assets/leader_test_king_573ccd_splash.png",
  "asset_type": "splash",
  "leader_name": "Test King",
  "leader_id": "leader_test_king_573ccd",
  "leader_ids": [],
  "leader_names": [],
  "seed": 827356658,
  "generation_mode": "static",
  "status": "completed",
  "prompt_used": "epic cinematic wide composition of A test king standing heroically on castle ramparts...",
  "resolution": "1920x1088",
  "generation_time_ms": 57
}
```

### Enum Reference

| Field | Valid Values |
|---|---|
| `asset_type` | `splash`, `profile`, `action` |
| `archetype` | `warrior_queen`, `warrior_king`, `philosopher_king`, `merchant_prince`, `spiritual_leader`, `diplomat`, `tyrant`, `visionary` |
| `culture` | `ancient_egyptian`, `classical_greek`, `roman_imperial`, `medieval_european`, `east_asian_imperial`, `mesopotamian`, `mesoamerican`, `nordic_viking`, `persian`, `sub_saharan_african`, `south_asian`, `islamic_golden_age` |
| `time_of_day` | `dawn`, `golden_hour`, `midday`, `twilight`, `night`, `storm` |
| `mood` | `triumphant`, `wise_serene`, `grim_determined`, `mystical`, `melancholic`, `menacing`, `hopeful`, `contemplative` |
| `action_category` | `military`, `diplomatic`, `construction`, `scientific`, `cultural`, `exploration`, `crisis` |

| Optional Field | Type | Notes |
|---|---|---|
| `seed` | `int` | Override the canonical seed |
| `leader_id` | `string` | Required for `profile` and single-leader `action` |
| `leader_ids` | `list[string]` | For multi-leader `action` scenes |
| `action_category` | `string` | Required for `action` |
| `action_description` | `string` | Required for `action`, max 800 chars |

---

## 2. POST `/structure` — Generate a Building

Generate top-down pixel art structures (fortifications, housing, production buildings, sacred sites).

### Minimal

```bash
curl -s -X POST 'http://localhost:8000/structure' \
  -H 'Content-Type: application/json' \
  -d '{
    "category": "fortification",
    "style": "nordic_wooden",
    "condition": "pristine",
    "scale": "small",
    "description": "A compact wooden watchtower with a pointed shingled roof and a signal fire burning on top."
  }'
```

### With Optional Seed

```bash
curl -s -X POST 'http://localhost:8000/structure' \
  -H 'Content-Type: application/json' \
  -d '{
    "category": "housing",
    "style": "gothic",
    "condition": "weathered",
    "scale": "medium",
    "description": "A two-story medieval townhouse with exposed timber framing and a steep tiled roof.",
    "seed": 12345
  }'
```

### Example 200 Response

```json
{
  "url": "/assets/780a1fcb-392a-4189-bd59-6340a995f295.png",
  "asset_type": "structure",
  "asset_id": "struct_fortification_c774ed",
  "category": "fortification",
  "style": "nordic_wooden",
  "condition": "pristine",
  "scale": "small",
  "description": "A compact wooden watchtower with a pointed shingled roof and a signal fire burning on top.",
  "seed": 16220365,
  "generation_mode": "static",
  "status": "completed",
  "prompt_used": "...",
  "resolution": "128x128",
  "generation_time_ms": 0
}
```

### Enum Reference

| Field | Valid Values |
|---|---|
| `category` | `fortification`, `production`, `housing`, `sacred` |
| `style` | `nordic_wooden`, `anglo_saxon_stone`, `norman_romanesque`, `gothic`, `mediterranean`, `slavic_timber`, `moorish` |
| `condition` | `pristine`, `weathered`, `ruined`, `under_construction`, `fortified` |
| `scale` | `small`, `medium`, `large` |

| Optional Field | Type |
|---|---|
| `seed` | `int` |

---

## 3. POST `/object` — Generate a Nature/World Object

Generate top-down pixel art objects (vegetation, geological features, props, debris).

### Minimal

```bash
curl -s -X POST 'http://localhost:8000/object' \
  -H 'Content-Type: application/json' \
  -d '{
    "category": "vegetation",
    "biome": "temperate_forest",
    "season": "autumn",
    "description": "An ancient oak tree with gnarled branches and scattered orange autumn leaves on the ground."
  }'
```

### Example 200 Response

```json
{
  "url": "/assets/b33c881a-8429-42a4-8ab8-088fefd105c4.png",
  "asset_type": "object",
  "asset_id": "object_vegetation_1c144f",
  "category": "vegetation",
  "biome": "temperate_forest",
  "season": "autumn",
  "description": "An ancient oak tree with gnarled branches and scattered orange autumn leaves on the ground.",
  "seed": 3371447465,
  "generation_mode": "static",
  "status": "completed",
  "prompt_used": "...",
  "resolution": "128x128",
  "generation_time_ms": 0
}
```

### Enum Reference

| Field | Valid Values |
|---|---|
| `category` | `vegetation`, `geological`, `rural_props`, `urban_props`, `debris` |
| `biome` | `temperate_forest`, `taiga`, `desert`, `swamp`, `mountain`, `coastal`, `grassland` |
| `season` | `spring`, `summer`, `autumn`, `winter` |

| Optional Field | Type |
|---|---|
| `seed` | `int` |

---

## 4. POST `/terrain` — Generate Terrain Elevation

Generate top-down pixel art terrain elevation features (hills, slopes, cliffs, ridges, depressions).

> ⚠️ **Important**: The `material` field uses `earthen`, NOT `grassy`. Valid materials are terrain composition types.

### Minimal

```bash
curl -s -X POST 'http://localhost:8000/terrain' \
  -H 'Content-Type: application/json' \
  -d '{
    "category": "hill",
    "scale": "medium",
    "material": "earthen",
    "description": "A gently rolling earthen hill with wildflowers and exposed rocks on the grassy slope."
  }'
```

### Example 200 Response

```json
{
  "url": "/assets/c0d631c5-8267-458a-b8d0-25c5075c55b6.png",
  "asset_type": "terrain",
  "asset_id": "terrain_hill_776195",
  "category": "hill",
  "scale": "medium",
  "material": "earthen",
  "description": "A gently rolling earthen hill with wildflowers and exposed rocks on the grassy slope.",
  "seed": 2854070037,
  "generation_mode": "static",
  "status": "completed",
  "prompt_used": "...",
  "resolution": "128x128",
  "generation_time_ms": 3
}
```

### Enum Reference

| Field | Valid Values |
|---|---|
| `category` | `hill`, `slope`, `cliff`, `ridge`, `depression` |
| `scale` | `low`, `medium`, `high` |
| `material` | `earthen`, `muddy`, `rocky`, `sandy`, `snowy` |

| Optional Field | Type |
|---|---|
| `seed` | `int` |

---

## 5. POST `/unit` — Generate a Unit Sprite

Generate a south-facing top-down pixel art unit sprite (128×128).

### Minimal

```bash
curl -s -X POST 'http://localhost:8000/unit' \
  -H 'Content-Type: application/json' \
  -d '{
    "unit_type": "archer",
    "description": "A skilled medieval archer in green leather armor holding a yew longbow with a quiver of arrows on the back."
  }'
```

### Example 200 Response

```json
{
  "url": "/assets/e8dac2fe-0193-499d-9887-a982961fbf72.png",
  "asset_type": "unit",
  "unit_id": "unit_archer_e3a0da",
  "unit_type": "archer",
  "description": "A skilled medieval archer in green leather armor holding a yew longbow with a quiver of arrows on the back.",
  "seed": 1618605823,
  "generation_mode": "static",
  "status": "completed",
  "prompt_used": "...",
  "resolution": "128x128",
  "generation_time_ms": 2
}
```

### Enum Reference

| Field | Valid Values |
|---|---|
| `unit_type` | `archer`, `scout`, `settler`, `warrior` |

| Optional Field | Type |
|---|---|
| `seed` | `int` |

---

## 6. POST `/background_tile` — Generate a Seamless Ground Tile

Generate a seamless 128×128 repeating ground texture (water, grass, sand, stone, dirt).

### Minimal

```bash
curl -s -X POST 'http://localhost:8000/background_tile' \
  -H 'Content-Type: application/json' \
  -d '{
    "tile_type": "grass"
  }'
```

### Example 200 Response

```json
{
  "url": "/assets/3838d585-1cf4-45ec-b9f1-ea87623f657c.png",
  "asset_type": "background_tile",
  "background_tile_id": "bg_grass_78f3493a",
  "tile_type": "grass",
  "seed": 2267137446,
  "generation_mode": "static",
  "status": "completed",
  "prompt_used": "...",
  "resolution": "128x128",
  "generation_time_ms": 2
}
```

### Enum Reference

| Field | Valid Values |
|---|---|
| `tile_type` | `water`, `grass`, `sand`, `stone`, `dirt` (case-insensitive) |

---

## Error Responses

| Code | Meaning | Example Response |
|---|---|---|
| **400** | Invalid field value (e.g., missing `leader_id` for profile) | `{"detail": "leader_id is required for profile assets"}` |
| **422** | Validation error (bad enum, missing required field, extra field) | `{"detail": [{"loc": ["body","material"], "msg": "Value error, Unknown material 'grassy'..."}]}` |
| **429** | Rate limit exceeded (2 POST req/s, burst 5) | `{"detail": "Rate limit exceeded. Slow down."}` |
| **503** | ComfyUI unavailable or database not initialized | `{"detail": "ComfyUI not available"}` |

## Quick Test All Endpoints

```bash
BASE="http://localhost:8000"

# 1. Leader splash
curl -s -X POST "$BASE/leader" -H 'Content-Type: application/json' \
  -d '{"asset_type":"splash","leader_name":"Test King","leader_description":"A test king standing heroically on castle ramparts at sunrise overlooking his kingdom.","archetype":"warrior_king","culture":"medieval_european","time_of_day":"dawn","mood":"triumphant"}' | python3 -m json.tool

# 2. Structure
curl -s -X POST "$BASE/structure" -H 'Content-Type: application/json' \
  -d '{"category":"fortification","style":"nordic_wooden","condition":"pristine","scale":"small","description":"A compact wooden watchtower with a pointed shingled roof and a signal fire burning on top."}' | python3 -m json.tool

# 3. Object
curl -s -X POST "$BASE/object" -H 'Content-Type: application/json' \
  -d '{"category":"vegetation","biome":"temperate_forest","season":"autumn","description":"An ancient oak tree with gnarled branches and scattered orange autumn leaves on the ground."}' | python3 -m json.tool

# 4. Terrain
curl -s -X POST "$BASE/terrain" -H 'Content-Type: application/json' \
  -d '{"category":"hill","scale":"medium","material":"earthen","description":"A gently rolling earthen hill with wildflowers and exposed rocks on the slope."}' | python3 -m json.tool

# 5. Unit
curl -s -X POST "$BASE/unit" -H 'Content-Type: application/json' \
  -d '{"unit_type":"archer","description":"A skilled medieval archer in green leather armor holding a yew longbow with a quiver of arrows on the back."}' | python3 -m json.tool

# 6. Background tile
curl -s -X POST "$BASE/background_tile" -H 'Content-Type: application/json' \
  -d '{"tile_type":"grass"}' | python3 -m json.tool
```

> **Tip**: Pipe through `| python3 -m json.tool` for pretty-printed JSON. Use `| jq .` if `jq` is installed.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `Connection refused` | Server not running | `uvicorn src.main:app --host 0.0.0.0 --port 8000` |
| `"status": "degraded"` on `/health` | ComfyUI unreachable | Expected in placeholder mode; set `.env` from `.env.testing` |
| All responses return `"generation_mode": "static"` | ComfyUI fallback active | Set `GENERATION__MODES__*` in `.env` |
| `429 Rate limit exceeded` | Too many requests in sequence | Wait 1 second between requests |
| `422` with unknown enum value | Wrong enum string | Check the enum reference tables above |
| `503 Database schema not initialized` | DB migration needed | Run `alembic upgrade head` |

## See Also

- [README.md](../README.md) — Project overview and quick-start guide
- [docs/architecture.md](architecture.md) — Full system architecture and endpoint table
- [scripts/validate_api.py](../scripts/validate_api.py) — Automated API validation script
- [scripts/smoke_test_endpoints.sh](../scripts/smoke_test_endpoints.sh) — Bash smoke-test script
