#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
python3 -m src.sync_validation_prompts \
  --dataset-root "$ROOT_DIR/dataset" \
  --training-config "$ROOT_DIR/config/lora_4b.yaml" \
  --max-chars 420 \
  "$@"
