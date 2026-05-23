#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_SIZE="${1:-}"

if [[ -z "$TARGET_SIZE" ]]; then
  echo "Usage: ./scripts/sample_dataset.sh <target_size> [additional args]"
  exit 1
fi
shift

OUTPUT_DIR="$ROOT_DIR/sampled_datasets"
OUTPUT_METADATA="$OUTPUT_DIR/metadata.${TARGET_SIZE}.jsonl"

python3 -m src.sample_dataset \
  --dataset-root "$ROOT_DIR/dataset" \
  --metadata-file metadata.jsonl \
  --output-metadata "$OUTPUT_METADATA" \
  --target-size "$TARGET_SIZE" \
  --stratify-column asset_family \
  "$@"

