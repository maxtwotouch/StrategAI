# Unit Generation API — Client Prompt Guide

═══════════════════════════════════════════════════════════════════
  UNIT GENERATION API — PROMPT WRITING GUIDE
═══════════════════════════════════════════════════════════════════

A single pipeline for top-down medieval character sprites.
Each unit generates one south-facing (front view) sprite at 512×512.

  POST /unit   → single character sprite


───────────────────────────────────────────────────────────────────
HOW IT WORKS
───────────────────────────────────────────────────────────────────

You pick a ``unit_type`` enum value and provide a free-form
``description``. The server maps the unit type to rich, hand-crafted
prose describing the character archetype, appends pixel-art style
directives (transparent background, crisp pixel edges, centered
sprite), and sends the assembled prompt to ComfyUI via the same
``txt2img.json`` workflow used by structure, object, and terrain
pipelines. You never write raw prompts.

All sprites are south-facing (front view) — the canonical direction
for top-down game characters facing the camera.


═══════════════════════════════════════════════════════════════════
  UNIT PIPELINE
═══════════════════════════════════════════════════════════════════

Endpoint:  POST /unit

FIELDS:

  unit_type    (required) — character archetype
  description  (required) — free-form specifics (20–400 chars)
  seed         (optional) — deterministic seed for reproducibility


───────────────────────────────────────────────────────────────────
UNIT TYPE — pick one
───────────────────────────────────────────────────────────────────

  archer       Ranged combat unit
               Medieval archer, bow in hand, quiver on back,
               leather armor, hooded cloak, light build,
               ranged combat stance

  scout        Fast reconnaissance unit
               Medieval scout, light leather armor, running
               pose, small dagger at belt, hood, lean build,
               fast agile movement, reconnaissance stance

  settler      Civilian non-combatant
               Medieval settler, civilian clothes, wool tunic,
               carrying bundle of supplies on shoulder, walking
               stick, non-combatant, humble appearance

  warrior      Heavy melee unit
               Medieval warrior, heavy plate armor, shield on
               arm, longsword, helmet with visor or nasal guard,
               stocky build, battle-ready stance


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

Archer:

  {
    "unit_type": "archer",
    "description": "a lean archer in a dark green hooded cloak
     over oiled brown leather armor, yew longbow drawn with an
     arrow nocked, quiver of white-fletched arrows on the back,
     crouched and alert stance"
  }

Warrior:

  {
    "unit_type": "warrior",
    "description": "a stocky warrior in burnished steel plate
     armor with gold trim at the pauldrons, a kite shield
     bearing a faded red lion crest, notched longsword held
     two-handed in a high guard, full helm with a T-slit visor,
     blue surcoat visible beneath the breastplate, feet planted
     wide in a battle-ready stance"
  }

Scout:

  {
    "unit_type": "scout",
    "description": "a wiry scout in a grey wool hood pulled low,
     dark leather vest over a linen shirt, a short curved dagger
     at the belt, mid-stride running pose, one hand holding the
     hood against wind, alert eyes scanning ahead"
  }

Settler:

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
    "seed": 123456789012345,
    "generation_mode": "comfyui",
    "status": "completed",
    "prompt_used": "pixel art top-down 2d game character sprite, ...",
    "resolution": "512x512",
    "generation_time_ms": 7120
  }

The ``url`` field is the canonical sprite URL — a single south-facing
(front view) 512×512 PNG with transparent background.


═══════════════════════════════════════════════════════════════════
  DISCOVERY & MANAGEMENT ENDPOINTS
═══════════════════════════════════════════════════════════════════

  GET  /unit/catalog     → available unit types
  GET  /unit             → list all generated units
  GET  /unit/{unit_id}   → get a specific unit by ID
  DELETE /unit/{unit_id} → remove a unit record

Catalog response:

  {
    "unit_types": ["archer", "scout", "settler", "warrior"]
  }


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
    archer.png
    scout.png
    settler.png
    warrior.png

A single PNG per unit type — simple flat naming.


═══════════════════════════════════════════════════════════════════
  ERROR REFERENCE
═══════════════════════════════════════════════════════════════════

| Scenario | HTTP Code | Message |
|---|---|---|
| ``unit_type`` missing or blank | 422 | Pydantic validation |
| ``description`` missing or blank | 422 | Pydantic validation |
| ``description`` < 20 chars | 422 | Pydantic validation |
| ``description`` > 400 chars | 422 | Pydantic validation |
| Invalid ``unit_type`` (e.g. ``"dragon"``) | 200 | Accepted by server (enum is not enforced at schema level) |
| ComfyUI unreachable | 503 | ``"Unit generation not available (ComfyUI unreachable)"`` |
| Generation error | 500 | ``"Internal server error: ..."`` |


═══════════════════════════════════════════════════════════════════
  ENUM QUICK-REFERENCE
═══════════════════════════════════════════════════════════════════

  UNIT TYPE
  archer
  scout
  settler
  warrior


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

All unit sprites are south-facing (front view) at 512×512 with
transparent backgrounds, ready for placement on the game map.

