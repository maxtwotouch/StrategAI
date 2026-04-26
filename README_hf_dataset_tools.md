# HF Dataset Tools

For a complete production checklist (generate -> curate -> HF export), see `processing/README_dataset_pipeline.md`.

Recommended workflow now uses two dataset versions:

- **Version 1 (generated):** raw output from `processing/source-data.py`.
- **Version 2 (hf_ready):** publishable export built only from assets whose PNG files still exist.

If you want to remove bad assets, simply delete the PNG files in the generated dataset, then run the HF export script.

Config files are centralized in `config/` (sibling of `processing/`):

- `config/DATASET-WORKFLOW.json`
- `config/BG-TILE-WORKFLOW.json`
- `config/prompt_templates.json`

This repo includes helpers for dataset publishing and maintenance:

- `processing/prepare_hf_dataset.py`: converts existing image + sidecar metadata into Hugging Face `imagefolder` layout.
- `processing/remove_bad_assets.py`: deletes bad assets by id (image + sidecar + optional `.txt`) and cleans JSONL manifests.
- `processing/extract_prompt_templates.py`: extracts shared prompt templates from prompt-pack JSONL into a structured JSON file.

## 1) Prepare a publishable Hugging Face dataset

Expected source layout (either form is supported):

- `<dataset_root>/images` + `<dataset_root>/metadata`
- `<dataset_root>/generated/images` + `<dataset_root>/generated/metadata`

Output layout:

- `<out_dir>/images/*.png`
- `<out_dir>/images/*.txt` (caption files colocated with images; default uses generation prompts)
- `<out_dir>/metadata.jsonl` (contains `file_name`, `text`, and selected extra fields)
- optional: `<out_dir>/metadata/*.json` (trimmed sidecars)

Default extra fields are now minimal and training-focused: `asset_family`, `domain`, `object_class`.
Generation controls like seed/guidance are intentionally excluded.

By default, exported IDs are linearized (`0000001`, `0000002`, ...) so output naming is stable and independent of UUID-based source ids.

Example:

```bash
python3 processing/prepare_hf_dataset.py ./dataset --out-dir ./dataset/hf_ready --link-mode hardlink --write-trimmed-sidecars
```

Merge multiple datasets into one HF export (processed in the exact order listed):

```bash
python3 processing/prepare_hf_dataset.py ./dataset_a ./dataset_b --out-dir ./dataset/hf_ready_merged --link-mode hardlink
```

If some metadata sidecars remain but their PNG was deleted, they are skipped by default (not treated as hard errors).

Optional strict behavior (fail when a metadata row points to a missing image):

```bash
python3 processing/prepare_hf_dataset.py ./dataset --out-dir ./dataset/hf_ready --fail-on-missing-image
```

Optional strict duplicate-id guard:

```bash
python3 processing/prepare_hf_dataset.py ./dataset --out-dir ./dataset/hf_ready --fail-on-duplicate-id
```

Notes:

- `--link-mode hardlink` avoids duplicating image bytes when possible.
- Use `--link-mode copy` when you want a fully standalone export folder.
- `metadata.jsonl` is ready for Hugging Face `imagefolder` publishing.
- Caption `.txt` files are written by default for LoRA training compatibility.
- Caption `.txt` content defaults to the original generation prompt (from metadata or embedded PNG prompt fields).
- Use `--skip-captions-txt` to disable `.txt` sidecar generation.
- Use `--keep-source-ids` to preserve original ids instead of sequential ids.
- Use `--include-source-id` to add original source ids to metadata rows for traceability.
- Use `--caption-source metadata_caption` to use metadata caption text instead of generation prompt text.

## 2) Remove bad assets safely by id

This is optional. If you prefer, you can delete only PNGs manually and skip this tool.

Delete files by id (removes both image and metadata sidecar together):

```bash
python3 processing/remove_bad_assets.py ./dataset 0002000_1e353e54 0002045_607e161f
```

Using an ids file:

```bash
python3 processing/remove_bad_assets.py ./dataset --ids-file ./bad_ids.txt
```

Dry run first:

```bash
python3 processing/remove_bad_assets.py ./dataset --ids-file ./bad_ids.txt --dry-run
```

The script also filters known JSONL files (`metadata.jsonl`, `dataset_manifest.jsonl`, `manifest_full.jsonl`) so deleted ids do not linger in manifests.

## 3) Generate directly in HF-friendly format

`processing/source-data.py` now supports direct HF-friendly output:

```bash
python3 processing/dataset_generator.py \
  --workflow-api-json ./config/DATASET-WORKFLOW.json \
  --tile-workflow-api-json ./config/BG-TILE-WORKFLOW.json \
  --prompt-node 100 \
  --tile-prompt-node 100 \
  --output-layout huggingface \
  --sidecar-profile publishable \
  --training-text-style short \
  --emit-hf-metadata
```

`processing/prompt-pack.py` uses `config/prompt_templates.json` by default.

This writes:

- `<base_dir>/images/*.png`
- `<base_dir>/metadata/*.json` (trimmed sidecars)
- `<base_dir>/metadata.jsonl` (HF imagefolder metadata)

`--output-layout generated` keeps the old `generated/` style while still allowing `--emit-hf-metadata`.

`source-data.py` now defaults to trimmed sidecars (`--sidecar-profile publishable`) so prompt-heavy fields are not duplicated in JSON metadata. Seed/guidance are also excluded from publishable sidecars and HF metadata rows.

If you still need full legacy records for audit/debugging:

```bash
python3 processing/dataset_generator.py ... --sidecar-profile full
```

## Prompt choice for HF fine-tuning

Recommended: store the prompt text you want the model to learn as `text` (short, target caption), not the full generation scaffold.

- `--training-text-style short` (recommended): compact training target text.
- `--training-text-style positive_prompt`: full input prompt from generation.
- `--training-text-style build_caption`: legacy concatenated caption style.

## Minimal two-version flow (recommended)

1) Generate dataset (version 1):

```bash
python3 processing/dataset_generator.py ... --output-layout generated
```

2) Manually delete bad PNGs from `generated/images/`.

3) Export publishable dataset (version 2):

```bash
python3 processing/prepare_hf_dataset.py ./dataset --out-dir ./dataset/hf_ready --link-mode hardlink
```

