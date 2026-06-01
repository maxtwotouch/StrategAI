# Development Guide

> **Last Validated: 2026-05-31**

How to get the game running on your machine, what env vars matter, how to test
your changes, and where the moving parts live.

For game mechanics see [GAMEPLAY.md](GAMEPLAY.md); for UI structure see
[frontend/docs/UI_GUIDE.md](frontend/docs/UI_GUIDE.md); for asset service integration see
`frontend/lib/assetManifest.ts` and `frontend/lib/assetApi.ts`. For the full asset integration contract, see [`docs/ASSET_INTEGRATION.md`](docs/ASSET_INTEGRATION.md).

> 📖 **Bottom-up documentation**: This is a Layer 2 synthesis document. For authoritative
> details on specific subsystems, follow links down to:
> - **[Backend docs](backend/docs/)** — API reference, configuration
> - **[Frontend docs](frontend/docs/)** — Architecture, UI guide
> - **[Asset server docs](assetserver/docs/INDEX.md)** — Pipeline, architecture, guides
> - **[Training docs](dataset-gen-train/docs/)** — Model card, dataset card, experiments

---

## 1. Prerequisites

| Tool | Version |
|---|---|
| Python | 3.11+ |
| Node.js | 20+ |
| npm | bundled with Node |

The asset service is an **external dependency** — you don't run it locally. It
lives at the URL in `NEXT_PUBLIC_ASSET_API_URL`. With that variable unset, the
game is fully playable with built-in colors and glyphs.

> ⚠️ **Port collision note**: The asset server's default port in `assetserver/config.yaml`
> and `assetserver/src/config.py` is **8000** — the same as the backend. If you run the
> asset server locally, you **must** override it to **8001** (the documented convention)
> with `--port 8001` or the `SERVER__PORT` env var to avoid a collision.

---

## 2. Repository Layout

```
StrategAI/
├── README.md                  this guide's entry point
├── .env                       OPENAI_API_KEY etc. (gitignored)
├── DEVELOPMENT.md             (you are here)
├── GAMEPLAY.md                game mechanics reference
├── docs/                      architecture and report materials
│   ├── ARCHITECTURE.md        backend engine layers + LLM goal source
│   └── report/                IEEE report and presentation materials
├── backend/docs/              backend API reference and config
├── frontend/docs/             frontend architecture and UI guide
├── backend/
│   ├── app/
│   │   ├── api/               FastAPI app + Pydantic schemas
│   │   │   ├── routers/       /games, /turns, /actions
│   │   │   ├── schemas.py     all DTOs
│   │   │   ├── store.py       in-memory game store
│   │   │   └── game_factory.py  civ roster + map gen wiring
│   │   └── engine/            pure-functional rules layer
│   │       ├── models.py            frozen dataclasses + UNIT_STATS etc.
│   │       ├── intents.py           dataclass intent types used by AI
│   │       ├── operations.py        Intent → Goal lowering
│   │       ├── executor.py          Goal → validated Action runner
│   │       ├── human_source.py      human player's action-source adapter
│   │       ├── openai_goals.py      LLM-backed goal source for AI civs
│   │       ├── turn_resolver.py     AI turn orchestration
│   │       ├── playthrough.py       end-to-end runner used in tests
│   │       ├── directives.py        QueueProduction / CancelProduction /
│   │       │                        PurchaseStructure / StartResearch
│   │       ├── production.py        city tick / yields
│   │       ├── economy.py           gold per turn, no-upkeep rules
│   │       ├── buildings.py         building catalog + bonuses
│   │       ├── city_founding.py     settler founding rules
│   │       ├── city_names.py        deterministic civ-specific city names
│   │       ├── starting_positions.py civ placement on generated maps
│   │       ├── borders.py           culture-driven border growth
│   │       ├── fog_of_war.py        per-civ visible-tile computation
│   │       ├── combat.py            attack resolution + terrain mods
│   │       ├── movement.py          move validation + healing
│   │       ├── diplomacy.py         stances, messages, truces, met_civs
│   │       ├── research.py          TECHS dict + UNIT_TECH_REQUIREMENTS
│   │       ├── improvements.py      farm/mine/road work orders
│   │       ├── victory.py           score victory formula
│   │       ├── serialize.py         GameState → DTO
│   │       ├── map_generator.py     procedural map generator
│   │       ├── terrain.py           passability + biome rules
│   │       └── hex.py               coordinate math
│   ├── scripts/
│   │   └── run_playthrough.py       headless game runner
│   └── tests/                       pytest suite
├── assetserver/
│   └── scripts/
│       └── smoke_test_endpoints.sh  smoke test for the asset service
└── frontend/
    ├── app/
    │   ├── page.tsx           single client page, owns all state
    │   ├── layout.tsx
    │   └── globals.css        design tokens + every UI surface
    ├── components/
    │   ├── SquareMap.tsx      SVG renderer for the map
    │   └── mapTypes.ts
    ├── lib/
    │   ├── api.ts             game backend client
    │   ├── hex.ts             coordinate math + glyph tables
    │   ├── turnEvents.ts      diff-driven event log
    │   ├── assetApi.ts        asset service client
    │   ├── assetManifest.ts   per-game asset resolver
    │   ├── assetMapping.ts    game taxonomy → asset enums
    │   ├── leaderMapping.ts   deterministic leader profiles
    │   └── useAudio.ts        intro/ambient music + mute toggle
    ├── public/
    │   └── audio/             intro.mp3, ambient.mp3 (drop in here)
    ├── .env.example
    └── .env.local             your own dev env (gitignored)
```

---

## 3. Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Run the dev server

```bash
# from backend/ with the venv active:
uvicorn app.main:app --reload --port 8000
```

The frontend points at `localhost:8000` by default.

### Environment

Most of the backend doesn't need env vars. The exception is the LLM-backed
AI civs:

```bash
# in the repo root .env file (gitignored):
OPENAI_API_KEY=sk-…
```

Without an OpenAI key, the AI civs fall back to a deterministic stub goal
source — useful for offline development. See `backend/app/engine/openai_goals.py`
for the swap.

### Headless playthrough

For end-to-end testing without the frontend:

```bash
cd backend
.venv/bin/python scripts/run_playthrough.py --seed 42 --turns 20
```

---

## 4. Frontend Setup

```bash
cd frontend
npm install
```

### Env file

Create `frontend/.env.local`:

```bash
# game backend
NEXT_PUBLIC_API_URL=http://localhost:8000

# asset service (optional — leave blank for color/glyph fallback)
NEXT_PUBLIC_ASSET_API_URL=https://localhost:8001
```

**Restart `next dev` after editing this file** — Next.js inlines
`NEXT_PUBLIC_*` vars at server start.

### Run the dev server

```bash
npm run dev
```

Open <http://localhost:3000>. Hot reload picks up code edits; env changes
require a restart.

### Audio assets (optional)

Drop MP3s into `frontend/public/audio/`:

- `ambient.mp3` — first track, starts on Begin Campaign.
- `bards-tale.mp3` — playlist track.
- `medieval-battle.mp3` — playlist track.

The player starts the playlist on Begin Campaign, lowers volume when the intro
is dismissed, and advances to the next track whenever the current one ends.
Current bundled music is from OpenGameArt. Attribution and license details live in
`frontend/public/audio/ATTRIBUTION.md`.

Missing files don't break anything; the audio hook silently catches the load
failure. Volume and crossfade tuning lives at the top of `frontend/lib/useAudio.ts`.

---

## 5. Testing

### Backend

```bash
cd backend
.venv/bin/python -m pytest                  # all tests
.venv/bin/python -m pytest -q tests/test_directives.py  # one file
.venv/bin/python -m pytest -q -k city       # filter by keyword
```

Tests use `pytest.mark.unit` for clarity. The suite covers the engine
end-to-end including a slow playthrough test (`test_playthrough.py`) — there's
one known intermittent failure there (pre-existing, unrelated to recent
changes) which doesn't block other work.

### Frontend

```bash
cd frontend
npm run typecheck      # tsc --noEmit
npm run build          # production build (catches lint + SSR issues)
```

There is no Jest/Vitest suite yet. Logic-heavy modules (`assetManifest.ts`,
`leaderMapping.ts`, `turnEvents.ts`) are good candidates for future unit tests.

### Asset service smoke test

```bash
bash assetserver/scripts/smoke_test_endpoints.sh
```

> **Note**: The smoke test lives in `assetserver/scripts/`, not at the repo root.
> There is no root-level `scripts/` directory — scripts are per-subproject.

---

## 6. Common Workflows

### Adding a new game action

1. Pydantic request schema in `backend/app/api/schemas.py`.
2. Endpoint in the appropriate `routers/*.py`.
3. Engine function (pure, immutable) in `backend/app/engine/`.
4. Tests in `backend/tests/`.
5. Frontend client method in `frontend/lib/api.ts`.
6. UI affordance in `frontend/app/page.tsx`.

### Adding a new building

1. Append to `BuildingType` enum in `backend/app/engine/models.py`.
2. Add a `BuildingDef` in `backend/app/engine/buildings.py` with bonuses +
   prereq.
3. If it changes a tile-yield rule, update `_city_tile_yields` in
   `backend/app/engine/production.py`.
4. Tests in `backend/tests/test_buildings.py` (or
   `test_directives.py` for queue interactions).

### Adding a new asset-API family

See `frontend/lib/assetManifest.ts` and `frontend/lib/assetApi.ts` for the
current implementation. Roughly: extend `AssetManifest`, add a `generate*` in
`assetApi.ts`, add a `mapLimit` batch in `assetManifest.ts`, consume the
resolved URL where it surfaces in the UI. See [`docs/ASSET_INTEGRATION.md`](docs/ASSET_INTEGRATION.md) for the full asset service contract.

### Tweaking AI persona

Persona prompts live in `backend/app/api/game_factory.py:_AI_ROSTER`. Each
is appended to `BASE_SYSTEM_PROMPT` in `backend/app/engine/openai_goals.py`.

---

## 7. Branch Conventions

Active feature branches as of this writing:

- `main` — shipped baseline.
- `feature/diplomacy-drawer` — original diplomacy drawer experiment
  (superseded by the audience overlay).
- `feature/asset-integration` — current branch; covers the asset service
  integration, intro screen, sovereign portrait, city drawer, audio plumbing,
  cancel-build + purchase-structure mechanics.

Naming: `feature/{kebab-name}` for new features, `fix/{kebab-name}` for
focused bug fixes.

---

## 8. CI & Quality

This repo does not currently run automated CI. Manual checks before opening
a PR:

```bash
# backend
cd backend && .venv/bin/python -m pytest -q

# frontend
cd ../frontend && npm run typecheck && npm run build
```

---

## 9. Useful Console + Shell Snippets

### Browser console — env + state inspection

The asset manifest is no longer persisted (see
`frontend/lib/assetManifest.ts` — manifests are resolved per-game and not
cached in localStorage), so cache clearing is rarely needed. Useful checks:

```js
// see what env was inlined
console.log("ASSET URL:", process.env.NEXT_PUBLIC_ASSET_API_URL);

// confirm no stale manifests linger from an earlier release
Object.keys(localStorage).filter(k => k.startsWith("inf3600:"));
```

### Shell — list which dev processes are running

```bash
pgrep -af next                                    # any next dev?
lsof -nP -iTCP:3000 -sTCP:LISTEN                  # frontend listener
lsof -nP -iTCP:8000 -sTCP:LISTEN                  # backend listener
```

### Shell — wipe the backend's in-memory store

The backend's store is in-memory; restarting `uvicorn` resets all games.
Game IDs restart at 1 each launch.

---

## 10. Where to Look First

| If you want to... | Start here |
|---|---|
| Add or change game mechanics | `backend/app/engine/` |
| Change an HTTP route | `backend/app/api/routers/` |
| Tweak the UI layout | `frontend/app/page.tsx` + `globals.css` |
| Add a new tile/unit/leader rendering | `frontend/components/SquareMap.tsx` |
| Integrate a new asset family | `frontend/lib/assetManifest.ts` |
| Adjust AI behavior | `backend/app/engine/openai_goals.py` + `game_factory.py` |
| Fix the cancel/purchase mechanics | `backend/app/engine/directives.py` |
