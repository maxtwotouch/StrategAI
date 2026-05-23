#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODEL_SIZE="${MODEL_SIZE:-4b}"

if [[ "$MODEL_SIZE" == "9b" ]]; then
  MODEL_CONFIG="$ROOT_DIR/config/model_flux2_klein_9b.yaml"
else
  MODEL_CONFIG="$ROOT_DIR/config/model_flux2_klein_4b.yaml"
fi

python3 -m src.train_lora \
  --data-config "$ROOT_DIR/config/data.yaml" \
  --model-config "$MODEL_CONFIG" \
  --run-config "$ROOT_DIR/config/run_lora.yaml" \
  --run-name flux2_klein_lora_v1 \
  "$@"
