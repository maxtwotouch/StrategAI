# Top-Down Medieval Pixel Art — FLUX.2 Klein LoRA

Training configs and dataset utilities for fine-tuning a FLUX.2 Klein LoRA on top-down medieval pixel art assets using the [Ostris AI Toolkit](https://github.com/ostris/ai-toolkit).

## What This Project Is

- **Training configs** (`config/lora_4b.yaml`, `config/lora_9b.yaml`) — ready-to-run Ostris ai-toolkit YAML files
- **Caption generator** (`src/extract_training_set.py`) — generates sidecar `.txt` caption files from HF JSONL metadata, with trigger token injection
- **Dataset validator** (`src/validate_dataset.py`) — checks your dataset before training (supports both JSONL and sidecar `.txt` modes)
- **Prompt sync tool** (`src/sync_validation_prompts.py`) — pulls sample prompts from your dataset captions
- **Metadata combiner** (`src/combine_metadata.py`) — merges per-item JSON files into a JSONL

## What the Ostris AI Toolkit Handles

The toolkit does the actual training. You pass it a YAML config, it handles:

- Trigger word injection (`trigger_word` prepended to captions at training time)
- Resolution bucketing
- Checkpoint saving / pruning
- Sample generation during training
- Training resumption
- LoRA network training
- Model quantization, gradient checkpointing, optimizers, schedulers

**You do not need custom Python to train.** The toolkit is the trainer. This repo is config + validation + workflow helpers.

## Trigger Token: `<tdmp>`

This project uses `<tdmp>` as the trigger token. The angle brackets help Flux2's text encoders treat it as a distinct concept token.

**Captions SHOULD contain the trigger word** (or the `[trigger]` placeholder which the toolkit replaces at training time). This ensures the model binds unexplained pixel information (style + camera pose) to the token.

- **Source captions** in `metadata.jsonl`: use bare natural language (no trigger)
- **Generated sidecar `.txt` files**: `extract_training_set.py` injects `[trigger]` by default
- **At training time**: the toolkit replaces `[trigger]` with `<tdmp>` (from `trigger_word` in config)
- **At inference**: always start your prompt with `<tdmp>` to activate the LoRA

```
<tdmp> a medieval granary in steampunk industrial style, top-down pixel art 16x16, white background
```

## Natural Language Captions

Flux2's text encoders work best with natural language. Write captions as descriptive sentences rather than structured key-value pairs:

**Good (natural language):**
```
A medieval granary building in steampunk industrial style, with aged stone masonry, dark timber bracing, and reinforced buttresses. Top-down front view, isolated on a white background. 16x16 pixel art, crisp edges, no anti-aliasing.
```

**Avoid (structured tags):**
```
pose:front, subject:medieval granary, style:steampunk industrial, top-down pixel art 16x16
```

The trigger token `<tdmp>` is injected by the toolkit at training time, so your source captions should be pure natural language descriptions.

## Project Layout

```
.
├── config/
│   ├── lora_4b.yaml          # Training config for FLUX.2 Klein 4B
│   └── lora_9b.yaml          # Training config for FLUX.2 Klein 9B
├── dataset/
│   ├── metadata.jsonl        # HF-style metadata (id, file_name, text, asset_family)
│   ├── images/               # Image files + generated .txt sidecar captions
│   └── metadata/             # Optional: per-item JSON files (combined by combine_metadata.py)
├── src/
│   ├── extract_training_set.py  # Generate sidecar .txt captions from JSONL, with trigger injection
│   ├── validate_dataset.py   # Dataset validation (structure, images, captions, balance)
│   ├── sync_validation_prompts.py  # Sync sample prompts from dataset captions into config
│   └── combine_metadata.py   # Merge dataset/metadata/*.json → dataset/metadata.jsonl
├── scripts/
│   ├── validate_dataset.sh   # Wrapper for validate_dataset.py
│   ├── sync_validation_prompts.sh  # Wrapper for sync_validation_prompts.py
│   └── extract_training_set.sh  # Wrapper for extract_training_set.py
├── tests/                    # pytest unit tests
├── README.md                 # This file — project overview and quick-start
├── dataset-sampling.md       # Guide for ratio-controlled extraction
├── PUBLISHING.md             # Model card template and publishing checklist
├── LICENSE                   # MIT license for repo tooling
└── requirements.txt          # Python dependencies
```

## Prerequisites

1. Install the [Ostris AI Toolkit](https://github.com/ostris/ai-toolkit) and authenticate with Hugging Face:
   ```bash
   huggingface-cli login
   ```
2. Install this repo's dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Dataset Format

The standard workflow starts with a Hugging Face-style JSONL metadata file and generates sidecar `.txt` captions from it.

### Step 1: Download from Hugging Face (JSONL)

Your HF dataset download gives you `metadata.jsonl` with one JSON object per line:

```json
{"id": "0000001", "file_name": "images/0000001.png", "text": "A medieval granary building in steampunk industrial style, with aged stone masonry and dark timber bracing. Top-down front view, isolated on white. 16x16 pixel art.", "asset_family": "structure"}
```

Required keys: `id`, `file_name`, `text`. Optional: `asset_family` (used for balance reporting).

### Step 2: Generate Sidecar Caption Files

Run the extraction tool to write `.txt` caption files alongside each image, with the trigger injected:

```bash
./scripts/extract_training_set.sh
```

This produces:
```
dataset/images/
├── 0000001.png
├── 0000001.txt   ← "A medieval granary..." with [trigger] injected
├── 0000002.png
├── 0000002.txt
└── ...
```

The configs already point at `dataset/images/` with `caption_ext: txt`, so after generating sidecar files, you're ready to train.

If you have per-item JSON files in `dataset/metadata/`, first combine them:

```bash
python3 -m src.combine_metadata
```

## Workflow

### 1. Generate Sidecar Captions

```bash
# Generate .txt sidecar files for all images (with [trigger] placeholder)
./scripts/extract_training_set.sh

# Or filter by ratio-controlled sampling
./scripts/extract_training_set.sh --total 120 --ratios structure=0.50,terrain=0.30,object=0.20,background=0.10

# Preview without writing files
./scripts/extract_training_set.sh --dry-run
```

The tool reads `dataset/metadata.jsonl`, injects `[trigger]` into captions, and writes `.txt` files alongside each source image. See `dataset-sampling.md` for full details.

### 2. Validate Dataset

```bash
./scripts/validate_dataset.sh
```

Checks:
- Image existence, resolution, squareness
- Sidecar `.txt` caption existence and length
- Trigger token presence in captions (expected by default)
- Dataset balance (asset family bucket counts)

Outputs:
- `dataset/validation_report.ostris.json`
- `dataset/validation_issues.ostris.jsonl`

You can also validate the raw JSONL before generating sidecar files:

```bash
./scripts/validate_dataset.sh --mode hf_jsonl
```

### 3. Sync Validation Prompts

The toolkit generates sample images during training using prompts from `config.sample.samples`. Keep them anchored to your actual captions:

```bash
./scripts/sync_validation_prompts.sh --max-prompts 6
```

This reads your dataset captions and writes them into `config/lora_4b.yaml` under `config.sample.samples`.

> **Note:** The `sync_validation_prompts.sh` script prepends `[trigger]` to sample prompts by default. The toolkit replaces `[trigger]` with `<tdmp>` at training time, matching caption behavior.

### 4. Train

```bash
# 4B (default)
cd /path/to/ai-toolkit
python run.py /path/to/this/repo/config/lora_4b.yaml

# 9B
cd /path/to/ai-toolkit
python run.py /path/to/this/repo/config/lora_9b.yaml
```

On first run, the toolkit downloads the base model from Hugging Face (~13 GB for 4B).

Checkpoints and samples are written to `./output/flux2_klein_4b_lora/` (or whatever `training_folder` is set to in the config).

### 5. Resume Training

Re-run the same command. The toolkit resumes from the last saved checkpoint.

Press Ctrl+C to stop. **Wait for the current checkpoint to finish saving** before killing the process.

## Config Reference

Key fields in `config/lora_4b.yaml`:

| Field | Value | Notes |
|-------|-------|-------|
| `trigger_word` | `<tdmp>` | Bracketed token. Captions should contain `[trigger]` — toolkit replaces at train time. Use `<tdmp>` in inference. |
| `network.linear` | `128` | LoRA rank. Higher capacity for dual-concept (style + camera pose). |
| `network.conv` | `64` | Conv rank. Captures spatial/camera relationships. |
| `train.steps` | `2500` | Total optimizer steps. More steps for dual-concept convergence. |
| `train.lr` | `0.00008` | Learning rate. Slightly below default to balance gradient competition. |
| `train.timestep_type` | `weighted` | Standard balanced training noise schedule. |
| `train.weight_decay` | `0.0001` | Prevents memorization; moderate to preserve style. |
| `save.save_every` | `200` | Checkpoint frequency for evaluation. |
| `train.cache_text_embeddings` | `false` | **Must be false** when using `trigger_word` or `caption_dropout_rate`. |
| `datasets[0].folder_path` | `./dataset/images` | Point at your image directory. |
| `sample.samples` | `[...]` | Validation prompts prefixed with `[trigger]`. Synced via `sync_validation_prompts.py`.

## Inference

Load the trained `.safetensors` checkpoint in ComfyUI, diffusers, or any LoRA-compatible inference tool.

Prompt with your trigger token:

```
<tdmp> a medieval granary in steampunk industrial style, top-down pixel art 16x16, white background
```

Typical settings for FLUX.2 Klein 4B:
- Sampler: FlowMatch
- Steps: 4–25
- Guidance scale: 3–4
- LoRA strength: 0.8–1.0

## Caption Guidelines

For top-down pixel art training with Flux2:

1. **Use natural language** — write descriptive sentences, not structured tags
2. **Source captions are trigger-free** — `metadata.jsonl` captions are bare; `[trigger]` is injected at extraction time
3. **Describe what you see** — subject, style, materials, condition, perspective
4. **Include technical specs** — "16x16 pixel art", "crisp edges", "top-down view"
5. **Keep under ~420 characters** when possible for stable conditioning

Example source caption (in `metadata.jsonl`):

```
A medieval granary building in steampunk industrial style, with aged stone masonry, dark timber bracing, and reinforced buttresses. The structure has a weathered, heavily used appearance with a desaturated retro color palette. Top-down front view, isolated on a white background. 16x16 pixel art, crisp edges, no anti-aliasing.
```

Generated sidecar caption (auto-generated with `[trigger]`):

```
[trigger] A medieval granary building in steampunk industrial style...
```

At inference:

```
<tdmp> a medieval granary in steampunk industrial style, top-down pixel art 16x16, white background
```

## Running Tests

```bash
pip install pytest
python3 -m pytest tests/ -v
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| CUDA OOM | Lower batch size, use 4B instead of 9B, enable `gradient_checkpointing`, remove `1024` from resolution buckets |
| Trigger token not working | Check `cache_text_embeddings: false` in config |
| Weak style separation | Improve per-style balance, use more descriptive natural language captions |
| Overfitting | Use earlier checkpoint, reduce `steps`, lower rank |
| Model download fails (403) | Run `huggingface-cli login` with a valid token; accept license on HF |
