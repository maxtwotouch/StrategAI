# Figure Descriptions for IEEE Report

> **Source files**: Individual Mermaid diagrams are in `docs/report/figures/`. Render to individual PDFs with `./compile_figures.sh`.
> **LoRA results**: The PNG image is at `dataset-gen-train/figures/report_figure.png`, copied to `docs/report/figures/pdf/fig5_lora_results.png` for inclusion in the final PDF.

---

## Fig. 1. System Architecture Overview

**Source**: `docs/report/figures/figures.md` (Mermaid `graph TB`)

**Caption**: System architecture showing four primary components and their data flows. The frontend mediates all communication — the backend game engine and asset server never interact directly.

**What it shows**:
- Four subgraph boxes: Frontend (Next.js/React), Backend (FastAPI/Game Engine/LLM), Asset Server (ComfyUI/FLUX.2 Klein 4B), Training Pipeline (Ostris/LoRA)
- Solid arrows for live data flow (REST JSON, HTTP POST, PNG images)
- Dashed arrow for "no direct contact" between backend and asset server
- Color-coded by component

**Purpose**: Establishes the multi-service architecture context for the entire paper.

---

## Fig. 2. Intent-Based LLM Abstraction Layer

**Source**: `docs/report/figures/figures.md` (Mermaid `flowchart TD`)

**Caption**: Two-layer architecture separating strategic LLM reasoning from deterministic tactical execution. The LLM emits high-level intents; the engine resolves them into validated actions. The LLM never accesses `GameState` directly.

**What it shows**:
- **Strategic Layer** (top): LLM with system prompt, game state view, persona, rolling memory → emits structured intents
- **9 Intent Types** (middle): Expand, Scout, Engage, Reinforce, Speak, AdjustStance, Build, Research, Improve
- **Resolution Layer**: `resolve_intents()` with example transformation (Engage → DeclareWar + MoveTo + Attack)
- **Tactical Layer** (bottom): A* pathfinding, combat resolution, rule validation → updated GameState
- Color-coded by layer

**Purpose**: Demonstrates the paper's core contribution — the intent abstraction that lets LLMs reason strategically without manipulating game state directly.

---

## Fig. 3. Four-Layer Prompt Architecture

**Source**: `docs/report/figures/figures.md` (Mermaid `flowchart BT`)

**Caption**: Systematic prompt construction through four layers. Layers 1–2 (HOW) are locked in version-controlled files — no client request can override style directives. Layer 3 (WHAT) exposes a curated vocabulary of game-design concepts.

**What it shows**:
- **Layer 1** (bottom, gray): Workflow Configuration — ComfyUI node graph, model selection, sampler settings
- **Layer 2** (blue): Style Templates — camera framing, quality tags, LoRA trigger token, format constraints
- **Layer 3** (green): Semantic Descriptions — 17 enum classes, 93 values, hand-crafted 20–40 word prose
- **Layer 4** (orange): Assembly Logic — template rendering, placeholder substitution, validation
- Side annotation: Separation of Concerns (HOW vs. WHAT)

**Purpose**: Demonstrates the systematic approach to achieving consistent asset generation through modular prompt construction — a key design contribution.

---

## Fig. 4. Three-Stage Leader Portrait Pipeline

**Source**: `docs/report/figures/figures.md` (Mermaid `flowchart LR`)

**Caption**: Identity-preserving leader portrait generation through three stages with calibrated denoising parameters. Stage 1 establishes canonical identity; Stages 2–3 use img2img with the splash as reference.

**What it shows**:
- **Stage 1**: txt2img, 1920×1088, guidance=3.5, denoise=1.0 → cinematic wide shot
- **Stage 2**: img2img ← Splash, 512×512, guidance=8.0, denoise=0.90 → close-up portrait
- **Stage 3**: img2img ← Splash, 1920×1088, guidance=4.5, denoise=0.85 → action scene
- Arrows from Stage 1 to Stages 2 and 3 (reference image + seed)
- Denoise trade-off scale (0.80 too constrained, 0.85–0.90 sweet spot, 0.95+ identity loss)

**Purpose**: Demonstrates the identity preservation technique through calibrated denoising — the third core contribution.

---

## Fig. 5. LoRA Fine-Tuning Experiment Results

**Source**: `dataset-gen-train/figures/report_figure.png` (rendered PNG, not Mermaid)

**Caption**: Qualitative comparison of LoRA caption detail strategies. A 2×4 grid showing two prompt subjects (watchtower, boulder) across four conditions: base model without LoRA (unreliable perspective), ultra-minimal captions with low rank (strongest generalization), minimal captions with high rank (balanced), and detailed captions with high rank (optimal architectural fidelity — deployed variant).

**What it shows**:
- 2 rows (prompt subjects: S1 watchtower, T3 boulder)
- 4 columns (conditions: base model, ultra_low, minimal_high, detailed_high)
- The detailed_high variant at step 1800 shows best in-distribution architectural fidelity
- Base model without LoRA fails to maintain consistent top-down perspective

**Purpose**: Provides the key experimental evidence for the LoRA fine-tuning section — shows that detailed captions with high rank produce the best deployment-quality results.

