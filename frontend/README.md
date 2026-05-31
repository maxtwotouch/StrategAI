# StrategAI — Frontend

Next.js 15 + React 19 UI with an SVG hex map and generative asset integration.

## Quick Start

```bash
cd frontend
npm install
cp .env.example .env.local   # set NEXT_PUBLIC_ASSET_API_URL if using asset server
npm run dev
```

Runs at `http://localhost:3000`. Without `NEXT_PUBLIC_ASSET_API_URL`, the game renders with built-in colors, glyphs, and letter-initial portraits — fully playable.

## What It Does

- **SVG hex map** — drag/zoom, fog of war, unit/city rendering, improvement overlays
- **Asset integration** — generative pixel-art assets from the asset server with graceful fallback (colors → glyphs → initials)
- **Diplomacy UI** — ribbon (leader portraits), full-screen diplomatic audience with free-form chat
- **City management** — production queue, gold-purchased structure placement, research panel, tile worked assignment
- **Audio** — ambient music, battle tracks, TTS intro narration
- **Turn system** — human actions → end turn → AI turn resolution → chronicle of events

## Documentation

| Document | Contents |
|----------|----------|
| [`docs/FRONTEND_ARCHITECTURE.md`](docs/FRONTEND_ARCHITECTURE.md) | Component tree, state management, Next.js structure |
| [`docs/UI_GUIDE.md`](docs/UI_GUIDE.md) | Panel lifecycle, map rendering, diplomatic audience, audio |
| [`../docs/ASSET_INTEGRATION.md`](../docs/ASSET_INTEGRATION.md) | Asset service contract, manifest resolution, fallback behavior |

## Testing

```bash
npx tsc --noEmit   # type check
npm run build       # production build verification
```

## Conventions

- **State management** — React `useState` + `useRef` + `useMemo`. No external state library.
- **API calls** — All go through `api.*` methods in `lib/api.ts`.
- **Asset fallback** — Every missing generative asset degrades gracefully to built-in colors, glyphs, or initials.
- **Single stylesheet** — `app/globals.css` (~1250 lines) with design tokens and all UI surfaces.

## Architecture

```
app/page.tsx          ← single client page, owns all game state
components/
  SquareMap.tsx       ← SVG hex map renderer (~920 lines)
lib/
  api.ts              ← backend game client + DTOs
  assetApi.ts         ← asset service client
  assetManifest.ts    ← manifest resolver (POST → cache → fallback)
  assetMapping.ts     ← deterministic game→asset param maps
  hex.ts              ← grid math, terrain/unit/glyph tables
  leaderMapping.ts    ← leader→generation params
  turnEvents.ts       ← prev/next state diff → TurnEvent[]
  useAudio.ts         ← audio hook (music, narration)
```

## Deployment

See **[`../DEPLOYMENT.md`](../DEPLOYMENT.md)** for production deployment — the frontend is part of the **Game Server** tier (static Next.js export, deployable anywhere).
