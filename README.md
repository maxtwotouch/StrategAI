# TopDownMedievalPixelArt Dataset Pipeline

This is the **single source of truth** for dataset generation, curation, and Hugging Face export in this repository.

If you see older README files, treat this file as canonical.

## What This Repo Produces

The pipeline is intentionally split into two dataset versions:

1. **Version 1 (`generated`)**
   - Raw generated images and minimal sidecar metadata.
   - Used for visual review and curation (delete bad PNGs).

2. **Version 2 (`hf_ready`)**
   - Clean export for Hugging Face `imagefolder` publishing and fine-tuning.
   - Produced only from assets whose PNGs still exist after curation.

## Repository Map (What Is Where)

- `src/dataset_generator.py`
  - Calls ComfyUI workflows and writes Version 1 dataset.
- `src/prompt_generator.py`
  - Builds prompt-data JSONL input used by the generator.
- `src/extract_prompt_templates.py`
  - Extracts reusable prompt templates from an existing prompt-data.
- `src/prepare_hf_dataset.py`
  - Converts Version 1 data into Version 2 (`hf_ready`).
- `src/validate_hf_export.py`
  - Validates `hf_ready` exports before publishing (CI-friendly reports and exit codes).
- `src/remove_bad_assets.py`
  - Optional helper to remove assets by ID and clean manifests.
- `config/DATASET-WORKFLOW.json`
  - Primary ComfyUI workflow for non-tile assets.
- `config/BG-TILE-WORKFLOW.json`
  - ComfyUI workflow for background tiles.
- `config/prompt_templates.json`
  - Prompt templates for prompt generation.
- `dataset/`
  - Working data root (prompts, generated dataset, hf export).
- `scripts/run_dataset.sh`
  - Example generator command.

## Prerequisites

- A running ComfyUI endpoint reachable by `--comfy-url`.
- Prompt data JSONL (for example from `src/prompt_generator.py`).
- Workflow API JSON files in `config/`.

### Required LoRas
- [lovis93/Flux-2-Multi-Angles-LoRA-v2](https://huggingface.co/lovis93/Flux-2-Multi-Angles-LoRA-v2)

### Required ComfyUI Nodes
Should be located under `ComfyUI/custom_nodes/` - see each node repo for installation instructions.
- [
dimtoneff/ComfyUI-PixelArt-Detector
](https://github.com/dimtoneff/ComfyUI-PixelArt-Detector)
- [Loewen-Hob/rembg-comfyui-node-better](https://github.com/Loewen-Hob/rembg-comfyui-node-better)

## End-to-End Flow

### 0) (Optional) Generate prompt data

```bash
python3 src/prompt_generator.py \
  --out-dir ./dataset/prompts \
  --templates-json ./config/prompt_templates.json
```

### 1) Generate Version 1 dataset

```bash
python3 src/dataset_generator.py \
  --comfy-url http://127.0.0.1:8188 \
  --base-dir ./dataset \
  --prompt-data ./dataset/prompts/generated_prompts.jsonl \
  --workflow-api-json ./config/structure_workflow.json \
  --tile-workflow-api-json ./config/background_tile_workflow.json \
  --prompt-node 100 \
  --tile-prompt-node 100 \
  --output-layout generated
```

Output:

- `dataset/generated/images/*.png`
- `dataset/generated/metadata/*.json`
- `dataset/generated/dataset_manifest.jsonl`
- `dataset/generated/run_report.json`

### 2) Curate quality (delete bad images)
Delete bad PNGs from `dataset/generated/images/` by visual review. `prepare_hf_dataset.py` will only include assets whose PNGs still exist in the next step, so this is the main curation mechanism.

### 3) Export Version 2 (`hf_ready`)

```bash
python3 src/prepare_hf_dataset.py \
  ./dataset \
  --out-dir ./dataset/hf_ready \
  --link-mode hardlink \
  --write-trimmed-sidecars
```

Output:

- `dataset/hf_ready/images/*.png`
- `dataset/hf_ready/images/*.txt`
- `dataset/hf_ready/metadata.jsonl`
- `dataset/hf_ready/prepare_hf_report.json`
- optional: `dataset/hf_ready/metadata/*.json`

### 4) Validate export before publish

```bash
python3 src/validate_hf_export.py ./dataset/hf_ready
```

By default, this writes:

- `dataset/hf_ready/validation_report.json`
- `dataset/hf_ready/validation_issues.jsonl`

Useful strict modes:

```bash
python3 src/validate_hf_export.py ./dataset/hf_ready --require-caption-txt
python3 src/validate_hf_export.py ./dataset/hf_ready --require-caption-txt --fail-on-warnings
python3 src/validate_hf_export.py ./dataset/hf_ready --skip-orphan-check
```

## Metadata Contracts

### Version 1 sidecar schema (`dataset/generated/metadata/*.json`)

Each generated asset sidecar contains:

- `asset_family`
- `id`
- `image_path`
- `positive_prompt`

This is the required minimal metadata contract for reproducible export.

### Version 2 HF metadata schema (`dataset/hf_ready/metadata.jsonl`)

Rows include:

- `id`
- `file_name`
- `text`
- optional `source_id` (when `--include-source-id` is enabled)
- default extra categorical fields: `asset_family`

`text` is read from ComfyUI PNG metadata when available; otherwise it falls back to sidecar `positive_prompt`.

## Reproducibility and Fine-Tuning Notes

- Use fixed prompt-data inputs and pinned workflow JSON files in `config/`.
- Keep generation controls (seed/guidance) in PNG metadata, not HF metadata rows.
- Curate by deleting PNGs only, then regenerate `hf_ready` from remaining assets.
- Prefer `--link-mode hardlink` for fast exports without extra storage duplication.
- Use `--fail-on-missing-image` and `--fail-on-duplicate-id` for stricter CI-style validation.

## Frequently Used Export Flags

```bash
python3 src/prepare_hf_dataset.py ./dataset --out-dir ./dataset/hf_ready --fail-on-missing-image
python3 src/prepare_hf_dataset.py ./dataset --out-dir ./dataset/hf_ready --fail-on-duplicate-id
python3 src/prepare_hf_dataset.py ./dataset --out-dir ./dataset/hf_ready --skip-captions-txt
python3 src/prepare_hf_dataset.py ./dataset --out-dir ./dataset/hf_ready --keep-source-ids
```

## License

### Code (this repository)
The pipeline scripts and configuration in this repository are provided as-is for educational and research purposes.

### Generated Dataset
**All images in this dataset were generated using third-party models and are bound by their respective licenses.**

- **Base model**: [Black Forest Labs FLUX.2 [dev]](https://huggingface.co/black-forest-labs/FLUX.2-dev) — outputs are subject to the [FLUX Non-Commercial License](https://huggingface.co/black-forest-labs/FLUX.2-dev/blob/main/LICENSE.md).
- **LoRA**: [lovis93/Flux-2-Multi-Angles-LoRA-v2](https://huggingface.co/lovis93/Flux-2-Multi-Angles-LoRA-v2) — subject to the license terms published by the LoRA author.

Because the dataset is derived from these models, **the generated images and captions must comply with the most restrictive of the above licenses**. This typically means:
- **Non-commercial use only** (unless you have a commercial license for FLUX.2 [dev]).
- You may not use the dataset to train competing models in violation of the base model license.
- You may not remove or alter license metadata when redistributing the dataset.

Before using this dataset for any purpose, review the current license terms of both the base model and the LoRA on Hugging Face.
