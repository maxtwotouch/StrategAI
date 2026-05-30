#!/usr/bin/env bash
#
# generate_images.sh — Batch-generate images via ComfyUI using preset arguments.
#
# Usage:
#     bash scripts/generate_images.sh
#
# Requirements:
#     - ComfyUI server running at http://127.0.0.1:8188
#     - Prompt data already generated (see: python -m src.generation.prompt_generator)
#     - Workflow JSON at config/comfyui/structure_workflow.json
#
set -euo pipefail

python3 -m src.generation.dataset_generator \
  --comfy-url http://127.0.0.1:8188 \
  --base-dir ./dataset \
  --workflow-api-json ./config/comfyui/structure_workflow.json \
  --limit 2000 \
  --prompt-node 100 \
  --guidance-node 101 \
  --guidance-randomize \
  --guidance-min 15 \
  --guidance-max 60 \
  --guidance-decimals 3 \
  --prompt-data ./dataset/prompts/generated_prompts.jsonl \
  --guidance-key guidance \
  --override-seed-mode random \
  --ksampler-node 70