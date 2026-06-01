# Finalized Report Outline: StrategAI Project Paper

> **Status**: ✅ Approved for handoff to Report Writer agent  
> **Created**: 2026-05-31  
> **Source of truth**: Verified against `backend/app/engine/`, `assetserver/src/`, `frontend/lib/`, `dataset-gen-train/`  
> **Based on**: `REPORT_PLAN.md` Phase 2 restructure, Phase 0 ground-truth audit  
> **Target**: 12–17 pages (IEEE two-column format), 5 figures, zero pseudocode/config listings

---

## Narrative Arc

```
Problem → Approach → Implementation → Results → Reflection

Game AI is brittle & scripted;           (Section 2: Introduction)
game art is expensive & manual.
    ↓
LLMs can reason strategically;           (Section 3: Related Work)
DiTs can generate visual content.
    ↓
We combine them: intent-based             (Section 4: System Overview)
abstraction + generative asset pipeline.
    ↓
How the LLM drives AI civs               (Section 5: LLM-Driven Game AI)
How the DiT generates pixel-art           (Section 6: Generative Asset Pipeline)
How we adapted the DiT with LoRA          (Section 7: LoRA Fine-Tuning)
How the frontend ties it together         (Section 8: Frontend Integration)
    ↓
Does it work? Performance, behavior,      (Section 9: Evaluation)
asset quality.
    ↓
What did we learn? Ethics, limits,        (Sections 10–12: Ethics,
next steps.                                Limitations, Conclusion)
```

---

## Finalized Structure

### Section 1 — ABSTRACT
**Pages**: ~0.3  
**Purpose**: Standalone summary for search indexing and quick comprehension.

- **1 ¶ Problem**: Strategy games rely on brittle scripted AI and costly manual art — generative AI offers an alternative but practical integration remains unexplored.
- **1 ¶ Approach**: We combined LLM-driven strategic reasoning (GPT-5.4-mini via OpenAI tool-use API) with Diffusion Transformer–based asset generation (FLUX.2 Klein 4B Distilled via ComfyUI), bridged by an intent-based abstraction layer and a four-layer prompt architecture.
- **1 ¶ Key results**: Three AI civilizations exhibit distinct strategic personas; 6 asset families generate on workstation GPUs in 2.5–7 seconds; LoRA fine-tuning on a 100-image dataset achieves consistent top-down pixel-art style; system degrades gracefully when AI services are unavailable.
- **1 ¶ Significance**: Demonstrates that multi-modal generative AI is viable for independent game development on consumer-grade hardware.
- **Index terms**: As in current report (LLMs, DiTs, Game AI, LoRA, Tool Use).

**Source files**: All claims derived from body sections below.  
**⚠️ Risk**: Performance numbers (2.5–7s) need source verification — see Risk Register.

---

### Section 2 — INTRODUCTION
**Pages**: ~1.0

#### 2.1 Motivation
- The two bottlenecks of indie game development: (a) AI behavior authoring (behavior trees/FSMs are labor-intensive and brittle), (b) asset creation (manual art is expensive; procgen lacks visual quality).
- Generative AI has matured rapidly — LLMs reason about strategy, DiTs produce high-quality images — but practical systems combining both modalities are rare.
- Existing work either uses LLMs in sandbox environments without competitive rules, or uses diffusion models for concept art rather than production-ready game assets.

**Source files**: `GAMEPLAY.md` §1–2 (game mechanics), `AGENTS.md` (project motivation), `backend/app/engine/openai_goals.py` (LLM integration), `assetserver/src/main.py` (asset pipeline entry).

#### 2.2 Problem Statement
- Can LLMs serve as autonomous strategic agents in a rule-bound competitive game?
- Can diffusion models generate consistent, production-quality pixel-art assets on workstation hardware?
- Can these two AI modalities be integrated into a cohesive, playable system with graceful degradation?

**Source files**: `docs/ARCHITECTURE.md` §1 (design principles), `backend/app/engine/intents.py` (intent abstraction).

#### 2.3 Contributions
1. **Intent-based LLM abstraction**: Decouples strategic reasoning (LLM) from tactical execution (deterministic engine) — LLM never touches `GameState` directly.
2. **Four-layer prompt architecture**: Modular prompt construction (workflow → style → semantics → assembly) for consistent cross-family asset generation.
3. **Three-stage identity-preserving leader portrait pipeline**: Calibrated img2img denoising stages maintain character consistency across splash, profile, and action views.
4. **LoRA fine-tuning methodology**: 3×2 experiment matrix evaluating caption detail × rank on a 100-image curated dataset, with style-leakage validation.
5. **Graceful degradation system**: Four-tier fallback (generative → static → placeholder → glyph/color) ensuring playability without AI services.

**Source files**: 
- (1) `backend/app/engine/intents.py`, `backend/app/engine/operations.py`, `backend/app/engine/serialize.py`
- (2) `assetserver/src/prompt_templates.py`, `config/prompt_templates.json`
- (3) `assetserver/src/leader/engine.py`, `assetserver/workflows/leader/`
- (4) `dataset-gen-train/src/`, `dataset-gen-train/config/`
- (5) `frontend/lib/hex.ts`, `frontend/lib/assetManifest.ts`

#### 2.4 Paper Organization
- One-paragraph roadmap referencing sections 3–12.

---

### Section 3 — RELATED WORK
**Pages**: ~1.0  
**Note**: Condensed from current §II (4 subsections → 3). Multi-agent systems content folded into §3.1.

#### 3.1 Game AI and Large Language Models
- Traditional approaches: behavior trees [1], FSMs [2], utility AI [3] — all require manual authoring and struggle with novel situations.
- LLM-based agents: Park et al. (generative agents in sandbox) [4], Wang et al. (Voyager in Minecraft) [25], Schick et al. (Toolformer — tool-use API) [26].
- Our differentiation: LLMs as competitive strategic agents in a rule-bound game; intent-based abstraction solves the spatial-reasoning/numerical-precision gap.

**Source files**: `backend/app/engine/openai_goals.py` (tool-use pattern), `backend/app/engine/intents.py` (intent design).

#### 3.2 Procedural Content Generation
- Classic PCG: Perlin noise [9], grammar-based structures [10], constraint solvers [11].
- Deep learning PCG: GANs for levels/textures [12] (mode collapse issues), VAEs [14] (blurry outputs).
- Diffusion models: Ho et al. [15], Rombach et al. [16], Peebles & Xie (DiT) [27], Liu et al. (rectified flow) [28].
- Gap: Most diffusion work targets concept art, not production assets with technical constraints (transparency, tiling, consistent perspective, palette limits).

**Source files**: `assetserver/docs/architecture/architecture.md`, `assetserver/src/tile/engine.py` (post-processing pipeline).

#### 3.3 Model Adaptation and LoRA
- Full fine-tuning prohibitive for diffusion models; LoRA [18] enables parameter-efficient adaptation (<1% of base parameters).
- Our contribution: systematic evaluation of caption-detail × rank interaction on FLUX.2 Klein 4B; trigger-token gating validated via style-leakage testing; deployment of adapted model into production pipeline.

**Source files**: `dataset-gen-train/docs/experiment-design.md`, `dataset-gen-train/config/`, `assetserver/config/prompt_templates.json` (trigger token usage).

---

### Section 4 — SYSTEM OVERVIEW
**Pages**: ~1.5  
**Note**: Clean 4-layer description (correcting current report's 3-layer claim). Architecture diagram at Fig. 1.

#### 4.1 High-Level Architecture
- Four components: Backend (FastAPI + game engine), Frontend (Next.js + SVG map), Asset Server (FastAPI + ComfyUI + FLUX.2 Klein 4B), Training Pipeline (Ostris AI Toolkit + LoRA).
- Inter-component data flow: Frontend mediates all communication — backend and asset server never interact directly.
- **Refer to Fig. 1**: System architecture overview (Mermaid `graph TB`).
- Four engine layers: Strategic (LLM emits intents) → Operations (intents → goals) → Tactical (pathfinding, combat) → Validator (rule enforcement, state mutation).
- Key design principle: LLM never accesses `GameState` directly — only serialized JSON views.

**Source files**: `docs/ARCHITECTURE.md` §1–2, `backend/app/engine/serialize.py`, `backend/app/engine/operations.py`, `docs/report/figures/figures.md`.

#### 4.2 Technology Choices
- **GPT-5.4-mini**: Selected for tool-use capability, 128K context window, strategic reasoning quality, API reliability. Model string from `backend/app/engine/openai_goals.py:471`.
- **FLUX.2 Klein 4B Distilled**: Selected for Apache 2.0 license, ~8.4 GB VRAM (FP8, fits workstation GPUs), 4-step distilled inference, DiT architecture with rectified flow. Four model files: DiT weights (6 GB), Qwen 3 4B text encoder (8 GB), VAE (320 MB), LoRA adapter (250 MB).
- **ComfyUI**: Node-graph workflow orchestration, HTTP/WebSocket API, community custom nodes for post-processing.
- Brief rationale table (not exhaustive — one sentence per choice).

**Source files**: `assetserver/docs/pipeline/workflow-design-justification.md`, `assetserver/src/comfyui_client.py`, `dataset-gen-train/docs/MODEL_CARD.md`.

#### 4.3 Data Flow
- **Gameplay loop**: User action → Backend API → Engine state update → LLM decision (AI turns) → State serialization → Frontend render.
- **Asset generation**: Frontend request → Asset server → ComfyUI workflow → FLUX.2 inference → Post-processing → Storage → Frontend display.
- **Model training**: Dataset curation → Caption generation → LoRA training → Evaluation → Weight deployment.

**Source files**: `backend/app/api/routers/`, `frontend/lib/api.ts`, `frontend/lib/assetApi.ts`, `assetserver/src/main.py`.

---

### Section 5 — LLM-DRIVEN GAME AI
**Pages**: ~2.5 (core contribution — largest section)  
**Note**: Zero pseudocode. Describe all concepts in prose. Refer to Fig. 2.

#### 5.1 Intent-Based Abstraction
- **The problem**: LLMs reason well about high-level strategy ("should I expand or fight?") but poorly about spatial coordinates, numerical combat formulas, and game-rule compliance.
- **The solution**: Two-layer separation — Strategic layer (LLM emits structured intents via OpenAI tool-use) → Tactical layer (deterministic Python engine resolves intents into validated actions).
- Concrete example: LLM emits `Engage(target_civ_id=2)` → Engine auto-declares war if needed, selects closest military unit via hex distance, identifies reachable enemy target, emits `MoveTo` + `Attack` goals.
- The LLM never selects unit IDs, never computes paths, never validates rules — it only expresses strategic desire.
- **Refer to Fig. 2**: Intent-based abstraction layer (Mermaid `flowchart TD`).

**Source files**: `backend/app/engine/intents.py` (intent dataclasses), `backend/app/engine/operations.py` (resolution logic), `backend/app/engine/serialize.py` (JSON view construction).

#### 5.2 Intent Types
- Table of 9 intents with 1-line descriptions (no pseudocode):
  1. **Expand** — Found a new city (engine picks settler + optimal site)
  2. **Scout** — Explore unexplored territory (engine picks unit + frontier target)
  3. **Engage** — Attack another civilization (engine auto-declares war, picks combatants)
  4. **Reinforce** — Move military units to defensive positions
  5. **Speak** — Send diplomatic message (direct text with message type)
  6. **AdjustStance** — Change diplomatic relationship (peace/war/alliance)
  7. **Build** — Queue unit production (engine validates tech prerequisites)
  8. **Research** — Select technology to research (engine validates availability)
  9. **Improve** — Construct tile improvement (engine picks worker + target tile)
- Each intent is a frozen dataclass with optional parameters — immutability guarantees thread safety.

**Source files**: `backend/app/engine/intents.py` (lines 25–104 — all 9 `@dataclass(frozen=True, slots=True)` classes + `Intent = Union[...]`).

#### 5.3 Persona System
- Three AI civilizations with distinct leader personas defined in `backend/app/api/game_factory.py`:
  - **Genghis Khan** (Mongolia): Aggressive expansionist, vindictive — "Conquest is the only true measure of a civilization."
  - **Cleopatra** (Egypt): Diplomatic opportunist — "Play factions against each other. Build a beautiful, wealthy civilization."
  - **Gandhi** (India): Peaceful developer — "Pursue victory through science and patient growth. Avoid aggression."
- Each persona is appended to a shared base prompt that defines game context, available intents, and strategic principles.
- Persona influences strategic choice distribution (Genghis favors Engage/Expand, Cleopatra favors Speak/AdjustStance, Gandhi favors Research/Build) without changing the underlying intent system.
- Include 2–3 excerpted persona prompt sentences per leader (verbatim from source) to convey voice.

**Source files**: `backend/app/api/game_factory.py` (lines 42–183, `_AI_ROSTER` tuples), `backend/app/engine/openai_goals.py` (prompt assembly), `GAMEPLAY.md` §2 (civilization roster).

#### 5.4 Memory, Context, and Error Handling
- **Rolling memory**: Last 32 intents and 32 diplomatic messages, filtered to last 8 turns — injected as `recent_actions` and `recent_messages` into each LLM call.
- **Purpose**: Avoids repeated failed strategies; enables diplomatic response continuity; maintains strategic coherence across turns.
- **Error resilience**: API failures → empty decisions (AI skips turn); invalid intents → parsed and skipped individually; missing state → graceful no-op. Temperature parameter suppressed for models that don't support it.
- **Diplomacy integration**: Free-form chat via `backend/app/engine/diplomacy.py` — LLM generates in-character replies reflecting persona voice and relationship history.

**Source files**: `backend/app/engine/openai_goals.py` (memory construction, error handling), `backend/app/engine/diplomacy.py` (diplomatic messaging).

---

### Section 6 — GENERATIVE ASSET PIPELINE
**Pages**: ~2.0  
**Note**: Describe design concepts, not ComfyUI internals. Refer to Figs. 3 and 4.

#### 6.1 Model and Infrastructure
- FLUX.2 Klein 4B Distilled: 4B-parameter DiT with rectified flow formulation, 4-step distilled sampling, Qwen 3 4B text encoder, FP8 quantization (16 GB → ~8.4 GB VRAM).
- Four model files totaling ~14.6 GB: DiT weights, text encoder, VAE, custom LoRA.
- ComfyUI as inference orchestrator: node-graph workflows, HTTP/WebSocket execution API, multi-node load balancing with health monitoring, 300s timeout, exponential-backoff retry (max 3 attempts).
- Deployment target: single workstation GPU (Blackwell RTX 6000 or RTX 3090).

**Source files**: `assetserver/docs/pipeline/workflow-design-justification.md`, `assetserver/src/comfyui_client.py`, `assetserver/src/comfyui_loadbalancer.py`, `dataset-gen-train/docs/MODEL_CARD.md`.

#### 6.2 Four-Layer Prompt Architecture
- **The problem**: Manual prompt engineering for 6 asset families × dozens of variants produces inconsistency. Need systematic, maintainable prompt construction.
- **The solution**: Four separated layers — **Refer to Fig. 3** (Mermaid `flowchart BT`):
  - **Layer 1 (Workflow)**: ComfyUI node graph, model/sampler selection, resolution, guidance — locked in version-controlled JSON.
  - **Layer 2 (Style)**: Camera framing ("top-down view."), quality tags ("Pixel art 16×16 game tile asset, crisp pixel edges"), LoRA trigger (`<tdp>`), format constraints ("Isolate on plain white background") — in `config/prompt_templates.json`.
  - **Layer 3 (Semantics)**: 19 enum classes with 88 values, hand-crafted 20–40 word prose descriptions per value — in `assetserver/src/*/prompts.py`.
  - **Layer 4 (Assembly)**: Template rendering, placeholder substitution, validation — in `assetserver/src/prompt_templates.py`.
- Separation ensures style changes edit only Layer 2, new asset types add only Layer 3.

**Source files**: `assetserver/docs/architecture/architecture.md` §3, `assetserver/src/prompt_templates.py`, `config/prompt_templates.json`, `assetserver/src/leader/prompts.py`, `assetserver/src/tile/prompts.py`.

#### 6.3 Leader Portrait Pipeline
- **The problem**: Leader portraits need consistent identity across multiple views (cinematic splash, UI profile, action scene) — single-generation approaches lose character recognizability.
- **The solution**: Three-stage img2img pipeline with calibrated denoising — **Refer to Fig. 4** (Mermaid `flowchart LR`):
  - **Stage 1 — Splash** (txt2img, 1920×1088, guidance=3.5, denoise=1.0): Establishes canonical identity; seed stored for reproducibility.
  - **Stage 2 — Profile** (img2img ← Splash, 512×512, guidance=8.0, denoise=0.90): Close-up portrait preserving facial features and attire.
  - **Stage 3 — Action** (img2img ← Splash, 1920×1088, guidance=4.5, denoise=0.85): Dramatic scene maintaining character identity.
- Denoise sweet spot: 0.85–0.90 (below 0.80 prevents composition changes; above 0.95 causes identity loss).
- 8 archetypes × 12 cultures × 6 times of day × 8 moods = rich combinatorial variety.

**Source files**: `assetserver/src/leader/engine.py`, `assetserver/src/leader/models.py` (lines 15–37: `Archetype` 8 values, `Culture` 12 values), `assetserver/workflows/leader/`, `assetserver/docs/guides/leader-prompt-guide.md`.

#### 6.4 Multi-Mode Generation and Post-Processing
- Three generation modes per asset family: **comfyui** (full AI generation), **static** (pre-generated files), **placeholder** (PIL-generated colored rectangles with labels).
- Configurable per-family mode selection — enables development without GPU, production with GPU.
- Post-processing pipeline: Lanczos resize (1024→256, preserves pixel-art edges), mild sharpening, ISNet background removal (for structures/objects/terrain/units — omitted for background tiles and leaders), atomic file writes with `os.rename`.
- 6 asset families: leader (multi-stage), structure (420 combinations from 4×7×5×3 enum dimensions), nature_object (140), terrain (75), unit (4 types), background_tile (5 types).

**Source files**: `assetserver/src/main.py` (lifespan — engine initialization per mode), `assetserver/src/config.py` (mode enum), `assetserver/src/tile/models.py` (enum dimensions), `assetserver/src/storage.py` (atomic writes).

---

### Section 7 — LORA FINE-TUNING
**Pages**: ~1.5  
**Note**: Rewrite as experimental narrative — no YAML configs, no Ostris toolkit internals. Refer to Fig. 5.

#### 7.1 Dataset and Training Setup
- 100 top-down medieval pixel-art images generated via FLUX.2 [dev] (32B teacher) + Multi-Angles LoRA v2 → knowledge distillation to FLUX.2 Klein 4B (4B student).
- Manual curation: quality filtering, diversity selection (structures ~55%, objects ~25%, terrain ~20%), resolution standardization to 1024×1024.
- Three caption detail levels for experimental comparison: **detailed** (50–100 words, architectural specifics), **minimal** (20–30 words, essential features), **ultra-minimal** (5–10 words, type + style only).
- Trigger token `<tdp>` (top-down perspective) baked into training via Ostris AI Toolkit — at inference, token + "top-down view." angle phrase activate the LoRA.

**Source files**: `dataset-gen-train/docs/DATASET_CARD.md` ⚠️ (file may be missing — verify existence), `dataset-gen-train/docs/generation.md`, `dataset-gen-train/src/`.

#### 7.2 Experiment Matrix and Methodology
- 3×2 design: caption detail (detailed / minimal / ultra-minimal) × LoRA rank (high: linear=128, conv=64 / low: linear=64, conv=32).
- Shared training config: 2500 steps, batch size 1, adamw8bit optimizer, flowmatch scheduler, checkpoints every 200 steps.
- Evaluation: 8 validation prompts (4 in-distribution medieval assets, 4 out-of-distribution modern objects) at 250-step intervals.
- Evaluation criteria: perspective consistency, style adherence, prompt fidelity, generalization to unseen types.
- **Style-leakage test**: Trigger-free prompt ("modern red sports car") — verifies the `<tdp>` token effectively gates LoRA influence.

**Source files**: `dataset-gen-train/docs/experiment-design.md`, `dataset-gen-train/config/`, `dataset-gen-train/figures/model_card_figure_7x4.png`.

#### 7.3 Results and Deployed Checkpoint
- **Refer to Fig. 5**: 2×4 grid (watchtower + boulder × base / ultra_low / minimal_high / detailed_high) — `dataset-gen-train/figures/report_figure.png`.
- **Key finding**: `detailed_high` at step 1800 achieves optimal balance — maximum in-distribution architectural fidelity (crisp crenellations, timber framing, stone masonry) with acceptable out-of-distribution generalization.
- **Ultra_low** generalizes best to unseen types but sacrifices architectural detail.
- **Base model** (no LoRA): "top-down view." text prompt alone produces unreliable perspective — confirms LoRA necessity.
- **Style leakage**: All variants produce recognizably modern sports cars without trigger token — `<tdp>` gates style effectively.
- **Training dynamics**: Under-training (<1000 steps: noisy, inconsistent), sweet spot (1500–2000 steps: peak quality), over-training (>2200 steps: memorization, palette collapse).
- **Deployed**: `detailed_high_1800.safetensors` (250 MB), strength 1.0, integrated into asset server prompt templates.

**Source files**: `dataset-gen-train/figures/report_figure.png`, `dataset-gen-train/docs/MODEL_CARD.md`, `assetserver/config/prompt_templates.json` (trigger token in templates).

---

### Section 8 — FRONTEND INTEGRATION
**Pages**: ~0.75  
**Note**: Focus on user-facing behavior and integration — not React component internals.

#### 8.1 Asset Resolution and Graceful Degradation
- The frontend maps game entities to generative assets via `frontend/lib/assetMapping.ts` and `frontend/lib/leaderMapping.ts`.
- Four-tier fallback ensures playability at every level of AI service availability:
  - **Tier 1 (generative)**: Full AI-generated pixel-art from asset server.
  - **Tier 2 (static)**: Pre-generated files from asset server filesystem.
  - **Tier 3 (placeholder)**: PIL-generated colored rectangles with text labels.
  - **Tier 4 (built-in)**: Color-coded hexagons, glyph icons (⚔ for warrior, ⌂ for settler, ↟ for archer, etc.), initial letters for leader portraits — all in `frontend/lib/hex.ts`.
- Caching: localStorage with host-tag invalidation — avoids redundant generation for repeated terrain/unit types.

**Source files**: `frontend/lib/hex.ts` (TERRAIN_COLORS, UNIT_GLYPH tables), `frontend/lib/assetManifest.ts` (resolution + fallback), `frontend/lib/assetMapping.ts` (game→asset vocabulary mapping), `GAMEPLAY.md` §1 (fallback documentation).

#### 8.2 Diplomatic Interface
- Chat-based diplomacy: free-text input with message type selection (chat, threat, offer peace, declare war, propose alliance).
- AI responses generated by LLM reflect leader persona (terse imperious for Genghis, warm witty for Cleopatra, calm principled for Gandhi).
- Relationship tracking: score (−100 hostile to +100 allied), stance indicator, message history.
- This is where the LLM integration (Section 5) and frontend (Section 8) converge — the player experiences AI personality through this interface.

**Source files**: `backend/app/engine/diplomacy.py`, `frontend/components/` (diplomacy UI components), `GAMEPLAY.md` §2 (leader personalities).

---

### Section 9 — EVALUATION
**Pages**: ~1.5  
**Note**: No test counts, no endpoint counts. Present as findings with narrative interpretation.

#### 9.1 System Performance
- **LLM decision latency**: 2–4 seconds per AI civilization per turn (GPT-5.4-mini API round-trip).
- **Asset generation latency**: 2.5–6 seconds per image on Blackwell RTX 6000; 3.5–7 seconds on RTX 3090. ⚠️ (Verify benchmark source — see Risk Register.)
- **Cache effectiveness**: ~80% hit rate in typical gameplay (repeated terrain/unit types). ⚠️ (Verify measurement — see Risk Register.)
- **Frontend rendering**: 60 FPS on 1000-tile maps with SVG optimization; <16ms for local actions.
- Interpret these numbers: workstation-grade GPUs achieve near-interactive asset generation; LLM latency is the bottleneck for turn pacing but acceptable for turn-based gameplay.

**Source files**: `assetserver/docs/pipeline/workflow-design-justification.md` ⚠️, backend API timing (measure), frontend rendering logic.

#### 9.2 AI Behavior Quality
- **Strategic diversity**: Qualitative observation confirms persona-aligned behavior — Genghis favors Engage/Expand, Cleopatra favors Speak/AdjustStance, Gandhi favors Research/Build.
- **Emergent behaviors**: Opportunistic attacks on weakened enemies, defensive alliances, technology trading, revenge behavior (Genghis remembering insults per memory system).
- **Limitations observed**: Occasional repetition of failed strategies (partially mitigated by 8-turn memory window), suboptimal city placement in edge cases, difficulty coordinating multi-unit attacks.
- **Evaluation method**: Manual playtesting observation — acknowledge this is qualitative, not quantitative. Future work should implement automated strategy-diversity metrics.

**Source files**: `backend/app/engine/openai_goals.py` (persona prompts + memory), `backend/app/api/game_factory.py` (`_AI_ROSTER`), playthrough logs.

#### 9.3 Asset Quality
- **Style consistency**: Uniform pixel-art aesthetic across 6 families; consistent color palettes; clean edges suitable for game integration.
- **Perspective adherence**: Top-down view maintained via LoRA trigger token + angle phrase; base model without LoRA fails this.
- **Identity preservation**: Leader portraits maintain facial features, attire, and recognizability across splash → profile → action stages — calibrated denoising (0.85–0.90) is the enabling technique.
- **Diversity**: 420 structure combinations, 140 object combinations, 8×12×6×8 leader variants — combinatorial variety prevents repetitive appearance.
- **Evaluation method**: Qualitative visual inspection — acknowledge lack of automated metrics (FID, CLIP score). Future work should implement quantitative evaluation.

**Source files**: `dataset-gen-train/figures/report_figure.png` (LoRA results), `assetserver/src/leader/models.py` (enum dimensions), `assetserver/src/tile/models.py` (enum dimensions).

---

### Section 10 — ETHICAL CONSIDERATIONS
**Pages**: ~1.0  
**Note**: Condense current §IX from ~3 pages to ~1 page. Keep all 4 topics but halve prose. Current §IX is well-written — selectively trim, don't rewrite from scratch.

#### 10.1 Bias in Generated Content
- Historical figure personas risk stereotyping — mitigations: persona prompts emphasize respectful framing (Genghis as strategic calculator, not barbarian; Cleopatra as intelligent diplomat, not seductress). Acknowledge fragility: persona prompts can be overridden by base-model priors.
- Dataset bias: 100-image training set dominated by European medieval architecture — non-European civilizations may receive stylistically incongruent assets. Acknowledge as limitation.

**Source files**: `backend/app/api/game_factory.py` (persona prompt text), `dataset-gen-train/docs/DATASET_CARD.md` ⚠️.

#### 10.2 Environmental Impact
- Inference energy: ~0.21–0.58 Wh per generated image (Blackwell RTX 6000, 300W TDP). Cache hit rate ~80% reduces redundant generation.
- LLM API energy is indirect (OpenAI infrastructure). Rolling memory limits token consumption growth.
- Training is inference-only for this project — dwarved by large-scale training runs. But deployment at scale accumulates.

**Source files**: `assetserver/docs/pipeline/workflow-design-justification.md` ⚠️, GPU TDP specifications.

#### 10.3 Copyright and Intellectual Property
- Training data: OpenGameArt CC-licensed images — whether LoRA weights constitute derivative work is legally unsettled.
- Generated outputs: U.S. Copyright Office guidance excludes purely AI-generated works — but StrategAI involves human creative choices at 4 prompt layers. Status uncertain.
- Model license: FLUX.2 Klein 4B is Apache 2.0 (permissive) — deliberate selection criterion over non-commercial alternatives.

**Source files**: HuggingFace model page for FLUX.2 Klein 4B, `dataset-gen-train/docs/generation.md`.

#### 10.4 Reproducibility
- Seeds: `secrets.randbits(31)` stored in database → exact image reproduction possible with same model weights.
- Training: Fixed seeds across all 6 experiments → differences attributable to variables, not stochasticity.
- Limitation: GPT-5.4-mini is a cloud API service — model snapshots change over time, so LLM behavior may not be exactly reproducible. Intent-based abstraction limits surface area of behavioral drift but doesn't eliminate it.

**Source files**: `assetserver/src/database.py` (seed storage), `dataset-gen-train/config/` (fixed seeds), `backend/app/engine/openai_goals.py` (API dependency).

---

### Section 11 — LIMITATIONS AND FUTURE WORK
**Pages**: ~0.75  
**Note**: Condense current §X. Be concrete and honest.

#### 11.1 Architectural Limitations
- Single-instance deployment (in-memory `GameStore`) — no horizontal scaling.
- Synchronous asset generation holds HTTP connections open — asynchronous job queue (Celery + Redis) would improve throughput.
- Frontend mediates all cross-service communication — adds latency but simplifies contracts.

**Source files**: `backend/app/api/store.py`, `assetserver/src/main.py` (synchronous generation endpoints).

#### 11.2 AI Limitations
- Strategic depth: LLMs excel at single-turn tactical decisions but struggle with multi-turn strategic planning ("build 3 cities, then research iron working, then attack").
- Multi-agent coordination: AI civilizations act independently — no coalition logic for coordinated attacks or multi-party alliances.
- Exploitation: Human players can exploit AI patterns despite memory system.

**Source files**: `backend/app/engine/openai_goals.py` (LLM prompt structure), playthrough observations.

#### 11.3 Future Directions
- Persistent storage (PostgreSQL) for multi-instance deployment and game continuity.
- Locally hosted open-weight models (Llama, Mistral) for reproducibility and cost independence.
- Multi-agent coalition logic for coordinated AI behavior.
- Automated quantitative evaluation metrics (FID, CLIP score, DINO similarity) for asset quality.
- Procedural narrative generation from game events.
- Expanded asset types: animations, sound effects, UI elements.

---

### Section 12 — CONCLUSION
**Pages**: ~0.5  
**Note**: Concrete, not generic. Tie back to contributions from §2.3.

- Restate the core insight: Generative AI is not just a research curiosity for game development — it's practical today on workstation hardware.
- Summarize the three key techniques: (1) Intent-based abstraction bridges the LLM→game-engine gap; (2) Four-layer prompt architecture + LoRA enables consistent, style-accurate asset generation; (3) Graceful degradation ensures the system works without AI services.
- Acknowledge limitations honestly: single-instance, synchronous generation, LLM reproducibility.
- Close with forward-looking statement: As models improve in quality and efficiency, the integration patterns demonstrated here provide a roadmap for independent developers to harness generative AI.

---

### REFERENCES
**Pages**: ~1.0  
**⚠️ Risk**: Verify all references are real and traceable. Current references [19] and [20] were previously identified as fictional and should already be removed per REPORT_PLAN.md Key Decision #6. Re-number remaining references. Key references:

[1]–[3] Game AI classics (behavior trees, FSMs, utility AI) — verify editions/dates.
[4] Park et al., "Generative Agents," UIST 2023. ✅ Real.
[15] Ho et al., "Denoising Diffusion Probabilistic Models," NeurIPS 2020. ✅ Real.
[16] Rombach et al., "High-Resolution Image Synthesis with Latent Diffusion Models," CVPR 2022. ✅ Real.
[18] Hu et al., "LoRA: Low-Rank Adaptation of Large Language Models," ICLR 2022. ✅ Real.
[21] Bender et al., "On the Dangers of Stochastic Parrots," FAccT 2021. ✅ Real.
[25] Wang et al., "Voyager," NeurIPS 2023. ✅ Real.
[26] Schick et al., "Toolformer," NeurIPS 2023. ✅ Real.
[27] Peebles & Xie, "Scalable Diffusion Models with Transformers," ICCV 2023. ✅ Real.
[28] Liu et al., "Flow Straight and Fast: Rectified Flow," ICLR 2023. ✅ Real.

**⚠️ Action for Report Writer**: Audit ALL references before finalizing. Remove any that cannot be verified against Google Scholar or equivalent.

---

## Page Budget Summary

| Section | Pages | Cumulative |
|---------|-------|------------|
| 1. Abstract | 0.3 | 0.3 |
| 2. Introduction | 1.0 | 1.3 |
| 3. Related Work | 1.0 | 2.3 |
| 4. System Overview | 1.5 | 3.8 |
| 5. LLM-Driven Game AI | 2.5 | 6.3 |
| 6. Generative Asset Pipeline | 2.0 | 8.3 |
| 7. LoRA Fine-Tuning | 1.5 | 9.8 |
| 8. Frontend Integration | 0.75 | 10.55 |
| 9. Evaluation | 1.5 | 12.05 |
| 10. Ethical Considerations | 1.0 | 13.05 |
| 11. Limitations & Future Work | 0.75 | 13.8 |
| 12. Conclusion | 0.5 | 14.3 |
| References | 1.0 | 15.3 |
| **Total** | **~15.3** | |

Within 10–20 page target. Figures occupy ~2 pages of space within section allocations.

---

## Figure Placement

| Fig | Title | Section | Source |
|-----|-------|---------|--------|
| 1 | System Architecture Overview | §4.1 | `docs/report/figures/figures.md` (Mermaid `graph TB`) |
| 2 | Intent-Based LLM Abstraction Layer | §5.1 | `docs/report/figures/figures.md` (Mermaid `flowchart TD`) |
| 3 | Four-Layer Prompt Architecture | §6.2 | `docs/report/figures/figures.md` (Mermaid `flowchart BT`) |
| 4 | Three-Stage Leader Portrait Pipeline | §6.3 | `docs/report/figures/figures.md` (Mermaid `flowchart LR`) |
| 5 | LoRA Fine-Tuning Experiment Results | §7.3 | `dataset-gen-train/figures/report_figure.png` (PNG) |

All figure captions and detailed descriptions are in `docs/report/FIGURE_DESCRIPTIONS.md`.

---

## Sections Merged or Cut

| Action | Section | Rationale |
|--------|---------|-----------|
| **Merged** | Current §II.D (Multi-Agent Systems) → §3.1 (Game AI and LLMs) | MAS content is about heterogeneous agent personas — fits naturally in the LLM game-AI discussion within Related Work. |
| **Merged** | Current §IV.F (Error Handling) → §5.4 (Memory, Context, and Error Handling) | Error handling is part of the LLM integration story, not a standalone concept. |
| **Merged** | Current §V.E (ComfyUI Integration) → §6.1 (Model and Infrastructure) | ComfyUI is infrastructure, not a separate conceptual contribution. |
| **Merged** | Current §V.F (Post-Processing) → §6.4 (Multi-Mode Generation and Post-Processing) | Post-processing is part of the pipeline, not standalone. |
| **Merged** | Current §VI.H (Deployment) → §7.3 (Results and Deployed Checkpoint) | Deployment is the conclusion of the training story, not a separate section. |
| **Merged** | Current §VII.E (Diplomatic Interface) → §8.2 (Diplomatic Interface) — kept but shortened | Diplomatic interface is a UX feature, not a major contribution — 1 paragraph. |
| **Cut** | Current §VIII.B (Test Coverage) — entirely removed | Test counts are implementation metrics, not research contributions (per REPORT_PLAN.md Key Decision #4). |
| **Cut** | Current §APPENDIX A (System Requirements) | Belongs in DEVELOPMENT.md, not an academic paper. |
| **Cut** | Current §APPENDIX B (API Endpoints) | Belongs in developer docs (API_REFERENCE.md), not an academic paper. |
| **Cut** | All pseudocode blocks (§IV.E, §VI.E, etc.) | Replaced with conceptual prose (per REPORT_PLAN.md Key Decision #3). |
| **Cut** | All config excerpts (YAML, JSON in body) | Replaced with design rationale in prose. |

---

## Risk Register: Unverifiable or At-Risk Claims

| # | Claim | Section | Risk | Mitigation | Owner |
|---|-------|---------|------|------------|-------|
| R1 | "2.5–6 seconds per image on Blackwell RTX 6000" | §6.1, §9.1 | **HIGH** — Traceability points to `assetserver/docs/pipeline/workflow-design-justification.md`. If file missing or lacks benchmarks, claim is unsubstantiated. | Before writing §6.1/§9.1, Research agent must verify this file exists and contains benchmark data. If absent, qualify: "informal benchmarks suggest…" or measure live. | Research agent |
| R2 | "3.5–7 seconds on RTX 3090" | §6.1, §9.1 | **HIGH** — Same as R1. | Same as R1. | Research agent |
| R3 | "~80% cache hit rate" | §9.1 | **MEDIUM** — No identified benchmark source. | Qualify as estimate or remove. Cache design is defensible without a specific hit-rate number. | Report Writer |
| R4 | "~$0.03 per AI turn" | (Removed) | **RESOLVED** — This claim was in current §X.B but has been cut from new outline. Cost discussion limited to qualitative mention in §11. | N/A — claim removed. | — |
| R5 | "100-image curated dataset" | §7.1 | **HIGH** — `dataset-gen-train/docs/DATASET_CARD.md` flagged as MISSING in TRACEABILITY.md. | Research agent must verify: (a) if DATASET_CARD.md now exists, or (b) count images in `dataset-gen-train/` data directory. If unverifiable, qualify as "approximately 100 images." | Research agent |
| R6 | "420 possible structure combinations" (4×7×5×3) | §6.4, §9.3 | **MEDIUM** — Enum dimensions verifiable in `assetserver/src/tile/models.py` but exact multiplication needs confirmation. | Read `StructureCategory`, `StructureStyle`, `StructureCondition`, `StructureScale` enums and multiply cardinalities. | Research agent |
| R7 | "Apache 2.0 license" for FLUX.2 Klein 4B | §4.2, §10.3 | **LOW** — Widely documented but verify on HuggingFace model page. | Quick check of HuggingFace model card. | Research agent |
| R8 | Terrain type count — 10 (engine) vs 13 (frontend display) | §6.4, §8.1 | **LOW** — Backend has 10 terrain types (`backend/app/engine/terrain.py`); frontend adds savanna/taiga/lake as display variants. | Use correct count for context: "10 terrain types in the engine; frontend adds 3 visual variants for display richness." Avoid wrong numbers. | Report Writer |
| R9 | References audit — some may be placeholder/fictional | References | **MEDIUM** — [19] and [20] already removed per REPORT_PLAN.md. Need to verify remaining 20+ references. | Research agent: verify each reference exists on Google Scholar / ACM DL / arXiv. Flag any that can't be confirmed. | Research agent |

---

## Writing Guidelines for Report Writer Agent

1. **No pseudocode, no configs, no endpoint lists** — anywhere. Describe all design choices in prose.
2. **No test counts, no line counts** — these are implementation details, not research contributions.
3. **Model names**: Use exactly `gpt-5.4-mini` and `FLUX.2 Klein 4B Distilled` (from source code).
4. **Intent names**: Use exactly Expand, Scout, Engage, Reinforce, Speak, AdjustStance, Build, Research, Improve (from `intents.py`).
5. **Asset family names**: Use leader, structure, nature_object, terrain, unit, background_tile (from asset server).
6. **Architecture layers**: Four layers — Strategic, Operations, Tactical, Validator+Engine (not three).
7. **Tech tree**: 20 technologies (not 21).
8. **Tone**: Academic but accessible to a CS graduate student. Explain concepts before diving deep.
9. **Length**: Target ~15 pages. Each subsection's page budget is a target, not a hard limit — prioritize clarity.
10. **Citations**: Every factual claim about prior work needs a citation. Every StrategAI-specific claim needs a source-file comment (not visible in final PDF) for traceability.
11. **Figures**: Reference all 5 figures in body text. Captions from `FIGURE_DESCRIPTIONS.md`.
12. **Consistency**: Use same terminology throughout (e.g., always "intent" not "action" for LLM outputs; always "asset server" not "image service").

---

## Handoff Checklist

Before the Report Writer agent begins drafting:

- [ ] **Research agent** verifies R1–R9 risks above and reports findings
- [ ] **Research agent** confirms `dataset-gen-train/docs/DATASET_CARD.md` exists or provides image count
- [ ] **Research agent** audits all references for verifiability
- [ ] **Research agent** counts enum cardinalities for structure/object/leader combinations
- [ ] **Report Writer** reads `FIGURE_DESCRIPTIONS.md` for figure captions
- [ ] **Report Writer** reads `GAMEPLAY.md` for mechanics grounding
- [ ] **Report Writer** reads `docs/ARCHITECTURE.md` for design context

---

*End of Finalized Report Outline. This document supersedes the structure proposed in REPORT_PLAN.md §2.2 and is the authoritative blueprint for the Phase 3 rewrite.*
