#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 -m src.extract_training_set \
  --dataset-root "$ROOT_DIR/dataset/hf" \
  --metadata "$ROOT_DIR/dataset/metadata.jsonl" \
  --trigger-mode placeholder \
  "$@"
