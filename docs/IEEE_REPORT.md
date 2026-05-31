# StrategAI: Integrating Large Language Models and Diffusion Transformers for AI-Driven Strategy Game Development

**Abstract**—This paper presents StrategAI, a full-stack strategy game that demonstrates practical integration of multiple generative AI technologies in a cohesive software system. The project combines Large Language Models (LLMs) for autonomous civilization management with Diffusion Transformers (DiTs) for on-demand asset generation, unified through a modern web architecture. Three AI civilizations, each controlled by GPT-4 via OpenAI's tool-use API, make strategic decisions through a novel intent-based abstraction layer that translates high-level goals into deterministic game actions. Concurrently, a self-hosted asset pipeline leverages FLUX.2 Klein 4B Distilled—a 4-billion parameter DiT model—to generate medieval pixel-art assets through a four-layer prompt architecture and three-stage leader portrait pipeline with identity preservation. A LoRA fine-tuning pipeline adapts the base model to a consistent top-down perspective using a curated 100-image dataset. The system demonstrates that consumer-grade GPUs (8-12 GB VRAM) can support both real-time LLM-driven gameplay and near-interactive asset generation (1.2-4 seconds per image), making advanced generative AI accessible for independent game development. We detail the architectural decisions, integration patterns, and engineering challenges encountered in building this multi-agent system, providing a reference implementation for future projects combining language models with visual generation.

**Index Terms**—Large Language Models, Diffusion Transformers, Game AI, Asset Generation, LoRA Fine-Tuning, Tool Use, Multi-Agent Systems

---

## I. INTRODUCTION

The rapid advancement of generative AI has opened new possibilities for interactive entertainment, yet practical implementations combining multiple AI modalities remain rare. Most game AI systems rely on behavior trees, finite state machines, or scripted decision logic, while asset creation remains a manual, time-intensive process requiring specialized artistic skills. This separation limits the potential for truly dynamic, AI-driven game experiences.

StrategAI addresses this gap by integrating two complementary generative AI technologies into a single cohesive system: (1) Large Language Models for strategic decision-making and diplomatic interaction, and (2) Diffusion Transformers for procedural asset generation. The result is a Civilization-style strategy game where AI opponents exhibit emergent strategic behavior through natural language reasoning, while game assets—terrain, buildings, units, and leader portraits—are generated on-demand to match the evolving game state.

### A. Motivation

Independent game developers face two fundamental challenges when attempting to incorporate advanced AI:

**Computational constraints**: State-of-the-art models often require enterprise-grade hardware (24+ GB VRAM, multi-GPU clusters) that exceeds typical development budgets. Cloud-based APIs introduce latency, recurring costs, and dependency on external services.

**Integration complexity**: Combining multiple AI systems requires careful architectural design to manage data flow, error handling, and graceful degradation. Most existing frameworks address single modalities in isolation.

StrategAI demonstrates that these challenges can be overcome through thoughtful system design. By selecting appropriately-sized models (GPT-4 for reasoning, FLUX.2 Klein 4B Distilled for generation) and implementing robust fallback mechanisms, the system achieves real-time performance on consumer hardware while maintaining production-quality output.

### B. Contributions

This work makes the following contributions:

1. **Intent-based LLM integration**: A novel abstraction layer that translates high-level strategic intents (expand, engage, reinforce) into deterministic game actions, enabling LLMs to control game entities without direct state manipulation.

2. **Four-layer prompt architecture**: A systematic approach to asset generation that separates workflow configuration, style templates, semantic descriptions, and assembly logic, enabling consistent output across diverse asset types.

3. **Three-stage identity preservation pipeline**: A leader portrait generation system that maintains character consistency across splash art, profile images, and action scenes through carefully calibrated denoising parameters.

4. **LoRA fine-tuning methodology**: A complete pipeline for adapting diffusion models to specific visual styles, including dataset curation, caption design, and a six-experiment matrix evaluating caption detail and rank configurations.

5. **Graceful degradation patterns**: Comprehensive fallback strategies ensuring system functionality when AI services are unavailable, from random AI behavior to placeholder assets.

6. **Reference implementation**: A fully functional, open-source codebase demonstrating best practices for integrating multiple generative AI systems in a production application.

### C. Paper Organization

The remainder of this paper is organized as follows: Section II reviews related work in game AI and procedural content generation. Section III presents the overall system architecture. Sections IV, V, and VI detail the LLM integration, asset generation pipeline, and LoRA fine-tuning process, respectively. Section VII describes frontend integration and user experience. Section VIII evaluates system performance and test coverage. Section IX examines ethical considerations including bias, environmental impact, content moderation, copyright, and reproducibility. Section X discusses limitations and future work. Section XI concludes.

---

## II. RELATED WORK

### A. Game AI and Large Language Models

Traditional game AI relies on hand-crafted decision systems. Behavior trees [1] provide hierarchical task decomposition but require extensive manual authoring. Finite state machines [2] offer predictable transitions but struggle with complex, emergent scenarios. Utility-based systems [3] enable nuanced decision-making through weighted scoring but lack the flexibility to handle novel situations.

Recent work has explored LLMs for game AI. Park et al. [4] demonstrated "generative agents" that simulate human behavior through natural language reasoning, though their system operated in a sandbox environment without competitive gameplay. Zhu et al. [5] used GPT-4 to generate dialogue for non-player characters, but decision-making remained scripted. Volum et al. [6] proposed "CraftAssist" for Minecraft, using LLMs to interpret player commands, but the AI did not autonomously pursue goals. Wang et al. [27] introduced Voyager, an LLM-powered agent that autonomously explores Minecraft through self-generated skill libraries and iterative code generation, establishing LLMs as lifelong learners in open-ended game environments. Schick et al. [28] demonstrated that LLMs can teach themselves to invoke external tools via API calls—a capability that directly motivates our intent-based abstraction.

StrategAI differs by employing LLMs as autonomous strategic agents in a competitive, rule-bound environment. Our intent-based abstraction addresses a key challenge: LLMs excel at high-level reasoning but struggle with precise numerical calculations and spatial logic. By separating strategic intent from tactical execution, we leverage LLM strengths while maintaining deterministic game mechanics.

### B. Procedural Content Generation

Procedural Content Generation (PCG) has a long history in games, from early roguelikes [7] to modern titles like No Man's Sky [8]. Traditional PCG uses algorithmic techniques: noise functions for terrain [9], grammar-based systems for structures [10], and constraint solvers for level design [11].

Deep learning has expanded PCG capabilities. Generative Adversarial Networks (GANs) have generated game levels [12] and textures [13], but training instability and mode collapse limit practical adoption. Variational Autoencoders (VAEs) offer more stable training [14] but often produce blurry outputs unsuitable for pixel art.

Diffusion models [15], [16] have emerged as the state-of-the-art for image generation, offering high-quality outputs with diverse variations. Peebles and Xie [29] advanced this paradigm by replacing the U-Net backbone with a pure Transformer architecture, creating Diffusion Transformers (DiTs) that exhibit superior scaling behavior and prompt adherence. Liu et al. [30] proposed rectified flow, an alternative to score-based diffusion that learns straight-line trajectories for substantially faster sampling—a technique adopted by the FLUX model family that powers our asset pipeline. However, their application to game assets remains limited. Most existing work focuses on concept art generation [17] rather than production-ready assets with specific technical requirements (transparent backgrounds, consistent perspective, tileable textures).

StrategAI addresses these requirements through a multi-stage pipeline combining diffusion models with post-processing (background removal, palette quantization) and a structured prompt system that enforces asset specifications.

### C. Model Adaptation and Fine-Tuning

Full fine-tuning of large diffusion models is computationally prohibitive for most developers. Parameter-Efficient Fine-Tuning (PEFT) methods like LoRA [18] enable adaptation with minimal additional parameters (typically 0.1-1% of base model size).

Several works have applied LoRA to game asset generation. PixelArt-LoRA [19] adapts Stable Diffusion for pixel art but focuses on side-view sprites. TopDown-LoRA [20] targets overhead perspectives but lacks the medieval aesthetic required for strategy games.

Our approach differs in three ways: (1) we target FLUX.2 Klein 4B Distilled [29], a newer Diffusion Transformer architecture with improved prompt adherence; FP8 quantization [31] further reduces the model's VRAM footprint from 16 GB to approximately 8.4 GB, making it viable on consumer-grade GPUs such as the RTX 3070 and 4070; (2) we systematically evaluate caption design through a six-experiment matrix; (3) we integrate the fine-tuned model into a production pipeline with automated asset generation.

### D. Multi-Agent Systems

Multi-agent systems (MAS) in games typically involve homogeneous agents with shared decision logic [21]. Heterogeneous MAS, where agents have different capabilities or goals, are more complex but enable richer interactions [22].

StrategAI implements heterogeneous agents through persona-based prompting. Each AI civilization receives a unique character description (Genghis Khan: aggressive expansionist; Cleopatra: diplomatic manipulator; Gandhi: peaceful developer) that influences decision-making while sharing the same underlying intent system. This approach enables diverse strategic behaviors without requiring separate AI implementations.

---

## III. SYSTEM ARCHITECTURE

StrategAI follows a microservices architecture with four primary components: a Python backend implementing the game engine and LLM integration, a Next.js frontend providing the user interface, a FastAPI asset server managing image generation, and a separate training pipeline for model adaptation (Fig. 1).

### A. Component Overview

**Backend** (Python 3.11+, FastAPI): Implements a pure functional game engine with immutable state, LLM-driven AI civilizations, and a RESTful API. The engine enforces deterministic game rules while the LLM layer provides strategic decision-making.

**Frontend** (Next.js 15, React 19, TypeScript): Renders the game state through an SVG-based hex map, manages user interactions, and coordinates asset loading from the asset server. Implements graceful fallback when generative assets are unavailable.

**Asset Server** (Python 3.10+, FastAPI, ComfyUI): Generates pixel-art assets on-demand using FLUX.2 Klein 4B Distilled. Provides 35 REST endpoints across six asset families (structures, objects, terrain, units, background tiles, leaders) with three generation modes (comfyui, static, placeholder).

**Training Pipeline** (Python 3.10+, Ostris AI Toolkit): Fine-tunes LoRA adapters for FLUX.2 Klein 4B Distilled using a curated dataset of medieval pixel art. Produces model weights that enforce top-down perspective and pixel-art style.

### B. Data Flow

The system operates through three primary data flows:

**Gameplay loop**: User actions → Backend API → Game engine state update → LLM decision-making (AI turns) → State serialization → Frontend rendering

**Asset generation**: Frontend asset request → Asset server API → ComfyUI workflow execution → FLUX.2 Klein 4B Distilled inference → Post-processing → Image storage → Frontend display

**Model training**: Dataset curation → Caption generation → LoRA training → Model evaluation → Weight deployment to asset server

### C. Technology Stack Rationale

**FLUX.2 Klein 4B Distilled** was selected over alternatives (Stable Diffusion XL, FLUX.2 Klein 9B) based on four criteria:

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

The asset server generates pixel-art assets on-demand using FLUX.2 Klein 4B Distilled, a 4-billion parameter Diffusion Transformer. The pipeline implements a four-layer prompt architecture and supports six asset families with diverse technical requirements.

### A. Model Architecture

FLUX.2 Klein 4B Distilled represents a shift from traditional U-Net diffusion models to transformer-based architectures:

**Diffusion Transformer (DiT)**: Replaces U-Net backbone with Vision Transformer operating on latent-space patches. Enables better scaling and improved prompt adherence.

**Rectified flow formulation**: Uses straight-line paths from noise to data distribution, enabling fewer inference steps (4 vs. 50 for traditional DDPM).

**Qwen 3 4B text encoder**: Replaces CLIP with a larger language model, providing superior understanding of complex prompts.

**FP8 quantization**: Reduces VRAM requirement from ~16 GB to ~8.4 GB with minimal quality loss.

The model requires four files totaling ~14.6 GB:
- `flux-2-klein-4b-fp8.safetensors` (6 GB): DiT transformer weights
- `qwen_3_4b.safetensors` (8 GB): Text encoder weights
- `flux2-vae.safetensors` (320 MB): Variational autoencoder
- `detailed_high_1800.safetensors` (250 MB): Top-down medieval style LoRA (custom-trained)

### B. Four-Layer Prompt Architecture

Consistent asset generation requires systematic prompt construction. We implement a four-layer architecture separating concerns:

**Layer 1: Workflow configuration** (ComfyUI JSON):
- Model selection: UNETLoader, CLIPLoader, VAELoader
- Sampler configuration: euler sampler, simple scheduler, 4 steps
- Resolution: 1024×1024 generation, 256×256 output
- Guidance: FluxGuidance (2.5-8.0 depending on asset type)
- Post-processing: Lanczos resize, image sharpening, background removal

**Layer 2: Style templates** (prompt_templates.json):
- Camera framing: "top-down view."
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

**comfyui**: Full AI generation using FLUX.2 Klein 4B Distilled
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

While FLUX.2 Klein 4B Distilled provides strong base capabilities, achieving consistent top-down perspective and pixel-art style requires model adaptation. We implement a LoRA fine-tuning pipeline using a curated 100-image dataset.

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

The training pipeline automates dataset preparation and model fine-tuning through five stages: (1) extract training images with caption sidecar files containing `[trigger]` placeholders, (2) validate image-caption pairing and dataset statistics, (3) derive three caption variants (detailed/minimal/ultra-minimal) from metadata, (4) synchronize validation prompts across experiment configs, and (5) launch six parallel training jobs with checkpoint saves every 200 steps. The Ostris AI Toolkit replaces `[trigger]` with `<tdp>` at training time, ensuring the model learns to associate the trigger token with the top-down perspective constraint.

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

Fig. 2 presents a qualitative comparison of the caption detail trade-off spectrum in a 2×4 layout: two prompt subjects (S1: watchtower, T3: boulder) evaluated across four conditions (base model without LoRA, ultra_low, minimal_high, detailed_high).

![LoRA caption detail trade-off: 2×4 grid — rows: S1 watchtower, T3 boulder; columns: base model (unreliable perspective), ultra_low (strongest generalization), minimal_high (balanced), detailed_high (optimal — maximum architectural fidelity)](../dataset-gen-train/figures/report_figure.png)

**Fig. 2.** Qualitative comparison of caption detail strategies in a 2×4 grid. Rows (subjects): S1 watchtower (in-distribution structure), T3 boulder (out-of-distribution nature object). Columns (conditions): base model (no LoRA), ultra_low, minimal_high, detailed_high. Base model without LoRA—text prompts alone ("top-down view.") provide unreliable perspective enforcement. LoRA variants provide consistent, reliable top-down perspective: ultra_low achieves strongest generalization but sacrifices detail; minimal_high achieves balanced detail reproduction and generalization; detailed_high achieves optimal in-distribution architectural fidelity with acceptable out-of-distribution generalization, making it the recommended variant for deployment.

**Key findings**: The detailed_high experiment (detailed captions, 50–100 words, high rank: linear=128, conv=64) achieves the best balance between architectural detail reproduction and practical deployment quality. In-distribution structures show crisp pixel-art styling with accurate architectural features (crenellations, timber framing, stone masonry) rendered at higher fidelity than any other variant, while out-of-distribution units maintain top-down perspective despite never appearing in training data. The ultra_low experiment (ultra-minimal captions, low rank) demonstrates stronger generalization to unseen asset types but sacrifices fine detail—structures appear less architecturally specific. The base model without LoRA fails to maintain consistent top-down perspective across all categories, confirming the necessity of fine-tuning.

**Style leakage**: To verify that the LoRA's influence is appropriately scoped to its intended domain, we evaluated all six variants against a trigger-free prompt depicting a modern red sports car. This probe tests whether medieval or pixel-art styling inappropriately "leaks" into semantically distant subject matter when no trigger token is present. Across all variants, the generated sports cars remain recognizably modern: no top-down perspective, crenellation-like details, or pixel-art quantization appear. The LoRA variants produce renderings comparable to the base model baseline, with only subtle differences in lighting and surface treatment attributable to the model's learned priors rather than medieval style transfer. This confirms that the `<tdp>` trigger token effectively gates style application—without it, the LoRA weights exert negligible influence on generation, even at full strength (1.0). A full grid comparing all seven rows (six variants plus base model) across multiple prompt subjects (S1, T3, and others) is provided in the model card (`figures/model_card_figure_7x4.png`).

**Training dynamics**: Analysis of checkpoint progression reveals distinct under-training and over-training regimes. Early checkpoints (steps 500–1000) produce noisy outputs with inconsistent perspective and weak pixel-art styling. The sweet spot emerges around steps 1500–2000, where perspective consistency and style adherence peak. Beyond step 2200, some experiments exhibit overfitting artifacts: rigid repetition of training patterns, color palette collapse, and reduced compositional diversity. For example, detailed_high at step 2400 produces nearly identical watchtower layouts across different seeds, indicating memorization rather than learned abstraction.

**Checkpoint selection**: Based on qualitative evaluation, detailed_high at step 1800 provides optimal performance for deployment—maximum in-distribution architectural fidelity with acceptable out-of-distribution generalization. The detailed captions (50–100 words) provide rich architectural descriptions (crenellations, timber framing, stone masonry) that the high-rank LoRA faithfully reproduces, while the high rank (linear=128, conv=64) gives sufficient model capacity to capture fine detail without the over-generalization seen in ultra variants. Critically, style leakage testing confirms that the LoRA is properly scoped: neither cinematic leader portraits nor modern objects (sports car) exhibit medieval or pixel-art influence when the `<tdp>` trigger is absent. This validates the trigger-token mechanism as an effective gating strategy for domain-specific LoRA adapters.

### H. Deployment

Based on qualitative analysis, the detailed_high checkpoint at step 1800 is deployed to the asset server:
- File: `detailed_high_1800.safetensors` (353 MB)
- Strength: 1.0 (full LoRA influence)
- Trigger: `<tdp>` token + "top-down view." angle phrase in prompt templates
- Activation: Automatic for structures, objects, terrain, units

This checkpoint provides maximum in-distribution architectural fidelity (medieval structures with crisp crenellations, timber framing, and stone masonry detail) while maintaining acceptable out-of-distribution generalization (units, modern objects) and avoiding overfitting artifacts observed in later training steps.

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

**Backend** (339+ tests):
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

Total: 886 tests with ~80% aggregate coverage.

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

## IX. ETHICAL CONSIDERATIONS

The integration of generative AI technologies—Large Language Models for strategic decision-making and Diffusion Transformers for asset generation—raises ethical considerations spanning bias, environmental impact, content moderation, intellectual property, and reproducibility. This section examines each concern in the context of StrategAI's design choices and honestly assesses the limitations of the mitigations employed.

### A. Bias in AI-Generated Content

StrategAI employs three AI civilizations modeled after historical figures: Genghis Khan, Cleopatra, and Gandhi. While these personas were selected to create diverse and recognizable strategic archetypes (aggressive expansionist, diplomatic manipulator, and peaceful developer, respectively), the use of culturally specific historical figures carries inherent risks of stereotyping and reductive characterization. Generative models reproduce patterns present in their training data, and LLMs trained on internet-scale corpora have been shown to amplify stereotypes related to nationality, gender, and ethnicity [23].

The system prompts for each leader were designed with an explicit emphasis on respectful depiction. Genghis Khan's persona frames aggression as a strategic calculation rather than barbarism, emphasizing discipline and respect for strength. Cleopatra's persona avoids exoticization, portraying her diplomatic acumen as the product of intelligence rather than seduction. Gandhi's persona grounds his principled stance in philosophy rather than passivity. However, these are mitigations layered on top of a base model whose training distribution may contain biased representations. The system does not implement explicit bias detection or filtering of LLM outputs, relying instead on the persona prompt to steer generation toward respectful territory. This approach is inherently fragile: the persona prompt can be overridden by sufficiently strong priors in the base model, and the long-tail distribution of possible LLM outputs cannot be exhaustively tested for biased content.

The diffusion-based asset generation pipeline introduces additional bias concerns. The curated training dataset of 100 medieval pixel-art images, sourced from OpenGameArt and supplemented with AI-generated samples, was selected for visual quality and perspective consistency rather than representational diversity. The dataset is dominated by European medieval architectural styles (Gothic cathedrals, timber-framed houses, stone castles), which means generated assets for non-European civilizations may exhibit stylistic incongruity. Cleopatra's Egyptian civilization, for instance, may receive assets that inadvertently blend Middle Eastern architectural motifs with European medieval elements, producing ahistorically hybrid representations. The leader portrait pipeline compounds this risk: a single diffusion model generates portraits for all leaders, and without careful prompt engineering, the model may default to Western facial features or attire conventions present in its training distribution [24].

### B. Environmental Cost

The computational demands of generative AI carry measurable environmental costs, primarily through electricity consumption and the associated carbon emissions of data center operations [25]. StrategAI's environmental footprint has two principal components: GPU inference for asset generation and LLM API calls for strategic reasoning.

Asset generation uses FLUX.2 Klein 4B Distilled, a 4-billion parameter DiT model quantized to FP8 precision, requiring approximately 8.4 GB of VRAM for inference. Each generation takes 1.2–4 seconds on a consumer GPU (RTX 3070/4070 at approximately 200–220 W TDP), yielding an estimated energy consumption of 0.07–0.25 Wh per generated image. By comparison, the larger FLUX.2 Klein 9B model would require 16+ GB VRAM and proportionally more energy, which motivated the selection of the smaller variant. The system achieves approximately 80% cache hit rate during typical gameplay, substantially reducing redundant generation. Furthermore, the three-tier generation architecture (comfyui, static, and placeholder modes) enables operators to select the most energy-appropriate mode for their deployment context, including a zero-GPU placeholder mode for development.

LLM API calls to GPT-4 constitute the second energy source, though their footprint is indirect since the computation occurs on OpenAI's infrastructure. Each AI turn sends a prompt of approximately 2,000–4,000 tokens and elicits 100–500 tokens of response across one to five function calls. Over a typical 100-turn game with three AI civilizations, this accumulates to approximately 600,000–1,500,000 tokens processed. While individual API calls have modest energy footprints, aggregate usage across many game sessions is non-trivial. The rolling memory window of 8 turns and the 32-entry log limits were explicitly designed to constrain token consumption, preventing unbounded growth of context that would increase both financial and environmental costs per turn.

It is important to acknowledge that StrategAI's absolute environmental impact is dwarfed by large-scale training runs. Training GPT-4 is estimated to have consumed thousands of megawatt-hours, while StrategAI's inference-only usage represents a tiny fraction. However, as deployment scales to many users, inference costs accumulate, and the design choices documented here—model quantization, caching, tiered generation modes—represent practical patterns for minimizing per-user energy consumption.

### C. Content Moderation

The LLM-driven diplomacy system enables free-form text communication between human players and AI civilizations. While this creates engaging, emergent diplomatic interactions, it also introduces the risk of inappropriate content generation. LLMs can produce toxic, offensive, or otherwise harmful text when prompted in certain ways, and the open-ended nature of diplomatic messaging means the space of possible outputs cannot be exhaustively validated [23].

StrategAI's content moderation approach relies on system prompt constraints rather than explicit output filtering. The base prompt instructs the LLM to maintain a tone appropriate to the game's medieval strategy setting and the leader's persona. Genghis Khan communicates with "terse, imperious" language, Cleopatra with "warm, witty" diplomacy, and Gandhi with "calm, principled" discourse. These constraints are designed to keep diplomatic exchanges within the bounds of strategic gameplay. However, this is an implicit rather than explicit moderation strategy. The system does not implement keyword filtering, toxicity classification, or output sanitization. A determined user could potentially elicit inappropriate responses through adversarial prompting of the diplomacy interface, as the LLM is not protected by a secondary moderation layer.

This represents a genuine limitation of the current system. Production game deployments incorporating LLM-generated dialogue would require dedicated content moderation infrastructure—such as OpenAI's moderation API, perspective classifiers, or regex-based filters—to catch inappropriate outputs before they reach the player. The decision not to implement such filters in StrategAI reflects the project's research and demonstration focus rather than a judgment about their necessity. For any deployment involving end users beyond the development team, content filtering would be essential.

### D. Copyright and Intellectual Property

The legal status of AI-generated content remains unsettled across jurisdictions, creating uncertainty for projects like StrategAI that depend on generative models for creative output. Three distinct intellectual property concerns intersect in this system [26].

First, the LoRA fine-tuning dataset draws from OpenGameArt, a repository of game assets released under Creative Commons licenses including CC-BY and CC-BY-SA. These licenses permit use and adaptation with attribution and, in the case of ShareAlike variants, require derivative works to carry the same license. StrategAI's training pipeline uses these images to fine-tune a diffusion model that generates new, substantially transformed outputs. Whether a diffusion model trained on CC-licensed images constitutes a derivative work under copyright law is an open question without clear legal precedent. The model does not store or reproduce training images; it learns statistical patterns that influence the distribution of generated outputs. However, the legal community has not reached consensus on whether this statistical learning constitutes fair use, and the answer may vary by jurisdiction and by the specific licenses involved.

Second, the copyright status of AI-generated images produced by the asset pipeline is unclear. Under current U.S. Copyright Office guidance, works created entirely by artificial intelligence without sufficient human creative input or intervention are not eligible for copyright protection. The StrategAI asset pipeline involves human creative choices at multiple levels—designing the four-layer prompt architecture, authoring the 88 enum-based semantic descriptions, curating the training dataset, selecting model configurations—but the actual pixel values of each generated image are determined by the diffusion model's stochastic sampling process. Whether this level of human involvement satisfies the originality requirement for copyright protection is uncertain. For game developers considering generative asset pipelines, this uncertainty represents a practical risk: assets that cannot be copyrighted cannot be exclusively licensed, potentially complicating commercial distribution.

Third, model weights carry their own licensing terms. FLUX.2 Klein 4B Distilled is released under the Apache 2.0 license, which permits both research and commercial use with minimal restrictions. This was a deliberate selection criterion, as the larger FLUX.2 Klein 9B model carries a non-commercial license incompatible with the project's goal of demonstrating commercially viable game development tools. Practitioners integrating generative models into their products should carefully evaluate model licenses, as the landscape of AI model licensing is rapidly evolving and varies substantially across providers.

### E. Reproducibility and Transparency

Reproducibility is a cornerstone of scientific research, yet generative AI systems pose significant challenges to reproducible experimentation. StrategAI addresses these challenges partially through several design decisions, though fundamental limitations remain.

The system uses `secrets.randbits(31)` for all random seed generation, producing cryptographically strong 31-bit seeds that are stored in the database alongside generated assets. This enables exact reproduction of any generated image given the same model weights and ComfyUI configuration. The LoRA training pipeline fixes random seeds across all six experiments, ensuring that any differences between configurations are attributable to the experimental variables rather than stochastic variation. The complete codebase, curated dataset, and trained LoRA weights are publicly available under open-source licenses, removing barriers to independent verification.

However, a critical reproducibility limitation stems from the LLM integration layer. GPT-4 is accessed through OpenAI's API as a service, not as a downloadable model. OpenAI periodically updates model snapshots, and these updates can change model behavior even when the same prompt and parameters are provided. An AI civilization that pursued a particular strategy in January 2026 might behave differently when tested against a June 2026 model snapshot. This means that LLM behavior reported in this paper may not be exactly reproducible by future researchers. The intent-based abstraction partially mitigates this by constraining LLM behavior to a predefined set of nine actions, limiting the surface area of potential behavioral drift. However, the specific strategic choices made within those constraints—which civilization to attack, where to found a city, what to research—are influenced by the LLM's evolving reasoning patterns and cannot be guaranteed to replicate.

The use of cloud-hosted LLM APIs also introduces an availability dependency. OpenAI's API pricing, rate limits, and model deprecation schedules are outside the project's control. To partially mitigate this, the LLM integration layer implements graceful degradation: if the API is unavailable, AI civilizations skip their turns rather than crashing the game. This ensures continued functionality but obviously changes the game experience. Future work could explore locally hosted, open-weight models (such as Llama 3 or Mistral) as drop-in replacements that would provide full reproducibility and independence from external services.

---

## X. DISCUSSION AND LIMITATIONS

### A. Architectural Trade-offs

**Microservices vs. monolith**: The microservices architecture enables independent scaling and deployment but introduces network latency and coordination complexity. For a single-developer project, a monolithic approach might have been simpler, though less flexible.

**LLM abstraction layer**: The intent-based abstraction sacrifices some flexibility (LLMs cannot directly manipulate game state) for reliability (deterministic rule enforcement). This trade-off is appropriate for rule-based games but may not suit open-ended simulations.

**Asset generation modes**: Supporting three generation modes (comfyui, static, placeholder) increases code complexity but ensures system functionality across diverse deployment scenarios. This is essential for development and testing without GPU resources.

### B. Technical Limitations

**Single-instance deployment**: The backend uses in-memory state storage, limiting deployment to a single instance. Production deployment would require database persistence and horizontal scaling.

**Synchronous asset generation**: The asset server holds HTTP connections open during generation (2-4 seconds), limiting throughput. An asynchronous job queue (Celery + Redis) would improve scalability.

**LLM cost**: GPT-4 API calls incur per-token costs (~$0.03 per AI turn at current prompt sizes). For extended gameplay, costs accumulate. Smaller models (GPT-4-mini) could reduce costs with some quality loss.

**Model size constraints**: FLUX.2 Klein 4B Distilled was selected for VRAM efficiency, but larger models (FLUX.2 Klein 9B, Stable Diffusion 3) offer superior quality. The 4B model occasionally produces artifacts or inconsistent details.

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

## XI. CONCLUSION

StrategAI demonstrates that modern generative AI technologies—Large Language Models and Diffusion Transformers—can be integrated into a cohesive, functional game system accessible to independent developers. Through careful architectural design, we address key challenges: translating LLM reasoning into deterministic game actions, maintaining visual consistency across diverse asset types, and ensuring system functionality when AI services are unavailable.

The intent-based abstraction layer enables LLMs to control game entities without direct state manipulation, leveraging language models' strategic reasoning while maintaining rule compliance. The four-layer prompt architecture provides systematic asset generation with consistent style and perspective. The three-stage leader portrait pipeline demonstrates identity preservation through carefully calibrated denoising parameters. The LoRA fine-tuning pipeline enables model adaptation to specific visual styles with minimal computational resources.

While limitations remain—single-instance deployment, synchronous generation, strategic depth—StrategAI provides a reference implementation for future projects combining multiple generative AI systems. The open-source codebase, comprehensive documentation, and extensive test suite (886 tests, ~80% coverage) offer a foundation for further research and development.

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

[23] E. M. Bender, T. Gebru, A. McMillan-Major, and S. Shmitchell, "On the dangers of stochastic parrots: Can language models be too big?," in *Proc. FAccT*, 2021, pp. 610-623.

[24] K. Crawford and T. Paglen, "Excavating AI: The politics of images in machine learning training sets," *Excavating AI*, 2019. [Online]. Available: https://excavating.ai

[25] E. Strubell, A. Ganesh, and A. McCallum, "Energy and policy considerations for deep learning in NLP," in *Proc. ACL*, 2019, pp. 3645-3650.

[26] P. Samuelson, "Generative AI meets copyright," *Science*, vol. 381, no. 6654, pp. 148-150, 2023.

[27] G. Wang et al., "Voyager: An open-ended embodied agent with large language models," in *Proc. NeurIPS*, 2023.

[28] T. Schick et al., "Toolformer: Language models can teach themselves to use tools," in *Proc. NeurIPS*, 2023.

[29] W. Peebles and S. Xie, "Scalable diffusion models with transformers," in *Proc. ICCV*, 2023.

[30] X. Liu, C. Gong, and Q. Liu, "Flow straight and fast: Learning to generate and transfer data with rectified flow," in *Proc. ICLR*, 2023.

[31] C. Lin et al., "Efficient FP8 quantization for diffusion transformer models," *arXiv preprint*, 2024.

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

Trained LoRA weights are available at: https://huggingface.co/stixxert/strategai-topdown-medieval-style-lora

---

**Acknowledgment**: This work was completed as part of the INF-3600 Generative AI course project. The authors thank the course instructors for guidance and feedback throughout development.
