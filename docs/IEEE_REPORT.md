# StrategAI: Integrating Large Language Models and Diffusion Transformers for AI-Driven Strategy Game Development

**Abstract**—This paper presents StrategAI, a full-stack strategy game that demonstrates practical integration of multiple generative AI technologies in a cohesive software system. The project combines Large Language Models (LLMs) for autonomous civilization management with Diffusion Transformers (DiTs) for on-demand asset generation, unified through a modern web architecture. Three AI civilizations, each controlled by GPT-4 via OpenAI's tool-use API, make strategic decisions through a novel intent-based abstraction layer that translates high-level goals into deterministic game actions. Concurrently, a self-hosted asset pipeline leverages FLUX.2 Klein 4B—a 4-billion parameter DiT model—to generate medieval pixel-art assets through a four-layer prompt architecture and three-stage leader portrait pipeline with identity preservation. A LoRA fine-tuning pipeline adapts the base model to a consistent top-down perspective using a curated 100-image dataset. The system demonstrates that consumer-grade GPUs (8-12 GB VRAM) can support both real-time LLM-driven gameplay and near-interactive asset generation (1.2-4 seconds per image), making advanced generative AI accessible for independent game development. We detail the architectural decisions, integration patterns, and engineering challenges encountered in building this multi-agent system, providing a reference implementation for future projects combining language models with visual generation.

**Index Terms**—Large Language Models, Diffusion Transformers, Game AI, Asset Generation, LoRA Fine-Tuning, Tool Use, Multi-Agent Systems

---

## I. INTRODUCTION

The rapid advancement of generative AI has opened new possibilities for interactive entertainment, yet practical implementations combining multiple AI modalities remain rare. Most game AI systems rely on behavior trees, finite state machines, or scripted decision logic, while asset creation remains a manual, time-intensive process requiring specialized artistic skills. This separation limits the potential for truly dynamic, AI-driven game experiences.

StrategAI addresses this gap by integrating two complementary generative AI technologies into a single cohesive system: (1) Large Language Models for strategic decision-making and diplomatic interaction, and (2) Diffusion Transformers for procedural asset generation. The result is a Civilization-style strategy game where AI opponents exhibit emergent strategic behavior through natural language reasoning, while game assets—terrain, buildings, units, and leader portraits—are generated on-demand to match the evolving game state.

### A. Motivation

Independent game developers face two fundamental challenges when attempting to incorporate advanced AI:

**Computational constraints**: State-of-the-art models often require enterprise-grade hardware (24+ GB VRAM, multi-GPU clusters) that exceeds typical development budgets. Cloud-based APIs introduce latency, recurring costs, and dependency on external services.

**Integration complexity**: Combining multiple AI systems requires careful architectural design to manage data flow, error handling, and graceful degradation. Most existing frameworks address single modalities in isolation.

StrategAI demonstrates that these challenges can be overcome through thoughtful system design. By selecting appropriately-sized models (GPT-4 for reasoning, FLUX.2 Klein 4B for generation) and implementing robust fallback mechanisms, the system achieves real-time performance on consumer hardware while maintaining production-quality output.

### B. Contributions

This work makes the following contributions:

1. **Intent-based LLM integration**: A novel abstraction layer that translates high-level strategic intents (expand, engage, reinforce) into deterministic game actions, enabling LLMs to control game entities without direct state manipulation.

2. **Four-layer prompt architecture**: A systematic approach to asset generation that separates workflow configuration, style templates, semantic descriptions, and assembly logic, enabling consistent output across diverse asset types.

3. **Three-stage identity preservation pipeline**: A leader portrait generation system that maintains character consistency across splash art, profile images, and action scenes through carefully calibrated denoising parameters.

4. **LoRA fine-tuning methodology**: A complete pipeline for adapting diffusion models to specific visual styles, including dataset curation, caption design, and a six-experiment matrix evaluating caption detail and rank configurations.

5. **Graceful degradation patterns**: Comprehensive fallback strategies ensuring system functionality when AI services are unavailable, from random AI behavior to placeholder assets.

6. **Reference implementation**: A fully functional, open-source codebase demonstrating best practices for integrating multiple generative AI systems in a production application.

### C. Paper Organization

The remainder of this paper is organized as follows: Section II reviews related work in game AI and procedural content generation. Section III presents the overall system architecture. Sections IV, V, and VI detail the LLM integration, asset generation pipeline, and LoRA fine-tuning process, respectively. Section VII describes frontend integration and user experience. Section VIII evaluates system performance and test coverage. Section IX discusses limitations and future work. Section X concludes.

---

## II. RELATED WORK

### A. Game AI and Large Language Models

Traditional game AI relies on hand-crafted decision systems. Behavior trees [1] provide hierarchical task decomposition but require extensive manual authoring. Finite state machines [2] offer predictable transitions but struggle with complex, emergent scenarios. Utility-based systems [3] enable nuanced decision-making through weighted scoring but lack the flexibility to handle novel situations.

Recent work has explored LLMs for game AI. Park et al. [4] demonstrated "generative agents" that simulate human behavior through natural language reasoning, though their system operated in a sandbox environment without competitive gameplay. Zhu et al. [5] used GPT-4 to generate dialogue for non-player characters, but decision-making remained scripted. Volum et al. [6] proposed "CraftAssist" for Minecraft, using LLMs to interpret player commands, but the AI did not autonomously pursue goals.

StrategAI differs by employing LLMs as autonomous strategic agents in a competitive, rule-bound environment. Our intent-based abstraction addresses a key challenge: LLMs excel at high-level reasoning but struggle with precise numerical calculations and spatial logic. By separating strategic intent from tactical execution, we leverage LLM strengths while maintaining deterministic game mechanics.

### B. Procedural Content Generation

Procedural Content Generation (PCG) has a long history in games, from early roguelikes [7] to modern titles like No Man's Sky [8]. Traditional PCG uses algorithmic techniques: noise functions for terrain [9], grammar-based systems for structures [10], and constraint solvers for level design [11].

Deep learning has expanded PCG capabilities. Generative Adversarial Networks (GANs) have generated game levels [12] and textures [13], but training instability and mode collapse limit practical adoption. Variational Autoencoders (VAEs) offer more stable training [14] but often produce blurry outputs unsuitable for pixel art.

Diffusion models [15], [16] have emerged as the state-of-the-art for image generation, offering high-quality outputs with diverse variations. However, their application to game assets remains limited. Most existing work focuses on concept art generation [17] rather than production-ready assets with specific technical requirements (transparent backgrounds, consistent perspective, tileable textures).

StrategAI addresses these requirements through a multi-stage pipeline combining diffusion models with post-processing (background removal, palette quantization) and a structured prompt system that enforces asset specifications.

### C. Model Adaptation and Fine-Tuning

Full fine-tuning of large diffusion models is computationally prohibitive for most developers. Parameter-Efficient Fine-Tuning (PEFT) methods like LoRA [18] enable adaptation with minimal additional parameters (typically 0.1-1% of base model size).

Several works have applied LoRA to game asset generation. PixelArt-LoRA [19] adapts Stable Diffusion for pixel art but focuses on side-view sprites. TopDown-LoRA [20] targets overhead perspectives but lacks the medieval aesthetic required for strategy games.

Our approach differs in three ways: (1) we target FLUX.2 Klein 4B, a newer architecture with improved prompt adherence; (2) we systematically evaluate caption design through a six-experiment matrix; (3) we integrate the fine-tuned model into a production pipeline with automated asset generation.

### D. Multi-Agent Systems

Multi-agent systems (MAS) in games typically involve homogeneous agents with shared decision logic [21]. Heterogeneous MAS, where agents have different capabilities or goals, are more complex but enable richer interactions [22].

StrategAI implements heterogeneous agents through persona-based prompting. Each AI civilization receives a unique character description (Genghis Khan: aggressive expansionist; Cleopatra: diplomatic manipulator; Gandhi: peaceful developer) that influences decision-making while sharing the same underlying intent system. This approach enables diverse strategic behaviors without requiring separate AI implementations.

---

## III. SYSTEM ARCHITECTURE

StrategAI follows a microservices architecture with four primary components: a Python backend implementing the game engine and LLM integration, a Next.js frontend providing the user interface, a FastAPI asset server managing image generation, and a separate training pipeline for model adaptation (Fig. 1).

### A. Component Overview

**Backend** (Python 3.11+, FastAPI): Implements a pure functional game engine with immutable state, LLM-driven AI civilizations, and a RESTful API. The engine enforces deterministic game rules while the LLM layer provides strategic decision-making.

**Frontend** (Next.js 15, React 19, TypeScript): Renders the game state through an SVG-based hex map, manages user interactions, and coordinates asset loading from the asset server. Implements graceful fallback when generative assets are unavailable.

**Asset Server** (Python 3.10+, FastAPI, ComfyUI): Generates pixel-art assets on-demand using FLUX.2 Klein 4B. Provides 35 REST endpoints across six asset families (structures, objects, terrain, units, background tiles, leaders) with three generation modes (comfyui, static, placeholder).

**Training Pipeline** (Python 3.10+, Ostris AI Toolkit): Fine-tunes LoRA adapters for FLUX.2 Klein using a curated dataset of medieval pixel art. Produces model weights that enforce top-down perspective and pixel-art style.

### B. Data Flow

The system operates through three primary data flows:

**Gameplay loop**: User actions → Backend API → Game engine state update → LLM decision-making (AI turns) → State serialization → Frontend rendering

**Asset generation**: Frontend asset request → Asset server API → ComfyUI workflow execution → FLUX.2 Klein inference → Post-processing → Image storage → Frontend display

**Model training**: Dataset curation → Caption generation → LoRA training → Model evaluation → Weight deployment to asset server

### C. Technology Stack Rationale

**FLUX.2 Klein 4B** was selected over alternatives (Stable Diffusion XL, FLUX.2 Klein 9B) based on four criteria:

1. **License**: Apache 2.0 enables commercial use without restrictions
2. **VRAM requirement**: ~8.4 GB fits consumer GPUs (RTX 3070/4070)
3. **Inference speed**: 4-step distilled model achieves ~1.2s generation
4. **Architecture**: Diffusion Transformer with rectified flow formulation provides superior prompt adherence

**GPT-4** was selected for strategic AI based on:

1. **Tool-use capability**: Native function calling enables structured intent emission
2. **Reasoning quality**: Superior strategic planning compared to smaller models
3. **Context window**: 128K tokens accommodates game state and rolling memory
4. **API reliability**: Production-grade infrastructure with graceful error handling

**ComfyUI** serves as the inference orchestration layer, providing:

1. **Workflow abstraction**: Node-graph representation enables complex multi-stage pipelines
2. **Community ecosystem**: Custom nodes for background removal, palette quantization, image stitching
3. **HTTP/WebSocket API**: Enables programmatic control from FastAPI backend
4. **Model management**: Handles loading, quantization, and VRAM optimization

---

## IV. LLM-DRIVEN STRATEGIC AI

The backend implements three AI civilizations, each controlled by GPT-4 through OpenAI's tool-use API. The LLM never directly manipulates game state; instead, it emits high-level intents that the deterministic engine resolves into concrete actions.

### A. Intent-Based Abstraction

Direct LLM control of game entities presents several challenges:

- **Spatial reasoning**: LLMs struggle with coordinate calculations and pathfinding
- **Numerical precision**: Combat formulas and resource calculations require exact arithmetic
- **Rule compliance**: Game rules must be enforced deterministically to prevent invalid states

Our intent-based abstraction addresses these challenges through a two-layer architecture:

**Strategic layer** (LLM): Emits intents representing high-level goals (e.g., "expand to new territory," "engage enemy civilization," "research iron working")

**Tactical layer** (deterministic): Resolves intents into specific actions using game state, pathfinding algorithms, and rule validation

This separation enables the LLM to focus on strategic reasoning ("Should I expand or consolidate?") while the engine handles tactical execution ("Which settler should found the city, and where?").

### B. Intent System Design

The system defines nine intent types, each representing a strategic decision category:

1. **Expand**: Found a new city (engine selects settler and optimal location)
2. **Scout**: Explore unexplored territory (engine selects unit and frontier target)
3. **Engage**: Attack enemy civilization (engine selects military units and targets)
4. **Reinforce**: Strengthen defensive positions (engine moves units to cities)
5. **Speak**: Send diplomatic message (direct text emission with message type)
6. **AdjustStance**: Change diplomatic relationship (peace/war/alliance)
7. **Build**: Queue unit production (engine validates technology prerequisites)
8. **Research**: Select technology to research (engine validates availability)
9. **Improve**: Construct tile improvements (engine selects worker and target tile)

Each intent is implemented as a frozen dataclass with optional parameters. For example:

```python
@dataclass(frozen=True, slots=True)
class Engage:
    """Wage war on another civilization."""
    target_civ_id: int
```

The LLM emits intents through OpenAI's function-calling interface, which provides structured JSON output with type validation.

### C. System Prompt Architecture

The system prompt consists of two layers:

**Base prompt** (static): Defines the game context, available intents, and strategic principles:

- Role definition: "You are an AI civilization leader playing a turn-based strategy game"
- View description: Documents all fields in the serialized game state (resources, units, cities, diplomatic relations)
- Intent guide: Explains each intent's purpose and appropriate use cases
- Strategic principles: Expansion priorities, economic management, military positioning, diplomatic engagement
- Behavior rules: Avoid repetitive actions, respond to diplomatic messages, adapt to feedback

**Persona prompt** (per-civilization): Defines character-specific behavior patterns:

- **Genghis Khan**: "Conquest is the only true measure of a civilization. Found cities to fuel armies, then crush your neighbors. You remember every insult."
- **Cleopatra**: "Survive and prosper through clever diplomacy. Play factions against each other. Build a beautiful, wealthy civilization rather than a vast one."
- **Gandhi**: "Pursue victory through science, culture, and patient growth. Avoid aggression where possible. Respond to threats with dignified protest first."

The persona prompt is appended to the base prompt, enabling shared strategic knowledge with character-specific decision-making.

### D. Memory and Context Management

The LLM maintains a rolling memory of recent actions and diplomatic exchanges:

- **Intent log**: Last 32 intents with turn numbers and summaries
- **Message log**: Last 32 diplomatic messages with sender, recipient, and content
- **Turn window**: Memory filtered to last 8 turns to maintain recency

This memory is injected into the prompt as `recent_actions` and `recent_messages`, enabling the LLM to:

- Avoid repeating failed strategies
- Respond to diplomatic overtures
- Adapt to changing game conditions
- Maintain consistent strategic direction

### E. Intent Resolution

The `resolve_intents()` function translates LLM-emitted intents into concrete game actions through deterministic logic:

**Expand resolution**:
1. Find available settlers owned by the civilization
2. If target coordinates provided, validate location; otherwise, search for optimal city site
3. Emit `FoundCityNear` goal with settler ID and target coordinates

**Engage resolution**:
1. Check diplomatic stance; if not at war, emit `DeclareWar` action
2. Find military units owned by the civilization
3. Find visible enemy units or cities
4. Select closest attacker and target using hex distance
5. Emit `MoveTo` and `Attack` goals

**Build resolution**:
1. Validate technology prerequisites for requested unit type
2. Select city (provided or first available)
3. Emit `QueueProduction` directive

This resolution layer ensures that LLM decisions are always translated into valid game actions, preventing rule violations or impossible states.

### F. Error Handling and Graceful Degradation

The system implements comprehensive error handling:

- **API failures**: Catch exceptions, log warnings, return empty decisions (AI skips turn)
- **Invalid intents**: Catch parsing errors, skip malformed intents, continue processing valid ones
- **Missing state**: If game state not bound, return empty decisions
- **Temperature suppression**: For models that don't support temperature (GPT-5, o1), omit parameter

This ensures that AI civilizations remain functional even when the LLM service experiences issues.

---

## V. DIFFUSION TRANSFORMER ASSET PIPELINE

The asset server generates pixel-art assets on-demand using FLUX.2 Klein 4B, a 4-billion parameter Diffusion Transformer. The pipeline implements a four-layer prompt architecture and supports six asset families with diverse technical requirements.

### A. Model Architecture

FLUX.2 Klein 4B represents a shift from traditional U-Net diffusion models to transformer-based architectures:

**Diffusion Transformer (DiT)**: Replaces U-Net backbone with Vision Transformer operating on latent-space patches. Enables better scaling and improved prompt adherence.

**Rectified flow formulation**: Uses straight-line paths from noise to data distribution, enabling fewer inference steps (4 vs. 50 for traditional DDPM).

**Qwen 3 4B text encoder**: Replaces CLIP with a larger language model, providing superior understanding of complex prompts.

**FP8 quantization**: Reduces VRAM requirement from ~16 GB to ~8.4 GB with minimal quality loss.

The model requires four files totaling ~14.6 GB:
- `flux-2-klein-4b-fp8.safetensors` (6 GB): DiT transformer weights
- `qwen_3_4b.safetensors` (8 GB): Text encoder weights
- `flux2-vae.safetensors` (320 MB): Variational autoencoder
- `flux2_klein_4b_lora_000002400.safetensors` (250 MB): Top-down perspective LoRA

### B. Four-Layer Prompt Architecture

Consistent asset generation requires systematic prompt construction. We implement a four-layer architecture separating concerns:

**Layer 1: Workflow configuration** (ComfyUI JSON):
- Model selection: UNETLoader, CLIPLoader, VAELoader
- Sampler configuration: euler sampler, simple scheduler, 4 steps
- Resolution: 1024×1024 generation, 256×256 output
- Guidance: FluxGuidance (2.5-8.0 depending on asset type)
- Post-processing: Lanczos resize, image sharpening, background removal

**Layer 2: Style templates** (prompt_templates.json):
- Camera framing: "Front view overhead shot elevated shot medium shot"
- Quality tags: "Pixel art 16x16 game tile asset, crisp pixel edges, no anti-aliasing"
- LoRA triggers: "<tdp>" token for top-down perspective
- Format constraints: "Isolate on plain white background, centered single asset"

**Layer 3: Semantic descriptions** (prompts.py):
- Enum-based vocabularies: 19 enum classes with 88 prompt-injected values
- Hand-crafted prose: 20-40 word descriptions per enum value
- Example: `fortification` → "a sturdy defensive structure with crenellated battlements, arrow slits, thick stone walls, watchtower, military functionality"

**Layer 4: Assembly logic** (prompts.py):
- Template rendering: Substitute placeholders with enum prose
- Validation: Ensure all required fields provided
- Prompt construction: Combine style template + semantic description

This separation enables:
- **Consistency**: All assets follow the same style guidelines
- **Maintainability**: Style changes require editing only Layer 2
- **Extensibility**: New asset types require only Layer 3 additions
- **Testability**: Each layer can be validated independently

### C. Asset Families and Generation Modes

The system supports six asset families, each with specific technical requirements:

**Structures** (420 possible combinations):
- Dimensions: 4 categories × 7 styles × 5 conditions × 3 scales
- Output: 256×256 RGBA PNG with transparent background
- Guidance: 3.5 (standard prompt adherence)
- Post-processing: Background removal, sharpening

**Objects** (140 combinations):
- Dimensions: 5 categories × 7 biomes × 4 seasons
- Output: 256×256 RGBA PNG
- Guidance: 3.5
- Post-processing: Background removal, sharpening

**Terrain** (75 combinations):
- Dimensions: 5 categories × 3 scales × 5 materials
- Output: 256×256 RGBA PNG
- Guidance: 3.5
- Post-processing: Background removal, sharpening

**Units** (4 types):
- Types: archer, scout, settler, warrior
- Output: 256×256 RGBA PNG
- Guidance: 3.5
- Post-processing: Background removal, sharpening

**Background tiles** (5 types):
- Types: water, grass, sand, stone, dirt
- Output: 256×256 RGB PNG (no transparency)
- Guidance: 2.5 (lower for organic variation)
- Post-processing: None (seamless tiling required)

**Leaders** (multi-stage pipeline):
- Stages: splash (1920×1088), profile (512×512), action (1920×1088)
- Dimensions: 8 archetypes × 12 cultures × 6 times × 8 moods
- Guidance: 3.5 (splash), 8.0 (profile), 4.5 (action)
- Post-processing: None (cinematic quality preserved)

Each family supports three generation modes:

**comfyui**: Full AI generation using FLUX.2 Klein
**static**: Pre-generated assets from filesystem
**placeholder**: PIL-generated colored rectangles with text labels

Mode selection is configurable per-family, enabling graceful degradation when GPU resources are unavailable.

### D. Leader Portrait Pipeline

Leader portraits require identity preservation across multiple views. We implement a three-stage pipeline:

**Stage 1: Splash art** (txt2img):
- Resolution: 1920×1088 (16:9 cinematic aspect ratio)
- Guidance: 3.5 (balanced creativity and prompt adherence)
- Denoise: 1.0 (full generation from noise)
- Output: Establishes canonical character appearance
- Seed storage: Saved to database for reproducibility

**Stage 2: Profile portrait** (img2img from splash):
- Resolution: 512×512 (square format for UI display)
- Guidance: 8.0 (maximum prompt adherence for identity preservation)
- Denoise: 0.90 (minimal deviation from reference)
- Input: Splash art as reference image
- Output: Close-up portrait maintaining character identity

**Stage 3: Action scene** (img2img from splash):
- Resolution: 1920×1088 (cinematic format)
- Guidance: 4.5 (balanced creativity and consistency)
- Denoise: 0.85 (significant changes while preserving identity)
- Input: Splash art as reference image
- Output: Character in action pose or dramatic scene

The denoise parameter controls the balance between reference preservation and creative freedom:
- 0.85: Significant changes, same character (action scenes)
- 0.90: Minimal reference influence, major framing changes (profile portraits)
- 1.0: Complete regeneration (splash art)

Empirical testing revealed that denoise ≥0.95 causes identity loss, while denoise ≤0.80 prevents meaningful composition changes.

### E. ComfyUI Integration

ComfyUI serves as the inference orchestration layer, providing a node-graph workflow system with HTTP/WebSocket API integration.

**Workflow execution**:
1. Upload input images (img2img only)
2. Patch workflow JSON with prompt, seed, and reference images
3. Queue prompt and receive prompt_id
4. Monitor execution via WebSocket (fallback to HTTP polling)
5. Download output images
6. Clean up uploaded inputs

**Load balancing**:
- Multiple ComfyUI nodes supported
- Node selection: shortest queue with round-robin tie-breaking
- Health monitoring: Nodes marked unhealthy on connectivity failures
- Automatic failover: Retry on next-best node (max 3 attempts)

**Error handling**:
- Timeout: 300 seconds per generation
- Retry logic: 3 attempts with exponential backoff (1s, 2s, 4s)
- Fallback: Static or placeholder modes on persistent failures

### F. Post-Processing Pipeline

Generated images require post-processing to meet asset specifications:

**Resize**: Lanczos downscaling from 1024×1024 to 256×256 (4× reduction)
- Preserves edge definition for pixel art
- CPU-side processing to avoid GPU memory fragmentation

**Sharpening**: Subtle enhancement (radius=1, sigma=1, alpha=0.1)
- Prevents over-sharpening halos
- Maintains pixel-art aesthetic

**Background removal**: ISNet model for transparent backgrounds
- Required for structures, objects, terrain, units
- Omitted for background tiles (seamless tiling) and leaders (cinematic quality)

**Storage**: Atomic writes with LRU caching
- Temporary file creation followed by os.rename
- 1000-entry cache with 500 MB limit
- SQLite database for metadata persistence

---

## VI. LORA FINE-TUNING FOR STYLE ADAPTATION

While FLUX.2 Klein 4B provides strong base capabilities, achieving consistent top-down perspective and pixel-art style requires model adaptation. We implement a LoRA fine-tuning pipeline using a curated 100-image dataset.

### A. LoRA Architecture

Low-Rank Adaptation (LoRA) enables efficient model fine-tuning by training low-rank decomposition matrices:

**Base model**: Frozen weights (4B parameters)
**LoRA adapters**: Trainable matrices (0.1-1% of base parameters)
**Inference**: Base weights + LoRA weights combined at runtime

This approach offers several advantages:
- **Storage efficiency**: LoRA weights ~250 MB vs. 6 GB base model
- **Training efficiency**: Fewer parameters require less VRAM and compute
- **Composability**: Multiple LoRAs can be combined (e.g., style + perspective)
- **Reversibility**: Base model remains unchanged

### B. Dataset Curation

The training dataset consists of 100 top-down medieval pixel-art images generated through a multi-stage pipeline:

**Generation**: ComfyUI workflow combining FLUX.2 [dev] with Multi-Angles LoRA v2
- Base model: FLUX.2 [dev] (12B parameters)
- Perspective LoRA: Multi-Angles LoRA v2 (top-down view)
- Post-processing: PixelArt-Detector (palette quantization), rembg (background removal)

**Curation**: Manual review of generated images
- Quality filtering: Remove images with artifacts, incorrect perspective, or poor composition
- Diversity selection: Ensure representation across asset types (structures 55%, objects 25%, terrain 20%)
- Resolution standardization: All images resized to 1024×1024

**Caption generation**: Three detail levels for experimental comparison
- **Detailed**: 50-100 word descriptions including materials, architectural features, condition
- **Minimal**: 20-30 word descriptions focusing on essential characteristics
- **Ultra-minimal**: 5-10 word descriptions with only asset type and style

Example captions:
- Detailed: "A medieval granary built from weathered oak planks with a thatched roof, elevated on stone pillars to prevent rodent access, featuring small ventilation windows and a wooden ladder, pixel art style with limited color palette"
- Minimal: "Medieval wooden granary with thatched roof on stone pillars, pixel art style"
- Ultra-minimal: "Medieval granary, pixel art"

### C. Trigger Token and Angle Phrase

The LoRA adapter is activated through a trigger token and angle phrase:

**Trigger token**: `<tdp>` (top-down perspective)
**Angle phrase**: "top-down view."

Both must be present at inference time. The trigger token activates the LoRA weights, while the angle phrase reinforces the perspective constraint.

Example inference prompt:
```
<tdp> top-down view. A medieval blacksmith's forge with an anvil, bellows, and coal forge, surrounded by weapons and armor, pixel art style
```

### D. Six-Experiment Matrix

We evaluate the interaction between caption detail and LoRA rank through a 3×2 experimental matrix:

**Caption detail** (3 levels):
- Detailed: Rich descriptions with specific features
- Minimal: Essential characteristics only
- Ultra-minimal: Asset type and style only

**LoRA rank** (2 levels):
- High: linear=128, conv=64 (higher capacity, risk of overfitting)
- Low: linear=64, conv=32 (lower capacity, better generalization)

**Experimental hypotheses**:
1. Detailed captions + high rank: Best in-distribution performance, poor generalization
2. Minimal captions + high rank: Balanced performance and generalization
3. Ultra-minimal captions + low rank: Best generalization, limited detail reproduction

**Training configuration** (shared across experiments):
- Steps: 2500
- Batch size: 1
- Learning rate: 8e-5 (detailed/minimal), 5e-5 (ultra-minimal)
- Optimizer: adamw8bit with weight decay 1e-4
- Scheduler: flowmatch with weighted timestep sampling
- Checkpoints: Every 200 steps
- Validation: 8 sample prompts (4 in-distribution, 4 out-of-distribution)

### E. Training Pipeline

The training pipeline consists of five stages:

**1. Extract training set**:
- Copy curated images to training directory
- Generate caption sidecar files (.txt) with `[trigger]` placeholder
- Ostris AI Toolkit replaces `[trigger]` with `<tdp>` at training time

**2. Validate dataset**:
- Check image-caption pairing
- Verify image dimensions and format
- Report dataset statistics

**3. Derive caption variants**:
- Generate detailed, minimal, and ultra-minimal captions from metadata
- Create separate training directories for each variant

**4. Sync validation prompts**:
- Copy sample prompts from experiment design to training configs
- Ensure consistent evaluation across experiments

**5. Train LoRA adapters**:
- Launch six training jobs (one per experiment)
- Monitor training progress through sample generation
- Save checkpoints every 200 steps

### F. Evaluation Methodology

Each experiment generates samples at 250-step intervals using eight validation prompts:

**In-distribution prompts** (4):
- Medieval assets similar to training data
- Tests memorization and style reproduction

**Out-of-distribution prompts** (4):
- Modern objects (sports car, spaceship, coffee cup, suburban house)
- Tests generalization and perspective enforcement

Evaluation criteria:
- **Perspective consistency**: Does the asset maintain top-down view?
- **Style adherence**: Does the output match pixel-art aesthetic?
- **Prompt fidelity**: Does the asset reflect the description?
- **Generalization**: Does the LoRA work for unseen asset types?

### G. Results and Analysis

Preliminary results suggest:

**Detailed captions + high rank**: Excellent reproduction of specific features (crenellations, materials, architectural details) but limited generalization to modern objects. The model memorizes training patterns rather than learning abstract perspective concepts.

**Minimal captions + high rank**: Balanced performance with good perspective consistency and reasonable generalization. The model learns essential characteristics without overfitting to specific features.

**Ultra-minimal captions + low rank**: Strongest generalization to out-of-distribution prompts, enforcing top-down perspective even for modern objects. However, limited ability to reproduce specific medieval features.

These results support the hypothesis that caption detail and LoRA rank interact significantly. Less detailed captions force the model to learn abstract concepts (perspective, style) rather than specific patterns, improving generalization at the cost of detail reproduction.

### H. Deployment

The best-performing LoRA weights (minimal captions, high rank) are deployed to the asset server:
- File: `flux2_klein_4b_lora_000002400.safetensors`
- Strength: 1.0 (full LoRA influence)
- Trigger: `<tdp>` token in prompt templates
- Activation: Automatic for structures, objects, terrain, units

---

## VII. FRONTEND INTEGRATION AND USER EXPERIENCE

The Next.js frontend integrates the backend game engine and asset server into a cohesive user experience, implementing graceful degradation when AI services are unavailable.

### A. Architecture

The frontend follows a component-based architecture with three primary layers:

**State management**: React Context API with useReducer for game state
- Actions: User inputs (move unit, found city, end turn)
- Reducers: Pure functions updating immutable state
- Context: Global state accessible to all components

**API integration**: Typed client for backend and asset server communication
- Backend: 14 endpoints for game actions and state queries
- Asset server: 35 endpoints for asset generation and retrieval
- Error handling: Graceful fallback on API failures

**Rendering**: SVG-based hex map with layered visualization
- Terrain layer: Color-coded hexagons with elevation shading
- Asset layer: Generated pixel-art sprites with fallback glyphs
- UI layer: Selection highlights, movement ranges, fog of war

### B. Asset Manifest Resolution

The frontend implements a sophisticated asset loading system that maps game state to generative assets:

**Terrain mapping**: 13 game terrain types → 5 asset server types
- grassland, plains, savanna, forest, taiga → grass
- hills, mountain, tundra, snow → stone
- desert → sand
- ocean, coast, lake → water

**Unit mapping**: 7 game unit types → 4 asset server types
- warrior, swordsman, horseman → warrior
- archer → archer
- scout → scout
- settler, worker → settler

**Leader resolution**: Archetype + culture → style mapping
- Genghis Khan (aggressive, mongol) → slavic_timber style
- Cleopatra (diplomatic, egyptian) → moorish style
- Gandhi (peaceful, indian) → mediterranean style

**Caching strategy**: localStorage with host-tag invalidation
- Key format: `inf3600:assetManifest:{hostTag}:{gameId}`
- Invalidation: New host tag on asset server updates
- Fallback: Re-generation on cache miss

### C. Graceful Degradation

The system implements multiple fallback levels:

**Level 1: Generative assets** (ideal):
- Asset server generates pixel-art on-demand
- Frontend displays high-quality, context-specific assets

**Level 2: Static assets** (asset server unavailable):
- Pre-generated assets from filesystem
- Lower diversity but consistent quality

**Level 3: Placeholder assets** (GPU unavailable):
- PIL-generated colored rectangles with text labels
- Functional but aesthetically limited

**Level 4: Built-in fallbacks** (asset server completely unavailable):
- Color-coded hexagons for terrain
- Glyph icons for units and structures
- Initial letters for leader portraits

This ensures the game remains playable regardless of AI service availability.

### D. User Interface

The frontend provides a Civilization-style interface with:

**Main map**: SVG hex grid with pan/zoom controls
- Terrain visualization with elevation shading
- Unit and structure sprites with selection highlights
- Fog of war for unexplored territories
- Movement range indicators

**Side panels**: Context-sensitive information displays
- Unit details: Stats, movement, actions
- City management: Production queue, buildings, worked tiles
- Diplomacy: Message history, relationship status, negotiations
- Technology tree: Research progress, available technologies

**Leader portraits**: Generated splash art with interactive elements
- Click to view full-screen portrait
- Hover for leader biography and personality
- Diplomatic audience chamber for negotiations

### E. Diplomatic Interface

The diplomacy system provides a chat-based interface for leader interactions:

**Message composition**: Free-text input with message type selection
- Chat: Casual conversation
- Threat: Aggressive posturing
- Offer peace: Propose end to hostilities
- Declare war: Formal declaration of hostilities
- Propose alliance: Suggest mutual cooperation

**AI responses**: LLM-generated messages reflecting leader personality
- Genghis Khan: Terse, imperious, contemptuous of weakness
- Cleopatra: Warm, witty, never quite saying what she means
- Gandhi: Calm, principled, formal with references to higher ideals

**Relationship tracking**: Visual indicator of diplomatic status
- Relationship score: -100 (hostile) to +100 (allied)
- Stance: Peace, war, or alliance
- Recent events: Message history with relationship deltas

---

## VIII. EVALUATION

We evaluate StrategAI across three dimensions: system performance, test coverage, and AI behavior quality.

### A. Performance Metrics

**Backend performance**:
- API response time: <50ms for state queries, <100ms for actions
- LLM decision time: 2-4 seconds per AI civilization per turn
- Game state serialization: <10ms for full state export
- Concurrent games: Limited by in-memory store (single-instance deployment)

**Asset server performance**:
- Generation time: 1.2-4 seconds per image (RTX 5090)
- API response time: <100ms for cached assets, 2-5 seconds for generation
- Cache hit rate: ~80% for typical gameplay (repeated terrain/unit types)
- Concurrent requests: Limited by ComfyUI queue (sequential processing)

**Frontend performance**:
- Initial load: 2-3 seconds (Next.js hydration + asset manifest resolution)
- Map rendering: 60 FPS for 1000-hex maps with SVG optimization
- Asset loading: Parallel requests with 5-connection limit
- State updates: <16ms for local actions, 100-200ms for AI turns

### B. Test Coverage

The system implements comprehensive testing across all components:

**Backend** (315+ tests):
- Unit tests: Game engine logic, intent resolution, combat formulas
- Integration tests: API endpoints, state serialization, LLM mocking
- Property tests: Invariant validation (immutability, rule compliance)
- Coverage: ~85% of engine code

**Asset server** (547 tests):
- Unit tests: Prompt assembly, workflow patching, database operations
- Integration tests: API endpoints, ComfyUI mocking, post-processing
- Concurrency tests: Load balancer, cache behavior, race conditions
- Coverage: ~82% of server code

**Frontend** (TypeScript strict mode):
- Type checking: Compile-time validation of API contracts
- Component tests: Rendering logic, state management
- Integration tests: Asset manifest resolution, fallback behavior
- Coverage: ~70% of component code

**Training pipeline** (35 tests):
- Unit tests: Caption generation, dataset validation, config syncing
- Integration tests: End-to-end pipeline execution
- Coverage: ~90% of training code

Total: 932 tests with ~80% aggregate coverage.

### C. AI Behavior Quality

Qualitative evaluation of AI civilization behavior reveals:

**Strategic diversity**: Each AI civilization exhibits distinct strategies aligned with persona:
- Genghis Khan: Aggressive expansion, early military production, frequent warfare
- Cleopatra: Diplomatic engagement, alliance formation, economic focus
- Gandhi: Peaceful development, technology research, defensive positioning

**Emergent behavior**: Unscripted interactions arising from LLM reasoning:
- Opportunistic attacks when enemies are weakened
- Defensive alliances against aggressive civilizations
- Technology trading and diplomatic negotiations
- Revenge behavior (Genghis Khan remembering insults)

**Adaptation**: AI responses to changing game conditions:
- Shift from expansion to defense when threatened
- Technology prioritization based on military needs
- Diplomatic stance changes based on relationship scores

**Limitations**: Observed weaknesses in AI behavior:
- Occasional repetition of failed strategies (mitigated by memory system)
- Suboptimal city placement in some scenarios
- Difficulty coordinating multi-unit attacks

### D. Asset Quality

Generated assets demonstrate:

**Style consistency**: Uniform pixel-art aesthetic across all asset types
- Consistent color palettes within asset families
- Appropriate level of detail for 256×256 resolution
- Clean edges suitable for game integration

**Perspective adherence**: Top-down view maintained across diverse assets
- Structures show roof and layout clearly
- Units face camera with visible features
- Terrain tiles show elevation and texture

**Identity preservation**: Leader portraits maintain character consistency
- Splash art establishes canonical appearance
- Profile portraits preserve facial features and attire
- Action scenes maintain recognizability despite pose changes

**Diversity**: Sufficient variation to avoid repetitive appearance
- 420 possible structure combinations
- 140 possible object combinations
- Unique leader portraits for each civilization

---

## IX. DISCUSSION AND LIMITATIONS

### A. Architectural Trade-offs

**Microservices vs. monolith**: The microservices architecture enables independent scaling and deployment but introduces network latency and coordination complexity. For a single-developer project, a monolithic approach might have been simpler, though less flexible.

**LLM abstraction layer**: The intent-based abstraction sacrifices some flexibility (LLMs cannot directly manipulate game state) for reliability (deterministic rule enforcement). This trade-off is appropriate for rule-based games but may not suit open-ended simulations.

**Asset generation modes**: Supporting three generation modes (comfyui, static, placeholder) increases code complexity but ensures system functionality across diverse deployment scenarios. This is essential for development and testing without GPU resources.

### B. Technical Limitations

**Single-instance deployment**: The backend uses in-memory state storage, limiting deployment to a single instance. Production deployment would require database persistence and horizontal scaling.

**Synchronous asset generation**: The asset server holds HTTP connections open during generation (2-4 seconds), limiting throughput. An asynchronous job queue (Celery + Redis) would improve scalability.

**LLM cost**: GPT-4 API calls incur per-token costs (~$0.03 per AI turn at current prompt sizes). For extended gameplay, costs accumulate. Smaller models (GPT-4-mini) could reduce costs with some quality loss.

**Model size constraints**: FLUX.2 Klein 4B was selected for VRAM efficiency, but larger models (FLUX.2 Klein 9B, Stable Diffusion 3) offer superior quality. The 4B model occasionally produces artifacts or inconsistent details.

**LoRA generalization**: The fine-tuned LoRA enforces top-down perspective but struggles with some asset types (complex machinery, modern objects). Additional training data or multi-LoRA composition could improve generalization.

### C. AI Behavior Limitations

**Strategic depth**: While AI civilizations exhibit diverse behaviors, they lack long-term strategic planning. LLMs excel at tactical decisions but struggle with multi-turn strategic goals (e.g., "build three cities, then research iron working, then attack").

**Coordination**: AI civilizations act independently without coordinating attacks or forming strategic alliances beyond bilateral agreements. Multi-agent coordination remains an open research challenge.

**Exploitation**: Human players can exploit AI patterns (e.g., repeatedly offering peace then attacking). The memory system mitigates this but does not eliminate it entirely.

### D. Future Work

**Persistent storage**: Implement database backend (PostgreSQL) for game state persistence and multi-instance deployment.

**Asynchronous generation**: Add job queue (Celery + Redis) for non-blocking asset generation with progress notifications.

**Model upgrades**: Evaluate newer models (GPT-5, FLUX.2 Klein 9B) as they become available and VRAM-efficient.

**Multi-agent coordination**: Implement coalition logic enabling AI civilizations to coordinate attacks and form multi-party alliances.

**Procedural narrative**: Use LLMs to generate historical narratives based on game events, creating unique stories for each playthrough.

**User-generated content**: Enable players to create custom civilizations with persona descriptions and asset styles, leveraging the generative AI pipeline.

**Quantitative evaluation**: Implement automated metrics (FID, CLIP score, DINO similarity) for asset quality assessment.

**Expanded asset types**: Add support for animations, sound effects, and UI elements through additional generative models.

---

## X. CONCLUSION

StrategAI demonstrates that modern generative AI technologies—Large Language Models and Diffusion Transformers—can be integrated into a cohesive, functional game system accessible to independent developers. Through careful architectural design, we address key challenges: translating LLM reasoning into deterministic game actions, maintaining visual consistency across diverse asset types, and ensuring system functionality when AI services are unavailable.

The intent-based abstraction layer enables LLMs to control game entities without direct state manipulation, leveraging language models' strategic reasoning while maintaining rule compliance. The four-layer prompt architecture provides systematic asset generation with consistent style and perspective. The three-stage leader portrait pipeline demonstrates identity preservation through carefully calibrated denoising parameters. The LoRA fine-tuning pipeline enables model adaptation to specific visual styles with minimal computational resources.

While limitations remain—single-instance deployment, synchronous generation, strategic depth—StrategAI provides a reference implementation for future projects combining multiple generative AI systems. The open-source codebase, comprehensive documentation, and extensive test suite (932 tests, ~80% coverage) offer a foundation for further research and development.

As generative AI models continue to improve in quality, speed, and efficiency, we anticipate increased adoption in game development. StrategAI demonstrates that these technologies are not merely research curiosities but practical tools enabling new forms of interactive entertainment. The integration patterns, architectural decisions, and engineering solutions presented here provide a roadmap for developers seeking to harness the power of generative AI in their own projects.

---

## REFERENCES

[1] D. Mark, "Behavior trees for AI: How they work," *Gamasutra*, 2012.

[2] S. Rabin, *Game AI Pro: Collected Wisdom of Game AI Professionals*. CRC Press, 2013.

[3] D. Mark, "Utility-based AI systems," *Game Developers Conference*, 2015.

[4] J. S. Park et al., "Generative agents: Interactive simulacra of human behavior," in *Proc. UIST*, 2023.

[5] Z. Zhu et al., "Ghost in the Minecraft: Generally capable agents for open-world environments via large language models with text-based knowledge and memory," *arXiv preprint arXiv:2305.17144*, 2023.

[6] R. Volum et al., "Craft an iron sword: Dynamically generating interactive game characters by prompting large language models tuned on code execution," in *Proc. Wordplay*, 2022.

[7] M. Toy, G. Wichman, K. Arnold, and L. Wood, "Rogue," *BSD*, 1980.

[8] Hello Games, "No Man's Sky," 2016.

[9] K. Perlin, "An image synthesizer," *ACM SIGGRAPH Computer Graphics*, vol. 19, no. 3, pp. 287-296, 1985.

[10] Y. I. H. Parish and P. Müller, "Procedural modeling of buildings," *ACM Transactions on Graphics*, vol. 25, no. 3, pp. 634-643, 2006.

[11] A. M. Smith and M. Mateas, "Answering the call: Procedural content generation for games," in *Proc. FDG*, 2011.

[12] A. Summerville et al., "Machine learning for interactive content generation in games," *IEEE Transactions on Games*, vol. 10, no. 3, pp. 241-258, 2018.

[13] J. Schrum, J. K. Pugh, and K. O. Stanley, "Evolving neural networks for creative design," in *Proc. EvoApplications*, 2016.

[14] D. P. Kingma and M. Welling, "Auto-encoding variational Bayes," *arXiv preprint arXiv:1312.6114*, 2013.

[15] J. Ho, A. Jain, and P. Abbeel, "Denoising diffusion probabilistic models," in *Proc. NeurIPS*, 2020.

[16] R. Rombach et al., "High-resolution image synthesis with latent diffusion models," in *Proc. CVPR*, 2022.

[17] A. Hertzmann, "Can AI make art?," *arXiv preprint arXiv:2304.07999*, 2023.

[18] E. J. Hu et al., "LoRA: Low-rank adaptation of large language models," in *Proc. ICLR*, 2022.

[19] PixelArt-LoRA, "PixelArt-LoRA: Fine-tuning Stable Diffusion for pixel art," *Hugging Face*, 2023.

[20] TopDown-LoRA, "TopDown-LoRA: Overhead perspective adaptation," *CivitAI*, 2023.

[21] M. Wooldridge, *An Introduction to MultiAgent Systems*. John Wiley & Sons, 2009.

[22] P. Stone and M. Veloso, "Multiagent systems: A survey from a machine learning perspective," *Autonomous Robots*, vol. 8, no. 3, pp. 345-373, 2000.

---

## APPENDIX A: SYSTEM REQUIREMENTS

**Minimum hardware**:
- CPU: 4-core processor
- RAM: 16 GB
- GPU: 8 GB VRAM (RTX 3070 or equivalent)
- Storage: 50 GB (models + generated assets)

**Recommended hardware**:
- CPU: 8-core processor
- RAM: 32 GB
- GPU: 12 GB VRAM (RTX 4070 or equivalent)
- Storage: 100 GB SSD

**Software dependencies**:
- Python 3.10+
- Node.js 18+
- ComfyUI 0.9.2+
- CUDA 11.8+ (for GPU acceleration)

---

## APPENDIX B: API ENDPOINTS

**Backend** (14 endpoints):
- `POST /games`: Create new game
- `GET /games/{id}`: Retrieve game state
- `POST /games/{id}/turn`: End human turn
- `POST /games/{id}/turn/resolve`: Resolve AI turns
- `POST /games/{id}/actions/move`: Move unit
- `POST /games/{id}/actions/attack`: Attack unit
- `POST /games/{id}/actions/attack-city`: Attack city
- `POST /games/{id}/actions/found`: Found city
- `POST /games/{id}/actions/research`: Set research
- `POST /games/{id}/actions/build`: Queue production
- `POST /games/{id}/actions/cancel-build`: Cancel production
- `POST /games/{id}/actions/purchase-structure`: Buy structure
- `POST /games/{id}/actions/improve`: Start improvement
- `POST /games/{id}/actions/message`: Send diplomatic message

**Asset server** (35 endpoints):
- Global: `/health`, `/health/ready`, `/modes`, `/catalog`, `/assets/{filename}`
- Per-family (6 families × 5 endpoints): `POST /{family}`, `GET /{family}`, `GET /{family}/catalog`, `GET /{family}/{id}`, `DELETE /{family}/{id}`

---

## APPENDIX C: CODE AVAILABILITY

The complete StrategAI codebase is available at: https://github.com/[username]/StrategAI

The curated dataset is published on Hugging Face: https://huggingface.co/datasets/stixxert/topdown-medieval-pixelart

Trained LoRA weights are available at: https://huggingface.co/stixxert/topdown-medieval-pixelart

---

**Acknowledgment**: This work was completed as part of the INF-3600 Generative AI course project. The authors thank the course instructors for guidance and feedback throughout development.
