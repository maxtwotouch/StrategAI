# StrategAI

A Civilization-style strategy game where rival civs are driven by LLM-backed
goals. Deterministic Python game engine, FastAPI backend, Next.js + SVG
frontend, and an external generative pixel-art service for tile / unit /
structure / leader art.

> **Need to read just one thing?** Start with **[docs/GAMEPLAY.md](docs/GAMEPLAY.md)**
> for the game itself, or **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** to get
> it running.

---

## Documentation

| Guide | What's in it |
|---|---|
| [docs/GAMEPLAY.md](docs/GAMEPLAY.md) | Every mechanic: setup, civs, terrain, units (stats + costs), cities (yields + growth), production queue, buildings + gold-purchased structures, the 21-tech tree, workers/improvements, combat, diplomacy, turn flow, victory. |
| [docs/UI_GUIDE.md](docs/UI_GUIDE.md) | Frontend lifecycle (Start → Load → Intro → War Room), layout breakdown of every panel and overlay (city drawer, diplomatic audience, sovereign portrait), map rendering layers, audio plumbing. |
| [docs/ASSET_INTEGRATION.md](docs/ASSET_INTEGRATION.md) | Contract with the asset service, taxonomy mapping, manifest resolver, cache strategy, graceful fallback, smoke test. |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Prerequisites, backend + frontend setup, env vars, tests, common workflows, where to hook new things in. |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Original backend architecture write-up (engine layers, deterministic state, LLM goal source). |
| [GAME_BACKLOG.md](GAME_BACKLOG.md) | Outstanding game-design work. |
| [TIER1_PLAN.md](TIER1_PLAN.md) | Tier-1 mechanics implementation record (shipped). |
| [planning.md](planning.md) | Original concept doc. |

---

## Quick Start

```bash
# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.api.main:app --reload --port 8000

# frontend (in another terminal)
cd frontend
npm install
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
# (optional) NEXT_PUBLIC_ASSET_API_URL=https://… to get generated art
npm run dev

# open the game
open http://localhost:3000
```

The game is fully playable without the asset service — it falls back to flat
colors + glyph rendering, and the start-screen leader inputs work as game
metadata even when no art can be fetched.

---

## Repository Layout

```
INF-3600/
├── README.md                this file
├── docs/                    ARCHITECTURE · GAMEPLAY · UI_GUIDE · ASSET_INTEGRATION · DEVELOPMENT
├── scripts/
│   └── asset_api_smoke.py   stdlib smoke test for the asset service
├── backend/
│   ├── app/
│   │   ├── api/             FastAPI routes + Pydantic schemas
│   │   └── engine/          pure, immutable rules layer
│   ├── scripts/             headless playthrough runner
│   └── tests/               pytest suite
└── frontend/
    ├── app/                 Next.js App Router (page.tsx, layout.tsx, globals.css)
    ├── components/          SquareMap and its types
    ├── lib/                 game + asset clients, manifest resolver, audio hook
    ├── public/audio/        drop intro.mp3 / ambient.mp3 here for music
    └── .env.example         env shape reference
```

---

## Stack

| Layer | Tech |
|---|---|
| Game engine | Python 3.11+, frozen dataclasses, pure functional state transitions |
| Backend HTTP | FastAPI, Pydantic, in-memory store, OpenAI tool-use for AI civs |
| Frontend | Next.js 15 (App Router), React 19, TypeScript strict, SVG-rendered map |
| Generative art | External Medieval Pixel Art service (Flux2 Klein via ComfyUI) |
| Audio | `HTMLAudioElement` with a small `useAudio` hook (intro swell + ambient bed + mute toggle) |

---

## Testing

```bash
# backend (pytest)
cd backend && .venv/bin/python -m pytest

# frontend (tsc + production build)
cd frontend && npm run typecheck && npm run build

# external asset service smoke (optional, hits the live host)
python3 scripts/asset_api_smoke.py --fast
```

See [docs/DEVELOPMENT.md §5](docs/DEVELOPMENT.md#5-testing) for the full
testing playbook.

---

## Status & Known Issues

- **Asset service generation** — the `/leader` pipeline works end-to-end;
  five other families (`/background_tile`, `/unit`, `/structure`, `/terrain`,
  `/object`) currently return HTTP 400 with a UTF-32-BE codec error.
  Documented in [docs/ASSET_INTEGRATION.md §10](docs/ASSET_INTEGRATION.md#10-known-issues-with-the-live-asset-service).
  The frontend handles the failures gracefully — game stays playable, map
  renders with color fills until the server-side fix lands.
- **Playthrough test flakiness** — `tests/test_playthrough.py::test_playthrough_with_generated_map`
  intermittently fails with a city-capture move error. Pre-existing and
  unrelated to recent work; tracked in the backlog.
- **No automated CI** — manual checks before opening a PR (see
  [docs/DEVELOPMENT.md §8](docs/DEVELOPMENT.md#8-ci--quality)).

---

## License

TBD.
