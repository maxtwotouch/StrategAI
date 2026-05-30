# Experiment Design: Camera-Angle LoRA on FLUX.2 Klein 4B

## 1. Motivation

We want a LoRA adapter that, when activated via a trigger token, forces a
**top-down (overhead) camera angle** on generated images — regardless of
subject matter.  The target use case is game-development asset pipelines
where consistent perspective is critical across hundreds of generated sprites,
tiles, and props.

The challenge is that our training images are all **top-down medieval
pixel art**.  If we are not careful, the LoRA will learn a compound concept:
"top-down **+** medieval **+** pixel art".  We want to isolate the
*angle* from the *style* as much as possible.

## 2. Why FLUX.2 Klein 4B

| Property | Rationale |
|----------|----------|
| **4B parameters** | Small enough to fine-tune on a single GPU; large enough to learn a compositional concept like camera angle |
| **Native fp8** | Base weights occupy ~8 GB VRAM; training instances are ~15–18 GB each, enabling parallel experiments |
| **Distilled transformer** | Trained via flow-matching; compatible with the Ostris AI Toolkit ecosystem |
| **Gated, but accessible** | Free for non-commercial research use via HuggingFace |

The 9B variant was excluded — the 4B model is sufficient for a narrow
concept like camera angle, and the smaller parameter count reduces the
risk of memorising style details.

## 3. Dataset

### 3.1 What we have

100 top-down medieval pixel-art PNGs (1024×1024), each with a detailed
caption.  The images were **generated** by a ComfyUI pipeline:

```
FLUX.2 [dev] + Multi-Angles LoRA v2 → PixelArt-Detector → rembg
```

The camera angle was enforced at generation time by the Multi-Angles LoRA,
not by prompt engineering.  This means every image truly IS top-down —
there is no variation in perspective.

### 3.2 Why 100 images

We settled on 100 images as a clean, round target that balances several
concerns:

| Reason | Detail |
|--------|--------|
| **Low-rank concept** | Camera angle affects global composition (layout, occlusion, vanishing-point geometry) rather than fine texture details. LoRA ranks of 32–128 have enough capacity to capture this without needing hundreds of examples |
| **Practical curation** | Generating ~150–200 raw images and curating down to the best 100 is manageable for one person in a single review session |
| **Checkpoint evaluation** | 100 images ÷ 6 evaluation prompts = ~16–17 images per prompt at each checkpoint — enough to judge quality without noise from a single outlier |
| **Training stability** | 100 samples is well above the minimum for LoRA training (~15–20), giving headroom for the ultra-minimal variant where all captions are identical |
| **Round number** | Clean target; easy to communicate in model cards and papers

The risk with a small dataset is overfitting to individual assets rather
than learning the shared angle.  Our countermeasures:
- Multiple caption detail levels to test whether text diversity helps or hurts
- Checkpoints every 200 steps so we can select an earlier one if overfitting occurs
- Out-of-distribution evaluation prompts to detect memorisation

### 3.3 Asset family distribution

| Family | Count | Description |
|--------|------:|-------------|
| structure | ~90 | Buildings, towers, mills, workshops, outposts (the dominant category, reflecting the target use case) |
| object | ~7 | Trees, boulders, stumps, props — non-walkable world scenery |
| terrain | ~3 | Hills and plateaus with wide flat tops for unit placement |

The heavy skew toward structures is deliberate — game-development asset pipelines
primarily need consistent building sprites. The angle concept should transfer
across categories because the perspective geometry is identical regardless of
what occupies the ground plane.


## 4. Caption Design

### 4.1 Why we replaced the angle phrase

**Before**: `Front view overhead elevated medium shot.` (6 words, 42 chars)

**After**: `top-down view.` (2 words, 12 chars)

| Problem with the old phrase | Why it matters |
|------------------------------|----------------|
| "Front view" contradicts "overhead" | Confuses the text encoder — is it front or top? |
| Cinematographic language ("elevated medium shot") | Not natural for pixel-art or game-asset contexts |
| Verbose (6 words) | Wastes token budget; users must reproduce it exactly at inference |
| Domain-specific | "Shot" implies photography/cinematography, not sprite generation |

"top-down view" is plain English, domain-agnostic, and short enough that
users will naturally type it at inference.

### 4.2 Three caption detail levels

We created three variants of every caption to test a core hypothesis:

> *Less text detail → less style binding → purer angle concept*

| Variant | Caption format | Hypothesis |
|---------|---------------|------------|
| **detailed** | `[trigger] top-down view. [full description — building type, setting, materials, condition, palette]` | Rich text gives the model more conditioning signal, but risks binding style descriptors (e.g. "warm muted palette") to the trigger token |
| **minimal** | `[trigger] top-down view. A medieval [category].` | Strips all descriptive detail; model must learn content variation from pixels. Category provides minimal discriminative signal |
| **ultra-minimal** | `[trigger] top-down view.` | All 100 images share an identical caption. Model must learn EVERYTHING from pixels — the ultimate test of image-driven learning. Risk: mode collapse or inability to respond to text prompts at inference |

**Why sidecar `.txt` files are essential for our experiment:** The Ostris
toolkit reads captions from `.txt` files alongside images (not from `metadata.jsonl`
directly). Since we need three different caption variants pointing at the same
images, we use `src/training/derive_captions.py` to create three separate dataset
directories (`dataset/derived/detailed/`, `minimal/`, `ultra_minimal/`), each with
symlinks to the original PNGs plus variant-specific `.txt` files. This lets us
swap caption detail while keeping the pixel data identical — the core variable
we're testing.

**Why not test caption dropout as a separate axis?**  Caption dropout
randomly blanks the text during training, forcing the model to rely on
images for those steps.  This is complementary to our approach — we are
testing *what text is present*, not *whether text is present*.  A follow-up
experiment could combine minimal captions with high dropout.

### 4.3 Why the trigger token is `<tdp>`

- Angle brackets help Flux2's T5 text encoder treat it as a distinct token
- Short (4 characters) — minimal token budget cost
- Not a real word — no pre-existing semantics to compete with
- The toolkit prepends it automatically via `trigger_word` in the config

## 5. Experiment Matrix

### 5.1 Why rank as the primary variable

LoRA rank controls how many parameters are added to the base model.
Higher rank = more capacity to learn complex patterns, but also more
capacity to **memorise** training-set specifics (individual buildings,
specific palette names, etc.).

| Rank (linear/conv) | Capacity | Risk |
|--------------------|----------|------|
| 128 / 64 (high) | ~250–350 MB safetensors | Higher style memorisation |
| 64 / 32 (mid) | ~120–180 MB | Balanced |
| 32 / 16 (low) | ~50–80 MB | May not capture angle concept adequately |

Comparing high vs. low rank within each caption type isolates the effect
of parameter count on style leakage.

### 5.2 The 6 experiments

| # | Config name | Caption | Linear rank | Conv rank | LR | Dropout |
|---|------------|---------|-------------|-----------|-----|---------|
| 1 | `minimal_high` | minimal | 128 | 64 | 8e-5 | 0.1 |
| 2 | `minimal_low` | minimal | 64 | 32 | 8e-5 | 0.1 |
| 3 | `detailed_high` | detailed | 128 | 64 | 8e-5 | 0.05 |
| 4 | `detailed_low` | detailed | 64 | 32 | 8e-5 | 0.05 |
| 5 | `ultra_high` | ultra-minimal | 128 | 64 | 5e-5 | 0.0 |
| 6 | `ultra_low` | ultra-minimal | 32 | 16 | 5e-5 | 0.0 |

### 5.3 Why conv layers are included

Top-down camera angle is inherently a **spatial** concept — it affects
how depth, occlusion, and layout are represented across the 2D latent grid.
Conv layers in the LoRA network can capture these spatial relationships
better than linear-only layers.  We use conv rank at half the linear rank
to keep parameter counts manageable while still providing spatial capacity.

### 5.4 Why ultra-minimal gets lower LR and no dropout

- **Lower LR (5e-5 vs 8e-5)**: All captions are identical, so the model
  converges faster.  A lower LR prevents it from overfitting to the single
  caption string.
- **No caption dropout**: If we drop the only caption, the model receives
  blank conditioning — this is degenerate and would cause the model to
  learn an unconditional distribution rather than the angle concept.
- **Why 0.1 dropout for minimal/detailed**: A small amount of dropout
  (5–10%) is standard practice — it acts as weak regularisation and
  slightly improves generalisation without harming concept learning.

## 6. Training Configuration

### 6.1 Why 2500 steps (all experiments)

Uniform step count enables direct comparison at every checkpoint interval
(200, 400, 600, ..., 2500).  Some configurations may converge earlier
(especially ultra-minimal), but we keep all checkpoints and can select
the best one post-hoc.  Over-training is detectable via the sample images.

### 6.2 Why checkpoints every 200 steps

- 200 steps is frequent enough to observe the learning trajectory
- Each checkpoint is a usable LoRA — if step 1800 looks better than 2500, we use it
- Total storage across 6 experiments × 13 checkpoints ≈ 13–14 GB — manageable
- `max_step_saves_to_keep: 15` retains all 13 checkpoints with headroom

### 6.3 Why gradient checkpointing

Gradient checkpointing trades compute for VRAM.  It is enabled as a
conservative default to ensure training stability across a range of
GPU configurations.  With sufficient VRAM (≥48 GB), it can be safely
disabled for higher throughput.

### 6.4 Why adamw8bit

8-bit AdamW reduces VRAM usage for optimizer states by ~75% compared to
fp32 AdamW, with negligible impact on training quality.  This is standard
practice in the Ostris toolkit ecosystem.

### 6.5 Why weighted timestep sampling

Flux2 models use flow-matching, which benefits from non-uniform timestep
sampling.  The "weighted" strategy samples more steps from the middle of
the diffusion process where concept formation is most active.

## 7. Evaluation Strategy

### 7.1 Shared prompts across all experiments

All 6 configs use identical sample prompts.  At each `sample_every: 250`
interval, every experiment generates the same 8 images.  This enables
direct side-by-side comparison — any visual difference between two
experiments at the same step count is attributable to the config
differences (caption type or rank), not to prompt variation.

### 7.2 Why 4 in-distribution + 4 OOD prompts

| Type | Count | Purpose |
|------|------:|---------|
| In-distribution | 4 | Verify the LoRA works on its training domain (medieval pixel art). Tests reproduction fidelity |
| Out-of-distribution | 4 | Test whether the angle transfers to unseen subjects (car, spaceship, coffee, house). Tests concept isolation |

The OOD prompts deliberately use **modern, non-medieval, non-pixel-art**
subjects.  If a car or spaceship shows pixel-art artifacts, the LoRA has
bound style to the trigger token.  If it shows a clean top-down perspective
without medieval texture, the angle has been isolated.

### 7.3 Why these specific prompts

**In-distribution prompts** were sampled directly from the dataset's
detailed captions (not invented).  They represent the actual training
distribution: vegetation (bramble), industrial (volcanic outpost),
religious (riverside sawmill), and mystical (watermill).  This diversity
tests whether the LoRA generalises across the training domain.

**OOD prompts** use the same `top-down view. [subject], white background.`
structure as the training captions.  The only variable is the subject.
This isolates the effect of subject-domain shift from caption-format shift.

### 7.4 What to look for at each checkpoint

| Step range | Expected behaviour | Warning signs |
|-----------|-------------------|---------------|
| 0–500 | Angle concept forming; images may be noisy or inconsistent | Complete noise at step 500 — LR too low or config error |
| 500–1500 | Angle stabilising; OOD subjects may show some style leakage | OOD subjects look fully medieval — style is binding to token |
| 1500–2500 | Fine-tuning; check if quality plateaus or degrades | OOD quality degrades while in-distribution improves — overfitting |

## 8. Training Pipeline

### 8.1 Why all 6 in parallel

With fp8 base weights (~8 GB per instance) + LoRA training overhead
(~7–10 GB), each experiment uses ~15–18 GB.  Six instances × 15–18 GB
= 90–108 GB total — fits on a 96 GB RTX 6000, potentially tight at the
upper end.

If VRAM is insufficient for all 6, the `train_experiments.sh` script
can be trivially modified to run 3+3 in two waves.

### 8.2 Why a bash orchestrator, not Python

The Ostris AI Toolkit is a CLI tool (`python run.py config.yaml`).  A
bash script is the simplest, most transparent way to launch multiple
instances, capture PIDs, wait for completion, and report exit codes.
No additional dependency or abstraction layer is needed.

## 9. HF Dataset Publishing

### 9.1 Why sequential numbering

The source images have non-sequential IDs (0000001, 0000009, 0000011, ...)
inherited from the generation pipeline.  For a public dataset, sequential
numbering (00001–00100) is cleaner, easier to reference, and follows
HuggingFace conventions.

### 9.2 Why metadata.jsonl co-located with images

Placing `metadata.jsonl` in the same directory as the PNGs (flat layout)
simplifies the `file_name` references (bare filenames, no subdirectory
prefixes) and matches the simplest HF `imagefolder` convention.  No
subdirectory nesting means one less thing for users to configure.

### 9.3 Why we generate captions ourselves

The published dataset uses HF `imagefolder` format: images + `metadata.jsonl`
in a flat directory.  However, the Ostris AI Toolkit reads captions from
`.txt` sidecar files (one per image, same base name), not from JSONL — so
we must generate `.txt` files before training.

We generate them ourselves rather than relying on pre-made sidecars for
three reasons:

| Reason | Detail |
|--------|--------|
| **Multi-variant experiment** | Our 6-experiment matrix tests three caption detail levels (detailed, minimal, ultra-minimal) against the same 100 images. The toolkit reads one `.txt` file per image — we need three different ones. `src/training/derive_captions.py` creates three symlinked dataset directories, each with variant-specific `.txt` files, so we can swap caption detail while keeping pixel data identical |
| **Clean published captions** | The HF dataset stores captions in their purest form: descriptive natural language, no trigger tokens, no style keywords. This keeps the dataset reusable for any training framework. `src/training/extract_training_set.py` layers on the training-specific concerns — injecting `[trigger]` placeholder and `top-down view.` angle phrase — at generation time |
| **Reproducibility** | `.txt` files are generated deterministically from `metadata.jsonl` via a version-controlled script. There is no risk of hand-edited sidecar files drifting from the canonical captions, and any pipeline improvement (e.g. a better angle phrase) can be applied by re-running the script |

The `.txt` files are generated on demand and never committed to the HF
dataset repository — they are training artifacts, not publishing artifacts.

### 9.4 Dataset card auto-generation

The `src/generation/prepare_dataset.py` script generates a `README.md`
dataset card with live statistics (total images, asset type breakdown,
caption lengths, resolution) embedded at build time.  This guarantees
the card never drifts from the actual dataset contents and eliminates
manual update errors.

## 10. Expected Outcomes

### 10.1 If ultra-minimal works best

The model learned the angle concept from pixels alone, with the trigger
token acting purely as an angle activator.  This is the ideal outcome —
the LoRA transfers to any subject without style contamination.

### 10.2 If detailed works best

The model needs rich text descriptions to disambiguate the training
signal.  Style leakage is inherent because the training images share
both angle and style — the model cannot fully disentangle them.

### 10.3 If minimal is the sweet spot

A small amount of text diversity (category labels) helps the model
converge, but stripping detailed descriptors prevents style binding.
This suggests a "minimum viable caption" strategy for future datasets.

### 10.4 If low rank outperforms high rank

Style memorisation requires parameter capacity.  A lower-rank LoRA
simply doesn't have enough parameters to memorise individual asset
details — only the shared angle concept fits.  This confirms the
low-rank hypothesis for concept-isolation training.

### 10.5 If high rank outperforms low rank

The angle concept is more complex than anticipated (perhaps involving
shadow direction, occlusion patterns, or perspective cues that need
more parameters to represent).  The rank must be high enough to capture
the concept, even at the cost of some style leakage.

## 11. Limitations & Future Work

- **Single camera angle**: Only top-down is tested.  Extending to
  isometric, side-scroller, or 3/4 view would require separate experiments.
- **Single base model**: Only FLUX.2 Klein 4B is tested.  Results may
  not transfer to SDXL, SD3, or other architectures.
- **Small dataset size**: 100 images is sufficient for a narrow concept
  but limits statistical power for detecting subtle differences between
  configurations.
- **Qualitative evaluation only**: No automated metric for "angle fidelity"
  or "style leakage" — evaluation is visual inspection of sample images.
  Future work could incorporate CLIP directional similarity or pose-estimation
  metrics.
- **No ablation on conv layers**: We include conv layers in all experiments.
  A follow-up could test linear-only LoRA to isolate the contribution of
  spatial layers to angle learning.
