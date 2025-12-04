#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Tourist Scheduling System - Demo Runner Script
# Runs the tourist scheduling demo with ADK agents
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# ── Colors / Logging ───────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}[RUN]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Defaults ───────────────────────────────────────────────────────────────────
TRANSPORT=http
SCHED_PORT=10010
UI_PORT=10021
AUTONOMOUS=true
NUM_GUIDES=2
NUM_TOURISTS=3

# SLIM settings (can be overridden by setup.sh env export)
SLIM_PORT="${SLIM_PORT:-46357}"
SLIM_ENDPOINT="${SLIM_ENDPOINT:-http://localhost:${SLIM_PORT}}"
SLIM_SHARED_SECRET="${SLIM_SHARED_SECRET:-supersecretsharedsecret123456789}"  # Must be 32+ chars
SLIM_TLS_INSECURE="${SLIM_TLS_INSECURE:-true}"

# Tracing settings
JAEGER_OTLP_HTTP_PORT="${JAEGER_OTLP_HTTP_PORT:-4318}"
JAEGER_UI_PORT="${JAEGER_UI_PORT:-16686}"

PID_FILE="${ROOT_DIR}/.agent_pids"
RUNNER_SCRIPT="${ROOT_DIR}/scripts/run_adk_demo.py"

# ── Agent Process Management ───────────────────────────────────────────────────
stop_agents() {
    log "Stopping agent processes..."
    if [[ -f "$PID_FILE" ]]; then
        while read -r pid; do
            if kill -0 "$pid" 2>/dev/null; then
                log "Killing PID $pid"
                kill "$pid" 2>/dev/null || true
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
        ok "Agent processes stopped"
    else
        log "No PID file found, killing by port and pattern..."
        for port in $SCHED_PORT $UI_PORT; do
            local pid
            pid=$(lsof -ti tcp:$port 2>/dev/null || true)
            if [[ -n "$pid" ]]; then
                log "Killing process on port $port (PID $pid)"
                kill "$pid" 2>/dev/null || true
            fi
        done
        # Kill by process name pattern
        pkill -f "scheduler_agent" 2>/dev/null || true
        pkill -f "ui_agent" 2>/dev/null || true
        pkill -f "run_adk_demo.py" 2>/dev/null || true
        ok "Agent processes stopped"
    fi
}

# ── Clean Function ─────────────────────────────────────────────────────────────
clean_demo() {
    log "Cleaning up demo processes and temporary files..."

    # Stop all agent processes
    stop_agents

    # Kill any remaining Python processes related to the demo
    pkill -f "run_adk_demo.py" 2>/dev/null || true
    pkill -f "scheduler_agent" 2>/dev/null || true
    pkill -f "ui_agent" 2>/dev/null || true

    # Kill processes on known ports
    for port in $SCHED_PORT $UI_PORT; do
        local pid
        pid=$(lsof -ti tcp:$port 2>/dev/null || true)
        if [[ -n "$pid" ]]; then
            log "Killing process on port $port (PID $pid)"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done

    # Clean up PID file
    rm -f "$PID_FILE"

    ok "Demo cleaned up"
}

# ── Help ───────────────────────────────────────────────────────────────────────
usage() {
cat <<EOF
Usage: $0 [options]
       $0 stop                           # Stop all agents
       $0 clean                          # Stop agents and clean up

Demo Runner for Tourist Scheduling System (ADK Agents).
Run setup.sh first to start infrastructure containers.

Transport Options:
        --transport MODE               Transport mode: http (default) or slim
                                       For slim mode, run: ./setup.sh start first

Tracing Options:
        --tracing                      Enable OpenTelemetry tracing
                                       Requires: ./setup.sh start --tracing

Port Options:
        --scheduler-port N             Scheduler port (default: $SCHED_PORT)
        --ui-port N                    UI Dashboard port (default: $UI_PORT)

Agent Options:
        --autonomous / --no-autonomous Enable or disable autonomous agents (default: $AUTONOMOUS)
        --guides N                     Number of guide agents (default: $NUM_GUIDES)
        --tourists N                   Number of tourist agents (default: $NUM_TOURISTS)

Examples:
        $0                                    # HTTP mode
        $0 --transport slim                   # SLIM mode (run setup.sh start first)
        $0 --tracing                          # With OpenTelemetry tracing
        $0 --transport slim --tracing         # SLIM + tracing
        $0 --guides 5 --tourists 10           # Custom agent counts
        $0 stop                               # Stop agent processes
        $0 clean                              # Stop agents and clean up

Workflow:
        1. ./setup.sh start [--tracing]   # Start infrastructure
        2. ./run.sh [options]             # Run demo
        3. ./run.sh stop                  # Stop agents
        4. ./setup.sh stop                # Stop infrastructure

EOF
}

# ── Handle commands ────────────────────────────────────────────────────────────
if [[ $# -ge 1 && "$1" == "stop" ]]; then
    stop_agents
    exit 0
fi

if [[ $# -ge 1 && "$1" == "clean" ]]; then
    clean_demo
    exit 0
fi

if [[ $# -ge 1 && ( "$1" == "--help" || "$1" == "-h" ) ]]; then
    usage
    exit 0
fi

# ── Parse CLI args ─────────────────────────────────────────────────────────────
ENABLE_TRACING=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --transport) TRANSPORT=$2; shift 2;;
        --tracing) ENABLE_TRACING=true; shift;;
        --scheduler-port) SCHED_PORT=$2; shift 2;;
        --ui-port) UI_PORT=$2; shift 2;;
        --autonomous) AUTONOMOUS=true; shift;;
        --no-autonomous) AUTONOMOUS=false; shift;;
        --guides) NUM_GUIDES=$2; shift 2;;
        --tourists) NUM_TOURISTS=$2; shift 2;;
        --help|-h) usage; exit 0;;
        *) err "Unknown option: $1"; usage; exit 1;;
    esac
done

# ── Validation ─────────────────────────────────────────────────────────────────
for p in $SCHED_PORT $UI_PORT; do
    [[ $p =~ ^[0-9]+$ ]] || { err "Port '$p' must be numeric"; exit 1; }
done

if [[ "$TRANSPORT" != "http" && "$TRANSPORT" != "slim" ]]; then
    err "Invalid transport mode: $TRANSPORT (use: http or slim)"
    exit 1
fi

[[ -f "$RUNNER_SCRIPT" ]] || { err "Runner not found: $RUNNER_SCRIPT"; exit 1; }

# ── SLIM mode checks ───────────────────────────────────────────────────────────
if [[ "$TRANSPORT" == "slim" ]]; then
    # Check if SLIM container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^slim-node$"; then
        err "SLIM node is not running. Start it first with:"
        echo "    ./setup.sh start"
        exit 1
    fi
    log "SLIM node detected, using endpoint: $SLIM_ENDPOINT"
    export SLIM_ENDPOINT
    export SLIM_SHARED_SECRET
    export SLIM_TLS_INSECURE
fi

# ── Tracing mode checks ────────────────────────────────────────────────────────
if [[ "$ENABLE_TRACING" == "true" ]]; then
    # Check if Jaeger container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^jaeger-tracing$"; then
        err "Jaeger is not running. Start it first with:"
        echo "    ./setup.sh start --tracing"
        exit 1
    fi
    log "Jaeger detected, enabling tracing"
    export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:${JAEGER_OTLP_HTTP_PORT}"
    export OTEL_SERVICE_NAME="tourist-scheduling"
fi

# ── Summary ────────────────────────────────────────────────────────────────────
echo "======================================================="
log "Transport: $TRANSPORT"
log "Tracing: $ENABLE_TRACING"
log "Scheduler Port: $SCHED_PORT"
log "UI Dashboard Port: $UI_PORT"
log "Guides: $NUM_GUIDES"
log "Tourists: $NUM_TOURISTS"
if [[ "$TRANSPORT" == "slim" ]]; then
    log "SLIM Endpoint: $SLIM_ENDPOINT"
fi
if [[ "$ENABLE_TRACING" == "true" ]]; then
    log "Jaeger UI: http://localhost:${JAEGER_UI_PORT}"
fi
echo "======================================================="

cleanup() { warn "Termination received; letting underlying script manage child processes."; }
trap cleanup INT TERM

# ── Launch ADK demo ────────────────────────────────────────────────────────────
log "Launching demo..."

# Use multi mode to get the dashboard, console for simple demo
ADK_MODE="multi"
if [[ "$AUTONOMOUS" == false ]]; then
    ADK_MODE="console"  # Simple console mode without dashboard
fi

ADK_ARGS=(--mode "$ADK_MODE" --port "$SCHED_PORT" --host localhost --guides "$NUM_GUIDES" --tourists "$NUM_TOURISTS")
if [[ "$TRANSPORT" == "slim" ]]; then
    ADK_ARGS+=(--transport slim)
    if [[ -n "${SLIM_ENDPOINT:-}" ]]; then
        ADK_ARGS+=(--slim-endpoint "$SLIM_ENDPOINT")
    fi
fi

uv run python "$RUNNER_SCRIPT" "${ADK_ARGS[@]}"
ok "Demo complete."
