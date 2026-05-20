---
license: other
task_categories:
  - text-to-image
language:
  - en
pretty_name: Top-Down Medieval Pixel Art (Flux2 Klein LoRA)
size_categories:
  - n<1K
---

# Dataset Card: Top-Down Medieval Pixel Art

## Dataset Summary
This dataset is prepared for Flux2 Klein LoRA fine-tuning using the tooling in this repository.

Current structure:
- `metadata.jsonl`: one JSON object per sample
- `images/`: image assets
- `metadata/`: per-item metadata sidecars

## Intended Use
- Fine-tuning style LoRAs for top-down medieval pixel art.
- Controlled experiments using consistent caption schema.

## Data Fields
Each row in `metadata.jsonl` is expected to include:
- `id`: unique sample id
- `file_name`: relative image path (for example `images/0000001.png`)
- `text`: training caption
- `asset_family` (recommended): bucket for stratified sampling and balance checks

## Curation and Validation
Validation is automated via:
- `python -m src.validate_dataset --dataset-root hf_ready`
- `python -m src.preflight_check`

Latest local validation reports are generated into:
- `hf_ready/validation_report.ostris.json`
- `hf_ready/validation_issues.ostris.jsonl`

## Limitations
- Small datasets can overfit quickly.
- Unbalanced `asset_family` buckets reduce style separation quality.
- Captions longer than ~700 characters may reduce conditioning stability.

## Bias, Risks, and Safety
This dataset may reflect stylistic and semantic biases from source data and captions.
Review outputs before production use and avoid unsafe or policy-violating prompts.



