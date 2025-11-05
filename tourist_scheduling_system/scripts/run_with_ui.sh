#!/usr/bin/env bash
# Clean UI + Scheduler + Demo launcher (replaces legacy block)
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
DEMO_ROUNDS=${DEMO_ROUNDS:-1}
NO_DEMO=${NO_DEMO:-false}
AUTONOMOUS=${AUTONOMOUS:-false}
AUTO_GUIDE_ID=${AUTO_GUIDE_ID:-auto-g-1}
AUTO_TOURIST_ID=${AUTO_TOURIST_ID:-auto-t-1}
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
        --guides) DEMO_GUIDES="$2"; shift 2 ;;
    --tourists) DEMO_TOURISTS="$2"; shift 2 ;;
    --demo-rounds) DEMO_ROUNDS="$2"; shift 2 ;;
    --no-demo) NO_DEMO=true; shift ;;
    --autonomous) AUTONOMOUS=true; shift ;;
    --auto-guide-id) AUTO_GUIDE_ID="$2"; shift 2 ;;
    --auto-tourist-id) AUTO_TOURIST_ID="$2"; shift 2 ;;
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

cleanup() { echo "[cleanup] stopping session processes"; jobs -p | xargs -r kill 2>/dev/null || true; }
trap cleanup EXIT

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
        echo "[reuse] port $port already bound (PID $(lsof -ti tcp:$port | head -n1)) -> reusing; log: $log_file"
    else
        echo "[start] ${cmd[*]} -> log: $log_file"
        nohup "${cmd[@]}" > "$log_file" 2>&1 &
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

if [[ "$AUTONOMOUS" == true ]]; then
    echo "[autonomous] launching autonomous guide ($AUTO_GUIDE_ID) and tourist ($AUTO_TOURIST_ID) for ${AUTO_DURATION_MIN}m"
    echo "[autonomous] guide intervals: ${AUTO_GUIDE_MIN_INTERVAL}-${AUTO_GUIDE_MAX_INTERVAL}s | tourist intervals: ${AUTO_TOURIST_MIN_INTERVAL}-${AUTO_TOURIST_MAX_INTERVAL}s"
    nohup uv run python src/agents/autonomous_guide_agent.py --scheduler-url http://localhost:$SCHED_PORT --guide-id "$AUTO_GUIDE_ID" --duration "$AUTO_DURATION_MIN" --min-interval "$AUTO_GUIDE_MIN_INTERVAL" --max-interval "$AUTO_GUIDE_MAX_INTERVAL" > autonomous_guide.log 2>&1 &
    nohup uv run python src/agents/autonomous_tourist_agent.py --scheduler-url http://localhost:$SCHED_PORT --tourist-id "$AUTO_TOURIST_ID" --duration "$AUTO_DURATION_MIN" --min-interval "$AUTO_TOURIST_MIN_INTERVAL" --max-interval "$AUTO_TOURIST_MAX_INTERVAL" > autonomous_tourist.log 2>&1 &
    echo "[autonomous] logs: autonomous_guide.log autonomous_tourist.log"
fi

echo "======================================================="
echo "Dashboard: http://localhost:$UI_WEB_PORT"
echo "Scheduler: http://localhost:$SCHED_PORT"
echo "UI A2A:    http://localhost:$UI_A2A_PORT"
echo "Logs: tail -f scheduler_agent_${SCHED_PORT}.log ui_agent_${UI_WEB_PORT}.log"
if [[ "$AUTONOMOUS" == true ]]; then
    echo "Autonomous logs: tail -f autonomous_guide.log autonomous_tourist.log"
fi
echo "Ctrl+C to exit"
echo "======================================================="

wait || true