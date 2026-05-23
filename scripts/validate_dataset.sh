#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
python3 -m src.validate_dataset \
  --dataset-root "$ROOT_DIR/dataset" \
  --data-config "$ROOT_DIR/config/data.yaml" \
  --expected-resolution 1024 \
  "$@"
