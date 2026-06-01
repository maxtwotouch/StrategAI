---
language:
- en
license: other
license_name: flux-non-commercial
license_link: https://huggingface.co/black-forest-labs/FLUX.2-dev/blob/main/LICENSE.md
license_details: >-
  This dataset is derived from FLUX.2 [dev] (non-commercial license) and
  Flux-2-Multi-Angles-LoRA-v2 (creativeml-openrail-m). All images and captions
  inherit the non-commercial restriction from the base model. See the License
  section below for the full dependency chain.
tags:
- pixel-art
- medieval
- top-down
- game-assets
- lora-training
- flux
- computer-vision
- image-generation
- synthetic
pretty_name: Top-Down Medieval Pixel Art
size_categories:
- n<1K
task_categories:
- text-to-image
annotations_creators:
- machine-generated
language_creators:
- machine-generated
---

# Dataset Card for Top-Down Medieval Pixel Art

## Quick Facts

| | |
|---|---|
| **Images** | 100 |
| **Resolution** | 1024 × 1024 px |
| **Format** | PNG, white background |
| **Asset families** | structure 97 / vegetation 2 / terrain 1 |
| **License** | Non-commercial, with Open RAIL-M usage restrictions (see [§License](#license)) |

## Dataset Description

**Top-Down Medieval Pixel Art** is a synthetic dataset of 100 top-down
(overhead) medieval fantasy pixel-art game assets, each paired with a
descriptive natural-language caption. It was designed for LoRA fine-tuning
of diffusion models to learn a consistent top-down camera angle, decoupled
from visual style as much as possible.

Each image is a 1024×1024 PNG with a white background, rendered in a crisp
16×16 pixel-art aesthetic. Asset categories include medieval structures
(buildings, towers, workshops, outposts), vegetation (brambles, reed
clusters), and terrain (boulders, rock formations).

> You may notice that the dataset is dominated by structures. This was not by design — the generation pipeline simply produced better results for buildings than for vegetation or terrain (see [Curation Rationale](#curation-rationale)). Despite the skew, the LoRA trained on this dataset successfully transfers top-down perspective to categories it barely saw during training, including character sprites and terrain features.

- **Curated by:** [stixxert](https://github.com/stixxert)
- **Language(s):** English (captions)
- **License:** Non-commercial use only — see [License](#license) for full dependency chain

### Dataset Sources

- **Base model:** [black-forest-labs/FLUX.2-dev](https://huggingface.co/black-forest-labs/FLUX.2-dev)
- **Camera-angle LoRA:** [lovis93/Flux-2-Multi-Angles-LoRA-v2](https://huggingface.co/lovis93/Flux-2-Multi-Angles-LoRA-v2)
- **Pixel-art post-processing:** [dimtoneff/ComfyUI-PixelArt-Detector](https://github.com/dimtoneff/ComfyUI-PixelArt-Detector) (MIT)
- **Background removal:** [Loewen-Hob/rembg-comfyui-node-better](https://github.com/Loewen-Hob/rembg-comfyui-node-better) (MIT, based on [rembg](https://github.com/danielgatis/rembg))

## Uses

### Direct Use

This dataset is intended for:

- **LoRA adapter training** — fine-tuning diffusion models to produce
  consistent top-down camera angles on generated images
- **Game-development asset pipelines** — generating consistent sprites,
  tilesets, and props with overhead perspective
- **Camera-pose conditioning research** — studying how diffusion models
  learn and apply viewpoint concepts from training data
- **Style-transfer experiments** — exploring pixel-art aesthetics in
  generative image models

The dataset is specifically designed to pair with
[FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4B)
using the [Ostris AI Toolkit](https://github.com/ostris/ai-toolkit).

This dataset was used to train the [StrategAI LoRA adapters](https://huggingface.co/stixxert/strategai-topdown-medieval-style-lora) — six LoRA variants for FLUX.2 Klein 4B that enforce top-down medieval style in generated game assets. See the [companion Model Card](https://huggingface.co/stixxert/strategai-topdown-medieval-style-lora) for training details and evaluation results.

### Out-of-Scope Use

This dataset is **not** suitable for:

- **Commercial asset production** — inherits non-commercial restriction
  from FLUX.2 [dev]; see [License](#license) for the full chain
- **Photorealistic generation** — all images are pixel art; the dataset
  will not teach a model to produce photorealistic top-down views
- **Training models intended to violate upstream licenses** — any use
  must comply with FLUX.2 [dev] (non-commercial) and
  Flux-2-Multi-Angles-LoRA-v2 (creativeml-openrail-m) terms
- **Generating NSFW, harmful, or deceptive content**
- **Identity or biometric inference** — the dataset contains no human
  subjects or personally identifiable information

### License

This dataset is a **derivative work** built from multiple upstream
components. Every image and caption inherits license obligations from
the models and tools used to create it.

#### Upstream License Chain

| Component | License | Link | Restriction |
|-----------|---------|------|-------------|
| **FLUX.2 [dev]** (base model) | FLUX.2-dev License | [LICENSE.md](https://huggingface.co/black-forest-labs/FLUX.2-dev/blob/main/LICENSE.md) | **Non-commercial only** |
| **Flux-2-Multi-Angles-LoRA-v2** (camera-angle adapter) | CreativeML Open RAIL-M | [model card](https://huggingface.co/lovis93/Flux-2-Multi-Angles-LoRA-v2) | Open RAIL-M (derivative works allowed; usage restrictions apply) |
| **ComfyUI-PixelArt-Detector** (palette quantization node) | MIT | [LICENSE](https://github.com/dimtoneff/ComfyUI-PixelArt-Detector/blob/main/LICENSE) | None (permissive) |
| **rembg-comfyui-node-better** (background removal node) | MIT | [rembg](https://github.com/danielgatis/rembg) | None (permissive) |

#### What This Means for You

- **Non-commercial use only.** The most restrictive upstream license
  (FLUX.2 [dev]) prohibits commercial use. This restriction flows
  through to all images and captions in this dataset.
- **You must retain the FLUX.2-dev license** when redistributing this
  dataset or models trained on it.
- **You must comply with CreativeML Open RAIL-M** usage restrictions
  (no harmful or illegal use, no medical advice, no law enforcement
  use, etc.) when using the Multi-Angles LoRA trained weights.
- **The MIT-licensed tools** (PixelArt-Detector, rembg) impose no
  additional restrictions on the output images.
- **If you hold a separate commercial license** for FLUX.2 [dev] from
  Black Forest Labs, the non-commercial restriction on this dataset
  may no longer apply — consult your licensing agreement.

**Summary:** The effective license of this dataset is **non-commercial,
with Open RAIL-M usage restrictions**. You may not use this dataset for
commercial purposes unless you hold a separate commercial license for
FLUX.2 [dev].

## Dataset Structure

### File Layout

```
images/
├── 00001.png
├── 00002.png
├── ...
├── 00100.png
└── metadata.jsonl
```

Each `.png` file is a 1024×1024 pixel RGBA image on a white background.
The companion `metadata.jsonl` contains one JSON object per line with
the following schema:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Zero-padded index (`"00001"`–`"00100"`) |
| `file_name` | string | Matching PNG filename |
| `text` | string | Natural-language caption (see [Caption Format](#caption-format)) |
| `asset_family` | string | One of `structure`, `vegetation`, `terrain` |

### Data Splits

This dataset has **no train/test/validation split**. All 100 images form
a single set intended for LoRA training. Users should create their own
splits if needed for evaluation.

### Example Data Point

```json
{
  "id": "00009",
  "file_name": "00009.png",
  "text": "top-down view. A medieval granary in a steampunk industrial expansion setting, featuring brass fittings and riveted mechanical accents, ornate but functional character, ornate detail, simple footprint, aged limestone blocks, weathered, smoky sepia palette",
  "asset_family": "structure"
}
```

### Dataset Statistics

| Statistic | Value |
|-----------|-------|
| Total images | 100 |
| Resolution | 1024 × 1024 px |
| Format | PNG, white background |
| Caption min length | 186 characters |
| Caption max length | 321 characters |
| Caption avg length | 281 characters |

| Asset Family | Count | Description |
|-------------|------:|-------------|
| `structure` | 97 | Buildings, towers, mills, workshops, outposts, keeps, cottages |
| `vegetation` | 2 | Bramble masses, reed clusters |
| `terrain` | 1 | Jagged boulder |

## Dataset Creation

### Curation Rationale

This dataset was created to test a specific hypothesis in LoRA
fine-tuning:

> *A low-rank adapter can learn a compositional concept like camera
> angle from ~100 examples if the training data is consistent in
> perspective and diverse in subject matter.*

The target use case is game-development pipelines where dozens or
hundreds of assets must share a consistent top-down perspective. Rather
than training a LoRA on each asset type separately, the goal is a single
adapter that enforces the overhead camera angle regardless of what is
being depicted.

Key design decisions:

| Decision | Rationale |
|----------|----------|
| 100 images | Enough for low-rank concept learning; manageable for manual curation |
| All top-down, no angle variation | Forces the LoRA to learn one perspective only |
| 16×16 pixel-art style | Crisp, readable assets; distinct from photorealistic training data |
| White background isolation | Removes confounding background context |
| Natural-language captions | Compatible with FLUX.2 text encoder; avoids structured tag formats |
| No trigger token in published data | Let users choose their own trigger token at training time. Dataset users are free to choose their own trigger token at training time — the companion [StrategAI LoRA](https://huggingface.co/stixxert/strategai-topdown-medieval-style-lora) uses `<tdp>`, but this is a training-time choice, not a property of the dataset. |

The heavy skew toward `structure` (97 of 100) was not intentional — it reflects where the generation pipeline worked well and where it struggled. The teacher pipeline (FLUX.2 [dev] + Multi-Angles LoRA v2, pixel-art quantization, background removal) reliably produced clean, readable structures. But the same pipeline faltered on non-structure categories: vegetation blurred into indistinct masses after quantization; rock formations rarely survived the strict top-down constraint with convincing geometry. Each usable vegetation or terrain image required many more generation attempts than a structure image. Within a curation budget of roughly 150–200 raw generations, the practical outcome was a structure-dominated dataset.

The skew has a silver lining: it provides a stronger test of concept isolation. If a LoRA trained on 97% structures successfully transfers top-down perspective to unseen categories (0% character sprites, 3% terrain), the angle concept has been genuinely isolated from subject matter.

### Source Data

#### Data Collection and Processing

**All images in this dataset are synthetically generated.** No
photographs, hand-drawn art, or web-scraped images were used.

The generation pipeline uses ComfyUI with the following components:

| Component | Model / Tool |
|-----------|-------------|
| Base model | [black-forest-labs/FLUX.2-dev](https://huggingface.co/black-forest-labs/FLUX.2-dev) |
| Camera-angle LoRA | [lovis93/Flux-2-Multi-Angles-LoRA-v2](https://huggingface.co/lovis93/Flux-2-Multi-Angles-LoRA-v2) |
| Pixel-art post-processing | [ComfyUI-PixelArt-Detector](https://github.com/dimtoneff/ComfyUI-PixelArt-Detector) |
| Background removal | [rembg-comfyui-node-better](https://github.com/Loewen-Hob/rembg-comfyui-node-better) |
| Pipeline runner | ComfyUI (API-driven generation) |

The camera angle was enforced at generation time by the Multi-Angles
LoRA, not by prompt engineering. This ensures every image truly is
top-down — there is no variation in perspective.

**Processing steps:**

1. **Prompt generation** — diverse medieval fantasy captions are produced from structured templates
2. **Image generation** — ComfyUI runs FLUX.2 [dev] + Multi-Angles LoRA
   with each prompt via HTTP API
3. **Pixel-art quantization** — ComfyUI-PixelArt-Detector reduces the
   color palette to a 16×16 pixel-art aesthetic
4. **Background removal** — rembg strips the generated background,
   replacing it with solid white
5. **Manual curation** — a human reviewer deletes images with artifacts,
   perspective errors, or poor composition; ~150–200 raw images were
   generated and culled to the best 100
6. **Dataset packaging** — embedded metadata is stripped, files are renumbered, and the final
   `metadata.jsonl` is produced

#### Who are the source data producers?

The images were generated by the FLUX.2 [dev] diffusion model
(Black Forest Labs), conditioned by prompt templates authored by the
dataset curator. The camera angle was enforced by the
Flux-2-Multi-Angles-LoRA-v2 adapter (lovis93).

No human artists, photographers, or annotators were involved in the
image creation process. No web-scraped or crowd-sourced data was used.

### Annotations

#### Annotation Process

Captions were **machine-generated** via structured prompt templates that combine:

- Asset type (granary, watchtower, sawmill, barracks, etc.)
- Setting/context (steampunk industrial, feudal military, mystical
  arcane, etc.)
- Architectural features (brass fittings, rune-carved stone, timber
  bracing, etc.)
- Condition (weathered, war-damaged, well-maintained, etc.)
- Color palette (ash-and-ember, mystic violet-cyan, cool medieval, etc.)

Each caption is prefixed with the **angle phrase** `top-down view.` to
bind the overhead perspective in the text embedding space.

Captions are natural-language sentences — **not** structured tags,
booru-style keywords, or comma-separated token lists. This format was
chosen for compatibility with FLUX.2's T5 text encoder, which expects
natural language input.

Three caption variants were derived from each original caption for
training experiments:

| Variant | Example | Purpose |
|---------|---------|---------|
| **Detailed** | `top-down view. A dramatic medieval world asset of a thorny bramble mass with ancient growth...` | Full description; tests whether detail helps or hurts angle learning |
| **Minimal** | `top-down view. A medieval vegetation.` | Category-only; reduces style binding to specific asset features |
| **Ultra-minimal** | `top-down view.` | Angle phrase only; isolates the angle concept completely |

These caption variants are used to test the hypothesis that less text detail leads
to purer angle-concept learning. They are not included in this published dataset.

#### Who are the annotators?

Captions were generated using structured templates.
The template design and caption review were performed by the dataset
curator. No crowd-sourced or third-party annotators were involved.

#### Personal and Sensitive Information

This dataset contains **no personal or sensitive information**:

- No human subjects, faces, or biometric data
- No names, addresses, or personally identifiable information
- No geolocation data
- No financial, health, or demographic data
- All images are synthetic renderings of imaginary medieval structures
  and landscapes

## Bias, Risks, and Limitations

### Known Biases

- **Medieval/fantasy domain bias** — all images depict medieval fantasy
  assets. A LoRA trained on this dataset will primarily produce
  medieval-themed outputs when the trigger token is activated.
- **Pixel-art style bias** — all images use a 16×16 pixel-art aesthetic.
  The LoRA may inadvertently learn pixel-art style alongside camera
  angle, despite efforts to isolate the angle concept.
- **Structure-heavy distribution** — 97% of images are structures. This reflects generation pipeline constraints (see [Curation Rationale](#curation-rationale)) rather than a design choice. The camera-angle concept may not transfer as reliably to vegetation, terrain, or organic subjects.
- **Single perspective** — all images are strictly top-down. The LoRA
  will not learn isometric, side-view, or ¾-angle perspectives.

### Technical Limitations

- **Small dataset size** — 100 images is sufficient for low-rank LoRA
  training but may not support full model fine-tuning or high-rank
  adapters without overfitting
- **Synthetic origin** — images were generated by a diffusion model and
  may contain artifacts typical of AI-generated imagery
- **Checkpoint dependence** — the dataset was generated with specific
  versions of FLUX.2 [dev] and ComfyUI custom nodes; reproducing the
  exact images requires the same software versions
- **No negative examples** — the dataset contains only top-down images
  with no counter-examples of other angles, which may limit the LoRA's
  ability to *suppress* non-top-down perspectives

### Recommendations

- **Use a trigger token** — set `trigger_word` in your training config
  (e.g., `<tdp>`). The Ostris AI Toolkit prepends it automatically.
  Always include both the trigger token and the angle phrase at
  inference: `<tdp> top-down view. a medieval watchtower...`
- **Pair with FLUX.2 Klein 4B** — the dataset was designed for and
  tested with this specific base model
- **Evaluate checkpoints** — train with frequent checkpoint saves
  (every 200 steps) and evaluate against out-of-distribution prompts
  to detect overfitting to individual assets
- **Consider caption detail level** — experiment with detailed, minimal,
  and ultra-minimal captions to find the right balance between style
  isolation and generation quality
- **Do not use commercially** — respect the upstream license chain:
  FLUX.2 [dev] (non-commercial) and Flux-2-Multi-Angles-LoRA-v2
  (creativeml-openrail-m). See [License](#license) for details.

## Citation

If you use this dataset in published research, please cite both the
dataset and the underlying models.

**BibTeX:**

```bibtex
@misc{topdown-medieval-pixelart-2026,
  author = {stixxert},
  title = {Top-Down Medieval Pixel Art},
  year = {2026},
  publisher = {Hugging Face},
  howpublished = {\url{https://huggingface.co/datasets/stixxert/topdown-medieval-pixelart}},
  note = {Synthetic dataset of 100 top-down medieval pixel-art game assets for LoRA fine-tuning}
}

@misc{flux2-dev,
  author = {Black Forest Labs},
  title = {FLUX.2 [dev]},
  year = {2025},
  publisher = {Hugging Face},
  howpublished = {\url{https://huggingface.co/black-forest-labs/FLUX.2-dev}}
}

@misc{multi-angles-lora,
  author = {lovis93},
  title = {Flux-2-Multi-Angles-LoRA-v2},
  year = {2025},
  publisher = {Hugging Face},
  howpublished = {\url{https://huggingface.co/lovis93/Flux-2-Multi-Angles-LoRA-v2}}
}
```

**APA:**

> stixxert. (2026). *Top-Down Medieval Pixel Art* [Dataset]. Hugging Face.
> https://huggingface.co/datasets/stixxert/topdown-medieval-pixelart

## Glossary

- **Trigger token** — a unique token (e.g., `<tdp>`) prepended to
  captions at training time to activate the LoRA at inference. Not
  present in the published dataset; users choose their own.
- **Angle phrase** — the text prefix `top-down view.` that binds the
  overhead perspective in the text embedding space. Present in all
  published captions.
- **LoRA (Low-Rank Adaptation)** — a parameter-efficient fine-tuning
  method that trains small adapter matrices rather than updating all
  model weights.
- **Camera angle / perspective** — the viewpoint from which a scene is
  rendered. "Top-down" means the camera is positioned directly above
  the subject, looking straight down.
- **Ostris AI Toolkit** — an open-source training toolkit for FLUX
  models, used to train the LoRA adapters in the companion project.
- **Pixel-art quantization** — reducing an image's color palette to
  produce a retro pixel-art aesthetic (16×16 pixel grid in this
  dataset).

## Dataset Card Authors

[stixxert](https://github.com/stixxert)
