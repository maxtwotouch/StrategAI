# Frontend — AI Agent System

This subproject contains the Next.js game UI, SVG hex map rendering, and asset integration for StrategAI.

## Architecture

Single-page React app ("use client") with session lifecycle:
```
Start → Loading → Intro (splash screen) → War Room (main game)
```

## Directory Structure

| Path | Purpose |
|------|---------|
| `app/page.tsx` | Main game page (~1960 lines) — setup, intro, war room, all panels/modals |
| `components/SquareMap.tsx` | SVG hex map renderer (~920 lines) — camera, layers, fog, borders |
| `components/mapTypes.ts` | TypeScript interfaces for map props |
| `lib/api.ts` | Backend API client — 14 methods matching backend endpoints |
| `lib/assetManifest.ts` | Asset manifest resolution — terrain/unit/leader mapping, caching, fallback |
| `app/layout.tsx` | Root layout |
| `next.config.mjs` | Next.js config |

## War Room Layout

- **Top bar**: Empire badge, metrics (science/gold/culture/score/cities), audio toggle, map mode, turn indicator, End Turn button
- **Left rail**: Minimap, Selection panel (unit details, found city, worker improvements)
- **Center**: `<SquareMap>` with terrain readout, banner events
- **Right rail**: Research panel, Cities panel, Other Leaders panel, Standings panel
- **Bottom**: Chronicle/event log with inbox badge
- **Modals/Drawers**: City naming, Diplomacy audience (full-screen overlay), City drawer, Sovereign portrait

## SquareMap Rendering Layers (in order)

1. Tile color fills (deterministic jitter)
2. Terrain sprites (from asset service, with `onError` fallback)
3. Elevation overlays (hills, cliffs)
4. Rivers (diagonal blue lines)
5. Feature glyphs (forest, jungle)
6. Resource badges (golden circles with symbols)
7. Improvement markers (farm, mine, road)
8. Worked-tile dots (yellow dots)
9. Grid lines
10. Fog overlay (dark semi-transparent rects)
11. Human territory borders (gold, thick)
12. Rival territory borders (civ-colored)
13. Reachable range highlights

## Asset Integration

**Location**: `lib/assetManifest.ts`

- **Config**: `NEXT_PUBLIC_ASSET_API_URL` in `.env.local`
- **Terrain mapping**: 13 game terrains → 5 service tile types (water, grass, stone, sand, dirt)
- **Unit mapping**: 7 game units → 4 API unit types (warrior, archer, scout, settler)
- **Leader resolution**: archetype + culture → style mapping
- **Caching**: localStorage key `inf3600:assetManifest:{hostTag}:{gameId}`
- **Fallback**: Every missing asset degrades to built-in colors/glyphs/initials
- **Leader pool fallback**: Ranks by archetype+culture match, rotates by civ ID

## API Client

**Location**: `lib/api.ts`

14 methods matching backend endpoints:
- `createGame()`, `getGame()`, `endTurn()`, `resolveTurn()`
- `move()`, `attack()`, `foundCity()`, `research()`
- `build()`, `cancelBuild()`, `purchaseStructure()`, `improve()`, `sendMessage()`

**DTOs**: `TileDTO`, `UnitDTO`, `CityDTO`, `CivDTO`, `GameStateDTO`, etc. — must match backend `schemas.py`

## Tech Tree (Client-Side Mirror)

20 techs across 4 tiers, mirrored from backend. 7 buildable units with tech prerequisites.

## Conventions

- **State management**: React `useState` + `useRef` + `useMemo` — no external state library
- **API calls**: All go through `api.*` methods in `lib/api.ts`
- **TypeScript**: Strict mode, DTOs mirror backend schemas
- **Styling**: Inline styles + CSS modules
- **Camera**: viewBox-based pan/zoom with momentum, clamped bounds

## Agent Roster

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| **Orchestrator** | Frontend feature coordination | Multi-step frontend tasks, UI changes |
| **UI Engineer** | React components, state management, panels | Component logic, panel layout, modals |

## Testing

```bash
npx tsc --noEmit
npm run build
```

## Quick Start

```bash
npm install
npm run dev
```

## Cross-Project Context

- **Backend provides**: REST API at `http://localhost:8000`, DTOs in `backend/app/api/schemas.py`
- **Asset Server provides**: Generative assets via `NEXT_PUBLIC_ASSET_API_URL`, endpoints in `assetserver/src/main.py`
- **Root orchestrator**: For cross-project tasks, delegate to root `.github/agents/orchestrator.agent.md`
