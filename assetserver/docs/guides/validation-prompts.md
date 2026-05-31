# Validation Prompts — ComfyUI Workflow Testing

Copy any prompt below directly into its target workflow to validate that the
pipeline is healthy. Every prompt is the exact output of the current prompt
builders (`src/*/prompts.py`) with the listed configuration.

| # | Workflow | Family | Key Configuration |
|---|----------|--------|-------------------|
| 1 | `workflows/txt2img.json` | structure | fortification, nordic_wooden, pristine, small |
| 2 | `workflows/txt2img.json` | object | vegetation, temperate_forest, summer |
| 3 | `workflows/txt2img.json` | terrain | hill, medium, earthen |
| 4 | `workflows/txt2img.json` | unit | archer |
| 5 | `workflows/background_tile.json` | background_tile | water |
| 6 | `workflows/background_tile.json` | background_tile | grass |
| 7 | `workflows/background_tile.json` | background_tile | sand |
| 8 | `workflows/background_tile.json` | background_tile | stone |
| 9 | `workflows/background_tile.json` | background_tile | dirt |
| 10 | `workflows/leader/leader_splash.json` | leader_splash | Cleopatra — warrior_queen, ancient_egyptian, golden_hour, triumphant |
| 11 | `workflows/leader/leader_profile.json` | leader_profile | Cleopatra — warrior_queen, triumphant |
| 12 | `workflows/leader/leader_action.json` | leader_action | Cleopatra — warrior_queen, ancient_egyptian, golden_hour, triumphant, military |
| 13 | `workflows/leader/leader_splash.json` | leader_splash | Marcus Aurelius — philosopher_king, classical_greek, midday, contemplative |
| 14 | `workflows/leader/leader_profile.json` | leader_profile | Marcus Aurelius — philosopher_king, contemplative |
| 15 | `workflows/leader/leader_action.json` | leader_action | Multi-leader — Cleopatra + Marcus Aurelius, diplomatic (two leaders) |

---

### 1. Structure — Fortification / Nordic Wooden / Pristine / Small

**Seed:** `42` · **Resolution:** 512×512 · **Denoise:** 1.0 · **Workflow:** `workflows/txt2img.json`

```
<tdp> top-down view. The structure is viewed from directly above, showing its roof and layout. The structure blends naturally at its base edges. Isolate on a plain white background, only focusing on the specified object. a compact single-room footprint, modest proportions, humble village scale, simple unpretentious architecture a sturdy defensive structure with crenellated battlements, arrow slits, thick stone walls, watchtower, military functionality, in dark timber construction with carved dragon-head gables, steep shingled roof, iron hinges and fittings, Norse craftsmanship style, freshly built, clean stonework with bright mortar, new timber showing no weathering, sharp edges and crisp details, A small wooden watchtower with a pointed roof and a lookout platform.. Pixel art 16x16 game tile asset, crisp pixel edges, no anti-aliasing, sharp blocky pixels, centered single asset on white. Grounded stable perspective, no floating objects.
```

---

### 2. Object — Vegetation / Temperate Forest / Summer

**Seed:** `42` · **Resolution:** 512×512 · **Denoise:** 1.0 · **Workflow:** `workflows/txt2img.json`

```
<tdp> top-down view. The object is viewed from directly above, showing its top surface. The object blends naturally at its base edges. Isolate on a plain white background, only focusing on the specified object. a natural living plant with organic form, textured bark or stems, leaves or needles, rooted in the ground, in a deciduous woodland context with rich soil, leaf litter, ferns, varied greens, during full mature foliage, dry ground, warm tones, peak growth and ripeness, A large oak tree with a thick trunk and sprawling branches full of green leaves.. Pixel art 16x16 game tile asset, crisp pixel edges, no anti-aliasing, sharp blocky pixels, centered single asset on white. Grounded stable perspective, no floating objects.
```

---

### 3. Terrain — Hill / Medium / Earthen

**Seed:** `42` · **Resolution:** 512×512 · **Denoise:** 1.0 · **Workflow:** `workflows/txt2img.json`

```
<tdp> top-down view. The terrain elevation feature is viewed from directly above, showing its top surface and contours. The terrain blends naturally at its base edges. Isolate on a plain white background, only focusing on the specified object. a noticeable elevation change of 3-4 pixels, moderate footprint occupying most of the tile, distinct landform a rounded mound or hill rising from the base plane, soft organic contour, natural elevation feature, with grass-topped soil with exposed dirt on steeper faces, green surface with brown earth edges, pastoral character material, A rounded grassy hill with gentle slopes on all sides and a flat top.. Pixel art 16x16 game tile asset, crisp pixel edges, no anti-aliasing, sharp blocky pixels, centered single asset on white. The base of the terrain feature sits flush with the bottom of the frame. Grounded stable perspective, no floating objects.
```

---

### 4. Unit — Archer

**Seed:** `42` · **Resolution:** 512×512 · **Denoise:** 1.0 · **Workflow:** `workflows/txt2img.json`

```
<tdp> top-down view. pixel art top-down 2d game character sprite, medieval archer, bow in hand, quiver on back, leather armor, hooded cloak, light build, ranged combat stance, longbow aimed shot, facing camera front view full frontal, character looks at viewer, isolated on transparent background, crisp pixel edges sharp blocky pixels, centered single sprite game asset
```

---

### 5. Background Tile — Water

**Seed:** `42` · **Resolution:** 512×512 · **Denoise:** 1.0 · **Workflow:** `workflows/background_tile.json`

```
top-down seamless repeating water surface texture. The entire image must be one single 16x16 pixel art tile that fully fills the frame with continuous texture. No borders, no centered composition, no empty space. Generate one cohesive tile that can be seamlessly repeated in all directions. No disruptive features or objects touching the outermost pixel edges. Consistent texture density across whole image, top-down orthographic view, flat surface plane, crisp pixel edges, no anti-aliasing, sharp blocky pixels, perfect seamless tiling, simple and readable at small scale.
```

---

### 6. Background Tile — Grass

**Seed:** `42` · **Resolution:** 512×512 · **Denoise:** 1.0 · **Workflow:** `workflows/background_tile.json`

```
top-down seamless repeating grass ground texture. The entire image must be one single 16x16 pixel art tile that fully fills the frame with continuous texture. No borders, no centered composition, no empty space. Generate one cohesive tile that can be seamlessly repeated in all directions. No disruptive features or objects touching the outermost pixel edges. Consistent texture density across whole image, top-down orthographic view, flat ground plane, crisp pixel edges, no anti-aliasing, sharp blocky pixels, perfect seamless tiling, simple and readable at small scale.
```

---

### 7. Background Tile — Sand

**Seed:** `42` · **Resolution:** 512×512 · **Denoise:** 1.0 · **Workflow:** `workflows/background_tile.json`

```
top-down seamless repeating sand ground texture. The entire image must be one single 16x16 pixel art tile that fully fills the frame with continuous texture. No borders, no centered composition, no empty space. Generate one cohesive tile that can be seamlessly repeated in all directions. No disruptive features or objects touching the outermost pixel edges. Consistent texture density across whole image, top-down orthographic view, flat ground plane, crisp pixel edges, no anti-aliasing, sharp blocky pixels, perfect seamless tiling, simple and readable at small scale.
```

---

### 8. Background Tile — Stone

**Seed:** `42` · **Resolution:** 512×512 · **Denoise:** 1.0 · **Workflow:** `workflows/background_tile.json`

```
top-down seamless repeating stone ground texture. The entire image must be one single 16x16 pixel art tile that fully fills the frame with continuous texture. No borders, no centered composition, no empty space. Generate one cohesive tile that can be seamlessly repeated in all directions. No disruptive features or objects touching the outermost pixel edges. Consistent texture density across whole image, top-down orthographic view, flat ground plane, crisp pixel edges, no anti-aliasing, sharp blocky pixels, perfect seamless tiling, simple and readable at small scale.
```

---

### 9. Background Tile — Dirt

**Seed:** `42` · **Resolution:** 512×512 · **Denoise:** 1.0 · **Workflow:** `workflows/background_tile.json`

```
top-down seamless repeating dirt ground texture. The entire image must be one single 16x16 pixel art tile that fully fills the frame with continuous texture. No borders, no centered composition, no empty space. Generate one cohesive tile that can be seamlessly repeated in all directions. No disruptive features or objects touching the outermost pixel edges. Consistent texture density across whole image, top-down orthographic view, flat ground plane, crisp pixel edges, no anti-aliasing, sharp blocky pixels, perfect seamless tiling, simple and readable at small scale.
```

---

### 10. Leader Splash — Warrior Queen / Egyptian / Golden Hour / Triumphant

**Seed:** `42` · **Resolution:** 1920×1088 · **Denoise:** 1.0 · **Workflow:** `workflows/leader/leader_splash.json`

```
epic cinematic wide composition of A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress., standing proudly, martial bearing, armor and weapons prominent, battle-hardened confidence, in a vast sandstone temple with towering hieroglyph-carved pillars, gold and lapis lazuli accents, bronze braziers burning incense, desert beyond colonnades, low golden sunlight casting long dramatic shadows, warm amber glow suffusing everything, dust motes dancing in light beams, expression of hard-won victory, proud celebratory atmosphere, head held high, epic civilization leader splash screen, cinematic composition with dramatic chiaroscuro lighting, painterly oil style, anatomically correct human figure with proper limb proportions, well-formed hands with five distinct fingers, natural joint articulation, symmetrical facial features, widescreen 16:9 format, professional cinematic quality, ultra-detailed
```

---

### 11. Leader Profile — Warrior Queen / Triumphant

**Seed:** `42` · **Resolution:** (workflow default) · **Denoise:** 0.30 · **Workflow:** `workflows/leader/leader_profile.json`

```
An extremely close-up professional portrait of A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress., expression of hard-won victory, proud celebratory atmosphere, head held high, face filling the frame, headpiece and collar visible at the edges of the frame, professional character profile portrait, sharp eye focus with dramatic Rembrandt-style lighting, shallow depth of field with smooth bokeh background, detailed facial features, symmetrical well-proportioned facial anatomy, square 1:1 format, professional cinematic quality, close-up portrait
```

---

### 12. Leader Action — Warrior Queen / Egyptian / Golden Hour / Triumphant / Military

**Seed:** `42` · **Resolution:** (workflow default) · **Denoise:** 0.60 · **Workflow:** `workflows/leader/leader_action.json`

```
epic cinematic scene depicting A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress., Leading troops into battle with sword raised high, in a vast sandstone temple with towering hieroglyph-carved pillars, gold and lapis lazuli accents, bronze braziers burning incense, desert beyond colonnades, low golden sunlight casting long dramatic shadows, warm amber glow suffusing everything, dust motes dancing in light beams, expression of hard-won victory, proud celebratory atmosphere, head held high, dynamic action composition, weapons drawn, battlefield context with smoke and banners, cavalry and infantry in motion, dramatic civilization event scene, painterly oil style with dynamic composition, anatomically correct human figure with proper limb proportions, well-formed hands with five distinct fingers, natural joint articulation, symmetrical facial features, consistent character rendering, widescreen 16:9 cinematic format, professional cinematic quality, dynamic action
```

---

### 13. Leader 2 Splash — Philosopher King / Classical Greek / Midday / Contemplative

**Seed:** `42` · **Resolution:** 1920×1088 · **Denoise:** 1.0 · **Workflow:** `workflows/leader/leader_splash.json`

```
epic cinematic wide composition of A stoic Roman emperor with a greying beard, deep-set contemplative eyes, wearing a simple purple-trimmed toga. He holds an open scroll of Meditations., seated or standing in contemplation, scrolls or scientific instruments nearby, learned wisdom, in a marble temple with corinthian columns, olive groves on the hillside, Aegean blue sea in the distance, white stone catching golden light, harsh clear sunlight from overhead, strong contrast with deep black shadows, bright cloudless sky, expression of deep thought, quiet introspective atmosphere, weighing profound decisions, epic civilization leader splash screen, cinematic composition with dramatic chiaroscuro lighting, painterly oil style, anatomically correct human figure with proper limb proportions, well-formed hands with five distinct fingers, natural joint articulation, symmetrical facial features, widescreen 16:9 format, professional cinematic quality, ultra-detailed
```

---

### 14. Leader 2 Profile — Philosopher King / Contemplative

**Seed:** `42` · **Resolution:** (workflow default) · **Denoise:** 0.30 · **Workflow:** `workflows/leader/leader_profile.json`

```
An extremely close-up professional portrait of A stoic Roman emperor with a greying beard, deep-set contemplative eyes, wearing a simple purple-trimmed toga. He holds an open scroll of Meditations., expression of deep thought, quiet introspective atmosphere, weighing profound decisions, face filling the frame, headpiece and collar visible at the edges of the frame, professional character profile portrait, sharp eye focus with dramatic Rembrandt-style lighting, shallow depth of field with smooth bokeh background, detailed facial features, symmetrical well-proportioned facial anatomy, square 1:1 format, professional cinematic quality, close-up portrait
```

---

### 15. Multi-Leader Action — Cleopatra VII + Marcus Aurelius / Diplomatic

**Seed:** `42` · **Resolution:** (workflow default) · **Denoise:** 0.60 · **Workflow:** `workflows/leader/leader_action.json`

Two leaders interacting in a single action scene. This validates the
`generate_multi_action` pipeline — generate both leaders' splash images first,
then run this prompt with `LoadImage` referencing both reference images.

```
epic cinematic scene depicting two leaders interacting: Cleopatra VII, A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress., and Marcus Aurelius, A stoic Roman emperor with a greying beard, deep-set contemplative eyes, wearing a simple purple-trimmed toga. He holds an open scroll of Meditations., Two leaders meeting at a marble negotiating table in a grand hall, exchanging treaty scrolls while advisors look on, in a vast sandstone temple with towering hieroglyph-carved pillars, gold and lapis lazuli accents, bronze braziers burning incense, desert beyond colonnades, low golden sunlight casting long dramatic shadows, warm amber glow suffusing everything, dust motes dancing in light beams, expression of hard-won victory, proud celebratory atmosphere, head held high, formal court or neutral meeting ground, treaty documents on the table, multiple parties present, ceremonial exchange unfolding, dramatic civilization event scene, painterly oil style with dynamic composition, anatomically correct human figure with proper limb proportions, well-formed hands with five distinct fingers, natural joint articulation, symmetrical facial features, consistent character rendering, widescreen 16:9 cinematic format, professional cinematic quality, dynamic action
```

---

## Usage

### In ComfyUI

1. Load the target workflow JSON file
2. Paste the prompt into the `CLIPTextEncode` node (node #2, "Positive Prompt")
3. Set the seed in `SamplerCustomAdvanced` or `RandomNoise`
4. Queue and generate

### Via the API

These exact prompts are produced by the following requests:

```bash
# Structure
curl -X POST http://localhost:8000/structure \
  -H "Content-Type: application/json" \
  -d '{"category":"fortification","style":"nordic_wooden","condition":"pristine","scale":"small","description":"A small wooden watchtower with a pointed roof and a lookout platform.","seed":42}'

# Object
curl -X POST http://localhost:8000/object \
  -H "Content-Type: application/json" \
  -d '{"category":"vegetation","biome":"temperate_forest","season":"summer","description":"A large oak tree with a thick trunk and sprawling branches full of green leaves.","seed":42}'

# Terrain
curl -X POST http://localhost:8000/terrain \
  -H "Content-Type: application/json" \
  -d '{"category":"hill","scale":"medium","material":"earthen","description":"A rounded grassy hill with gentle slopes on all sides and a flat top.","seed":42}'

# Unit
curl -X POST http://localhost:8000/unit \
  -H "Content-Type: application/json" \
  -d '{"unit_type":"archer","description":"longbow aimed shot","seed":42}'

# Background Tile — water (repeat with "grass","sand","stone","dirt")
curl -X POST http://localhost:8000/background_tile \
  -H "Content-Type: application/json" \
  -d '{"tile_type":"water","seed":42}'

# Leader Splash — Cleopatra VII
curl -X POST http://localhost:8000/leader \
  -H "Content-Type: application/json" \
  -d '{"leader_name":"Cleopatra VII","leader_description":"A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress.","archetype":"warrior_queen","culture":"ancient_egyptian","time_of_day":"golden_hour","mood":"triumphant","asset_type":"splash","seed":42}'

# Leader Splash — Marcus Aurelius
curl -X POST http://localhost:8000/leader \
  -H "Content-Type: application/json" \
  -d '{"leader_name":"Marcus Aurelius","leader_description":"A stoic Roman emperor with a greying beard, deep-set contemplative eyes, wearing a simple purple-trimmed toga. He holds an open scroll of Meditations.","archetype":"philosopher_king","culture":"classical_greek","time_of_day":"midday","mood":"contemplative","asset_type":"splash","seed":42}'

# Multi-leader action — Cleopatra + Marcus Aurelius (diplomatic)
# Requires both leaders to exist first (generate splash for each, capture their IDs)
curl -X POST http://localhost:8000/leader \
  -H "Content-Type: application/json" \
  -d '{"leader_ids":["<cleopatra_id>","<marcus_id>"],"asset_type":"action","action_category":"diplomatic","action_description":"Two leaders meeting at a marble negotiating table in a grand hall, exchanging treaty scrolls while advisors look on","culture":"ancient_egyptian","time_of_day":"golden_hour","mood":"triumphant","seed":42}'
```

## Updating

When you intentionally change a prompt template or prose map, regenerate this
file by running:

```bash
python -c "
from src.tile.prompts import build_structure_prompt, build_object_prompt, build_terrain_prompt
from src.tile.models import StructureRequest, ObjectRequest, TerrainRequest
from src.unit.prompts import build_unit_prompt
from src.leader.prompts import build_splash_prompt, build_profile_prompt, build_action_prompt
from src.leader.models import LeaderRequest
from src.prompt_templates import render as _render

print('=== STRUCTURE ===')
req = StructureRequest(category='fortification',style='nordic_wooden',condition='pristine',scale='small',description='A small wooden watchtower with a pointed roof and a lookout platform.')
print(build_structure_prompt(req))
# ... repeat for each entry
"
```
