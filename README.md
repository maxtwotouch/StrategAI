# StrategAI

A Civilization-style turn-based strategy game where rival civs are driven by
LLM-emitted goals and illustrated with on-demand generative pixel art. The
repository contains the full system: the Python game engine and FastAPI
backend (`backend/`), the Next.js frontend (`frontend/`), the self-hosted
generative pixel-art microservice (`assetserver/`), and the LoRA training
pipeline that produced the model the microservice runs (`dataset-gen-train/`).

---

## The Game

### What you do

A deterministic 4X game played on a square-tile map under fog of war. Each
turn you move and fight with four unit types — archer, scout, settler,
warrior — found cities with settlers, fill a per-city production queue
(units, buildings, gold-purchased structures placed directly on tiles),
research along a 21-node tech tree, dispatch workers to lay improvements
(farms, mines, roads), and negotiate with the rival civs. The match ends on
a score-based victory. The complete mechanics — every cost, yield, terrain
modifier, combat formula and turn-phase ordering — is documented in
[docs/GAMEPLAY.md](docs/GAMEPLAY.md).

### Engine architecture

The backend is a pure-functional engine wrapped in a FastAPI HTTP layer.
Game state is built from frozen dataclasses, every rule is a pure function
that returns a new `GameState`, and state transitions are organized into
three layers:

1. **Strategic layer (LLM).** The AI civ sees a fog-filtered local view
   serialized by `serialize.py` and emits `Intents` via the OpenAI tool-use
   API (nine intent tools — move, attack, found city, queue production,
   research, send message, etc.).
2. **Tactical layer (Python).** `operations.py` lowers `Intents` to `Goals`;
   `executor.py` resolves goals against current state (A\* pathfinding,
   move budget, occupancy, line-of-sight) and emits concrete `Actions`.
3. **Validator + engine.** Each `Action` is legality-checked, then applied
   by the appropriate engine module (`combat.py`, `city_founding.py`,
   `production.py`, `economy.py`, `diplomacy.py`, …) which returns a brand
   new `GameState`.

The LLM never touches `GameState` directly. All inputs to the model are
serialized views; all outputs go through the validator before any state
change. This makes the AI civs cheat-resistant, fog-of-war-respecting, and
fully replayable from a seed. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### LLM-driven AI civs

Each AI civ has a per-leader persona (`backend/app/api/game_factory.py:_AI_ROSTER`)
appended to a shared system prompt (`backend/app/engine/openai_goals.py`).
A rolling memory window of recent turn outcomes is included on every call
so the LLM can reason about its own history. Validation errors are returned
to the LLM as machine-readable error codes (`not_your_turn`, `not_owner`,
`no_moves`, …) so the model can self-correct on the next intent. With no
`OPENAI_API_KEY` set, AI civs fall back to a deterministic stub goal source
that keeps the engine fully exercisable for offline development.

### Diplomacy

Civs track per-pair **stance** (peace, war), a numeric **relationship**
score, and active **truces**. The diplomacy module persists a message log
between every pair and exposes a free-form chat: the human player opens an
audience with a met civ, sends a message, and the rival civ's LLM replies
in-character with the same persona it uses for strategic play. Recent UI
work added a **diplomatic ribbon** along the top of the map that surfaces
every met leader as a portrait — relationship-coloured ring, stance dot,
truce halo, inbox pill — clickable to open the audience overlay.

### Frontend

The UI is a single Next.js 15 / React 19 / TypeScript client. The map is
rendered in SVG by `SquareMap.tsx`; the war-room layout, city drawer,
diplomatic audience, sovereign portrait and the ribbon are all in
`page.tsx` + `globals.css`. State is local React (`useState` / `useRef` /
`useMemo`, no external library). Audio is a three-track playlist with
narration ducking via a `useAudio` hook.

Every asset surface degrades gracefully: missing assets fall back to flat
colours, glyph rendering, or letter-initial portraits, so the game is
fully playable without the asset server running. When the asset server is
configured, the frontend talks to it through a **same-origin proxy** at
`/api/asset/[...path]` (see [docs/ASSET_INTEGRATION.md](docs/ASSET_INTEGRATION.md)),
which sidesteps CORS even when upstream returns a 5xx without
`Access-Control-Allow-Origin` headers.

---

## The Asset Server

A FastAPI microservice that drives ComfyUI workflows over **FLUX2 Klein 4B
Distilled** to generate top-down medieval pixel-art game assets on demand.
Lives under `assetserver/` and is independently runnable — full deep-dive in
[`assetserver/README.md`](assetserver/README.md).

### Six asset families

| Family | Purpose | Key fields |
|---|---|---|
| `leader` | Leader portraits (splash / profile / action) | archetype, culture, time_of_day, mood, action_category |
| `structure` | Buildings: fortification, production, housing, sacred | category, style, condition, scale |
| `object` | Nature objects + world props | category (vegetation/geological/rural/urban/debris), biome, season |
| `terrain` | Elevation features | category (hill/slope/cliff/ridge/depression), scale, material |
| `unit` | South-facing top-down character sprites | unit_type (archer/scout/settler/warrior) |
| `background_tile` | Seamless terrain tiles | tile_type (water/grass/sand/stone/dirt) |

Each family supports the full CRUD set — `POST` to generate, `GET` to list
(with `?limit=` / `?offset=` pagination, max 200), `GET /{id}` to fetch one,
`DELETE /{id}` to remove. Combined with health, discovery, catalog and
asset-download endpoints the service exposes 33 routes total.

### The leader pipeline

The leader family is a **three-stage img2img chain** that preserves visual
identity across multiple portraits of the same character:

```
POST /leader  asset_type=splash    → reference image stored
POST /leader  asset_type=profile   → uses splash as img2img reference
POST /leader  asset_type=action    → uses splash as img2img reference
```

Splash creates the leader's identity (full-body promo art). Profile and
action stages run with the splash as an img2img reference so face, clothing
and palette stay consistent. The action stage accepts an `action_category`
(military / diplomatic / civic / …) and a free-form `action_description`,
and can take a `leader_ids` array to put multiple leaders in the same scene
(treaty signings, war councils). All other families use a single
text-to-image generation.

### ComfyUI integration

A multi-node load balancer (`COMFYUI__NODES`) routes generations across
GPUs with health checks, automatic failover, and configurable retry counts.
Every workflow JSON in `workflows/` is structurally validated at startup;
a missing output node or malformed prompt-injection target is a fatal
error in production mode. A warm-up generation runs at boot to preload
GPU VRAM. The WebSocket protocol is preferred with automatic fallback to
HTTP polling.

### Three generation modes

Per family, in `config.yaml` or via `GENERATION__MODES__*` env vars:

- `comfyui` — real GPU generation through the load-balanced ComfyUI pool
- `static` — serve from a pre-curated PNG catalog
- `placeholder` — procedural rectangle with the requested label

`placeholder` lets the **entire API** (client contracts, validation, pagination,
errors) be exercised with zero external dependencies. The drop-in preset
`assetserver/.env.testing` flips every family to placeholder mode for tests.

### Storage, caching, security

SQLite with WAL journal for safe concurrent reads/writes. Alembic
migrations run automatically at startup. An in-memory LRU cache (configurable
`SERVER__CACHE_MAX_ENTRIES` / `SERVER__CACHE_MAX_MB`) accelerates asset
serving; atomic temp-file + rename writes prevent half-flushed files; orphan
records are cleaned up on persist failure. Rate limiting (global POST and
GET budgets with burst size) is on by default. Production mode adds API-key
auth, explicit CORS origins (no `*`), fatal schema-mismatch checks at
startup, and blocks the dev-only `DATABASE_RESET=true` switch.

---

## The Dataset and LoRA Training

The visual style of the generated art comes from a LoRA fine-tuned on a
curated top-down medieval pixel-art dataset. The full pipeline that
produced both the dataset and the trained weights lives in
`dataset-gen-train/`. Two independent phases connected by a single
`metadata.jsonl` handoff file. Deep-dive in
[`dataset-gen-train/README.md`](dataset-gen-train/README.md).

### Phase 1 — Dataset generation

```
generate-prompts      → dataset/prompts/*.jsonl
bash scripts/generate_images.sh   (drives ComfyUI from the prompt file)
                      → dataset/raw/*.png  (with sidecar metadata)
<manual curation: delete bad PNGs>
prepare-dataset       → dataset/hf/  (clean PNGs + metadata.jsonl manifest)
```

Prompts are sampled from `config/prompt_templates.json` (categories, biomes,
styles, conditions), images are generated through a fixed ComfyUI workflow
preset, hand-curated for quality, then packaged as a Hugging Face dataset.
The curated dataset is published at
[`stixxert/topdown-medieval-pixelart`](https://huggingface.co/datasets/stixxert/topdown-medieval-pixelart).

### Phase 2 — LoRA training

```
extract-training-set        → .txt caption sidecars per PNG
validate-dataset            → schema + image-integrity checks
derive-captions             → 3 caption variants (minimal/detailed/ultra_minimal)
sync-validation-prompts     → inject sample prompts into training YAMLs
bash scripts/train_experiments.sh   → batch launch via Ostris AI Toolkit
                            → output/*.safetensors
```

Training uses the [Ostris AI Toolkit](https://github.com/ostris/ai-toolkit)
over **FLUX2 Klein 4B Distilled** as the base. The repo ships a six-experiment
matrix in `config/training/` so caption-density, learning-rate and rank
variations can be compared on a single dataset. Each console command is also
runnable as a `python -m src.training.*` module.

### The trigger token

The trained LoRA is activated with the token `<tdp>` followed by the angle
phrase `top-down view.`:

```
<tdp> top-down view. a medieval granary in steampunk industrial style,
16x16 pixel art, white background
```

Both must be present at inference. The asset server's prompt templates
prepend this automatically; if you call the underlying ComfyUI workflow
directly you have to include it yourself.

### Hand-off to the asset server

The output of this pipeline is the `.safetensors` LoRA file loaded into
the ComfyUI workflows the asset server submits. The two services share
their ComfyUI infrastructure and base model; the training pipeline never
talks to the asset server directly.

---

## Quick Start

Game only — backend + frontend, no GPU required:

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.api.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
# Optional, to pull generated art:
# echo 'NEXT_PUBLIC_ASSET_API_URL=https://your-asset-host' >> .env.local
npm run dev

open http://localhost:3000
```

Asset server (GPU-free placeholder mode):

```bash
cd assetserver
pip install -e ".[dev]"
cp .env.testing .env       # flips every family to placeholder mode
uvicorn src.main:app --host 127.0.0.1 --port 8001
```

For real generation set `COMFYUI__BASE_URL` (single node) or
`COMFYUI__NODES` (multi-node) to a ComfyUI server with the required
models and custom nodes loaded — see
[`assetserver/README.md`](assetserver/README.md) for the exact list.

LoRA training is a multi-step pipeline with its own prerequisites
(Hugging Face CLI auth, Ostris AI Toolkit, ComfyUI for dataset
generation) — follow
[`dataset-gen-train/README.md`](dataset-gen-train/README.md).

A consolidated walk-through for all four parts together lives in
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

---

## Repository Layout

```
INF-3600/
├── backend/                    Python game engine + FastAPI API
│   ├── app/api/                routes, Pydantic schemas, game store
│   ├── app/engine/             pure-functional rules layer (22 modules)
│   ├── scripts/                headless playthrough runner
│   └── tests/                  pytest suite (339 passing)
├── frontend/                   Next.js + React + TypeScript UI
│   ├── app/                    App Router (page.tsx, globals.css,
│   │                           api/asset/[...path] same-origin proxy)
│   ├── components/             SquareMap SVG renderer
│   ├── lib/                    game + asset clients, manifest resolver,
│   │                           audio hook, hex math
│   └── public/audio/           music tracks (ATTRIBUTION.md inside)
├── assetserver/                Medieval Pixel Art Image Service (FastAPI)
│   ├── src/                    asset-family engines, ComfyUI client +
│   │                           load balancer, storage, config
│   ├── workflows/              ComfyUI workflow JSONs (txt2img, img2img,
│   │                           leader splash/profile/action, background)
│   ├── config/                 prompt templates + per-family modes
│   ├── docs/                   pipeline + architecture deep-dive
│   └── tests/                  pytest suite
├── dataset-gen-train/          LoRA training pipeline
│   ├── src/generation/         prompt + dataset generation
│   ├── src/training/           Ostris AI Toolkit integration
│   ├── config/training/        6 LoRA experiment YAMLs
│   ├── config/comfyui/         ComfyUI workflow API JSONs
│   ├── dataset/                raw → hf handoff folders
│   ├── docs/                   generation + training deep-dives
│   └── tests/                  pytest suite (35 tests)
├── docs/                       game-system documentation
│   ├── ARCHITECTURE.md         engine layers + LLM goal source
│   ├── GAMEPLAY.md             every mechanic with engine-exact numbers
│   ├── UI_GUIDE.md             frontend lifecycle, layout, overlays, audio
│   ├── ASSET_INTEGRATION.md    asset service contract + resolver + fallback
│   ├── DEVELOPMENT.md          run, env, test, hook-in points
│   └── REPORT_HANDOFF.md       summary + source map for AI report writers
├── scripts/
│   └── asset_api_smoke.py      stdlib smoke test against a live asset host
├── AGENTS.md                   multi-agent development system overview
├── GAME_BACKLOG.md             outstanding game-design work
├── TIER1_PLAN.md               Tier-1 mechanics implementation record
└── planning.md                 original concept doc
```

---

## Documentation

| Guide | What's in it |
|---|---|
| [docs/GAMEPLAY.md](docs/GAMEPLAY.md) | Every mechanic: setup, civs, terrain, units (stats + costs), cities (yields + growth), production queue, buildings + gold-purchased structures, the 21-tech tree, workers, combat, diplomacy, turn flow, victory. |
| [docs/UI_GUIDE.md](docs/UI_GUIDE.md) | Frontend lifecycle (Start → Load → Intro → War Room), every panel and overlay (city drawer, diplomatic audience + ribbon, sovereign portrait), map rendering layers, audio plumbing. |
| [docs/ASSET_INTEGRATION.md](docs/ASSET_INTEGRATION.md) | Contract between the game and the asset server, taxonomy mapping, manifest resolver, same-origin proxy, graceful fallback, smoke test. |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Prerequisites, setup for all four parts, env vars, tests, common workflows, where to hook new things in. |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Backend engine architecture — pure-functional state, intent → goal → action lowering, LLM goal source. |
| [docs/REPORT_HANDOFF.md](docs/REPORT_HANDOFF.md) | Concise project summary and source map for AI agents writing reports about what has been implemented. |
| [`assetserver/README.md`](assetserver/README.md) + [`assetserver/docs/`](assetserver/docs/) | Asset-server pipeline deep-dive, architecture notes, ComfyUI setup, prompt-writing guides per family, deployment + production hardening. |
| [`dataset-gen-train/README.md`](dataset-gen-train/README.md) + [`dataset-gen-train/docs/`](dataset-gen-train/docs/) | Generation pipeline, training pipeline, ComfyUI workflows, experiment design. |
| [GAME_BACKLOG.md](GAME_BACKLOG.md) | Outstanding game-design work. |
| [TIER1_PLAN.md](TIER1_PLAN.md) | Tier-1 mechanics implementation record. |
| [planning.md](planning.md) | Original concept doc. |

---

## Stack

| Layer | Tech |
|---|---|
| Game engine | Python 3.11+, frozen dataclasses, pure functional state transitions |
| Backend HTTP | FastAPI, Pydantic, in-memory store, OpenAI tool-use for AI civs |
| Frontend | Next.js 15 (App Router), React 19, TypeScript strict, SVG-rendered map |
| Asset service | Python 3.10+, FastAPI, SQLite (WAL) + Alembic, ComfyUI client with multi-node load balancer |
| Generative model | FLUX2 Klein 4B Distilled (Diffusion Transformer) via ComfyUI + custom LoRA |
| LoRA training | Ostris AI Toolkit, ComfyUI for dataset generation, 6-experiment matrix |
| Dataset hosting | Hugging Face Hub (`stixxert/topdown-medieval-pixelart`) |
| Audio | `HTMLAudioElement` + `useAudio` hook (playlist + narration ducking + mute) |

---

## Testing

```bash
# Game backend (339 tests)
cd backend && .venv/bin/python -m pytest

# Frontend (typecheck + production build)
cd frontend && npm run typecheck && npm run build

# Asset server (~345 tests, runs in placeholder mode without ComfyUI)
cd assetserver && python -m pytest tests/ -v

# Dataset/training pipeline (35 tests)
cd dataset-gen-train && python -m pytest tests/ -v

# External asset service smoke test (hits a live host)
python3 scripts/asset_api_smoke.py --fast
```

See [docs/DEVELOPMENT.md §5](docs/DEVELOPMENT.md#5-testing) for the full
playbook.

---

## Status & Known Issues

- The asset service is reached through a Next.js same-origin proxy at
  `/api/asset/[...path]`. The browser only talks to its own origin, so CORS
  is never a factor — even when the upstream returns a 5xx without
  `Access-Control-Allow-Origin` headers. See
  [docs/ASSET_INTEGRATION.md §1](docs/ASSET_INTEGRATION.md#1-configuration).
- The leader profile pipeline is the asset service's only remaining trouble
  spot. `POST /leader` (splash) is healthy; the chained profile stage
  occasionally returns HTTP 500. The frontend catches that silently and
  falls back to the splash, cropped via `object-position: center 20%`, so
  the empire badge and portrait surfaces still show real art.
- `backend/tests/test_playthrough.py::test_playthrough_with_generated_map`
  intermittently fails with a city-capture move error. Pre-existing and
  unrelated to recent work; tracked in the backlog.
- No automated CI. Manual checks before opening a PR are described in
  [docs/DEVELOPMENT.md §8](docs/DEVELOPMENT.md#8-ci--quality).

---

## AI Agent System

The repository includes a multi-agent development system that supports both
**GitHub Copilot** and **Claude Code** harnesses.

| Harness | Format | Location |
|---|---|---|
| GitHub Copilot | `.agent.md` files | `.github/agents/` (root + each area) |
| Claude Code | `AGENTS.md` files | Root + each area |

**Root-level agents** (Orchestrator, Planner, AI Showcase, Research,
Integration Tester, Backend Specialist, Frontend Specialist, Report Writer,
Oral Presentation) coordinate cross-area work. **Area-specific agents**
specialise per directory: backend (3), frontend (2), asset server (11),
dataset/training (5). Delegation graph and cross-harness invocation guide
in [`.github/agents/README.md`](.github/agents/README.md); per-area context
in each `AGENTS.md`.

Usage:

```
# GitHub Copilot
@Orchestrator Add a new unit type across backend, frontend, and asset server

# Claude Code
Use the Orchestrator agent to coordinate adding a new unit type
```

---

## License

TBD.
