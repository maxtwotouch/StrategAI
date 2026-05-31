# Architecture

AI Civilization-style game with a deterministic Python game engine driven by
LLM-emitted strategic goals.  This document summarizes the system as it stands
today (151 tests green, end-to-end playthroughs runnable).

---

## 1. High-Level Design

The system is split into three layers:

```
┌─────────────────────────────────────────────────────────┐
│  STRATEGIC LAYER     (LLM via OpenAI tool-use API)      │
│  Sees fog-filtered local view → emits Goals             │
└──────────────────────┬──────────────────────────────────┘
                       │ Goal (MoveTo / FoundCityNear / AttackUnit)
                       ▼
┌─────────────────────────────────────────────────────────┐
│  TACTICAL LAYER      (deterministic Python)             │
│  A* pathfinding, move-budget, occupancy → Actions       │
└──────────────────────┬──────────────────────────────────┘
                       │ Action (Move / FoundCity / Attack / …)
                       ▼
┌─────────────────────────────────────────────────────────┐
│  VALIDATOR + ENGINE  (pure functional, immutable state) │
│  Legality check → apply → new GameState                 │
└─────────────────────────────────────────────────────────┘
```

Key principle: the LLM never touches `GameState` directly.  Every LLM
intent passes through the executor (which knows pathfinding rules) and the
validator (which knows game rules) before any state mutation.

---

## 2. Repository Layout

```
INF-3600/
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
│   │   │   ├── fog_of_war.py       Per-civ visibility
│   │   │   ├── victory.py          Domination + score victory
│   │   │   ├── turn_resolver.py    End-of-turn bookkeeping
│   │   │   ├── executor.py         Goals → primitive Actions (A*)
│   │   │   ├── serialize.py        GameState → JSON local view
│   │   │   ├── playthrough.py      Headless game loop + GoalSources
│   │   │   └── openai_goals.py     OpenAI tool-use GoalSource
│   │   └── main.py                 FastAPI app entry
│   ├── scripts/
│   │   └── run_playthrough.py      CLI playthrough runner
│   ├── tests/                      151 tests, pytest
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

## 7. Tactical Executor (`engine/executor.py`)

Translates strategic goals into validated primitive actions.

**Goals** the LLM can express:
- `MoveTo(unit_id, target_hex)`
- `FoundCityNear(unit_id, target_hex, name)`
- `AttackUnit(attacker_id, target_id)`

**`find_path(state, start, goal)`** — A* on the hex grid using `heapq`.
Treats impassable terrain and occupied tiles as obstacles, but allows the
*goal* tile to be occupied (so attack pathing can land adjacent to a target).

**`execute_goal(state, civ_id, goal)`** — emits a `list[Action]`:
- `MoveTo` walks along the shortest path up to `unit.moves_remaining`.
- `FoundCityNear` walks then appends a `FoundCityAction` if it arrives.
- `AttackUnit` walks adjacent (reserving 1 move) then appends an `AttackAction`.

The executor never mutates state — it only proposes actions.

---

## 8. Local View Serializer (`engine/serialize.py`)

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

## 9. Playthrough Harness (`engine/playthrough.py`)

The full headless game loop.

### `GoalSource` Protocol

```python
class GoalSource(Protocol):
    def goals(self, view: dict, civ_id: int) -> list[Goal]: ...
```

Implementations:

| Source              | Use case                                 |
|---------------------|------------------------------------------|
| `RandomGoalSource`  | Smoke testing — settlers found cities, military randomly walks |
| `ScriptedGoalSource`| Deterministic integration scenarios — goals keyed by `(turn, civ_id)` |
| `OpenAIGoalSource`  | Real LLM gameplay via tool-use API       |

### Loop

```
while state.turn <= max_turns:
    if check_victory(state): return
    civ = state.current_civ()
    view = local_view(state, civ.id)
    for goal in goal_source.goals(view, civ.id):
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

## 10. OpenAI Goal Source (`engine/openai_goals.py`)

Uses the OpenAI Chat Completions API with `tool_choice="required"`.

Three tools mirror the Goal types: `move_to`, `found_city_near`, `attack_unit`.
Each takes integer `unit_id` and target `(q, r)` (and `name` for founding).

The LLM receives:
- A static system prompt describing the game and strategy hints.
- The user message is the JSON `local_view` payload.

Tool calls are parsed back into `Goal` objects.  Errors (API failure, bad
JSON, unknown tool name) are logged and degrade to "no goals this turn"
rather than crashing the loop.

Configurable: `model` (default `gpt-4o-mini`), `temperature` (default 0.7),
explicit `api_key` (else `OPENAI_API_KEY` from env).

---

## 11. HTTP Layer (`app/api/routers/`)

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

## 12. Testing

`pytest` with `unit` / `integration` markers.  151 tests covering:

- Hex math, terrain yields, map gen invariants
- Movement, founding, combat, production, research edge cases
- Fog of war + serializer determinism
- Validator rejection codes
- A* pathfinding (open map, blocked, impassable)
- Random + scripted full-loop playthroughs
- OpenAI source with mocked client (no real API calls in CI)

Run:
```bash
cd backend
.venv/bin/python -m pytest -q
```

---

## 13. Design Decisions Worth Knowing

1. **Two-layer AI** — letting the LLM emit *goals* not *primitive actions*
   keeps tool calls compact, hides hex-math grunt work from the model, and
   gives the validator a single sane place to enforce rules.
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

## 14. What's Not Built Yet

- **Production / research as Goals** — engine supports queues + research,
  but there's no `BuildUnit` / `Research` Goal type yet, so the LLM can't
  drive them.
- **Replay/trace logging** — playthrough events go to `logging` at DEBUG;
  no structured trace artifact for diffing runs.
- **Token/cost telemetry** for OpenAI runs.
- **Diplomacy actions** — stance is in state, but no actions to declare
  war / make peace.
- **Persistent store** — games live in-memory only.
- **Frontend wiring** — the renderer consumes `local_view` JSON but isn't
  hooked up to the live engine yet.

---

## 15. Quick Start

```bash
# Test suite
cd backend
.venv/bin/python -m pytest -q

# Random AI playthrough
.venv/bin/python -m scripts.run_playthrough --seed 42 --turns 20

# OpenAI playthrough
export OPENAI_API_KEY=sk-...
.venv/bin/python -m scripts.run_playthrough --source openai --model gpt-4o-mini --turns 10

# HTTP server
.venv/bin/uvicorn app.main:app --reload
```
