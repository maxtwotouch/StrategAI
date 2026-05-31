# Figure Descriptions for IEEE Report

This document provides detailed descriptions of all figures needed for the StrategAI IEEE report. Each description includes the caption, visual elements, and purpose.

---

## Fig. 1. System Architecture Overview

**Caption**: System architecture showing four primary components and data flow between backend game engine, frontend UI, asset generation server, and LoRA training pipeline.

**Visual Elements**:
- Four large boxes arranged in a diamond pattern:
  - **Backend** (top): Python/FastAPI, Game Engine, LLM Integration
  - **Frontend** (left): Next.js, React, SVG Rendering
  - **Asset Server** (right): FastAPI, ComfyUI, FLUX.2 Klein 4B Distilled
  - **Training Pipeline** (bottom): Ostris AI Toolkit, LoRA Fine-Tuning
- Bidirectional arrows showing data flow:
  - Frontend ↔ Backend: REST API (game state, user actions)
  - Frontend → Asset Server: HTTP requests (asset generation)
  - Asset Server → Frontend: PNG images (generated assets)
  - Training Pipeline → Asset Server: LoRA weights (model adaptation)
- Technology stack labels on each box
- Color coding: Blue (backend), Green (frontend), Orange (asset server), Purple (training)

**Purpose**: Provides high-level overview of system components and their interactions, establishing the multi-service architecture context.

---

## Fig. 2. Intent-Based LLM Abstraction Layer

**Caption**: Two-layer architecture separating strategic LLM reasoning from deterministic tactical execution through intent-based abstraction.

**Visual Elements**:
- **Top layer** (Strategic - LLM):
  - Box labeled "GPT-4" with "System Prompt + Game State + Memory"
  - Arrow down labeled "Emits Intents"
  - List of 9 intent types: expand, scout, engage, reinforce, speak, adjust_stance, build, research, improve
- **Middle layer** (Intent Resolution):
  - Box labeled "resolve_intents()"
  - Shows transformation: Intent → Goal/Directive
  - Example: `Engage(target_civ_id=2)` → `DeclareWar(civ_id=2)` + `MoveTo(unit_id=5, target=Hex(3,4))`
- **Bottom layer** (Tactical - Deterministic):
  - Box labeled "Game Engine"
  - Sub-boxes: Pathfinding (A*), Combat Resolution, Rule Validation
  - Arrow down labeled "Executes Actions"
  - Final state: "Updated GameState"
- Side annotations:
  - "LLM never touches GameState directly"
  - "All actions validated before execution"
  - "Deterministic, reproducible outcomes"

**Purpose**: Demonstrates the novel contribution of separating strategic reasoning from tactical execution, enabling LLMs to control game entities without direct state manipulation.

---

## Fig. 3. Four-Layer Prompt Architecture

**Caption**: Systematic prompt construction through four layers separating workflow configuration, style templates, semantic descriptions, and assembly logic.

**Visual Elements**:
- Vertical stack of four layers (bottom to top):
  - **Layer 1** (bottom, gray): "Workflow Configuration"
    - Icon: ComfyUI node graph
    - Content: Model selection, sampler (euler), steps (4), resolution (1024×1024→256×256), guidance (3.5)
    - File: `workflows/txt2img.json`
  - **Layer 2** (blue): "Style Templates"
    - Icon: JSON document
    - Content: Camera framing ("top-down view."), quality tags ("Pixel art 16x16"), LoRA triggers ("<tdp>")
    - File: `config/prompt_templates.json`
  - **Layer 3** (green): "Semantic Descriptions"
    - Icon: Python code
    - Content: Enum vocabularies (19 classes, 88 values), hand-crafted prose (20-40 words each)
    - Example: `fortification` → "sturdy defensive structure with crenellated battlements..."
    - File: `src/*/prompts.py`
  - **Layer 4** (top, orange): "Assembly Logic"
    - Icon: Gear/cog
    - Content: Template rendering, placeholder substitution, validation
    - File: `src/*/prompts.py`
- Arrows showing data flow upward
- Right side: Example output showing final assembled prompt
- Left side: Annotations explaining separation of concerns

**Purpose**: Demonstrates systematic approach to achieving consistent asset generation across diverse asset types through modular prompt construction.

---

## Fig. 4. Three-Stage Leader Portrait Pipeline

**Caption**: Identity-preserving leader portrait generation through three stages with calibrated denoising parameters.

**Visual Elements**:
- Horizontal flow with three stages:
  - **Stage 1: Splash Art** (left)
    - Box: "txt2img"
    - Parameters: 1920×1088, guidance=3.5, denoise=1.0
    - Sample image: Cinematic wide shot of leader (e.g., Genghis Khan on horseback)
    - Annotation: "Establishes canonical identity"
    - Arrow right with label "Seed stored"
  - **Stage 2: Profile Portrait** (center)
    - Box: "img2img from splash"
    - Parameters: 512×512, guidance=8.0, denoise=0.90
    - Sample image: Close-up portrait of same leader (same face, different framing)
    - Annotation: "Maximum identity preservation"
    - Arrow from Stage 1 image (dashed line showing reference)
  - **Stage 3: Action Scene** (right)
    - Box: "img2img from splash"
    - Parameters: 1920×1088, guidance=4.5, denoise=0.85
    - Sample image: Leader in action pose (same character, dynamic scene)
    - Annotation: "Creative freedom with consistency"
    - Arrow from Stage 1 image (dashed line showing reference)
- Bottom: Denoise scale showing trade-off
  - 0.80: "Too constrained"
  - 0.85-0.90: "Sweet spot"
  - 0.95+: "Identity loss"

**Purpose**: Demonstrates identity preservation technique through carefully calibrated denoising parameters, enabling consistent character rendering across diverse compositions.

---

## Fig. 5. LoRA Fine-Tuning Experiment Matrix

**Caption**: Six-experiment matrix evaluating interaction between caption detail level and LoRA rank on model generalization.

**Visual Elements**:
- 3×2 grid matrix:
  - **Rows** (caption detail):
    - Detailed (50-100 words): "A medieval granary built from weathered oak planks with a thatched roof, elevated on stone pillars..."
    - Minimal (20-30 words): "Medieval wooden granary with thatched roof on stone pillars, pixel art style"
    - Ultra-minimal (5-10 words): "Medieval granary, pixel art"
  - **Columns** (LoRA rank):
    - High (linear=128, conv=64): Higher capacity, risk of overfitting
    - Low (linear=64, conv=32): Lower capacity, better generalization
- Each cell contains:
  - Experiment name (e.g., "detailed_high")
  - Training parameters (steps=2500, lr=8e-5)
  - Sample output thumbnail (4 in-distribution + 4 out-of-distribution)
- Color coding:
  - Green: Best generalization (ultra-minimal + low rank)
  - Yellow: Balanced performance (minimal + high rank)
  - Red: Overfitting risk (detailed + high rank)
- Bottom: Key finding annotation
  - "Less detailed captions force abstract concept learning, improving generalization to unseen asset types"

**Purpose**: Demonstrates systematic evaluation of fine-tuning parameters and key insight about caption design for model adaptation.

---

## Fig. 6. Asset Generation Modes and Fallback Strategy

**Caption**: Four-level graceful degradation ensuring system functionality across diverse deployment scenarios.

**Visual Elements**:
- Vertical stack of four levels (top to bottom):
  - **Level 1** (top, green): "Generative Assets"
    - Icon: GPU + sparkle
    - Description: "On-demand AI generation using FLUX.2 Klein 4B Distilled"
    - Quality: "High-quality, context-specific"
    - Requirements: "GPU (8+ GB VRAM), ComfyUI"
    - Sample: High-quality pixel art structure
  - **Level 2** (blue): "Static Assets"
    - Icon: Folder
    - Description: "Pre-generated assets from filesystem"
    - Quality: "Lower diversity, consistent quality"
    - Requirements: "Filesystem only"
    - Sample: Pre-made pixel art structure
  - **Level 3** (yellow): "Placeholder Assets"
    - Icon: Rectangle with text
    - Description: "PIL-generated colored rectangles with labels"
    - Quality: "Functional, aesthetically limited"
    - Requirements: "Pillow library only"
    - Sample: Colored rectangle with "BARRACKS" text
  - **Level 4** (bottom, red): "Built-in Fallbacks"
    - Icon: Hexagon
    - Description: "Color-coded hexagons and glyphs"
    - Quality: "Minimal, fully playable"
    - Requirements: "None"
    - Sample: Simple colored hexagon with icon
- Right side: Arrow labeled "Degradation path" pointing downward
- Left side: Annotations showing when each level activates
  - Level 1: "Normal operation"
  - Level 2: "Asset server unavailable"
  - Level 3: "GPU unavailable"
  - Level 4: "Complete failure"

**Purpose**: Demonstrates robust error handling ensuring game remains playable regardless of AI service availability.

---

## Fig. 7. Game State Serialization and Fog of War

**Caption**: Local view serialization applying fog-of-war filtering to prevent AI cheating through information asymmetry.

**Visual Elements**:
- **Left side**: Full GameState (omniscient view)
  - Hex grid showing entire map
  - All units visible (including enemy units)
  - All cities visible
  - All resources visible
  - Label: "Complete game state (not visible to AI)"
- **Center**: Serialization process
  - Box: "local_view(state, civ_id)"
  - Arrows showing filtering:
    - "Apply visibility mask"
    - "Filter enemy units outside range"
    - "Hide unexplored tiles"
    - "Remove future information"
- **Right side**: Local view (AI perspective)
  - Same hex grid but with fog of war
  - Only friendly units visible
  - Enemy units only if in visibility range
  - Unexplored tiles shown as dark/foggy
  - Label: "Serialized view for AI civilization"
- Bottom: Code snippet showing key function
  ```python
  def local_view(state: GameState, civ_id: int) -> dict:
      visible = state.visibility.get(civ_id, frozenset())
      # Filter units, tiles, cities by visibility
      # Apply fog of war
      # Return serialized dict for LLM
  ```

**Purpose**: Demonstrates fair play enforcement through information asymmetry, preventing AI from accessing information unavailable to human players.

---

## Fig. 8. ComfyUI Workflow Node Graph

**Caption**: ComfyUI workflow for txt2img generation showing 22-node pipeline from prompt input to final asset output.

**Visual Elements**:
- Node graph with 22 nodes connected by arrows:
  - **Input nodes** (left):
    - Node 5: PrimitiveStringMultiline (prompt injection point)
    - Node 15: RandomNoise (seed injection point)
    - Node 24, 25: PrimitiveInt (width=1024, height=1024)
  - **Model loading** (center-left):
    - Node 1: UNETLoader (flux-2-klein-4b-fp8.safetensors)
    - Node 3: CLIPLoader (qwen_3_4b.safetensors)
    - Node 11: VAELoader (flux2-vae.safetensors)
    - Node 12: LoraLoaderModelOnly (<tdp> LoRA, strength=1.0)
  - **Conditioning** (center):
    - Node 4: CLIPTextEncode (prompt → conditioning)
    - Node 7: FluxGuidance (guidance=3.5)
    - Node 17: ConditioningZeroOut (negative conditioning)
    - Node 18: CFGGuider (cfg=1.0)
  - **Sampling** (center-right):
    - Node 23: EmptyLatentImage (1024×1024)
    - Node 62: BasicScheduler (simple, 4 steps)
    - Node 8: KSamplerSelect (euler)
    - Node 10: SamplerCustomAdvanced (orchestrates denoising)
  - **Post-processing** (right):
    - Node 16: VAEDecode (latent → image)
    - Node 27: ImageResizeKJv2 (1024→256, Lanczos)
    - Node 47: ImageSharpen (radius=1, alpha=0.1)
    - Node 32: Image Remove Background (rembg, ISNet)
    - Node 43: SaveImage (final 256×256 RGBA)
- Color coding by function:
  - Blue: Model loading
  - Green: Conditioning
  - Orange: Sampling
  - Purple: Post-processing
- Annotations highlighting injection points and key parameters

**Purpose**: Demonstrates technical implementation of diffusion model orchestration through ComfyUI's node-graph workflow system.

---

## Fig. 9. Diplomatic Relationship System

**Caption**: Diplomatic relationship scoring system with message types, stance changes, and truce mechanics.

**Visual Elements**:
- **Top**: Relationship score scale
  - Horizontal bar from -100 (hostile) to +100 (allied)
  - Color gradient: Red (-100) → Yellow (0) → Green (+100)
  - Markers showing thresholds:
    - -50: "Declare war"
    - -20: "Attack"
    - 0: "Neutral"
    - +25: "Accept peace"
    - +50: "Propose alliance"
- **Middle**: Message types and relationship deltas
  - Table with columns: Message Type | Relationship Delta | Example
  - Rows:
    - DECLARE_WAR | -50 | "Your expansion threatens our borders"
    - ATTACK | -20 | (automatic on combat)
    - THREAT | -10 | "Withdraw your troops or face consequences"
    - REJECT | -5 | "We decline your offer"
    - CHAT | +1 | "Greetings, fellow leader"
    - OFFER_PEACE | +8 | "Let us end this conflict"
    - ACCEPT_PEACE | +25 | "We accept your peace offering"
    - PROPOSE_ALLIANCE | +15 | "Together we could achieve great things"
    - ACCEPT_ALLIANCE | +30 | "We gladly join forces with you"
- **Bottom**: Stance and truce mechanics
  - Three stance boxes: PEACE (green), WAR (red), ALLIANCE (blue)
  - Arrows showing transitions:
    - PEACE → WAR: "Declare war" (requires relationship ≤ -30)
    - WAR → PEACE: "Accept peace" (sets 10-turn truce)
    - PEACE → ALLIANCE: "Accept alliance" (requires relationship ≥ +50)
  - Truce box: "10-turn truce after peace"
    - Annotation: "Blocks hostile escalation during truce"

**Purpose**: Demonstrates diplomatic interaction system enabling emergent AI behavior through relationship-based mechanics.

---

## Fig. 10. Test Coverage and Quality Metrics

**Caption**: Comprehensive test suite across all components with 886 tests achieving ~80% aggregate coverage.

**Visual Elements**:
- **Bar chart** showing test counts by component:
  - Backend: 315 tests (blue bar)
  - Asset Server: 547 tests (orange bar)
  - Frontend: 35 tests (green bar)
  - Training Pipeline: 35 tests (purple bar)
  - Total: 886 tests (black line)
- **Line chart** overlay showing coverage percentages:
  - Backend: 85% (blue line)
  - Asset Server: 82% (orange line)
  - Frontend: 70% (green line)
  - Training Pipeline: 90% (purple line)
  - Average: 80% (black dashed line)
- **Table** below chart:
  | Component | Tests | Coverage | Test Types |
  |-----------|-------|----------|------------|
  | Backend | 315 | 85% | Unit, Integration, Property |
  | Asset Server | 547 | 82% | Unit, Integration, Concurrency |
  | Frontend | 35 | 70% | Type checking, Component |
  | Training | 35 | 90% | Unit, Integration |
- **Annotations**:
  - "Property tests validate invariants (immutability, rule compliance)"
  - "Concurrency tests verify load balancer and cache behavior"
  - "Type checking ensures API contract consistency"

**Purpose**: Demonstrates engineering rigor through comprehensive testing across all system components.

---

## Fig. 11. AI Civilization Behavior Patterns

**Caption**: Emergent strategic behavior exhibited by three AI civilizations with distinct personas.

**Visual Elements**:
- **Three panels** (one per civilization):
  - **Panel 1: Genghis Khan (Mongolia)**
    - Timeline showing aggressive expansion
    - Turn 1-5: Found 2 cities, build warriors
    - Turn 6-10: Declare war on nearest civ, attack cities
    - Turn 11-15: Continue expansion, maintain military pressure
    - Key behaviors: "Aggressive expansion", "Early military", "Frequent warfare"
    - Quote: "Conquest is the only true measure of a civilization"
  - **Panel 2: Cleopatra (Egypt)**
    - Timeline showing diplomatic engagement
    - Turn 1-5: Found 1 city, build settlers and workers
    - Turn 6-10: Propose alliances, trade messages
    - Turn 11-15: Form coalition, economic focus
    - Key behaviors: "Diplomatic manipulation", "Alliance formation", "Economic growth"
    - Quote: "Survive and prosper through clever diplomacy"
  - **Panel 3: Gandhi (India)**
    - Timeline showing peaceful development
    - Turn 1-5: Found 1 city, build library and monument
    - Turn 6-10: Research technologies, improve tiles
    - Turn 11-15: Defensive positioning, cultural victory path
    - Key behaviors: "Peaceful development", "Technology focus", "Defensive posture"
    - Quote: "Pursue victory through science, culture, and patient growth"
- **Bottom**: Emergent interactions
  - Example 1: "Genghis attacks Cleopatra → Cleopatra proposes alliance with Gandhi → Gandhi accepts → Coalition defeats Genghis"
  - Example 2: "Gandhi sends peace offer to Genghis → Genghis rejects and threatens → Gandhi builds defensive units"

**Purpose**: Demonstrates diverse AI behavior emerging from persona-based prompting and intent-based decision making.

---

## Fig. 12. Asset Generation Performance

**Caption**: Asset generation performance metrics showing inference time, cache hit rate, and API response time.

**Visual Elements**:
- **Line chart** (top): Inference time by asset type
  - X-axis: Asset type (structure, object, terrain, unit, background, leader-splash, leader-profile, leader-action)
  - Y-axis: Time (seconds)
  - Line showing: 1.2s (structure) → 1.3s (object) → 1.2s (terrain) → 1.4s (unit) → 1.5s (background) → 2.8s (leader-splash) → 3.2s (leader-profile) → 4.0s (leader-action)
  - Annotation: "RTX 5090 GPU, 4-step distilled inference"
- **Bar chart** (middle): Cache hit rate
  - X-axis: Gameplay scenario (early game, mid game, late game, repeated terrain)
  - Y-axis: Cache hit rate (%)
  - Bars: 60% (early) → 75% (mid) → 85% (late) → 95% (repeated)
  - Annotation: "Average 80% cache hit rate reduces generation load"
- **Table** (bottom): API response times
  | Endpoint | Cached | Generation | Total |
  |----------|--------|------------|-------|
  | GET /structure/{id} | <50ms | N/A | <50ms |
  | POST /structure | N/A | 1.2s | 1.3s |
  | POST /leader | N/A | 2.8-4.0s | 3.0-4.2s |
  | GET /health | <10ms | N/A | <10ms |
- **Annotations**:
  - "Synchronous generation holds HTTP connection open"
  - "Future work: Async job queue for non-blocking generation"

**Purpose**: Demonstrates real-time performance enabling near-interactive asset generation on consumer hardware.

---

## Usage Instructions

When creating the actual figures:

1. **Use consistent style**: Same color scheme, font sizes, and layout across all figures
2. **High resolution**: Minimum 300 DPI for print quality
3. **Readable text**: Minimum 10pt font for labels, 12pt for annotations
4. **Clear legends**: Include legends for all charts and graphs
5. **Proper sizing**: Figures should fit IEEE two-column format (3.5" single column, 7" double column)

Recommended tools:
- **Diagrams**: draw.io, Lucidchart, or TikZ (LaTeX)
- **Charts**: matplotlib, seaborn, or Excel
- **Screenshots**: Game UI with annotations
- **Node graphs**: ComfyUI screenshot with overlays

Each figure should be referenced in the text (e.g., "As shown in Fig. 3...") and placed near its first mention.
