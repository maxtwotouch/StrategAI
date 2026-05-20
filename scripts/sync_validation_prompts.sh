#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
python3 -m src.sync_validation_prompts \
  --dataset-root "$ROOT_DIR/hf_ready" \
  --run-config "$ROOT_DIR/configs/run_lora.yaml" \
  --max-chars 420 \
  "$@"
