# StrategAI

A Civilization-style strategy game where rival civs are driven by LLM-backed
goals, illustrated with on-demand generative pixel art. **Umbrella repository**
collecting four subprojects that together implement the full system: a Python
game engine + FastAPI backend, a Next.js + SVG frontend, a self-hosted
generative pixel-art microservice, and the LoRA training pipeline that
produced the model that microservice runs.

> **Just want to play the game?** Read [docs/GAMEPLAY.md](docs/GAMEPLAY.md).
> **Just want to run it locally?** Follow [Quick Start](#quick-start) below.
> **Writing a project report?** Start with [docs/REPORT_HANDOFF.md](docs/REPORT_HANDOFF.md).

---

## Subprojects

| Subproject | Path | Role | Stack |
|---|---|---|---|
| **Game backend** | [`backend/`](backend/) | Deterministic engine, LLM-driven AI civs, REST API the frontend talks to. | Python 3.11+, FastAPI, OpenAI tool-use API |
| **Game frontend** | [`frontend/`](frontend/) | The playable UI — map, war room, diplomacy, city drawer, audio. | Next.js 15, React 19, TypeScript, SVG |
| **Asset server** | [`assetserver/`](assetserver/) | Generative pixel-art microservice. Six asset families (tiles / units / structures / terrain / leaders / objects) served over HTTP. | Python 3.10+, FastAPI, ComfyUI, FLUX2 Klein 4B Distilled |
| **Dataset & LoRA training** | [`dataset-gen-train/`](dataset-gen-train/) | Pipeline that built the curated dataset and trained the LoRA the asset server style-adapts with. | Python 3.10+, Ostris AI Toolkit, ComfyUI |
| **Docs** | [`docs/`](docs/) | Architecture, gameplay rules, UI guide, asset-integration contract, development guide, report handoff. | Markdown |

Each subproject has its own `README.md` with deeper setup notes and (where
applicable) its own `docs/` directory. This top-level README is the umbrella —
pick a subproject above for the detail.

---

## What runs together vs. independently

```
                            ┌──────────────────────────────────────┐
   Player ───►  Frontend ───┤  Game backend (FastAPI :8000)        │
                            └──────────┬───────────────────────────┘
                                       │  HTTP (proxied via Next.js)
                                       ▼
                            ┌──────────────────────────────────────┐
                            │  Asset server (FastAPI, own venv)    │
                            │      │                               │
                            │      ▼                               │
                            │  ComfyUI nodes + FLUX2 Klein 4B      │
                            │  + LoRA produced by dataset/training │
                            └──────────────────────────────────────┘
```

- **The game is fully playable without the asset server.** The frontend
  detects a missing `NEXT_PUBLIC_ASSET_API_URL`, skips the asset resolver,
  and falls back to flat-colour tiles + glyph rendering + letter-initial
  portraits.
- **The asset server runs standalone too.** It has a placeholder mode for
  GPU-free testing and a real-ComfyUI mode for live generation.
- **The training pipeline is offline.** Its output is the `.safetensors`
  LoRA weights the asset server loads at start-up.

---

## Quick Start

The minimum is the game backend + frontend (no GPU, no asset server).

```bash
# 1. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.api.main:app --reload --port 8000

# 2. Frontend (in another terminal)
cd frontend
npm install
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
# (optional, to get generated art)
# echo 'NEXT_PUBLIC_ASSET_API_URL=https://your-asset-host' >> .env.local
npm run dev

# 3. Play
open http://localhost:3000
```

Full setup with all four subprojects (asset server + LoRA training) lives in
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) and in each subproject's own
README.

---

## Documentation

### Top-level (game system)

| Guide | What's in it |
|---|---|
| [docs/GAMEPLAY.md](docs/GAMEPLAY.md) | Every game mechanic: setup, civs, terrain, units (stats + costs), cities (yields + growth), production queue, buildings + gold-purchased structures, the 21-tech tree, workers, combat, diplomacy, turn flow, victory. |
| [docs/UI_GUIDE.md](docs/UI_GUIDE.md) | Frontend lifecycle (Start → Load → Intro → War Room), layout breakdown of every panel and overlay (city drawer, diplomatic audience + ribbon, sovereign portrait), map rendering layers, audio plumbing. |
| [docs/ASSET_INTEGRATION.md](docs/ASSET_INTEGRATION.md) | Contract between the game and the asset server, taxonomy mapping, manifest resolver, same-origin proxy, graceful fallback, smoke test. |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Prerequisites, backend + frontend setup, env vars, tests, common workflows, where to hook new things in. |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Backend engine architecture — pure-functional state, intent → goal → action lowering, LLM goal source. |
| [docs/REPORT_HANDOFF.md](docs/REPORT_HANDOFF.md) | Concise project summary and source map for AI agents writing reports about what has been implemented. |
| [GAME_BACKLOG.md](GAME_BACKLOG.md) | Outstanding game-design work. |
| [TIER1_PLAN.md](TIER1_PLAN.md) | Tier-1 mechanics implementation record. |
| [planning.md](planning.md) | Original concept doc. |

### Per-subproject

- **Asset server:** see [`assetserver/README.md`](assetserver/README.md) and
  [`assetserver/docs/`](assetserver/docs/) — pipeline deep-dive, architecture
  notes, ComfyUI setup, prompt-writing guides per asset family.
- **Dataset & training:** see
  [`dataset-gen-train/README.md`](dataset-gen-train/README.md) and
  [`dataset-gen-train/docs/`](dataset-gen-train/docs/) — generation pipeline,
  training pipeline, ComfyUI workflows, experiment design.

---

## Repository Layout

```
INF-3600/
├── README.md                   this umbrella entry point
├── AGENTS.md                   multi-agent system overview for the course
├── docs/                       game-system documentation
│   ├── ARCHITECTURE.md         backend engine layers + LLM goal source
│   ├── GAMEPLAY.md             every mechanic with engine-exact numbers
│   ├── UI_GUIDE.md             frontend lifecycle, layout, overlays, audio
│   ├── ASSET_INTEGRATION.md    asset service contract + resolver + fallback
│   ├── DEVELOPMENT.md          run, env, test, hook-in points
│   └── REPORT_HANDOFF.md       concise summary for AI report writers
├── backend/                    Python game engine + FastAPI API
│   ├── app/api/                routes + Pydantic schemas + game store
│   ├── app/engine/             pure-functional rules layer
│   ├── scripts/                headless playthrough runner
│   └── tests/                  pytest suite (339 passing)
├── frontend/                   Next.js + React + TypeScript UI
│   ├── app/                    Next.js App Router (page.tsx, globals.css,
│   │                           api/asset/[...path] same-origin proxy)
│   ├── components/             SquareMap (SVG map renderer)
│   ├── lib/                    game + asset clients, manifest resolver,
│   │                           audio hook
│   └── public/audio/           intro / ambient music tracks
├── assetserver/                Medieval Pixel Art Image Service (FastAPI)
│   ├── src/                    leader/tile/unit asset-family engines,
│   │                           ComfyUI client + load balancer, storage
│   ├── workflows/              ComfyUI workflow JSONs (txt2img, inpaint,
│   │                           leader splash/profile/action, background)
│   ├── config/                 prompt templates + per-family modes
│   ├── docs/                   pipeline + architecture deep-dive
│   └── tests/                  pytest suite
├── dataset-gen-train/          LoRA training pipeline
│   ├── src/generation/         prompt + dataset generation
│   ├── src/training/           Ostris AI Toolkit integration
│   ├── config/                 per-experiment LoRA YAMLs + ComfyUI workflows
│   ├── docs/                   generation + training deep-dives
│   └── dataset/                handoff folder
├── scripts/
│   └── asset_api_smoke.py      stdlib smoke test for the asset service
├── GAME_BACKLOG.md             outstanding game-design work
├── TIER1_PLAN.md               Tier-1 mechanics implementation record
└── planning.md                 original concept doc
```

---

## Stack

| Layer | Tech |
|---|---|
| Game engine | Python 3.11+, frozen dataclasses, pure functional state transitions |
| Backend HTTP | FastAPI, Pydantic, in-memory store, OpenAI tool-use for AI civs |
| Frontend | Next.js 15 (App Router), React 19, TypeScript strict, SVG-rendered map |
| Generative art | Self-hosted Medieval Pixel Art service (FLUX2 Klein 4B Distilled via ComfyUI + custom LoRA) |
| LoRA training | Ostris AI Toolkit + ComfyUI dataset generation, FLUX2 Klein 4B Distilled base |
| Audio | `HTMLAudioElement` with a small `useAudio` hook (playlist + narration ducking + mute toggle) |

---

## Testing

```bash
# backend (pytest)
cd backend && .venv/bin/python -m pytest                 # 339 tests

# frontend (tsc + production build)
cd frontend && npm run typecheck && npm run build

# asset server (pytest, in its own venv)
cd assetserver && pytest

# external asset service smoke (hits a live host)
python3 scripts/asset_api_smoke.py --fast
```

See [docs/DEVELOPMENT.md §5](docs/DEVELOPMENT.md#5-testing) for the full
testing playbook, and each subproject's README for its own test runner notes.

---

## Status & Known Issues

- **Asset service is reached through a Next.js same-origin proxy** at
  `/api/asset/[...path]`. The browser only talks to its own origin, so CORS
  is never a factor — even when the upstream is degraded and would otherwise
  return a 5xx response without `Access-Control-Allow-Origin` headers. See
  [docs/ASSET_INTEGRATION.md §1](docs/ASSET_INTEGRATION.md#1-configuration).
- **The leader profile pipeline is the asset service's only remaining
  trouble spot.** `POST /leader` (splash) is healthy; the chained profile
  stage occasionally returns HTTP 500. The frontend catches that silently
  and falls back to the splash, cropped via `object-position: center 20%`,
  so the empire badge and portrait surfaces still show real art.
- **Playthrough test flakiness** — `backend/tests/test_playthrough.py::test_playthrough_with_generated_map`
  intermittently fails with a city-capture move error. Pre-existing and
  unrelated to recent work; tracked in the backlog.
- **No automated CI** — manual checks before opening a PR (see
  [docs/DEVELOPMENT.md §8](docs/DEVELOPMENT.md#8-ci--quality)).

---

## AI Agent System

StrategAI includes a multi-agent system to assist with development across all subprojects. The system supports both **GitHub Copilot** and **Claude Code** harnesses.

### Quick Reference

| Harness | Format | Location |
|---------|--------|----------|
| **GitHub Copilot** | `.agent.md` files | `.github/agents/` (root + subprojects) |
| **Claude Code** | `AGENTS.md` files | Root + each subproject |

### Root-Level Agents

- **Orchestrator**: Cross-project coordination, multi-subproject features
- **Planner**: Create implementation plans, break down complex features, coordinate modifications
- **AI Showcase**: Generate reports and presentations highlighting AI/ML aspects
- **Research**: Read-only codebase exploration and data flow tracing
- **Integration Tester**: Validate cross-project contracts and integration points
- **Backend Specialist**: Game engine, LLM integration, API design
- **Frontend Specialist**: Next.js UI, state management, asset integration
- **Report Writer**: Write IEEE academic report sections, create figure descriptions, add citations
- **Oral Presentation**: Prepare 7-8 minute presentation, create slide outlines, practice Q&A

### Subproject Agents

Each subproject has specialized agents:
- **Backend** (3 agents): Orchestrator, Game Engine, LLM Integration
- **Frontend** (2 agents): Orchestrator, UI Engineer
- **Asset Server** (11 agents): Full specialist coverage
- **Dataset/Training** (5 agents): Training, dataset, publishing, code quality

### Documentation

- **Agent system details**: [`.github/agents/README.md`](.github/agents/README.md)
- **Project context**: `AGENTS.md` files in root and each subproject
- **Architecture diagram**: See `.github/agents/README.md` for delegation patterns

### Usage Examples

**GitHub Copilot**:
```
@Orchestrator Add a new unit type across backend, frontend, and asset server
```

**Claude Code**:
```
Use the Orchestrator agent to coordinate adding a new unit type
```

---

## License

TBD.
