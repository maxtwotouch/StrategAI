# Backend — AI Agent System

This subproject contains the game engine, LLM integration, and REST API for StrategAI.

## Architecture

Three-layer design:
```
STRATEGIC LAYER (LLM via OpenAI tool-use API)
  → emits Intents (expand, scout, engage, reinforce, speak, build, research, improve)
TACTICAL LAYER (deterministic Python)
  → A* pathfinding, move-budget, occupancy → Actions
VALIDATOR + ENGINE (pure functional, immutable state)
  → legality check → apply → new GameState
```

**Key principle**: LLM never touches `GameState` directly. All state objects are **frozen dataclasses** — mutations return new copies.

## Directory Structure

| Path | Contents |
|------|----------|
| `app/engine/` | 27 modules: hex coords, terrain, models, map gen, movement, combat, production, research, diplomacy, economy, borders, buildings, fog of war, victory, turn resolver, executor, serializer, playthrough, LLM goals, human source, intents, operations, directives, improvements, starting positions |
| `app/api/` | FastAPI routers (games, actions, turns), schemas (DTOs), validator, store, game factory |
| `app/api/routers/` | 14 REST endpoints |
| `tests/` | 315+ pytest tests |

## LLM Integration

**Location**: `app/engine/openai_goals.py`

- **9 intent tools**: expand, scout, engage, reinforce, speak, adjust_stance, build, research, improve
- **Per-leader personas**: Genghis (aggressive), Cleopatra (diplomatic), Gandhi (peaceful)
- **Rolling memory**: Last 8 turns of intents + last 32 diplomatic messages
- **Graceful degradation**: Falls back to `RandomGoalSource` on API errors
- **`OpenAIGoalSource` class**: `bind_state()` → `decide(view, civ_id)` → `Decisions(goals, diplomacy, directives)`

**Supporting files**:
- `app/engine/intents.py` — Intent dataclass definitions
- `app/engine/operations.py` — Intent → Goal/Directive resolution
- `app/engine/diplomacy.py` — Diplomatic stance, messages, events
- `app/engine/human_source.py` — Queue-based human goal source (contrast with LLM)
- `app/engine/playthrough.py` — Headless game loop + GoalSource protocol
- `app/api/game_factory.py` — Game initialization with AI roster + personas

## API Surface

| Router | Endpoints |
|--------|-----------|
| `games.py` | `POST /games`, `GET /games/{id}` |
| `actions.py` | 10 action endpoints (move, attack, attack-city, found, research, build, cancel-build, purchase-structure, improve, message) |
| `turns.py` | `POST /games/{id}/turn`, `POST /games/{id}/turn/resolve` |

**DTOs**: Defined in `app/api/schemas.py` — `GameStateOut`, `TileOut`, `UnitOut`, `CityOut`, `CivOut`, etc.

## Conventions

- **Frozen dataclasses**: `@dataclass(frozen=True)` for all engine state
- **Result types**: `ValidationResult = ValidationOk | ValidationError` — never throw for LLM-facing validation
- **Error codes**: Machine-readable strings (`not_your_turn`, `not_owner`, `no_moves`, etc.) for LLM feedback
- **Seeds**: `secrets.randbits(31)` — never `random`
- **Tests**: `pytest -xvs`, mirror `app/` structure in `tests/`
- **Game store**: In-memory `GameStore` with threading lock (`app/api/store.py`)

## Agent Roster

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| **Orchestrator** | Backend feature coordination | Multi-step backend tasks, engine changes |
| **Game Engine** | Pure functional engine, combat, economy, tech tree | Engine logic, combat resolution, production |
| **LLM Integration** | OpenAI tool-use, diplomacy, persona tuning | AI civ behavior, prompt tuning, memory system |

## Testing

```bash
python -m pytest tests/ -x --tb=short
```

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m uvicorn app.main:app --reload
```

## Cross-Project Context

- **Frontend consumes**: REST API at `http://localhost:8000`, DTOs must match `frontend/lib/api.ts` TypeScript interfaces
- **Asset Server**: No direct contract — frontend mediates all asset requests
- **Root orchestrator**: For cross-project tasks, delegate to root `.github/agents/orchestrator.agent.md`
