# Unit Generation API — Client Prompt Guide

═══════════════════════════════════════════════════════════════════
  UNIT GENERATION API — PROMPT WRITING GUIDE
═══════════════════════════════════════════════════════════════════

A single pipeline for top-down medieval character sprites with
directional facings. Each unit type generates up to 4 cardinal
directions (south/north/east/west) as separate 512×512 sprites.

  POST /unit   → character sprites with directional facings


───────────────────────────────────────────────────────────────────
HOW IT WORKS
───────────────────────────────────────────────────────────────────

You pick a ``unit_type`` enum value and provide a free-form
``description``. The server maps the unit type to rich, hand-crafted
prose describing the character archetype, then assembles a complete
pixel-art prompt behind the scenes. You never write raw prompts.

Optionally, you can request a single direction (e.g. ``"s"`` for
south/front) for fast iteration — ~4× faster than generating all
four facings.

The assembled prompt is wrapped in a template from the server's
``config/prompt_templates.json`` (pixel-art style directives, 512×512
sprite constraints, transparent background isolation) and sent to
ComfyUI via the same ``txt2img.json`` workflow used by structure,
object, and terrain pipelines.


═══════════════════════════════════════════════════════════════════
  UNIT PIPELINE
═══════════════════════════════════════════════════════════════════

Endpoint:  POST /unit

FIELDS:

  unit_type    (required) — character archetype
  description  (required) — free-form specifics (20–400 chars)
  direction    (optional) — single direction or all 4
  seed         (optional) — deterministic seed for reproducibility


───────────────────────────────────────────────────────────────────
UNIT TYPE — pick one
───────────────────────────────────────────────────────────────────

  archer       Ranged combat unit
               Bow in hand, quiver on back, leather armor,
               hooded cloak, light build, ranged combat stance

  scout        Fast reconnaissance unit
               Light leather armor, running pose, small dagger
               at belt, hood, lean build, agile movement

  settler      Civilian non-combatant
               Wool tunic, carrying bundle of supplies on
               shoulder, walking stick, humble appearance

  warrior      Heavy melee unit
               Plate armor, shield on arm, longsword, helmet
               with visor or nasal guard, stocky build,
               battle-ready stance


───────────────────────────────────────────────────────────────────
DIRECTION — pick one (optional)
───────────────────────────────────────────────────────────────────

When omitted, all 4 directions are generated. When set, only
that single facing is produced — ~4× faster.

  s     South / front   — character faces camera (canonical)
  n     North / back    — character faces away
  e     East / right    — character faces right
  w     West / left     — character faces left

The south-facing sprite is canonical. If you only generate one
direction, make it ``"s"``. In static mode, missing directions
fall back to the south sprite automatically.


───────────────────────────────────────────────────────────────────
DESCRIPTION — free-form text (20–400 characters)
───────────────────────────────────────────────────────────────────

Describe the specific character you want. Be concrete about
materials, colours, and what makes this unit distinct.

  INCLUDE:
    • Clothing colour and material (crimson wool tunic, oiled
      leather jerkin, burnished steel plate)
    • Weapon details (notched longsword, yew longbow, iron-
      rimmed wooden shield with painted crest)
    • Posture and stance (crouched and alert, standing guard,
      mid-stride)
    • One distinctive feature (feathered cap, scar across the
      eye, hood pulled low, crest on shield, tattered cloak)
    • Build (lean, stocky, tall, wiry)

  DO NOT INCLUDE:
    • Camera directions ("top-down", "front view", "side view")
    • Style words ("pixel art", "16×16", "sprite sheet")
    • Image quality words ("crisp", "detailed", "high resolution")
    • Background description (the server handles transparent
      background)
    • Abstract vibes ("epic", "awesome", "cool")

  BAD (18 chars):
    "a cool archer guy"

  GOOD (280 chars):
    "a lean archer in a dark green hooded cloak over oiled
     brown leather armor, yew longbow drawn with an arrow
     nocked, quiver of white-fletched arrows on the back,
     a green cloth wrapped around the lower face, crouched
     and alert stance, light on the feet"

  BAD (22 chars):
    "a warrior with a sword"

  GOOD (290 chars):
    "a stocky warrior in burnished steel plate armor with
     gold trim at the pauldrons, a kite shield bearing a
     faded red lion crest, notched longsword held two-handed
     in a high guard, full helm with a T-slit visor, blue
     surcoat visible beneath the breastplate, feet planted
     wide in a battle-ready stance"


───────────────────────────────────────────────────────────────────
EXAMPLE REQUESTS
───────────────────────────────────────────────────────────────────

Single direction — fast iteration (south-facing archer):

  {
    "unit_type": "archer",
    "direction": "s",
    "description": "a lean archer in a dark green hooded cloak
     over oiled brown leather armor, yew longbow drawn with an
     arrow nocked, quiver of white-fletched arrows on the back,
     crouched and alert stance"
  }

All four directions — full unit (warrior):

  {
    "unit_type": "warrior",
    "description": "a stocky warrior in burnished steel plate
     armor with gold trim at the pauldrons, a kite shield
     bearing a faded red lion crest, notched longsword held
     two-handed in a high guard, full helm with a T-slit visor,
     blue surcoat visible beneath the breastplate, feet planted
     wide in a battle-ready stance"
  }

Scout — single direction:

  {
    "unit_type": "scout",
    "direction": "s",
    "description": "a wiry scout in a grey wool hood pulled low,
     dark leather vest over a linen shirt, a short curved dagger
     at the belt, mid-stride running pose, one hand holding the
     hood against wind, alert eyes scanning ahead"
  }

Settler — all four directions:

  {
    "unit_type": "settler",
    "description": "a humble settler in a patched brown wool
     tunic with a rope belt, a large cloth bundle tied to a
     walking stick resting on the shoulder, worn leather boots,
     a wide-brimmed straw hat, walking pose with a slight stoop,
     weary but determined expression"
  }


═══════════════════════════════════════════════════════════════════
  RESPONSE FORMAT
═══════════════════════════════════════════════════════════════════

A successful POST /unit returns:

  {
    "url": "/assets/a1b2c3d4.png",
    "asset_type": "unit",
    "unit_id": "unit_archer_a1b2c3",
    "unit_type": "archer",
    "directions": {
      "s": "/assets/a1b2c3d4.png",
      "n": "/assets/e5f6g7h8.png",
      "e": "/assets/i9j0k1l2.png",
      "w": "/assets/m3n4o5p6.png"
    },
    "generated_directions": ["s", "n", "e", "w"],
    "seed": 123456789012345,
    "generation_mode": "comfyui",
    "status": "completed",
    "prompt_used": "pixel art top-down 2d game character sprite, ...",
    "resolution": "512x512",
    "generation_time_ms": 28450
  }

When only a single direction is requested (e.g. ``"s"``):

  {
    "directions": {
      "s": "/assets/a1b2c3d4.png",
      "n": null,
      "e": null,
      "w": null
    },
    "generated_directions": ["s"],
    ...
  }

The ``directions`` object always has all four keys (s/n/e/w).
Non-generated directions are ``null``. The south-facing sprite
is always present and is the canonical reference.


═══════════════════════════════════════════════════════════════════
  DISCOVERY & MANAGEMENT ENDPOINTS
═══════════════════════════════════════════════════════════════════

  GET  /unit/catalog     → available unit_types and directions
  GET  /unit             → list all generated units
  GET  /unit/{unit_id}   → get a specific unit by ID
  DELETE /unit/{unit_id} → remove a unit record

Catalog response:

  {
    "unit_types": ["archer", "scout", "settler", "warrior"],
    "directions": ["e", "n", "s", "w"]
  }


═══════════════════════════════════════════════════════════════════
  ENUM QUICK-REFERENCE TABLE
═══════════════════════════════════════════════════════════════════

UNIT TYPE            DIRECTION
archer               s  (south / front — canonical)
scout                n  (north / back)
settler              e  (east / right)
warrior              w  (west / left)


═══════════════════════════════════════════════════════════════════
  GENERATION MODES
═══════════════════════════════════════════════════════════════════

Unit generation respects the same per-family mode system as all
other pipelines, controlled via ``config.yaml``:

  generation:
    modes:
      unit: "comfyui"    # or "static" / "placeholder" / "random"

| Mode          | Behaviour |
|---------------|-----------|
| ``comfyui``   | Generates via ComfyUI txt2img. 503 if unreachable. |
| ``static``    | Serves pre-made PNGs from ``static_tiles/unit/``. Falls back to placeholder. |
| ``placeholder`` | Always returns procedural coloured rectangles with labels. |
| ``random``    | Coin-flip between comfyui and static per request. |

In static mode, sprites are resolved from:

  static_tiles/unit/
    archer_s.png      ← south (canonical)
    archer_n.png      ← north (falls back to archer_s.png if missing)
    archer_e.png      ← east  (falls back to archer_s.png if missing)
    archer_w.png      ← west  (falls back to archer_s.png if missing)
    warrior_s.png
    ...

Missing direction files automatically fall back to the south-
facing sprite. Only ``{unit_type}_s.png`` is strictly required.


═══════════════════════════════════════════════════════════════════
  LAYERING MODEL (for game engine integration)
═══════════════════════════════════════════════════════════════════

  Layer 4:  Units (characters)        ← POST /unit
  Layer 3:  Structures & Objects      ← POST /structure, POST /object
  Layer 2:  Terrain features          ← POST /terrain
  Layer 1:  Background tiles          ← POST /generate

Units sit on top of everything — they're the characters that
move across the map. Generate bottom-up: background tile first,
then terrain, then structures/objects, then units on top.

Each unit has up to 4 directional sprites. Your game engine
should swap between them based on the character's facing
direction. The south sprite is the canonical front view.

