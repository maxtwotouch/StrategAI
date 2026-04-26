# convert_dataset_for_lora.py

Embeds LoRA-relevant metadata directly into PNG files for ComfyUI-friendly colocation.

## What it changes

- Writes PNG text fields: `asset_family`, `caption`, `pixelart_meta` (JSON).
- Trims template-heavy `positive_prompt` text into a compact LoRA caption.
- Uses `convertive/templates.txt` markers to isolate prompt-specific content.
- Enforces `front view overhead shot` in `structure` captions.
- Processes PNG-only images (no metadata JSON) using embedded ComfyUI `prompt` metadata.
- Writes `conversion_report.json` and `conversion_errors.jsonl` in the dataset output root.

Optional compatibility outputs:

- `--write-sidecar-json`: update metadata JSON files (`caption`, `lora_caption`, `generation_object_type`).
- `--write-txt`: write image-adjacent `*.txt` captions.

## Supported layouts

- `<dataset_root>/images` and `<dataset_root>/metadata`
- `<dataset_root>/generated/images` and `<dataset_root>/generated/metadata`

## Usage

```bash
python3 processing/convert_dataset_for_lora.py ./convertive/dataset
python3 processing/convert_dataset_for_lora.py ./dataset --caption-detail minimal
python3 processing/convert_dataset_for_lora.py ./dataset --caption-detail balanced --write-sidecar-json --write-txt
python3 processing/convert_dataset_for_lora.py ./dataset --dry-run
```

