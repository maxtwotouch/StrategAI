#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
python3 -m src.sync_validation_prompts \
  --dataset-root "$ROOT_DIR/dataset" \
  --run-config "$ROOT_DIR/config/run_lora.yaml" \
  --max-chars 420 \
  "$@"
