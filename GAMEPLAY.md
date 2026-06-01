# StrategAI — Gameplay Reference

> **Last Validated: 2026-05-31** — cross-referenced against `backend/app/engine/` source.

Everything a player or designer needs to know about how the game works. Numbers
come directly from the engine (`backend/app/engine/`) and stay in sync with
the rules the code enforces.

---

## 1. Match Setup

The Start Screen collects what you bring to the world. Defaults work; every
field is optional.

| Field | What it does | Default |
|---|---|---|
| **Civilization Name** | Your civ's name on the map and in the standings. | `Athens` |
| **Leader Name** | Your sovereign's name (shown in the Empire Badge, intro, audience). | _empty → uses Civilization Name_ |
| **Archetype** | One of 8 leader vocabularies: Warrior King/Queen, Philosopher King, Merchant Prince, Spiritual Leader, Diplomat, Tyrant, Visionary. Drives the leader's splash art prompt. | `Philosopher King` |
| **Culture** | One of 12 cultural prompts: Medieval European, Classical Greek, Ancient Egyptian, East Asian Imperial, Nordic Viking, etc. Drives splash/profile art and city-building style. | `Medieval European` |
| **Leader Appearance** | Free-text physical description (50–800 chars to take effect). Becomes the literal prompt the asset service generates from. Blank → a neutral default. | _empty_ |
| **Map Radius** | Half-width of the square map (`r=20` → 41×41 tiles). **Backend default is 8** (`game_factory.py:new_game(radius=8)`); the frontend initializer overrides this to 20. | `20` (frontend), `8` (backend) |

The seed is randomized each "Begin Campaign" so two consecutive games on the
same settings produce different maps and leader art.

After clicking **Begin Campaign**:

1. The game backend builds the map and places four civs (you + three AI).
2. The frontend's asset resolver fans out to the asset service (terrain, unit,
   structure, leader splash + profile, elevation overlays). Fallback logic:
   `frontend/lib/hex.ts` (built-in colors/glyphs) and
   `frontend/lib/assetManifest.ts` (null resolution when the asset server is
   unreachable).
3. The intro screen plays — full-bleed splash, civ name, leader name, an epic
   line, "Begin the Age" CTA.
4. The war room reveals the map.

> **Note on asset integration**: The frontend's asset resolver maps game entities
> to generative pixel-art assets. Fallback logic lives in
> `frontend/lib/hex.ts` (built-in colors/glyphs for missing terrain assets) and
> `frontend/lib/assetManifest.ts` (null resolution when the asset server is
> unreachable). See [`docs/ASSET_INTEGRATION.md`](docs/ASSET_INTEGRATION.md) for the full asset service contract.

---

## 2. The Civilizations

Backend roster lives in `backend/app/api/game_factory.py`. Three AI civs ship by
default:

| Civ | Leader | Traits | Personality |
|---|---|---|---|
| Mongolia | Genghis Khan | aggressive, vindictive | Conquest-first. Remembers insults; declares war within two turns of being threatened. Respects strength. |
| Egypt | Cleopatra | diplomatic, opportunistic | Plays factions against each other; flatters allies, mocks pretenders. Avoids first strikes unless cornered. |
| India | Mahatma Gandhi | peaceful, scientific | Science + culture victories. Responds to threats with protest first. Welcomes alliances. |

The fourth seat is the **player** (`Athens` by default). Each AI civ has a full
persona prompt that feeds the LLM goal source — see
`backend/app/engine/openai_goals.py`.

---

## 3. The Map

| Concept | Detail |
|---|---|
| Coordinate system | Square grid using `(q, r)` integer axes (legacy hex naming). |
| Terrain types | 10: `ocean`, `coast`, `plains`, `grassland`, `forest`, `hills`, `mountain`, `desert`, `tundra`, `snow`. |
| Features | `forest`, `jungle`, `marsh`, `oasis` (overlay glyphs on the base tile). |
| Resources | `wheat`, `cattle`, `fish`, `iron`, `horses`, `coal`, `gems`, `silk`, `spices` (tile bonuses). |
| Rivers | Boolean on a tile — boosts defense for any unit standing on it. |
| Fog of war | Tiles not currently in any of your unit/city sight radii are dimmed. The frontend caches "explored" tiles separately so you can still see the terrain you've discovered, even when fogged. |

### Passable vs impassable

- **Impassable**: ocean, mountain, snow (`IMPASSABLE_TERRAIN`). No unit type can cross these — including scouts (no unit-type override exists).
- **Passable**: coast, plains, grassland, forest, hills, desert, tundra. Land units CAN enter coast tiles.
- See `backend/app/engine/terrain.py:is_passable` for the canonical rules.

---

## 4. Units

Stats live in `UNIT_STATS` and `UNIT_BUILD_COST` (`backend/app/engine/models.py`).

| Unit | HP | Attack | Defense | Moves | Sight | Build cost | Tech required |
|---|---:|---:|---:|---:|---:|---:|---|
| Settler | 10 | 0 | 1 | 2 | 2 | 15 | — |
| Warrior | 20 | 4 | 3 | 2 | 2 | 10 | — |
| Scout | 10 | 1 | 1 | 4 | 3 | 8 | — |
| Worker | 10 | 0 | 1 | 2 | 1 | 10 | — |
| Archer | 20 | 5 | 2 | 2 | 2 | 15 | `archery` |
| Horseman | 20 | 6 | 3 | 4 | 2 | 22 | `horseback_riding` |
| Swordsman | 25 | 7 | 5 | 2 | 2 | 30 | `iron_working` |

### Special actions

- **Found City** (Settler only) — consumes the unit; spawns a city tile.
  Must stand on dry, owned-or-neutral land with no city in the surrounding
  tiles.
- **Build Improvement** (Worker only) — issue a `Farm`, `Mine`, or `Road`
  order on the unit's current tile. Worker is occupied until the work order
  completes; see §8.
- **Move** — click an adjacent tile while a unit is selected.
- **Attack** — click an adjacent enemy unit (requires `war` stance — peace
  attacks are rejected with an explanatory toast).

### Gold

Every civilization gains a flat **+5 gold per turn**. Units have no upkeep,
and there is no bankruptcy disbanding.

### Healing rate (per turn, when not acting)

- On a tile your civ owns: **+4 HP**.
- On unowned / neutral land: **+2 HP**.
- On hostile-controlled tile: **+1 HP** (`HEAL_ENEMY_TERRITORY = 1`).

---

## 5. Cities

```
class City:
  population, food_stored, production_stored,
  health, max_health (20),
  buildings: frozenset[BuildingType],
  purchased_structures: frozenset[str],
  structures: tuple[CityStructure, ...] on GameState,
  production_queue: tuple[BuildItem, ...],
  border_radius (1 → 2 → 3),
  culture_stored,
  worked_tiles: frozenset[Hex],
```

### Per-turn yields

For each city, accumulated from worked tiles + base yields + building bonuses
+ purchased-structure bonuses:

| Yield | Formula | Notes |
|---|---|---|
| **Food** | `2 + Σ worked-tile food + city_food_bonus(buildings)` | Surplus feeds growth: when `food_stored ≥ 10 × population`, population grows by 1 and `food_stored` resets to 0. |
| **Production** | `1 + Σ worked-tile production + city_production_bonus(buildings) + 2 × len(purchased_structures)` | Drains into queue head each turn until item completes. |
| **Culture** | `1 + Σ culture bonuses` | Accumulates in `culture_stored`. Border ring grows at thresholds — see below. |
| **Gold** | Flat +5 gold per civilization per turn. Tile/market gold is still serialized for inspection, but the web economy currently uses the flat rule. | Pooled across civ, not per-city. |
| **Science** | 2 per city + library bonus. | Pooled across civ. |

### Border growth (culture)

| Border ring | Culture cost to advance | Effect |
|---|---:|---|
| 1 (default) | 10 culture | City center only. |
| 2 | 30 culture | One-tile ring claimed. |
| 3 (max) | _further accumulation has no effect_ | Two-tile ring claimed. |

### City health & damage

- Max HP **20**; damage from attacks against the city tile.
- A city at 0 HP becomes capturable — an attacker who moves into the tile
  takes control (`attack-city` endpoint).
- Captured cities keep their building list; the new owner picks production.

---

## 6. Production Queue

Queue items are `BuildItem`s (unit or building). The queue is a tuple — head
is what's currently building, the rest are waiting.

Per turn:

1. The city accumulates `production_yield` into `production_stored`.
2. If `production_stored ≥ cost_of(queue[0])`, the head completes:
   - Unit → spawned in the city tile (or adjacent if occupied).
   - Building → added to `city.buildings`.
3. `production_stored` overflow rolls to the next item (no waste).

### Queue mutations the player can issue

| Action | Endpoint | What it does |
|---|---|---|
| Append | `POST /actions/build` | Add unit or building to the tail. |
| Cancel | `POST /actions/cancel-build` | Remove an item by index. **Cancelling index 0 forfeits accumulated `production_stored`**, since that progress was earmarked for the head. Cancelling later positions is free. |

In the UI: open a city → **Production Queue** section. Each row has a red
`×` cancel button (disabled when it's not your turn or another request is in
flight). The hover tooltip on the head row warns about the forfeit.

---

## 7. Buildings & Gold-Purchased Structures

### A. Queue-built buildings (cost production over multiple turns)

Defined in `backend/app/engine/buildings.py`.

| Building | Production cost | Prereq | Effect |
|---|---:|---|---|
| Granary | 20 | `pottery` | +1 food/turn |
| Monument | 18 | — | +1 culture/turn |
| Library | 24 | `writing` | +2 science/turn |
| Barracks | 22 | `bronze_working` | +3 HP to units trained in this city |
| Market | 24 | `currency` | +2 gold/turn |

Queue them via the **Build Order** list in the City Drawer.

### B. Gold-purchased structures (drag-and-drop placement)

A separate mechanism introduced for the asset-API integration. Categories
mirror the asset service's `StructureCategory`. These are not queue-built
buildings; they are instant gold purchases placed onto a map tile.

| Category | Asset-API style | Gold cost | Effect |
|---|---|---:|---|
| Production | workshop / forge / mill | 15 | +2 production/turn |
| Fortification | walls / keep / gatehouse | 15 | +2 production/turn (visual differentiator) |
| Housing | townhouse / longhouse / manor | 15 | +2 production/turn |
| Sacred | temple / shrine / cathedral | 15 | +2 production/turn |

Per city you can buy **one of each category** (max 4). Drag a structure row
from the **Structures** section in the City Drawer onto a passable, empty tile
inside that city's borders. The backend validates the drop target and stores a
`CityStructure(city_id, owner, category, location)` in `GameState.structures`.
The city also records the owned category in `purchased_structures` so the
production bonus can be computed as `2 × len(purchased_structures)`.

Invalid drops are rejected if the tile is outside the city's borders,
impassable, already has a city/unit/structure, or the category is already
owned by that city. See `_purchase_structure` in
`backend/app/engine/directives.py`.

---

## 8. Workers, Improvements & Roads

Improvements are issued by a Worker via `POST /actions/improve`.

| Improvement | Eligible terrain | Build time | Effect |
|---|---|---:|---|
| Farm | grassland, plains | 3 turns | +1 food on that tile |
| Mine | hills | 4 turns | +1 production on that tile |
| Road | any passable | 2 turns | Free movement between adjacent road tiles |

The Worker is occupied for the duration. Status shown in the unit chip
(small overlay on the unit's tile: improvement glyph + turns remaining).

---

## 9. Tech Tree

20 techs across 4 tiers (5 Tier 1, 6 Tier 2, 5 Tier 3, 4 Tier 4;
`backend/app/engine/research.py`). Science is pooled across the civilization;
**2 science/city/turn baseline**, plus Library bonus.

```
Tier 1 (no prerequisites)
  ─ Agriculture        (20 sci)
  ─ Pottery            (20)
  ─ Mining             (25)
  ─ Fishing            (20)
  ─ Archery            (25) → unlocks Archer

Tier 2
  ─ Animal Husbandry   (35)  ← Agriculture
  ─ Trapping           (35)  ← Pottery
  ─ Bronze Working     (55)  ← Mining           → unlocks Barracks
  ─ Sailing            (45)  ← Fishing
  ─ The Wheel          (55)  ← Animal Husbandry
  ─ Masonry            (55)  ← Mining

Tier 3
  ─ Writing            (75)  ← Pottery          → unlocks Library
  ─ Horseback Riding   (70)  ← Animal Husbandry → unlocks Horseman
  ─ Currency           (80)  ← Bronze Working   → unlocks Market
  ─ Calendar           (70)  ← Pottery + Agriculture
  ─ Iron Working      (120)  ← Bronze Working   → unlocks Swordsman

Tier 4
  ─ Mathematics       (110)  ← Currency
  ─ Construction      (100)  ← Masonry
  ─ Philosophy        (120)  ← Writing
  ─ Astronomy         (130)  ← Mathematics + Sailing
```

Set your civ's current research via `POST /actions/research`. The Research
panel in the right rail shows available techs (filtered to those whose
prerequisites are met).

---

## 10. Combat

### Attack resolution (`backend/app/engine/combat.py`)

Combat is **purely deterministic** — no RNG anywhere.
- **Damage to defender**: `max(1, 2 × attacker_attack − effective_defense)`
- **Damage to attacker**: `max(0, defender_attack − attacker_defense)`

The defender benefits from terrain (see below).

### Terrain defense multiplier

Each qualifying condition multiplies the defender's defense by 1.25:

- Standing on **hills** (mountains are impassable — no unit can stand on a mountain tile).
- Standing on **forest**, **jungle**, **marsh**, or in a **forest** feature.
- Tile has a **river** (forces attackers to cross).

The multiplier caps at **1.6×** (`MAX_TERRAIN_DEFENSE_MULT`). So a Swordsman
(defense 5) on hills+river+forest gets `5 × 1.6 = 8` effective defense, not
`5 × 1.25³ ≈ 9.77`.

### Stance enforcement

Attacks require `war` stance with the defender's owner. The frontend's
`canAttackOwner` check surfaces a toast if you try to attack while at peace.
City capture requires `attack-city` against a city already at 0 HP.

---

## 11. Diplomacy

### Stances (`DiplomaticStance`)

`peace` (default), `war`, `alliance`. Plus an orthogonal **truce flag** that
disables hostile actions for 10 turns (`TRUCE_DURATION_TURNS`).

### Relationships

Integer score per ordered pair `(civ_a, civ_b)`. Range typically `-100…+100`.
Labels:

| Score | Label | Color in UI |
|---|---|---|
| ≤ −60 | Furious | red |
| ≤ −30 | Hostile | red |
| ≤ −10 | Cold | warm grey |
| −9…+9 | Neutral | warm grey |
| 10…29 | Warm | gold |
| 30…59 | Friendly | green |
| ≥ 60 | Devoted | green |

Relationships shift via `DiplomaticEvent`s — see `backend/app/engine/diplomacy.py`
and the deltas applied by message kinds (e.g. `threat: -10`, `declare_war: -50`).

### Message kinds (`MessageKind`)

- `chat` — free-form, no automatic effect
- `threat` — relationship penalty
- `offer_peace` / `accept_peace` — pair to end a war (triggers 10-turn truce)
- `declare_war` — switches stance to war (blocked while truce_active)
- `propose_alliance` / `accept_alliance` — pair to form an alliance
- `reject` — refuses the most recent offer

### Truces

After a peace is accepted, a **10-turn truce** is set on the relationship.
While `truce_active`, the UI removes "Declare War" and "Threat" from the
composer's tone dropdown.

### Diplomatic Audience (frontend)

Clicking a leader avatar in the **Diplomatic Ribbon** on the right edge of
the map opens a full-screen Diplomatic Audience overlay backed by the
rival's splash art. See
[frontend/docs/UI_GUIDE.md §4.1](frontend/docs/UI_GUIDE.md#41-diplomatic-ribbon-met-leader-portraits-on-the-map)
and [frontend/docs/UI_GUIDE.md §5 Diplomatic Audience](frontend/docs/UI_GUIDE.md#diplomatic-audience-full-screen-overlay).

---

## 12. Turn System

Turns alternate between the human and the three AI civs.

1. Human takes whatever actions they want (move units, found cities, queue
   production, send messages, research, etc.) — each is an immediate API
   call that returns the updated `GameStateOut`.
2. Human clicks **End Turn** → `POST /games/{id}/turn/resolve`.
3. The backend runs each AI civ's `OpenAIGoalSource` to emit Goals, lowers
   them through the tactical layer to Actions, validates and applies each,
   then ticks every city (production, growth, culture, healing) and resolves
   any active work orders.
4. The returned `GameState` reflects the next human turn. The frontend diffs
   the prev/next state to surface **TurnEvent**s in the Chronicle and a brief
   banner.

`isHumanTurn` is checked at the frontend before issuing actions; the backend
also enforces turn ownership on the API boundary.

---

## 13. Victory

Score-based. Default threshold is **200** (`SCORE_THRESHOLD`).
`civ.score` is calculated by `backend/app/engine/victory.py:civ_score`:
`10 × cities + 2 × population + 3 × known_techs`.
(No "cultural standing" term exists in the engine.)

First civ to cross the threshold wins; the UI shows a "you reached the goal"
banner. (Defeat conditions and proper end-game screens are planned but not yet
implemented.)

---

## 14. Reference: Source Files

| Topic | File |
|---|---|
| Civ + map definitions | `backend/app/api/game_factory.py` |
| All immutable models | `backend/app/engine/models.py` |
| Map generation | `backend/app/engine/map_generator.py` |
| City yields & production tick | `backend/app/engine/production.py` |
| Buildings + structures | `backend/app/engine/buildings.py` |
| Combat | `backend/app/engine/combat.py` |
| Movement & healing | `backend/app/engine/movement.py` |
| Diplomacy | `backend/app/engine/diplomacy.py` |
| Tech tree | `backend/app/engine/research.py` |
| Improvements | `backend/app/engine/improvements.py` |
| Score | `backend/app/engine/victory.py` |
| LLM goal source | `backend/app/engine/openai_goals.py` |
| Turn orchestration | `backend/app/engine/turn_resolver.py`, `playthrough.py` |
| Directives (queue, research, structures) | `backend/app/engine/directives.py` |
| HTTP routes | `backend/app/api/routers/*.py` |
| Serializer | `backend/app/engine/serialize.py` |

## 15. Where to Find Details

This document describes game mechanics. For implementation details and related systems:

- **[Backend API Reference](backend/docs/API_REFERENCE.md)** — All game actions as REST endpoints with DTOs and error codes
- **[Backend Config](backend/docs/BACKEND_CONFIG.md)** — LLM model selection, game parameters, environment setup
- **[Architecture Overview](docs/ARCHITECTURE.md)** — How the three-layer engine (Strategic → Tactical → Validator) processes these mechanics
- **[UI Guide](frontend/docs/UI_GUIDE.md)** — How these mechanics surface in the frontend (panels, drawers, map interactions)
- **[Asset Integration](docs/ASSET_INTEGRATION.md)** — How game entities (units, cities, terrain) map to generative pixel-art assets. See also `frontend/lib/hex.ts` and `frontend/lib/assetManifest.ts` for fallback logic
- **[Report Traceability](docs/report/TRACEABILITY.md)** — Claims about game mechanics mapped to verifiable sources
