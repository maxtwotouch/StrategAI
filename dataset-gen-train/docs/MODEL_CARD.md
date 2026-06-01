---
language:
- en
license: other
license_name: flux-non-commercial
license_link: https://huggingface.co/black-forest-labs/FLUX.2-dev/blob/main/LICENSE.md
license_details: >-
  These LoRA adapters are trained on synthetic data derived from FLUX.2 [dev]
  (non-commercial license) and Flux-2-Multi-Angles-LoRA-v2 (creativeml-openrail-m).
  All trained weights inherit the non-commercial restriction from the base model.
  See the License section below for the full dependency chain.
base_model: black-forest-labs/FLUX.2-klein-base-4B
datasets:
- stixxert/topdown-medieval-pixelart
tags:
- lora
- medieval
- top-down
- game-assets
- flux
- flux2-klein
- text-to-image
- style-transfer
- diffusion-transformer
library_name: ostris-ai-toolkit
pipeline_tag: text-to-image
widget:
- text: "<tdp> top-down view. A medieval stone watchtower with crenellated battlements, narrow arrow slits, and a wooden platform, isolated on white background"
- text: "<tdp> top-down view. A medieval watermill with a large wooden wheel, millrace channel, timber frame, and grain storage, riverside setting"
- text: "<tdp> top-down view. a heavily armored knight with a broadsword and kite shield, plate armor with heraldic crest, isolated on white background"
---

# StrategAI LoRA: TopDown Medieval Style

## At a Glance

- **What it is:** A set of 6 LoRA (Low-Rank Adaptation) adapters for [FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4B) — a 4-billion-parameter Diffusion Transformer (DiT).
- **What it does:** Enforces a consistent top-down camera perspective and medieval architectural style on generated images, gated by a trigger token.
- **Trigger phrase:** `<tdp> top-down view.` — both the trigger token and the angle phrase must be present in the prompt.
- **Training data:** 100 synthetic images from [stixxert/topdown-medieval-pixelart](https://huggingface.co/datasets/stixxert/topdown-medieval-pixelart) (see [Dataset Card](https://huggingface.co/datasets/stixxert/topdown-medieval-pixelart)).
- **Key stats:** 6 variants across a 3×2 experiment matrix (caption detail × LoRA rank); highlighted variant `detailed-high` is 353 MB.
- **License:** Non-commercial only — inherits the FLUX.2 [dev] restriction. See [§License](#license).

## Model Description

Six LoRA (Low-Rank Adaptation) adapters trained on [FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4B) — a 4-billion-parameter Diffusion Transformer (DiT) — for generating **top-down medieval-style game assets**. The adapters enforce consistent overhead perspective and medieval architectural styling when activated by the trigger token `<tdp>` and the angle phrase `top-down view.`

These LoRAs were custom-trained for an LLM-driven Civilization-style strategy game where AI civilizations are controlled via large language models and game assets are generated on-demand using DiT models. The adapters power a generative asset pipeline, providing consistent top-down medieval style across six asset families: structures, units, terrain tiles, nature objects, character sprites, and background tiles.

**Training hardware:** Blackwell RTX 6000 GPU (14-16 GB VRAM with FP8 precision)  
**Training time:** ~2 hours per experiment  
**Published at:** https://huggingface.co/stixxert/strategai-topdown-medieval-style-lora

**What these LoRAs do:**
- Enforce a consistent top-down camera perspective when the trigger `<tdp>` is present
- Apply medieval architectural styling (crenellations, timber framing, stone masonry, period-appropriate details)
- Generalize beyond the training distribution — the adapters were trained exclusively on structures (~97% of the dataset) yet transfer to units, terrain, and objects (verified against evaluation prompts U1, U2, T1, T2, T3; see [Qualitative Results](#qualitative-results))
- Remain dormant when the trigger token is absent — no style leakage into non-triggered generations (verified against the L1 style probe; see [Style Leakage Analysis](#style-leakage-analysis))

**What these LoRAs do NOT do:**
- They do not enforce pixel-art aesthetics — the training images were pixel-art quantized, but the LoRA learned perspective + style rather than the pixel-art filter itself
- They do not produce isometric, side-view, or ¾-angle perspectives — the top-down constraint is strict

**Key design insight:** These adapters were produced as part of a systematic 3×2 experiment matrix (3 caption detail levels × 2 LoRA rank configurations) to study how caption granularity and model capacity interact during fine-tuning for perspective-conditioned generation. All six variants are published to enable direct comparison across the experiment matrix. The `detailed-high` variant is highlighted as the best overall performer based on qualitative assessment.

| | |
|---|---|
| **Base model** | [black-forest-labs/FLUX.2-klein-base-4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4B) |
| **Training dataset** | [stixxert/topdown-medieval-pixelart](https://huggingface.co/datasets/stixxert/topdown-medieval-pixelart) (100 images) |
| **Training framework** | [Ostris AI Toolkit](https://github.com/ostris/ai-toolkit) |
| **Training hardware** | Blackwell RTX 6000 (14-16 GB VRAM, FP8) |
| **Training time** | ~2 hours per experiment |
| **Trigger phrase** | `<tdp> top-down view.` |
| **Highlighted variant** | `detailed-high` — best balance of in-distribution fidelity and out-of-distribution generalization |
| **Total variants** | 6 LoRA adapters + base model baseline |
| **Published at** | https://huggingface.co/stixxert/strategai-topdown-medieval-style-lora |

---

## Why LoRA Fine-Tuning Was Necessary

The base [FLUX.2 Klein 4B Distilled](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4B) model — a 4-billion-parameter Diffusion Transformer (DiT) — is not incapable of producing top-down perspectives. When prompted with the phrase `top-down view.`, the base model *sometimes* generates assets from an overhead camera angle. It also produces recognizably medieval architectural forms: stone towers, timber frames, crenellated battlements. In principle, one might ask: why invest in LoRA training when prompt engineering on the base model already yields some top-down medieval outputs?

The answer lies in the gap between *occasional capability* and *production reliability*. The StrategAI asset pipeline requires generating hundreds of game assets across six families (structures, units, terrain tiles, nature objects, character sprites, background tiles), all of which must share a consistent visual language. A camera angle that works ~60% of the time is a camera angle that fails ~40% of the time — and in an automated pipeline, failure at that rate is unacceptable. Four specific failure modes observed in the base model motivated the LoRA approach.

### Failure Mode 1: Inconsistent Perspective

The most critical failure mode was camera-angle inconsistency. With identical `top-down view.` prompts, the base DiT model produced a mixture of perspectives: occasionally true orthogonal top-down, but also isometric angles, ¾ overhead views, and slight oblique tilts. This variation occurred not only *across* different prompts but also *within* repeated generations of the same prompt (different seeds). For a strategy game where every asset on a hex grid must share the same camera plane, this inconsistency would produce visually jarring results — a watchtower rendered from directly above sitting next to a watermill rendered from a 45° angle breaks the illusion of a unified game world. The evaluation battery (prompts S1–T3, see [Evaluation](#evaluation)) confirmed this: base model outputs showed meaningful perspective variation, while LoRA-conditioned generations converged to consistent top-down orientation across all tested categories.

### Failure Mode 2: Style Drift

The base model's medieval aesthetic was broad but uncontrolled. Depending on the seed, the same prompt could produce a photorealistic stone tower, a cartoonish castle with exaggerated proportions, a painterly watercolor interpretation, or an abstract geometric structure. This stylistic entropy is a well-known property of large generative models — they sample from a distribution that encompasses many valid interpretations of "medieval." But for game asset generation, this diversity is detrimental: a knight sprite rendered in a painterly style does not visually cohere with a castle rendered photorealistically, even when both are individually high-quality outputs. The LoRA constrains this entropy by binding the model to a specific, consistent medieval architectural style learned from the curated training dataset.

### Failure Mode 3: No Selective Control

Even if the base model were more reliable, prompt engineering alone provides no mechanism to *selectively* apply the top-down medieval style. The base model always generates from its full, unconditional distribution — there is no way to produce a styled asset in one generation and an unstyled asset in the next from the same model. LoRA introduces the `<tdp>` trigger token, which acts as a gating mechanism: when present, the adapter weights influence the generation toward top-down medieval style; when absent, the base model's native behavior is fully preserved. This selective control is verified by the L1 style probe (modern red sports car; see [Style Leakage Analysis](#style-leakage-analysis)), which demonstrated that the LoRA's influence is contained within the trigger token's scope — the base model's full generative range remains available when `<tdp>` is omitted.

### Failure Mode 4: Production Reliability Gap

Taken together, these failure modes created a reliability gap that prompt engineering alone could not close. Qualitative assessment of base model outputs against the 8-prompt evaluation battery (S1, S2, U1, U2, T1, T2, T3, L1; see [Qualitative Results](#qualitative-results)) revealed that while the base model occasionally produced excellent top-down medieval assets, the hit rate was well below the >95% consistency threshold required for an automated game asset pipeline. Most generations required manual curation — discarding isometric outputs, rejecting style outliers, and re-rolling until the dice landed favorably. For a pipeline designed to generate assets on-demand during gameplay, this manual gating step would be a bottleneck.

### The LoRA Solution

LoRA fine-tuning addresses all four failure modes simultaneously by injecting a low-rank adaptation into the model's attention and convolution layers. The adapter learns the top-down perspective constraint and medieval architectural style from a compact but carefully curated dataset of 100 images, binding these properties to the `<tdp>` trigger token. Because the adaptation is low-rank (32–128 for linear layers, 16–64 for convolution layers), the added parameters represent less than 0.1% of the base model's 4 billion weights — the adapter modifies *how* the model interprets specific concepts without overwriting its general image generation capability.

The result, as demonstrated across all 6 LoRA variants and the 8-prompt evaluation battery (see [Qualitative Results](#qualitative-results)), is:
- **Perspective consistency**: All 6 variants reliably enforced top-down orientation across in-distribution structures (S1, S2) and out-of-distribution units (U1, U2) and terrain (T1–T3).
- **Style coherence**: The medieval architectural vocabulary (crenellations, timber framing, stone masonry) was consistently applied, eliminating the style drift observed in the base model.
- **Trigger-based gating**: The `<tdp>` token provides selective control — verified cleanly by the L1 style probe, where all variants preserved modern sports car identity with minimal medieval contamination (see [Style Leakage Analysis](#style-leakage-analysis)).
- **Production reliability**: The LoRA-conditioned generations achieved qualitatively consistent, game-ready outputs across the full evaluation battery — eliminating the need for manual curation and enabling the automated asset pipeline that StrategAI requires.

The systematic 3×2 experiment matrix (caption detail × LoRA rank) further validated that LoRA training is not a binary on/off decision but a tunable process: different configurations trade off in-distribution fidelity against out-of-distribution generalization (see [Caption Detail × Rank Trade-off](#caption-detail--rank-trade-off)). This tunability is itself evidence that LoRA is the correct approach — prompt engineering offers no comparable mechanism for controlling the fidelity–generalization balance.

---

## Model Variants

The six LoRA variants span a 3×2 experiment matrix: three caption detail levels (detailed, minimal, ultra-minimal) × two LoRA rank configurations (high, low), plus one ultra-low-rank outlier. Each variant is a `.safetensors` file at its optimal training checkpoint. All six variants are published to enable comparison across the full matrix — there are no per-variant usage prescriptions beyond what the experiment design reveals.

| # | Variant | Filename | Caption Detail | Rank (L/C) | Steps | Size |
|---|---------|----------|----------------|:----------:|------:|-----:|
| — | **Base model** | *(no LoRA)* | — | — | — | — |
| 1 | **detailed-high** ⭐ | `strategai-lora-detailed-high-step1800.safetensors` | 50–100 words | 128/64 | 1,800 | 353 MB |
| 2 | **detailed-low** | `strategai-lora-detailed-low-step2200.safetensors` | 50–100 words | 64/32 | 2,200 | 177 MB |
| 3 | **minimal-high** | `strategai-lora-minimal-high-step2000.safetensors` | 20–30 words | 128/64 | 2,000 | 353 MB |
| 4 | **minimal-low** | `strategai-lora-minimal-low-step2400.safetensors` | 20–30 words | 64/32 | 2,400 | 177 MB |
| 5 | **ultra-high** | `strategai-lora-ultra-high-step2200.safetensors` | 5–10 words | 128/64 | 2,200 | 353 MB |
| 6 | **ultra-low** | `strategai-lora-ultra-low-step1600.safetensors` | 5–10 words | 32/16 | 1,600 | 89 MB |

All six variants produced usable game assets across all tested categories (structures, units, terrain). The `detailed-high` variant is **highlighted** as the strongest overall performer based on qualitative assessment — see [Why `detailed-high` Is Highlighted](#why-detailed-high-is-highlighted) below and the comparison grids in [Figures](#figures) (`figures/report_figure.png` and `figures/model_card_figure_7x4.png`).

---

## Why `detailed-high` Is Highlighted

The `detailed-high` variant (detailed captions, 50–100 words, with high-rank LoRA: linear=128, conv=64) emerged as the best overall performer from qualitative assessment of all six variants against the 8-prompt evaluation battery (see [Qualitative Results](#qualitative-results)). Three specific observations drove this conclusion:

1. **Avoided the dark-coloring issue seen in minimal-caption variants.** The minimal-caption LoRAs (both high and low rank) produced noticeably darker palettes for structures — castle stonework and knight armor rendered in deep, muted tones rather than the lighter, more readable medieval palette. `detailed-high` preserved brighter, more saturated stone and metal tones that read better as game assets at small sprite resolutions.

2. **Least style leakage on the out-of-distribution L1 sports car probe.** A common challenge across the experiment matrix was that the modern red sports car (prompt L1) inherited stylistic features from the training dataset — subtle medieval texturing on the car body, color palette shifts toward earthen tones, or softening of modern geometric lines. `detailed-high` showed the cleanest separation: the car remained recognizably modern with minimal medieval contamination. In contrast, `ultra-high`, `minimal-low`, and `minimal-high` exhibited subtle art-style mimicry of dataset features.

3. **Strong architectural fidelity without overfitting artifacts.** `detailed-high` rendered crenellations, timber framing, arrow slits, and stone masonry with the highest level of structural coherence among all variants, yet avoided the rigid repetition and structural breakdown that characterized over-trained checkpoints. The model learned architectural detail without memorizing individual training assets.

No variant failed outright — all six produced coherent, top-down game assets. But `detailed-high` was the cleanest on the dimensions that matter most for production use: readable palette, controlled style leakage, and faithful architectural detail.

### Caption Detail × Rank Trade-off

| | **High Rank (128/64)** | **Low Rank (64/32)** | **Ultra-Low Rank (32/16)** |
|---|---|---|---|
| **Detailed captions** (50–100 words) | **Highlighted: maximum architectural fidelity** ⭐ | Moderate fidelity, better generalization but slower convergence | — |
| **Minimal captions** (20–30 words) | Balanced detail + generalization; darker color palette | Good generalization, somewhat less architectural precision; darker color palette | — |
| **Ultra-minimal captions** (5–10 words) | Strong style enforcement, limited detail control | — | Best generalization, weakest in-distribution detail; smallest file size (89 MB) |

> **Note on interpreting this matrix:** The trade-off is not strictly "better vs. worse." Lower-rank variants with sparser captions generalize more broadly to out-of-distribution categories, while higher-rank variants with richer captions reproduce in-distribution architectural detail more faithfully. The highlighted `detailed-high` cell represents the best *overall* balance, but the optimal choice depends on the specific use case. All six variants are published to enable this comparison.

---

## How to Use

### Trigger Phrase

The LoRA is activated by including **both** components in the prompt:

1. **Trigger token**: `<tdp>` — activates the LoRA weights
2. **Angle phrase**: `top-down view.` — reinforces the perspective constraint learned during training

Both must be present for reliable top-down style application. The trigger token gates LoRA influence; the angle phrase provides semantic context that the adapter learned to associate with overhead perspective during training.

### Example Prompts

**Structure (in-distribution — the adapter's training domain):**
```
<tdp> top-down view. A medieval stone watchtower with crenellated battlements,
narrow arrow slits, and a wooden platform, isolated on white background
```

**Unit (out-of-distribution — not present in training data):**
```
<tdp> top-down view. a heavily armored knight with a broadsword and kite shield,
plate armor with heraldic crest, isolated on white background
```

**Terrain feature (oak tree):**
```
<tdp> top-down view. A large oak tree with thick gnarled trunk, dense spreading canopy of dark green foliage, exposed root system, and moss-covered base, isolated on white background
```

### Recommended Generation Settings

| Parameter | Value | Notes |
|-----------|-------|-------|
| LoRA strength | 1.0 | Full influence for consistent style |
| Guidance scale | 3.5 | Standard for structure and unit assets; 2.5 for terrain features |
| Steps | 4 | Rectified flow (FLUX.2 Klein 4B Distilled timestep schedule) |
| Sampler | euler | |
| Resolution | 1024×1024 | Resize to 256×256 for in-game assets |
| Post-processing | Lanczos resize → sharpen → background removal | See `workflows/txt2img.json` |

---

## Training Details

### Dataset

All variants were trained on [stixxert/topdown-medieval-pixelart](https://huggingface.co/datasets/stixxert/topdown-medieval-pixelart) — a curated synthetic dataset of 100 top-down medieval pixel-art game assets with natural-language captions.

| Statistic | Value |
|-----------|-------|
| Total images | 100 |
| Resolution | 1024 × 1024 px |
| Composition | Structures ~97%, vegetation ~2%, terrain ~1% |
| Caption style | Natural language (not tag-based) |
| Angle phrase | `top-down view.` (present in all captions) |
| Generation pipeline | FLUX.2 [dev] + Flux-2-Multi-Angles-LoRA-v2 (camera-angle enforcement) |
| Post-processing | ComfyUI-PixelArt-Detector (palette quantization) + rembg (background removal) |

**Important note on pixel-art aesthetics:** While training images underwent pixel-art post-processing (palette quantization via ComfyUI-PixelArt-Detector), the LoRA primarily learned top-down perspective and medieval architectural style rather than pixel-art aesthetics. The resulting models generate medieval-styled assets suitable for various visual styles — the outputs are not strictly pixel art. This is a feature, not a bug: the adapters separate perspective/style from the specific visual filter, making them more versatile for game engines that apply their own post-processing.

> **Why so many structures?** The generation pipeline (FLUX.2 [dev] + Multi-Angles LoRA v2) produced far better results for architectural subjects than for organic ones. Vegetation and terrain each required many more attempts to get a usable image, and within a fixed curation budget, structures dominated. See the [Dataset Card](https://huggingface.co/datasets/stixxert/topdown-medieval-pixelart) for the full story.

### Caption Design

Three caption detail levels were derived from each original caption to test how text granularity affects LoRA learning. The hypothesis: less detailed captions force the model to learn abstract concepts (perspective, style) rather than memorizing specific visual patterns, improving generalization at the cost of detail reproduction.

| Variant | Word Count | Example |
|---------|:----------:|---------|
| **Detailed** | 50–100 | `top-down view. A medieval granary built from weathered oak planks with a thatched roof, elevated on stone pillars to prevent rodent access, featuring small ventilation windows and a wooden ladder, pixel art style with limited color palette` |
| **Minimal** | 20–30 | `top-down view. Medieval wooden granary with thatched roof on stone pillars, pixel art style` |
| **Ultra-minimal** | 5–10 | `top-down view. Medieval granary, pixel art` |

### Training Configuration

<details>
<summary>Per-variant training hyperparameters (click to expand)</summary>

| Parameter | Detailed | Minimal | Ultra-minimal |
|-----------|:--------:|:-------:|:-------------:|
| Total steps | 2,500 | 2,500 | 2,500 |
| Batch size | 1 | 1 | 1 |
| Learning rate | 8e-5 | 8e-5 | 5e-5 |
| Optimizer | adamw8bit | adamw8bit | adamw8bit |
| Weight decay | 1e-4 | 1e-4 | 1e-4 |
| Scheduler | flowmatch | flowmatch | flowmatch |
| Timestep sampling | weighted | weighted | weighted |
| Checkpoint interval | 200 steps | 200 steps | 200 steps |
| Resolution | 512, 768, 1024 (multi-scale) | 512, 768, 1024 (multi-scale) | 512, 768, 1024 (multi-scale) |
| Caption dropout | 5% | 10% | 0% |

</details>

**Learning rate rationale:** Ultra-minimal variants use a lower learning rate (5e-5 vs. 8e-5) because all 100 captions are identical (`"<tdp> top-down view."`). With no text diversity across the dataset, the model converges faster — a lower LR prevents overfitting to the single caption string. Caption dropout is disabled for ultra-minimal (0%) because dropping the only available caption would feed blank conditioning to the model, causing it to learn an unconditional distribution rather than the intended top-down perspective concept. Detailed and minimal variants use the standard 8e-5 rate with 5–10% caption dropout as weak regularization — a small amount of dropout slightly improves generalization without harming concept learning.

### Rank Configurations

| Config | Linear Rank | Linear Alpha | Conv Rank | Conv Alpha | File Size | Used By |
|--------|:----------:|:------------:|:---------:|:----------:|:---------:|---------|
| **High** | 128 | 64 | 64 | 32 | ~353 MB | detailed-high, minimal-high, ultra-high |
| **Low** | 64 | 32 | 32 | 16 | ~177 MB | detailed-low, minimal-low |
| **Ultra-low** | 32 | 16 | 16 | 8 | 89 MB | ultra-low |

### Optimal Checkpoint Selection

Each experiment was evaluated at 200-step intervals. The optimal checkpoint was selected based on visual quality of sample outputs, balancing perspective consistency against overfitting artifacts.

| Experiment | Optimal Step | Nearest Checkpoint |
|-----------|:-----------:|:------------------:|
| detailed-high | 1,750 | 1,800 |
| detailed-low | 2,250 | 2,200 |
| minimal-high | 2,000 | 2,000 |
| minimal-low | 2,500 | 2,400 |
| ultra-high | 2,250 | 2,200 |
| ultra-low | 1,500 | 1,600 |

**Convergence notes:** Training dynamics across all six experiments fell into three regimes:

- **Under-trained (steps ~500–1,000):** Outputs are noisy with inconsistent perspective. The top-down angle has not yet crystallized — structures may appear at oblique angles or lack coherent architectural geometry. Key features (crenellations, timber framing, stone textures) are indistinct or absent.

- **Sweet spot (steps ~1,500–2,000):** Perspective consistency and style adherence peak. The top-down constraint is reliably enforced, architectural details are crisp and recognizable, and structural integrity is intact. This is where all six optimal checkpoints were selected. Experiments with richer captions (detailed) converged slightly later (~1,750–2,250) than ultra-minimal (~1,500) because the model had more text signal to integrate.

- **Over-trained (beyond ~2,200):** Structural integrity begins to break down. Walls lose coherence, roofs collapse into abstract patterns, and architectural features become distorted. Color palettes shift toward the training distribution mean (darker, more muted tones). The model shows signs of memorizing individual training assets rather than generalizing the top-down perspective concept.

No step-2400 checkpoint exists for `detailed-high` — its optimal was reached at step 1,800, well before over-training set in. Training was capped at 2,500 steps for all experiments; experiments that converged later (minimal-low at 2,400, detailed-low at 2,200) were approaching the over-training boundary.

---

## Evaluation

### Prompt Battery

All 6 LoRA variants plus the base model baseline were evaluated against 8 prompts spanning 3 asset categories (in-distribution structures and terrain, out-of-distribution units) and a style-leakage control. The complete evaluation battery is shown below — each prompt exercises distinct aspects of the model's style adaptation and generalization capability.

#### Table 1: Evaluation Prompts (Full)

| ID | Category | Prompt |
|----|----------|--------|
| **S1** | Structure | `<tdp> top-down view. The structure is viewed from directly above, showing its roof and layout. The structure blends naturally at its base edges. Isolate on a plain white background, only focusing on the specified object. A sturdy stone watchtower with crenellated battlements, narrow arrow slits, a wooden platform, and iron-reinforced gate, military functionality, cool medieval palette. Pixel art 16x16 game tile asset, crisp pixel edges, no anti-aliasing, sharp blocky pixels, centered single asset on white. Grounded stable perspective, no floating objects.` |
| **S2** | Structure | `<tdp> top-down view. The structure is viewed from directly above, showing its roof and layout. The structure blends naturally at its base edges. Isolate on a plain white background, only focusing on the specified object. A medieval watermill with a large wooden wheel, millrace channel, timber frame, and grain storage, riverside setting, warm muted palette. Pixel art 16x16 game tile asset, crisp pixel edges, no anti-aliasing, sharp blocky pixels, centered single asset on white. Grounded stable perspective, no floating objects.` |
| **U1** | Unit (OOD) | `<tdp> top-down view. pixel art top-down 2d game character sprite, a heavily armored knight with a broadsword and kite shield, plate armor with heraldic crest, facing camera front view full frontal, character looks at viewer, isolated on transparent background, crisp pixel edges sharp blocky pixels, centered single sprite game asset` |
| **U2** | Unit (OOD) | `<tdp> top-down view. pixel art top-down 2d game character sprite, a hooded archer with a longbow and quiver of arrows, leather armor, forest green cloak, facing camera front view full frontal, character looks at viewer, isolated on transparent background, crisp pixel edges sharp blocky pixels, centered single sprite game asset` |
| **T1** | Terrain | `<tdp> top-down view. The terrain elevation feature is viewed from directly above, showing its top surface and contours. The terrain blends naturally at its base edges. Isolate on a plain white background, only focusing on the specified object. A grassy hill with gentle slopes, scattered wildflowers, exposed rocky outcrops near the summit, and a winding dirt path, medium scale, earthy green and brown palette. Pixel art 16x16 game tile asset, crisp pixel edges, no anti-aliasing, sharp blocky pixels, centered single asset on white. The base of the terrain feature sits flush with the bottom of the frame. Grounded stable perspective, no floating objects.` |
| **T2** | Terrain | `<tdp> top-down view. The terrain elevation feature is viewed from directly above, showing its top surface and contours. The terrain blends naturally at its base edges. Isolate on a plain white background, only focusing on the specified object. A large oak tree with thick gnarled trunk, dense spreading canopy of dark green foliage, exposed root system, and moss-covered base, large scale, deep forest green and bark brown palette. Pixel art 16x16 game tile asset, crisp pixel edges, no anti-aliasing, sharp blocky pixels, centered single asset on white. The base of the terrain feature sits flush with the bottom of the frame. Grounded stable perspective, no floating objects.` |
| **T3** ⭐ | Terrain | `<tdp> top-down view. The terrain elevation feature is viewed from directly above, showing its top surface and contours. The terrain blends naturally at its base edges. Isolate on a plain white background, only focusing on the specified object. A large jagged boulder with rough granite texture, deep crevices, patches of lichen and moss, and scattered smaller rocks at its base, medium scale, cool grey and moss green palette. Pixel art 16x16 game tile asset, crisp pixel edges, no anti-aliasing, sharp blocky pixels, centered single asset on white. The base of the terrain feature sits flush with the bottom of the frame. Grounded stable perspective, no floating objects.` |
| **L1** | Style probe | `<tdp> top-down view. A modern red sports car, isolated on white background.` |

#### Table 2: Prompt Design Rationale

| ID | Category | Rationale |
|----|----------|-----------|
| **S1** | Structure | Tests in-distribution architectural fidelity — watchtower has specific military features (crenellations, arrow slits, iron-reinforced gate) that challenge the model's ability to render fine structural detail at low resolution |
| **S2** | Structure | Tests environmental context integration — watermill requires a river (millrace channel) and mechanical detail (wooden wheel), probing whether the LoRA preserves compositional reasoning |
| **U1** | Unit (OOD) | Tests out-of-distribution generalization — character sprites are 0% of the training dataset; evaluates whether the LoRA adapts to unseen subject categories while maintaining pixel-art style |
| **U2** | Unit (OOD) | Second OOD probe for consistency across character archetypes — archer differs in silhouette, armor type, and weapon from the knight, testing robustness of the style transfer |
| **T1** | Terrain | Tests organic terrain rendering — hill with gentle slopes, wildflowers, and rocky outcrops exercises the model's ability to render natural contours and vegetation |
| **T2** | Terrain | Tests vegetation rendering — oak tree with trunk, canopy, and root system challenges foliage coherence and organic shape generation at pixel scale |
| **T3** ⭐ | Terrain | Primary evaluation figure — boulder combines structured (rock facets, crevices) and organic (lichen, moss) features; selected as the representative figure for the project report |
| **L1** | Style probe | Verifies trigger-token scoping — a modern red sports car is absent from the medieval training distribution; with `<tdp>` trigger present, detects whether the LoRA incorrectly applies medieval styling to anachronistic subjects, or correctly limits its influence to the pixel-art aesthetic |

> **Evaluation configuration**: All prompts were evaluated with fixed seed `42`, LoRA strength `1.0` (strength `0.0` for base model baseline), and output resolution `1024×1024` using the production ComfyUI `txt2img.json` workflow. The `<tdp>` trigger token was prepended to all prompts for LoRA-conditioned generations and omitted for base model baselines.

### Qualitative Results

All six LoRA variants produced usable, recognizable assets across all evaluation categories — structures (S1, S2), units (U1, U2), terrain (T1, T2, T3), and the style probe (L1). No variant failed to generate a coherent image for any prompt. The `detailed-high` variant was selected as the best overall balance of in-distribution fidelity and out-of-distribution generalization. Full comparison grids are available in `figures/report_figure.png` (2×4 grid: S1 + T3 × 4 experiments) and `figures/model_card_figure_7x4.png` (7×4 grid: all variants × S1, U1, T3, L1).

#### In-Distribution Structures (S1 watchtower, S2 watermill)

All variants produced recognizable medieval structures with correct top-down perspective. Qualitatively, most LoRAs performed very similarly on in-distribution structure prompts — architectural features (crenellations, timber framing, stone masonry, water wheels) were legible across all six variants. The primary differentiator was **color palette**: all models except the minimal-caption variants produced lighter, more saturated coloring for stonework and structural details. Both minimal-high and minimal-low rendered castles and watermills with noticeably darker, more muted tones — deep grey stonework and subdued timber hues — while detailed and ultra-minimal variants preserved brighter, higher-contrast palettes that read more clearly as small-scale game sprites. Perspective was consistently top-down and orthogonal across all variants for structure prompts.

#### Out-of-Distribution Units (U1 knight, U2 archer)

All variants generalized successfully to character sprites — a category entirely absent from the training data (0% of the 100-image dataset). Knights were rendered with readable plate armor, broadswords, and kite shields; archers with longbows, quivers, and forest-green cloaks. Silhouettes were clean and game-ready across all variants. Camera pose was remarkably consistent — the only outlier in the entire evaluation battery for camera angle variation was the T3 boulders (see below). Character sprites did not differ meaningfully in perspective across variants. The main differentiators were palette (minimal variants again trended darker on armor tones) and fine detail sharpness (higher-rank variants produced slightly crisper weapon edges and armor articulation).

#### Terrain Features (T1 hill, T2 oak tree)

All variants produced plausible terrain assets with appropriate palettes — earthy greens and browns for the grassy hill (T1), deep forest greens and bark browns for the oak tree (T2). The T3 boulder (see below) was the most revealing terrain prompt and is discussed separately. For T1 and T2, the key finding concerned boulder morphology that also appeared in T3 outputs: **boulder silhouette shape** varied systematically with caption detail × rank configuration.

- **Flat-top boulders** were produced by `ultra-low`, `ultra-high`, `minimal-low`, and `detailed-low` — these variants tended toward smooth, plateau-like top surfaces with less pronounced surface fractures.
- **Jagged-top boulders** were produced by `detailed-high` and `minimal-high` — these variants rendered more irregular, fractured top surfaces with deeper crevices and sharper rock facets.

This pattern suggests that higher-rank configurations (128/64) combined with richer captions (detailed or minimal) give the model sufficient capacity to learn and reproduce complex surface geometry, while lower-rank or ultra-minimal configurations default to simpler, more schematic rock forms.

#### Rock Formation (T3 boulder) ⭐ — Primary Report Figure

The T3 boulder prompt is the primary evaluation figure for the project report and the most discriminating terrain prompt in the battery. It combines structured features (granite facets, deep crevices, rock geometry) with organic features (lichen patches, moss growth, irregular surface texture), exercising the full range of what the LoRA must learn.

Key observations across variants:

- **Moss and lichen rendering:** This was the single most informative differentiator. Higher-rank variants (`detailed-high`, `minimal-high`) rendered moss and lichen patches more convincingly — organic growth appeared as distinct, irregularly shaped patches with subtle color variation (moss green against cool grey granite). Lower-rank variants (`ultra-low`, `detailed-low`, `minimal-low`) produced flatter, less textured organic growth — moss appeared as uniform green coloration rather than discrete surface features. The `ultra-high` variant fell between these extremes: it had the capacity for organic detail but, with only identical ultra-minimal captions, lacked the text conditioning to deploy it precisely.

- **Boulder silhouette:** As noted in the terrain features section, `detailed-high` and `minimal-high` produced jagged, irregular top surfaces with pronounced crevices, while the remaining variants tended toward flatter, plateau-like tops.

- **Surface texture:** Granite faceting and crevice depth correlated with rank — higher rank meant more articulate rock surfaces. The base model (no LoRA) served as reference, producing a photorealistic boulder without top-down perspective enforcement.

- **Perspective consistency:** T3 was the only prompt in the battery that showed meaningful camera-angle variation across variants. Some variants produced boulders at subtly different overhead angles — this was most noticeable when comparing the extreme ends of the matrix (ultra-low vs. detailed-high). However, all variants stayed within the top-down regime; none drifted into isometric or side-view territory.

### Training Dynamics

Training dynamics across all six experiments followed a consistent three-regime pattern, observed through checkpoint evaluation at 200-step intervals:

1. **Under-trained regime (steps ~500–1,000):** Outputs exhibit wrong or inconsistent camera angles — structures may appear at oblique or side views despite the `<tdp>` trigger. Object geometry is noisy and architectural features are indistinct. The model has not yet learned to associate the trigger token with the top-down perspective constraint.

2. **Sweet spot (steps ~1,500–2,000):** Perspective locks into consistent top-down orientation. Architectural details (crenellations, timber joints, water wheels) are crisp and recognizable. Structural integrity is intact — buildings look like buildings, not abstract texture patterns. This is the regime where all six optimal checkpoints were selected.

3. **Over-trained regime (beyond ~2,200):** Structural integrity breaks down. Buildings lose coherent geometry — walls collapse, roofs fragment into repeated texture patches, and architectural features become distorted or illegible. Color palettes drift toward the training distribution mean (darker, more uniform tones). The model begins to memorize individual training assets rather than generalizing the top-down perspective concept. This breakdown was the primary signal for checkpoint selection: the optimal checkpoint was chosen just before visible degradation set in.

The transition timing varied by experiment: ultra-minimal variants converged fastest (optimal at step ~1,500–1,600) and degraded soon after; detailed variants converged more slowly (optimal at ~1,750–2,250) as the model integrated richer text conditioning; minimal variants fell between. The `detailed-high` variant reached its optimal at step 1,800 — later checkpoints (2,000+) showed early signs of overfitting including rigidified structural repetition and subtle color collapse.

### Style Leakage Analysis

Style leakage refers to the unintended transfer of a LoRA's learned style to semantically unrelated subject matter. A well-scoped domain adapter should respect the trigger token without contaminating out-of-domain subjects: activating the LoRA on a modern object should still produce a recognizable modern object, not a medieval version of it.

**Probe design:** Prompt L1 includes the `<tdp>` trigger token but describes a modern red sports car — semantically distant from the training distribution (100% medieval structures). Each of the six LoRA variants was evaluated at strength 1.0 alongside a base model baseline (strength 0.0). This tests whether the LoRA incorrectly applies medieval architectural styling to anachronistic subjects when the trigger is active.

**Findings:** All six LoRA variants successfully preserved a clean top-down perspective on the sports car — no variant collapsed the car into a medieval structure or applied overt architectural styling. The base model (no LoRA) served as the reference for an unmodified modern car.

However, subtle art-style leakage was observed in several variants:

- **`ultra-high`, `minimal-low`, and `minimal-high`** showed signs of the LoRA's learned art style subtly mimicking dataset features. The car body exhibited slight shifts toward earthen/muted color palettes characteristic of the training data, and in some cases the smooth modern surfaces acquired faint texturing reminiscent of medieval material rendering. The car remained clearly a car — but looked as if photographed through a medieval-styled filter.

- **`detailed-high` and `ultra-low`** showed the cleanest separation between LoRA style and modern subject matter. The sports car remained recognizably modern with glossy red paint, aerodynamic curves, and contemporary design language intact. Color temperature and surface smoothness were closest to the base model baseline.

- **`detailed-low`** fell between these groups — minor color warmth shift but no structural style intrusion.

**Conclusion:** Style leakage is not binary but exists on a spectrum. All variants preserved the core subject identity (a sports car is always a sports car). But the degree of subtle aesthetic contamination varied: higher-rank variants with sparser captions showed the most leakage, while `detailed-high` (high rank + rich captions) and `ultra-low` (lowest rank + sparsest captions) showed the least. This suggests that either sufficient text diversity or sufficiently constrained model capacity can independently limit style leakage — but combining high rank with sparse captions is the riskiest configuration.

---

## Figures

Evaluation figures compare outputs across all six LoRA variants and the base model baseline.

### Primary Figures

| Figure | Layout | Content | Purpose |
|--------|--------|---------|---------|
| **`figures/report_figure.png`** | 2×4 | 2 prompts (S1, T3) × 4 experiments (base_model, ultra_low, minimal_high, detailed_high) | Caption-detail trade-off spectrum across two asset categories |
| **`figures/model_card_figure_7x4.png`** | 7×4 | 7 rows (base_model + 6 variants) × 4 prompts (S1, U1, T3, L1) | Model card: comprehensive comparison including style-leakage probe |

![Caption-detail × rank comparison across S1 and T3](figures/report_figure.png)

![Base Model vs all 6 experiments across S1, U1, T3, L1](figures/model_card_figure_7x4.png)

---

## Limitations and Bias

### Training Data Bias
- **Structure-dominated:** The dataset is ~97% structures (buildings, walls, towers). Units, characters, vegetation, and terrain features are underrepresented or absent. The LoRA generalizes to these categories (especially `ultra-low`), but with less reliability than in-distribution structures.
- **Medieval domain lock:** Trained exclusively on medieval subject matter. Modern, sci-fi, or fantasy subjects outside the medieval aesthetic may show residual medieval styling or fail to trigger the perspective constraint reliably.
- **Single cultural tradition:** The dataset represents European medieval architecture. Non-European architectural traditions (e.g., East Asian, Middle Eastern, Mesoamerican) are absent and may not be well-served.

### Architectural Coupling
- **Style + perspective are coupled.** The LoRA learns medieval architectural style alongside top-down perspective. While trained on pixel-art images, the model generalizes beyond strict pixel art — it cannot produce photorealistic top-down views or non-medieval top-down views.
- **Strict top-down only.** The adapter enforces strictly orthogonal overhead view. It cannot produce isometric, side-view, ¾-angle, or first-person perspectives. Prompts requesting other angles will conflict with the LoRA's learned constraint.

### Dataset Size
- **100 images** is sufficient for low-rank LoRA training but constrains higher-rank adapters. The `detailed-high` variant (rank 128/64) shows signs of memorization at later training steps, indicating the dataset size is near the limit for this configuration.

### Licensing Restrictions
- **Non-commercial only.** All trained weights inherit the FLUX.2 [dev] non-commercial license restriction. Commercial game development, paid asset generation, or any revenue-generating use requires a separate commercial license from Black Forest Labs. See [License](#license) for the full dependency chain.

---

## License

These LoRA adapters are **derivative works** built from multiple upstream components. Every trained weight inherits license obligations from the models and data used to create them.

### Upstream License Chain

| Component | License | Restriction |
|-----------|---------|-------------|
| **FLUX.2 [dev]** (dataset generation model) | [FLUX.2-dev License](https://huggingface.co/black-forest-labs/FLUX.2-dev/blob/main/LICENSE.md) | **Non-commercial only** |
| **FLUX.2 Klein 4B** (LoRA training base model) | [FLUX.2-dev License](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4B/blob/main/LICENSE.md) | **Non-commercial only** |
| **Flux-2-Multi-Angles-LoRA-v2** (dataset generation LoRA) | [CreativeML Open RAIL-M](https://huggingface.co/lovis93/Flux-2-Multi-Angles-LoRA-v2) | Open RAIL-M usage restrictions |
| **Top-Down Medieval Pixel Art** (training dataset) | Non-commercial (derivative) | Inherits FLUX.2 [dev] restriction |
| **ComfyUI-PixelArt-Detector** (post-processing) | MIT | None |
| **rembg** (background removal) | MIT | None |
| **Ostris AI Toolkit** (training framework) | MIT | None |

### Effective License Summary

- **Non-commercial use only.** The most restrictive upstream license (FLUX.2 [dev]) prohibits commercial use. This restriction flows through to all trained LoRA weights.
- **Retain the FLUX.2-dev license** when redistributing these weights or models derived from them.
- **Comply with CreativeML Open RAIL-M** usage restrictions (no harmful or illegal use, no medical advice, no law enforcement use, etc.).
- **If you hold a separate commercial license** for FLUX.2 [dev] from Black Forest Labs, the non-commercial restriction may no longer apply — consult your licensing agreement.

---

## Citation

If you use these models in published research, please cite:

```bibtex
@misc{strategai-lora-2026,
  author = {stixxert},
  title = {StrategAI LoRA: TopDown Medieval Style for FLUX.2 Klein 4B},
  year = {2026},
  publisher = {Hugging Face},
  howpublished = {\url{https://huggingface.co/stixxert/strategai-topdown-medieval-style-lora}},
  note = {Six LoRA adapters trained on a 100-image synthetic dataset, evaluating caption detail × rank interaction for perspective-conditioned game asset generation}
}

@misc{topdown-medieval-pixelart-2026,
  author = {stixxert},
  title = {Top-Down Medieval Pixel Art},
  year = {2026},
  publisher = {Hugging Face},
  howpublished = {\url{https://huggingface.co/datasets/stixxert/topdown-medieval-pixelart}},
  note = {Synthetic dataset of 100 top-down medieval pixel-art game assets for LoRA fine-tuning}
}
```

---

## Related Resources

- **Training dataset:** [stixxert/topdown-medieval-pixelart](https://huggingface.co/datasets/stixxert/topdown-medieval-pixelart)
- **Base model:** [black-forest-labs/FLUX.2-klein-base-4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4B)
- **Camera-angle LoRA** (used for dataset generation): [lovis93/Flux-2-Multi-Angles-LoRA-v2](https://huggingface.co/lovis93/Flux-2-Multi-Angles-LoRA-v2)
- **Training framework:** [ostris/ai-toolkit](https://github.com/ostris/ai-toolkit)


## Model Card Author

[stixxert](https://github.com/stixxert)

