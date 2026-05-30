#!/usr/bin/env bash
#
# train_experiments.sh — Launch the full 6-experiment LoRA training matrix.
#
# Usage:
#     bash scripts/train_experiments.sh
#
# Requirements:
#     - Ostris AI Toolkit at  AI_TOOLKIT/run.py  (relative to project root)
#     - HuggingFace CLI authenticated (huggingface-cli login)
#     - All 6 configs present in config/
#     - Derived datasets already generated (see: python -m src.derive_captions)
#
# Runs from the project root.  All paths are relative to PROJECT_ROOT.
set -euo pipefail

# ── Resolve project root ──────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

TOOLKIT="$PROJECT_ROOT/AI_TOOLKIT/run.py"
CONFIG_DIR="$PROJECT_ROOT/config/training"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="$PROJECT_ROOT/output/logs"
mkdir -p "$LOG_DIR"

# ── Colour helpers ────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Colour

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

# ── Pre-flight checks ─────────────────────────────────────────────────

log "Project root : $PROJECT_ROOT"

if [ ! -f "$TOOLKIT" ]; then
    err "AI Toolkit not found at $TOOLKIT"
    err "Expected: AI_TOOLKIT/run.py  relative to project root."
    exit 1
fi
ok "AI Toolkit found: $TOOLKIT"

# Gather experiment configs
shopt -s nullglob
CONFIGS=("$CONFIG_DIR"/*.yaml)
shopt -u nullglob

if [ ${#CONFIGS[@]} -eq 0 ]; then
    err "No config files found in $CONFIG_DIR"
    exit 1
fi
ok "Found ${#CONFIGS[@]} experiment config(s)"

# ── Validate derived datasets ──────────────────────────────────────────

log "Validating derived datasets..."

VARIANTS=(minimal detailed ultra_minimal)

for variant in "${VARIANTS[@]}"; do
    DATA_DIR="$PROJECT_ROOT/dataset/derived/$variant"
    if [ ! -d "$DATA_DIR" ]; then
        err "Derived dataset missing: $DATA_DIR"
        err "Run: python -m src.training.derive_captions"
        exit 1
    fi
    log "  Validating $variant ..."
    python -m src.training.validate_dataset \
        --mode sidecar_txt \
        --dataset-root "$DATA_DIR" \
        --image-dir . \
        --trigger-word-override '[trigger]' \
        --trigger-mode expected \
        > "$LOG_DIR/validate_${variant}.log" 2>&1 || {
            err "Validation FAILED for $variant — see $LOG_DIR/validate_${variant}.log"
            exit 1
        }
    ok "  $variant OK"
done

# ── Launch experiments ─────────────────────────────────────────────────

log "Launching ${#CONFIGS[@]} experiments in parallel ..."
echo ""

PIDS=()
CONFIG_NAMES=()

for config_path in "${CONFIGS[@]}"; do
    config_name="$(basename "$config_path" .yaml)"
    log_file="$LOG_DIR/${config_name}_${TIMESTAMP}.log"

    log "  Starting: $config_name"
    python "$TOOLKIT" "$config_path" > "$log_file" 2>&1 &
    pid=$!
    PIDS+=($pid)
    CONFIG_NAMES+=("$config_name")
    echo "         PID=$pid  log=$log_file"
done

echo ""
log "All experiments launched.  Waiting for completion ..."
echo ""

# ── Wait & report ──────────────────────────────────────────────────────

FAILED=()
PASSED=()

for i in "${!PIDS[@]}"; do
    pid=${PIDS[$i]}
    name=${CONFIG_NAMES[$i]}

    if wait $pid; then
        ok "  $name  (PID $pid) — DONE"
        PASSED+=("$name")
    else
        err "  $name  (PID $pid) — FAILED (exit code $?)"
        FAILED+=("$name")
    fi
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Training complete — ${#PASSED[@]} passed, ${#FAILED[@]} failed"
echo "═══════════════════════════════════════════════════════════════"

if [ ${#PASSED[@]} -gt 0 ]; then
    echo ""
    ok "Passed:"
    for n in "${PASSED[@]}"; do
        echo "      $n"
    done
fi

if [ ${#FAILED[@]} -gt 0 ]; then
    echo ""
    err "Failed:"
    for n in "${FAILED[@]}"; do
        echo "      $n  (see $LOG_DIR/${n}_${TIMESTAMP}.log)"
    done
    exit 1
fi

echo ""
ok "All experiments completed successfully."
echo "  Checkpoints in: $PROJECT_ROOT/output/"
echo "  Logs in:        $LOG_DIR/"
