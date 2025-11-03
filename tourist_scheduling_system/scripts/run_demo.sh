#!/usr/bin/env bash
# Multi-Agent Tourist Scheduling Demo
# Usage: ./scripts/run_demo.sh [--ui] [--scheduler-port 10010] [--ui-web-port 10011] [--ui-a2a-port 10012]
set -euo pipefail

UI=false
SCHEDULER_PORT=10010
UI_WEB_PORT=10011
UI_A2A_PORT=10012

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ui) UI=true; shift ;;
        --scheduler-port) SCHEDULER_PORT="$2"; shift 2 ;;
        --ui-web-port) UI_WEB_PORT="$2"; shift 2 ;;
        --ui-a2a-port) UI_A2A_PORT="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

echo "===================================================="
echo "A2A Multi-Agent Tourist Scheduling Demo"
echo "Scheduler Port: $SCHEDULER_PORT"
if $UI; then echo "UI Web Port: $UI_WEB_PORT | UI A2A Port: $UI_A2A_PORT"; fi
echo "===================================================="

cd "$(dirname "$0")/.."  # project root

if ! command -v python &>/dev/null; then
    echo "Python not found"; exit 1
fi

VENV=.venv
if [[ ! -d $VENV ]]; then
    echo "[setup] creating venv"
    python -m venv $VENV --copies
fi
source $VENV/bin/activate
export PYTHONPATH=src
pip install -q --upgrade pip
pip install -q -e .

echo "[1] Starting scheduler"
if lsof -ti tcp:$SCHEDULER_PORT >/dev/null 2>&1; then
    echo "Scheduler port $SCHEDULER_PORT already in use; reusing existing process"
    SCHEDULER_PID=$(lsof -ti tcp:$SCHEDULER_PORT | head -n1)
else
    nohup python src/agents/scheduler_agent.py --host localhost --port $SCHEDULER_PORT > scheduler_demo.log 2>&1 &
    SCHEDULER_PID=$!
    sleep 2
    if ! kill -0 $SCHEDULER_PID 2>/dev/null; then
        echo "Scheduler failed"; tail -n 40 scheduler_demo.log; exit 1
    fi
fi
echo "Scheduler running PID=$SCHEDULER_PID"

if $UI; then
    echo "[2] Starting UI agent"
    if lsof -ti tcp:$UI_WEB_PORT >/dev/null 2>&1 || lsof -ti tcp:$UI_A2A_PORT >/dev/null 2>&1; then
        echo "UI ports already in use; reusing existing UI process"
        # Try to infer PID from web port first
        UI_PID=$(lsof -ti tcp:$UI_WEB_PORT | head -n1 || lsof -ti tcp:$UI_A2A_PORT | head -n1)
    else
        nohup python src/agents/ui_agent.py --host localhost --port $UI_WEB_PORT --a2a-port $UI_A2A_PORT > ui_demo.log 2>&1 &
        UI_PID=$!
        sleep 2
        if ! kill -0 $UI_PID 2>/dev/null; then
            echo "UI failed"; tail -n 40 ui_demo.log; exit 1
        fi
    fi
    echo "UI running PID=$UI_PID"
fi

echo "[3] Sending guide offers"
for gid in g1 g2 g3; do
    python src/agents/guide_agent.py --scheduler-url http://localhost:$SCHEDULER_PORT --guide-id "$gid" || echo "Guide $gid failed"
done

echo "[4] Sending tourist requests"
for tid in t1 t2 t3; do
    python src/agents/tourist_agent.py --scheduler-url http://localhost:$SCHEDULER_PORT --tourist-id "$tid" || echo "Tourist $tid failed"
done

echo "===================================================="
echo "✅ Demo Complete"
echo "Logs: scheduler_demo.log"; $UI && echo "UI log: ui_demo.log"
if $UI; then echo "Dashboard: http://localhost:$UI_WEB_PORT"; fi
echo "Stop: kill $SCHEDULER_PID"; $UI && echo "Kill UI: kill $UI_PID"
echo "===================================================="
