# LoRA Training Guide

How to prepare a dataset and fine-tune FLUX.2 Klein 4B LoRA adapters using the [Ostris AI Toolkit](https://github.com/ostris/ai-toolkit).

## Prerequisites

1. Install the Ostris AI Toolkit:
   ```bash
   git clone https://github.com/ostris/ai-toolkit.git
   cd ai-toolkit
   git submodule update --init --recursive
   python -m venv venv && source venv/bin/activate
   pip install torch && pip install -r requirements.txt
   ```

2. Authenticate with Hugging Face (model is gated):
   ```bash
   huggingface-cli login
   ```
   Accept the license at [black-forest-labs/FLUX.2-klein-4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B).

3. Install this repo's dependencies (from the project root):
   ```bash
   # Option A — quick start:
   pip install -r requirements.txt

   # Option B — editable install + console commands (recommended):
   pip install -e .
   ```
   See the [README Setup section](../README.md#setup) for details.

## Pipeline Steps

Start after dataset generation (see [`docs/generation.md`](generation.md)). You should have `dataset/hf/` populated with clean PNGs and a `metadata.jsonl` manifest.

### 1. Extract Sidecar Captions

Generates `.txt` caption files alongside each image, with trigger token injection.

```bash
extract-training-set

# Ratio-controlled sampling:
extract-training-set --total 120 --ratios structure=0.50,terrain=0.30,object=0.20

# Preview:
extract-training-set --dry-run
```

Produces:
```
dataset/hf/0000001.png
dataset/hf/0000001.txt   ← "[trigger] top-down view. A medieval granary..."
```

The tool reads `dataset/hf/metadata.jsonl`, injects `[trigger]` into captions, and writes `.txt` files alongside each image. At training time, the Ostris toolkit replaces `[trigger]` with `<tdp>`.

### 2. Validate Dataset

```bash
validate-dataset --mode sidecar_txt --dataset-root dataset/hf --image-dir .
```

Checks:
- Image existence, resolution, squareness
- Sidecar `.txt` caption existence and length
- Trigger token presence in captions
- Dataset balance (asset family bucket counts)

Output:
- `dataset/validation_report.ostris.json`
- `dataset/validation_issues.ostris.jsonl`

### 3. Derive Caption Variants (Optional)

Creates three caption-detail variants for the experiment matrix.

```bash
derive-captions
```

| Variant | Format | Use Case |
|---------|--------|----------|
| `detailed/` | `[trigger] top-down view. [full description]` | Rich conditioning, risk of style binding |
| `minimal/` | `[trigger] top-down view. A medieval [category].` | Balanced: category signal, minimal style |
| `ultra_minimal/` | `[trigger] top-down view.` | Pure image-driven learning, risk of mode collapse |

Output: `dataset/derived/detailed/`, `dataset/derived/minimal/`, `dataset/derived/ultra_minimal/` — each with symlinks to original PNGs + new `.txt` files.

### 4. Sync Validation Prompts

The toolkit generates sample images during training. Keep prompts anchored to actual captions.

```bash
sync-validation-prompts --max-prompts 6
```

Reads captions from your dataset and writes them into `config/training/lora_4b_*.yaml` under sample prompts.

### 5. Train

Single experiment:
```bash
cd /path/to/ai-toolkit
source venv/bin/activate
python run.py /path/to/this/repo/config/training/lora_4b_detailed_high.yaml
```

Batch launch (all 6 experiments):
```bash
export OSTRIS_TOOLKIT=/path/to/ai-toolkit
bash scripts/train_experiments.sh
```

## Trigger Token System

**`<tdp>`** — the trigger token. Configured in `config/training/*.yaml` as `trigger_word`, injected by the Ostris toolkit at training time. The angle phrase `top-down view.` is embedded in every caption to bind the overhead perspective to the token.

At inference, always start prompts with the trigger token followed by the angle phrase:
```
<tdp> top-down view. a medieval watchtower in gothic style, 16x16 pixel art, white background
```

How it works in the pipeline:
- **Training configs**: `trigger_word: <tdp>` — the toolkit automatically prepends it to captions
- **Source captions** in `metadata.jsonl`: bare natural language (no trigger, no `top-down view.`)
- **Sidecar `.txt` files**: `[trigger] top-down view. [description]` — the `[trigger]` placeholder gets replaced with `<tdp>` at train time, and `top-down view.` provides the angle command
- **At inference**: `<tdp> top-down view. [your description]` — both the trigger and the angle phrase must be present to activate the LoRA

## Caption Design

Flux2's text encoders work best with natural language sentences, not structured tags.

**Good:**
```
A medieval granary building in steampunk industrial style, with aged stone masonry, dark timber bracing, and reinforced buttresses. The structure has a weathered, heavily used appearance with a desaturated retro color palette.
```

**Avoid:**
```
pose:front, subject:medieval granary, style:steampunk industrial, 16x16 pixel art
```

The angle phrase is always `top-down view.` (replaced the old `Front view overhead elevated medium shot.`).

## Dataset Format

A dataset directory with images and matching `.txt` caption files:

```
dataset/hf/
├── 0000001.png
├── 0000001.txt
├── 0000002.png
├── 0000002.txt
└── ...
```

Images are never upscaled, only downscaled into resolution buckets (512, 768, 1024). Supported formats: `jpg`, `jpeg`, `png`.

## Experiment Matrix

6 experiments testing caption detail × LoRA rank. See [`docs/experiment-design.md`](experiment-design.md) for the full design rationale.

| # | Config | Caption | Linear Rank | Conv Rank | LR | Dropout |
|---|--------|---------|:-----------:|:---------:|-----|:-------:|
| 1 | `lora_4b_detailed_high.yaml` | detailed | 128 | 64 | 8e-5 | 0.05 |
| 2 | `lora_4b_detailed_low.yaml` | detailed | 64 | 32 | 8e-5 | 0.05 |
| 3 | `lora_4b_minimal_high.yaml` | minimal | 128 | 64 | 8e-5 | 0.1 |
| 4 | `lora_4b_minimal_low.yaml` | minimal | 64 | 32 | 8e-5 | 0.1 |
| 5 | `lora_4b_ultra_high.yaml` | ultra-minimal | 128 | 64 | 5e-5 | 0.0 |
| 6 | `lora_4b_ultra_low.yaml` | ultra-minimal | 32 | 16 | 5e-5 | 0.0 |

All configs: 2500 steps, adamw8bit, flowmatch scheduler, weighted timestep sampling, checkpoints every 200 steps.

## Training Parameters

| Parameter | Value |
|-----------|-------|
| Base model | `black-forest-labs/FLUX.2-klein-base-4B` |
| Method | LoRA |
| Steps | 2500 |
| Optimizer | adamw8bit |
| Scheduler | flowmatch |
| Timestep sampling | weighted |
| Resolution buckets | 512, 768, 1024 |
| Batch size | 1 |
| Weight decay | 1e-4 |

## Inference Settings

| Setting | Recommended |
|---------|:-----------:|
| Sampler | FlowMatch |
| Steps | 4–25 |
| Guidance scale | 3–4 |
| LoRA strength | 0.8–1.0 |
| Resolution | 1024×1024 (scales down) |

## License

- **Code** (`src/`, `scripts/`, `config/`): [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0)
- **Trained LoRA weights**: [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0)
- **Base model dependency**: This project fine-tunes [FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B), released under the [FLUX DiT License](https://huggingface.co/black-forest-labs/FLUX.2-dev/blob/main/LICENSE.md). Users must accept that license on Hugging Face before downloading the base model.
- **Dataset generation dependency**: The dataset was generated using [Flux-2-Multi-Angles-LoRA-v2](https://huggingface.co/lovis93/Flux-2-Multi-Angles-LoRA-v2). Generated images are subject to that LoRA's license terms and the FLUX DiT License. Review both before redistributing generated datasets.
- Include attribution to Black Forest Labs in published model cards.
