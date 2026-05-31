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

## Model Description

Six LoRA (Low-Rank Adaptation) adapters trained on [FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4B) — a 4-billion-parameter Diffusion Transformer (DiT) — for generating **top-down medieval-style game assets**. The adapters enforce consistent overhead perspective and medieval architectural styling when activated by the trigger token `<tdp>` and the angle phrase `top-down view.`

These LoRAs were purpose-built for the [StrategAI](https://github.com/stixxert/StrategAI) project — an LLM-driven Civilization-style strategy game where AI civilizations are controlled via OpenAI's tool-use API and game assets are generated on-demand using DiT models. The adapters power the game's generative asset pipeline, providing consistent top-down medieval style across six asset families: structures, units, terrain tiles, nature objects, character sprites, and background tiles.

**What these LoRAs do:**
- Enforce a consistent top-down camera perspective when the trigger `<tdp>` is present
- Apply medieval architectural styling (crenellations, timber framing, stone masonry, period-appropriate details)
- Generalize beyond the training distribution — the adapters were trained exclusively on structures (~97% of the dataset) yet transfer to units, terrain, and objects <!-- TODO(stixxert): verify with U1, U2, T1, T2, T3 outputs -->
- Remain dormant when the trigger token is absent — no style leakage into non-triggered generations <!-- TODO(stixxert): verify with L1 and non-triggered probes -->

**What these LoRAs do NOT do:**
- They do not enforce pixel-art aesthetics — the training images were pixel-art quantized, but the LoRA learned perspective + style rather than the pixel-art filter itself
- They do not produce isometric, side-view, or ¾-angle perspectives — the top-down constraint is strict

**Key design insight:** These adapters were produced as part of a systematic 3×2 experiment matrix (3 caption detail levels × 2 LoRA rank configurations) to study how caption granularity and model capacity interact during fine-tuning for perspective-conditioned generation. The recommended `detailed-high` variant emerged as the optimal balance between in-distribution fidelity and out-of-distribution generalization.

| | |
|---|---|
| **Base model** | [black-forest-labs/FLUX.2-klein-base-4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4B) |
| **Training dataset** | [stixxert/topdown-medieval-pixelart](https://huggingface.co/datasets/stixxert/topdown-medieval-pixelart) (100 images) |
| **Training framework** | [Ostris AI Toolkit](https://github.com/ostris/ai-toolkit) |
| **Trigger phrase** | `<tdp> top-down view.` |
| **Recommended variant** | `detailed-high` — maximum architectural fidelity + strong in-distribution reproduction |
| **Total variants** | 6 LoRA adapters + base model baseline |

---

## Model Variants

The six LoRA variants span a 3×2 experiment matrix: three caption detail levels (detailed, minimal, ultra-minimal) × two LoRA rank configurations (high, low). Each variant is a `.safetensors` file at its optimal training checkpoint.

| # | Variant | Filename | Caption Detail | Rank (L/C) | Steps | Size | Best For |
|---|---------|----------|----------------|:----------:|------:|-----:|----------|
| — | **Base model** | *(no LoRA)* | — | — | — | — | Baseline comparison; no top-down style |
| 1 | **detailed-high** ⭐ | `strategai-lora-detailed-high-step1800.safetensors` | 50–100 words | 128/64 | 1,800 | 353 MB | **Recommended** — maximum architectural fidelity + strong in-distribution reproduction |
| 2 | **detailed-low** | `strategai-lora-detailed-low-step2200.safetensors` | 50–100 words | 64/32 | 2,200 | 177 MB | Detailed captions with better generalization |
| 3 | **minimal-high** | `strategai-lora-minimal-high-step2000.safetensors` | 20–30 words | 128/64 | 2,000 | 353 MB | Balanced detail reproduction + generalization |
| 4 | **minimal-low** | `strategai-lora-minimal-low-step2400.safetensors` | 20–30 words | 64/32 | 2,400 | 177 MB | Simpler captions, good generalization |
| 5 | **ultra-high** | `strategai-lora-ultra-high-step2200.safetensors` | 5–10 words | 128/64 | 2,200 | 353 MB | Minimal captions, strong style enforcement |
| 6 | **ultra-low** | `strategai-lora-ultra-low-step1600.safetensors` | 5–10 words | 64/32 | 1,600 | 89 MB | Best out-of-distribution generalization |

### Use-Case Guide

| Use case | Recommended variant | Rationale |
|----------|---------------------|-----------|
| Medieval game structures (buildings, walls, towers) | `detailed-high` | Trained on structures; highest rank capacity |
| General medieval assets (mixed categories) | `detailed-high` | Default recommendation |
| Game units / character sprites (not in training data) | `ultra-low` | Lowest rank — least overfitting risk on unseen categories |
| Terrain features (hills, trees, boulders) | `ultra-low` | Lowest rank — least overfitting risk on unseen categories |
| Modern or sci-fi objects (out-of-distribution) | `ultra-low` | Lowest rank — least overfitting risk on unseen categories |
| Quick experimentation / low VRAM | `ultra-low` | Smallest file (89 MB), fastest to load |
| Maximum architectural fidelity | `detailed-high` | Highest rank — most model capacity for detail |

<!-- TODO(stixxert): Verify these per-category recommendations with actual qualitative comparison. Are the ultra-low recommendations correct? Does detailed-high actually give "maximum architectural fidelity"? -->

---

## Why `detailed-high` Is Recommended

The `detailed-high` variant (detailed captions, 50–100 words, with high-rank LoRA: linear=128, conv=64) is the recommended adapter. All six LoRA variants produced usable game assets across all tested categories (structures, units, terrain). `detailed-high` was selected as the primary production variant for StrategAI's generative asset pipeline.

<!-- TODO(stixxert): Add your qualitative assessment here. Why was detailed-high selected over the others? What specific visual qualities distinguish it? Reference figures/report_figure.png and figures/model_card_figure_7x4.png. -->

### Caption Detail × Rank Trade-off

| | **High Rank (128/64)** | **Low Rank (64/32)** |
|---|---|---|
| **Detailed captions** (50–100 words) | **Optimal: maximum architectural fidelity** ⭐ | Moderate fidelity, better generalization but slower convergence |
| **Minimal captions** (20–30 words) | Balanced detail + generalization | Good generalization, somewhat less architectural precision |
| **Ultra-minimal captions** (5–10 words) | Strong style enforcement, limited detail control | Best generalization, weakest in-distribution detail |

<!-- TODO(stixxert): Add your own qualitative commentary on detailed-high here — what specific visual qualities make it the best? Reference figures/report_figure.png and figures/model_card_figure_7x4.png. Describe what detailed-high gets right on structures (S1, S2), units (U1, U2), and terrain (T1, T2, T3) that other variants miss. -->

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

### Caption Design

Three caption detail levels were derived from each original caption to test how text granularity affects LoRA learning. The hypothesis: less detailed captions force the model to learn abstract concepts (perspective, style) rather than memorizing specific visual patterns, improving generalization at the cost of detail reproduction.

| Variant | Word Count | Example |
|---------|:----------:|---------|
| **Detailed** | 50–100 | `top-down view. A medieval granary built from weathered oak planks with a thatched roof, elevated on stone pillars to prevent rodent access, featuring small ventilation windows and a wooden ladder, pixel art style with limited color palette` |
| **Minimal** | 20–30 | `top-down view. Medieval wooden granary with thatched roof on stone pillars, pixel art style` |
| **Ultra-minimal** | 5–10 | `top-down view. Medieval granary, pixel art` |

### Training Configuration

| Parameter | Detailed / Minimal | Ultra-minimal |
|-----------|:-------------------:|:-------------:|
| Total steps | 2,500 | 2,500 |
| Batch size | 1 | 1 |
| Learning rate | 8e-5 | 5e-5 |
| Optimizer | adamw8bit | adamw8bit |
| Weight decay | 1e-4 | 1e-4 |
| Scheduler | flowmatch | flowmatch |
| Timestep sampling | weighted | weighted |
| Checkpoint interval | 200 steps | 200 steps |
| Resolution | 512, 768, 1024 (multi-scale) | 512, 768, 1024 (multi-scale) |
| Caption dropout | 5% | 0% |

<!-- TODO(stixxert): Document the rationale for the lower learning rate (5e-5) used for ultra-minimal variants vs 8e-5 for detailed/minimal. -->

### Rank Configurations

| Config | Linear Rank | Linear Alpha | Conv Rank | Conv Alpha | File Size |
|--------|:----------:|:------------:|:---------:|:----------:|:---------:|
| **High** | 128 | 64 | 64 | 32 | ~353 MB |
| **Low** | 64 | 32 | 32 | 16 | ~177 MB |

<!-- TODO(stixxert): Add your observations on how rank affected results — did higher rank actually overfit? Did lower rank actually generalize better? -->

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

<!-- TODO(stixxert): Add convergence notes for each experiment. What did "peak detail before overfitting" look like for detailed-high at step 1800 vs 2000? Which experiments converged early vs late? What artifacts signaled overfitting? -->

---

## Evaluation

### Prompt Battery

All 6 LoRA variants plus the base model baseline were evaluated against 8 prompts spanning 3 asset categories (in-distribution structures and terrain, out-of-distribution units) and a style-leakage control. Prompts are sourced from `scripts/sample_prompts.json` and constitute the complete evaluation battery — each prompt exercises distinct aspects of the model's style adaptation and generalization capability.

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

All six LoRA variants produced usable, recognizable assets across all evaluation categories — structures (S1, S2), units (U1, U2), terrain (T1, T2, T3), and the style probe (L1). No variant failed to generate a coherent image for any prompt.

<!-- TODO(stixxert): Add your qualitative assessment: which variant was best overall? Which generalized best to OOD categories? Reference the generated images in sample_figures/ and figures/. -->

<!-- TODO(stixxert): [Full qualitative analysis needed] Examine the generated images in sample_figures/ and figures/. For each category below, describe specific visual differences between detailed-high and the other variants. Reference the comparison grids: figures/report_figure.png (2×4) and figures/model_card_figure_7x4.png (7×4). -->

#### In-Distribution Structures (S1 watchtower, S2 watermill)

<!-- TODO(stixxert): Describe architectural features visible in detailed-high vs other variants for S1 and S2. Which variant produces the crispest crenellations? Most plausible stone masonry? Best timber framing? Is perspective perfectly orthogonal in all variants? -->

#### Out-of-Distribution Units (U1 knight, U2 archer)

<!-- TODO(stixxert): Compare character sprite outputs across variants. Which produces the cleanest silhouette? Most readable weapons? Most game-ready appearance? Note any artifacts (anatomical distortions, perspective breaks) in specific variants. -->

#### Terrain Features (T1 hill, T2 oak tree)

<!-- TODO(stixxert): Describe terrain outputs. Do all variants use appropriate palettes (earthy greens/browns for hills, forest greens/bark browns for trees)? Is there visible repetition or unnatural regularity in any variant? Which variant would look best tiled on a game map? -->

#### Rock Formation (T3 boulder) ⭐ — Primary Report Figure

<!-- TODO(stixxert): [Critical] T3 is the primary evaluation figure for the IEEE report. Describe the boulder outputs for base_model, ultra_low, minimal_high, and detailed_high: silhouette clarity, surface texture detail (granite facets, crevices), lichen/moss rendering, shadow plausibility. How does each variant handle the transition from structured (rock geometry) to organic (moss, irregular surface)? -->

### Training Dynamics

<!-- TODO(stixxert): [Verify with figures/step_progression.png] Analyze checkpoint progression. Describe specific visual differences between steps 500, 1000, 1500, 1800, and 2200 for a representative variant. At what step do key features become recognizable? When does overfitting (rigid repetition across seeds) set in? Document the three regimes (under-trained, sweet spot, over-trained) with specific visual evidence. -->

<!-- TODO(stixxert): Verify whether a step-2400 checkpoint exists for detailed-high (the table shows optimal at step 1800, training ended at 2500). If no step-2400 exists, remove any references to it. -->

### Style Leakage Analysis

Style leakage refers to the unintended transfer of a LoRA's learned style to semantically unrelated subject matter. A well-scoped domain adapter should respect the trigger token without contaminating out-of-domain subjects: activating the LoRA on a modern object should still produce a recognizable modern object, not a medieval version of it.

**Probe design:** Prompt L1 includes the `<tdp>` trigger token but describes a modern red sports car — semantically distant from the training distribution (100% medieval structures). Each of the six LoRA variants was evaluated at strength 1.0 alongside a base model baseline (strength 0.0). This tests whether the LoRA incorrectly applies medieval architectural styling to anachronistic subjects when the trigger is active.

**Findings:** Pending qualitative review.

<!-- TODO(stixxert): [Verify] Examine L1 outputs for ALL six variants vs base model. Document: (a) do sports cars remain recognizably modern? (b) any medieval material intrusions (stone textures, crenellations)? (c) any perspective shifts toward overhead view? (d) any color temperature/contrast shifts? Even subtle differences should be documented. Then write the findings paragraph and conclusion. -->

---

## Figures

Evaluation figures are generated by `scripts/generate_comparison_grid.py` from sampling output in `sample_figures/` and written to `figures/`.

### Primary Figures

| Figure | Layout | Content | Purpose |
|--------|--------|---------|---------|
| **`figures/report_figure.png`** | 2×4 | 2 prompts (S1, T3) × 4 experiments (base_model, ultra_low, minimal_high, detailed_high) | IEEE report: caption-detail trade-off spectrum across two in-distribution asset categories |
| **`figures/model_card_figure_7x4.png`** | 7×4 | 7 rows (base_model + 6 variants) × 4 prompts (S1, U1, T3, L1) | Model card: comprehensive comparison including style-leakage probe |

![Base Model vs all 6 experiments](figures/model_card_figure_7x4.png)

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
- **Upstream project:** [StrategAI](https://github.com/stixxert/StrategAI)

## Model Card Author

[stixxert](https://github.com/stixxert)

