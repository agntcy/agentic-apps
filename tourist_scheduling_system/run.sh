# ─────────────────────────────────────────────────────────────────────────────
# Tourist Scheduling System - Demo Runner
# Source this script to run in current shell: source run.sh [options]
# Or run directly: ./run.sh [options] (will use current shell's env vars)
# ─────────────────────────────────────────────────────────────────────────────

# IMPORTANT: Capture arguments immediately before they get lost when sourcing
# In zsh, when sourcing a script, $@ may not contain the args passed after source
# This workaround captures them via the functrace/BASH_ARGV mechanism
_RUN_ARGS=("$@")

# Determine script directory (works for both source and execute)
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
    _RUN_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
elif [[ -n "${0:-}" ]]; then
    _RUN_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
else
    _RUN_SCRIPT_DIR="$(pwd)"
fi

# Save current directory to return to it if sourced
_RUN_ORIG_DIR="$(pwd)"
cd "$_RUN_SCRIPT_DIR" || return 1

# ── Colors / Logging ───────────────────────────────────────────────────────────
_RED='\033[0;31m'; _GREEN='\033[0;32m'; _YELLOW='\033[1;33m'; _BLUE='\033[0;34m'; _NC='\033[0m'
_log()  { printf "${_BLUE}[RUN]${_NC} %s\n" "$*"; }
_ok()   { printf "${_GREEN}[OK]${_NC} %s\n" "$*"; }
_warn() { printf "${_YELLOW}[WARN]${_NC} %s\n" "$*"; }
_err()  { printf "${_RED}[ERROR]${_NC} %s\n" "$*" >&2; }

# ── Defaults (inherit from environment if set) ─────────────────────────────────
_TRANSPORT="${TRANSPORT:-http}"
_TRACING="${TRACING:-false}"
_SCHED_PORT="${SCHED_PORT:-10000}"
_UI_PORT="${UI_PORT:-10021}"
_NUM_GUIDES="${NUM_GUIDES:-2}"
_NUM_TOURISTS="${NUM_TOURISTS:-3}"
_DURATION="${DURATION:-0}"
_INTERVAL="${INTERVAL:-1.0}"

# SLIM settings
_SLIM_PORT="${SLIM_PORT:-46357}"
_SLIM_ENDPOINT="${SLIM_ENDPOINT:-http://localhost:${_SLIM_PORT}}"
_SLIM_SHARED_SECRET="${SLIM_SHARED_SECRET:-supersecretsharedsecret123456789}"
_SLIM_TLS_INSECURE="${SLIM_TLS_INSECURE:-true}"

# Tracing settings
_JAEGER_OTLP_HTTP_PORT="${JAEGER_OTLP_HTTP_PORT:-4318}"
_JAEGER_UI_PORT="${JAEGER_UI_PORT:-16686}"
_OTEL_ENDPOINT="${OTEL_EXPORTER_OTLP_ENDPOINT:-http://localhost:${_JAEGER_OTLP_HTTP_PORT}}"

# PID tracking
_PID_FILE="${_RUN_SCRIPT_DIR}/.agent_pids"
_PIDS=()

# ── Help ───────────────────────────────────────────────────────────────────────
_usage() {
cat <<EOF
Usage: source run.sh [options]    # Run in current shell (preserves env vars)
       ./run.sh [options]         # Run directly
       ./run.sh stop              # Stop all agents
       ./run.sh clean             # Stop agents and clean up

Demo Runner for Tourist Scheduling System.
Run ./setup.sh start first for infrastructure.

Options:
    --transport MODE       Transport: http (default) or slim
    --tracing              Enable OpenTelemetry tracing
    --scheduler-port N     Scheduler port (default: $_SCHED_PORT)
    --ui-port N            Dashboard port (default: $_UI_PORT)
    --guides N             Number of guides (default: $_NUM_GUIDES)
    --tourists N           Number of tourists (default: $_NUM_TOURISTS)
    --duration N           Duration in minutes (0=single run)
    --interval N           Request interval in seconds (default: $_INTERVAL)
    --no-demo              Start servers only, no demo traffic

Environment variables (recommended for zsh - args may not work when sourcing):
    export TRANSPORT=slim          # Use SLIM transport
    export TRACING=true            # Enable OpenTelemetry tracing
    export AZURE_OPENAI_API_KEY=...
    source run.sh

Examples:
    # Using environment variables (recommended for zsh)
    export TRANSPORT=slim TRACING=true && source run.sh

    # Using command line args (works with ./run.sh)
    ./run.sh --transport slim --tracing

    # Stop agents
    ./run.sh stop
EOF
}

# ── Process Management ─────────────────────────────────────────────────────────
_save_pid() {
    local pid=$1
    _PIDS+=("$pid")
    echo "$pid" >> "$_PID_FILE"
}

_cleanup() {
    _warn "Shutting down..."
    for pid in "${_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            _log "Stopping PID $pid"
            kill "$pid" 2>/dev/null || true
        fi
    done
    sleep 1
    for pid in "${_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    rm -f "$_PID_FILE"
    _ok "Stopped"
    cd "$_RUN_ORIG_DIR" 2>/dev/null || true
    # Don't exit if sourced
    if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
        return 0
    fi
    exit 0
}

_stop_agents() {
    _log "Stopping agents..."
    if [[ -f "$_PID_FILE" ]]; then
        while read -r pid; do
            if kill -0 "$pid" 2>/dev/null; then
                _log "Killing PID $pid"
                kill "$pid" 2>/dev/null || true
            fi
        done < "$_PID_FILE"
        rm -f "$_PID_FILE"
    fi
    for port in $_SCHED_PORT $_UI_PORT; do
        pid=$(lsof -ti tcp:$port 2>/dev/null || true)
        if [[ -n "$pid" ]]; then
            _log "Killing process on port $port"
            kill "$pid" 2>/dev/null || true
        fi
    done
    pkill -f "scheduler_agent" 2>/dev/null || true
    pkill -f "ui_agent" 2>/dev/null || true
    _ok "Agents stopped"
}

_clean_demo() {
    _stop_agents
    rm -f "$_PID_FILE"
    rm -f "${_RUN_SCRIPT_DIR}"/*.log
    _ok "Cleaned up"
}

_wait_for_port() {
    local port=$1 name=$2 retries=${3:-30}
    _log "Waiting for $name on port $port..."
    for _ in $(seq 1 $retries); do
        if nc -z localhost "$port" 2>/dev/null; then
            _ok "$name ready"
            return 0
        fi
        sleep 0.5
    done
    _err "$name not responding on port $port"
    return 1
}

_wait_for_health() {
    local url=$1 name=$2 retries=${3:-30}
    _log "Checking $name health..."
    for _ in $(seq 1 $retries); do
        if curl -fsS "$url" >/dev/null 2>&1; then
            _ok "$name healthy"
            return 0
        fi
        sleep 0.5
    done
    _warn "$name health check failed"
    return 1
}

# ── Main Function ──────────────────────────────────────────────────────────────
_run_demo() {
    local args=("$@")

    # Handle commands
    if [[ ${#args[@]} -ge 1 ]]; then
        case "${args[0]}" in
            stop) _stop_agents; cd "$_RUN_ORIG_DIR" 2>/dev/null || true; return 0 ;;
            clean) _clean_demo; cd "$_RUN_ORIG_DIR" 2>/dev/null || true; return 0 ;;
            -h|--help) _usage; cd "$_RUN_ORIG_DIR" 2>/dev/null || true; return 0 ;;
        esac
    fi

    # Parse options - inherit from environment first
    local ENABLE_TRACING="$_TRACING"
    local NO_DEMO=false

    while [[ ${#args[@]} -gt 0 && -n "${args[0]:-}" ]]; do
        case "${args[0]}" in
            --transport) _TRANSPORT="${args[1]:-http}"; args=("${args[@]:2}") ;;
            --tracing) ENABLE_TRACING=true; args=("${args[@]:1}") ;;
            --scheduler-port) _SCHED_PORT="${args[1]:-10000}"; args=("${args[@]:2}") ;;
            --ui-port) _UI_PORT="${args[1]:-10021}"; args=("${args[@]:2}") ;;
            --guides) _NUM_GUIDES="${args[1]:-2}"; args=("${args[@]:2}") ;;
            --tourists) _NUM_TOURISTS="${args[1]:-3}"; args=("${args[@]:2}") ;;
            --duration) _DURATION="${args[1]:-0}"; args=("${args[@]:2}") ;;
            --interval) _INTERVAL="${args[1]:-1.0}"; args=("${args[@]:2}") ;;
            --no-demo) NO_DEMO=true; args=("${args[@]:1}") ;;
            -h|--help) _usage; cd "$_RUN_ORIG_DIR" 2>/dev/null || true; return 0 ;;
            "") args=("${args[@]:1}") ;;  # Skip empty args
            *) _err "Unknown option: ${args[0]}"; _usage; cd "$_RUN_ORIG_DIR" 2>/dev/null || true; return 1 ;;
        esac
    done

    # Validation
    [[ "$_TRANSPORT" == "http" || "$_TRANSPORT" == "slim" ]] || { _err "Invalid transport: $_TRANSPORT"; return 1; }

    if [[ "$_TRANSPORT" == "slim" ]]; then
        if ! docker ps --format '{{.Names}}' | grep -q "^slim-node$"; then
            _err "SLIM node not running. Run: ./setup.sh start"
            return 1
        fi
        export SLIM_ENDPOINT="$_SLIM_ENDPOINT"
        export SLIM_SHARED_SECRET="$_SLIM_SHARED_SECRET"
        export SLIM_TLS_INSECURE="$_SLIM_TLS_INSECURE"
    fi

    if [[ "$ENABLE_TRACING" == "true" ]]; then
        if ! docker ps --format '{{.Names}}' | grep -q "^jaeger-tracing$"; then
            _err "Jaeger not running. Run: ./setup.sh start --tracing"
            return 1
        fi
        export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:${_JAEGER_OTLP_HTTP_PORT}"
        # Don't set OTEL_SERVICE_NAME globally - let each agent set its own
    fi

    # Setup Python environment
    export PYTHONPATH="${_RUN_SCRIPT_DIR}/src:${PYTHONPATH:-}"

    local VENV_DIR="${_RUN_SCRIPT_DIR}/.venv"
    if [[ -d "$VENV_DIR" ]]; then
        source "${VENV_DIR}/bin/activate"
        local PYTHON="${VENV_DIR}/bin/python"
    else
        _err "Virtual environment not found: $VENV_DIR"
        _err "Run: cd $_RUN_SCRIPT_DIR && uv sync"
        return 1
    fi

    # Summary
    echo "======================================================="
    echo "Tourist Scheduling System"
    echo "======================================================="
    _log "Transport: $_TRANSPORT"
    _log "Tracing: $ENABLE_TRACING"
    _log "Scheduler: http://localhost:$_SCHED_PORT"
    _log "Dashboard: http://localhost:$_UI_PORT"
    _log "Guides: $_NUM_GUIDES | Tourists: $_NUM_TOURISTS"
    if [[ "$_DURATION" -gt 0 ]]; then
        _log "Duration: ${_DURATION} minutes"
    fi
    if [[ "$_TRANSPORT" == "slim" ]]; then
        _log "SLIM: $_SLIM_ENDPOINT"
    fi
    if [[ "$ENABLE_TRACING" == "true" ]]; then
        _log "Jaeger: http://localhost:${_JAEGER_UI_PORT}"
    fi
    echo "======================================================="

    trap _cleanup INT TERM
    rm -f "$_PID_FILE"

    # Build agent arguments
    local SCHED_ARGS=(--mode a2a --port "$_SCHED_PORT" --host localhost)
    local UI_ARGS=(--port "$_UI_PORT" --host localhost --dashboard)

    if [[ "$_TRANSPORT" == "slim" ]]; then
        SCHED_ARGS+=(--transport slim --slim-endpoint "$_SLIM_ENDPOINT" --slim-local-id "agntcy/tourist_scheduling/adk_scheduler")
        UI_ARGS+=(--transport slim --slim-endpoint "$_SLIM_ENDPOINT" --slim-local-id "agntcy/tourist_scheduling/adk_ui")
    fi

    if [[ "$ENABLE_TRACING" == "true" ]]; then
        SCHED_ARGS+=(--tracing)
        UI_ARGS+=(--tracing)
    fi

    # Start agents
    _log "Starting scheduler agent..."
    local SCHED_LOG="${_RUN_SCRIPT_DIR}/scheduler_agent.log"
    "$PYTHON" -m agents.scheduler_agent "${SCHED_ARGS[@]}" > "$SCHED_LOG" 2>&1 &
    _save_pid $!
    _log "Scheduler PID: $! -> $SCHED_LOG"

    sleep 2

    _log "Starting dashboard agent..."
    local UI_LOG="${_RUN_SCRIPT_DIR}/ui_agent.log"
    "$PYTHON" -m agents.ui_agent "${UI_ARGS[@]}" > "$UI_LOG" 2>&1 &
    _save_pid $!
    _log "Dashboard PID: $! -> $UI_LOG"

    sleep 2

    # Wait for services
    _wait_for_port "$_SCHED_PORT" "Scheduler" 20 || _warn "Scheduler may not be ready"
    _wait_for_health "http://localhost:$_UI_PORT/health" "Dashboard" 20 || { _err "Dashboard failed"; _cleanup; return 1; }

    echo "======================================================="
    _ok "Agents running!"
    echo "   📊 Dashboard: http://localhost:$_UI_PORT"
    echo "   🗓️  Scheduler: http://localhost:$_SCHED_PORT"
    if [[ "$ENABLE_TRACING" == "true" ]]; then
        echo "   🔍 Jaeger: http://localhost:${_JAEGER_UI_PORT}"
    fi
    echo ""
    echo "Logs:"
    echo "   tail -f $SCHED_LOG"
    echo "   tail -f $UI_LOG"
    echo "======================================================="

    # Run demo simulation
    if [[ "$NO_DEMO" == "true" ]]; then
        _log "No demo traffic (--no-demo). Press Ctrl+C to stop."
        wait
    else
        _log "Running demo simulation..."

        local SIM_ARGS=(--mode sim --port "$_SCHED_PORT" --ui-port "$_UI_PORT" --guides "$_NUM_GUIDES" --tourists "$_NUM_TOURISTS" --interval "$_INTERVAL")

        if [[ "$_DURATION" -gt 0 ]]; then
            SIM_ARGS+=(--duration "$_DURATION")
        fi

        if [[ "$ENABLE_TRACING" == "true" ]]; then
            SIM_ARGS+=(--tracing)
        fi

        "$PYTHON" "${_RUN_SCRIPT_DIR}/scripts/run_adk_demo.py" "${SIM_ARGS[@]}"

        _ok "Demo complete!"
        echo ""
        _log "Dashboard still running at http://localhost:$_UI_PORT"
        _log "Press Ctrl+C to stop agents."
        wait
    fi
}

# Run the main function with captured arguments
_run_demo "${_RUN_ARGS[@]}"
