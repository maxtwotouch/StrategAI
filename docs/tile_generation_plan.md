# Tile Generation Plan: Extending the Leader-Style API to Structures, Objects, and Terrain

This document consolidates the full design, implementation plan, client-facing API contract, and prompt-writing guide for three new generation pipelines that mirror the leader pipeline architecture.

---

## 1. Current State & Motivation

### 1.1 What the leader pipeline does well (the pattern to replicate)

| Layer | File | Role |
|---|---|---|
| **Enums** | `leader_models.py` | `Archetype`, `Culture`, `TimeOfDay`, `Mood`, `ActionCategory` — constrained vocabularies the client picks from |
| **Request/Response** | `leader_models.py` | `LeaderRequest` / `LeaderResponse` — Pydantic schemas with rich field descriptions so clients know exactly what to send |
| **Prompt injection maps** | `leader_prompts.py` | Hand-crafted prose per enum value, assembled by `build_prompt()` into a final prompt |
| **Engine** | `leader_engine.py` | Orchestrates generation, persistence, registry |
| **Registry** | `leader_registry.py` | SQLite-backed CRUD for generated assets |
| **API endpoint** | `main.py` | `POST /leader`, `GET /leader`, etc. |
| **Client guide** | `docs/client-api-leader-guide.md` | Section 6 — comprehensive guide for writing descriptions + picking enums, with BAD/GOOD examples and quick-reference tables |

### 1.2 What the existing `/generate` endpoint does (the old way)

- `GenerationRequest` has a free-form `prompt` field — the client writes raw prompts.
- `ComfyUIGenerator._build_positive_prompt()` does minimal assembly: `"pixel art top-down 2d game {subtype} building, top-down view, isometric pixel art, medieval fantasy"` + user's raw prompt.
- No enum-driven injection, no hand-crafted prose maps, no structured variation, no client guide.

### 1.3 The prompt templates in `config/prompt_templates.json`

```json
"structure": "<tdp> ... {PROMPT_HERE}. Pixel art 16x16..."
"object":    "<tdp> ... {PROMPT_HERE}. Pixel art 16x16..."
"terrain":   "<tdp> ... {PROMPT_HERE}. Pixel art 16x16..."
```

These are **wrapper templates** with a `{PROMPT_HERE}` placeholder. The idea: the server fills `{PROMPT_HERE}` with a richly assembled prompt (just like the leader pipeline does), then wraps it in the template.

---

## 2. The Three Pipelines

### 2.1 Structure Pipeline

**Categories (the user's spec, formalized):**

| Category | Key | Examples |
|---|---|---|
| Fortification | `fortification` | Towers, walls, gatehouses, keeps, battlements, palisades, barbicans, watchtowers, bastions |
| Production | `production` | Forges, windmills, watermills, workshops, lumber mills, kilns, smithies, breweries |
| Housing | `housing` | Townhouses (small/medium/large), taverns, inns, cottages, manors, farmhouses, longhouses |
| Sacred | `sacred` | Churches, cathedrals, shrines, temples, monasteries, chapels, abbeys |

**Enums the client selects from:**

```python
class StructureCategory:
    FORTIFICATION = "fortification"
    PRODUCTION    = "production"
    HOUSING       = "housing"
    SACRED        = "sacred"
    ALL = {FORTIFICATION, PRODUCTION, HOUSING, SACRED}

class StructureStyle:          # architectural style
    NORDIC_WOODEN       = "nordic_wooden"
    ANGLO_SAXON_STONE   = "anglo_saxon_stone"
    NORMAN_ROMANESQUE   = "norman_romanesque"
    GOTHIC              = "gothic"
    MEDITERRANEAN       = "mediterranean"
    SLAVIC_TIMBER       = "slavic_timber"
    MOORISH             = "moorish"
    ALL = {...}

class StructureCondition:      # state of the building
    PRISTINE            = "pristine"
    WEATHERED           = "weathered"
    RUINED              = "ruined"
    UNDER_CONSTRUCTION  = "under_construction"
    FORTIFIED           = "fortified"        # extra defenses added
    ALL = {...}

class StructureScale:          # size tier
    SMALL  = "small"            # cottage, shrine, small tower, smithy
    MEDIUM = "medium"           # townhouse, church, forge, tavern
    LARGE  = "large"            # cathedral, castle keep, great hall, abbey
    ALL = {SMALL, MEDIUM, LARGE}
```

**Prompt injection maps (hand-crafted prose per value, same pattern as `leader_prompts.py`):**

```python
STRUCTURE_CATEGORY = {
    "fortification": (
        "a sturdy defensive structure with crenellated battlements, arrow slits, "
        "thick stone walls, watchtower, military functionality"
    ),
    "production": (
        "a working industrial building with chimney smoke, visible tools and "
        "raw materials outside, functional workshop architecture"
    ),
    "housing": (
        "a lived-in residential building with shuttered windows, chimney, "
        "small garden or yard, domestic warmth and character"
    ),
    "sacred": (
        "a reverent religious building with stained glass, spire or steeple, "
        "ceremonial entrance, spiritual architectural grandeur"
    ),
}

STRUCTURE_STYLE = {
    "nordic_wooden": (
        "dark timber construction with carved dragon-head gables, steep "
        "shingled roof, iron hinges and fittings, Norse craftsmanship"
    ),
    "anglo_saxon_stone": (
        "rough-hewn stone walls with timber framing, thick thatched roof, "
        "low profile, wattle-and-daub accents, early medieval English vernacular"
    ),
    "norman_romanesque": (
        "heavy stone construction with round arches, thick pillars, small "
        "deep-set windows, fortress-like solidity, chevron ornament"
    ),
    "gothic": (
        "pointed arches soaring upward, flying buttresses, tall spires, "
        "ornate stone tracery, large rose window, vertical emphasis"
    ),
    "mediterranean": (
        "warm terracotta roof tiles, whitewashed stone or stucco walls, "
        "arched colonnades and loggias, cypress trees nearby, sun-baked palette"
    ),
    "slavic_timber": (
        "horizontal log construction with notched corners, carved wooden "
        "trim and window frames, steep shingled roofs, onion-dome influences"
    ),
    "moorish": (
        "horseshoe arches, intricate geometric tile patterns, carved stucco "
        "arabesques, interior courtyard implied, domed roofs with tile work"
    ),
}

STRUCTURE_CONDITION = {
    "pristine": (
        "freshly built, clean stonework with bright mortar, new timber showing "
        "no weathering, sharp edges and crisp details"
    ),
    "weathered": (
        "aged stone with patches of moss and lichen, faded and greyed timber, "
        "subtle settlement cracks, lived-in character, slightly worn edges"
    ),
    "ruined": (
        "collapsed roof sections exposing beams, ivy and climbing plants covering "
        "walls, broken or missing windows, scattered rubble and fallen stones at the base"
    ),
    "under_construction": (
        "wooden scaffolding lashed to partially built walls, piles of cut stone "
        "and timber on the ground, workers' tools and rope, exposed structural framing"
    ),
    "fortified": (
        "extra defensive additions — reinforced iron-bound doors, added crenellations, "
        "wooden barricades and sharpened stakes, hurried military practicality"
    ),
}

STRUCTURE_SCALE = {
    "small": (
        "compact single-room footprint, modest proportions, humble village scale, "
        "simple unpretentious architecture"
    ),
    "medium": (
        "substantial multi-room building, prominent in a village or town setting, "
        "balanced proportions with architectural detail"
    ),
    "large": (
        "imposing grand structure that dominates the landscape, monumental scale, "
        "complex architecture with multiple sections and towers"
    ),
}
```

**Prompt assembly:**

```python
def build_structure_prompt(req: StructureRequest) -> str:
    inner = ", ".join([
        f"a {STRUCTURE_SCALE[req.scale]} {STRUCTURE_CATEGORY[req.category]}",
        f"in {STRUCTURE_STYLE[req.style]} style",
        STRUCTURE_CONDITION[req.condition],
        req.description.strip(),
    ])
    template = load_template("structure")  # from config/prompt_templates.json
    return template.replace("{PROMPT_HERE}", inner)
```

**Request/Response models:**

```python
class StructureRequest(BaseModel):
    category: str = Field(
        ...,
        description="One of: fortification, production, housing, sacred",
    )
    style: str = Field(
        ...,
        description="One of: nordic_wooden, anglo_saxon_stone, norman_romanesque, "
                    "gothic, mediterranean, slavic_timber, moorish",
    )
    condition: str = Field(
        ...,
        description="One of: pristine, weathered, ruined, under_construction, fortified",
    )
    scale: str = Field(
        ...,
        description="One of: small, medium, large",
    )
    description: str = Field(
        ...,
        min_length=20,
        max_length=400,
        description="Free-form specifics: roof material, height, distinctive features, "
                    "what's around the entrance, visible activity. No camera directions "
                    "or style words.",
    )
    seed: Optional[int] = None

class StructureResponse(BaseModel):
    url: str                        # "/assets/{uuid}.png"
    asset_type: str                 # "structure"
    asset_id: str                   # "struct_fortification_a1b2c3"
    category: str
    style: str
    condition: str
    scale: str
    seed: int
    generation_mode: str
    prompt_used: Optional[str]
    resolution: Optional[str]
    generation_time_ms: Optional[int]
```

**Database record:**

```python
class StructureRecord(Base):
    __tablename__ = "structure_records"
    structure_id = Column(String, primary_key=True)
    category = Column(String, nullable=False)
    style = Column(String, nullable=False)
    condition = Column(String, nullable=False)
    scale = Column(String, nullable=False)
    description = Column(String, nullable=False)
    image_id = Column(String, nullable=False)
    seed = Column(Integer, nullable=False)
    prompt_used = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
```

**API endpoints:**

```
POST   /structure              → generate a structure
GET    /structure              → list all generated structures
GET    /structure/{id}         → get one structure's info
DELETE /structure/{id}         → delete
GET    /structure/catalog      → list available categories, styles, conditions, scales
```

---

### 2.2 Object Pipeline

**Categories:**

| Category | Key | Examples |
|---|---|---|
| Vegetation | `vegetation` | Trees (oak, pine, dead, fruit), bushes, shrubs, flowers, crops, mushrooms, vines |
| Geological | `geological` | Boulders, rock formations, cliffs, stalagmites, crystal formations, stone outcrops |
| Rural Props | `rural_props` | Fences, hay bales, carts, wells, signposts, barrels, troughs, scarecrows, beehives |
| Urban Props | `urban_props` | Street lamps, market stalls, statues, fountains, benches, notice boards, hanging signs, crates |
| Debris | `debris` | Rubble piles, broken carts, scattered bones, fallen trees, abandoned campfires, wreckage |

**Enums:**

```python
class ObjectCategory:
    VEGETATION   = "vegetation"
    GEOLOGICAL   = "geological"
    RURAL_PROPS  = "rural_props"
    URBAN_PROPS  = "urban_props"
    DEBRIS       = "debris"
    ALL = {VEGETATION, GEOLOGICAL, RURAL_PROPS, URBAN_PROPS, DEBRIS}

class Biome:                     # shared with Terrain
    TEMPERATE_FOREST = "temperate_forest"
    TAIGA            = "taiga"
    DESERT           = "desert"
    SWAMP            = "swamp"
    MOUNTAIN         = "mountain"
    COASTAL          = "coastal"
    ALL = {TEMPERATE_FOREST, TAIGA, DESERT, SWAMP, MOUNTAIN, COASTAL}

class Season:
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"
    ALL = {SPRING, SUMMER, AUTUMN, WINTER}
```

**Prompt injection maps:**

```python
OBJECT_CATEGORY = {
    "vegetation": (
        "a natural living plant with organic form, textured bark or stems, "
        "leaves or needles, rooted in the ground"
    ),
    "geological": (
        "a natural rock formation with textured stone surface, mineral colouring, "
        "angular or weathered shape, heavy grounded presence"
    ),
    "rural_props": (
        "a hand-crafted countryside object made of wood, stone, or metal, "
        "functional rustic design, weathered by outdoor exposure"
    ),
    "urban_props": (
        "a crafted town object with refined workmanship, iron or wood construction, "
        "decorative or functional civic purpose"
    ),
    "debris": (
        "scattered broken remnants, damaged and abandoned, fragments and wreckage, "
        "signs of past destruction or decay"
    ),
}

BIOME = {
    "temperate_forest": "deciduous woodland context with rich soil, leaf litter, ferns, varied greens",
    "taiga": "boreal conifer forest context with pale soil, pine needles, lichen, muted greens",
    "desert": "arid desert context with sand, dry cracked earth, sparse scrub, warm earth tones",
    "swamp": "wetland marsh context with dark mud, still water, reeds, twisted roots, murky tones",
    "mountain": "alpine rocky context with exposed stone, scree, thin soil, sparse vegetation",
    "coastal": "seaside context with sand, driftwood, salt-worn textures, bleached tones",
}

SEASON = {
    "spring": "fresh green growth, new leaves unfurling, blossoms, bright and verdant",
    "summer": "full mature foliage, dry ground, warm tones, peak growth and ripeness",
    "autumn": "orange and red turning leaves, bare branches appearing, fallen leaves on ground, harvest tones",
    "winter": "bare dormant branches, snow cover, ice, muted browns and greys, stark silhouette",
}
```

**Prompt assembly:**

```python
def build_object_prompt(req: ObjectRequest) -> str:
    inner = ", ".join([
        OBJECT_CATEGORY[req.category],
        f"in a {BIOME[req.biome]}",
        f"during {SEASON[req.season]}",
        req.description.strip(),
    ])
    template = load_template("object")
    return template.replace("{PROMPT_HERE}", inner)
```

**Request/Response — same shape as Structure, with category/biome/season fields.**

**API endpoints:**

```
POST   /object
GET    /object
GET    /object/{id}
DELETE /object/{id}
GET    /object/catalog
```

---

### 2.3 Terrain Pipeline — Elevation Features

**What terrain is (corrected):** terrain features are elevation / topographical sprites that map **on top of** background tiles. A grass background tile covers the ground; a hill terrain sprite sits on top of it. This is analogous to structures and objects — an isolated asset on white, placed in-game over the background layer.

**What terrain is NOT:** it is not a seamless repeating background tile. Background tiles (water, grass, sand, stone) are handled by the existing `POST /generate` endpoint with `asset_family: "background_tile"`.

**Categories:**

| Category | Key | Examples |
|---|---|---|
| Hill / Rise | `hill` | Gentle rolling hills, small mounds, grassy knolls, sand dunes, snowdrifts |
| Slope / Ramp | `slope` | Gradual elevation changes, ramps, stepped inclines, terraced land |
| Cliff / Bluff | `cliff` | Sheer rock faces, bluff edges, cliff overhangs, rocky escarpments |
| Ridge | `ridge` | Narrow elevated spines, mountain ridges, connecting highlands |
| Depression | `depression` | Pits, sinkholes, craters, dried lakebeds, quarry excavations |

**Enums the client selects from:**

```python
class TerrainCategory:
    HILL       = "hill"
    SLOPE      = "slope"
    CLIFF      = "cliff"
    RIDGE      = "ridge"
    DEPRESSION = "depression"
    ALL = {HILL, SLOPE, CLIFF, RIDGE, DEPRESSION}

class TerrainScale:             # elevation height / footprint
    LOW    = "low"              # gentle barely-there rise, 1-2 pixel height
    MEDIUM = "medium"           # noticeable hill, 3-4 pixel height, significant footprint
    HIGH   = "high"             # prominent feature, 5+ pixel height, dominates the tile
    ALL = {LOW, MEDIUM, HIGH}

class TerrainMaterial:          # what the terrain feature is made of
    EARTHEN   = "earthen"       # dirt, soil, grass-covered
    SANDY     = "sandy"         # sand, loose granular
    ROCKY     = "rocky"         # exposed stone, boulder-strewn
    SNOWY     = "snowy"         # snow-covered, icy patches
    MUDDY     = "muddy"         # wet earth, swampy ground
    ALL = {EARTHEN, SANDY, ROCKY, SNOWY, MUDDY}
```

**Prompt injection maps:**

```python
TERRAIN_CATEGORY = {
    "hill": (
        "a rounded mound or hill rising from the base plane, soft organic "
        "contour, natural elevation feature"
    ),
    "slope": (
        "a gradual inclined ramp sloping upward from one edge to the other, "
        "directional grade change, stepped or smooth transition"
    ),
    "cliff": (
        "a sheer vertical rock face with a sharp drop-off, exposed stone strata "
        "on the vertical face, flat or sloped top surface"
    ),
    "ridge": (
        "a narrow elevated spine connecting higher points, ridgeline with slopes "
        "falling away on both sides, jagged or rounded crest"
    ),
    "depression": (
        "a sunken pit or bowl-shaped hollow below the base plane, concave form, "
        "descending below grade level"
    ),
}

TERRAIN_SCALE = {
    "low": (
        "subtle barely-perceptible elevation change, just 1-2 pixels of height, "
        "small footprint, gentle barely-there feature"
    ),
    "medium": (
        "noticeable elevation change of 3-4 pixels, moderate footprint occupying "
        "most of the tile, distinct landform"
    ),
    "high": (
        "prominent dramatic elevation of 5+ pixels, fills the tile with towering "
        "presence, dominant landscape feature"
    ),
}

TERRAIN_MATERIAL = {
    "earthen": (
        "grass-topped soil with exposed dirt on steeper faces, green surface "
        "with brown earth edges, pastoral character"
    ),
    "sandy": (
        "loose sand with granular texture, wind-rippled surface, warm beige and "
        "tan tones, soft edges and curves"
    ),
    "rocky": (
        "grey stone with visible strata lines, scattered small boulders on the "
        "surface, hard angular edges, mineral tones"
    ),
    "snowy": (
        "white snow cover on the top surface with darker ground exposed on "
        "steep faces, crisp cold palette, ice patches"
    ),
    "muddy": (
        "dark wet earth with a slick sheen, soft squelchy contours, deep brown "
        "tones, small puddles in depressions"
    ),
}
```

**Prompt assembly:**

```python
def build_terrain_prompt(req: TerrainRequest) -> str:
    inner = ", ".join([
        f"a {TERRAIN_SCALE[req.scale]} {TERRAIN_CATEGORY[req.category]}",
        f"with {TERRAIN_MATERIAL[req.material]} material",
        req.description.strip(),
    ])
    template = load_template("terrain")
    return template.replace("{PROMPT_HERE}", inner)
```

**Template:** terrain uses the same pattern as structure/object — isolated on white, flows into any inserted background — but with terrain-specific direction:

```json
"terrain": "<tdp> Front view overhead shot elevated shot medium shot. The terrain elevation feature faces the camera straight from the front. The terrain should flow into any inserted background at its base edges. Isolate the object on a plain white background, only focusing on the specified object. {PROMPT_HERE}. Pixel art 16x16 for game tile assets, crisp pixel edges, no anti-aliasing, centered single asset on white. The base of the terrain feature should sit flush with the bottom of the frame. Grounded, stable perspective, no floating objects."
```

**Request/Response models:**

```python
class TerrainRequest(BaseModel):
    category: str = Field(
        ...,
        description="One of: hill, slope, cliff, ridge, depression",
    )
    scale: str = Field(
        ...,
        description="One of: low, medium, high",
    )
    material: str = Field(
        ...,
        description="One of: earthen, sandy, rocky, snowy, muddy",
    )
    description: str = Field(
        ...,
        min_length=20,
        max_length=400,
        description="Free-form specifics: shape, contour, distinguishing features, "
                    "what it would sit on top of. No camera directions or style words.",
    )
    seed: Optional[int] = None

class TerrainResponse(BaseModel):
    url: str
    asset_type: str                 # "terrain"
    asset_id: str                   # "terrain_hill_a1b2c3"
    category: str
    scale: str
    material: str
    seed: int
    generation_mode: str
    prompt_used: Optional[str]
    resolution: Optional[str]
    generation_time_ms: Optional[int]
```

**Database record:**

```python
class TerrainRecord(Base):
    __tablename__ = "terrain_records"
    terrain_id = Column(String, primary_key=True)
    category = Column(String, nullable=False)
    scale = Column(String, nullable=False)
    material = Column(String, nullable=False)
    description = Column(String, nullable=False)
    image_id = Column(String, nullable=False)
    seed = Column(Integer, nullable=False)
    prompt_used = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
```

**API endpoints:**

```
POST   /terrain
GET    /terrain
GET    /terrain/{id}
DELETE /terrain/{id}
GET    /terrain/catalog
```

---

## 3. Background Tiles — Separate from the Terrain Pipeline

### 3.1 The Boundary is Clear

| Concept | What it is | How it's generated | Where it goes |
|---|---|---|---|
| **Background tile** | The base ground layer — water, grass, sand, stone. Seamless repeating texture. | `POST /generate` with `asset_family: "background_tile"` and `tile_type` (existing system) | Bottom layer of the game map |
| **Terrain feature** | Elevation sprites — hills, slopes, cliffs. Isolated on white, alpha-masked in-game. | `POST /terrain` (new pipeline) | Placed on top of background tiles |
| **Structure** | Buildings — towers, houses, churches. Isolated on white. | `POST /structure` (new pipeline) | Placed on top of background tiles (and possibly terrain) |
| **Object** | Props and nature — trees, rocks, fences. Isolated on white. | `POST /object` (new pipeline) | Placed on top of background tiles (and possibly terrain) |

### 3.2 Background Tiles Stay on the Old Endpoint

The existing four tile types remain on `POST /generate`:

```
water  |  grass  |  sand  |  stone
```

This endpoint already works. The CoW inpainting system is built around it. There is no need to migrate background tiles to the new enum-driven system — they are simple, one-dimensional (just a `tile_type`), and don't benefit from multi-axis parameter injection the way structures/objects/terrain do.

The `get_inpaint_prompt()` vocabulary in `inpainting.py` provides sufficient prompt richness for background tiles.

### 3.3 Static Background Tile Randomization

When the server is in `static` mode for `background_tile`, the `StaticCatalog` provides **built-in random variation**. If multiple PNGs exist for the same tile type — e.g. `grass_1.png`, `grass_2.png`, `grass_3.png` all in `static_tiles/background_tile/` — calling `resolve_tile("grass")` randomly picks one. The client makes the same request every time but gets a different tile on each call. This is the static-tile equivalent of changing the `seed` on a generative request.

In `comfyui` mode, variation comes from changing the `seed` parameter; in `static` mode, variation comes from dropping more PNGs into the folder.

**How to add static background tile variants** (no code changes needed):

1. Place PNG files in `static_tiles/background_tile/` using the naming convention `{tile_type}_{n}.png`:
   ```
   static_tiles/background_tile/
     grass_1.png      → grouped under key "grass"
     grass_2.png      → grouped under key "grass"
     grass_3.png      → grouped under key "grass"
     sand_1.png       → grouped under key "sand"
     sand_2.png       → grouped under key "sand"
     water.png        → grouped under key "water" (single variant, always returned)
     stone.png        → grouped under key "stone" (single variant, always returned)
   ```
2. The `_scan_flat_named()` method in `StaticCatalog` strips the `_N` suffix and groups variants under their base key.
3. `resolve_tile("grass")` calls `random.choice()` across all grass variants — no API changes, no config changes.

The `GET /catalog` endpoint returns all tile types that have at least one variant, so clients can discover what's available at runtime:

```json
{
  "background_tile": {
    "tile_types": ["grass", "sand", "stone", "water"]
  }
}
```

### 3.4 How Terrain and Background Tiles Interact in a Game

A game engine layers them:

```
Layer 3:  Structures & Objects  (isolated sprites on top)
Layer 2:  Terrain features       (hills, slopes, cliffs — alpha-masked sprites)
Layer 1:  Background tiles       (water, grass, sand, stone — seamless repeating)
```

A client would typically:
1. Generate a background tile: `POST /generate { "asset_family": "background_tile", "tile_type": "grass" }`
2. Generate a terrain feature for that tile: `POST /terrain { "category": "hill", "scale": "medium", "material": "earthen", "description": "a rounded grassy hill with a gentle slope on the left side" }`
3. Place the terrain sprite on top of the grass tile in the game engine

### 3.5 CoW Inpainting Still Works

The existing CoW system operates on background tiles — painting paths, roads, and other flat features directly into the tile texture. This sits at Layer 1 and is orthogonal to the terrain pipeline (Layer 2). Both can coexist on the same tile: a grass background tile with a dirt path inpainted onto it, then a hill terrain sprite placed on top.

---

## 4. End-to-End Flow

Here is the flow for a structure request (object and terrain are identical in structure):

1. **Client sends:**
```json
POST /structure
{
  "category": "sacred",
  "style": "gothic",
  "condition": "pristine",
  "scale": "large",
  "description": "a grand cathedral with twin bell towers and a rose window above the entrance"
}
```

2. **Server validates** enums against known values. Returns 422 if invalid.

3. **Server builds the inner prompt** (from injection maps):
```
a large imposing grand structure that dominates the landscape, monumental scale, complex architecture with multiple sections and towers a reverent religious building with stained glass, spire or steeple, ceremonial entrance, spiritual architectural grandeur in gothic style with pointed arches soaring upward, flying buttresses, tall spires, ornate stone tracery, large rose window, vertical emphasis freshly built, clean stonework with bright mortar, new timber showing no weathering, sharp edges and crisp details a grand cathedral with twin bell towers and a rose window above the entrance
```

4. **Server wraps in the template** (from `config/prompt_templates.json`):
```
<tdp> Front view overhead shot elevated shot medium shot. The structure faces the camera straight from the front. The structure should flow into any inserted background. Isolate the object on a plain white background, only focusing on the specified object. [INNER PROMPT]. Pixel art 16x16 for game tile assets, crisp pixel edges, no anti-aliasing, centered single asset on white. Grounded, stable perspective, no floating objects.
```

5. **Sent to ComfyUI** via `txt2img.json` workflow (same node structure as existing generation — single-shot txt2img, no img2img or reference images needed).

6. **Result saved**, persisted to SQLite, returned to client with `prompt_used` for transparency.

**Terrain example** (same flow, different params):

```
POST /terrain
{
  "category": "hill",
  "scale": "medium",
  "material": "earthen",
  "description": "a rounded grassy hill with a gentle slope on the left side, wildflowers scattered on top"
}
```

Inner prompt:
```
a noticeable elevation change of 3-4 pixels, moderate footprint occupying most of the tile, distinct landform a rounded mound or hill rising from the base plane, soft organic contour, natural elevation feature with grass-topped soil with exposed dirt on steeper faces, green surface with brown earth edges, pastoral character material a rounded grassy hill with a gentle slope on the left side, wildflowers scattered on top
```

---

## 5. File Structure

We use a **consolidated approach** — the three tile pipelines are similar enough to share files, unlike the leader pipeline which has multi-stage complexity justifying its own files.

```
src/
  tile_models.py            # All enums + Pydantic request/response for structure, object, terrain
  tile_prompts.py           # All injection maps + build_structure_prompt(), build_object_prompt(), build_terrain_prompt()
  tile_engine.py            # Unified orchestrator (ComfyUI generator, static fallback, placeholder)
  tile_registry.py          # Unified CRUD for StructureRecord, ObjectRecord, TerrainRecord
```

**Existing files to modify:**

| File | Change |
|---|---|
| `prompt_templates.json` | Add terrain template (isolated on white, not seamless tile), bump schema_version to 3 |
| `database.py` | Add `StructureRecord`, `ObjectRecord`, `TerrainRecord` tables |
| `config.yaml` / `config.py` | Add `structure`, `object`, `terrain` to `generation.modes` |
| `main.py` | Add `POST/GET/DELETE /structure`, `/object`, `/terrain` endpoints + catalog endpoints |
| `models.py` | (Optional) Keep old `GenerationRequest` for backward compat; new endpoints use `tile_models.py` |

**New files:**

| File | Purpose |
|---|---|
| `docs/tile_generation_plan.md` | This document — the complete written plan |
| `docs/client-api-tile-guide.md` | Client-facing prompt-writing guide with BAD/GOOD examples and enum quick-reference |

---

## 6. Key Design Decisions

### 6.1 No multi-stage pipeline for tiles

Unlike leaders (splash→profile→action with img2img reference images), tiles are **single-shot txt2img**. No reference images, no seed anchoring across stages. The engine is dramatically simpler — just build prompt, call ComfyUI, save, return.

### 6.2 Shared enums where appropriate

`Biome` is used by both `Object` and `Terrain` pipelines. Defined once in `tile_models.py`, imported by both. `Season` is object-only. `TerrainScale` and `TerrainMaterial` are terrain-only. `EdgeStyle` has been removed — terrain features are isolated-on-white sprites, not seamless tiles, so edge blending is not applicable.

### 6.3 The `{PROMPT_HERE}` placeholder stays

The template wrapper in `config/prompt_templates.json` is the right abstraction. The server fills it with richly assembled prose from the injection maps. The client never sees the template. All templates (structure, object, terrain) follow the same "isolated on white" pattern — terrain is **not** a seamless-tile template.

### 6.4 Free-form `description` field

Exactly like `leader_description` in the leader pipeline, every tile request has a free-form text field for specifics the enums can't capture. This gives clients creative control while the enums guarantee quality and consistency. The client guide tells them what to include and exclude.

### 6.5 Consolidated files, not 3×4=12 files

`tile_models.py`, `tile_prompts.py`, `tile_engine.py`, `tile_registry.py` — four files instead of twelve. The leader pipeline justifies its own files because it has multi-stage complexity (splash→profile→action with workflow routing, reference image upload, seed anchoring) that tiles don't have.

### 6.6 Backward compatibility

The existing `POST /generate` endpoint and `GenerationRequest` model remain untouched. The new endpoints are additive. The old `structure_subtype` field on `GenerationRequest` continues to work for clients that haven't migrated.

### 6.7 Terrain ≠ Background Tiles

Terrain features (hills, slopes, cliffs) are isolated-on-white elevation sprites that sit on top of background tiles. Background tiles (water, grass, sand, stone) remain on `POST /generate` with `asset_family: "background_tile"`. This is a clean separation — terrain is a foreground overlay layer, not a base layer.

---

## 7. Client-Facing API Contract: How Clients Choose Params

There are **four mechanisms** ensuring clients have an easy way to choose parameters:

### 7.1 The client guide (`docs/client-api-tile-guide.md`)

A comprehensive, human-readable document providing:
- A clear mental model — three independent pipelines, no multi-stage dependencies
- BAD vs GOOD examples for every `description` field, showing exactly what to include/exclude
- Enum quick-reference tables at the bottom — all valid values in a scannable format
- Full example requests for each pipeline showing realistic combinations
- Error reference table

### 7.2 Catalog discovery endpoints (runtime)

```
GET /structure/catalog  → { categories: [...], styles: [...], conditions: [...], scales: [...] }
GET /object/catalog     → { categories: [...], biomes: [...], seasons: [...] }
GET /terrain/catalog    → { categories: [...], scales: [...], materials: [...] }
```

Clients discover all valid enum values at runtime — no hardcoding. If a new architectural style is added (e.g., `byzantine`), clients discover it automatically by calling the catalog endpoint.

### 7.3 Pydantic field descriptions (self-documenting API)

Every field on the request models carries a `description` parameter listing all valid values. FastAPI exposes these in the auto-generated OpenAPI docs at `/docs`. Example:

```python
category: str = Field(
    ...,
    description="One of: fortification, production, housing, sacred",
)
```

### 7.4 The `prompt_used` field in responses (transparency)

Every response includes the full assembled prompt. Clients can inspect what the server actually sent to ComfyUI, which helps them understand how their enum choices + description map to the final prompt. This is the same pattern as `LeaderResponse.prompt_used`.

---

## 8. Implementation Phases

| Phase | What | Effort | Files |
|---|---|---|---|
| **1. Models + Prompts** | `tile_models.py` (all enums + Pydantic schemas), `tile_prompts.py` (all injection maps + builders) | Medium | 2 new |
| **2. Prompt templates** | Add terrain template (isolated on white, not seamless tile), bump schema_version to 3 | Small | 1 edit |
| **3. Database** | Add `StructureRecord`, `ObjectRecord`, `TerrainRecord` to `database.py` | Small | 1 edit |
| **4. Engine + Registry** | `tile_engine.py` (ComfyUI + Static + Placeholder generators), `tile_registry.py` (CRUD) | Medium | 2 new |
| **5. API endpoints** | `POST/GET/DELETE /structure`, `/object`, `/terrain` + catalog endpoints in `main.py` | Medium | 1 edit |
| **6. Config** | Add `structure`, `object`, `terrain` to `generation.modes` in `config.yaml` | Small | 1 edit |
| **7. Client guide** | `docs/client-api-tile-guide.md` — prompt-writing guide | Done | 1 new |
| **8. This plan doc** | `docs/tile_generation_plan.md` — consolidated written plan | Done | 1 new |

---

## 9. Generation Modes (Per-Family)

Each tile pipeline respects the same mode system the rest of the app uses:

| Mode | Behaviour |
|---|---|
| `comfyui` | Always calls ComfyUI. 503 if unreachable. |
| `static` | Serves from `static_tiles/`. Falls back to placeholder. |
| `placeholder` | Always returns procedural coloured placeholder. |
| `random` | Coin-flip per request between comfyui and static. |

Controlled via `config.yaml` under `generation.modes.structure`, `generation.modes.object`, `generation.modes.terrain`.

---

## 10. Workflow Integration

All three tile pipelines use the existing `txt2img.json` workflow — the same one already used by the `/generate` endpoint for structures and nature objects. The only thing that changes per request is the positive prompt text and seed. Resolution, steps, CFG, sampler, and scheduler are baked into the workflow JSON and do not vary per request.

This means **no new ComfyUI workflows are needed** for the tile pipelines. The leader pipeline is the only one that requires custom workflows (splash/profile/action with img2img routing).
