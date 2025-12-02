#!/bin/bash
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
#
# Start Tourist Scheduling System with SLIM transport
#
# Prerequisites:
#   - SLIM node running on localhost:46357
#   - Install slim dependencies: uv pip install -e ".[slim]"
#
# Usage:
#   ./start_slim.sh              # Start all agents with SLIM transport
#   ./start_slim.sh scheduler    # Start only the scheduler
#   ./start_slim.sh guide 1      # Start guide with ID 1
#   ./start_slim.sh tourist 1    # Start tourist with ID 1

set -e

# Change to script directory
cd "$(dirname "$0")"

# Activate existing .venv
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Error: .venv not found. Create it first with: uv venv && uv pip install -e .[slim]"
    exit 1
fi

# Configuration
export SLIM_ENDPOINT="${SLIM_ENDPOINT:-http://localhost:46357}"
export SLIM_SHARED_SECRET="${SLIM_SHARED_SECRET:-demo-secret}"
export SLIM_TLS_INSECURE="${SLIM_TLS_INSECURE:-true}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[SLIM]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[SLIM]${NC} $1"
}

start_scheduler() {
    log "Starting Scheduler Agent with SLIM transport..."
    uv run python src/agents/scheduler_agent.py --transport slim \
        --slim-endpoint "$SLIM_ENDPOINT" \
        --slim-local-id "agntcy/tourist_scheduling/scheduler" &
    echo $! >> .slim_pids
}

start_guide() {
    local guide_id="${1:-1}"
    log "Starting Guide $guide_id with SLIM transport..."
    uv run python src/agents/autonomous_guide_server.py --transport slim \
        --guide-id "guide-$guide_id" \
        --slim-endpoint "$SLIM_ENDPOINT" \
        --slim-local-id "agntcy/tourist_scheduling/guide-$guide_id" &
    echo $! >> .slim_pids
}

start_tourist() {
    local tourist_id="${1:-1}"
    log "Starting Tourist $tourist_id with SLIM transport..."
    uv run python src/agents/autonomous_tourist_server.py --transport slim \
        --tourist-id "tourist-$tourist_id" \
        --slim-endpoint "$SLIM_ENDPOINT" \
        --slim-local-id "agntcy/tourist_scheduling/tourist-$tourist_id" &
    echo $! >> .slim_pids
}

start_all() {
    log "Starting all agents with SLIM transport..."

    # Clean up previous PIDs
    rm -f .slim_pids

    # Check if SLIM node is running
    if ! curl -s "$SLIM_ENDPOINT" > /dev/null 2>&1; then
        warn "SLIM node not reachable at $SLIM_ENDPOINT"
        warn "Make sure to start SLIM node first: docker run -p 46357:46357 ghcr.io/agntcy/slim:latest"
        exit 1
    fi

    # Start scheduler
    start_scheduler
    sleep 1

    # Start guides
    for i in 1 2 3 4 5; do
        start_guide $i
        sleep 0.5
    done

    # Start tourists
    for i in 1 2 3 4 5 6; do
        start_tourist $i
        sleep 0.5
    done

    log "All agents started. PIDs saved to .slim_pids"
    log "Use 'kill \$(cat .slim_pids)' to stop all agents"
}

stop_all() {
    log "Stopping all SLIM agents..."
    if [ -f .slim_pids ]; then
        while read pid; do
            kill "$pid" 2>/dev/null || true
        done < .slim_pids
        rm -f .slim_pids
    fi
    log "All agents stopped"
}

case "${1:-all}" in
    scheduler)
        start_scheduler
        ;;
    guide)
        start_guide "${2:-1}"
        ;;
    tourist)
        start_tourist "${2:-1}"
        ;;
    stop)
        stop_all
        ;;
    all)
        start_all
        ;;
    *)
        echo "Usage: $0 {all|scheduler|guide <id>|tourist <id>|stop}"
        exit 1
        ;;
esac
