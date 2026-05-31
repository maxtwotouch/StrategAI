#!/usr/bin/env bash
# =============================================================================
# spawn_comfyui.sh — Launch N ComfyUI workers on a single GPU node
# =============================================================================
#
# Starts N ComfyUI instances on sequential ports, each binding to the same
# GPU.  Prints host:port URLs ready for the comfyui.nodes config block.
#
# Designed for Blackwell RTX 6000 (96 GB VRAM): Flux2 Klein 4B fp8 uses
# ~14 GB per instance → 5-6 instances fit comfortably.
#
# Usage:
#   spawn_comfyui.sh [OPTIONS] start       Launch N ComfyUI instances
#   spawn_comfyui.sh [OPTIONS] stop        Kill all tracked instances
#   spawn_comfyui.sh [OPTIONS] status      Show instance health
#   spawn_comfyui.sh --help                Show this help
#
# Options (start mode):
#   -n, --count N            Number of instances to spawn       [default: 1]
#   -p, --start-port PORT    First port (increments by 1)       [default: 8188]
#   -d, --comfyui-dir DIR    Path to ComfyUI installation       [default: $COMFYUI_DIR or $HOME/ComfyUI]
#   -g, --gpu ID             CUDA GPU device ID                 [default: 0]
#   -l, --listen ADDR        Bind address                      [default: 0.0.0.0]
#       --host ADDR          Hostname printed in output URLs    [default: $(hostname)]
#   -w, --wait               Wait for each instance to be healthy before printing
#       --wait-timeout SEC   Max seconds to wait per instance   [default: 120]
#       --pid-dir DIR        Directory for PID files            [default: /tmp/comfyui-pids]
#       --log-dir DIR        Directory for per-instance logs    [default: $COMFYUI_DIR/logs]
#   -q, --quiet              Suppress info messages, only print URLs
#   -h, --help               Show this help
#
# Options (stop mode):
#       --pid-dir DIR        Directory containing PID files     [default: /tmp/comfyui-pids]
#       --force              Send SIGKILL immediately (skip SIGTERM)
#
# Options (status mode):
#       --pid-dir DIR        Directory containing PID files     [default: /tmp/comfyui-pids]
#
# Environment variables:
#   COMFYUI_DIR              Default ComfyUI install path
#   CUDA_VISIBLE_DEVICES     Overridden by --gpu
#
# Examples:
#   # Basic: 1 instance on port 8188
#   ./spawn_comfyui.sh start
#
#   # 6 instances on ports 8188-8193, Blackwell RTX 6000
#   ./spawn_comfyui.sh -n 6 start
#
#   # 3 instances starting at port 8190, GPU 2, wait for readiness
#   ./spawn_comfyui.sh -n 3 -p 8190 -g 2 -w start
#
#   # Stop all instances
#   ./spawn_comfyui.sh stop
#
#   # Check health of all spawned instances
#   ./spawn_comfyui.sh status
# =============================================================================

set -euo pipefail

# ---- constants ---------------------------------------------------------
SCRIPT_NAME="$(basename "$0")"
DEFAULT_START_PORT=8188
DEFAULT_COUNT=1
DEFAULT_GPU=0
DEFAULT_LISTEN="0.0.0.0"
DEFAULT_WAIT_TIMEOUT=120

# ---- helpers -----------------------------------------------------------
_info()  { if [[ "${QUIET:-false}" != "true" ]]; then echo "[INFO]  $*" >&2; fi; }
_warn()  { echo "[WARN]  $*" >&2; }
_error() { echo "[ERROR] $*" >&2; }
_die()   { _error "$@"; exit 1; }

_usage() {
    sed -n '/^# =/{n; :a; /^#/{p; n; ba;}; q;}' "$0" | sed 's/^# \?//'
    exit 0
}

# ---- defaults resolution -----------------------------------------------
_resolve_defaults() {
    COMFYUI_DIR="${COMFYUI_DIR:-${COMFYUI_DIR_ENV:-$HOME/ComfyUI}}"
    COUNT="${COUNT:-$DEFAULT_COUNT}"
    START_PORT="${START_PORT:-$DEFAULT_START_PORT}"
    GPU="${GPU:-$DEFAULT_GPU}"
    LISTEN="${LISTEN:-$DEFAULT_LISTEN}"
    WAIT="${WAIT:-false}"
    WAIT_TIMEOUT="${WAIT_TIMEOUT:-$DEFAULT_WAIT_TIMEOUT}"
    PID_DIR="${PID_DIR:-/tmp/comfyui-pids}"
    LOG_DIR="${LOG_DIR:-$COMFYUI_DIR/logs}"
    FORCE="${FORCE:-false}"
    PRINT_HOST="${PRINT_HOST:-$(hostname)}"
    QUIET="${QUIET:-false}"

    # If listen is 0.0.0.0, the printed host should be the machine's hostname
    # (or whatever --host was set to).  If listen is 127.0.0.1, print 127.0.0.1.
    if [[ "$PRINT_HOST" == "$(hostname)" && "$LISTEN" == "127.0.0.1" ]]; then
        PRINT_HOST="127.0.0.1"
    fi
}

# ---- argument parsing --------------------------------------------------
parse_args() {
    local args
    args=$(getopt -o n:p:d:g:l:wqh --long count:,start-port:,comfyui-dir:,gpu:,listen:,host:,wait,wait-timeout:,pid-dir:,log-dir:,force,quiet,help -n "$SCRIPT_NAME" -- "$@") || exit 1
    eval set -- "$args"

    while true; do
        case "$1" in
            -n|--count)        COUNT="$2"; shift 2 ;;
            -p|--start-port)   START_PORT="$2"; shift 2 ;;
            -d|--comfyui-dir)  COMFYUI_DIR_ENV="$2"; shift 2 ;;
            -g|--gpu)          GPU="$2"; shift 2 ;;
            -l|--listen)       LISTEN="$2"; shift 2 ;;
            --host)            PRINT_HOST="$2"; shift 2 ;;
            -w|--wait)         WAIT="true"; shift ;;
            --wait-timeout)    WAIT_TIMEOUT="$2"; shift 2 ;;
            --pid-dir)         PID_DIR="$2"; shift 2 ;;
            --log-dir)         LOG_DIR="$2"; shift 2 ;;
            --force)           FORCE="true"; shift ;;
            -q|--quiet)        QUIET="true"; shift ;;
            -h|--help)         _usage ;;
            --) shift; break ;;
            *)                 _die "Unknown option: $1" ;;
        esac
    done

    COMMAND="${1:-}"

    _resolve_defaults
}

# ---- validation --------------------------------------------------------
_validate_start() {
    # Check COUNT is positive integer
    if ! [[ "$COUNT" =~ ^[1-9][0-9]*$ ]]; then
        _die "Invalid count: '$COUNT' — must be a positive integer"
    fi

    # Check START_PORT is valid port number
    if ! [[ "$START_PORT" =~ ^[0-9]+$ ]] || (( START_PORT < 1024 || START_PORT > 65535 )); then
        _die "Invalid start port: '$START_PORT' — must be 1024-65535"
    fi

    # Check GPU is a valid integer
    if ! [[ "$GPU" =~ ^[0-9]+$ ]]; then
        _die "Invalid GPU ID: '$GPU' — must be a non-negative integer"
    fi

    # Check WAIT_TIMEOUT
    if ! [[ "$WAIT_TIMEOUT" =~ ^[0-9]+$ ]] || (( WAIT_TIMEOUT < 1 )); then
        _die "Invalid wait timeout: '$WAIT_TIMEOUT' — must be a positive integer"
    fi

    # Check ComfyUI directory exists
    if [[ ! -d "$COMFYUI_DIR" ]]; then
        _die "ComfyUI directory not found: $COMFYUI_DIR"
    fi

    # Check main.py exists
    if [[ ! -f "$COMFYUI_DIR/main.py" ]]; then
        _die "ComfyUI main.py not found at: $COMFYUI_DIR/main.py"
    fi

    # Check virtualenv
    local venv_python="$COMFYUI_DIR/venv/bin/python"
    if [[ ! -x "$venv_python" ]]; then
        _warn "ComfyUI venv not found at $venv_python — trying system python3"
        venv_python="python3"
    fi
    PYTHON_BIN="$venv_python"

    # Check last port is in range
    local last_port=$(( START_PORT + COUNT - 1 ))
    if (( last_port > 65535 )); then
        _die "Last port $last_port exceeds 65535 — reduce count or start port"
    fi

    # Create directories
    mkdir -p "$PID_DIR" "$LOG_DIR"

    # VRAM sanity check (optional — only if nvidia-smi is available)
    if command -v nvidia-smi &>/dev/null; then
        local total_vram_mb
        total_vram_mb=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits -i "$GPU" 2>/dev/null || echo "0")
        if (( total_vram_mb > 0 )); then
            local total_vram_gb=$(( total_vram_mb / 1024 ))
            local per_instance_gb=14  # Flux2 Klein 4B fp8 with headroom
            local estimated_usage=$(( COUNT * per_instance_gb ))
            _info "GPU $GPU: ${total_vram_gb} GB VRAM total, ~${estimated_usage} GB estimated for $COUNT instance(s) at ~${per_instance_gb} GB each"
            if (( estimated_usage > total_vram_gb )); then
                _warn "Estimated VRAM usage (${estimated_usage} GB) exceeds GPU memory (${total_vram_gb} GB) — instances may OOM"
            fi
        fi
    fi
}

# ---- port checking -----------------------------------------------------
_port_in_use() {
    local port="$1"
    # Try ss first (modern Linux), fall back to parsing /proc/net/tcp
    if command -v ss &>/dev/null; then
        ss -tlnp 2>/dev/null | grep -q ":$port " && return 0
    elif [[ -f /proc/net/tcp ]]; then
        # /proc/net/tcp uses hex ports; convert port to hex, pad to 4 chars
        local hex_port
        hex_port=$(printf '%04X' "$port")
        grep -q ":$hex_port " /proc/net/tcp 2>/dev/null && return 0
    fi
    return 1
}

# ---- health check ------------------------------------------------------
_poll_health() {
    local url="$1"
    local timeout="$2"
    local deadline
    deadline=$(($(date +%s) + timeout))

    while (( $(date +%s) < deadline )); do
        if curl -sSf --max-time 5 "$url/system_stats" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    return 1
}

# ---- signal handler for cleanup on Ctrl+C ------------------------------
_cleanup_on_interrupt() {
    _warn "Interrupted — stopping launched instances..."
    CMD_STOP
    exit 130
}

# ---- start command -----------------------------------------------------
CMD_START() {
    _validate_start

    local instance=0
    local launched=0
    local urls=()

    # Trap SIGINT/SIGTERM so Ctrl+C kills what we started
    trap _cleanup_on_interrupt INT TERM

    for (( i = 0; i < COUNT; i++ )); do
        local port=$(( START_PORT + i ))
        instance=$(( i + 1 ))

        _info "[$instance/$COUNT] Checking port $port..."

        if _port_in_use "$port"; then
            _warn "[$instance/$COUNT] Port $port is already in use — skipping"
            continue
        fi

        _info "[$instance/$COUNT] Launching ComfyUI on port $port (GPU $GPU)..."

        # Build the URL
        local url="http://${PRINT_HOST}:${port}"
        urls+=("$url")

        # Launch ComfyUI in background
        local log_file="$LOG_DIR/comfyui-${port}.log"
        local pid_file="$PID_DIR/comfyui-${port}.pid"

        # Truncate log for this run
        : > "$log_file"

        (
            export CUDA_VISIBLE_DEVICES="$GPU"
            cd "$COMFYUI_DIR"
            # Use exec so the PID we capture is the python process itself
            exec "$PYTHON_BIN" main.py \
                --port "$port" \
                --listen "$LISTEN" \
                --highvram \
                >> "$log_file" 2>&1
        ) &
        local pid=$!

        # Atomic PID write (follows project convention)
        local tmp_pid="$PID_DIR/.comfyui-${port}.pid.tmp"
        echo "$pid" > "$tmp_pid"
        mv "$tmp_pid" "$pid_file"

        _info "[$instance/$COUNT] PID $pid → port $port, log → $log_file"
        launched=$(( launched + 1 ))
    done

    trap - INT TERM

    if (( launched == 0 )); then
        _die "No instances were launched — all ports in use or other errors"
    fi

    # Optional readiness wait
    if [[ "$WAIT" == "true" ]]; then
        echo ""
        _info "Waiting for $launched instance(s) to become healthy (timeout: ${WAIT_TIMEOUT}s each)..."
        echo ""
        local all_ready=true
        for url in "${urls[@]}"; do
            local port="${url##*:}"
            printf "  %-35s " "$url"
            if _poll_health "$url" "$WAIT_TIMEOUT"; then
                echo "✓ ready"
            else
                echo "✗ TIMEOUT (check $LOG_DIR/comfyui-${port}.log)"
                all_ready=false
            fi
        done
        if [[ "$all_ready" != "true" ]]; then
            _warn "Some instances did not become healthy within ${WAIT_TIMEOUT}s"
        fi
        echo ""
    fi

    # Print results — one URL per line, ready for config
    echo "# ===== ComfyUI Instances ====="
    echo "# Add these to config.yaml under comfyui.nodes:"
    echo "#   comfyui:"
    echo "#     nodes:"
    for url in "${urls[@]}"; do
        echo "#       - \"$url\""
    done
    echo ""
    echo "# PID directory: $PID_DIR"
    echo "# Log directory: $LOG_DIR"
    echo "# Stop all:    $SCRIPT_NAME --pid-dir '$PID_DIR' stop"
    echo "# Check:       $SCRIPT_NAME --pid-dir '$PID_DIR' status"
    echo ""
    # Print bare URLs for easy scripting
    for url in "${urls[@]}"; do
        echo "$url"
    done
}

# ---- stop command ------------------------------------------------------
CMD_STOP() {
    if [[ ! -d "$PID_DIR" ]]; then
        _info "PID directory '$PID_DIR' does not exist — nothing to stop"
        return 0
    fi

    local stopped=0
    local missing=0

    for pid_file in "$PID_DIR"/comfyui-*.pid; do
        [[ -f "$pid_file" ]] || continue

        local pid
        pid=$(cat "$pid_file" 2>/dev/null || true)
        local port
        port=$(basename "$pid_file" .pid | sed 's/^comfyui-//')

        if [[ -z "$pid" ]]; then
            _warn "Empty PID file: $pid_file — removing"
            rm -f "$pid_file"
            continue
        fi

        if ! kill -0 "$pid" 2>/dev/null; then
            _info "PID $pid (port $port) is not running — removing stale PID file"
            rm -f "$pid_file"
            missing=$(( missing + 1 ))
            continue
        fi

        if [[ "$FORCE" == "true" ]]; then
            _info "Force-killing PID $pid (port $port)"
            kill -9 "$pid" 2>/dev/null || true
        else
            _info "Stopping PID $pid (port $port) — SIGTERM"
            kill "$pid" 2>/dev/null || true

            # Wait for graceful shutdown
            local waited=0
            while kill -0 "$pid" 2>/dev/null && (( waited < 10 )); do
                sleep 0.5
                waited=$(( waited + 1 ))
            done

            # Force kill if still alive
            if kill -0 "$pid" 2>/dev/null; then
                _warn "PID $pid (port $port) did not stop — sending SIGKILL"
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi

        rm -f "$pid_file"
        stopped=$(( stopped + 1 ))
    done

    _info "Stopped: $stopped  |  Already gone: $missing"
}

# ---- status command ----------------------------------------------------
CMD_STATUS() {
    if [[ ! -d "$PID_DIR" ]]; then
        _info "PID directory '$PID_DIR' does not exist — no instances tracked"
        return 0
    fi

    local found_any=false
    local running=0
    local dead=0

    printf "%-10s %-8s %-10s %s\n" "PORT" "PID" "STATUS" "URL"
    printf "%-10s %-8s %-10s %s\n" "----" "---" "------" "---"

    for pid_file in "$PID_DIR"/comfyui-*.pid; do
        [[ -f "$pid_file" ]] || continue
        found_any=true

        local pid
        pid=$(cat "$pid_file" 2>/dev/null || true)
        local port
        port=$(basename "$pid_file" .pid | sed 's/^comfyui-//')

        if [[ -z "$pid" ]]; then
            printf "%-10s %-8s %-10s %s\n" "$port" "-" "STALE" "—"
            dead=$(( dead + 1 ))
            continue
        fi

        if kill -0 "$pid" 2>/dev/null; then
            local status="RUNNING"
            # Quick health check
            if curl -sSf --max-age 5 "http://${LISTEN}:${port}/system_stats" >/dev/null 2>&1; then
                status="HEALTHY"
            fi
            printf "%-10s %-8s %-10s http://%s:%s\n" "$port" "$pid" "$status" "$PRINT_HOST" "$port"
            running=$(( running + 1 ))
        else
            printf "%-10s %-8s %-10s http://%s:%s\n" "$port" "$pid" "DEAD" "$PRINT_HOST" "$port"
            dead=$(( dead + 1 ))
        fi
    done

    if [[ "$found_any" != "true" ]]; then
        _info "No PID files found in $PID_DIR"
        return 0
    fi

    echo ""
    _info "Running: $running  |  Dead/Stale: $dead"
}

# ---- main --------------------------------------------------------------
main() {
    parse_args "$@"

    case "${COMMAND:-}" in
        start)  CMD_START ;;
        stop)   CMD_STOP ;;
        status) CMD_STATUS ;;
        "")     _die "No command specified — use 'start', 'stop', or 'status'" ;;
        *)      _die "Unknown command: '$COMMAND' — use 'start', 'stop', or 'status'" ;;
    esac
}

main "$@"
