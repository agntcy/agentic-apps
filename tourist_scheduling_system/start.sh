#!/usr/bin/env bash
# Unified launcher for Multi-Agent Tourist Scheduling System
# Supports both HTTP (A2A direct) and SLIM transport modes.
#
# Usage:
#   ./start.sh                           # Run demo using HTTP transport (default)
#   ./start.sh --transport slim          # Run demo using SLIM group transport
#   ./start.sh --no-autonomous           # Disable autonomous agent loops
#   ./start.sh node start                # Start SLIM node Docker container only
#   ./start.sh node stop                 # Stop SLIM node Docker container
#   ./start.sh stop                      # Stop all agents (keep SLIM node running)
#   ./start.sh clean                     # Full cleanup (agents + SLIM node)
#
# Transport Modes:
#   http - Direct HTTP/gRPC peer-to-peer communication (default)
#   slim - SLIM group transport (pub/sub with moderator pattern)

set -euo pipefail
IFS=$'\n\t'

ROOT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT_DIR"
RUNNER_SCRIPT="${ROOT_DIR}/scripts/run_with_ui.sh"

# ── Logging ────────────────────────────────────────────────────────────────────
COLOR_INFO='\033[1;34m'; COLOR_WARN='\033[1;33m'; COLOR_ERR='\033[1;31m'; COLOR_OK='\033[1;32m'; COLOR_RESET='\033[0m'
log() { echo -e "${COLOR_INFO}[start.sh]${COLOR_RESET} $*"; }
warn() { echo -e "${COLOR_WARN}[start.sh] WARN:${COLOR_RESET} $*" >&2; }
err()  { echo -e "${COLOR_ERR}[start.sh] ERROR:${COLOR_RESET} $*" >&2; }
ok()   { echo -e "${COLOR_OK}[start.sh]${COLOR_RESET} $*"; }

# ── Virtual Environment ────────────────────────────────────────────────────────
if [[ -d ".venv" ]]; then
    log "Activating virtual environment from .venv"
    # shellcheck source=/dev/null
    source .venv/bin/activate
    export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"
else
    log "No .venv found, using uv or system Python"
fi

# ── SLIM Node Configuration ────────────────────────────────────────────────────
SLIM_CONTAINER_NAME="slim-node"
SLIM_IMAGE="ghcr.io/agntcy/slim:latest"
SLIM_PORT="${SLIM_PORT:-46357}"
SLIM_SHARED_SECRET="${SLIM_SHARED_SECRET:-tourist-scheduling-demo-secret-32}"
SLIM_TLS_INSECURE="${SLIM_TLS_INSECURE:-true}"
SLIM_ENDPOINT="http://localhost:${SLIM_PORT}"
PID_FILE=".demo_pids"

# ── Defaults ───────────────────────────────────────────────────────────────────
TRANSPORT=http
SCHED_PORT=10010
UI_WEB_PORT=10011
UI_A2A_PORT=10012
AUTONOMOUS=true
AUTO_DURATION=20
GUIDE_MIN_INTERVAL=1
GUIDE_MAX_INTERVAL=5
TOURIST_MIN_INTERVAL=1
TOURIST_MAX_INTERVAL=5

GUIDE_IDS=(guide-champs-elisees guide-louvre guide-eiffel-tower guide-notre-dame guide-montmartre)
TOURIST_IDS=(tourist-alice tourist-bob tourist-charlie tourist-diana tourist-ellen tourist-frank)

# ── SLIM Node Docker Functions ─────────────────────────────────────────────────
start_slim_node() {
    log "Starting SLIM node container..."
    if docker ps --format '{{.Names}}' | grep -q "^${SLIM_CONTAINER_NAME}$"; then
        log "Container '$SLIM_CONTAINER_NAME' is already running"
        return 0
    fi
    if docker ps -a --format '{{.Names}}' | grep -q "^${SLIM_CONTAINER_NAME}$"; then
        log "Removing stopped container '$SLIM_CONTAINER_NAME'"
        docker rm -f "$SLIM_CONTAINER_NAME" >/dev/null
    fi
    docker run -d \
        --name "$SLIM_CONTAINER_NAME" \
        -p "${SLIM_PORT}:46357" \
        -v "${ROOT_DIR}/slim-config.yaml:/config.yaml:ro" \
        "$SLIM_IMAGE" /slim -c /config.yaml
    log "SLIM node started on port $SLIM_PORT"
    # Wait for SLIM node to be ready (check port is open, since SLIM uses gRPC not HTTP)
    log "Waiting for SLIM node to be ready..."
    for i in {1..30}; do
        if nc -z localhost "$SLIM_PORT" 2>/dev/null; then
            ok "SLIM node is ready"
            return 0
        fi
        sleep 1
    done
    warn "SLIM node health check timed out (continuing anyway)"
}

stop_slim_node() {
    log "Stopping SLIM node container..."
    if docker ps --format '{{.Names}}' | grep -q "^${SLIM_CONTAINER_NAME}$"; then
        docker stop "$SLIM_CONTAINER_NAME" >/dev/null
        ok "SLIM node stopped"
    else
        log "SLIM node not running"
    fi
}

remove_slim_node() {
    log "Removing SLIM node container..."
    if docker ps -a --format '{{.Names}}' | grep -q "^${SLIM_CONTAINER_NAME}$"; then
        docker rm -f "$SLIM_CONTAINER_NAME" >/dev/null
        ok "SLIM node removed"
    else
        log "SLIM node container not found"
    fi
}

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
        for port in $SCHED_PORT $UI_WEB_PORT $UI_A2A_PORT; do
            local pid
            pid=$(lsof -ti tcp:$port 2>/dev/null || true)
            if [[ -n "$pid" ]]; then
                log "Killing process on port $port (PID $pid)"
                kill "$pid" 2>/dev/null || true
            fi
        done
        # Also kill by process name pattern for autonomous agents
        pkill -f "scheduler_agent" 2>/dev/null || true
        pkill -f "ui_agent" 2>/dev/null || true
        pkill -f "autonomous_guide_agent" 2>/dev/null || true
        pkill -f "autonomous_tourist_agent" 2>/dev/null || true
        ok "Agent processes stopped"
    fi
}

full_cleanup() {
    log "Full cleanup..."
    stop_agents
    remove_slim_node
    rm -f *.log "$PID_FILE" .slim_pids 2>/dev/null || true
    ok "Cleanup complete"
}

# ── Help ───────────────────────────────────────────────────────────────────────
usage() {
cat <<EOF
Usage: $0 [options] [-- extra runner args]
       $0 node {start|stop}              # SLIM node management
       $0 stop                           # Stop all agents
       $0 clean                          # Full cleanup (agents + SLIM node)

Transport Options:
        --transport MODE               Transport mode: http (default) or slim

Port Options:
        --scheduler-port N             Scheduler port (default: $SCHED_PORT)
        --ui-web-port N                UI web port (default: $UI_WEB_PORT)
        --ui-a2a-port N                UI A2A port (default: $UI_A2A_PORT)

Agent Options:
        --autonomous / --no-autonomous Enable or disable autonomous agents (default: $AUTONOMOUS)
        --auto-duration MIN            Autonomous duration minutes (default: $AUTO_DURATION)
        --guide-id ID                  Add guide ID (repeatable)
        --tourist-id ID                Add tourist ID (repeatable)
        --guides N                     Limit number of guide agents (alias: --auto-limit-guides)
        --tourists N                   Limit number of tourist agents (alias: --auto-limit-tourists)
        --auto-guide-min-interval S    Min seconds between guide offers (default: $GUIDE_MIN_INTERVAL)
        --auto-guide-max-interval S    Max seconds between guide offers (default: $GUIDE_MAX_INTERVAL)
        --auto-tourist-min-interval S  Min seconds between tourist requests (default: $TOURIST_MIN_INTERVAL)
        --auto-tourist-max-interval S  Max seconds between tourist requests (default: $TOURIST_MAX_INTERVAL)

SLIM Options (when --transport slim):
        SLIM_PORT                      SLIM node port (env, default: 46357)
        SLIM_SHARED_SECRET             Shared secret for SLIM (env, min 32 chars)

Examples:
        $0                             # HTTP mode with autonomous agents
        $0 --transport slim            # SLIM mode with autonomous agents
        $0 --transport slim --no-autonomous  # SLIM mode, no autonomous agents
        $0 node start                  # Start SLIM node only
        $0 clean                       # Stop everything and clean up

EOF
}

# ── Handle special commands first ──────────────────────────────────────────────
if [[ $# -ge 1 ]]; then
    case "$1" in
        node)
            if [[ $# -ge 2 ]]; then
                case "$2" in
                    start) start_slim_node; exit 0 ;;
                    stop) stop_slim_node; exit 0 ;;
                    *) err "Unknown node command: $2 (use: start, stop)"; exit 1 ;;
                esac
            else
                err "Usage: $0 node {start|stop}"; exit 1
            fi
            ;;
        stop) stop_agents; exit 0 ;;
        clean) full_cleanup; exit 0 ;;
        --help|-h) usage; exit 0 ;;
    esac
fi

# ── Parse CLI args ─────────────────────────────────────────────────────────────
PASS_ARGS=()
AUTO_LIMIT_GUIDES=""
AUTO_LIMIT_TOURISTS=""
while [[ $# -gt 0 ]]; do
        case "$1" in
                --transport) TRANSPORT=$2; shift 2;;
                --scheduler-port) SCHED_PORT=$2; shift 2;;
                --ui-web-port) UI_WEB_PORT=$2; shift 2;;
                --ui-a2a-port) UI_A2A_PORT=$2; shift 2;;
                --autonomous) AUTONOMOUS=true; shift;;
                --no-autonomous) AUTONOMOUS=false; shift;;
                --auto-duration) AUTO_DURATION=$2; shift 2;;
                --guide-id) GUIDE_IDS+=($2); shift 2;;
                --tourist-id) TOURIST_IDS+=($2); shift 2;;
                --guides|--auto-limit-guides) AUTO_LIMIT_GUIDES=$2; shift 2;;
                --tourists|--auto-limit-tourists) AUTO_LIMIT_TOURISTS=$2; shift 2;;
                --auto-guide-min-interval) GUIDE_MIN_INTERVAL=$2; shift 2;;
                --auto-guide-max-interval) GUIDE_MAX_INTERVAL=$2; shift 2;;
                --auto-tourist-min-interval) TOURIST_MIN_INTERVAL=$2; shift 2;;
                --auto-tourist-max-interval) TOURIST_MAX_INTERVAL=$2; shift 2;;
                --help|-h) usage; exit 0;;
                --) shift; PASS_ARGS=("$@"); break;;
                *) PASS_ARGS+=("$1"); shift;;
        esac
done

# ── Validation ─────────────────────────────────────────────────────────────────
for p in $SCHED_PORT $UI_WEB_PORT $UI_A2A_PORT; do
        [[ $p =~ ^[0-9]+$ ]] || { err "Port '$p' must be numeric"; exit 1; }
done

if [[ "$TRANSPORT" != "http" && "$TRANSPORT" != "slim" ]]; then
    err "Invalid transport mode: $TRANSPORT (use: http or slim)"
    exit 1
fi

[[ -x "$RUNNER_SCRIPT" ]] || { err "Runner not executable: $RUNNER_SCRIPT"; exit 1; }

# ── Apply limits ───────────────────────────────────────────────────────────────
if [[ -n "$AUTO_LIMIT_GUIDES" ]]; then
        if [[ ! $AUTO_LIMIT_GUIDES =~ ^[0-9]+$ ]]; then err "--auto-limit-guides must be numeric"; exit 1; fi
        if (( AUTO_LIMIT_GUIDES < ${#GUIDE_IDS[@]} )); then
                GUIDE_IDS=("${GUIDE_IDS[@]:0:$AUTO_LIMIT_GUIDES}")
        fi
fi
if [[ -n "$AUTO_LIMIT_TOURISTS" ]]; then
        if [[ ! $AUTO_LIMIT_TOURISTS =~ ^[0-9]+$ ]]; then err "--auto-limit-tourists must be numeric"; exit 1; fi
        if (( AUTO_LIMIT_TOURISTS < ${#TOURIST_IDS[@]} )); then
                TOURIST_IDS=("${TOURIST_IDS[@]:0:$AUTO_LIMIT_TOURISTS}")
        fi
fi

# ── SLIM mode: start SLIM node before launching agents ─────────────────────────
if [[ "$TRANSPORT" == "slim" ]]; then
    start_slim_node
    # Export SLIM env vars for agents
    export SLIM_ENDPOINT
    export SLIM_SHARED_SECRET
    export SLIM_TLS_INSECURE
fi

# ── Summary ────────────────────────────────────────────────────────────────────
echo "======================================================="
log "Transport: $TRANSPORT"
log "Scheduler:$SCHED_PORT UI:$UI_WEB_PORT/$UI_A2A_PORT Autonomous:$AUTONOMOUS Duration:${AUTO_DURATION}m"
log "Guides (${#GUIDE_IDS[@]}): ${GUIDE_IDS[*]}"
log "Tourists (${#TOURIST_IDS[@]}): ${TOURIST_IDS[*]}"
if [[ "$TRANSPORT" == "slim" ]]; then
    log "SLIM Endpoint: $SLIM_ENDPOINT"
fi
echo "======================================================="

# ── Build run args ─────────────────────────────────────────────────────────────
RUN_ARGS=(--transport "$TRANSPORT" --scheduler-port "$SCHED_PORT" --ui-web-port "$UI_WEB_PORT" --ui-a2a-port "$UI_A2A_PORT")
if [[ "$AUTONOMOUS" == true ]]; then
        RUN_ARGS+=(--autonomous --auto-duration "$AUTO_DURATION" --auto-guide-min-interval "$GUIDE_MIN_INTERVAL" --auto-guide-max-interval "$GUIDE_MAX_INTERVAL" --auto-tourist-min-interval "$TOURIST_MIN_INTERVAL" --auto-tourist-max-interval "$TOURIST_MAX_INTERVAL")
        # Pass aggregated lists via plural flags (space-separated). run_with_ui.sh will parse these into arrays.
        # Because IFS is set to newlines globally, ${ARRAY[*]} joins with newlines. Reconstruct space-separated lists explicitly.
        GUIDE_LIST="$(printf '%s ' "${GUIDE_IDS[@]}")"; GUIDE_LIST="${GUIDE_LIST% }"
        TOURIST_LIST="$(printf '%s ' "${TOURIST_IDS[@]}")"; TOURIST_LIST="${TOURIST_LIST% }"
        RUN_ARGS+=(--auto-guide-ids "$GUIDE_LIST" --auto-tourist-ids "$TOURIST_LIST")
fi

cleanup() { warn "Termination received; letting underlying script manage child processes."; }
trap cleanup INT TERM

log "Launching demo..."
"$RUNNER_SCRIPT" "${RUN_ARGS[@]}" ${PASS_ARGS[@]:-}
ok "Launch complete (background processes may continue)."
