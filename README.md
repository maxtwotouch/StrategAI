# Flux2 Klein (4B/9B) LoRA Fine-Tuning with Ostris ai-toolkit

This repository gives you a practical, beginner-friendly pipeline for training one Flux2 Klein LoRA from your dataset in `dataset/`.

This README is optimized for your current goal:
- one fixed pose
- multiple visual styles
- one single LoRA that learns style differences while keeping pose stable

> **Important:** ai-toolkit command shapes can differ by version. This repo supports command templates through environment variables (`OSTRIS_TRAIN_COMMAND`, `OSTRIS_INFER_COMMAND`).

## Ostris Flux Conformance Checklist

Use this quick checklist before any real training run:

- [ ] base model is a Flux2 Klein model ID in `config/model_flux2_klein_4b.yaml` or `config/model_flux2_klein_9b.yaml`
- [ ] dataset uses either HF JSONL metadata or image-sidecar `.txt` captions (`caption_source` in `config/data.yaml`)
- [ ] all commands use `config/` (this is the canonical config folder)
- [ ] validation prompts are anchored to the same caption style used for training
- [ ] generated run file `runs/<run_name>/ostris_train.yaml` is created by `src/train_lora.py`

## Quick Answer: One Pose + Several Styles

If pose is fixed, you need less data than multi-pose training. Focus on **style balance** and **caption consistency**.

| Goal | Minimum | Good | Strong |
|------|---------|------|--------|
| Images per style | 30-50 | 80-150 | 200+ |

Rule of thumb:
- `total_images = number_of_styles × images_per_style`
- Example: 12 styles × 100 each = `1,200` images

For one-pose/multi-style, quality and balance matter more than raw scale.

## Project Layout

| Path                                | Purpose |
|-------------------------------------|---------|
| `dataset/`                          | Dataset (`metadata.jsonl`, images, per-item metadata) |
| `config/data.yaml`                 | Dataset settings (source mode, trigger token, resolution, repeats, columns) |
| `config/model_flux2_klein_4b.yaml` | 4B model profile |
| `config/model_flux2_klein_9b.yaml` | 9B model profile |
| `config/run_lora.yaml`             | LoRA training hyperparameters |
| `src/validate_dataset.py`           | Dataset validation |
| `src/sample_dataset.py`             | Stratified metadata sampling by `asset_family` |
| `src/train_lora.py`                 | ai-toolkit config generation + train launcher |
| `src/infer_lora.py`                 | Sample generation from trained LoRA |
| `src/smoke_test.py`                 | Safe end-to-end dry-run test |
| `src/preflight_check.py`            | Readiness check before training |
| `scripts/*.sh`                      | Simple wrappers for common commands |
| `tests/`                            | Unit tests (pytest) |

## 1) Setup

```zsh
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 2) Configure Ostris ai-toolkit Commands

```zsh
cp .env.example .env
# Edit .env if your ai-toolkit installation uses different command syntax
source .env
```

Defaults:
- `OSTRIS_TRAIN_COMMAND=ai-toolkit train lora --config {config_path}`
- `OSTRIS_INFER_COMMAND=ai-toolkit infer text2img --base-model {base_model} --lora {adapter_path} --prompt {prompt} --num-images {num_images} --seed {seed} --output {output_dir}`

> **Tip:** `src/train_lora.py` auto-loads `.env` so you don't have to `source` it every time. But you still need to create it once.

## 3) Prepare Dataset for One Pose + Multi-Style

Your current dataset can train from either:
- `dataset/metadata.jsonl` (HF JSONL mode)
- `.txt` captions colocated with images, such as `dataset/images/0000001.png` + `dataset/images/0000001.txt` (sidecar mode)

Keep validation prompts in the same language style used for training captions.

Guidelines:
- **Keep pose concept constant** across the set if you train a one-pose LoRA
- **Keep style labels consistent** in wording (always use the same style phrase for the same look)
- **Maintain balanced image count per style** (avoid one dominant style)
- **Remove near-duplicates** and low-quality outliers
- **Avoid mixing caption styles** inside one run unless intentional
- **Keep captions ≤700 chars** for stable Flux2 conditioning

To auto-anchor validation prompts to real dataset captions:

```zsh
./scripts/sync_validation_prompts.sh --max-prompts 8
```

> This caps prompts at 420 characters — a safe default for Flux2. Pass `--max-chars 600` if you need longer.

## 4) Validate Dataset

```zsh
./scripts/validate_dataset.sh
```

Outputs:
- `dataset/validation_report.ostris.json`
- `dataset/validation_issues.ostris.jsonl`

The validator now checks:
- JSON structure and required keys
- Image existence, resolution, and squareness
- Caption length warnings
- **Dataset balance** (`asset_family` bucket counts)

To validate sidecar caption mode directly:

```zsh
./scripts/validate_dataset.sh --mode sidecar_txt --image-dir images --caption-txt-extension .txt
```

## 5) Pre-Flight Check (Recommended Before Every Run)

```zsh
./scripts/preflight_check.sh
```

This checks:
- All config files exist
- `.env` is present
- ai-toolkit CLI is accessible
- Dataset has enough images
- No missing image files
- Effective batch size and estimated epochs are printed

## 6) Select Model Size (4B or 9B)

Set `base_model_id` in:
- `config/model_flux2_klein_4b.yaml`
- `config/model_flux2_klein_9b.yaml`

Guidance:
- **4B**: easier and cheaper to run, good for first experiments
- **9B**: more capacity but typically higher VRAM/compute requirements

Wrappers support model switching via `MODEL_SIZE`:
- `MODEL_SIZE=4b` (default)
- `MODEL_SIZE=9b`

## 7) Tune Training Config

Main file: `config/run_lora.yaml`

Defaults are tuned for one-pose/multi-style starter training:
- `lora_rank: 32`
- `learning_rate: 0.0001`
- `num_train_steps: 1500`
- `optimizer: adamw_8bit` with `weight_decay: 0.01`
- validation prompts should be synced from your dataset captions for checkpoint selection

Main file: `config/data.yaml`
- `repeats: 1` (correct for larger datasets)
- increase repeats **only** when training set is very small
- `sampling.dataset_size`: optional fixed sample size for ratio-preserving experiments
- `sampling.stratify_column`: group field for ratio preservation (`asset_family`)
- `caption_source`: `metadata` (default) or `sidecar_txt`

### Custom tokens (trigger, pose, style, asset)

Tokens are `<angle-bracket>` identifiers that teach the LoRA to respond to specific
keywords at inference time. The most important one is the **trigger token** — a rare
token like `<tmp>` or `<mytoken>` that you'll use in your prompts to activate the
trained LoRA.

**How it works at training time:**

1. Configure your tokens in `config/data.yaml` under the `tokens:` block.
2. At launch, `train_lora.py` **prepends** every configured token to the start of
   every caption in the dataset (if `prepend_to_captions: true`).
3. Validation prompts in `run_lora.yaml` also get the trigger token prepended
   automatically — you don't need to hardcode tokens in your validation prompts.
4. The final captions are written to `runs/<run_name>/metadata.prepared.jsonl`
   so you can inspect exactly what the model was trained on.

**Example config (`config/data.yaml`):**

```yaml
tokens:
  trigger: "<tmp>"       # your LoRA's identity token
  pose: null             # optional, e.g. "<pose-topdown>"
  style: null            # optional, e.g. "<style-steampunk>"
  asset: null            # optional, e.g. "<asset-structure>"
  custom: []             # extra freeform tokens
  prepend_to_captions: true    # prepend tokens to every training caption
  validate_presence: true      # log a warning if tokens are missing from captions
```

**Result:** If your dataset caption is:

```
pose:front, subject:medieval blacksmith, style:weathered stone
```

and `tokens.trigger` is `<tmp>`, then at training time the caption becomes:

```
<tmp> pose:front, subject:medieval blacksmith, style:weathered stone
```

Tokens already present in a caption are **not duplicated**.

**Why inject at training time rather than baking tokens into source captions?**

The dataset lives in `dataset/` and describes *content* (pose, style, subject). The
trigger token is a *training artifact* — you might want `<tmp>` for one experiment
and `<medieval-lora>` for another. Injecting at training time keeps your dataset
portable and reusable. If you prefer to bake tokens directly into your source
captions, that works too — the pipeline skips duplicates automatically.

> **Tip:** Check `runs/<run_name>/metadata.prepared.jsonl` after a dry run to see
> exactly what captions ended up in training. No guessing required.

### Sidecar `.txt` training mode

To train directly from image-adjacent caption files, set:

```yaml
caption_source: sidecar_txt
image_dir: images
caption_txt_extension: .txt
```

Then run training normally; `src/train_lora.py` will assemble `metadata.prepared.jsonl` automatically for ai-toolkit.

### Quick tuning guide for beginners

| Symptom | Fix |
|---------|-----|
| OOM / CUDA out of memory | Lower `train_batch_size` to 1, use 4B, enable `gradient_checkpointing` |
| Style looks muddy or all the same | Increase per-style data, make `style:<name>` more explicit in captions |
| Pose drifts | Shorten captions, make pose description identical across all samples |
| Overfitting / memorization | Reduce `num_train_steps`, reduce `repeats`, use earlier checkpoint |
| Training is very slow | Reduce `gradient_accumulation_steps`, ensure images are 1024x1024 (not larger) |

## 8) Dataset Size Experiments (Stratified)

When you compare dataset sizes, keep `asset_family` ratios stable so results are fair.

### Standalone sampled metadata

```zsh
./scripts/sample_dataset.sh 1200
```

This writes:
- `sampled_datasets/metadata.1200.jsonl`
- `sampled_datasets/metadata.1200.report.json`

### Plug sampling directly into training

```zsh
./scripts/train_lora.sh --dataset-size 1200 --dry-run
```

This creates sampled metadata inside the run folder and auto-points the training config to it.

## 9) Run Smoke Test (Recommended)

```zsh
./scripts/smoke_test.sh
```

This verifies validator + config builder + dry-run train launch.

## 10) Launch Training

### Dry-run

```zsh
./scripts/train_lora.sh --dry-run
```

This command generates `runs/<run_name>/ostris_train.yaml` and `runs/<run_name>/train_command.sh` without launching training.
It also writes `runs/<run_name>/metadata.prepared.jsonl` (or sampled metadata) for transparent caption audit.

### Real run (4B default)

```zsh
./scripts/train_lora.sh
```

### Real run with stratified subset

```zsh
./scripts/train_lora.sh --dataset-size 2400
```

### Real run (9B)

```zsh
MODEL_SIZE=9b ./scripts/train_lora.sh
```

Generated run artifacts:
- `runs/<run_name>/ostris_train.yaml`
- `runs/<run_name>/train_command.sh`
- checkpoints/logs written by ai-toolkit

The launcher now prints:
- Dataset size and repeats
- Effective batch size
- Estimated epochs
- Warnings if your dataset is too small

### Resume training

```zsh
python3 -m src.train_lora \
  --data-config config/data.yaml \
  --model-config config/model_flux2_klein_4b.yaml \
  --run-config config/run_lora.yaml \
  --run-name flux2_klein_lora_v1 \
  --resume-from /absolute/path/to/checkpoint
```

## 11) Generate Evaluation Samples

```zsh
./scripts/run_eval_samples.sh /absolute/path/to/trained/lora_adapter
```

For 9B eval wrapper:

```zsh
MODEL_SIZE=9b ./scripts/run_eval_samples.sh /absolute/path/to/trained/lora_adapter
```

Custom prompt:

```zsh
python3 -m src.infer_lora \
  --model-config config/model_flux2_klein_4b.yaml \
  --adapter-path /absolute/path/to/lora_adapter \
  --prompt "<tmp> pose:front, subject:medieval blacksmith, style:weathered stone, top-down pixel art" \
  --num-images 8 \
  --output-dir eval_samples/custom
```

## 12) Validation Strategy for Best Checkpoint

For one-pose/multi-style training, evaluate on a fixed prompt grid:
- one prompt per style bucket
- 2-4 images per prompt

Prompt wording should match the caption style used in training data.

Choose best checkpoint by:
- **style separability** (styles look different from each other)
- **style consistency** (same style stays stable across subjects)
- **pose stability** (pose does not drift)

Do not always pick the final checkpoint. Often an intermediate checkpoint (around 60-80% of total steps) generalizes best.

## Caption Schema Recommendation

For one-pose/multi-style, a structured caption is easier to control than free-form prose:

```
<tmp> pose:front, subject:medieval granary, style:steampunk industrial, top-down pixel art 16x16, white background
```

Rules:
- `<tmp>` is your rare token trigger
- `pose:front` is identical across all captions (keeps pose stable)
- `style:X` varies per style (teaches the LoRA style differences)
- Keep total length under 420 characters when possible

## Running Tests

```zsh
pip install pytest ruff
python3 -m pytest tests/ -v
python3 -m ruff check src/ tests/
```

## Troubleshooting

| Problem | Cause & Fix |
|---------|-------------|
| `ai-toolkit: command not found` | Activate your ai-toolkit environment or update `.env` command templates. Run `./scripts/preflight_check.sh` to verify. |
| OOM / VRAM errors | Use 4B, lower batch size, lower LoRA rank, keep gradient checkpointing on. |
| Weak style separation | Improve per-style balance and make `style:<name>` tokens more explicit. |
| Overfitting look (repetition/memorization) | Reduce steps, reduce repeats, or stop at earlier checkpoint. |
| Sampling command fails with target size error | Ensure `--dataset-size` is less than or equal to total rows in `dataset/metadata.jsonl`. |
| `.env` not loading | `src/train_lora.py` auto-loads it now. If overriding, explicitly `source .env` before running. |

## Recommended Next Steps

1. **Curate one-pose data** into balanced style buckets (30+ per style minimum).
2. **Standardize captions** with fixed `pose:` and variable `style:` fields.
3. **Run pre-flight check:** `./scripts/preflight_check.sh`
4. **Run smoke test:** `./scripts/smoke_test.sh`
5. **Run a 4B baseline** first, then scale to 9B only if needed.
6. **Keep each run config/checkpoint tracked** in git or a run log.
