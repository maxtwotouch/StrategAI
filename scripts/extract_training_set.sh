#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.." && exec python -m src.extract_training_set \
  --trigger-mode placeholder \
  "$@"
