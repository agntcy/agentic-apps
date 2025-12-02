#!/bin/bash
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
#
# Start Tourist Scheduling System with SLIM transport
#
# Prerequisites:
#   - Docker installed and running
#   - Install slim dependencies: uv pip install -e ".[slim]"
#
# Usage:
#   ./start_slim.sh              # Start SLIM node + all agents
#   ./start_slim.sh scheduler    # Start only the scheduler
#   ./start_slim.sh guide 1      # Start guide with ID 1
#   ./start_slim.sh tourist 1    # Start tourist with ID 1
#   ./start_slim.sh node start   # Start only the SLIM node
#   ./start_slim.sh node stop    # Stop only the SLIM node
#   ./start_slim.sh stop         # Stop all agents (keeps SLIM node running)
#   ./start_slim.sh clean        # Stop agents, stop and remove SLIM node

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
SLIM_CONTAINER_NAME="slim-node"
SLIM_IMAGE="ghcr.io/agntcy/slim:latest"
SLIM_PORT="${SLIM_PORT:-46357}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[SLIM]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[SLIM]${NC} $1"
}

err() {
    echo -e "${RED}[SLIM]${NC} $1" >&2
}

# Start SLIM node Docker container
start_slim_node() {
    # Check if container already exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${SLIM_CONTAINER_NAME}$"; then
        # Container exists, check if running
        if docker ps --format '{{.Names}}' | grep -q "^${SLIM_CONTAINER_NAME}$"; then
            log "SLIM node already running"
            return 0
        else
            log "Starting existing SLIM node container..."
            docker start "$SLIM_CONTAINER_NAME"
        fi
    else
        log "Creating and starting SLIM node container..."
        docker run -d \
            --name "$SLIM_CONTAINER_NAME" \
            -p "${SLIM_PORT}:46357" \
            -v "$(pwd)/slim-config.yaml:/config.yaml:ro" \
            "$SLIM_IMAGE" /slim -c /config.yaml
    fi

    # Wait for SLIM node to be ready
    log "Waiting for SLIM node to be ready..."
    for i in {1..30}; do
        if curl -s "$SLIM_ENDPOINT" > /dev/null 2>&1; then
            log "SLIM node is ready at $SLIM_ENDPOINT"
            return 0
        fi
        sleep 1
    done

    err "SLIM node failed to start within 30 seconds"
    return 1
}

# Stop SLIM node Docker container
stop_slim_node() {
    if docker ps --format '{{.Names}}' | grep -q "^${SLIM_CONTAINER_NAME}$"; then
        log "Stopping SLIM node container..."
        docker stop "$SLIM_CONTAINER_NAME"
    fi
}

# Remove SLIM node Docker container
remove_slim_node() {
    if docker ps -a --format '{{.Names}}' | grep -q "^${SLIM_CONTAINER_NAME}$"; then
        log "Removing SLIM node container..."
        docker rm -f "$SLIM_CONTAINER_NAME"
    fi
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

    # Start SLIM node if not running
    start_slim_node || exit 1

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
    log "Use './start_slim.sh stop' to stop agents, './start_slim.sh node stop' to stop SLIM node"
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

# Handle node subcommand
handle_node_command() {
    case "${1:-start}" in
        start)
            start_slim_node
            ;;
        stop)
            stop_slim_node
            ;;
        *)
            echo "Usage: $0 node {start|stop}"
            exit 1
            ;;
    esac
}

case "${1:-all}" in
    node)
        handle_node_command "${2:-start}"
        ;;
    scheduler)
        start_slim_node || exit 1
        start_scheduler
        ;;
    guide)
        start_slim_node || exit 1
        start_guide "${2:-1}"
        ;;
    tourist)
        start_slim_node || exit 1
        start_tourist "${2:-1}"
        ;;
    stop)
        stop_all
        ;;
    clean)
        stop_all
        stop_slim_node
        remove_slim_node
        log "Cleaned up all containers"
        ;;
    all)
        start_all
        ;;
    *)
        echo "Usage: $0 {all|node [start|stop]|scheduler|guide <id>|tourist <id>|stop|clean}"
        exit 1
        ;;
esac
