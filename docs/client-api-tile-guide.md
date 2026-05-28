# Tile Generation API — Client Prompt Guide

═══════════════════════════════════════════════════════════════════
  TILE GENERATION API — PROMPT WRITING GUIDE
═══════════════════════════════════════════════════════════════════

Three independent pipelines. No multi-stage dependencies — every
request is a standalone txt2img generation.

  POST /structure   → buildings and architecture
  POST /object      → nature objects, props, debris
  POST /terrain     → elevation features (hills, cliffs, etc.)


───────────────────────────────────────────────────────────────────
HOW IT WORKS
───────────────────────────────────────────────────────────────────

You pick enum values for category, style, condition, scale, etc.
The server maps each enum to rich, hand-crafted prose and assembles
a complete prompt behind the scenes. You never write raw prompts.

You also provide a free-form `description` field for specifics the
enums can't capture — exactly like `leader_description` in the
leader pipeline.

The assembled prompt is wrapped in a template from the server's
`config/prompt_templates.json` (pixel-art style directives, 16×16 tile
constraints, white background isolation) and sent to ComfyUI.


═══════════════════════════════════════════════════════════════════
  STRUCTURE PIPELINE
═══════════════════════════════════════════════════════════════════

Endpoint:  POST /structure

FIELDS:

  category     (required) — what kind of building
  style        (required) — architectural style
  condition    (required) — state of the building
  scale        (required) — size tier
  description  (required) — free-form specifics (20–400 chars)
  seed         (optional) — deterministic seed for reproducibility


───────────────────────────────────────────────────────────────────
CATEGORY — pick one
───────────────────────────────────────────────────────────────────

  fortification    Defensive military structures
                   Towers, walls, gatehouses, keeps, battlements,
                   palisades, barbicans, watchtowers, bastions

  production       Industrial / crafting buildings
                   Forges, windmills, watermills, workshops,
                   lumber mills, kilns, smithies, breweries

  housing          Residential buildings
                   Townhouses (small/medium/large), taverns, inns,
                   cottages, manors, farmhouses, longhouses

  sacred           Religious / ceremonial buildings
                   Churches, cathedrals, shrines, temples,
                   monasteries, chapels, abbeys


───────────────────────────────────────────────────────────────────
STYLE — pick one
───────────────────────────────────────────────────────────────────

  nordic_wooden       Dark timber, carved dragon-head gables,
                      steep shingled roofs, iron fittings

  anglo_saxon_stone   Rough-hewn stone, thatched roofs, low
                      profiles, timber framing, wattle-and-daub

  norman_romanesque   Heavy stone, round arches, thick pillars,
                      small windows, fortress-like solidity

  gothic              Pointed arches, flying buttresses, tall
                      spires, ornate stone tracery, rose windows

  mediterranean       Warm terracotta tiles, whitewashed walls,
                      arched colonnades, cypress trees nearby

  slavic_timber       Horizontal log construction, carved wooden
                      trim, onion-dome influences, steep roofs

  moorish             Horseshoe arches, geometric tile patterns,
                      courtyards, intricate stucco, domed roofs


───────────────────────────────────────────────────────────────────
CONDITION — pick one
───────────────────────────────────────────────────────────────────

  pristine              Freshly built, clean stonework, bright
                        mortar, new timber, no wear

  weathered             Aged stone with moss and lichen, faded
                        timber, settled foundation, lived-in

  ruined                Collapsed roof sections, ivy-covered walls,
                        broken windows, scattered rubble

  under_construction    Wooden scaffolding, half-built walls,
                        piles of stone and timber, workers' tools

  fortified             Extra defensive additions — reinforced
                        doors, added battlements, barricades


───────────────────────────────────────────────────────────────────
SCALE — pick one
───────────────────────────────────────────────────────────────────

  small     Compact single-room footprint, modest proportions
            Example: cottage, shrine, small watchtower, smithy

  medium    Substantial multi-room building, prominent in a
            village setting
            Example: townhouse, church, forge, tavern

  large     Imposing grand structure, dominates the landscape
            Example: cathedral, castle keep, great hall, abbey


───────────────────────────────────────────────────────────────────
DESCRIPTION — free-form text (20–400 characters)
───────────────────────────────────────────────────────────────────

Describe the specific building you want. Be concrete about
materials, distinctive features, and what makes this building
unique within its category.

  INCLUDE:
    • Roof material and shape (thatched, shingled, slate, flat)
    • Number of stories / height cues
    • One distinctive feature (bell tower, chimney smoke, signboard,
      stained glass window, portcullis, water wheel)
    • What's immediately around the entrance
    • Any visible activity indicators (lit windows, smoke, open doors)

  DO NOT INCLUDE:
    • Camera directions ("top-down", "overhead", "front view")
    • Style words ("pixel art", "16x16", "tile asset")
    • Image quality words ("crisp", "detailed", "high resolution")
    • Background description (the server handles white background)
    • Abstract vibes ("epic", "awesome", "cool")

  BAD (18 chars):
    "a cool castle"

  GOOD (280 chars):
    "a two-story stone gatehouse with a raised iron portcullis,
     crenellated parapet with archer slits, heavy oak doors banded
     with iron, twin torch sconces flanking the entrance, a small
     guardroom window glowing with candlelight above the gate"

  BAD (30 chars):
    "a nice little house for villagers"

  GOOD (260 chars):
    "a half-timbered two-story townhouse with a steep thatched roof,
     diamond-pane leaded windows with wooden shutters thrown open,
     a carved wooden signboard hanging above the door, chimney
     trailing thin smoke, a small herb garden beside the entrance"


───────────────────────────────────────────────────────────────────
EXAMPLE REQUESTS
───────────────────────────────────────────────────────────────────

Minimal — a weathered nordic wooden small house:

  {
    "category": "housing",
    "style": "nordic_wooden",
    "condition": "weathered",
    "scale": "small",
    "description": "a humble single-room cottage with a steep
     shingled roof, carved dragon-head beam ends, a smoking
     chimney, firewood stacked beside the door"
  }

Maximal — a pristine gothic large sacred building:

  {
    "category": "sacred",
    "style": "gothic",
    "condition": "pristine",
    "scale": "large",
    "description": "a grand cathedral with twin bell towers,
     a large rose window above the main entrance, flying
     buttresses along the nave, ornate stone tracery, three
     arched doorways with carved tympanums, a spire rising
     from the crossing"
  }

Fortification — a ruined norman romanesque medium tower:

  {
    "category": "fortification",
    "style": "norman_romanesque",
    "condition": "ruined",
    "scale": "medium",
    "description": "a square stone keep with a collapsed corner
     exposing the interior, ivy covering the remaining walls,
     a broken wooden door hanging from one hinge, rubble
     scattered at the base"
  }

Production — a pristine mediterranean medium windmill:

  {
    "category": "production",
    "style": "mediterranean",
    "condition": "pristine",
    "scale": "medium",
    "description": "a whitewashed stone windmill with four
     wooden sails, a conical terracotta-tiled roof, a wooden
     loading platform at the upper door, sacks of grain visible
     through the ground-floor archway"
  }


═══════════════════════════════════════════════════════════════════
  OBJECT PIPELINE
═══════════════════════════════════════════════════════════════════

Endpoint:  POST /object

FIELDS:

  category     (required) — what kind of object
  biome        (required) — environmental context
  season       (required) — seasonal appearance
  description  (required) — free-form specifics (20–400 chars)
  seed         (optional)


───────────────────────────────────────────────────────────────────
CATEGORY — pick one
────────────────────────────────────────────────────────────────���──

  vegetation     Living plants
                 Trees (oak, pine, dead, fruit), bushes, shrubs,
                 flowers, crops, mushrooms, vines

  geological     Natural rock formations
                 Boulders, rock clusters, cliffs, stalagmites,
                 crystal formations, stone outcrops

  rural_props    Countryside objects
                 Fences, hay bales, carts, wells, signposts,
                 barrels, troughs, scarecrows, beehives

  urban_props    Town/city objects
                 Street lamps, market stalls, statues, fountains,
                 benches, notice boards, hanging signs, crates

  debris         Broken / scattered objects
                 Rubble piles, broken carts, scattered bones,
                 fallen trees, abandoned campfires, wreckage


───────────────────────────────────────────────────────────────────
BIOME — pick one
───────────────────────────────────────────────────────────────────

  temperate_forest    Deciduous trees, ferns, moss, rich soil
  taiga               Conifers, snow patches, rocky ground, lichen
  desert              Sand, cacti, dry scrub, bleached stone
  swamp               Murky water, reeds, twisted trees, mud
  mountain            Exposed rock, sparse vegetation, scree
  coastal             Sandy shore, driftwood, sea-worn stone


───────────────────────────────────────────────────────────────────
SEASON — pick one
───────────────────────────────────────────────────────────────────

  spring    Fresh green growth, blossoms, new leaves, bright tones
  summer    Full foliage, dry ground, warm tones, mature plants
  autumn    Orange/red leaves, bare branches, fallen leaves, harvest
  winter    Bare trees, snow cover, ice, dormant vegetation


───────────────────────────────────────────────────────────────────
DESCRIPTION — free-form text (20–400 characters)
─────────────────────────────────────────────────��─────────────────

Describe the specific object. Be concrete about what it is and
what makes it distinct.

  INCLUDE:
    • Exact object type (not just "tree" — "ancient oak with
      gnarled branches")
    • Material and texture cues
    • Size relative to a person (if relevant)
    • One distinctive feature (hollow trunk, broken spoke, moss
      covering, carved initials, rusted metal)

  DO NOT INCLUDE:
    • Camera directions or style words
    • Background description
    • Abstract vibes

  BAD:
    "a tree"

  GOOD:
    "a massive ancient oak with thick gnarled branches spreading
     wide, a hollow at the base of the trunk, acorns scattered
     on the ground beneath, patches of moss on the north side
     of the bark"

  BAD:
    "some rocks"

  GOOD:
    "a cluster of three moss-covered granite boulders, the largest
     split cleanly in half with ferns growing from the crack,
     lichen patches in pale grey-green"


───────────────────────────────────────────────────────────────────
EXAMPLE REQUESTS
───────────────────────────────────���───────────────────────────────

Vegetation — autumn temperate forest tree:

  {
    "category": "vegetation",
    "biome": "temperate_forest",
    "season": "autumn",
    "description": "a tall oak tree with orange and red leaves
     still clinging to the branches, a thick trunk with rough
     bark, a pile of fallen leaves at the base, one low branch
     broken and hanging"
  }

Rural prop — summer coastal well:

  {
    "category": "rural_props",
    "biome": "coastal",
    "season": "summer",
    "description": "a circular stone well with a wooden bucket
     hanging from a rope over a crossbeam, a small shingled roof
     on two posts above it, sea-worn stones at the base, a
     weathered wooden crank handle"
  }

Debris — winter mountain wreckage:

  {
    "category": "debris",
    "biome": "mountain",
    "season": "winter",
    "description": "the shattered remains of a wooden cart half
     buried in snow, one wheel still intact but tilted, scattered
     planks and a broken axle, snow accumulating on the debris"
  }


═══════════════════════════════════════════════════════��═══════════
  TERRAIN PIPELINE — ELEVATION FEATURES
═══════════════════════════════════════════════════════════════════

IMPORTANT: terrain features are elevation sprites (hills, slopes,
cliffs) that sit ON TOP of background tiles — they are NOT ground
textures. Background tiles (water, grass, sand, stone) remain on
the existing POST /generate endpoint.

Endpoint:  POST /terrain

FIELDS:

  category     (required) — what kind of elevation feature
  scale        (required) — how tall / prominent
  material     (required) — what the feature is made of
  description  (required) — free-form specifics (20–400 chars)
  seed         (optional)


───────────────────────────────────────────────────────────────────
CATEGORY — pick one
───────────────────────────────────────────────────────────────────

  hill           Rounded mounds rising from the base plane
                 Gentle rolling hills, grassy knolls, sand dunes,
                 snowdrifts

  slope          Inclined surfaces with directional grade change
                 Ramps, stepped inclines, terraced land, gradual
                 elevation transitions

  cliff          Vertical or near-vertical rock faces
                 Sheer drops, bluff edges, cliff overhangs, rocky
                 escarpments with exposed strata

  ridge          Narrow elevated spines connecting higher points
                 Mountain ridges, ridgelines with slopes falling
                 away on both sides

  depression     Sunken areas below the base plane
                 Pits, sinkholes, craters, dried lakebeds, quarry
                 excavations, bowl-shaped hollows


───────────────────────────────────────────────────────────────────
SCALE — pick one
───────────────────────────────────────────────────────────────────

  low         Subtle barely-perceptible rise, 1–2 pixel height
              Small footprint, gentle feature
              Example: shallow mound, low berm, gentle ridge

  medium      Noticeable elevation, 3–4 pixel height
              Occupies most of the tile, distinct landform
              Example: proper hill, noticeable slope, modest cliff

  high        Prominent dramatic elevation, 5+ pixel height
              Fills the tile, dominant landscape feature
              Example: towering cliff face, steep mountain ridge,
              deep crater


───────────────────────────────────────────────────────────────────
MATERIAL — pick one
───────────────────────────────────────────────────────────────────

  earthen     Grass-topped soil, exposed dirt on steep faces
              Green surface, brown earth edges, pastoral
              Use with: hill, slope, ridge

  sandy       Loose granular sand, wind-rippled texture
              Warm beige and tan tones, soft curves
              Use with: hill (dunes), slope, depression

  rocky       Grey stone with strata lines, scattered boulders
              Hard angular edges, mineral tones
              Use with: cliff, ridge, slope

  snowy       White snow on top, darker ground on steep faces
              Crisp cold palette, ice patches
              Use with: hill, slope, ridge

  muddy       Dark wet earth with slick sheen, soft contours
              Deep brown tones, small puddles
              Use with: slope, depression


───────────────────────────────────────────────────────────────────
DESCRIPTION — free-form text (20–400 characters)
───────────────────────────────────────────────────────────────────

Describe the specific elevation feature. Focus on shape, contour,
and what distinguishes it.

  INCLUDE:
    • Shape and contour (rounded, jagged, stepped, smooth)
    • Which edges rise/fall (left side higher, slopes right)
    • Surface details (small rocks on top, grass tufts, snow cap)
    • What background tile it's meant to sit on (helps the model)

  DO NOT INCLUDE:
    • Camera directions or style words
    • Seamless/tileable (terrain is isolated-on-white)
    • Objects placed on top (that's what /object and /structure
      are for)

  BAD (8 chars):
    "a hill"

  GOOD:
    "a rounded grassy hill rising from the left, peaking two-thirds
     across the tile, gently sloping down to ground level at the
     right edge, a few small rocks embedded in the grass on the
     steeper face, meant to sit on a grass background tile"

  BAD (10 chars):
    "a cliff"

  GOOD:
    "a sheer grey rock cliff face with visible horizontal strata
     lines in lighter and darker grey bands, flat grassy top
     surface, sharp drop-off at the front edge, small loose stones
     at the base, meant to sit on stone background tile"


───────────────────────────────────────────────────────────────────
EXAMPLE REQUESTS
───────────────────────────────────────────────────────────────────

Medium earthen hill:

  {
    "category": "hill",
    "scale": "medium",
    "material": "earthen",
    "description": "a broad grassy hill rising from the bottom
     edge and peaking in the centre, gentle slope on all sides,
     patches of darker green moss on the north face, a few
     scattered wildflowers, meant for a grass tile"
  }

Low sandy slope:

  {
    "category": "slope",
    "scale": "low",
    "material": "sandy",
    "description": "a gentle sand slope rising from left to right,
     wind ripples in the sand surface, a few small pebbles
     embedded in the slope, meant for a sand tile"
  }

High rocky cliff:

  {
    "category": "cliff",
    "scale": "high",
    "material": "rocky",
    "description": "a towering vertical cliff face dominating the
     tile, three distinct grey stone strata bands, jagged uneven
     top edge, small rocky outcrops on the face, rubble at the
     base, meant for stone or grass tile below"
  }

Medium snowy ridge:

  {
    "category": "ridge",
    "scale": "medium",
    "material": "snowy",
    "description": "a narrow snow-covered ridgeline running
     diagonally across the tile, white snow cap on the crest,
     darker rocky patches visible where wind has scoured the snow,
     meant for snow or rock tile"
  }

Medium muddy depression:

  {
    "category": "depression",
    "scale": "medium",
    "material": "muddy",
    "description": "a bowl-shaped depression sinking into dark wet
     mud, a small puddle of brown water pooled at the lowest point,
     soft squelchy edges, a few reeds around the rim, meant for
     swamp or mud tile"
  }


╔═══════════════════════════════════════════════════════════════════
  ENUM QUICK-REFERENCE TABLES
╚═══════════════════════════════════════════════════════════════════

STRUCTURE
────────
CATEGORY              STYLE                  CONDITION
fortification         nordic_wooden          pristine
production            anglo_saxon_stone      weathered
housing               norman_romanesque      ruined
sacred                gothic                 under_construction
                      mediterranean          fortified
                      slavic_timber
                      moorish                SCALE
                                             small
                                             medium
                                             large


OBJECT
──────
CATEGORY              BIOME                  SEASON
vegetation            temperate_forest       spring
geological            taiga                  summer
rural_props           desert                 autumn
urban_props           swamp                  winter
debris                mountain
                      coastal


TERRAIN
───────
CATEGORY              SCALE                  MATERIAL
hill                  low                    earthen
slope                 medium                 sandy
cliff                 high                   rocky
ridge                                        snowy
depression                                   muddy


═══════════════════════════════════════════════════════════════════
  DISCOVERY ENDPOINTS
═══════════════════════════════════════════════════════════════════

Clients can discover all valid enum values at runtime — no need
to hardcode them:

  GET /structure/catalog
  GET /object/catalog
  GET /terrain/catalog

Each returns the available categories, styles, conditions, scales,
biomes, seasons, and materials. The server is the single source
of truth for what's valid.


═════════════════════════════════════════════════���═════════════════
  BACKGROUND TILES (existing POST /generate)
═══════════════════════════════════════════════════════════════════

Background tiles are the base ground layer — seamless repeating
textures that form the floor of your game map. Unlike structure,
object, and terrain pipelines, background tiles use the existing
POST /generate endpoint with a simple tile_type parameter.

Endpoint:  POST /generate

FIELDS:

  asset_family     (required) — must be "background_tile"
  tile_type        (required) — one of: water, grass, sand, stone
  base_image_id    (optional) — for copy-on-write inpainting
  inpaints         (optional) — list of inpainting patches

  {
    "asset_family": "background_tile",
    "tile_type": "grass"
  }


RANDOMIZATION — in static mode

When the server runs in static mode, background tiles are served
from the static_tiles/ folder. If multiple variants exist for a
tile type, the server randomly picks one on every request:

  static_tiles/background_tile/
    grass_1.png      ─┐
    grass_2.png       ├── POST /generate { tile_type: "grass" }
    grass_3.png      ─┘   → randomly returns one of the three

A single request can return different tiles each call — no need
to change parameters. This is the static-mode equivalent of
varying the seed in comfyui mode.

In comfyui mode, variation comes from changing the seed (future
addition) or from the inherent randomness of the diffusion model.


RANDOMIZATION — in comfyui mode

When the server runs in comfyui mode, the model generates a new
tile each call from prompt text. Each call is independent — the
same request produces a different result every time, just like
the structure/object/terrain pipelines.


DISCOVERING AVAILABLE TILE TYPES

  GET /catalog

Returns:

  {
    "background_tile": {
      "tile_types": ["grass", "sand", "stone", "water"]
    }
  }

Only tile types that have at least one static PNG (or are
supported by comfyui generation) appear in this list.


INPAINTING (CoW)

Background tiles support copy-on-write inpainting — paint paths,
roads, and other features directly into the tile texture:

  {
    "asset_family": "background_tile",
    "tile_type": "grass",
    "base_image_id": "abc123.png",
    "inpaints": [
      {
        "point_a": { "x": 0, "y": 256 },
        "point_b": { "x": 512, "y": 256 },
        "fill_type": "gravel_road"
      }
    ]
  }

This is orthogonal to the terrain pipeline. A grass tile with an
inpainted dirt path can still have a hill terrain sprite placed
on top of it.


LAYERING MODEL (for game engine integration)

  Layer 4:  Units (characters)        ← POST /unit
  Layer 3:  Structures & Objects      ← POST /structure, POST /object
  Layer 2:  Terrain features          ← POST /terrain
  Layer 1:  Background tiles          ← POST /generate

Generate bottom-up: background tile first, then terrain features
for elevation, then structures and objects, then units on top.

See docs/client-api-unit-guide.md for the unit generation API.
