#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODEL_SIZE="${MODEL_SIZE:-4b}"
ADAPTER_PATH="${1:-$ROOT_DIR/runs/flux2_klein_lora_v1}"
if [[ "$#" -gt 0 ]]; then
  shift
fi

if [[ "$MODEL_SIZE" == "9b" ]]; then
  MODEL_CONFIG="$ROOT_DIR/configs/model_flux2_klein_9b.yaml"
else
  MODEL_CONFIG="$ROOT_DIR/configs/model_flux2_klein_4b.yaml"
fi

python3 -m src.infer_lora \
  --model-config "$MODEL_CONFIG" \
  --adapter-path "$ADAPTER_PATH" \
  --prompt "<sks> medieval granary, top-down pixel art 16x16, white background" \
  --output-dir "$ROOT_DIR/eval_samples" \
  --num-images 4 \
  "$@"

