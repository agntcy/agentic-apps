#!/usr/bin/env bash
# Clean UI + Scheduler + Demo launcher (replaces legacy block)
set -euo pipefail

SCHED_PORT=${SCHED_PORT:-10010}
UI_WEB_PORT=${UI_WEB_PORT:-10011}
UI_A2A_PORT=${UI_A2A_PORT:-10012}
DEMO_GUIDES=${DEMO_GUIDES:-"g1 g2"}
DEMO_TOURISTS=${DEMO_TOURISTS:-"t1 t2"}
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
echo "Guides: $DEMO_GUIDES | Tourists: $DEMO_TOURISTS | Demo traffic: $([[ $NO_DEMO == true ]] && echo OFF || echo ON) | Autonomous: $([[ $AUTONOMOUS == true ]] && echo ON || echo OFF)"
echo "======================================================="

PROJECT_ROOT="$(dirname "$0")/.."; cd "$PROJECT_ROOT"
VENV=.venv
if [[ ! -d $VENV ]]; then
    python -m venv $VENV --copies
fi
source $VENV/bin/activate
export PYTHONPATH=src
pip install -q --upgrade pip
pip install -q -e .

cleanup() { echo "[cleanup] stopping session processes"; jobs -p | xargs -r kill 2>/dev/null || true; }
trap cleanup EXIT

start_or_reuse() {
    local port="$1"; shift
    local cmd=("$@")
    if lsof -ti tcp:$port >/dev/null 2>&1; then
        echo "[reuse] port $port already bound (PID $(lsof -ti tcp:$port | head -n1))"
    else
        echo "[start] ${cmd[*]}"
        nohup "${cmd[@]}" > "${cmd[1]}_${port}.log" 2>&1 &
    fi
}

start_or_reuse "$SCHED_PORT" python src/agents/scheduler_agent.py --host localhost --port "$SCHED_PORT"
sleep 2
start_or_reuse "$UI_WEB_PORT" python src/agents/ui_agent.py --host localhost --port "$UI_WEB_PORT" --a2a-port "$UI_A2A_PORT"
sleep 2

if [[ "$NO_DEMO" == false ]]; then
    echo "[demo] guide offers"
    for gid in $DEMO_GUIDES; do
        python src/agents/guide_agent.py --scheduler-url http://localhost:$SCHED_PORT --guide-id "$gid" || echo "guide $gid failed";
    done
    echo "[demo] tourist requests"
    for tid in $DEMO_TOURISTS; do
        python src/agents/tourist_agent.py --scheduler-url http://localhost:$SCHED_PORT --tourist-id "$tid" || echo "tourist $tid failed";
    done
fi

if [[ "$AUTONOMOUS" == true ]]; then
    echo "[autonomous] launching autonomous guide ($AUTO_GUIDE_ID) and tourist ($AUTO_TOURIST_ID) for ${AUTO_DURATION_MIN}m"
    echo "[autonomous] guide intervals: ${AUTO_GUIDE_MIN_INTERVAL}-${AUTO_GUIDE_MAX_INTERVAL}s | tourist intervals: ${AUTO_TOURIST_MIN_INTERVAL}-${AUTO_TOURIST_MAX_INTERVAL}s"
    nohup python src/agents/autonomous_guide_agent.py --scheduler-url http://localhost:$SCHED_PORT --guide-id "$AUTO_GUIDE_ID" --duration "$AUTO_DURATION_MIN" --min-interval "$AUTO_GUIDE_MIN_INTERVAL" --max-interval "$AUTO_GUIDE_MAX_INTERVAL" > autonomous_guide.log 2>&1 &
    nohup python src/agents/autonomous_tourist_agent.py --scheduler-url http://localhost:$SCHED_PORT --tourist-id "$AUTO_TOURIST_ID" --duration "$AUTO_DURATION_MIN" --min-interval "$AUTO_TOURIST_MIN_INTERVAL" --max-interval "$AUTO_TOURIST_MAX_INTERVAL" > autonomous_tourist.log 2>&1 &
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