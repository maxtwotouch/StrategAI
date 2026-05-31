# StrategAI Backend — API Reference

> **Base URL:** `http://localhost:8000`  
> **Content-Type:** `application/json`  
> **CORS:** All origins allowed  
> **Authentication:** None (localhost-only)  
> **Version:** 0.0.1

---

## Table of Contents

- [Overview](#overview)
- [Endpoints](#endpoints)
  - [Health Check](#health-check)
  - [Games](#games)
  - [Actions](#actions)
  - [Turns](#turns)
  - [Audio](#audio)
- [Data Transfer Objects (DTOs)](#data-transfer-objects-dtos)
  - [Request Bodies](#request-bodies)
  - [Response Shapes](#response-shapes)
- [Error Code Catalog](#error-code-catalog)

---

## Overview

The StrategAI backend exposes a REST API organized into four router modules:

| Router | Prefix | Endpoints |
|--------|--------|-----------|
| **Games** | `/games` | 2 — create & fetch game state |
| **Actions** | `/games/{game_id}/actions` | 10 — unit movement, combat, city management, diplomacy |
| **Turns** | `/games/{game_id}/turn` | 2 — advance human turn, resolve AI turns |
| **Audio** | `/audio` | 1 — generate AI-narrated intro MP3 |

All state-modifying endpoints return the full `GameStateOut` response so the frontend can re-render in a single round-trip.

---

## Endpoints

### Health Check

#### `GET /health`

Returns a simple liveness check.

**Parameters:** None

**Response `200`:**

```json
{
  "status": "ok"
}
```

**Errors:** None

**Example:**

```bash
curl http://localhost:8000/health
```

---

### Games

#### `POST /games`

Create a new game with a procedurally generated hex map and four civilizations (1 human + 3 AI).

**Request Body:** `CreateGameRequest`

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `radius` | `int` | `8` | `1–20` | Hex map radius in tiles |
| `seed` | `int` | `0` | — | Map generation seed (`0` = random) |
| `human_name` | `str` | `"Athens"` | `1–40` chars | Name of the human player's civ |

**Response `200`:** `GameStateOut` — full initial game state

**Response `422`:** Pydantic validation error (e.g., `radius` out of range)

**Example:**

```bash
curl -X POST http://localhost:8000/games \
  -H "Content-Type: application/json" \
  -d '{"radius": 8, "seed": 42, "human_name": "Sparta"}'
```

<details>
<summary>Example response (truncated)</summary>

```json
{
  "id": 1,
  "turn": 0,
  "current_civ_id": 1,
  "map_radius": 8,
  "tiles": [
    {
      "q": 0, "r": 0,
      "terrain": "grassland",
      "resource": "horses",
      "feature": null,
      "river": false,
      "improvement": null,
      "food": 2,
      "production": 1,
      "gold": 0
    }
  ],
  "civs": [
    {
      "id": 1,
      "name": "Sparta",
      "leader_name": "The Player",
      "is_human": true,
      "gold": 100,
      "gold_income": 8,
      "gold_upkeep": 0,
      "science": 4,
      "culture": 2,
      "known_techs": [],
      "researching": null,
      "score": 10
    }
  ],
  "civ_roster": [
    { "id": 1, "name": "Sparta", "leader_name": "The Player", "is_human": true },
    { "id": 2, "name": "Mongolia", "leader_name": "Genghis Khan", "is_human": false },
    { "id": 3, "name": "Egypt", "leader_name": "Cleopatra", "is_human": false },
    { "id": 4, "name": "India", "leader_name": "Mahatma Gandhi", "is_human": false }
  ],
  "cities": [],
  "structures": [],
  "units": [
    {
      "id": 1,
      "owner": 1,
      "type": "settler",
      "q": 0,
      "r": 0,
      "health": 20,
      "moves_remaining": 2,
      "work_order": null
    }
  ],
  "known_civ_ids": [],
  "messages": [],
  "inbox": [],
  "stances": [],
  "visible_tile_keys": ["0,0","0,1","1,0"],
  "explored_tile_keys": ["0,0","0,1","1,0"],
  "tile_owner": [],
  "diplomatic_events": [],
  "standings": [],
  "score_threshold": 200
}
```

</details>

---

#### `GET /games/{game_id}`

Retrieve the current game state for a specific game.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `game_id` | `int` | Unique game identifier |

**Response `200`:** `GameStateOut`

**Response `404`:**

```json
{ "detail": "game not found" }
```

**Example:**

```bash
curl http://localhost:8000/games/1
```

---

### Actions

All action endpoints live under `/games/{game_id}/actions`. Every action validates the request against the engine, applies the change, persists the new state, and returns the full `GameStateOut`.

**Common path parameter:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `game_id` | `int` | Unique game identifier |

**Common error:** `404` — `"game not found"`  
**Common error:** `400` — engine-level error with a descriptive `detail` string

---

#### `POST /games/{game_id}/actions/move`

Move a unit to an adjacent hex tile.

**Request Body:** `MoveRequest`

| Field | Type | Description |
|-------|------|-------------|
| `unit_id` | `int` | ID of the unit to move |
| `q` | `int` | Destination hex column |
| `r` | `int` | Destination hex row |

**Engine Errors (400):**

| Error Detail | Meaning |
|-------------|---------|
| `unknown unit id N` | Unit does not exist |
| `unit N has no moves remaining` | Unit has exhausted moves this turn |
| `destination (q,r) is off map` | Target hex is outside the map |
| `destination (q,r) is not adjacent to unit at (q,r)` | Target is more than 1 hex away |
| `terrain X is impassable` | Tile terrain blocks movement (ocean, mountain) |
| `destination (q,r) is occupied` | Another unit already occupies the tile |
| `enemy city must be reduced to 0 health before capture` | City is still defended |

**Example:**

```bash
curl -X POST http://localhost:8000/games/1/actions/move \
  -H "Content-Type: application/json" \
  -d '{"unit_id": 1, "q": 0, "r": 1}'
```

---

#### `POST /games/{game_id}/actions/attack`

Have one unit attack another unit.

**Request Body:** `AttackRequest`

| Field | Type | Description |
|-------|------|-------------|
| `attacker_id` | `int` | ID of the attacking unit |
| `defender_id` | `int` | ID of the defending unit |

**Engine Errors (400):**

| Error Detail | Meaning |
|-------------|---------|
| `unknown unit id N` | Unit does not exist |
| `cannot attack own unit` | Attacker and defender belong to same civ |
| `civs A and B are not at war` | Diplomatic stance is not WAR |
| `attacker N has no moves` | Attacker has no moves remaining |
| `target not adjacent` | Units are more than 1 hex apart |

**Example:**

```bash
curl -X POST http://localhost:8000/games/1/actions/attack \
  -H "Content-Type: application/json" \
  -d '{"attacker_id": 3, "defender_id": 7}'
```

---

#### `POST /games/{game_id}/actions/attack-city`

Have a unit attack a city.

**Request Body:** `AttackCityRequest`

| Field | Type | Description |
|-------|------|-------------|
| `attacker_id` | `int` | ID of the attacking unit |
| `city_id` | `int` | ID of the target city |

**Engine Errors (400):**

| Error Detail | Meaning |
|-------------|---------|
| `unknown unit id N` | Attacker unit does not exist |
| `unknown city id N` | City does not exist |
| `cannot attack own city` | Same-civ attack |
| `civs A and B are not at war` | Diplomatic stance is not WAR |
| `attacker N has no moves` | Attacker has no moves remaining |
| `target city not adjacent` | Attacker is more than 1 hex from city |

**Example:**

```bash
curl -X POST http://localhost:8000/games/1/actions/attack-city \
  -H "Content-Type: application/json" \
  -d '{"attacker_id": 3, "city_id": 2}'
```

---

#### `POST /games/{game_id}/actions/found`

Found a new city with a settler unit. The settler is consumed on success.

**Request Body:** `FoundCityRequest`

| Field | Type | Description |
|-------|------|-------------|
| `unit_id` | `int` | ID of the settler unit |
| `name` | `str` | Name for the new city |

**Engine Errors (400):**

| Error Detail | Meaning |
|-------------|---------|
| `unknown unit id N` | Unit does not exist |
| `unit N is not a settler` | Unit type is not SETTLER |
| `unit location (q,r) is off map` | Settler is somehow off-map |
| `cannot found city on X` | Terrain is ocean or mountain |
| `a city already exists at (q,r)` | Tile already hosts a city |

**Example:**

```bash
curl -X POST http://localhost:8000/games/1/actions/found \
  -H "Content-Type: application/json" \
  -d '{"unit_id": 1, "name": "New Sparta"}'
```

---

#### `POST /games/{game_id}/actions/research`

Set a civilization's current research target.

**Request Body:** `ResearchRequest`

| Field | Type | Description |
|-------|------|-------------|
| `civ_id` | `int` | ID of the civilization |
| `tech_id` | `str` | Tech identifier (see tech tree below) |

**Tech IDs:** `pottery`, `animal_husbandry`, `mining`, `archery`, `horseback_riding`, `iron_working`, `writing`, `mathematics`, `currency`, `construction`, `philosophy`, `theology`, `civil_service`, `guilds`, `education`, `astronomy`, `navigation`

**Engine Errors (400):**

| Error Detail | Meaning |
|-------------|---------|
| `unknown civ id N` | Civ does not exist |
| `unknown tech X` | Tech ID not recognized |
| `tech X already researched` | Already known |
| `prerequisites not met for X` | Missing prerequisite techs |

**Example:**

```bash
curl -X POST http://localhost:8000/games/1/actions/research \
  -H "Content-Type: application/json" \
  -d '{"civ_id": 1, "tech_id": "pottery"}'
```

---

#### `POST /games/{game_id}/actions/build`

Queue a unit or building for production in a city.

**Request Body:** `BuildRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `civ_id` | `int` | — | ID of the civilization |
| `city_id` | `int` | — | ID of the city |
| `build_kind` | `str` | `"unit"` | `"unit"` or `"building"` |
| `unit_type` | `str\|null` | `null` | Unit type ID (if `build_kind` is `"unit"`) |
| `item_id` | `str\|null` | `null` | Item ID (alternative to `unit_type`) |

**Unit types (build_kind=unit):** `settler`, `worker`, `scout`, `warrior`, `archer`, `horseman`, `swordsman`

**Building types (build_kind=building):** `granary`, `barracks`, `library`, `market`, `walls`, `temple`, `workshop`, `university`, `harbor`

**Engine Errors (400):**

| Error Detail | Meaning |
|-------------|---------|
| `unknown city id N` | City does not exist |
| `city N is not owned by civ M` | Wrong civ |
| `unknown civ id N` | Civ does not exist |
| `unit X is not unlocked` | Tech prerequisite not met |
| `building X already built` | Already present in city |
| `building X already queued` | Already in queue |
| `building X is not unlocked` | Tech prerequisite not met |

**Example:**

```bash
curl -X POST http://localhost:8000/games/1/actions/build \
  -H "Content-Type: application/json" \
  -d '{"civ_id": 1, "city_id": 1, "build_kind": "unit", "unit_type": "warrior"}'
```

---

#### `POST /games/{game_id}/actions/cancel-build`

Remove an item from a city's production queue. Cancelling the queue head (index 0) forfeits accumulated production.

**Request Body:** `CancelBuildRequest`

| Field | Type | Description |
|-------|------|-------------|
| `civ_id` | `int` | ID of the civilization |
| `city_id` | `int` | ID of the city |
| `index` | `int` | Queue position (0-based) to remove |

**Engine Errors (400):**

| Error Detail | Meaning |
|-------------|---------|
| `unknown city id N` | City does not exist |
| `city N is not owned by civ M` | Wrong civ |
| `queue index N out of bounds (queue size M)` | Invalid index |

**Example:**

```bash
curl -X POST http://localhost:8000/games/1/actions/cancel-build \
  -H "Content-Type: application/json" \
  -d '{"civ_id": 1, "city_id": 1, "index": 0}'
```

---

#### `POST /games/{game_id}/actions/purchase-structure`

Spend gold to place a cosmetic structure on a city tile. One structure per category per city.

**Request Body:** `PurchaseStructureRequest`

| Field | Type | Description |
|-------|------|-------------|
| `civ_id` | `int` | ID of the civilization |
| `city_id` | `int` | ID of the city |
| `category` | `str` | Structure category: `fortification`, `production`, `housing`, `sacred` |
| `q` | `int` | Hex column for placement |
| `r` | `int` | Hex row for placement |

**Engine Errors (400):**

| Error Detail | Meaning |
|-------------|---------|
| `unknown city id N` | City does not exist |
| `city N is not owned by civ M` | Wrong civ |
| `unknown structure category 'X'` | Invalid category |
| `city already has a X structure` | Category already purchased |
| `unknown civ id N` | Civ does not exist |
| `not enough gold (need N, have M)` | Insufficient gold |
| `structure location (q,r) is off map` | Off map |
| `cannot place structure on X` | Terrain is impassable |
| `structure must be placed inside this city's borders` | Outside borders |
| `structure tile already has a city` | Tile occupied by city |
| `structure tile is occupied by a unit` | Tile occupied by unit |
| `structure tile already has a structure` | Tile occupied by structure |

**Example:**

```bash
curl -X POST http://localhost:8000/games/1/actions/purchase-structure \
  -H "Content-Type: application/json" \
  -d '{"civ_id": 1, "city_id": 1, "category": "fortification", "q": 0, "r": 3}'
```

---

#### `POST /games/{game_id}/actions/improve`

Start a tile improvement (farm, mine, road) using a worker unit. The worker spends all remaining moves.

**Request Body:** `BuildImprovementRequest`

| Field | Type | Description |
|-------|------|-------------|
| `unit_id` | `int` | ID of the worker unit |
| `improvement` | `str` | Improvement type: `farm`, `mine`, `road` |

**Engine Error Codes (400):**

| Machine Code | Meaning |
|-------------|---------|
| `not_worker` | Unit is not a worker |
| `worker_already_busy` | Worker already has a work order |
| `bad_terrain_for_improvement` | Improvement not allowed on this terrain |
| `tile_already_improved` | Tile already has an improvement |
| `not_in_own_borders` | Tile is not within own borders |

**Example:**

```bash
curl -X POST http://localhost:8000/games/1/actions/improve \
  -H "Content-Type: application/json" \
  -d '{"unit_id": 5, "improvement": "farm"}'
```

---

#### `POST /games/{game_id}/actions/message`

Send a diplomatic message to another civilization. Message kinds have engine side-effects (stance changes, relationship adjustments, truces).

**Request Body:** `MessageRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `from_civ_id` | `int` | — | Sender civilization ID |
| `to_civ_id` | `int` | — | Recipient civilization ID |
| `kind` | `str` | `"chat"` | Message kind (see below) |
| `text` | `str` | — | Free-form message content |

**Message Kinds (& side-effects):**

| Kind | Side-Effect |
|------|-------------|
| `chat` | Relationship +1 |
| `threat` | Relationship −10 |
| `offer_peace` | Relationship +8 |
| `accept_peace` | Relationship +25, sets stance PEACE, activates 10-turn truce |
| `declare_war` | Relationship −50, sets stance WAR |
| `propose_alliance` | Relationship +15 |
| `accept_alliance` | Relationship +30, sets stance ALLIANCE |
| `reject` | Relationship −5 |

**Engine Errors (400):**

| Error Detail | Meaning |
|-------------|---------|
| `cannot send message to self` | Sender and recipient are the same civ |
| `unknown recipient civ N` | Recipient civ does not exist |
| `cannot message unmet civ N` | Sender has not yet met the recipient |
| `truce with civ N is still binding` | Cannot threaten or declare war during truce |

**Example:**

```bash
curl -X POST http://localhost:8000/games/1/actions/message \
  -H "Content-Type: application/json" \
  -d '{"from_civ_id": 1, "to_civ_id": 3, "kind": "chat", "text": "Greetings, Pharaoh."}'
```

---

### Turns

#### `POST /games/{game_id}/turn`

End the human player's turn. This runs the engine's turn-resolver: production ticks, research ticks, city growth, improvement progress, and AI diplomatic response. The next turn begins with the human civ as the active player.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `game_id` | `int` | Unique game identifier |

**Response `200`:** `GameStateOut`

**Response `404`:** `{ "detail": "game not found" }`

**Example:**

```bash
curl -X POST http://localhost:8000/games/1/turn
```

---

#### `POST /games/{game_id}/turn/resolve`

Run the full AI playthrough: each AI civilization takes its turn (LLM-driven decisions via OpenAI tool-use), cycling through all AI civs until it is the human's turn again. This is the compound "advance until my turn" operation.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `game_id` | `int` | Unique game identifier |

**Response `200`:** `GameStateOut` — state after all AI civs have acted

**Response `400`:** `{ "detail": "game has no human civ" }`

**Response `404`:** `{ "detail": "game not found" }`

**Example:**

```bash
curl -X POST http://localhost:8000/games/1/turn/resolve
```

---

### Audio

#### `POST /audio/intro`

Generate an AI-narrated MP3 introduction using OpenAI's TTS API. Requires `OPENAI_API_KEY` environment variable.

**Request Body:** `IntroNarrationRequest`

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | Narration text, 1–1200 characters |

**Response `200`:** `audio/mpeg` — MP3 binary stream with `Cache-Control: no-store`

**Response `503`:** `{ "detail": "OPENAI_API_KEY is not configured" }`

**Response `502`:** `{ "detail": "voice generation failed: <OpenAI error>" }`

**Example:**

```bash
curl -X POST http://localhost:8000/audio/intro \
  -H "Content-Type: application/json" \
  -d '{"text": "In the year of the great flood, four kingdoms rose from the ashes..."}' \
  --output intro.mp3
```

---

## Data Transfer Objects (DTOs)

### Request Bodies

#### `CreateGameRequest`

```python
class CreateGameRequest(BaseModel):
    radius: int = 8          # Map radius (1–20)
    seed: int = 0            # Map seed (0 = random)
    human_name: str = "Athens"  # Human civ name (1–40 chars)
```

#### `IntroNarrationRequest`

```python
class IntroNarrationRequest(BaseModel):
    text: str  # 1–1200 characters
```

#### `MoveRequest`

```python
class MoveRequest(BaseModel):
    unit_id: int
    q: int
    r: int
```

#### `AttackRequest`

```python
class AttackRequest(BaseModel):
    attacker_id: int
    defender_id: int
```

#### `AttackCityRequest`

```python
class AttackCityRequest(BaseModel):
    attacker_id: int
    city_id: int
```

#### `FoundCityRequest`

```python
class FoundCityRequest(BaseModel):
    unit_id: int
    name: str
```

#### `ResearchRequest`

```python
class ResearchRequest(BaseModel):
    civ_id: int
    tech_id: str
```

#### `BuildRequest`

```python
class BuildRequest(BaseModel):
    civ_id: int
    city_id: int
    unit_type: str | None = None
    build_kind: str = "unit"   # "unit" or "building"
    item_id: str | None = None # Alternative to unit_type
```

#### `CancelBuildRequest`

```python
class CancelBuildRequest(BaseModel):
    civ_id: int
    city_id: int
    index: int   # 0-based queue position
```

#### `PurchaseStructureRequest`

```python
class PurchaseStructureRequest(BaseModel):
    civ_id: int
    city_id: int
    category: str   # fortification | production | housing | sacred
    q: int
    r: int
```

#### `MessageRequest`

```python
class MessageRequest(BaseModel):
    from_civ_id: int
    to_civ_id: int
    kind: str = "chat"   # chat | threat | offer_peace | accept_peace | declare_war | propose_alliance | accept_alliance | reject
    text: str
```

#### `BuildImprovementRequest`

```python
class BuildImprovementRequest(BaseModel):
    unit_id: int
    improvement: str   # farm | mine | road
```

### Response Shapes

#### `GameStateOut` (top-level response)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Game ID |
| `turn` | `int` | Current turn number |
| `current_civ_id` | `int` | ID of the active civilization |
| `map_radius` | `int` | Map radius in hex tiles |
| `tiles` | `list[TileOut]` | Explored tiles |
| `civs` | `list[CivOut]` | Visible civilizations |
| `civ_roster` | `list[CivRosterEntry]` | All civs (identity only, no gameplay state) |
| `cities` | `list[CityOut]` | Visible cities |
| `structures` | `list[CityStructureOut]` | Visible purchased structures |
| `units` | `list[UnitOut]` | Visible units |
| `known_civ_ids` | `list[int]` | IDs of civs the human has met |
| `messages` | `list[MessageOut]` | Diplomatic messages visible to the human |
| `inbox` | `list[MessageOut]` | Messages addressed to the human civ |
| `stances` | `list[StanceOut]` | Diplomatic stances with each known civ |
| `visible_tile_keys` | `list[str]` | `"q,r"` strings for currently visible tiles |
| `explored_tile_keys` | `list[str]` | `"q,r"` strings for ever-seen tiles |
| `tile_owner` | `list[TileOwnerOut]` | City ownership of visible tiles |
| `diplomatic_events` | `list[DiplomaticEventOut]` | Last 20 diplomatic events involving human |
| `standings` | `list[StandingOut]` | Scoreboard sorted by score descending |
| `score_threshold` | `int` | Points needed for victory (default 200) |

#### `TileOut`

| Field | Type | Description |
|-------|------|-------------|
| `q` | `int` | Hex column |
| `r` | `int` | Hex row |
| `terrain` | `str` | `grassland` \| `plains` \| `desert` \| `tundra` \| `hills` \| `forest` \| `ocean` \| `mountain` |
| `resource` | `str\|null` | Strategic/luxury resource or null |
| `feature` | `str\|null` | `forest` \| `jungle` \| `marsh` \| `oasis` \| `floodplains` or null |
| `river` | `bool` | Whether the tile has a river |
| `improvement` | `str\|null` | `farm` \| `mine` \| `road` or null |
| `food` | `int` | Food yield |
| `production` | `int` | Production yield |
| `gold` | `int` | Gold yield |

#### `UnitOut`

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Unique unit ID |
| `owner` | `int` | Owning civ ID |
| `type` | `str` | `settler` \| `worker` \| `scout` \| `warrior` \| `archer` \| `horseman` \| `swordsman` |
| `q` | `int` | Hex column |
| `r` | `int` | Hex row |
| `health` | `int` | Current health |
| `moves_remaining` | `int` | Moves left this turn |
| `work_order` | `WorkOrderOut\|null` | Active improvement work or null |

#### `WorkOrderOut`

| Field | Type | Description |
|-------|------|-------------|
| `q` | `int` | Target hex column |
| `r` | `int` | Target hex row |
| `improvement` | `str` | Improvement type |
| `turns_remaining` | `int` | Turns until completion |

#### `CityOut`

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Unique city ID |
| `owner` | `int` | Owning civ ID |
| `name` | `str` | City name |
| `q` | `int` | Hex column |
| `r` | `int` | Hex row |
| `population` | `int` | Current population |
| `food_stored` | `int` | Accumulated food toward next growth |
| `production_stored` | `int` | Accumulated production toward current item |
| `health` | `int` | Current health |
| `max_health` | `int` | Maximum health |
| `is_capital` | `bool` | Whether this is the civ's capital |
| `buildings` | `list[str]` | Built building IDs |
| `purchased_structures` | `list[str]` | Purchased structure categories |
| `production_queue` | `list[str]` | Queued item IDs |
| `border_radius` | `int` | Cultural border reach in hexes |
| `culture_stored` | `int` | Accumulated culture toward next border expansion |
| `worked_tiles` | `list[dict]` | `[{"q": int, "r": int}, ...]` |

#### `CityStructureOut`

| Field | Type | Description |
|-------|------|-------------|
| `city_id` | `int` | Parent city ID |
| `owner` | `int` | Owning civ ID |
| `category` | `str` | Structure category |
| `q` | `int` | Hex column |
| `r` | `int` | Hex row |

#### `CivOut`

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Civilization ID |
| `name` | `str` | Civ name (e.g., "Egypt") |
| `leader_name` | `str` | Leader name (e.g., "Cleopatra") |
| `is_human` | `bool` | Whether human-controlled |
| `gold` | `int` | Treasury |
| `gold_income` | `int` | Gold per turn |
| `gold_upkeep` | `int` | Gold costs per turn |
| `science` | `int` | Science output per turn |
| `culture` | `int` | Culture output per turn |
| `known_techs` | `list[str]` | Researched tech IDs |
| `researching` | `str\|null` | Current research target or null |
| `score` | `int` | Victory score |

#### `CivRosterEntry`

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Civilization ID |
| `name` | `str` | Civ name |
| `leader_name` | `str` | Leader name |
| `is_human` | `bool` | Whether human-controlled |

#### `MessageOut`

| Field | Type | Description |
|-------|------|-------------|
| `from_civ_id` | `int` | Sender civ ID |
| `to_civ_id` | `int` | Recipient civ ID |
| `turn` | `int` | Turn when sent |
| `kind` | `str` | Message kind |
| `text` | `str` | Message content |

#### `StanceOut`

| Field | Type | Description |
|-------|------|-------------|
| `other_civ_id` | `int` | The other civilization's ID |
| `stance` | `str` | `neutral` \| `war` \| `peace` \| `alliance` |
| `relationship` | `int` | Relationship score (−100 to +100) |
| `truce_active` | `bool` | Whether a binding truce is in effect |
| `truce_until` | `int\|null` | Turn when truce expires, or null |

#### `DiplomaticEventOut`

| Field | Type | Description |
|-------|------|-------------|
| `turn` | `int` | Turn when event occurred |
| `kind` | `str` | Event kind |
| `actor_civ_id` | `int` | Initiating civ ID |
| `target_civ_id` | `int` | Target civ ID |
| `summary` | `str` | Human-readable description |
| `relationship_delta` | `int` | Relationship score change |

#### `StandingOut`

| Field | Type | Description |
|-------|------|-------------|
| `civ_id` | `int` | Civilization ID |
| `name` | `str` | Civ name |
| `score` | `int` | Victory score |

#### `TileOwnerOut`

| Field | Type | Description |
|-------|------|-------------|
| `q` | `int` | Hex column |
| `r` | `int` | Hex row |
| `city_id` | `int` | ID of the city that owns the tile |

---

## Error Code Catalog

### HTTP Status Codes

| Status | Meaning |
|--------|---------|
| `200` | Success |
| `400` | Engine-level validation error — see `detail` field |
| `404` | Resource not found (game ID unknown) |
| `422` | Pydantic request validation error |
| `502` | Upstream API failure (OpenAI TTS) |
| `503` | Service unavailable (missing configuration) |

### Engine Error Codes (alphabetical)

These machine-readable strings appear in the `detail` field of 400 responses. They are designed for LLM/UI consumption.

| Error Code | Source Module | Meaning |
|------------|--------------|---------|
| `a city already exists at (q,r)` | `city_founding` | Cannot found city on occupied tile |
| `already built` | `directives` | Building already constructed in city |
| `already queued` | `directives` | Building already in production queue |
| `already researched` | `research` | Tech is already known |
| `bad_terrain_for_improvement` | `improvements` | Improvement not compatible with this terrain |
| `cannot attack own city` | `combat` | Self-attack on own city |
| `cannot attack own unit` | `combat` | Self-attack on own unit |
| `cannot change stance with self` | `diplomacy` | Stance change targeting own civ |
| `cannot change stance with unmet civ N` | `diplomacy` | Must meet civ before changing stance |
| `cannot found city on X` | `city_founding` | Terrain blocks city founding |
| `cannot message unmet civ N` | `diplomacy` | Must meet civ before messaging |
| `cannot place structure on X` | `directives` | Terrain impassable for structure |
| `cannot send message to self` | `diplomacy` | Self-message attempt |
| `destination ... is not adjacent` | `movement` | Move target more than 1 hex away |
| `destination ... is occupied` | `movement` | Tile already occupied by another unit |
| `destination ... is off map` | `movement` | Target hex outside map bounds |
| `enemy city must be reduced to 0 health before capture` | `movement` | Cannot capture defended city |
| `has no moves` / `has no moves remaining` | `combat` / `movement` | Unit out of moves this turn |
| `is not a settler` | `city_founding` | Wrong unit type for founding |
| `is not unlocked` | `directives` | Tech prerequisite not met |
| `not enough gold (need N, have M)` | `directives` | Insufficient funds |
| `not_in_own_borders` | `improvements` | Tile outside own cultural borders |
| `not_worker` | `improvements` | Unit type is not WORKER |
| `prerequisites not met for X` | `research` | Missing prerequisite techs |
| `queue index N out of bounds` | `directives` | Invalid queue position |
| `structure location (q,r) is off map` | `directives` | Placement outside map |
| `structure must be placed inside this city's borders` | `directives` | Placement outside city borders |
| `structure tile already has a city` | `directives` | Tile occupied by a city |
| `structure tile already has a structure` | `directives` | Tile occupied by another structure |
| `structure tile is occupied by a unit` | `directives` | Tile occupied by a unit |
| `target city not adjacent` | `combat` | City attack range violation |
| `target not adjacent` | `combat` | Unit attack range violation |
| `terrain X is impassable` | `movement` | Terrain blocks movement |
| `tile_already_improved` | `improvements` | Tile already has an improvement |
| `truce with civ N is still binding` | `diplomacy` | Cannot perform hostile action during truce |
| `unknown city id N` | `combat` / `directives` | City does not exist |
| `unknown civ id N` | `research` / `directives` | Civ does not exist |
| `unknown diplomatic action type` | `diplomacy` | Internal: unsupported action type |
| `unknown recipient civ N` | `diplomacy` | Target civ does not exist |
| `unknown structure category 'X'` | `directives` | Invalid structure category |
| `unknown tech X` | `research` | Tech ID not recognized |
| `unknown unit id N` | `movement` / `combat` / `improvements` / `city_founding` | Unit does not exist |
| `unit location (q,r) is off map` | `city_founding` | Unit is somehow off the map |
| `worker_already_busy` | `improvements` | Worker already has a work order |
