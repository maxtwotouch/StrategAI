# Asset Integration Guide

> **Last Validated: 2026-06-01**

## 1. Overview

StrategAI uses a self-hosted generative pixel-art service to produce game visuals at runtime. The frontend resolves every game entity (terrain tile, unit sprite, city structure, leader portrait) into a concrete image URL from the asset server, then renders the result on the SVG hex map. When the asset server is unreachable or `NEXT_PUBLIC_ASSET_API_URL` is unset, the game degrades gracefully through a four-tier fallback chain ending in built-in Unicode glyphs and deterministic color fills.

### Service contract at a glance

| Concern | Mechanism |
|---|---|
| **Generation** | POST to `/background_tile`, `/terrain`, `/structure`, `/unit`, `/leader` — each returns a unique `/assets/{uuid}.png` URL |
| **Image serving** | GET `/assets/{filename}` — raw PNG, no auth, no CORS restriction |
| **Discovery** | GET `/catalog`, `/modes`, `/health`, `/leader` (leader catalog) |
| **Client proxy** | `frontend/app/api/asset/[...path]/route.ts` — Next.js API route that forwards POST calls server-to-server, sidestepping browser CORS |
| **Image loading** | Direct `<img>` / SVG `<image>` from `ASSET_BASE_URL` — PNGs are not CORS-blocked by browsers |

### Key source files

| File | Role |
|---|---|
| `frontend/lib/assetManifest.ts` | Resolution orchestrator — fans out all POSTs, collects results, returns `AssetManifest` |
| `frontend/lib/assetApi.ts` | API client — typed wrappers around every asset server endpoint |
| `frontend/lib/assetMapping.ts` | Entity → enum mapping — terrain, unit, structure, elevation, culture profiles |
| `frontend/lib/leaderMapping.ts` | Leader name → archetype/culture/mood/time-of-day mapping |
| `frontend/lib/hex.ts` | Tier-4 fallback — 13 terrain colors, Unicode glyphs for units/improvements/resources |
| `assetserver/src/main.py` | Asset server endpoints and middleware |

---

## 2. Entity-to-Asset Mapping

### 2.1 Terrain → Background Tiles

The 13 frontend terrain display types (10 engine terrains + 3 display-only) collapse onto **5 background tile types**. Every distinct terrain key resolves its own image, so terrains sharing a type (e.g. ocean/coast/lake → `water`) still look different within a game.

**Defined in:** `frontend/lib/assetManifest.ts` (`TERRAIN_TO_TILE_TYPE`)

| Tile Type | Terrains |
|---|---|
| `water` | ocean, coast, lake |
| `grass` | grassland, plains, savanna, forest, taiga |
| `stone` | hills, mountain, tundra, snow |
| `sand` | desert |

Additionally, **elevation overlays** are generated for `hills` and `mountain` via `POST /terrain` and layered on top of the base tile:

**Defined in:** `frontend/lib/assetMapping.ts` (`ELEVATION_TERRAINS`)

| Terrain | Asset Category | Scale | Material |
|---|---|---|---|
| hills | `hill` | `medium` | `earthen` |
| mountain | `cliff` | `high` | `rocky` |

### 2.2 Unit Types

**7 backend unit types** map onto **4 asset server unit categories** (`archer`, `scout`, `settler`, `warrior`). All sprites are south-facing (front view) — the canonical direction for top-down characters.

**Defined in:** `frontend/lib/assetMapping.ts` (`UNIT_TYPE_MAP`)

| API Unit Type | Game Units |
|---|---|
| `warrior` | warrior, swordsman, horseman |
| `archer` | archer |
| `scout` | scout |
| `settler` | settler, worker |

Each civilization gets its own per-culture variant. The unit description string is assembled from the culture profile's `unitKit`, `motifs`, and `culturePrefix`, combined with a base shape description:

```
"{culturePrefix} {baseShape}, wearing {unitKit}, with visual motifs of {motifs}"
```

**Culture profiles** (11 total) are defined in `frontend/lib/assetMapping.ts` (`CULTURE_PROFILES`), with per-leader overrides for Genghis Khan, Cleopatra, and Mahatma Gandhi.

### 2.3 Structures

**4 structure categories** are generated per civilization:

**Defined in:** `frontend/lib/assetMapping.ts` (`STRUCTURE_CATEGORIES`)

| Category ID | Label | Hint |
|---|---|---|
| `production` | Production Hall | Workshop, forge, mill |
| `fortification` | Fortification | Walls, keep, gatehouse |
| `housing` | Housing District | Townhouse, longhouse, manor |
| `sacred` | Sacred Site | Temple, shrine, cathedral |

The `cityStructureFor()` function assembles a `StructureParams` object from the culture profile's materials, silhouette, motifs, and architectural style. Styles map to asset server enum values: `nordic_wooden`, `moorish`, `mediterranean`, `anglo_saxon_stone`, `slavic_timber`.

### 2.4 Leaders

Leader name → deterministic parameter lookup. Each leader has an archetype, culture, time-of-day, mood, and physical description (≥50 chars).

**Defined in:** `frontend/lib/leaderMapping.ts` (`LEADER_DEFS`)

| Leader | Archetype | Culture | Time of Day | Mood |
|---|---|---|---|---|
| Genghis Khan | `warrior_king` | `east_asian_imperial` | `storm` | `menacing` |
| Cleopatra | `diplomat` | `ancient_egyptian` | `golden_hour` | `wise_serene` |
| Mahatma Gandhi | `philosopher_king` | `south_asian` | `dawn` | `wise_serene` |
| *(fallback)* | `philosopher_king` | `medieval_european` | `golden_hour` | `contemplative` |

**Two-stage pipeline:** `POST /leader` with `asset_type: "splash"` returns a `leader_id`, then `POST /leader` with `asset_type: "profile"` + `leader_id` generates the square portrait via img2img for face consistency.

**Human player custom leaders:** When the player authors their own leader on the start screen, `buildCustomLeaderParams()` in `leaderMapping.ts` constructs the `LeaderParams` from user-supplied archetype, culture, and description, filling in safe defaults for missing fields.

---

## 3. Asset Resolution Flow

The `resolveManifest()` function in `frontend/lib/assetManifest.ts` orchestrates the entire resolution. It runs once per game start (every "Begin Campaign" or page refresh).

```
resolveManifest(input)
  │
  ├─ [guard] assetApiConfigured()? → no → return null (skip all fetches)
  │
  ├─ [parallel] terrain tiles     (bounded concurrency: 4)
  │   └─ POST /background_tile {tile_type}
  │
  ├─ [parallel] elevation overlays (bounded concurrency: 2)
  │   └─ POST /terrain {category, scale, material, description}
  │
  ├─ [parallel] per-civ unit sprites (all civs in parallel, each civ 2-at-a-time)
  │   └─ POST /unit {unit_type, description}
  │
  ├─ [parallel] per-civ structures   (all civs in parallel, each civ 2-at-a-time)
  │   └─ POST /structure {category, style, condition, scale, description}
  │
  ├─ [fetch] GET /leader (existing catalog — fallback pool)
  │
  ├─ [serial] leader splashes + profiles (bounded concurrency: 2)
  │   ├─ POST /leader {asset_type: "splash", …} → leader_id
  │   └─ POST /leader {asset_type: "profile", leader_id, …}
  │
  └─ → AssetManifest (or null)
```

**Concurrency model:** The `mapLimit()` helper runs an async worker over items with a bounded number in flight — terrain tiles at 4 concurrent POSTs, units/structures at 2 per civ, leaders at 2 globally. This prevents the frontend from hammering the (potentially GPU-bound) asset server with dozens of parallel generation requests.

**Progress reporting:** An optional `onProgress(done, total)` callback reports resolution progress, driving the loading bar on the War Room splash screen.

**Leader catalog fallback:** Before generating leader assets, the manifest resolver fetches `GET /leader` to build a pool of previously generated leaders. If a splash generation POST fails (e.g. upstream model error), it picks the best-matching existing leader by archetype+culture score from this pool.

---

## 4. Four-Tier Fallback

Every visual asset follows a four-tier fallback chain. If any generation or fetch fails, the renderer silently moves to the next tier.

### Tier 1: ComfyUI Generative
The asset server generates a fresh PNG via FLUX2 Klein 4B Distilled + LoRA. The POST returns a `/assets/{uuid}.png` URL. This is the normal operating mode.

### Tier 2: Static Pre-generated
When the asset server runs in `static` mode (no ComfyUI available), it serves pre-generated PNGs from `static_tiles/` and `splash_assets/` directories. These are shipped with the asset server and indexed by enum values.

### Tier 3: PIL Placeholder
When the asset server runs in `placeholder` mode, it generates simple colored rectangles with text labels via Python Pillow (PIL). These are visually minimal but preserve layout and discoverability.

### Tier 4: Built-in Colors, Glyphs, and Initials
When `NEXT_PUBLIC_ASSET_API_URL` is unset, `resolveManifest()` returns `null`, and every renderer falls back to deterministic built-in values defined in `frontend/lib/hex.ts`:

| Asset | Fallback |
|---|---|
| **Terrain tiles** | `TERRAIN_COLORS` — 13 hex color values (e.g. grassland `#4f7a2a`, ocean `#13243a`) |
| **Terrain borders** | `TERRAIN_STROKE` — matching darker stroke colors |
| **Unit sprites** | `UNIT_GLYPH` — Unicode glyphs (⚔ warrior, ⌂ settler, ◉ scout, ⚙ worker, ↟ archer, ♞ horseman, ✦ swordsman) |
| **Improvements** | `IMPROVEMENT_GLYPH` — ≈ farm, ⛏ mine, ═ road |
| **Resources** | `RESOURCE_GLYPH` — 🌾 wheat, 🐂 cattle, 🐟 fish, ⚒ iron, 🐎 horses, ▮ coal, ◆ gems, ❀ silk, ✦ spices |
| **Features** | `FEATURE_GLYPH` — ♣ forest, ❦ jungle, ≈ marsh, ❂ oasis |
| **Leaders** | Colored initial circle (first letter of leader name) |
| **Structures** | Colored square with category abbreviation |
| **Civ colors** | `CIV_COLORS` — 4 preset faction colors (`#d4a443`, `#5a8cc4`, `#b05a4a`, `#7e6ac4`) assigned by civ index |

---

## 5. Caching Strategy

**There is no persistent cache.** Every "Begin Campaign" (and every page refresh that triggers a new game) hits the asset service fresh. The original `localStorage` cache under key `inf3600:assetManifest:{hostTag}:{gameId}` was removed because it could serve stale URLs when the backend restarted and reused a `gameId`. A one-time housekeeping block at the top of `assetManifest.ts` purges any leftover localStorage entries from earlier sessions.

**Rationale:** The asset server is a generate-and-cache API — every POST returns a unique `/assets/{uuid}.png` URL. These URLs are ephemeral (tied to the asset server's local storage). Caching them client-side risks broken images after an asset server restart. The speed win of skipping fetches doesn't outweigh that hazard.

Within a single game session, the resolved `AssetManifest` object is held in React state on `page.tsx` and passed as a prop to `<SquareMap>` and all panel components. No re-resolution occurs until the next game start.

---

## 6. Configuration

### Environment Variable

| Variable | Purpose | Default |
|---|---|---|
| `NEXT_PUBLIC_ASSET_API_URL` | Base URL of the asset server (e.g. `http://localhost:8001`) | *(empty)* |

**When unset:** `assetApiConfigured()` returns `false`, `resolveManifest()` returns `null`, and the game renders entirely with Tier-4 built-in colors, glyphs, and initials. Set this in `frontend/.env.local` and restart `next dev` after editing.

### Asset Server Modes

The asset server supports three generation modes per asset family, configured via `assetserver/config.yaml` or `ASSET_MODE__{family}` env vars:

| Mode | Behavior |
|---|---|
| `comfyui` | Full generative pipeline (FLUX2 Klein 4B + LoRA) |
| `static` | Pre-generated PNGs from `static_tiles/` |
| `placeholder` | PIL-generated colored rectangles with labels |

Families: `background_tile`, `terrain`, `structure`, `object`, `unit`, `leader`. Each family can be configured independently. The frontend discovers active modes via `GET /modes`.

### Next.js API Proxy

All POST requests from the browser are routed through `frontend/app/api/asset/[...path]/route.ts`. This Next.js API route forwards requests server-to-server, sidestepping browser CORS restrictions for JSON API calls. Image loading (`<img>`, SVG `<image>`) uses direct URLs from `ASSET_BASE_URL` — browsers do not enforce CORS on image requests, so no proxy is needed for PNGs.

---

## 7. Endpoint Reference

### Generation (POST)

| Endpoint | Used For | Key Parameters |
|---|---|---|
| `POST /background_tile` | Terrain base tiles | `tile_type` (water, grass, sand, stone, dirt) |
| `POST /terrain` | Elevation overlays | `category`, `scale`, `material`, `description` |
| `POST /structure` | City buildings | `category`, `style`, `condition`, `scale`, `description` |
| `POST /unit` | Unit sprites | `unit_type` (archer, scout, settler, warrior), `description` |
| `POST /leader` | Leader portraits | `asset_type` (splash, profile, action), `leader_name`, `archetype`, `culture`, `time_of_day`, `mood`, `leader_description` |

### Discovery (GET)

| Endpoint | Used For |
|---|---|
| `GET /leader` | Existing leader catalog (fallback pool) |
| `GET /catalog` | Available static assets and valid enum values |
| `GET /modes` | Active generation mode per family |
| `GET /health` | Component-level health (database, ComfyUI, templates) |
| `GET /health/ready` | Readiness probe (returns 200 after startup complete) |
| `GET /assets/{filename}` | Raw PNG serving |

---

## 8. Adding a New Asset Type

1. **Asset server:** Define Pydantic request/response models, create an engine class, register a POST endpoint in `assetserver/src/main.py`, and add prompt templates in `config/prompt_templates.json`.
2. **Frontend API client:** Add typed wrapper function(s) in `frontend/lib/assetApi.ts`.
3. **Frontend mapping:** Add enum-to-parameter mapping in `frontend/lib/assetMapping.ts`.
4. **Frontend manifest:** Add resolution work to `resolveManifest()` in `frontend/lib/assetManifest.ts` — update the `total` counter, add the parallel work block, and extend the `AssetManifest` interface.
5. **Fallback:** Add Tier-4 glyph/color entries in `frontend/lib/hex.ts`.
6. **Renderer:** Consume the new manifest field in `frontend/components/SquareMap.tsx` or the relevant panel component, with an `onError` fallback to the Tier-4 glyph/color.
