Here is a complete, self-contained reference guide designed to be injected as system context into a coding LLM. It covers the full lifecycle: installation, dataset preparation, configuration, trigger word injection, training, and inference — all via CLI on Linux, with no UI dependency.

```markdown
# FLUX.2 Klein 4B LoRA Training Guide — Ostris AI Toolkit (CLI / Linux)

## Overview

This guide documents how to train a LoRA adapter on the **FLUX.2 Klein 4B** distilled
image model using the **Ostris AI Toolkit**, entirely from the Linux command line — no
web UI is required.

- **Model**: `black-forest-labs/FLUX.2-klein-4B` — a 4B-parameter distilled diffusion
  transformer from Black Forest Labs.  Fits in ~13 GB VRAM at inference; training works
  on 16 GB+ GPUs with quantisation and `low_vram` enabled.
- **Toolkit**: https://github.com/ostris/ai-toolkit — the most widely-used open-source
  LoRA / LoKr trainer for modern diffusion models.
- **Training target**: LoRA (low-rank adaptation) — small, portable `.safetensors` files
  that can be loaded alongside the base model in ComfyUI, diffusers, etc.

---

## 1. Installation (Linux)

### 1.1 Clone & set up the environment

```bash
git clone https://github.com/ostris/ai-toolkit.git
cd ai-toolkit
git submodule update --init --recursive
python -m venv venv
source venv/bin/activate
pip install torch
pip install -r requirements.txt
```

### 1.2 Hugging Face authentication

The FLUX.2 Klein 4B model is gated.  Accept the license at
https://huggingface.co/black-forest-labs/FLUX.2-klein-4B, then create a read-only
access token at https://huggingface.co/settings/tokens and log in:

```bash
huggingface-cli login
```

---

## 2. Dataset format

A dataset is a directory containing image files and matching `.txt` caption files.

### 2.1 Directory layout

```
datasets/my_concept/
├── img_01.jpg
├── img_01.txt
├── img_02.jpg
├── img_02.txt
├── img_03.png
├── img_03.txt
└── ...
```

### 2.2 Caption rules

- The `.txt` file must have **exactly the same base name** as its image (e.g.
  `img_01.jpg` ↔ `img_01.txt`).
- Supported image formats: `jpg`, `jpeg`, `png` (webp is not reliable).
- Images are **never upscaled**, only downscaled into resolution buckets — you do not
  need to crop or resize images beforehand.
- A dataset of **15–20 diverse, high-quality images** is sufficient for a character LoRA;
  style LoRAs generally need more.

### 2.3 Pure captions (trigger word NOT in source files)

The recommended approach is to keep captions **clean and reusable**: describe the
scene, clothing, background, and accessories, but do NOT describe the permanent
features you want the LoRA to learn (facial structure, eye colour, skin tone).

**Captions should not contain your trigger word.**  The toolkit injects it at training
time (see §3.1).

Example:
```
# img_01.txt (a character LoRA)
a woman wearing a red dress, standing in a garden, natural lighting

# img_02.txt
a woman at a coffee shop, holding a ceramic cup, indoor lighting
```

---

## 3. How trigger word injection works

The toolkit provides **two** non-destructive injection mechanisms.  Neither modifies
your source `.txt` files — injection happens in-memory at training time.

### 3.1 `trigger_word` — automatic prepending

When you set `trigger_word: "my_token"` in the config, the toolkit **prepends** that
token to every caption before it is encoded.  If the caption already contains the
trigger word anywhere, it is *not* duplicated.

```
Source caption:      "a woman wearing a red dress"
trigger_word:        "sks_char_neo"
Effective caption:   "sks_char_neo a woman wearing a red dress"
```

### 3.2 `[trigger]` — positional placeholder

If a `.txt` caption contains the literal string `[trigger]`, the toolkit replaces it
with the value of `trigger_word`.  This is useful when you want the token at a
specific position rather than always prepended.

```yaml
trigger_word: "sks_char_neo"
```

```
Source caption:      "[trigger] is a woman wearing a red dress"
Effective caption:   "sks_char_neo is a woman wearing a red dress"
```

### 3.3 Critical interaction with `cache_text_embeddings`

When `cache_text_embeddings` is `true`, the text encoder runs once per unique caption
and the embeddings are saved to disk.  **This must be `false`** when using trigger word
injection (or `caption_dropout_rate`, or any per-step caption modification).  Cached
embeddings would freeze the caption content, defeating dynamic injection.

### 3.4 Trigger word best practices

- Use a **unique nonsense token** that the base model has no prior knowledge of
  (e.g. `sks_myconcept_v1`, `zx9_style_token`).  Avoid real words like `woman` or
  `portrait` — these compete with the base model's existing understanding.
- Be consistent: the exact same token string must be used during inference.
- Case matters: `My_Token` ≠ `my_token`.

---

## 4. The training config file (YAML)

The config is a YAML file passed to `python run.py <config>.yml`.  The toolkit ships
examples under `config/examples/`.

### 4.1 Complete reference config for FLUX.2 Klein 4B LoRA

```yaml
---
job: "extension"
config:
  # ── Job identity ──────────────────────────────────────────────────
  name: "my_flux2_klein_4b_lora"        # used for output folder & filenames
  process:
    - type: "diffusion_trainer"
  training_folder: "./output"
  device: "cuda"

  # ── Trigger word (injected at training time, never saved to disk) ─
  trigger_word: "sks_char_neo"

  # ── LoRA network definition ───────────────────────────────────────
  network:
    type: "lora"                         # or "lokr"
    linear: 32                           # rank (capacity): 16-32 typical
    linear_alpha: 32                     # scaling factor; usually == linear

  # ── Checkpoint saving ─────────────────────────────────────────────
  save:
    dtype: "bf16"
    save_every: 500                      # save checkpoint every N steps
    max_step_saves_to_keep: 10           # prune older checkpoints

  # ── Dataset(s) ────────────────────────────────────────────────────
  datasets:
    - folder_path: "./datasets/my_concept"
      default_caption: ""                # fallback if image has no .txt
      caption_ext: "txt"
      caption_dropout_rate: 0.05         # randomly drop 5% of captions
      resolution:                        # buckets; images downscaled to fit
        - 512
        - 768
        - 1024

  # ── Training hyperparameters ──────────────────────────────────────
  train:
    batch_size: 1
    gradient_accumulation: 2             # effective batch = batch_size × this
    steps: 1500                          # total optimizer steps
    train_unet: true
    train_text_encoder: false
    gradient_checkpointing: true

    noise_scheduler: "flowmatch"         # REQUIRED for FLUX.2 models
    optimizer: "adamw_8bit"              # "prodigy_8bit" is an alternative
    timestep_type: "sigmoid"             # "weighted" also common
    content_or_style: "balanced"

    lr: 0.0001                           # learning rate
    weight_decay: 0.01
    dtype: "bf16"

    # MUST be false when trigger_word injection or caption_dropout is used
    cache_text_embeddings: false

    # Optional EMA (costs VRAM, can improve stability on small datasets)
    ema_config:
      use_ema: false
      ema_decay: 0.99

  # ── Model loading ─────────────────────────────────────────────────
  model:
    name_or_path: "black-forest-labs/FLUX.2-klein-4B"
    quantize: true
    qtype: "qfloat8"                     # float8 quantisation
    arch: "flux2_klein_4b"
    low_vram: true

  # ── Sample generation during training ─────────────────────────────
  sample:
    sampler: "flowmatch"
    sample_every: 500                    # match save_every for paired previews
    width: 1024
    height: 1024
    guidance_scale: 4
    sample_steps: 25
    seed: 42
    walk_seed: true

    # Sample prompts should NOT include the trigger word; the toolkit
    # prepends it just as it does for training captions.
    samples:
      - prompt: "a woman in studio lighting, portrait shot"
      - prompt: "a woman at a coffee shop, candid photo"
      - prompt: "a woman in a forest, cinematic lighting"
```

### 4.2 LoKR alternative

To train a LoKr (Low-Rank Kronecker product) instead of LoRA, change the network
block:

```yaml
network:
  type: "lokr"
  linear: 32
  linear_alpha: 32
  conv: 16
  conv_alpha: 16
  lokr_full_rank: true
  lokr_factor: 8
```

LoKr is more parameter-efficient but less universally supported at inference time.
Most ComfyUI LoRA loaders handle it.

---

## 5. Running training

### 5.1 Start training

```bash
cd ai-toolkit
source venv/bin/activate
python run.py config/my_flux2_klein_4b_lora.yml
```

On first run, the toolkit downloads the base model from Hugging Face (~13 GB).

### 5.2 Interruption & resumption

Press Ctrl+C to stop.  **Wait for the current checkpoint to finish saving** before
killing the process, or that checkpoint will be corrupted.  Re-running the same
command resumes from the last saved checkpoint.

### 5.3 Monitoring

- The terminal prints loss values and step progress.
- Generated sample images and `.safetensors` checkpoint files appear in
  `./output/<job_name>/`.
- Compare samples across checkpoints — an earlier checkpoint is often better than
  the final one if overfitting occurs.

### 5.4 Output files

```
output/my_flux2_klein_4b_lora/
├── my_flux2_klein_4b_lora_step_500.safetensors
├── my_flux2_klein_4b_lora_step_1000.safetensors
├── my_flux2_klein_4b_lora_step_1500.safetensors
├── samples/                              # generated preview images
│   ├── step_500_sample_0.png
│   ├── step_500_sample_1.png
│   └── ...
└── ...
```

---

## 6. Programmatic usage (scripting)

Wrap training in a shell script to accept parameters:

```bash
#!/bin/bash
# train_lora.sh — Usage: ./train_lora.sh <dataset_path> <trigger_word> [steps]
set -euo pipefail

DATASET="${1:?Usage: $0 <dataset_path> <trigger_word> [steps]}"
TRIGGER="${2:?Usage: $0 <dataset_path> <trigger_word> [steps]}"
STEPS="${3:-1500}"
NAME="lora_$(date +%Y%m%d_%H%M%S)"

cd "$(dirname "$0")"
source venv/bin/activate

python run.py - <<YAML
---
job: "extension"
config:
  name: "${NAME}"
  process:
    - type: "diffusion_trainer"
  training_folder: "./output"
  device: "cuda"
  trigger_word: "${TRIGGER}"
  network:
    type: "lora"
    linear: 32
    linear_alpha: 32
  save:
    dtype: "bf16"
    save_every: 500
    max_step_saves_to_keep: 10
  datasets:
    - folder_path: "${DATASET}"
      caption_ext: "txt"
      caption_dropout_rate: 0.05
      resolution:
        - 512
        - 768
        - 1024
  train:
    batch_size: 1
    steps: ${STEPS}
    gradient_accumulation: 2
    train_unet: true
    train_text_encoder: false
    gradient_checkpointing: true
    noise_scheduler: "flowmatch"
    optimizer: "adamw_8bit"
    timestep_type: "sigmoid"
    lr: 0.0001
    dtype: "bf16"
    cache_text_embeddings: false
  model:
    name_or_path: "black-forest-labs/FLUX.2-klein-4B"
    quantize: true
    qtype: "qfloat8"
    arch: "flux2_klein_4b"
    low_vram: true
  sample:
    sampler: "flowmatch"
    sample_every: 500
    width: 1024
    height: 1024
    guidance_scale: 4
    sample_steps: 25
    samples:
      - prompt: "a person, studio lighting, portrait"
      - prompt: "a person at a cafe, candid photo"
      - prompt: "a person in a forest, cinematic lighting"
YAML
```

```bash
chmod +x train_lora.sh
./train_lora.sh "./datasets/my_character" "sks_char_v2" 2000
```

---

## 7. Parameter reference

### 7.1 Network (LoRA capacity)

| Parameter | Typical range | Notes |
|-----------|--------------|-------|
| `linear` (rank) | 16–32 | Higher = more capacity, larger file, more VRAM, higher overfit risk.  16 is enough for most character LoRAs; 32 for styles or very consistent subjects. |
| `linear_alpha` | == rank or ½ rank | Scaling factor.  Equal to rank is standard; half-rank produces a weaker adapter. |

### 7.2 Training dynamics

| Parameter | Typical range | Notes |
|-----------|--------------|-------|
| `steps` | 1500–3000 | ~100 passes per image for character LoRAs.  Fewer steps = earlier checkpoint is best; more steps = risk of overfitting. |
| `batch_size` | 1 | Increase only with ample VRAM.  Higher values may harm quality. |
| `gradient_accumulation` | 2–4 | Simulates larger batches without extra VRAM.  Effective batch = batch_size × this. |
| `lr` | 0.00005–0.0002 | 0.0001 is a safe default.  Lower if loss is unstable; raise slightly if LoRA is too weak. |
| `weight_decay` | 0.0–0.01 | Regularisation; 0.01 helps prevent overfitting. |

### 7.3 Timestep strategies

| `timestep_type` | Effect |
|----------------|--------|
| `weighted` | General-purpose. |
| `sigmoid` | Concentrates on mid-noise levels; reported better for character LoRAs. |
| `linear` | Even distribution across all noise levels. |

`content_or_style`: `balanced` (default), `content` (coarse structure), or `style`
(fine textures).

### 7.4 Optimizer choice

| Optimizer | Notes |
|-----------|-------|
| `adamw_8bit` | Reliable default; good for small-to-medium datasets.  Lower VRAM than full AdamW. |
| `prodigy_8bit` | Adaptive learning rate; may converge faster but can be harder to tune. |

### 7.5 VRAM-saving options

| Option | Effect | Trade-off |
|--------|--------|-----------|
| `low_vram: true` | Offloads parts of the model between steps | Slower training |
| `quantize: true` + `qtype: qfloat8` | 8-bit transformer weights | Minimal quality loss |
| `qtype: qfloat8_e4m3fn` | 8-bit using E4M3 format | Slightly more memory-efficient |
| `gradient_checkpointing: true` | Trades compute for VRAM | ~20% slower |
| Remove `1024` from resolution buckets | Smaller images | Loss of detail at high resolutions |

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| CUDA OOM at start | Too little VRAM | Remove 1024 bucket; set `low_vram: true`; try `qtype: qfloat8_e4m3fn` |
| CUDA OOM during sampling | Sample resolution too high | Lower `sample.width`/`height` to 768; reduce `sample_steps` to 15 |
| LoRA too weak | Under-trained | Increase `steps`; increase `linear` rank to 32; check trigger word is being injected |
| LoRA overfits / "bleeds" into all outputs | Over-trained | Use earlier checkpoint; reduce `steps`; lower rank; increase `weight_decay`; add DOP |
| Model download fails (403) | Gated model, no token | Run `huggingface-cli login` with a valid read token; accept license on HF |
| Trigger word not appearing | `cache_text_embeddings: true` | Set `cache_text_embeddings: false` |
| Loss spikes / training collapse | LR too high | Lower `lr` to 0.00005; switch from `prodigy_8bit` to `adamw_8bit` |

---

## 9. Inference (using the trained LoRA)

The output `.safetensors` file is a standard LoRA adapter.  Load it in:

- **ComfyUI**: Use a LoRA Loader node, typically at strength 0.8–1.2 for FLUX.2 Klein.
  Prompt with your trigger word: `"sks_char_neo a woman in a garden"`.
- **Diffusers**: Load via `PeftModel` or the diffusers LoRA loading APIs.
  Example: `pipe.load_lora_weights("path/to/lora.safetensors")`

Typical inference settings for the distilled 4B model:
- Sampler: FlowMatch
- Steps: 4–25 (the distilled model works well at very low step counts)
- Guidance scale: 3–4
- LoRA strength: 0.8–1.0

---

## 10. Key constraints & edge cases

1. **No UI needed**: The command `python run.py <config.yml>` is the sole entry point.
   The web UI (`http://localhost:8675`) is optional and unused in this guide.
2. **Min VRAM**: 16 GB on an NVIDIA GPU (RTX 4060 Ti 16GB / RTX 4080).  Training has
   been reported on 8 GB cards with very aggressive quantisation, but this is
   experimental.
3. **Disk space**: ~13 GB for the downloaded model, plus output checkpoints (~50–200 MB
   each for rank-32 LoRAs).
4. **Resumption**: Ctrl+C is safe *between* checkpoint saves.  Interrupting during a
   save corrupts that one checkpoint, but all previous ones remain intact.
5. **Dataset captions are never modified on disk** by the toolkit.  All trigger word
   manipulation is in-memory.
6. **The `default_caption` field also receives trigger word prepending.**  If an image
   has no `.txt` file and `default_caption: "a person"`, the effective caption during
   training will be `"sks_char_neo a person"`.
7. **Resolution buckets only downscale.**  A 2048×2048 image placed in a 1024 bucket
   becomes 1024×1024.  No upscaling ever occurs.
8. **Sample prompts in the config do NOT need the trigger word** — the same
   prepend/replace logic applies to them as it does to training captions.
```

This document is fully self-contained.  An LLM can use it to generate correct YAML configs, shell scripts, dataset preparation code, and troubleshooting advice for any `FLUX.2 Klein 4B` LoRA training workflow using the Ostris AI Toolkit.