# StrategAI — Backend

Python game engine with LLM-driven AI civilizations and a REST API.

## Quick Start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # add your OPENAI_API_KEY
python -m uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`. Without `OPENAI_API_KEY`, AI civs fall back to deterministic random behavior — the game is still playable.

## What It Does

- **Pure-functional game engine** — all state in frozen `@dataclass` types, every mutation returns a new `GameState`
- **LLM-driven AI civilizations** — 9 intent tools (expand, scout, engage, reinforce, develop, turtle, diplomacy, research, idle) via OpenAI tool-use API
- **Three-layer architecture** — Strategic (LLM intents) → Tactical (A* pathfinding) → Validator (legality checks)
- **REST API** — 16 endpoints for game creation, turn resolution, actions, diplomacy, audio

## Configuration

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | Yes | GPT model access for AI civs + TTS narration |

See **[`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)** for all endpoints, DTOs, and error codes.
See **[`docs/BACKEND_CONFIG.md`](docs/BACKEND_CONFIG.md)** for the complete configuration reference.

## Documentation

| Document | Contents |
|----------|----------|
| [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) | All 16 REST endpoints, DTOs, error code catalog |
| [`docs/BACKEND_CONFIG.md`](docs/BACKEND_CONFIG.md) | Environment variables, hardcoded parameters, config flow |
| [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) | System architecture, engine layers, LLM integration design |
| [`../GAMEPLAY.md`](../GAMEPLAY.md) | Complete game mechanics reference |

## Testing

```bash
python -m pytest tests/ -x --tb=short   # 339+ tests
```

## Conventions

- **Frozen dataclasses** — `@dataclass(frozen=True, slots=True)` for all engine state. Mutations use `dataclasses.replace`.
- **Pure functions** — `(state, args) → new_state`. No side effects, no I/O in engine modules.
- **Result types** — `ValidationResult` (Ok | Error) for LLM-facing validation. Never throws.
- **Seeds** — `secrets.randbits(31)`, never `random`.
- **LLM isolation** — LLM never touches `GameState` directly; only serialized views via `serialize.py`.

## Deployment

See **[`../DEPLOYMENT.md`](../DEPLOYMENT.md)** for production deployment — the backend is part of the **Game Server** tier (CPU-only, deployable anywhere with Python 3.11+).
