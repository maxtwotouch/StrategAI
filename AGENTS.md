# StrategAI — AI Agent System

This repository contains a multi-agent system for an INF-3600 Generative AI student project. The project combines an LLM-driven Civilization-style strategy game with a self-hosted generative pixel-art asset pipeline.

## Project Overview

**StrategAI** is a full-stack strategy game where:
- **AI civilizations** are controlled by LLMs via OpenAI's tool-use API (strategic decision-making, diplomacy)
- **Game assets** are generated on-demand using Diffusion Transformers (FLUX2 Klein 4B via ComfyUI)
- **Style adaptation** is achieved through LoRA fine-tuning on curated medieval pixel art

## Architecture

### Subprojects

| Subproject | Path | Tech Stack | Purpose |
|-----------|------|-----------|---------|
| **Backend** | `backend/` | Python 3.11+, FastAPI, OpenAI API | Game engine (pure functional, frozen dataclasses), LLM-driven AI civs, REST API |
| **Frontend** | `frontend/` | Next.js 15, React 19, TypeScript, SVG | Game UI, hex map rendering, asset integration, diplomacy chat |
| **Asset Server** | `assetserver/` | Python 3.10+, FastAPI, ComfyUI, FLUX2 Klein 4B | Generative pixel-art service (6 asset families, 33 endpoints) |
| **Dataset/Training** | `dataset-gen-train/` | Python 3.10+, Ostris AI Toolkit, ComfyUI | LoRA fine-tuning pipeline for FLUX2 Klein |
| **Docs** | `docs/` | Markdown | Architecture, gameplay, development, UI, asset integration guides |

### AI Technologies (Course Relevance)

| Component | Technology | Location |
|-----------|-----------|----------|
| **LLM-driven AI civs** | OpenAI tool-use API | `backend/app/engine/openai_goals.py` — 9 intent tools, per-leader personas, rolling memory |
| **Diplomacy chat** | LLM with persistent conversation | `backend/app/engine/diplomacy.py` — free-form chat with AI leaders |
| **Generative pixel art** | ComfyUI + FLUX2 Klein 4B (DiT) | `assetserver/src/` — 6 asset families, 3 generation modes |
| **Style adaptation** | LoRA fine-tuning | `dataset-gen-train/` — Ostris AI Toolkit, 6-experiment matrix |

### Inter-Service Contracts

- **Frontend ↔ Backend**: REST API at `http://localhost:8000` — 14 endpoints (games, actions, turns). DTOs defined in `backend/app/api/schemas.py`, consumed by `frontend/lib/api.ts`
- **Frontend ↔ Asset Server**: Asset manifest resolution via `frontend/lib/assetManifest.ts` → `NEXT_PUBLIC_ASSET_API_URL`. POST endpoints for leader, unit, structure, terrain, background_tile. GET for asset files
- **Backend ↔ Asset Server**: No direct contract — frontend mediates
- **Asset Server ↔ Dataset/Training**: Shared ComfyUI infrastructure, shared FLUX2 Klein model, LoRA weights applied at inference time

## Agent Roster

### Root-Level Agents (Cross-Project)

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| **Orchestrator** | Coordinate work spanning 2+ subprojects | Multi-subproject features, integration work, report preparation |
| **Planner** | Create implementation plans, break down complex features | Architecture design, task decomposition, multi-step coordination |
| **AI Showcase** | Document AI/ML aspects for report/presentation | Report sections, presentation slides, architecture diagrams |
| **Research** | Read-only exploration across all subprojects | Understanding codebase, tracing data flow, investigating patterns |
| **Integration Tester** | Verify subprojects work together | API contract validation, asset manifest resolution, smoke tests |
| **Backend** | Game engine, LLM integration, API design | Backend-specific tasks, engine changes, LLM prompt tuning |
| **Frontend** | Next.js UI, SVG map, asset integration | Frontend-specific tasks, UI changes, asset resolution |

### Subproject Agents

#### Asset Server (`assetserver/.github/agents/`)

| Agent | Purpose |
|-------|---------|
| **Orchestrator** | Multi-step feature coordination, 6-phase workflow |
| **Implementation** | Code changes, bug fixes, endpoint implementation |
| **API Designer** | REST endpoint design, Pydantic models |
| **Planner** | Feature planning, architecture design |
| **Research** | Codebase exploration (read-only) |
| **Test Engineer** | Test writing, coverage analysis |
| **Code Reviewer** | Pattern compliance, bug detection |
| **Documentation Engineer** | Docs, docstrings, guides |
| **Database Architect** | Schema design, Alembic migrations |
| **Workflow Engineer** | ComfyUI workflow JSON, prompt templates |
| **Security Auditor** | Vulnerability scanning, input validation |

#### Dataset/Training (`dataset-gen-train/.github/agents/`)

| Agent | Purpose |
|-------|---------|
| **Orchestrator** | Pipeline coordination, phase management |
| **Training** | LoRA config YAML, experiment launching |
| **Dataset** | Image generation, curation, caption derivation |
| **Publishing** | HuggingFace publishing, model cards |
| **Code Quality** | Tests, linting, Python refactoring |

#### Backend (`backend/.github/agents/`)

| Agent | Purpose |
|-------|---------|
| **Orchestrator** | Backend feature coordination |
| **Game Engine** | Pure functional engine, combat, economy, tech tree |
| **LLM Integration** | OpenAI tool-use, diplomacy, persona tuning |

#### Frontend (`frontend/.github/agents/`)

| Agent | Purpose |
|-------|---------|
| **Orchestrator** | Frontend feature coordination |
| **UI Engineer** | React components, state management, panels |

## Project Conventions

### Universal Rules

- **Seeds**: `secrets.randbits(31)` — never `random`
- **DB sessions**: `with SessionLocal() as db:` — always context manager (assetserver)
- **Atomic writes**: temp file + `os.rename` for all file I/O
- **Frozen dataclasses**: all engine state objects are immutable — mutations return new copies (backend)
- **Result types**: validation returns `ValidationResult` (Ok | Error), never throws for LLM-facing code (backend)
- **Config**: `config.yaml` for defaults, `.env` for overrides (nested via `__` delimiter)
- **Tests**: mirror `src/` structure, use pytest fixtures, `@pytest.mark.asyncio` for async

### Backend-Specific

- **Frozen dataclasses**: `@dataclass(frozen=True)` for all engine state
- **Error codes**: Machine-readable strings (`not_your_turn`, `not_owner`, `no_moves`) for LLM feedback
- **Game store**: In-memory `GameStore` with threading lock
- **LLM isolation**: LLM never touches `GameState` directly — only serialized views via `serialize.py`

### Asset Server-Specific

- **Orphan cleanup**: Call `_try_remove_asset()` on DB persist failure
- **Async safety**: No blocking calls in async context
- **Prompts**: Templates in `config/prompt_templates.json`, enum prose in `src/*/prompts.py`
- **Workflows**: JSON node graphs in `workflows/`, validated at startup

### Frontend-Specific

- **State management**: React `useState` + `useRef` + `useMemo` — no external state library
- **API calls**: All go through `api.*` methods in `frontend/lib/api.ts`
- **Asset fallback**: Every missing generative asset degrades to built-in colors/glyphs/initials

## Quick Start

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Asset Server
```bash
cd assetserver
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn src.main:app --reload --port 8001
```

### Dataset/Training
```bash
cd dataset-gen-train
# See dataset-gen-train/README.md for setup
```

## Testing

```bash
# Backend (315+ tests)
cd backend && python -m pytest tests/ -x --tb=short

# Asset Server (~345 tests)
cd assetserver && python -m pytest tests/ -x --tb=short

# Frontend (type check)
cd frontend && npx tsc --noEmit

# Integration smoke test
python scripts/asset_api_smoke.py
```

## Documentation

- `docs/ARCHITECTURE.md` — Backend engine layers, LLM goal source, pure functional design
- `docs/DEVELOPMENT.md` — Setup, env vars, workflows, where to hook new features
- `docs/GAMEPLAY.md` — Complete game mechanics reference
- `docs/ASSET_INTEGRATION.md` — Asset service contract, manifest resolution, fallback
- `docs/UI_GUIDE.md` — Frontend lifecycle, panel breakdown, audio plumbing
- `assetserver/docs/project-report.md` — **Main student technical report** (read this first)

## Agent System Architecture

See `.github/agents/README.md` for:
- Agent delegation graph
- Cross-harness compatibility notes
- How to invoke agents in GitHub Copilot vs Claude Code
