# StrategAI — Frontend Architecture

> **Updated:** 2026-05-31  
> **Target audience:** New frontend developers joining the project.

---

## 1. Overview

### 1.1 Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | [Next.js](https://nextjs.org/) (App Router) | ^15.0.0 |
| UI Library | [React](https://react.dev/) | ^19.0.0 |
| Language | TypeScript (strict mode) | ^5.5.0 |
| Styling | CSS Modules (`globals.css` — single global stylesheet) | — |
| State | React `useState` + `useRef` + `useMemo` (no external lib) | — |
| Rendering | SVG (map) + HTML (panels) | — |
| Asset service proxy | Next.js Route Handlers (`app/api/asset/[...path]/route.ts`) | — |

> **`pixi.js`** (`^8.18.1`) is listed in `package.json` but is **not currently used** — the map is rendered in SVG. It was added speculatively for a potential WebGL layer.

### 1.2 Directory Structure

```
frontend/
├── app/
│   ├── api/
│   │   └── asset/
│   │       └── [...path]/
│   │           └── route.ts        # Server-to-server proxy for asset service
│   ├── globals.css                 # Global stylesheet (~1250 lines)
│   ├── layout.tsx                  # Root layout (<html>, <body>, metadata)
│   └── page.tsx                    # Main game component (~2180 lines)
├── components/
│   ├── SquareMap.tsx               # SVG hex map renderer (~920 lines)
│   └── mapTypes.ts                 # TypeScript interfaces for map props
├── lib/
│   ├── api.ts                      # Backend API client (~260 lines)
│   ├── assetApi.ts                 # Asset service client (~310 lines)
│   ├── assetManifest.ts            # Asset manifest resolver (~360 lines)
│   ├── assetMapping.ts             # Deterministic game→asset param maps (~350 lines)
│   ├── hex.ts                      # Grid math, colors, glyphs (~145 lines)
│   ├── leaderMapping.ts            # Leader→generation params (~110 lines)
│   ├── turnEvents.ts               # Turn diff/event extraction (~110 lines)
│   └── useAudio.ts                 # Audio hook (music, narration) (~200 lines)
├── public/
│   └── audio/                      # MP3 music tracks (ambient, battle, bards-tale)
├── .env.example                    # Env var template
├── next.config.mjs                 # Next.js config (strict mode on)
├── package.json
└── tsconfig.json
```

### 1.3 Build & Run Commands

```bash
# Development
cd frontend
npm install
npm run dev           # → http://localhost:3000

# Type checking
npm run typecheck     # ≡ tsc --noEmit

# Production build
npm run build
npm start

# Environment
cp .env.example .env.local
# Edit NEXT_PUBLIC_API_URL and NEXT_PUBLIC_ASSET_API_URL as needed
```

**Key env vars:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend FastAPI server |
| `NEXT_PUBLIC_ASSET_API_URL` | _(empty)_ | Optional asset generation service. When empty, all assets fall back to built-in colors/glyphs. |

---

## 2. Component Hierarchy

The entire game lives in a single file: `app/page.tsx` (~2180 lines). This is a **"use client"** component — no server rendering.

### 2.1 Application Lifecycle

```
┌─────────┐    ┌──────────┐    ┌────────┐    ┌────────────┐
│  Start  │───→│  Loading  │───→│  Intro  │───→│  War Room  │
│  Screen │    │  Screen   │    │  Screen │    │  (main)    │
└─────────┘    └──────────┘    └────────┘    └────────────┘
     ↑              ↑               ↑               ↑
 hasStarted     state===null   !introDismissed   introDismissed
   =false        && hasStarted   && state          && state
```

Three `if` branches in the `HomePage` component:

1. **`!hasStarted`** → Start screen (civilization name, leader, archetype, culture, map radius, appearance description)
2. **`hasStarted && !state`** → Loading screen with slideshow of prior campaign leader splashes, asset generation progress
3. **`hasStarted && state && !introDismissed`** → Intro splash screen (Chapter I, campaign narration, "Begin the Age" button)
4. **`hasStarted && state && introDismissed`** → War Room (main game)

### 2.2 Start Screen (`!hasStarted`)

- Civilization name input
- Leader name input
- Archetype dropdown (8 options: Warrior King, Philosopher King, Diplomat, Tyrant, etc.)
- Culture dropdown (12 options: Medieval European, Ancient Egyptian, Roman Imperial, etc.)
- Map radius slider (2–32)
- Leader appearance textarea (custom physical description, 50–800 characters)
- "Begin Campaign" button triggers `beginGame()` → `loadGame()`

### 2.3 Loading Screen (`hasStarted && !state`)

- Slideshow of randomly selected prior campaign leader splash art
- Loading spinner
- Asset generation progress counter (e.g., "Conjuring world art… 12/48")
- Polls `listLeaders()` from the asset service for the slideshow

### 2.4 Intro Screen (`hasStarted && state && !introDismissed`)

- Full-screen leader splash as background
- "Chapter I" plate, civilization name, leader name
- Epitaph text
- "Begin the Age" primary CTA → `dismissIntro()` → `startAmbient()`
- "Replay Proclamation" button → re-generates narration audio
- AI voice narration status indicator
- Dismiss by: click backdrop, Escape, Enter, Space

### 2.5 War Room Layout (`introDismissed && state`)

```
┌──────────────────────────────────────────────────┐
│ TOP BAR: badge · metrics · mute · turn · end turn│
├──────┬───────────────────────────────┬───────────┤
│ LEFT │         MAP STAGE              │   RIGHT   │
│ RAIL │   ┌─────────────────────┐     │   RAIL    │
│      │   │    <SquareMap>      │     │           │
│ Mini │   │                     │     │ Research  │
│ map  │   │   leader ribbon     │     │ panel     │
│      │   │   banner events     │     │           │
│ Unit │   │   terrain readout   │     │ Cities    │
│ sele │   └─────────────────────┘     │ panel     │
│ ction│                               │           │
│      │                               │ Standings │
│      │                               │ panel     │
├──────┴───────────────────────────────┴───────────┤
│ BOTTOM: Chronicle / Event log                     │
└──────────────────────────────────────────────────┘
```

#### Top Bar Components

- **Empire Badge**: Click → opens sovereign portrait overlay. Shows leader profile image or initial.
- **Metrics**: Science, Gold (with net income delta), Culture, Score, Cities count.
- **Audio Toggle**: Mute/unmute button with SVG glyph.
- **Turn Box**: Current turn number, whose move it is (human/AI name), "End Turn" button.
- **Next Objective**: One-line hint of what the player should do next (auto-computed from game state).

#### Left Rail

1. **Minimap Panel**: CSS-grid minimap — each cell colored by terrain type, with visible/focused markers.
2. **Selection Panel**: When a unit is selected — shows type, health, moves, owner, tile position. Buttons: "Clear", "Found City" (settlers), improvement selection (workers).

#### Center — Map Stage

- **`<SquareMap>`** (see Section 6)
- **Leader Ribbon**: Horizontal row of rival civ avatars below the map. Click to open diplomacy drawer.
- **Banner Events**: Turn chronicle popup (auto-dismisses after 4.5s)
- **Terrain Readout**: Hovered tile details — terrain name, feature, yields (food/prod/gold), resource, unit/city info

#### Right Rail

1. **Research Panel**: Current research progress bar, tech choice grid (20 techs across 4 tiers)
2. **Cities Panel**: List of human cities, click to open city drawer
3. **Standings Panel**: Scoreboard — all civs ranked with current score vs. threshold

#### Bottom — Chronicle

- Collapsible event log (last 80 events)
- Tabs: "Events" | "Inbox (N)" with badge count
- Log entries show kind tag, text, turn number

### 2.6 Drawers & Overlays

| Component | Trigger | Behavior |
|-----------|---------|----------|
| **City Naming Modal** | "Found City" button on settler | Modal with text input + Enter to confirm |
| **Diplomacy Audience** | Click leader in ribbon | Full-screen overlay: splash bg, portrait, message thread, composer, incident history |
| **City Drawer** | Click city in map or cities panel | Right slide-in panel: stats, production queue, build order, structures (draggable) |
| **Sovereign Portrait** | Click empire badge | Full-screen overlay showing leader splash + details |

### 2.7 Helper UI Components (defined in `page.tsx`)

| Component | Purpose |
|-----------|---------|
| `Panel` | Reusable card with label, title, body slot |
| `TopMetric` | Metric with strong number, label, optional delta |
| `MetricStat` | Label + value statistic |
| `YieldLine` | Tile yield display (food/prod/gold) |
| `EmptyCopy` | Muted placeholder text for empty panels |
| `LeaderPortrait` | Circular leader image with fallback initial |
| `MiniMap` | CSS-grid minimap |
| `MessageCard` | Diplomacy message bubble |
| `AudioGlyph` | SVG speaker icon with mute state |
| `formatNetDelta`, `capitalize`, `formatError`, `maxHealthFor`, `canAttackOwner`, `relationshipLabel`, `relationshipColor` | Utility functions |

---

## 3. State Management

**No external state libraries** — pure React hooks only.

### 3.1 `useState` — Core Game & UI State

All state is held in `HomePage` (the top-level component in `page.tsx`). There is no context provider or global store.

| State Variable | Type | Purpose |
|---------------|------|---------|
| `state` | `GameStateDTO \| null` | Full game state from backend |
| `selectedUnit` | `UnitDTO \| null` | Currently selected human unit |
| `hoveredTile` | `TileDTO \| null` | Tile under cursor |
| `error` | `string \| null` | Error toast (auto-clears after 5s) |
| `busy` | `boolean` | Loading lock for actions |
| `pending` | `PendingAction \| null` | Pending "found city" action |
| `cityName` | `string` | City naming input |
| `setup` | `Setup` | Start screen form fields |
| `messageTargetId` | `number \| null` | Diplomacy target civ |
| `messageKind` | `string` | Diplomacy message tone |
| `messageText` | `string` | Diplomacy message body |
| `activeConversationCivId` | `number \| null` | Which civ's diplomacy is open |
| `activeCityId` | `number \| null` | Which city drawer is open |
| `hasStarted` | `boolean` | App lifecycle gate |
| `chronicleCollapsed` | `boolean` | Event log collapsed state |
| `bannerEvents` | `TurnEvent[] \| null` | Popup events (auto-dismiss) |
| `eventLog` | `TurnEvent[]` | Persistent event log (capped at 80) |
| `assets` | `AssetManifest \| null` | Resolved asset URLs |
| `placedStructureAssets` | `Record<string, string>` | Per-placement structure images |
| `assetProgress` | `{ done, total } \| null` | Loading progress counter |
| `loadingSplashUrls` | `string[]` | Slideshow images |
| `loadingSplashIndex` | `number` | Current slideshow frame |
| `introDismissed` | `boolean` | Intro screen dismissed |
| `showSovereign` | `boolean` | Sovereign overlay visible |
| `introNarrationStatus` | `"idle" \| "generating" \| "playing" \| "unavailable"` | Narration lifecycle |

### 3.2 `useRef` — Mutable References

Used for values that shouldn't trigger re-renders:

| Ref | Purpose |
|-----|---------|
| `prevStateRef` | Previous game state (for diffing turn events) |
| `bannerTimerRef` | Timeout handle for auto-dismissing banner events |
| `loadingSplashRunRef` | Run counter (prevents stale slideshow updates on rapid restarts) |
| `introNarratedRef` | Guard flag (narrate only once per game) |
| `introNarrationUrlRef` | Object URL for narration blob (for cleanup) |
| `musicRef` / `narrationRef` | Audio element refs (in `useAudio.ts`) |
| `phaseRef` / `trackIndexRef` / `targetVolumeRef` | Audio state refs (in `useAudio.ts`) |

**In `SquareMap.tsx`**, refs manage the camera and drag state to avoid React re-render overhead during panning:

| Ref | Purpose |
|-----|---------|
| `containerRef` | Map container div (ResizeObserver target) |
| `svgRef` | SVG element (viewBox manipulation) |
| `dragRef` | Drag state (start, last, moved) |
| `stageSizeRef` | Cached container dimensions |
| `cameraRef` | Cached camera (for non-React viewBox updates) |
| `boundsRef` | Cached map bounds |
| `panDeltaRef` | Accumulated pan deltas |
| `panFrameRef` | rAF handle for pan flush |
| `justDraggedRef` | Drag-vs-click disambiguation |
| `userCameraDirtyRef` | Whether user has manually panned/zoomed |
| `homeFocusRef` | Auto-center target |

### 3.3 `useMemo` — Derived Computations

Heavy or frequently-referenced derived values are memoized:

- **`SquareMap`**: `pixels` (tile→pixel coords), `unitAt` (tile→unit lookup), `cityAt` (tile→city lookup), `tileOwnerByCiv` (civ→tiles map), `humanOwnedKeys`, `workedHighlight`, `bounds`, `focusPoint`
- **`HomePage`**: `humanCiv`, `humanCities`, `humanUnits`, `isHumanTurn`, `otherCivs`, `visibleTiles`, `activeCity`, `selectedCity`, `reachable` (adjacent tiles), `availableTechs`, `buildableUnits`, `currentResearch`, `selectedProductionCity`, `activeConversation`, `activeConversationCiv`, `activeLeaderSplash`, `activeStance`, `activeDiplomaticEvents`, `availableMessageKinds`, `inboxCounts`, `totalInbox`, `mapFocusHex`, `hoveredUnit`, `hoveredCity`

### 3.4 State Flow Pattern

```
Backend API → run(fn) → setState(next) → ingestEvents(next) → re-render
                                        → setSelectedUnit(updated)
                                        → setHoveredTile(updated)
```

The `run()` wrapper:
1. Sets `busy = true`
2. Calls the async action function
3. On success: calls `ingestEvents()` to diff turn events, updates state + selectedUnit + hoveredTile
4. On error: sets `error` state (auto-clears after 5 seconds)
5. Sets `busy = false`

---

## 4. API Integration

### 4.1 `lib/api.ts` — Backend API Client

All backend communication goes through this module. Two base primitives:

- **`req<T>(path, init?)`**: JSON request → typed JSON response. Sets `Content-Type: application/json`, `cache: no-store`.
- **`reqBlob(path, init?)`**: Same but returns a `Blob` (used for audio).

**Base URL**: `NEXT_PUBLIC_API_URL ?? "http://localhost:8000"`

### 4.2 API Methods (14 total)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `createGame(radius, seed, human_name)` | `POST /games` | Create new game |
| `getGame(id)` | `GET /games/{id}` | Fetch game state |
| `endTurn(id)` | `POST /games/{id}/turn` | Advance turn (legacy) |
| `resolveTurn(id)` | `POST /games/{id}/turn/resolve` | Resolve all AI turns |
| `move(id, unit_id, q, r)` | `POST /games/{id}/actions/move` | Move unit |
| `attack(id, attacker_id, defender_id)` | `POST /games/{id}/actions/attack` | Attack unit |
| `foundCity(id, unit_id, name)` | `POST /games/{id}/actions/found` | Found a city |
| `research(id, civ_id, tech_id)` | `POST /games/{id}/actions/research` | Choose research |
| `build(id, civ_id, city_id, unit_type)` | `POST /games/{id}/actions/build` | Queue unit production |
| `cancelBuild(id, civ_id, city_id, index)` | `POST /games/{id}/actions/cancel-build` | Remove from queue |
| `purchaseStructure(id, civ_id, city_id, category, q, r)` | `POST /games/{id}/actions/purchase-structure` | Buy city structure |
| `improve(id, unit_id, improvement)` | `POST /games/{id}/actions/improve` | Build improvement |
| `sendMessage(id, from_civ_id, to_civ_id, kind, text)` | `POST /games/{id}/actions/message` | Send diplomatic message |
| `generateIntroNarration(text)` | `POST /audio/intro` | TTS narration (returns Blob) |

### 4.3 DTOs (Data Transfer Objects)

All DTOs mirror backend schemas from `backend/app/api/schemas.py`. Key types:

- **`GameStateDTO`**: Top-level — `id`, `turn`, `current_civ_id`, `map_radius`, `tiles`, `civs`, `civ_roster`, `cities`, `structures`, `units`, `known_civ_ids`, `messages`, `inbox`, `stances`, `visible_tile_keys`, `tile_owner`, `diplomatic_events`, `standings`, `score_threshold`
- **`TileDTO`**: `q`, `r`, `terrain`, `resource`, `feature`, `river`, `improvement`, `food`, `production`, `gold`
- **`UnitDTO`**: `id`, `owner`, `type`, `q`, `r`, `health`, `moves_remaining`, `work_order`
- **`CityDTO`**: `id`, `owner`, `name`, `q`, `r`, `population`, `food_stored`, `production_stored`, `health`, `max_health`, `is_capital`, `buildings`, `production_queue`, `border_radius`, `culture_stored`, `worked_tiles`, `purchased_structures`
- **`CivDTO`**: `id`, `name`, `leader_name`, `is_human`, `gold`, `gold_income`, `gold_upkeep`, `science`, `culture`, `known_techs`, `researching`, `score`
- **`MessageDTO`**, **`StanceDTO`**, **`DiplomaticEventDTO`**, **`StandingDTO`**, **`CivRosterEntryDTO`**, **`CityStructureDTO`**, **`WorkOrderDTO`**, **`TileOwnerDTO`**

### 4.4 Error Handling Pattern

```typescript
// api.ts — throws on non-2xx with status + body
if (!res.ok) {
  const body = await res.text();
  throw new Error(`${res.status} ${res.statusText}: ${body}`);
}

// page.tsx — caught by run() wrapper
const run = async (fn: () => Promise<GameStateDTO>) => {
  setBusy(true);
  setError(null);
  try {
    const next = await fn();
    // ... update state
  } catch (e: unknown) {
    setError(formatError(e));  // 5s auto-clear via useEffect
  } finally {
    setBusy(false);
  }
};
```

---

## 5. Asset Resolution Pipeline

### 5.1 Architecture Overview

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  page.tsx    │────→│ assetManifest.ts │────→│   assetApi.ts    │
│  loadGame()  │     │  resolveManifest │     │  POST generation  │
└──────────────┘     └──────────────────┘     └────────┬─────────┘
                                                       │
                                              ┌────────▼─────────┐
                                              │  /api/asset/     │
                                              │  [...path]       │
                                              │  (Next.js proxy)  │
                                              └────────┬─────────┘
                                                       │
                                              ┌────────▼─────────┐
                                              │  Asset Server    │
                                              │  (ComfyUI/FLUX2) │
                                              └──────────────────┘
```

### 5.2 `lib/assetManifest.ts` — Manifest Resolution

**`resolveManifest(input, options?)`** is called once during `loadGame()`. It:

1. Checks `assetApiConfigured()` — returns `null` immediately if no asset server URL
2. Collapses 13 game terrain types into 4 service tile types (water/grass/sand/stone)
3. Runs 5 parallel generation phases with bounded concurrency (`mapLimit`):

| Phase | Items | Concurrency | Result |
|-------|-------|-------------|--------|
| Terrain tiles | ~4–13 distinct terrains | 4 | `terrain[terrainKey] → imageUrl` |
| Elevation overlays | Hills, mountain only | 2 | `elevation[terrainKey] → imageUrl` |
| Unit sprites | Per-civ × 4 API types | 2 per civ | `units[civId][gameType] → imageUrl` |
| Structure sprites | Per-civ × 4 categories | 2 per civ | `structures[civId][category] → imageUrl` |
| Leader portraits | Per-leader (splash + profile) | 2 total | `leaders[civId] → { splashUrl, profileUrl }` |

4. Returns `AssetManifest` with all resolved URLs

**Key design decisions:**
- **No persistent cache** — Every game start hits the asset service fresh. Previous localStorage caching was removed to prevent stale URLs when the backend reuses game IDs.
- **Graceful degradation** — Every phase has try/catch; failures leave individual asset slots unmapped.
- **Leader fallback pool** — If POST generation fails for a leader, the resolver picks a best-match entry from the existing leader catalog (`listLeaders()`) by archetype + culture match.

### 5.3 `lib/assetApi.ts` — Asset Service Client

All generation calls go through a **Next.js API route proxy** (`app/api/asset/[...path]/route.ts`) to avoid browser CORS issues. PNG downloads go direct to the asset server via `absoluteAssetUrl()`.

**Functions:**

| Function | Endpoint | Returns |
|----------|----------|---------|
| `generateBackgroundTile(tileType)` | `POST /background_tile` | Absolute image URL |
| `generateTerrainFeature(params)` | `POST /terrain` | Absolute image URL (elevation overlay) |
| `generateLeaderSplash(params)` | `POST /leader` | `{ url, leaderId, seed }` |
| `generateLeaderProfile(params, leaderId)` | `POST /leader` | Absolute image URL |
| `generateStructure(params)` | `POST /structure` | Absolute image URL |
| `generateUnit(unitType, description)` | `POST /unit` | Absolute image URL |
| `listLeaders()` | `GET /leader` | Existing leader catalog |

### 5.4 `lib/assetMapping.ts` — Deterministic Parameter Mapping

No LLM is used for asset generation — the service uses enum-driven prompt assembly. This file provides:

- **`UNIT_TYPE_MAP`**: 7 game unit types → 4 API unit types (warrior/archer/scout/settler)
- **`CULTURE_PROFILES`**: 12 culture-specific visual profiles with materials, silhouettes, motifs, unit kits
- **`unitDescriptionFor(apiType, culture, leaderName)`**: Composes unit descriptions from culture profiles
- **`ELEVATION_TERRAINS`**: Which terrains get elevation overlays with params
- **`cityStructureFor(leaderName, category, culture)`**: Composes structure generation params
- **`STRUCTURE_CATEGORIES`**: 4 structure types (production, fortification, housing, sacred)
- **`ARCHETYPE_OPTIONS`** / **`CULTURE_OPTIONS`**: Dropdown enum values for the start screen

### 5.5 `lib/leaderMapping.ts` — Leader Parameter Table

Deterministic map from leader name → generation params (archetype, culture, timeOfDay, mood, physical description). Only 3 leaders have explicit definitions (Genghis Khan, Cleopatra, Mahatma Gandhi); others fall back to a generic medieval ruler.

### 5.6 Fallback Behavior

Every missing asset degrades gracefully:

| Missing Asset | Fallback |
|--------------|----------|
| Terrain sprite | Color fill from `TERRAIN_COLORS` |
| Elevation overlay | None (base tile shows alone) |
| Unit sprite | Colored circle with first-letter initial |
| Structure sprite | Built-in city/structure marker |
| Leader portrait | Colored circle with first-letter initial |

The `SquareMap` component tracks failed image loads in `failedHrefs` state and removes those `<image>` elements — the underlying color fill shows through.

---

## 6. Hex Map Rendering

### 6.1 Grid System

Despite the component name `SquareMap`, the game uses a **square grid** (not hexagonal). The module name `hex.ts` is retained for historical reasons.

- **Coordinates**: `q` (column/x) and `r` (row/y) — integer indices
- **Tile size**: 22px (`TILE_SIZE` / `HEX_SIZE`)
- **Distance**: Chebyshev distance — `max(|Δq|, |Δr|)`
- **Pixel conversion**: `x = q × size`, `y = r × size`

### 6.2 SVG Rendering Layers (in order)

Each layer is a `<g>` element with `pointerEvents="none"` to avoid blocking interaction. The clickable layer is the bottom-most `<rect>` per tile.

| # | Layer | SVG Elements | Description |
|---|-------|-------------|-------------|
| 1 | **Tile fills** | `<rect>` × N | Solid color from `TERRAIN_COLORS` with deterministic per-tile jitter (±7 luminance) |
| 2 | **Terrain sprites** | `<image>` × N | PNG tiles from asset service, `imageRendering: pixelated`, `onError` removes broken images |
| 3 | **Elevation overlays** | `<image>` × N | Relief sprites (hills, cliffs) layered over base tiles |
| 4 | **Rivers** | `<line>` × N | Diagonal blue lines (`#7fbde7`, 85% opacity) |
| 5 | **Feature glyphs** | `<text>` × N | Unicode glyphs for forest (♣), jungle (❦), marsh (≈), oasis (❂) |
| 6 | **Resource badges** | `<circle>` + `<text>` | Golden circles with resource glyphs (wheat 🌾, iron ⚒, horses 🐎, etc.) |
| 7 | **Improvement markers** | `<circle>` + `<text>` | Off-white circles with improvement glyphs (farm ≈, mine ⛏, road ═) |
| 8 | **Worked-tile dots** | `<circle>` × N | Yellow dots marking tiles worked by the selected city |
| 9 | **Grid lines** | `<rect>` × N | Thin dark strokes outlining each tile |
| 10 | **Fog overlay** | `<rect>` × N | Dark semi-transparent rects (`#050810`, 66% opacity) over unexplored tiles |
| 11 | **Human territory borders** | `<line>` per outer edge | Thick gold (`#d4a443`) strokes on outer edges of human-owned tiles |
| 12 | **Rival territory borders** | `<line>` per outer edge | Thinner civ-colored strokes on outer edges of AI-owned tiles |
| 13 | **Reachable range** | `<rect>` + border | Gold-tinted overlay + outline on tiles adjacent to selected unit |
| – | **Units** | `<g>` per unit | Clickable unit markers (colored circles with type glyph or sprite) |
| – | **Cities** | `<g>` per city | City name labels with population count |
| – | **Structures** | `<image>` per structure | Placed structure sprites (draggable from city drawer) |

### 6.3 Camera System

- **viewBox-based**: SVG `viewBox` attribute controls pan/zoom
- **Pan**: Pointer events → drag → `requestAnimationFrame`-synced viewBox translation
- **Zoom**: Mouse wheel → exponential factor (`exp(deltaY × 0.0022)`) anchored to cursor position
- **Recenter**: Resets camera to focus point (selected unit's city, or first human city, or first human unit)
- **Auto-focus**: Camera pans to `focusHex` when a unit is selected (if not already in view)
- **Bounds clamping**: Camera is clamped to map bounds with margins
- **Scale**: `1.5 - radius × 0.018`, clamped to `[0.6, 1.8]`

### 6.4 `lib/hex.ts` — Grid Utilities

| Export | Type | Purpose |
|--------|------|---------|
| `TILE_SIZE` / `HEX_SIZE` | `number` (22) | Tile pixel size |
| `hexToPixel(h, size?)` | Function | Coordinate → pixel center |
| `tileCorners(cx, cy, size?)` | Function | Pixel center → 4 corners (square) |
| `hexCorners` | Alias | Alias for `tileCorners` |
| `hexDistance(a, b)` | Function | Chebyshev distance |
| `tileKey(q, r)` | Function | `"q,r"` string key |
| `TERRAIN_COLORS` | Record | 13 terrain → hex color |
| `TERRAIN_STROKE` | Record | 13 terrain → border color |
| `CIV_COLORS` | `string[]` | 4 faction colors (gold, blue, red, purple) |
| `UNIT_GLYPH` | Record | 7 unit types → Unicode glyph |
| `UNIT_LABEL` | Record | 7 unit types → display name |
| `IMPROVEMENT_GLYPH` / `LABEL` | Record | 3 improvements → glyph/name |
| `RESOURCE_GLYPH` / `LABEL` | Record | 9 resources → glyph/name |
| `FEATURE_GLYPH` / `LABEL` | Record | 4 features → glyph/name |

### 6.5 `components/mapTypes.ts`

TypeScript interface for `SquareMap` props:

```typescript
interface StrategyMapProps {
  state: GameStateDTO;
  selectedUnitId: number | null;
  reachable: Set<string>;
  highlightedTileKey?: string | null;
  focusHex?: Hex | null;
  humanCivId?: number | null;
  visibleTiles: Set<string>;
  assets?: AssetManifest | null;
  placedStructureAssets?: Record<string, string>;
  onTileClick?: (q: number, r: number) => void;
  onTileHover?: (q: number, r: number) => void;
  onStructureDrop?: (cityId: number, category: string, q: number, r: number) => void;
  onUnitClick?: (unit: UnitDTO) => void;
}
```

### 6.6 Performance Considerations

- **`useMemo`** for tile→pixel mapping, unit/city lookups, territory maps
- **`requestAnimationFrame`** for pan rendering (avoids React state updates during drag)
- **Ref-based camera writes** during drag (bypasses React render cycle via `applyViewBox()`)
- **`Set<string>`** for fast tile lookups (visible, reachable, owned)
- **`failedHrefs` tracking** — prevents repeated load attempts for broken images
- **`pointerEvents="none"`** on all decorative `<g>` groups (only interactive elements receive clicks)
- **No WebGL** — all rendering is DOM/SVG, which scales to ~2,500 tiles (radius 28) before noticeable slowdown

---

## 7. Styling

### 7.1 Architecture

- **Single global stylesheet**: `app/globals.css` (~1250 lines)
- **No CSS modules** — all classes are global (BEM-like naming convention)
- **No CSS-in-JS** — all styling is via plain CSS classes
- **Inline styles** used sparingly for dynamic values (colors, backgrounds, progress bars)

### 7.2 Design System

**Color palette** (OKLCH-based CSS custom properties):

| Token | Purpose |
|-------|---------|
| `--bg` | Dark blue background (`oklch(0.13 0.02 245)`) |
| `--bg-deep` | Deeper background |
| `--panel` | Panel background (94% opacity) |
| `--panel-soft` / `--panel-strong` | Panel variants |
| `--line` / `--line-strong` | Border colors (gold-tinted) |
| `--ink` / `--ink-soft` / `--ink-muted` | Text colors (warm off-white) |
| `--accent` / `--accent-strong` / `--accent-dim` | Gold accent |
| `--danger` | Red (warnings) |
| `--success` | Green (positive) |

**Typography**:
- Display: Baskerville / Palatino / Book Antiqua (serif)
- Body: Avenir Next / Segoe UI (sans-serif)

**Spacing scale**: 4px → 8px → 12px → 16px → 24px → 32px → 48px → 64px

**Border radius**: 10px (sm), 16px (md), 24px (lg)

### 7.3 Responsive Design

The application is **not fully responsive** — it targets desktop screens. Key layout:

- `war-room__layout`: CSS Grid with left rail (auto), map (1fr), right rail (auto)
- Map container fills available space via `ResizeObserver`
- Start screen uses `min(720px, 100%)` for the panel width
- Min-width of 320px is enforced via ResizeObserver

### 7.4 Background Effects

- Radial gradients (gold + blue tint)
- CSS grid overlay lines for a parchment/strategic feel
- `mix-blend-mode: screen` overlay

---

## 8. Additional Libraries

### 8.1 `lib/turnEvents.ts` — Turn Diff Engine

Computes the delta between two game states to produce `TurnEvent[]`:

| Event Kind | Detection |
|-----------|-----------|
| `city_founded` | New city IDs not in previous state |
| `tech_completed` | New techs in civ's `known_techs` |
| `unit_lost` | Human unit IDs missing from new state |
| `civ_met` | New entries in `known_civ_ids` |
| `stance_changed` | Different `stance` for same `other_civ_id` |
| `message_received` | New messages in inbox not seen in previous inbox |

Events are accumulated in `eventLog` (capped at 80) and briefly shown as `bannerEvents` (auto-dismisses after 4.5s).

### 8.2 `lib/useAudio.ts` — Audio Hook

Manages the game's audio lifecycle:

- **Phase machine**: `silent → intro → ambient`
- **Music**: 3 tracks (ambient, bards-tale, medieval-battle) — randomized, crossfaded
- **Volume ramping**: Smooth transitions via `requestAnimationFrame` + linear interpolation
- **Narration**: Generated TTS audio from backend (`POST /audio/intro`) played over intro music
- **Mute**: Persisted in `localStorage` key `inf3600:audioMuted`
- **Cleanup**: Pauses on unmount (HMR-safe), revokes object URLs

### 8.3 API Proxy (`app/api/asset/[...path]/route.ts`)

Server-to-server proxy that:

- Forwards POST/PUT/GET requests to the asset server
- Strips hop-by-hop headers (host, connection, content-length, accept-encoding, content-encoding, transfer-encoding)
- Returns unmodified response body + status
- Returns 503 if `NEXT_PUBLIC_ASSET_API_URL` is not configured
- Returns 502 on upstream fetch failures
- **Only used for JSON API calls** — PNG downloads go direct to avoid proxying high-volume image data

---

## 9. Tech Tree (Client-Side Mirror)

The frontend maintains a mirror of the backend tech tree for UI display:

- **20 technologies** across 4 tiers
- **7 buildable units** with tech prerequisites
- Tech costs, prerequisites, emoji icons, and names are all duplicated in `page.tsx` (lines ~80–100)
- The `availableTechs` memo filters techs the player can currently research

**Buildable Units**:

| Unit | Cost | Requires |
|------|------|----------|
| Warrior | 10 prod | — |
| Scout | 8 prod | — |
| Settler | 15 prod | — |
| Worker | 10 prod | — |
| Archer | 15 prod | Archery |
| Horseman | 22 prod | Horseback Riding |
| Swordsman | 30 prod | Iron Working |

---

## 10. Known Limitations

### 10.1 Monolithic `page.tsx` (~2180 lines)

The entire application lives in a single component file. This creates:
- **Poor maintainability** — all UI logic, state, event handlers, and JSX in one place
- **Hard to test** — no isolated components to unit test
- **Difficult onboarding** — new developers must understand the whole file before making changes

**Recommended refactor** (not yet done):
- Extract start screen → `components/StartScreen.tsx`
- Extract intro screen → `components/IntroScreen.tsx`
- Extract loading screen → `components/LoadingScreen.tsx`
- Extract war room layout → `components/WarRoom.tsx`
- Extract each panel (Research, Cities, Standings, Selection) → individual components
- Extract diplomacy audience → `components/DiplomacyAudience.tsx`
- Extract city drawer → `components/CityDrawer.tsx`
- Extract top bar → `components/TopBar.tsx`
- Extract chronicle → `components/Chronicle.tsx`
- Lift shared state into a context or a custom hook (`useGameState`)

### 10.2 No Test Coverage

There are **zero tests** for the frontend. The project has:
- No Jest/Vitest configuration
- No React Testing Library setup
- No Playwright/Cypress E2E tests
- TypeScript `tsc --noEmit` is the only automated check

### 10.3 TypeScript Weak Spots

- Some event handlers use `any` or implicit types (especially drag-and-drop)
- The `canAttackOwner` function accesses `state.stances` without null checking `state` in some call paths
- `UNIT_MAX_HEALTH` is manually kept in sync with `backend/app/engine/models.py` — no shared type package

### 10.4 No Responsive Design

The UI targets desktop (≥1280px wide). Mobile/tablet layouts are not implemented. The map would be difficult to use on touch screens.

### 10.5 Asset Generation is Synchronous During Load

All asset generation happens during `loadGame()`, blocking the loading screen. If the asset server is slow or has many assets to generate (large map + many civs), the loading screen can last 30+ seconds. There's no incremental/streaming asset loading.

### 10.6 No Routing

The entire app is a single page with conditional rendering. There are no Next.js routes or pages — the URL never changes. This means:
- No deep linking to specific game states
- No browser back/forward navigation
- Page refresh restarts the game

### 10.7 State is Not Serializable/Persisted

Game state exists only in React component memory. A browser refresh loses the game. There's no `localStorage` persistence of game state (only audio mute preference is persisted).

### 10.8 CSS Organization

The global stylesheet (`globals.css`, ~1250 lines) is a single file with no partitioning. Class names follow a loose BEM convention but there's no enforced naming standard.

---

## 11. Development Workflow

### 11.1 Adding a New Feature

1. Read `page.tsx` to understand the current structure
2. Identify which logical section your feature touches (start screen, war room, diplomacy, etc.)
3. Add state variables to the `useState` block at the top of `HomePage`
4. Add API methods to `lib/api.ts` if needed
5. Add UI in the appropriate JSX branch
6. Run `npm run typecheck` to verify TypeScript
7. Run `npm run build` to verify production build

### 11.2 Adding a New Asset Type

1. Add generation function to `lib/assetApi.ts`
2. Add mapping logic to `lib/assetMapping.ts` if needed
3. Add resolution phase to `lib/assetManifest.ts` → `resolveManifest()`
4. Update `AssetManifest` interface with new URL records
5. Add rendering layer to `SquareMap.tsx`
6. Add fallback behavior (colors/glyphs)

### 11.3 Debugging

- **Backend API errors**: Check the Network tab — all API calls go through `api.*` methods which throw descriptive errors
- **Asset loading**: Check browser console for `[assetManifest]` prefixed logs
- **Map rendering**: Inspect the SVG element — each rendering layer is a `<g>` group
- **Type errors**: Run `npm run typecheck`

---

## 12. Quick Reference

| What | Where |
|------|-------|
| Game entry point | `app/page.tsx` — `HomePage` component |
| All API calls | `lib/api.ts` — `api.*` methods |
| Asset generation | `lib/assetManifest.ts` — `resolveManifest()` |
| Asset service client | `lib/assetApi.ts` |
| Game→asset mappings | `lib/assetMapping.ts`, `lib/leaderMapping.ts` |
| Map rendering | `components/SquareMap.tsx` |
| Grid math & colors | `lib/hex.ts` |
| Turn event diffing | `lib/turnEvents.ts` |
| Audio system | `lib/useAudio.ts` |
| Styles | `app/globals.css` |
| Map props interface | `components/mapTypes.ts` |
| Asset proxy route | `app/api/asset/[...path]/route.ts` |
| Layout & metadata | `app/layout.tsx` |
