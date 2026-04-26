# Dataset Pipeline Guide (Generated -> HF Ready)

This guide describes the production flow for this repo:

- **Version 1: generated dataset** from `processing/source-data.py`
- **Version 2: hf_ready dataset** from `processing/prepare_hf_dataset.py`

The intended curation workflow is simple: **delete bad PNG files in version 1**, then export version 2 from the remaining assets.

## Config layout

Configuration lives in the top-level `config/` directory (sibling of `processing/`):

- `config/DATASET-WORKFLOW.json`
- `config/BG-TILE-WORKFLOW.json`
- `config/prompt_templates.json`

## 0) Prerequisites

- Running ComfyUI endpoint reachable by `--comfy-url`
- Prompt pack JSONL available (for example from `processing/prompt-pack.py`)
- Workflow API JSON files available:
  - `config/DATASET-WORKFLOW.json`
  - `config/BG-TILE-WORKFLOW.json`

- Prompt template JSON available:
  - `config/prompt_templates.json`

## 0.5) Extract prompt templates (optional but recommended)

You can extract shared prompt scaffolding from the prompt-pack into JSON:

```bash
python3 processing/extract_prompt_templates.py \
  ./dataset/prompts/medieval_prompt_pack.jsonl \
  --out-json ./dataset/prompts/prompt_templates.json
```

This writes grouped templates with:

- common prefix
- common suffix
- merged template string (`{PROMPT_BODY}` placeholder)
- variable prompt examples and basic stats

The output JSON includes prompt-pack-compatible fields:

- `templates.structure`
- `templates.background_tile`

Use these template fields when generating prompt packs:

```bash
python3 processing/prompt_generator.py \
  --out-dir ./dataset/prompts \
  --templates-json ./dataset/prompts/prompt_templates.json
```

## 1) Generate Version 1 (raw generated dataset)

Run `source-data.py` to create images and trimmed metadata sidecars.

```bash
python3 processing/dataset_generator.py \
  --comfy-url http://localhost:9000 \
  --base-dir ./dataset \
  --prompt-pack ./dataset/prompts/medieval_prompt_pack.jsonl \
  --workflow-api-json ./config/DATASET-WORKFLOW.json \
  --tile-workflow-api-json ./config/BG-TILE-WORKFLOW.json \
  --prompt-node 100 \
  --tile-prompt-node 100 \
  --output-layout generated \
  --sidecar-profile publishable \
  --training-text-style short
```

Output (version 1):

- `dataset/generated/images/*.png`
- `dataset/generated/metadata/*.json`
- `dataset/generated/dataset_manifest.jsonl`
- `dataset/generated/run_report.json`

Notes:

- Publishable sidecars are intentionally minimal.
- Seed/guidance are not emitted in publishable metadata.
- ComfyUI generation details remain embedded in PNG metadata.

## 2) Curate by deleting bad PNG files

Delete bad images directly from the generated images folder.

```bash
# example: remove two bad assets by PNG filename
rm -f ./dataset/generated/images/0002000_1e353e54.png
rm -f ./dataset/generated/images/0002045_607e161f.png
```

You can also use the helper if you want ID-based coordinated cleanup:

```bash
python3 processing/remove_bad_assets.py ./dataset --ids-file ./bad_ids.txt
```

## 3) Build Version 2 (HF-ready export)

Export only non-deleted assets into Hugging Face `imagefolder` layout.

```bash
python3 processing/prepare_hf_dataset.py \
  ./dataset \
  --out-dir ./dataset/hf_ready \
  --link-mode hardlink \
  --write-trimmed-sidecars
```

Merge multiple curated datasets into one HF export (in the listed order):

```bash
python3 processing/prepare_hf_dataset.py \
  ./dataset_a \
  ./dataset_b \
  --out-dir ./dataset/hf_ready_merged \
  --link-mode hardlink
```

Output (version 2):

- `dataset/hf_ready/images/*.png` (sequential names by default: `0000001.png`, `0000002.png`, ...)
- `dataset/hf_ready/images/*.txt` (generation prompt captions, same basename as each PNG)
- `dataset/hf_ready/metadata.jsonl`
- optional: `dataset/hf_ready/metadata/*.json`
- `dataset/hf_ready/prepare_hf_report.json`

Behavior details:

- Missing PNG files are skipped by default (treated as intentional deletions).
- Caption `.txt` files are written by default for LoRA fine-tuning workflows.
- Caption `.txt` content defaults to the prompt that generated each asset.
- IDs are linearized by default during export, independent of source UUID ids.
- Add `--include-source-id` if you want original IDs preserved as a metadata field for traceability.
- Use strict missing-image validation when needed:

```bash
python3 processing/prepare_hf_dataset.py ./dataset --out-dir ./dataset/hf_ready --fail-on-missing-image
```

- Use strict duplicate-id validation when needed:

```bash
python3 processing/prepare_hf_dataset.py ./dataset --out-dir ./dataset/hf_ready --fail-on-duplicate-id
```

- If you only want `metadata.jsonl` and no `.txt` sidecars:

```bash
python3 processing/prepare_hf_dataset.py ./dataset --out-dir ./dataset/hf_ready --skip-captions-txt
```

- Preserve source ids/filenames instead of sequential ids:

```bash
python3 processing/prepare_hf_dataset.py ./dataset --out-dir ./dataset/hf_ready --keep-source-ids
```

## 4) Validate the HF-ready metadata

Quick row count check:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('./dataset/hf_ready/metadata.jsonl')
rows = [line for line in p.read_text(encoding='utf-8').splitlines() if line.strip()]
print({'rows': len(rows)})
PY
```

Optional check that every metadata row points to an existing image:

```bash
python3 - <<'PY'
import json
from pathlib import Path
root = Path('./dataset/hf_ready')
missing = []
for line in (root / 'metadata.jsonl').read_text(encoding='utf-8').splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    if not (root / row['file_name']).exists():
        missing.append(row['file_name'])
print({'missing_count': len(missing)})
PY
```

## 5) Upload to Hugging Face

After validation, upload `dataset/hf_ready` to your HF dataset repo using your preferred workflow (web upload, git-lfs, or huggingface_hub CLI/API).

Recommended metadata row shape in `metadata.jsonl`:

- `file_name`
- `text`
- optional: `source_id` (original id before linearization, enabled via `--include-source-id`)
- optional categorical fields such as `asset_family`, `domain`, `object_class`

Avoid training-noise fields in HF metadata (such as generation seed/guidance), since those are not training targets.

## 6) Next step: Osiris AI FLUX2 fine-tuning

This pipeline now outputs LoRA-ready assets (`.png` + colocated `.txt`) and clean metadata for downstream training.
The next phase is wiring these outputs into your Osiris AI toolkit fine-tuning workflow for FLUX2.

