# Architecture

AI Civilization-style game with a deterministic Python game engine driven by
LLM-emitted strategic intents.  This document summarizes the system as it stands
today (339+ tests, end-to-end playthroughs runnable).

---

## 1. High-Level Design

The system is split into three layers:

```
┌──────────────────────────────────────────────────────────┐
│  STRATEGIC LAYER     (LLM via OpenAI tool-use API)       │
│  Sees fog-filtered local view → emits Intents            │
└──────────────────────┬───────────────────────────────────┘
                       │ Intent (Expand / Scout / Engage / …)
                       ▼
┌──────────────────────────────────────────────────────────┐
│  OPERATIONS LAYER    (deterministic Python)              │
│  Intents → Goals + DiplomaticActions + Directives        │
└──────────────────────┬───────────────────────────────────┘
                       │ Goal (MoveTo / FoundCityNear / AttackUnit / …)
                       ▼
┌──────────────────────────────────────────────────────────┐
│  TACTICAL LAYER      (deterministic Python)              │
│  A* pathfinding, move-budget, occupancy → Actions        │
└──────────────────────┬───────────────────────────────────┘
                       │ Action (Move / FoundCity / Attack / …)
                       ▼
┌──────────────────────────────────────────────────────────┐
│  VALIDATOR + ENGINE  (pure functional, immutable state)  │
│  Legality check → apply → new GameState                  │
└──────────────────────────────────────────────────────────┘
```

Key principle: the LLM never touches `GameState` directly.  Every LLM
intent passes through the operations layer (which resolves high-level intents
into concrete goals), the executor (which knows pathfinding rules), and the
validator (which knows game rules) before any state mutation.

---

## 2. Repository Layout

```
StrategAI/
├── backend/
│   ├── app/
│   │   ├── api/                    FastAPI routes + DTOs
│   │   │   ├── actions.py          Action dataclasses + validator
│   │   │   ├── game_factory.py     new_game() — initial state builder
│   │   │   ├── routers/            FastAPI endpoint routers
│   │   │   ├── schemas.py          Pydantic DTOs for HTTP layer
│   │   │   └── store.py            In-memory game store
│   │   ├── engine/                 Pure game logic (no I/O)
│   │   │   ├── hex.py              Axial hex coords + math
│   │   │   ├── terrain.py          Terrain, features, resources, yields
│   │   │   ├── models.py           Tile / Unit / City / Civ / GameState
│   │   │   ├── map_generator.py    Layered-noise procedural maps
│   │   │   ├── starting_positions.py  Fair start placement
│   │   │   ├── movement.py         Unit move validation + apply
│   │   │   ├── city_founding.py    Settler → city
│   │   │   ├── production.py       City growth + unit building
│   │   │   ├── research.py         Tech tree + science ticks
│   │   │   ├── combat.py           Melee combat resolution
│   │   │   ├── diplomacy.py        Stances, messaging, relationships
│   │   │   ├── fog_of_war.py       Per-civ visibility
│   │   │   ├── victory.py          Domination + score victory
│   │   │   ├── turn_resolver.py    End-of-turn bookkeeping
│   │   │   ├── intents.py          Strategic intent dataclasses (9 types)
│   │   │   ├── operations.py       Intents → Goals + Diplomacy + Directives
│   │   │   ├── directives.py       City/civ directives (queue, research)
│   │   │   ├── executor.py         Goals → primitive Actions (A*)
│   │   │   ├── serialize.py        GameState → JSON local view
│   │   │   ├── playthrough.py      Headless game loop + GoalSources
│   │   │   ├── openai_goals.py     OpenAI tool-use GoalSource
│   │   │   ├── human_source.py     Human player input source
│   │   │   ├── improvements.py     Tile improvements (farm, mine, road)
│   │   │   ├── buildings.py        City buildings / structures
│   │   │   ├── economy.py          Gold income, upkeep, tile yields
│   │   │   ├── borders.py          Cultural border expansion
│   │   │   └── city_names.py       Procedural city name generator
│   │   └── main.py                 FastAPI app entry
│   ├── scripts/
│   │   └── run_playthrough.py      CLI playthrough runner
│   ├── tests/                      339+ tests, pytest
│   └── pyproject.toml
└── frontend/                       Next.js viewer (separate workstream)
```

---

## 3. Core Domain Model (`engine/models.py`)

All state objects are **frozen dataclasses** — every "mutation" returns a new
copy via `dataclasses.replace`.  This rules out hidden side effects and makes
the engine trivially testable.

| Type            | Purpose                                                             |
|-----------------|---------------------------------------------------------------------|
| `Hex`           | Axial coords `(q, r)` with derived `s = -q-r`                       |
| `Tile`          | `terrain`, `elevation`, `moisture`, `temperature`, `feature`, `resource`, `river` |
| `GameMap`       | `radius` + `dict[Hex, Tile]`                                        |
| `Unit`          | `id`, `owner`, `type`, `location`, `health`, `moves_remaining`     |
| `UnitStats`     | `max_health`, `attack`, `defense`, `moves`, `sight` (per UnitType)  |
| `City`          | `id`, `owner`, `name`, `location`, `population`, food/prod stores, queue |
| `Civilization`  | `id`, `name`, gold/science/culture, `known_techs`, `researching`, color, traits |
| `DiplomaticStance` | `PEACE` / `WAR` / `ALLIANCE`                                     |
| `GameState`     | `turn`, `map`, `civs`, `cities`, `units`, `seed`, `current_civ_idx`, `diplomacy`, `visibility` |

`GameState` is the single source of truth.  Helper methods: `units_for(civ_id)`,
`cities_for(civ_id)`, `current_civ()`, `stance_between(a, b)`.

---

## 4. Map Generation (`engine/map_generator.py`)

Layered, deterministic, seed-driven pipeline:

1. **Elevation** — OpenSimplex noise + center bias (so a continent forms),
   forced ocean on the outer hex ring.
2. **Temperature** — derived from latitude (`abs(r)/radius`) minus an
   elevation penalty.
3. **Moisture** — independent OpenSimplex noise (offset seed).
4. **Base biome** — `(elevation, temperature)` → ocean/coast/snow/tundra/hills/mountain/plains.
5. **Refine** — moisture promotes plains→grassland→forest, low moisture + heat → desert.
6. **Features** — forest/jungle/marsh/oasis placed probabilistically on
   compatible biomes.
7. **Resources** — terrain-compatible scatter with min spacing 2.
8. **Rivers** — traced downhill from the highest land tiles, marked on tiles
   they flow through (river adds +1 gold yield).

Same seed ⇒ identical map ⇒ reproducible playthroughs.

### Yields (`engine/terrain.py`)

`tile_yields(tile)` sums terrain + feature + resource + river bonuses into a
`Yields(food, production, gold)` triple.  Used by both the city tick and the
starting-position scorer.

---

## 5. Engine Modules

Each engine module is a pure function module:
`(state, args) -> new_state` — they raise typed errors (`MoveError`,
`CombatError`, `FoundError`, `ResearchError`) for *programmatic* misuse.
LLM-facing legality is handled separately by the validator.

| Module          | Entry point                                   |
|-----------------|------------------------------------------------|
| `movement.py`   | `move_unit(state, unit_id, dest)`             |
| `city_founding.py` | `found_city(state, unit_id, name)`         |
| `combat.py`     | `attack(state, attacker_id, defender_id)`     |
| `production.py` | `process_cities(state)` — runs each turn      |
| `research.py`   | `set_research(state, civ, tech)`, `tick_research(state)` |
| `fog_of_war.py` | `visible_tiles(state, civ_id) -> frozenset[Hex]` |
| `victory.py`    | `check_victory(state)` — domination + score   |
| `turn_resolver.py` | `end_turn(state)` — production + research + refresh moves |

### Additional modules

| Module            | Purpose                                                |
|-------------------|--------------------------------------------------------|
| `diplomacy.py`    | Diplomatic stances, messaging, relationship scores, truces |
| `intents.py`      | 9 strategic intent dataclasses (Expand, Scout, …)      |
| `operations.py`   | Translates Intents → Goals + DiplomaticActions + Directives |
| `directives.py`   | City/civ-level orders: queue production, set research  |
| `improvements.py` | Tile improvements: farm, mine, road                     |
| `buildings.py`    | City buildings and structures                           |
| `economy.py`      | Gold income, upkeep, tile yield calculations            |
| `borders.py`      | Cultural border expansion from cities                   |
| `city_names.py`   | Procedural civilization-themed city name generator      |
| `human_source.py` | Human player input source for GoalSource protocol       |

### Tech tree

20 techs across 4 tiers with prerequisites (e.g. `iron_working` needs
`bronze_working` needs `mining`).  Each city contributes `+2 science/turn`.

### Combat

Deterministic damage formula `max(1, 2*atk - def)` to defender,
`max(0, def_atk - atk_def)` to attacker.  Defender death moves attacker into
the vacated tile.  Attacker uses all remaining moves.

### Victory

- **Domination** — last civ standing.
- **Score** — first civ past `SCORE_THRESHOLD = 200`
  (`10·cities + 2·population + 3·techs`).

---

## 6. Action Validator (`api/actions.py`)

Returns a **Result type**, never raises:

```python
ValidationOk(action)     # legal, ready to apply
ValidationError(reason, code)   # rejected, machine-readable code
```

Action types: `MoveAction`, `FoundCityAction`, `BuildAction`,
`ResearchAction`, `AttackAction`, `EndTurnAction`.

Error codes (for LLM tool-call feedback): `not_your_turn`, `not_owner`,
`no_moves`, `off_map`, `not_adjacent`, `impassable`, `occupied`,
`wrong_unit_type`, `unfoundable_terrain`, `city_exists`, `not_at_war`,
`friendly_fire`, …

Turn ownership is checked first so out-of-turn calls get an immediate clear
rejection before any deeper validation.

---

## 7. Intents & Operations (`engine/intents.py`, `engine/operations.py`)

The LLM no longer emits Goals directly.  Instead it emits high-level
**Intents** — semantic declarations like "expand" or "engage Egypt".
The **operations layer** (`operations.py`) translates each Intent plus the
current `GameState` into one or more concrete Goals, DiplomaticActions,
and Directives.

### The 9 Intent Types (`intents.py`)

| Intent           | Purpose                                                     |
|------------------|-------------------------------------------------------------|
| `Expand`         | Found a city (settler + site picked deterministically)      |
| `Scout`          | Explore unknown territory                                   |
| `Engage`         | Wage war on a target civ (auto-declares war if needed)      |
| `Reinforce`      | March a military unit toward a friendly position            |
| `Speak`          | Send a diplomatic message to another leader                 |
| `AdjustStance`   | Set diplomatic stance (peace/war/alliance)                   |
| `Build`          | Queue a unit at a city                                      |
| `Research`       | Set the civ's currently-researching tech                    |
| `Improve`        | Send a worker to build a tile improvement (farm/mine/road)  |

### Operations Layer (`operations.py`)

`resolve_intents(state, civ_id, intents) → Decisions` is a pure function that:
- Picks the best unit for each intent (closest-to-target, lowest-id tiebreak)
- Auto-declares war before `Engage` if not already at war
- Drops self-targeted `Speak` / `AdjustStance` / `Engage`
- Emits `MoveTo`, `FoundCityNear`, `AttackUnit`, or `BuildImprovementGoal` goals
- Emits `SendMessage` / `SetStance` diplomatic actions
- Emits `QueueProduction` / `StartResearch` directives

---

## 8. Tactical Executor (`engine/executor.py`)

Translates concrete Goals into validated primitive actions.

**Goals** produced by the operations layer:
- `MoveTo(unit_id, target_hex)`
- `FoundCityNear(unit_id, target_hex, name)`
- `AttackUnit(attacker_id, target_id)`
- `BuildImprovementGoal(unit_id, target, improvement)`

**`find_path(state, start, goal)`** — A* on the hex grid using `heapq`.
Treats impassable terrain and occupied tiles as obstacles, but allows the
*goal* tile to be occupied (so attack pathing can land adjacent to a target).

**`execute_goal(state, civ_id, goal)`** — emits a `list[Action]`:
- `MoveTo` walks along the shortest path up to `unit.moves_remaining`.
- `FoundCityNear` walks then appends a `FoundCityAction` if it arrives.
- `AttackUnit` walks adjacent (reserving 1 move) then appends an `AttackAction`.
- `BuildImprovementGoal` walks a worker to the target tile then appends a `BuildImprovementAction`.

The executor never mutates state — it only proposes actions.

---

## 9. Local View Serializer (`engine/serialize.py`)

`local_view(state, civ_id) -> dict` produces the **single payload** consumed
by both:
- the LLM prompt (as JSON)
- the future frontend renderer

It applies fog-of-war: only tiles in `visible_tiles(state, civ_id)` are
included, and only units/cities on those tiles.  `known_civs` is derived from
ownership of those visible entities.

Output keys:
```
turn, seed, current_civ_id, map_radius,
self           — full data for the requesting civ
known_civs     — public info for met civs
visible_tiles  — list of tile dicts (q, r, terrain, yields, …)
visible_units  — list of unit dicts
visible_cities — list of city dicts
```

Deterministic ordering (sorted by coord/id) for diff-friendly outputs.

---

## 10. Playthrough Harness (`engine/playthrough.py`)

The full headless game loop.

### `GoalSource` Protocol

```python
class Decisions:
    goals: tuple[Goal, ...]
    diplomacy: tuple[DiplomaticAction, ...]
    directives: tuple[Directive, ...]

class GoalSource(Protocol):
    def decide(self, view: dict, civ_id: int) -> Decisions: ...
```

Implementations:

| Source              | Use case                                 |
|---------------------|------------------------------------------|
| `RandomGoalSource`  | Smoke testing — settlers found cities, military randomly walks |
| `ScriptedGoalSource`| Deterministic integration scenarios — goals keyed by `(turn, civ_id)` |
| `OpenAIGoalSource`  | Real LLM gameplay via tool-use API       |
| `HumanGoalSource`   | Human player input via API               |

### Loop

```
while state.turn <= max_turns:
    if check_victory(state): return
    civ = state.current_civ()
    view = local_view(state, civ.id)
    decisions = goal_source.decide(view, civ.id)
    # 1. Apply directives (queue production, set research)
    for directive in decisions.directives:
        state = apply_directive(state, civ.id, directive)
    # 2. Apply diplomatic actions
    for da in decisions.diplomacy:
        state = apply_diplomatic_action(state, da)
    # 3. Execute goals → actions → validate → apply
    for goal in decisions.goals:
        for action in execute_goal(state, civ.id, goal):
            result = validate(action, state, civ.id)
            if isinstance(result, ValidationOk):
                state = apply_action(state, action, civ.id)
    state = _advance_civ(state)   # cycles civ_idx, calls end_turn on wrap
```

`_advance_civ` skips eliminated civilizations and triggers `end_turn` (which
runs `process_cities` + `tick_research` + refreshes move points) once all
civs have played.

`apply_action` dispatches to the right engine module by action type.

Returns a `PlaythroughResult` with `turns_played`, `actions_applied`,
`actions_rejected`, `victory`, and the final `GameState`.

---

## 11. OpenAI Goal Source (`engine/openai_goals.py`)

Uses the OpenAI Chat Completions API with `tool_choice="required"`.

### 9 Intent Tools

The LLM calls high-level intent tools — it never picks unit IDs or coordinates.

| Tool             | Intent Class     | Description                                              |
|------------------|------------------|----------------------------------------------------------|
| `expand`         | `Expand`         | Found a city (engine picks settler + site)               |
| `scout`          | `Scout`          | Explore unknown territory                                |
| `engage`         | `Engage`         | Wage war on a civ (auto-declares if needed)              |
| `reinforce`      | `Reinforce`      | March a military unit toward a friendly position         |
| `speak`          | `Speak`          | Send a diplomatic message (chat/threat/offer_peace/…)    |
| `adjust_stance`  | `AdjustStance`   | Set peace/war/alliance with another civ                  |
| `build`          | `Build`          | Queue a unit at a city                                   |
| `research`       | `Research`       | Pick the tech to study                                   |
| `improve`        | `Improve`        | Send a worker to build farm/mine/road                    |

### Prompt & Memory

The LLM receives:
- A detailed system prompt (base tactical rules + per-leader persona).
- The user message is the JSON `local_view` payload augmented with:
  - `recent_actions` — last 8 turns of intents this leader issued
  - `recent_messages` — last 32 diplomatic messages this leader has seen
  - `last_turn_feedback` — engine rejection reasons from previous turn

### Pipeline

1. LLM calls intent tools → parsed into `Intent` dataclasses via `_parse_tool_call`
2. `bind_state()` provides the live `GameState` (called each turn by playthrough loop)
3. `resolve_intents(state, civ_id, intents)` → `Decisions(goals, diplomacy, directives)`
4. Playthrough loop executes goals, applies diplomatic actions and directives

Tool-call parse errors (bad JSON, unknown tool name, invalid enum values) are
logged and degrade to "no intents this turn" rather than crashing the loop.

Configurable: `model` (default `gpt-5.4-mini`), `temperature` (default 0.7),
explicit `api_key` (else `OPENAI_API_KEY` from env), `persona` (per-leader
prompt), `memory_turns` (default 8).

---

## 12. HTTP Layer (`app/api/routers/`)

FastAPI surface for the future frontend:

| Endpoint                        | Purpose                              |
|---------------------------------|--------------------------------------|
| `POST /games`                   | Create a new game (radius, seed)     |
| `GET /games/{game_id}`          | Fetch full state                     |
| `POST /games/{game_id}/turns/end` | End-of-turn tick                   |
| `POST /games/{game_id}/actions/*` | Apply player actions               |

Backed by an in-memory `store.py` (single-process, ephemeral) — fine for
demos and tests, would swap for persistent storage in production.

---

## 13. Testing

`pytest` with `unit` / `integration` markers.  339+ tests covering:

- Hex math, terrain yields, map gen invariants
- Movement, founding, combat, production, research edge cases
- Diplomacy: stances, messaging, relationships, truces
- Tile improvements (farm, mine, road)
- City buildings, borders, economy
- Fog of war + serializer determinism
- Validator rejection codes
- A* pathfinding (open map, blocked, impassable)
- Intents → operations resolution
- Random + scripted full-loop playthroughs
- OpenAI source with mocked client (no real API calls in CI)

Run:
```bash
cd backend
.venv/bin/python -m pytest -q
```

---

## 14. Design Decisions Worth Knowing

1. **Three-layer AI** — the LLM emits *intents* (semantic), the operations
   layer resolves them into *goals* (concrete unit/target pairs), and the
   executor produces *actions* (primitive moves).  This keeps tool calls
   compact, hides hex-math grunt work from the model, and gives the validator
   a single sane place to enforce rules.
2. **Result types over exceptions for LLM-facing code** — the validator must
   be safe to call on garbage input from a model, so `ValidationError`
   carries a machine-readable code instead of bubbling a stack trace.
3. **Frozen everything** — every state-mutating function returns a new
   `GameState`.  Trivial undo, trivial parallel evaluation, trivial replay.
4. **Single serializer for LLM + frontend** — `local_view` is the only thing
   that converts `GameState` into something external; both consumers speak
   the same fog-filtered JSON dialect.
5. **Seed in state, not just in map** — playthroughs are reproducible from
   `(seed, goal_source_seed)` pairs.

---

## 15. What's Not Built Yet

- **Replay/trace logging** — playthrough events go to `logging` at DEBUG;
  no structured trace artifact for diffing runs.
- **Token/cost telemetry** for OpenAI runs.
- **Persistent store** — games live in-memory only (in-memory `GameStore`
  with threading lock).
- **Frontend wiring** — the renderer consumes `local_view` JSON but isn't
  fully hooked up to the live engine yet.

---

## 16. Quick Start

```bash
# Test suite
cd backend
.venv/bin/python -m pytest -q

# Random AI playthrough
.venv/bin/python -m scripts.run_playthrough --seed 42 --turns 20

# OpenAI playthrough
export OPENAI_API_KEY=sk-...
.venv/bin/python -m scripts.run_playthrough --source openai --model gpt-5.4-mini --turns 10

# HTTP server
.venv/bin/uvicorn app.main:app --reload
```

---

## 17. Where to Find Details

This document synthesizes the overall system architecture. For authoritative details on specific domains, follow the links down to subproject documentation.

### Backend (Game Engine & LLM Integration)
- **[API Reference](../backend/docs/API_REFERENCE.md)** — All 16 REST endpoints, DTOs, error codes
- **[Backend Config](../backend/docs/BACKEND_CONFIG.md)** — Environment variables, settings, OpenAI configuration
- **[Gameplay Reference](../GAMEPLAY.md)** — Complete game mechanics (units, cities, combat, tech tree)
- **Source code**: `backend/app/engine/` — pure-functional engine modules

### Frontend (UI & Asset Resolution)
- **[Frontend Architecture](../frontend/docs/FRONTEND_ARCHITECTURE.md)** — Component tree, state management, Next.js structure
- **[UI Guide](../frontend/docs/UI_GUIDE.md)** — Panel lifecycle, map rendering, diplomatic audience
- **[Asset Integration](ASSET_INTEGRATION.md)** — Asset service contract, manifest resolution, fallback behavior
- **Source code**: `frontend/app/`, `frontend/components/`, `frontend/lib/`

### Asset Server (Generative Pipeline)
- **[Asset Server Docs Index](../assetserver/docs/INDEX.md)** — Entry point for all asset server documentation
- **[Project Report](../assetserver/docs/project-report.md)** — Comprehensive technical report on the DiT pipeline
- **[Image Generation Pipeline](../assetserver/docs/pipeline/image-generation-pipeline.md)** — DiT mechanics, pipeline stages, post-processing
- **[Server API](../assetserver/docs/guides/server-api.md)** — Endpoint reference for 35 asset endpoints
- **Source code**: `assetserver/src/`

### Training Pipeline (LoRA Fine-Tuning)
- **[Model Card](../dataset-gen-train/docs/MODEL_CARD.md)** — Base model, LoRA architecture, published weights
- **[Dataset Card](../dataset-gen-train/docs/DATASET_CARD.md)** — Training dataset composition and curation
- **[Experiment Design](../dataset-gen-train/docs/experiment-design.md)** — 6-experiment matrix, hyperparameters
- **Source code**: `dataset-gen-train/src/`

### Report Traceability
- **[Claim Traceability Matrix](report/TRACEABILITY.md)** — Every quantitative claim in the IEEE report mapped to its verifiable source
