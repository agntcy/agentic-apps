#!/usr/bin/env bash
# Clean UI + Scheduler + Demo launcher (replaces legacy block)
# Requires bash 4+ for associative arrays.
set -euo pipefail

# This script now uses uv exclusively for dependency resolution and execution.
# It no longer creates or manages a pip virtual environment or installs the
# package in editable mode. Source layout is used with PYTHONPATH=src.

HEALTH_RETRIES=${HEALTH_RETRIES:-25}
HEALTH_INTERVAL=${HEALTH_INTERVAL:-0.4}

SCHED_PORT=${SCHED_PORT:-10010}
UI_WEB_PORT=${UI_WEB_PORT:-10011}
UI_A2A_PORT=${UI_A2A_PORT:-10012}
DEMO_GUIDES=${DEMO_GUIDES:-"g1 g2"}
DEMO_TOURISTS=${DEMO_TOURISTS:-"t1 t2"}
# Flags tracking whether user explicitly overrode demo sets via CLI
DEMO_GUIDES_SET=false
DEMO_TOURISTS_SET=false
DEMO_ROUNDS=${DEMO_ROUNDS:-1}
NO_DEMO=${NO_DEMO:-false}
AUTONOMOUS=${AUTONOMOUS:-false}
# PID tracking arrays
STARTED_PIDS=()
PID_KIND_KEYS=()
PID_KIND_VALUES=()

pid_kind_set() {
    local pid="$1" kind="$2"
    PID_KIND_KEYS+=("$pid")
    PID_KIND_VALUES+=("$kind")
}
pid_kind_get() {
    local pid="$1"
    for i in "${!PID_KIND_KEYS[@]}"; do
        if [[ "${PID_KIND_KEYS[$i]}" == "$pid" ]]; then
            echo "${PID_KIND_VALUES[$i]}"; return 0
        fi
    done
    echo "unknown"
}
AUTO_GUIDE_ID=${AUTO_GUIDE_ID:-auto-g-1}
AUTO_TOURIST_ID=${AUTO_TOURIST_ID:-auto-t-1}
# Support multiple autonomous agents via comma or space separated lists
AUTO_GUIDE_IDS=${AUTO_GUIDE_IDS:-""}
AUTO_TOURIST_IDS=${AUTO_TOURIST_IDS:-""}
AUTO_DURATION_MIN=${AUTO_DURATION_MIN:-2}
AUTO_GUIDE_MIN_INTERVAL=${AUTO_GUIDE_MIN_INTERVAL:-10}
AUTO_GUIDE_MAX_INTERVAL=${AUTO_GUIDE_MAX_INTERVAL:-30}
AUTO_TOURIST_MIN_INTERVAL=${AUTO_TOURIST_MIN_INTERVAL:-20}
AUTO_TOURIST_MAX_INTERVAL=${AUTO_TOURIST_MAX_INTERVAL:-40}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scheduler-port) SCHED_PORT="$2"; shift 2 ;;
        --ui-web-port) UI_WEB_PORT="$2"; shift 2 ;;
        --ui-a2a-port) UI_A2A_PORT="$2"; shift 2 ;;
        --guides) DEMO_GUIDES="$2"; DEMO_GUIDES_SET=true; shift 2 ;;
    --tourists) DEMO_TOURISTS="$2"; DEMO_TOURISTS_SET=true; shift 2 ;;
    --demo-rounds) DEMO_ROUNDS="$2"; shift 2 ;;
    --no-demo) NO_DEMO=true; shift ;;
    --autonomous) AUTONOMOUS=true; shift ;;
    --auto-guide-id) AUTO_GUIDE_ID="$2"; shift 2 ;;
    --auto-tourist-id) AUTO_TOURIST_ID="$2"; shift 2 ;;
    --auto-guide-ids) AUTO_GUIDE_IDS="$2"; shift 2 ;;
    --auto-tourist-ids) AUTO_TOURIST_IDS="$2"; shift 2 ;;
    --auto-duration) AUTO_DURATION_MIN="$2"; shift 2 ;;
    --auto-guide-min-interval) AUTO_GUIDE_MIN_INTERVAL="$2"; shift 2 ;;
    --auto-guide-max-interval) AUTO_GUIDE_MAX_INTERVAL="$2"; shift 2 ;;
    --auto-tourist-min-interval) AUTO_TOURIST_MIN_INTERVAL="$2"; shift 2 ;;
    --auto-tourist-max-interval) AUTO_TOURIST_MAX_INTERVAL="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

echo "======================================================="
echo "UI Demo Launcher"
echo "Scheduler: $SCHED_PORT | UI Web: $UI_WEB_PORT | UI A2A: $UI_A2A_PORT"
echo "Guides: $DEMO_GUIDES | Tourists: $DEMO_TOURISTS | Rounds: $DEMO_ROUNDS | Demo traffic: $([[ $NO_DEMO == true ]] && echo OFF || echo ON) | Autonomous: $([[ $AUTONOMOUS == true ]] && echo ON || echo OFF)"
echo "======================================================="

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$PROJECT_ROOT"
export PYTHONPATH=src

if ! command -v uv >/dev/null 2>&1; then
    echo "[fatal] 'uv' command not found. Install from https://github.com/astral-sh/uv" >&2
    exit 1
fi

# Pure global usage: rely on system/installed environment; uv will resolve on demand.
echo "[env] Skipping virtual environment creation (global uv usage)"
if [[ ! -f uv.lock ]]; then
    echo "[env] (optional) generate lock for reproducibility: uv lock";
fi

graceful_shutdown() {
    echo "[shutdown] initiating graceful termination of started processes (${#STARTED_PIDS[@]} total)"
    local pid
    for pid in "${STARTED_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "[shutdown] TERM $pid ($(pid_kind_get "$pid"))"
            kill "$pid" 2>/dev/null || true
        fi
    done
    # Wait up to 5s for exit
    local waited=0
    while (( waited < 50 )); do
        local alive=0
        for pid in "${STARTED_PIDS[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then alive=$((alive+1)); fi
        done
        (( alive == 0 )) && break
        sleep 0.1; waited=$((waited+1))
    done
    # Force kill remaining
    for pid in "${STARTED_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "[shutdown] KILL $pid ($(pid_kind_get "$pid"))"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    echo "[shutdown] summary:";
    for pid in "${STARTED_PIDS[@]}"; do
        local status="exited"
        kill -0 "$pid" 2>/dev/null && status="forced"
        echo "[shutdown] pid=$pid kind=$(pid_kind_get "$pid") status=$status"
    done
}
trap graceful_shutdown EXIT INT TERM

start_or_reuse() {
    local port="$1"; shift
    local cmd=("$@")
    local script_name="proc"
    for arg in "${cmd[@]}"; do
        if [[ "$arg" == *.py ]]; then
            script_name="$(basename "$arg" .py)"
        fi
    done
    local log_file="${script_name}_${port}.log"
    if lsof -ti tcp:$port >/dev/null 2>&1; then
        local existing_pid
        existing_pid=$(lsof -ti tcp:$port | head -n1)
        echo "[reuse] port $port already bound (PID $existing_pid) -> reusing; log: $log_file"
        pid_kind_set "$existing_pid" "reused-$script_name"
    else
        echo "[start] ${cmd[*]} -> log: $log_file"
        nohup "${cmd[@]}" > "$log_file" 2>&1 &
        local child=$!
        STARTED_PIDS+=("$child")
        pid_kind_set "$child" "${script_name}"
    fi
}

start_or_reuse "$SCHED_PORT" uv run python src/agents/scheduler_agent.py --host localhost --port "$SCHED_PORT"
sleep 1
start_or_reuse "$UI_WEB_PORT" uv run python src/agents/ui_agent.py --host localhost --port "$UI_WEB_PORT" --a2a-port "$UI_A2A_PORT"

wait_for_health() {
    local name="$1" url="$2"; shift 2 || true
    echo "[health] checking $name at $url (retries=$HEALTH_RETRIES interval=${HEALTH_INTERVAL}s)"
    local attempt=0
    while (( attempt < HEALTH_RETRIES )); do
        if curl -fsS "$url" >/dev/null 2>&1; then
            echo "[health] $name OK (attempt $((attempt+1)))"
            return 0
        fi
        attempt=$((attempt+1))
        sleep "$HEALTH_INTERVAL"
    done
    echo "[health] FAILED: $name not healthy after $HEALTH_RETRIES attempts" >&2
    return 1
}

wait_for_scheduler_health() {
    local port="$1"
    echo "[health] scheduler (port $port) checking /health then / (fallback)"
    if curl -fsS "http://localhost:$port/health" >/dev/null 2>&1; then
        echo "[health] scheduler OK (/health)"; return 0
    fi
    if curl -fsS "http://localhost:$port/" >/dev/null 2>&1; then
        echo "[health] scheduler OK (root)"; return 0
    fi
    echo "[health] scheduler not healthy after fallback attempts"; return 1
}

wait_for_ui_health() {
    local port="$1"
    wait_for_health "ui" "http://localhost:$port/health"
}

# Dependency fallback: ensure starlette is present (required by a2a-sdk http-server extras)
if ! python -c "import starlette, sse_starlette" 2>/dev/null; then
    echo "[deps] Missing starlette/sse_starlette -> running 'uv sync'"
    uv sync || echo "[deps] uv sync failed (continuing anyway)"
fi

wait_for_scheduler_health "$SCHED_PORT" || echo "[warn] scheduler health check failed (continuing)"
wait_for_ui_health "$UI_WEB_PORT" || { echo "[fatal] ui not healthy; aborting demo launch"; exit 1; }

if [[ "$NO_DEMO" == false ]]; then
    # Auto-skip baseline demo if autonomous mode active and user did not explicitly set demo guide/tourist lists.
    if [[ "$AUTONOMOUS" == true && "$DEMO_GUIDES_SET" == false && "$DEMO_TOURISTS_SET" == false ]]; then
        echo "[demo] skipping baseline demo (autonomous agents provided, no explicit --guides/--tourists)"
    else
        for round in $(seq 1 "$DEMO_ROUNDS"); do
            echo "[demo] round $round guide offers"
            for gid in $DEMO_GUIDES; do
                uv run python src/agents/guide_agent.py --scheduler-url http://localhost:$SCHED_PORT --guide-id "$gid" || echo "guide $gid failed";
            done
            echo "[demo] round $round tourist requests"
            for tid in $DEMO_TOURISTS; do
                uv run python src/agents/tourist_agent.py --scheduler-url http://localhost:$SCHED_PORT --tourist-id "$tid" || echo "tourist $tid failed";
            done
        done
    fi
fi

if [[ "$AUTONOMOUS" == true ]]; then
    # Build arrays: if plural lists provided use them, else fallback to singular vars
    IFS=', ' read -r -a _guide_list <<< "${AUTO_GUIDE_IDS:-}"
    IFS=', ' read -r -a _tourist_list <<< "${AUTO_TOURIST_IDS:-}"
    if [[ ${#_guide_list[@]} -eq 0 ]]; then _guide_list=("$AUTO_GUIDE_ID"); fi
    if [[ ${#_tourist_list[@]} -eq 0 ]]; then _tourist_list=("$AUTO_TOURIST_ID"); fi

    echo "[autonomous] launching ${#_guide_list[@]} guide agent(s) and ${#_tourist_list[@]} tourist agent(s) for ${AUTO_DURATION_MIN}m"
    echo "[autonomous] guide intervals: ${AUTO_GUIDE_MIN_INTERVAL}-${AUTO_GUIDE_MAX_INTERVAL}s | tourist intervals: ${AUTO_TOURIST_MIN_INTERVAL}-${AUTO_TOURIST_MAX_INTERVAL}s"

    for gid in "${_guide_list[@]}"; do
        log_file="autonomous_guide_${gid}.log"
        echo "[autonomous] start guide $gid -> $log_file"
        nohup uv run python src/agents/autonomous_guide_agent.py --scheduler-url http://localhost:$SCHED_PORT --guide-id "$gid" --duration "$AUTO_DURATION_MIN" --min-interval "$AUTO_GUIDE_MIN_INTERVAL" --max-interval "$AUTO_GUIDE_MAX_INTERVAL" > "$log_file" 2>&1 &
        child=$!; STARTED_PIDS+=("$child"); pid_kind_set "$child" "auto-guide:$gid"
    done
    for tid in "${_tourist_list[@]}"; do
        log_file="autonomous_tourist_${tid}.log"
        echo "[autonomous] start tourist $tid -> $log_file"
        nohup uv run python src/agents/autonomous_tourist_agent.py --scheduler-url http://localhost:$SCHED_PORT --tourist-id "$tid" --duration "$AUTO_DURATION_MIN" --min-interval "$AUTO_TOURIST_MIN_INTERVAL" --max-interval "$AUTO_TOURIST_MAX_INTERVAL" > "$log_file" 2>&1 &
        child=$!; STARTED_PIDS+=("$child"); pid_kind_set "$child" "auto-tourist:$tid"
    done
    echo -n "[autonomous] logs: "
    ls autonomous_guide_*.log autonomous_tourist_*.log 2>/dev/null || echo "(none?)"
fi

echo "======================================================="
echo "Dashboard: http://localhost:$UI_WEB_PORT"
echo "Scheduler: http://localhost:$SCHED_PORT"
echo "UI A2A:    http://localhost:$UI_A2A_PORT"
echo "Logs: tail -f scheduler_agent_${SCHED_PORT}.log ui_agent_${UI_WEB_PORT}.log"
if [[ "$AUTONOMOUS" == true ]]; then
    echo "Autonomous logs: tail -f autonomous_guide_*.log autonomous_tourist_*.log"
fi
echo "Ctrl+C to exit"
echo "======================================================="

wait || true