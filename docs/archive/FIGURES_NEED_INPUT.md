# Figures Requiring Team Input

**Date**: May 31, 2026  
**Status**: Assessment of figures that cannot be auto-generated and require manual input  
**Context**: INF-3600 Generative AI course project report

---

## Executive Summary

Two recommended figures require actual game data, screenshots, or generated images that cannot be automatically produced:

1. **Generated Asset Examples Grid** — Actual images from the asset server showing the 6 asset families
2. **AI Decision Logs** — Real LLM reasoning traces from a playthrough session

Both are **important for academic credibility** but not critical for report completion. The 7 Mermaid diagrams (fig1-fig7) provide the core architectural and conceptual figures.

---

## Figure A: Generated Asset Examples Grid

### What's Needed

A 2×3 or 3×2 grid showing **one example from each of the 6 asset families**:

| Asset Family | Example | Description |
|--------------|---------|-------------|
| **Structure** | Medieval granary or fortification | Shows building/city art |
| **Nature Object** | Tree, rock, or bush | Shows environmental decoration |
| **Terrain Feature** | Hills, forest, or mountain overlay | Shows elevation/relief |
| **Unit** | Warrior, archer, or scout sprite | Shows character sprite (south-facing) |
| **Background Tile** | Water, grass, stone, or sand | Shows base terrain texture |
| **Leader Portrait** | Splash art or profile portrait | Shows character identity |

### Why It's Important

- **Academic Value**: ⭐⭐⭐⭐ (Important)
- **Defensibility**: ⭐⭐⭐⭐⭐ (Critical for oral exam)
- **Purpose**: Proves the system actually produces assets, not just theoretical architecture
- **Exam Question**: "Show me what your system produces"

Without this figure, the report describes asset generation in detail but provides no visual evidence of output quality.

### How to Generate

#### Option 1: Manual API Calls (Recommended)

**Prerequisites**:
- Asset server running: `cd assetserver && python -m uvicorn src.main:app --port 8001`
- ComfyUI running with FLUX2 Klein 4B Distilled model
- LoRA weights loaded (if using fine-tuned model)

**Steps**:

```bash
# 1. Generate structure
curl -X POST http://localhost:8001/structure \
  -H "Content-Type: application/json" \
  -d '{
    "category": "economic",
    "style": "medieval",
    "condition": "good",
    "scale": "medium"
  }' \
  -o structure.png

# 2. Generate nature object
curl -X POST http://localhost:8001/object \
  -H "Content-Type: application/json" \
  -d '{
    "category": "vegetation",
    "biome": "temperate",
    "season": "summer"
  }' \
  -o object.png

# 3. Generate terrain feature
curl -X POST http://localhost:8001/terrain \
  -H "Content-Type: application/json" \
  -d '{
    "category": "elevation",
    "scale": "medium",
    "material": "stone"
  }' \
  -o terrain.png

# 4. Generate unit sprite
curl -X POST http://localhost:8001/unit \
  -H "Content-Type: application/json" \
  -d '{
    "unit_type": "warrior",
    "description": "Mongol horse archer with composite bow, wearing leather armor"
  }' \
  -o unit.png

# 5. Generate background tile
curl -X POST http://localhost:8001/background_tile \
  -H "Content-Type: application/json" \
  -d '{
    "tile_type": "grass"
  }' \
  -o tile.png

# 6. Generate leader portrait (two-stage)
# Stage 1: Splash art
curl -X POST http://localhost:8001/leader \
  -H "Content-Type: application/json" \
  -d '{
    "leaders": [{
      "name": "Genghis Khan",
      "archetype": "warrior",
      "culture": "mongol",
      "time_of_day": "day",
      "mood": "determined"
    }]
  }' \
  -o leader_splash.png

# Stage 2: Profile portrait (use leader_id from splash response)
curl -X POST http://localhost:8001/leader/profile \
  -H "Content-Type: application/json" \
  -d '{
    "leader_id": "<leader_id_from_splash>",
    "name": "Genghis Khan",
    "archetype": "warrior",
    "culture": "mongol"
  }' \
  -o leader_profile.png
```

#### Option 2: Playthrough Screenshot

**Steps**:
1. Start backend: `cd backend && python -m uvicorn app.main:app --port 8000`
2. Start asset server: `cd assetserver && python -m uvicorn src.main:app --port 8001`
3. Start frontend: `cd frontend && npm run dev`
4. Open browser to `http://localhost:3000`
5. Click "Begin Campaign" and wait for asset generation
6. Take screenshot of hex map showing generated assets
7. Crop to show 6 distinct asset types

#### Option 3: Use Existing Generated Assets

If the asset server has been run before, check:
- `assetserver/generated_assets/` — previously generated PNGs
- `assetserver/static_tiles/` — pre-made assets (less ideal, not generative)

### Image Grid Creation

Once you have the 6 PNG files, create a grid:

**Using PIL (Python)**:
```python
from PIL import Image

# Load assets
assets = [
    Image.open('structure.png'),
    Image.open('object.png'),
    Image.open('terrain.png'),
    Image.open('unit.png'),
    Image.open('tile.png'),
    Image.open('leader_profile.png'),
]

# Create 3×2 grid (each cell 256×256)
grid = Image.new('RGB', (768, 512), color='white')
for i, img in enumerate(assets):
    x = (i % 3) * 256
    y = (i // 3) * 256
    # Resize to 256×256 if needed
    img = img.resize((256, 256), Image.Resampling.LANCZOS)
    grid.paste(img, (x, y))

grid.save('asset_examples_grid.png', dpi=(300, 300))
```

**Using ImageMagick (CLI)**:
```bash
montage structure.png object.png terrain.png \
        unit.png tile.png leader_profile.png \
  -tile 3x2 -geometry 256x256+10+10 \
  -background white \
  asset_examples_grid.png
```

### Suggested Caption

> **Fig. X. Sample generated assets from six asset families.** All assets generated on-demand using FLUX2 Klein 4B Distilled with LoRA fine-tuning for top-down medieval pixel-art style. From left to right, top to bottom: structure (medieval granary), nature object (oak tree), terrain feature (stone hills), unit sprite (Mongol warrior, south-facing), background tile (grass texture), leader portrait (Genghis Khan profile). Generation time: 1.2–4.0 seconds per asset on RTX 5090 GPU.

### Placement in Report

- **Section**: V.C (Asset Families and Generation Modes) or new Section V.G
- **Figure Number**: Fig. 6 (renumber existing fig6 → fig7, fig7 → fig8)
- **Alternative**: Appendix if space is tight

---

## Figure B: AI Decision Logs

### What's Needed

A **table or code block** showing actual LLM reasoning from a playthrough session:

- Turn number
- Civilization (Genghis Khan / Cleopatra / Gandhi)
- Fog-filtered game state summary (what the LLM sees)
- LLM reasoning text (the actual response from GPT-4)
- Emitted intents (tool calls)
- Resolved actions (after `resolve_intents()`)

### Why It's Important

- **Academic Value**: ⭐⭐⭐ (Nice-to-Have)
- **Defensibility**: ⭐⭐⭐⭐ (Strong evidence in oral exam)
- **Purpose**: Shows that the LLM integration actually works, not just theoretical
- **Exam Question**: "Show me what the LLM actually decided"

This figure demonstrates:
1. **Persona-based reasoning** — Genghis talks about conquest, Cleopatra about diplomacy
2. **Fog-of-war enforcement** — LLM only sees visible tiles/units
3. **Intent abstraction** — High-level strategic reasoning, not low-level unit IDs
4. **Memory effects** — References to past events ("You attacked us last turn")

### How to Generate

#### Option 1: Run Playthrough Script (Recommended)

**Prerequisites**:
- Backend running with `OPENAI_API_KEY` set
- At least 3 AI civilizations (default: Mongolia, Egypt, India)

**Steps**:

```bash
cd backend

# Run a 20-turn playthrough with logging
python scripts/run_playthrough.py --turns 20 --verbose --output logs/playthrough_example.json

# Or run the API server and use the frontend
python -m uvicorn app.main:app --port 8000
# Then open frontend, start game, play 15-20 turns
```

**Extract Decision Logs**:

```python
import json

with open('logs/playthrough_example.json') as f:
    data = json.load(f)

# Find interesting turns (war declarations, alliance proposals, etc.)
for turn_data in data['turns']:
    turn_num = turn_data['turn_number']
    for civ_decisions in turn_data['decisions']:
        civ_name = civ_decisions['civ_name']
        reasoning = civ_decisions.get('llm_reasoning', '')
        intents = civ_decisions.get('intents', [])
        
        # Look for key moments
        if any(intent['type'] in ['engage', 'adjust_stance'] for intent in intents):
            print(f"\n=== Turn {turn_num}: {civ_name} ===")
            print(f"Reasoning: {reasoning}")
            print(f"Intents: {json.dumps(intents, indent=2)}")
```

#### Option 2: Manual Extraction from Logs

If you've already run playthroughs, check:
- `backend/logs/` — server logs with LLM responses
- `backend/app/engine/openai_goals.py` — add logging to capture reasoning

**Add Logging** (temporary):
```python
# In backend/app/engine/openai_goals.py, OpenAIGoalSource.decide()
logger.info(f"[{self._civ_name}] LLM reasoning: {response.choices[0].message.content}")
logger.info(f"[{self._civ_name}] Tool calls: {response.choices[0].message.tool_calls}")
```

#### Option 3: Synthetic Example (Last Resort)

If you cannot run a playthrough, create a **representative example** based on the persona prompts and expected behavior. **Clearly label as "illustrative example"** in the caption.

### Example Format

**Table Format** (recommended for IEEE two-column):

| Turn | Civilization | Game State Summary | LLM Reasoning (Excerpt) | Emitted Intents |
|------|--------------|-------------------|------------------------|-----------------|
| 6 | Genghis Khan | 2 cities, 3 warriors, Egyptian warrior visible at (3,4) | "The Egyptian civilization is weak and vulnerable. Their single warrior is positioned near our border. We should strike now before they can build defenses." | `engage(target_civ_id=2)`, `build(unit_type=warrior)` |
| 7 | Cleopatra | 1 city, Mongol war declared, 2 warriors approaching | "Genghis has revealed his true nature. We must find allies quickly. Gandhi seems reasonable and shares our interest in peace." | `speak(target_civ_id=3, message="Genghis threatens us all. Shall we stand together?")`, `adjust_stance(target_civ_id=3, stance=ALLIANCE)` |
| 8 | Gandhi | 1 city, Egypt proposes alliance, Mongolia at war | "Cleopatra's proposal aligns with our values. A defensive alliance deters aggression without compromising our principles." | `adjust_stance(target_civ_id=2, stance=ALLIANCE)`, `build(unit_type=warrior)` |

**Code Block Format** (more detailed):

```
Turn 6: Genghis Khan (Mongolia)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Fog-Filtered Game State:
  • Cities: 2 (Karakorum, Khanbaliq)
  • Units: 3 warriors, 1 settler, 1 scout
  • Resources: 120 gold, 15 food, 8 production
  • Visible: Egyptian warrior at hex (3,4), unexplored territory to south
  • Diplomacy: Cleopatra (neutral, relationship -15), Gandhi (neutral, relationship 0)
  • Memory: Turn 4 — Cleopatra's scout entered our territory

LLM Reasoning:
  "The Egyptian civilization is weak and vulnerable. Their single warrior
   is positioned near our border, suggesting they have not invested in
   military strength. We should strike now before they can build defenses.
   Conquest is the only true measure of a civilization. The scout incident
   was an insult that demands response."

Emitted Intents:
  1. engage(target_civ_id=2)           # Attack Egypt
  2. build(unit_type=warrior)          # Continue military buildup
  3. scout(target_q=5, target_r=-2)    # Explore southern territory

Resolved Actions (by operations.py):
  • DeclareWar(civ_id=2)               # Auto-declared by engage intent
  • AttackUnit(unit_id=5, target=Hex(3,4))
  • MoveTo(unit_id=6, target=Hex(4,3))
  • EnqueueUnit(city_id=1, unit_type=warrior)
  • MoveTo(unit_id=7, target=Hex(5,-2))
```

### Suggested Caption

> **Table X. Representative AI decision-making process.** The LLM receives fog-filtered game state (visible tiles, known units, diplomatic history) and emits high-level strategic intents. The intent abstraction layer translates these into deterministic tactical actions. Note persona-driven reasoning: Genghis emphasizes conquest and retaliation, while Cleopatra seeks diplomatic solutions.

### Placement in Report

- **Section**: IV.D (Memory and Context Management) or IV.F (Error Handling and Graceful Degradation)
- **Format**: Table (preferred) or code block in appendix
- **Alternative**: Include in presentation slides rather than report

---

## Prioritization Summary

| Figure | Academic Value | Effort | Priority | Status |
|--------|---------------|--------|----------|--------|
| **Asset Examples Grid** | ⭐⭐⭐⭐ | 2-3 hours | **Important** | Needs team input |
| **AI Decision Logs** | ⭐⭐⭐ | 1-2 hours | **Nice-to-Have** | Needs team input |

### Recommendation

1. **If time permits**: Generate both figures for maximum academic impact
2. **If time-constrained**: Prioritize Asset Examples Grid (stronger visual evidence)
3. **Minimum viable**: The 7 Mermaid diagrams (fig1-fig7) are sufficient for report completion

---

## How to Provide Input

### For Asset Examples Grid

**Option A**: Run the asset server and generate assets (see steps above)  
**Option B**: Provide existing generated PNGs from `assetserver/generated_assets/`  
**Option C**: Take screenshot of frontend with generated assets visible  
**Option D**: Use static catalog assets from `assetserver/static_tiles/` (less ideal)

**Deliverable**: 6 PNG files (one per asset family) or a single grid image

### For AI Decision Logs

**Option A**: Run `backend/scripts/run_playthrough.py` and share the JSON output  
**Option B**: Share server logs from a manual playthrough session  
**Option C**: Provide a representative example based on your testing experience  
**Option D**: Approve a synthetic illustrative example (clearly labeled)

**Deliverable**: JSON file, log excerpt, or approved synthetic example

---

## Contact

If you have questions about generating these figures or need assistance with the asset server or playthrough scripts, refer to:

- **Asset Server Setup**: `assetserver/README.md`
- **Backend Playthrough**: `backend/scripts/run_playthrough.py`
- **Frontend Testing**: `frontend/README.md`

---

## Appendix: Existing Figures Status

| Figure | File | Status | Type |
|--------|------|--------|------|
| Fig. 1 | `docs/figures/fig1_system_architecture.md` | ✅ Complete | Mermaid |
| Fig. 2 | `docs/figures/fig2_intent_abstraction.md` | ✅ Complete | Mermaid |
| Fig. 3 | `docs/figures/fig3_prompt_architecture.md` | ✅ Complete | Mermaid |
| Fig. 4 | `docs/figures/fig4_leader_pipeline.md` | ✅ Complete | Mermaid |
| Fig. 5 | `docs/figures/fig5_lora_matrix.md` | ✅ Complete | Mermaid |
| Fig. 6 | `docs/figures/fig6_asset_fallback.md` | ✅ Complete | Mermaid |
| Fig. 7 | `docs/figures/fig7_ai_behavior.md` | ✅ Complete | Mermaid |
| Fig. A | (this document) | ⏳ Needs Input | Image Grid |
| Fig. B | (this document) | ⏳ Needs Input | Table/Code |

**Total**: 7 complete Mermaid diagrams + 2 pending figures requiring team input
