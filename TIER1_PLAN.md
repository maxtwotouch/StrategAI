# Tier 1 Implementation Plan — Core Mechanics

This document specifies the five Tier-1 mechanics that turn the current prototype
into a game that feels like an early-Civ prototype. Each section lists data-model
diffs, engine functions, validator codes, serializer changes, HTTP impact, and
test cases.

Status: **all five items shipped**. Test suite at 315 passing (was 252 baseline,
+63 new tests). One pre-existing playthrough flake remains (unrelated to Tier 1).

## Goals

- Close the largest gameplay gaps: dead gold, static yields, no healing, useless
  tech tree, no worker economy.
- Stay inside the existing pure-functional engine architecture (frozen
  dataclasses, `(state, args) → new state`, single serializer).
- One PR per item. Each ends with the test suite green and adds its own tests.

## Resolved cross-cutting decisions

1. **Border growth** — culture-only. The existing Monument building's culture
   bonus already feeds this; no Tier-1 dependency on additional buildings.
2. **Bankruptcy** — disband the oldest non-settler unit; clamp `gold` to 0;
   surface the event in the turn report. Standard early-Civ behavior.
3. **Worker placement** — manual. Player issues a `BuildImprovement` action with
   an explicit `(unit, improvement, target_tile)`. Auto-assignment is a later
   convenience.
4. **Heal-rate territory classification** — read from `GameState.tile_owner`:
   - tile owned by self → 4 HP/turn
   - tile unowned (key missing or `None`) → 2 HP/turn
   - tile owned by another civ → 1 HP/turn

## Cross-cutting implementation rules

- All new state on `GameState`, `City`, `Tile`, `Unit` stays as frozen
  dataclasses. Mutations go through `dataclasses.replace`.
- All new engine modules are pure `(state, args) → state`.
- New validator codes are added to `api/actions.py` `Result.error.code`.
  Keep them short, machine-readable, snake_case.
- New `local_view` keys are additive; the LLM tool schema is updated in
  `engine/openai_goals.py` only when new actions are introduced.
- Tests live in `backend/tests/test_<feature>.py`; mark integration tests with
  `pytest.mark.integration`.

---

## Item 1 — Tile ownership & worked tiles

### Data model

```python
# engine/models.py
@dataclass(frozen=True, slots=True)
class City:
    ...
    border_radius: int = 1
    culture_stored: int = 0
    worked_tiles: frozenset[Hex] = field(default_factory=frozenset)

@dataclass(frozen=True, slots=True)
class GameState:
    ...
    tile_owner: dict[Hex, int] = field(default_factory=dict)  # Hex → city_id
```

`tile_owner` is the authoritative claim map. `City.worked_tiles` is a subset of
its claimed tiles actively worked (capped at `population`). `border_radius`
grows from culture.

### New module — `engine/borders.py`

```python
def claimed_tiles(state, city) -> set[Hex]
def recompute_claims(state) -> GameState         # rebuilds tile_owner from cities
def grow_borders(state) -> GameState             # culture thresholds → radius
def auto_assign_workers(state) -> GameState      # greedy yield pick
def working_yields(state, city) -> Yields       # sum over worked + center
```

- **Conflict rule:** closer city wins; tie → lower `city_id` wins. Center is
  always owned by the city.
- **Culture thresholds:** `10 → radius 2`, `30 → radius 3` (cap).
- `working_yields` uses `terrain.tile_yields(tile)` (full feature + resource +
  river yield), fixing a latent bug where `production._city_tile_yields` ignored
  features and resources on the city center.

### Touched files

| File | Change |
|------|--------|
| `engine/models.py` | `City` and `GameState` fields above |
| `engine/borders.py` | new module |
| `engine/production.py::_city_tile_yields` | delegate to `borders.working_yields` |
| `engine/city_founding.py::found_city` | call `recompute_claims` after add |
| `engine/movement.py::move_unit` | call `recompute_claims` on city capture |
| `engine/turn_resolver.py::end_turn` | `grow_borders` then `auto_assign_workers` |
| `engine/serialize.py::local_view` | emit `tile_owner`, per-city `worked_tiles`, `border_radius`, `culture_stored` |
| `api/schemas.py` | `CityOut.border_radius`, `CityOut.worked_tiles`, `GameStateOut.tile_owner` |

### Validator codes — none new
Auto-assignment in Tier 1; manual worker placement is Tier 2.

### Tests

- `test_borders_new_city_claims_ring`
- `test_borders_contested_closer_wins`
- `test_borders_culture_grows_radius`
- `test_borders_capture_transfers_ownership`
- `test_workers_assigned_by_yield`
- `test_yields_scale_with_population`

**Size:** ~1.5 days.

---

## Item 2 — Gold economy

### Data model

Reuse `Civilization.gold`. Add upkeep tables and gold fields on buildings.

```python
# engine/models.py
UNIT_UPKEEP: dict[UnitType, int] = {
    UnitType.SETTLER: 1, UnitType.WARRIOR: 1, UnitType.SCOUT: 1,
    UnitType.WORKER:  1, UnitType.ARCHER:  1,
    UnitType.HORSEMAN: 2, UnitType.SWORDSMAN: 2,
}

# engine/buildings.py — extend BuildingDef
gold_upkeep: int = 0
gold_bonus:  int = 0
```

### New module — `engine/economy.py`

```python
def city_gold_income(state, city) -> int
def civ_gold_income(state, civ_id) -> int
def civ_gold_upkeep(state, civ_id) -> int
def tick_economy(state) -> GameState    # apply delta; bankruptcy → disband
```

**Bankruptcy rule:** if `gold_after < 0`, disband the oldest non-settler unit
owned by that civ, clamp `gold` to 0, append a `BankruptcyEvent` to the turn
report.

### Touched files

| File | Change |
|------|--------|
| `engine/economy.py` | new module |
| `engine/models.py` | `UNIT_UPKEEP` |
| `engine/buildings.py` | gold fields on `BuildingDef`; add `MARKET` (req `currency`, +2 gold) |
| `engine/turn_resolver.py::end_turn` | call `tick_economy` after `process_cities` |
| `engine/serialize.py` | `self.gold_income`, `self.gold_upkeep` |
| `api/schemas.py` | `CivOut.gold_income`, `CivOut.gold_upkeep` |

### Validator codes — none new
Unit purchasing is Tier 2 (`not_enough_gold`).

### Tests

- `test_economy_river_tile_generates_gold`
- `test_economy_unit_upkeep_deducted`
- `test_economy_bankruptcy_disbands_unit`
- `test_economy_market_increases_income`
- `test_economy_multi_city_sums`

**Size:** ~1 day. Depends on Item 1 for non-trivial city income.

---

## Item 3 — Healing & terrain defense

### Data model

```python
# engine/models.py
@dataclass(frozen=True, slots=True)
class Unit:
    ...
    acted_this_turn: bool = False
```

### Engine

```python
# engine/combat.py
def _terrain_defense_multiplier(state, defender) -> float
    # forest/jungle/marsh: 1.25 ; hills: 1.25 ; river edge: 1.25 ; else 1.0
    # multipliers stack multiplicatively, cap at 1.6

# engine/turn_resolver.py
def _heal_units(state) -> GameState
    # rate by tile_owner classification (own=4, unowned=2, enemy=1)
    # only if not acted_this_turn
```

### Touched files

| File | Change |
|------|--------|
| `engine/models.py` | `Unit.acted_this_turn` |
| `engine/combat.py` | apply multiplier; set `acted_this_turn` |
| `engine/movement.py` | set `acted_this_turn` |
| `engine/turn_resolver.py` | heal pass before refreshing moves; reset flag |
| `engine/serialize.py` | unit serializer includes `acted_this_turn` |

### Validator codes — none new

### Tests

- `test_heal_in_own_territory`
- `test_heal_in_unowned_neutral`
- `test_heal_in_enemy_territory`
- `test_no_heal_after_combat_same_turn`
- `test_heal_capped_at_max_health`
- `test_terrain_defense_forest_reduces_damage`
- `test_terrain_defense_hills_and_forest_stack_under_cap`

**Size:** ~0.5 day.

---

## Item 4 — Tech-gated units

### Data model

```python
# engine/models.py
class UnitType(str, Enum):
    SETTLER = "settler"
    WARRIOR = "warrior"
    SCOUT   = "scout"
    WORKER  = "worker"
    ARCHER  = "archer"
    HORSEMAN = "horseman"
    SWORDSMAN = "swordsman"

UNIT_STATS[UnitType.ARCHER]    = UnitStats(20, 5, 2, 2, 2)
UNIT_STATS[UnitType.HORSEMAN]  = UnitStats(20, 6, 3, 4, 2)
UNIT_STATS[UnitType.SWORDSMAN] = UnitStats(25, 7, 5, 2, 2)
UNIT_STATS[UnitType.WORKER]    = UnitStats(10, 0, 1, 2, 1)

UNIT_BUILD_COST[UnitType.ARCHER]    = 15
UNIT_BUILD_COST[UnitType.HORSEMAN]  = 22
UNIT_BUILD_COST[UnitType.SWORDSMAN] = 30
UNIT_BUILD_COST[UnitType.WORKER]    = 10
```

```python
# engine/research.py
UNIT_TECH_REQUIREMENTS = {
    UnitType.SETTLER: None, UnitType.WARRIOR: None, UnitType.SCOUT: None,
    UnitType.WORKER: None,
    UnitType.ARCHER:    "archery",
    UnitType.HORSEMAN:  "horseback_riding",
    UnitType.SWORDSMAN: "iron_working",
}
```

### Touched files

| File | Change |
|------|--------|
| `engine/models.py` | enum + stat tables |
| `engine/research.py` | requirements |
| `engine/directives.py::apply_directive` | reject queueing unresearched unit with `tech_not_researched` |
| `engine/operations.py::_do_build` | filter intents whose tech is missing |
| `engine/openai_goals.py` | extend `Build` tool schema enum |
| `engine/serialize.py` | `available_units` field per civ |
| `api/schemas.py` | accept new strings in `BuildRequest.unit_type` |

### Validator codes
- `tech_not_researched`

### Tests
- `test_build_archer_without_archery_rejected`
- `test_build_archer_after_research_succeeds`
- `test_horseman_has_4_moves`
- `test_swordsman_outdamages_warrior`
- `test_operations_drops_invalid_build_intent`
- `test_local_view_lists_available_units`

**Size:** ~0.5 day.

---

## Item 5 — Tile improvements + worker unit

### Data model

```python
# engine/terrain.py
class Improvement(str, Enum):
    FARM = "farm"
    MINE = "mine"
    ROAD = "road"

# engine/models.py
@dataclass(frozen=True, slots=True)
class Tile:
    ...
    improvement: Improvement | None = None

@dataclass(frozen=True, slots=True)
class Unit:
    ...
    work_order: tuple[Hex, Improvement] | None = None
    work_turns_remaining: int = 0
```

### Improvement effects (additive in `tile_yields`)

| Improvement | Terrain allowed         | Yield bonus    | Turns |
|-------------|-------------------------|----------------|-------|
| FARM        | plains, grassland       | +1 food        | 3     |
| MINE        | hills                   | +1 production  | 4     |
| ROAD        | any passable land       | (Tier-2 mvmt)  | 2     |

### New module — `engine/improvements.py`

```python
def start_improvement(state, worker_id, improvement) -> GameState
def cancel_improvement(state, worker_id) -> GameState
def tick_improvements(state) -> GameState
def can_improve(tile, improvement, owner_id, tile_owner_map) -> bool
```

### Touched files

| File | Change |
|------|--------|
| `engine/terrain.py` | `Improvement` enum + yields extension |
| `engine/models.py` | `Tile.improvement`, `Unit.work_order`, `Unit.work_turns_remaining` |
| `engine/improvements.py` | new module |
| `engine/movement.py::move_unit` | cancel `work_order` on move |
| `engine/turn_resolver.py::end_turn` | call `tick_improvements` before economy/research |
| `engine/intents.py` | `Improve(unit_id_hint, target, kind)` |
| `engine/operations.py` | `_do_improve` |
| `engine/executor.py` | new `BuildImprovementGoal`; path-then-start expansion |
| `api/actions.py` | `BuildImprovementAction` + validator |
| `api/routers/actions.py` | `POST /games/{id}/actions/improve` |
| `api/schemas.py` | `TileOut.improvement`, `UnitOut.work_order` |
| `engine/serialize.py` | tile + unit serializers include new fields |
| `engine/openai_goals.py` | new `build_improvement` tool |

### Validator codes
- `not_worker`
- `bad_terrain_for_improvement`
- `tile_already_improved`
- `not_in_own_borders`
- `worker_already_busy`

### Tests
- `test_worker_starts_farm_on_plains`
- `test_worker_completes_farm_after_3_turns`
- `test_worker_cannot_farm_hills`
- `test_worker_cannot_improve_unowned_tile`
- `test_worker_moving_cancels_work_order`
- `test_improve_intent_picks_idle_worker`
- `test_can_improve_skips_already_improved`

**Size:** ~1.5 days.

---

## Recommended implementation sequence

```
1. Item 1  Tile ownership          (foundation; Items 2 & 5 lean on it)
2. Item 3  Healing + terrain def   (smallest, low blast radius — quick win)
3. Item 4  Tech-gated units        (pure additions; no shape change)
4. Item 2  Gold economy            (uses Item 1's worked-tile yields)
5. Item 5  Workers + improvements  (touches every layer; do last)
```

Total expected test additions: **30–40 new tests**, taking the suite from 151 to
roughly 180–190 green.

## After Tier 1

Tier 2 (strategic depth): ranged combat, city walls + siege, movement cost per
terrain, remembered fog, happiness/growth caps.
Tier 3 (mid-game): naval game, wonders, trade routes, deeper diplomacy.
Tier 4 (polish): unit XP/promotions, tech yield bonuses, more victory paths.
Tier 5 (UX/architecture, can ship in parallel with Tier 2): pending-orders +
submit-turn batching, structured turn report, human local-view endpoint.
