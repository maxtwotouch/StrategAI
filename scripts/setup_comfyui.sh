#!/usr/bin/env bash
# =============================================================================
# setup_comfyui.sh — Idempotent ComfyUI + Flux2 Klein 4B provisioning script
# =============================================================================
#
# Usage:
#   bash scripts/setup_comfyui.sh                  # full setup
#   bash scripts/setup_comfyui.sh --dry-run        # print plan, don't execute
#   HF_BASE=https://hf-mirror.com bash scripts/setup_comfyui.sh  # China mirror
#   COMFYUI_DIR=/opt/ComfyUI bash scripts/setup_comfyui.sh       # custom path
#   SKIP_COMFYUI=true bash scripts/setup_comfyui.sh              # models only
#
# Environment variables:
#   COMFYUI_DIR     — ComfyUI install directory (default: $HOME/ComfyUI)
#   HF_BASE         — HuggingFace base URL (default: https://huggingface.co)
#   SKIP_COMFYUI    — If "true", skip git clone + venv + pip install
#   SKIP_MANAGER    — If "true", skip ComfyUI Manager install
#   SKIP_WORKFLOWS  — If "true", skip copying workflow JSONs into ComfyUI
# =============================================================================

set -euo pipefail

# ---- Color helpers ----------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
header()  { echo -e "\n${BOLD}─── $* ───${NC}"; }

# ---- Configuration ----------------------------------------------------------
COMFYUI_DIR="${COMFYUI_DIR:-$HOME/ComfyUI}"
HF_BASE="${HF_BASE:-https://huggingface.co}"
SKIP_COMFYUI="${SKIP_COMFYUI:-false}"
SKIP_MANAGER="${SKIP_MANAGER:-false}"
SKIP_WORKFLOWS="${SKIP_WORKFLOWS:-false}"
DRY_RUN=false

# Parse --dry-run flag
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        *) error "Unknown argument: $arg"; exit 1 ;;
    esac
done

# ---- Model download table ---------------------------------------------------
# Format: "local_subdir|filename|hf_repo|hf_filepath|expected_size_human|expected_bytes_lower"
# expected_bytes_lower is the minimum acceptable file size in bytes.
MODELS=(
    "unet|flux-2-klein-4b-fp8.safetensors|black-forest-labs/FLUX.2-klein-4b-fp8|flux-2-klein-4b-fp8.safetensors|~6.0 GB|5000000000"
    "clip|qwen_3_4b.safetensors|Comfy-Org/vae-text-encorder-for-flux-klein-4b|split_files/text_encoders/qwen_3_4b.safetensors|~8.0 GB|7000000000"
    "vae|flux2-vae.safetensors|Comfy-Org/vae-text-encorder-for-flux-klein-4b|split_files/vae/flux2-vae.safetensors|~320 MB|300000000"
    # LoRA placeholder — uncomment and update when available:
    # "loras|<tdp_lora_filename>|<repo>|<filepath>|~?? MB|1000000"
)

# ---- Helper functions -------------------------------------------------------

check_command() {
    if ! command -v "$1" &>/dev/null; then
        error "Required command '$1' not found. Please install it and retry."
        return 1
    fi
}

check_disk_space() {
    local dir="$1"
    local required_gb="$2"

    # Resolve to an existing parent
    local check_dir="$dir"
    while [[ ! -d "$check_dir" ]]; do
        check_dir="$(dirname "$check_dir")"
    done

    local available_kb
    available_kb=$(df -k --output=avail "$check_dir" 2>/dev/null | tail -1)
    if [[ -z "$available_kb" ]]; then
        warn "Could not check disk space for $check_dir — proceeding anyway."
        return 0
    fi

    local available_gb=$((available_kb / 1024 / 1024))
    if (( available_gb < required_gb )); then
        error "Insufficient disk space: ${available_gb} GB available, ${required_gb} GB needed."
        error "Free up space or set COMFYUI_DIR to a volume with more room."
        return 1
    fi
    info "Disk space OK: ${available_gb} GB available (need ~${required_gb} GB)."
}

download_model() {
    local subdir="$1"
    local filename="$2"
    local repo="$3"
    local filepath="$4"
    local expected_size="$5"
    local min_bytes="$6"

    local dest_dir="${COMFYUI_DIR}/models/${subdir}"
    local dest_file="${dest_dir}/${filename}"

    # Skip if already downloaded and has reasonable size
    if [[ -f "$dest_file" ]]; then
        local actual_bytes
        actual_bytes=$(stat -c%s "$dest_file" 2>/dev/null || stat -f%z "$dest_file" 2>/dev/null || echo 0)
        if (( actual_bytes >= min_bytes )); then
            success "Already downloaded: $filename ($(numfmt --to=iec "$actual_bytes" 2>/dev/null || echo "$actual_bytes bytes"))"
            return 0
        else
            warn "Found truncated $filename ($actual_bytes bytes) — re-downloading."
            rm -f "$dest_file"
        fi
    fi

    if $DRY_RUN; then
        echo "  [DRY-RUN] wget -c -P $dest_dir/ ${HF_BASE}/${repo}/resolve/main/${filepath}"
        return 0
    fi

    info "Downloading $filename ($expected_size)..."
    mkdir -p "$dest_dir"

    if wget --show-progress -c -q -P "$dest_dir/" \
        "${HF_BASE}/${repo}/resolve/main/${filepath}"; then
        local final_bytes
        final_bytes=$(stat -c%s "$dest_file" 2>/dev/null || stat -f%z "$dest_file" 2>/dev/null || echo 0)
        if (( final_bytes < min_bytes )); then
            error "Downloaded $filename but it appears truncated ($final_bytes bytes)."
            error "Delete it and re-run: rm $dest_file"
            return 1
        fi
        success "Downloaded $filename ($(numfmt --to=iec "$final_bytes" 2>/dev/null || echo "$final_bytes bytes"))"
    else
        error "Failed to download $filename from ${HF_BASE}/${repo}"
        error "Check the URL or try with: HF_BASE=https://hf-mirror.com bash $0"
        return 1
    fi
}

# ---- Main -------------------------------------------------------------------

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   ComfyUI + Flux2 Klein 4B — Automated Setup                ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
info "Install directory : ${COMFYUI_DIR}"
info "HuggingFace base   : ${HF_BASE}"
info "Dry run            : ${DRY_RUN}"
info "Skip ComfyUI       : ${SKIP_COMFYUI}"
echo ""

# ---- Step 0: Pre-flight checks ---------------------------------------------
header "Pre-flight checks"

check_command git || exit 1
check_command python3 || exit 1
check_command wget || exit 1

# Check disk space (~15 GB for models, ~5 GB for ComfyUI + venv)
if ! $DRY_RUN; then
    check_disk_space "$COMFYUI_DIR" 20 || exit 1
else
    info "Dry-run: skipping disk space check."
fi

# ---- Step 1: Install ComfyUI -----------------------------------------------
header "Step 1: ComfyUI installation"

if $SKIP_COMFYUI; then
    info "SKIP_COMFYUI=true — skipping ComfyUI installation."
    if [[ ! -d "$COMFYUI_DIR" ]]; then
        error "SKIP_COMFYUI is set but $COMFYUI_DIR does not exist."
        error "Either unset SKIP_COMFYUI or point COMFYUI_DIR to an existing ComfyUI installation."
        exit 1
    fi
elif [[ -d "$COMFYUI_DIR/.git" ]]; then
    info "ComfyUI already cloned at $COMFYUI_DIR"
    if ! $DRY_RUN; then
        cd "$COMFYUI_DIR"
        info "Pulling latest changes..."
        git pull --ff-only || warn "git pull failed — continuing with existing checkout."
    fi
else
    info "Cloning ComfyUI..."
    if $DRY_RUN; then
        echo "  [DRY-RUN] git clone https://github.com/comfyanonymous/ComfyUI.git $COMFYUI_DIR"
    else
        git clone https://github.com/comfyanonymous/ComfyUI.git "$COMFYUI_DIR"
        success "ComfyUI cloned."
    fi
fi

# ---- Step 2: Python virtual environment ------------------------------------
header "Step 2: Python virtual environment"

VENV_DIR="${COMFYUI_DIR}/venv"

if $SKIP_COMFYUI; then
    info "SKIP_COMFYUI=true — skipping venv setup."
elif [[ -f "$VENV_DIR/bin/python" ]]; then
    info "Virtual environment already exists at $VENV_DIR"
    if ! $DRY_RUN; then
        info "Installing/updating ComfyUI dependencies..."
        "$VENV_DIR/bin/pip" install -r "$COMFYUI_DIR/requirements.txt" --quiet || {
            error "pip install failed. Check the ComfyUI requirements."
            exit 1
        }
        success "Dependencies up to date."
    fi
else
    info "Creating virtual environment..."
    if $DRY_RUN; then
        echo "  [DRY-RUN] python3 -m venv $VENV_DIR"
        echo "  [DRY-RUN] $VENV_DIR/bin/pip install -r $COMFYUI_DIR/requirements.txt"
    else
        python3 -m venv "$VENV_DIR"
        "$VENV_DIR/bin/pip" install -r "$COMFYUI_DIR/requirements.txt"
        success "Virtual environment created and dependencies installed."
    fi
fi

# ---- Step 3: ComfyUI Manager (optional) ------------------------------------
header "Step 3: ComfyUI Manager"

MANAGER_DIR="${COMFYUI_DIR}/custom_nodes/ComfyUI-Manager"

if $SKIP_MANAGER; then
    info "SKIP_MANAGER=true — skipping ComfyUI Manager."
elif $SKIP_COMFYUI; then
    info "SKIP_COMFYUI=true — skipping ComfyUI Manager."
elif [[ -d "$MANAGER_DIR/.git" ]]; then
    info "ComfyUI Manager already installed."
else
    info "Installing ComfyUI Manager..."
    if $DRY_RUN; then
        echo "  [DRY-RUN] git clone https://github.com/ltdrdata/ComfyUI-Manager.git $MANAGER_DIR"
        echo "  [DRY-RUN] $VENV_DIR/bin/pip install -r $MANAGER_DIR/requirements.txt"
    else
        git clone https://github.com/ltdrdata/ComfyUI-Manager.git "$MANAGER_DIR"
        if [[ -f "$MANAGER_DIR/requirements.txt" ]]; then
            "$VENV_DIR/bin/pip" install -r "$MANAGER_DIR/requirements.txt" --quiet
        fi
        success "ComfyUI Manager installed."
    fi
fi

# ---- Step 4: Create model directories --------------------------------------
header "Step 4: Model directories"

if $DRY_RUN; then
    echo "  [DRY-RUN] mkdir -p ${COMFYUI_DIR}/models/{unet,clip,vae,loras}"
else
    mkdir -p "${COMFYUI_DIR}/models"/{unet,clip,vae,loras}
    success "Model directories created."
fi

# ---- Step 5: Download models -----------------------------------------------
header "Step 5: Download models"

for entry in "${MODELS[@]}"; do
    IFS='|' read -r subdir filename repo filepath expected_size min_bytes <<< "$entry"
    download_model "$subdir" "$filename" "$repo" "$filepath" "$expected_size" "$min_bytes" || exit 1
done

# ---- Step 6: Copy workflow JSONs (optional) --------------------------------
header "Step 6: Workflow files"

WORKFLOW_DEST="${COMFYUI_DIR}/user/default/workflows"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if $SKIP_WORKFLOWS; then
    info "SKIP_WORKFLOWS=true — skipping workflow copy."
elif $DRY_RUN; then
    echo "  [DRY-RUN] cp ${PROJECT_ROOT}/workflows/txt2img.json $WORKFLOW_DEST/"
    echo "  [DRY-RUN] cp ${PROJECT_ROOT}/workflows/background_tile.json $WORKFLOW_DEST/"
    echo "  [DRY-RUN] cp ${PROJECT_ROOT}/workflows/leader/*.json $WORKFLOW_DEST/"
else
    if [[ -d "$PROJECT_ROOT/workflows" ]]; then
        mkdir -p "$WORKFLOW_DEST"
        cp "$PROJECT_ROOT/workflows/txt2img.json" "$WORKFLOW_DEST/" 2>/dev/null || true
        cp "$PROJECT_ROOT/workflows/background_tile.json" "$WORKFLOW_DEST/" 2>/dev/null || true
        cp "$PROJECT_ROOT/workflows/leader/"*.json "$WORKFLOW_DEST/" 2>/dev/null || true
        success "Workflow files copied to $WORKFLOW_DEST"
    else
        warn "Project workflows/ directory not found at $PROJECT_ROOT/workflows — skipping."
        warn "Run this script from within the TopDownMedievalPixelArt-Prod project tree."
    fi
fi

# ---- Step 7: Verification --------------------------------------------------
header "Step 7: Verification"

FAILURES=0

for entry in "${MODELS[@]}"; do
    IFS='|' read -r subdir filename repo filepath expected_size min_bytes <<< "$entry"
    local_file="${COMFYUI_DIR}/models/${subdir}/${filename}"

    if $DRY_RUN; then
        echo "  [DRY-RUN] Would check: $local_file (> $expected_size)"
        continue
    fi

    if [[ -f "$local_file" ]]; then
        actual_bytes=$(stat -c%s "$local_file" 2>/dev/null || stat -f%z "$local_file" 2>/dev/null || echo 0)
        if (( actual_bytes >= min_bytes )); then
            success "$filename — $(numfmt --to=iec "$actual_bytes" 2>/dev/null || echo "$actual_bytes bytes") ✓"
        else
            error "$filename — only $actual_bytes bytes (expected > $expected_size) ✗"
            FAILURES=$((FAILURES + 1))
        fi
    else
        error "$filename — NOT FOUND ✗"
        FAILURES=$((FAILURES + 1))
    fi
done

echo ""

if $DRY_RUN; then
    info "Dry-run complete. Run without --dry-run to execute."
elif (( FAILURES == 0 )); then
    success "All models verified!"
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║   Setup complete!                                           ║${NC}"
    echo -e "${BOLD}╠══════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${BOLD}║                                                            ${NC}${BOLD}║${NC}"
    echo -e "${BOLD}║   Start ComfyUI:                                           ${NC}${BOLD}║${NC}"
    echo -e "${BOLD}║     cd ${COMFYUI_DIR}                         ${NC}${BOLD}║${NC}"
    echo -e "${BOLD}║     source venv/bin/activate                                ${NC}${BOLD}║${NC}"
    echo -e "${BOLD}║     python main.py                                          ${NC}${BOLD}║${NC}"
    echo -e "${BOLD}║                                                            ${NC}${BOLD}║${NC}"
    echo -e "${BOLD}║   Then open: http://127.0.0.1:8188                         ${NC}${BOLD}║${NC}"
    echo -e "${BOLD}║                                                            ${NC}${BOLD}║${NC}"
    echo -e "${BOLD}║   See docs/comfyui-setup-guide.md for next steps.          ${NC}${BOLD}║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
else
    error "Verification failed with $FAILURES issue(s)."
    error "Re-run the script to retry failed downloads."
    exit 1
fi
