#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Tourist Scheduling System - Infrastructure Setup Script
# Manages Docker containers for SLIM transport and Jaeger tracing
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# ── Colors / Logging ───────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}[SETUP]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── SLIM Configuration ─────────────────────────────────────────────────────────
SLIM_CONTAINER_NAME="slim-node"
SLIM_IMAGE="${SLIM_IMAGE:-ghcr.io/agntcy/slim:latest}"
SLIM_PORT="${SLIM_PORT:-46357}"
SLIM_SHARED_SECRET="${SLIM_SHARED_SECRET:-supersecretsharedsecret123456789}"  # Must be 32+ chars
SLIM_TLS_INSECURE="${SLIM_TLS_INSECURE:-true}"
SLIM_ENDPOINT="${SLIM_ENDPOINT:-http://localhost:${SLIM_PORT}}"
SLIM_CONFIG_FILE="${SLIM_CONFIG_FILE:-}"

# ── Jaeger Configuration ───────────────────────────────────────────────────────
JAEGER_CONTAINER_NAME="jaeger-tracing"
JAEGER_IMAGE="${JAEGER_IMAGE:-jaegertracing/all-in-one:latest}"
JAEGER_UI_PORT="${JAEGER_UI_PORT:-16686}"
JAEGER_OTLP_GRPC_PORT="${JAEGER_OTLP_GRPC_PORT:-4317}"
JAEGER_OTLP_HTTP_PORT="${JAEGER_OTLP_HTTP_PORT:-4318}"

# ── Directory Configuration ──────────────────────────────────────────────────────
DIR_CONTAINER_NAME="dir-service"
DIR_IMAGE="${DIR_IMAGE:-ghcr.io/agntcy/dir-apiserver:v0.5.7}"
DIR_PORT="${DIR_PORT:-8888}"
DIR_METRICS_PORT="${DIR_METRICS_PORT:-9090}"

# ── Zot Configuration (OCI Registry for Directory) ─────────────────────────────
ZOT_CONTAINER_NAME="zot-registry"
ZOT_IMAGE="${ZOT_IMAGE:-ghcr.io/project-zot/zot:v2.1.11}"
ZOT_PORT="${ZOT_PORT:-5001}"

# ── Network Configuration ──────────────────────────────────────────────────────
NETWORK_NAME="agentic-apps-net"

# ── Network Functions ──────────────────────────────────────────────────────────
ensure_network() {
    if ! docker network ls --format '{{.Name}}' | grep -q "^${NETWORK_NAME}$"; then
        log "Creating network '$NETWORK_NAME'..."
        docker network create "$NETWORK_NAME" >/dev/null
        ok "Network '$NETWORK_NAME' created"
    else
        log "Network '$NETWORK_NAME' already exists"
    fi
}

# ── Zot Functions ──────────────────────────────────────────────────────────────
start_zot() {
    ensure_network
    log "Starting Zot registry container..."
    if docker ps --format '{{.Names}}' | grep -q "^${ZOT_CONTAINER_NAME}$"; then
        log "Container '$ZOT_CONTAINER_NAME' is already running"
        return 0
    fi
    if docker ps -a --format '{{.Names}}' | grep -q "^${ZOT_CONTAINER_NAME}$"; then
        log "Removing stopped container '$ZOT_CONTAINER_NAME'"
        docker rm -f "$ZOT_CONTAINER_NAME" >/dev/null
    fi

    docker run -d \
        --name "$ZOT_CONTAINER_NAME" \
        --network "$NETWORK_NAME" \
        -p "${ZOT_PORT}:5000" \
        "$ZOT_IMAGE"

    log "Zot registry started on port $ZOT_PORT"

    # Wait for Zot to be ready
    log "Waiting for Zot to be ready..."
    for i in {1..15}; do
        if curl -s "http://localhost:${ZOT_PORT}/v2/" >/dev/null 2>&1; then
            ok "Zot registry is ready"
            return 0
        fi
        sleep 1
    done
    warn "Zot registry health check timed out (continuing anyway)"
}

stop_zot() {
    log "Stopping Zot registry container..."
    if docker ps --format '{{.Names}}' | grep -q "^${ZOT_CONTAINER_NAME}$"; then
        docker stop "$ZOT_CONTAINER_NAME" >/dev/null
        ok "Zot registry stopped"
    else
        log "Zot registry not running"
    fi
}

remove_zot() {
    log "Removing Zot registry container..."
    if docker ps -a --format '{{.Names}}' | grep -q "^${ZOT_CONTAINER_NAME}$"; then
        docker rm -f "$ZOT_CONTAINER_NAME" >/dev/null
        ok "Zot registry removed"
    else
        log "Zot registry container not found"
    fi
}


# ── SLIM Node Functions ────────────────────────────────────────────────────────
start_slim_node() {
    local with_otel="${1:-false}"

    log "Starting SLIM node container..."
    if docker ps --format '{{.Names}}' | grep -q "^${SLIM_CONTAINER_NAME}$"; then
        log "Container '$SLIM_CONTAINER_NAME' is already running"
        return 0
    fi
    if docker ps -a --format '{{.Names}}' | grep -q "^${SLIM_CONTAINER_NAME}$"; then
        log "Removing stopped container '$SLIM_CONTAINER_NAME'"
        docker rm -f "$SLIM_CONTAINER_NAME" >/dev/null
    fi

    # Determine config file
    local config_file
    if [[ -n "$SLIM_CONFIG_FILE" ]]; then
        config_file="$SLIM_CONFIG_FILE"
    elif [[ "$with_otel" == "true" ]]; then
        config_file="${ROOT_DIR}/slim-config-otel.yaml"
    else
        config_file="${ROOT_DIR}/slim-config.yaml"
    fi

    if [[ ! -f "$config_file" ]]; then
        err "SLIM config file not found: $config_file"
        exit 1
    fi

    log "Using SLIM config: $config_file"
    docker run -d \
        --name "$SLIM_CONTAINER_NAME" \
        -p "${SLIM_PORT}:46357" \
        -v "${config_file}:/config.yaml:ro" \
        "$SLIM_IMAGE" /slim -c /config.yaml

    log "SLIM node started on port $SLIM_PORT"

    # Wait for SLIM node to be ready
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

# ── Directory Functions ────────────────────────────────────────────────────────
start_directory() {
    start_zot

    log "Starting Directory service container..."
    if docker ps --format '{{.Names}}' | grep -q "^${DIR_CONTAINER_NAME}$"; then
        log "Container '$DIR_CONTAINER_NAME' is already running"
        return 0
    fi
    if docker ps -a --format '{{.Names}}' | grep -q "^${DIR_CONTAINER_NAME}$"; then
        log "Removing stopped container '$DIR_CONTAINER_NAME'"
        docker rm -f "$DIR_CONTAINER_NAME" >/dev/null
    fi

    docker run -d \
        --name "$DIR_CONTAINER_NAME" \
        --network "$NETWORK_NAME" \
        -p "${DIR_PORT}:8888" \
        -p "${DIR_METRICS_PORT}:9090" \
        -e DIRECTORY_SERVER_LISTEN_ADDRESS=0.0.0.0:8888 \
        -e DIRECTORY_SERVER_AUTHN_ENABLED=false \
        -e DIRECTORY_SERVER_STORE_PROVIDER=oci \
        -e DIRECTORY_SERVER_STORE_OCI_REGISTRY_ADDRESS=${ZOT_CONTAINER_NAME}:5000 \
        -e DIRECTORY_SERVER_STORE_OCI_REPOSITORY_NAME=dir \
        -e DIRECTORY_SERVER_STORE_OCI_AUTH_CONFIG_INSECURE=true \
        -e DIRECTORY_LOGGER_LOG_LEVEL=DEBUG \
        "$DIR_IMAGE"

    log "Directory service started:"
    log "  API:     localhost:${DIR_PORT}"
    log "  Metrics: localhost:${DIR_METRICS_PORT}"

    # Wait for Directory to be ready
    log "Waiting for Directory service to be ready..."
    for i in {1..15}; do
        # Use grpc-health-probe if available, or check logs/port
        if nc -z localhost "$DIR_PORT" 2>/dev/null; then
            ok "Directory service is ready"
            return 0
        fi
        sleep 1
    done
    warn "Directory service health check timed out (continuing anyway)"
}

stop_directory() {
    log "Stopping Directory service container..."
    if docker ps --format '{{.Names}}' | grep -q "^${DIR_CONTAINER_NAME}$"; then
        docker stop "$DIR_CONTAINER_NAME" >/dev/null
        ok "Directory service stopped"
    else
        log "Directory service not running"
    fi
    stop_zot
}

remove_directory() {
    log "Removing Directory service container..."
    if docker ps -a --format '{{.Names}}' | grep -q "^${DIR_CONTAINER_NAME}$"; then
        docker rm -f "$DIR_CONTAINER_NAME" >/dev/null
        ok "Directory service removed"
    else
        log "Directory service container not found"
    fi
    remove_zot
}

# ── Jaeger Functions ───────────────────────────────────────────────────────────
start_jaeger() {
    log "Starting Jaeger container for tracing..."
    if docker ps --format '{{.Names}}' | grep -q "^${JAEGER_CONTAINER_NAME}$"; then
        log "Container '$JAEGER_CONTAINER_NAME' is already running"
        return 0
    fi
    if docker ps -a --format '{{.Names}}' | grep -q "^${JAEGER_CONTAINER_NAME}$"; then
        log "Removing stopped container '$JAEGER_CONTAINER_NAME'"
        docker rm -f "$JAEGER_CONTAINER_NAME" >/dev/null
    fi

    docker run -d \
        --name "$JAEGER_CONTAINER_NAME" \
        -p "${JAEGER_UI_PORT}:16686" \
        -p "${JAEGER_OTLP_GRPC_PORT}:4317" \
        -p "${JAEGER_OTLP_HTTP_PORT}:4318" \
        -e COLLECTOR_OTLP_ENABLED=true \
        "$JAEGER_IMAGE"

    log "Jaeger started:"
    log "  UI:        http://localhost:${JAEGER_UI_PORT}"
    log "  OTLP gRPC: localhost:${JAEGER_OTLP_GRPC_PORT}"
    log "  OTLP HTTP: localhost:${JAEGER_OTLP_HTTP_PORT}"

    # Wait for Jaeger to be ready
    log "Waiting for Jaeger to be ready..."
    for i in {1..15}; do
        if curl -s "http://localhost:${JAEGER_UI_PORT}" >/dev/null 2>&1; then
            ok "Jaeger is ready"
            return 0
        fi
        sleep 1
    done
    warn "Jaeger health check timed out (continuing anyway)"
}

stop_jaeger() {
    log "Stopping Jaeger container..."
    if docker ps --format '{{.Names}}' | grep -q "^${JAEGER_CONTAINER_NAME}$"; then
        docker stop "$JAEGER_CONTAINER_NAME" >/dev/null
        ok "Jaeger stopped"
    else
        log "Jaeger not running"
    fi
}

remove_jaeger() {
    log "Removing Jaeger container..."
    if docker ps -a --format '{{.Names}}' | grep -q "^${JAEGER_CONTAINER_NAME}$"; then
        docker rm -f "$JAEGER_CONTAINER_NAME" >/dev/null
        ok "Jaeger removed"
    else
        log "Jaeger container not found"
    fi
}

# ── Status Function ────────────────────────────────────────────────────────────
show_status() {
    echo "======================================================="
    log "Infrastructure Status"
    echo "======================================================="

    # SLIM status
    if docker ps --format '{{.Names}}' | grep -q "^${SLIM_CONTAINER_NAME}$"; then
        ok "SLIM node: RUNNING on port $SLIM_PORT"
    elif docker ps -a --format '{{.Names}}' | grep -q "^${SLIM_CONTAINER_NAME}$"; then
        warn "SLIM node: STOPPED"
    else
        log "SLIM node: NOT CREATED"
    fi

    # Jaeger status
    if docker ps --format '{{.Names}}' | grep -q "^${JAEGER_CONTAINER_NAME}$"; then
        ok "Jaeger:    RUNNING - UI at http://localhost:${JAEGER_UI_PORT}"
    elif docker ps -a --format '{{.Names}}' | grep -q "^${JAEGER_CONTAINER_NAME}$"; then
        warn "Jaeger:    STOPPED"
    else
        log "Jaeger:    NOT CREATED"
    fi

    # Directory status
    if docker ps --format '{{.Names}}' | grep -q "^${DIR_CONTAINER_NAME}$"; then
        ok "Directory: RUNNING - API at localhost:${DIR_PORT}"
    elif docker ps -a --format '{{.Names}}' | grep -q "^${DIR_CONTAINER_NAME}$"; then
        warn "Directory: STOPPED"
    else
        log "Directory: NOT CREATED"
    fi

    echo "======================================================="
}

# ── Environment Export ─────────────────────────────────────────────────────────
print_env() {
    echo "# Add these to your environment before running demo:"
    echo "export SLIM_ENDPOINT=\"${SLIM_ENDPOINT}\""
    echo "export SLIM_SHARED_SECRET=\"${SLIM_SHARED_SECRET}\""
    echo "export SLIM_TLS_INSECURE=\"${SLIM_TLS_INSECURE}\""
    echo "export OTEL_EXPORTER_OTLP_ENDPOINT=\"http://localhost:${JAEGER_OTLP_HTTP_PORT}\""
    echo "export OTEL_SERVICE_NAME=\"tourist-scheduling\""
    echo "export DIRECTORY_CLIENT_SERVER_ADDRESS=\"localhost:${DIR_PORT}\""
}

# ── Help ───────────────────────────────────────────────────────────────────────
usage() {
cat <<EOF
Usage: $0 <command> [options]

Infrastructure Setup for Tourist Scheduling System.
Manages Docker containers for SLIM transport and Jaeger tracing.

Commands:
    start [--tracing]     Start infrastructure containers
                          --tracing: Also start Jaeger and use OTEL-enabled SLIM config

    stop                  Stop all infrastructure containers (keeps them for restart)

    clean                 Stop and remove all infrastructure containers
                          Also cleans up demo processes

    status                Show status of infrastructure containers

    env                   Print environment variables for demo script

    slim start            Start SLIM node only
    slim stop             Stop SLIM node
    slim remove           Remove SLIM node container

    jaeger start          Start Jaeger only
    jaeger stop           Stop Jaeger
    jaeger remove         Remove Jaeger container

    dir start             Start Directory service only
    dir stop              Stop Directory service
    dir remove            Remove Directory service container

Environment Variables:
    SLIM_PORT             SLIM node port (default: 46357)
    SLIM_IMAGE            SLIM Docker image (default: ghcr.io/agntcy/slim:latest)
    SLIM_SHARED_SECRET    SLIM shared secret (min 32 chars)
    SLIM_CONFIG_FILE      Custom SLIM config file path

    JAEGER_UI_PORT        Jaeger UI port (default: 16686)
    JAEGER_OTLP_GRPC_PORT OTLP gRPC port (default: 4317)
    JAEGER_OTLP_HTTP_PORT OTLP HTTP port (default: 4318)
    JAEGER_IMAGE          Jaeger Docker image (default: jaegertracing/all-in-one:latest)

Examples:
    $0 start                    # Start SLIM only
    $0 start --tracing          # Start SLIM + Jaeger with OTEL
    $0 status                   # Check what's running
    $0 stop                     # Stop containers
    $0 clean                    # Remove containers
    $0 env                      # Get env vars for run.sh

EOF
}

# ── Main ───────────────────────────────────────────────────────────────────────
if [[ $# -lt 1 ]]; then
    usage
    exit 1
fi

COMMAND="$1"
shift

case "$COMMAND" in
    start)
        WITH_TRACING=false
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --tracing) WITH_TRACING=true; shift ;;
                *) err "Unknown option: $1"; usage; exit 1 ;;
            esac
        done

        echo "======================================================="
        log "Starting Infrastructure"
        echo "======================================================="

        # Start SLIM node
        start_slim_node "$WITH_TRACING"

        # Start Directory service
        start_directory

        # Start Jaeger if tracing enabled
        if [[ "$WITH_TRACING" == "true" ]]; then
            start_jaeger
        fi

        echo "======================================================="
        ok "Infrastructure started"
        if [[ "$WITH_TRACING" == "true" ]]; then
            log "Jaeger UI: http://localhost:${JAEGER_UI_PORT}"
        fi
        echo "======================================================="
        ;;

    stop)
        echo "======================================================="
        log "Stopping Infrastructure"
        echo "======================================================="
        stop_slim_node
        stop_jaeger
        stop_directory
        ok "Infrastructure stopped"
        echo "======================================================="
        ;;

    clean)
        echo "======================================================="
        log "Cleaning Infrastructure and Demo Processes"
        echo "======================================================="

        # Clean demo processes first
        log "Stopping demo processes..."
        pkill -f "run_adk_demo.py" 2>/dev/null || true
        pkill -f "adk_scheduler_runner" 2>/dev/null || true
        pkill -f "adk_dashboard_runner" 2>/dev/null || true
        pkill -f "scheduler_agent" 2>/dev/null || true
        pkill -f "ui_agent" 2>/dev/null || true
        pkill -f "autonomous_guide_agent" 2>/dev/null || true
        pkill -f "autonomous_tourist_agent" 2>/dev/null || true

        # Clean up common demo ports
        for port in 10010 10011 10012 10021; do
            pid=$(lsof -ti tcp:$port 2>/dev/null || true)
            if [[ -n "$pid" ]]; then
                log "Killing process on port $port (PID $pid)"
                kill -9 "$pid" 2>/dev/null || true
            fi
        done

        # Remove infrastructure containers
        remove_slim_node
        remove_jaeger
        remove_directory

        # Clean up PID file
        rm -f "${ROOT_DIR}/.agent_pids" 2>/dev/null || true

        ok "Infrastructure and demo cleaned"
        echo "======================================================="
        ;;

    status)
        show_status
        ;;

    env)
        print_env
        ;;

    slim)
        if [[ $# -lt 1 ]]; then
            err "Usage: $0 slim {start|stop|remove}"
            exit 1
        fi
        case "$1" in
            start) start_slim_node ;;
            stop) stop_slim_node ;;
            remove) remove_slim_node ;;
            *) err "Unknown slim command: $1"; exit 1 ;;
        esac
        ;;

    jaeger)
        if [[ $# -lt 1 ]]; then
            err "Usage: $0 jaeger {start|stop|remove}"
            exit 1
        fi
        case "$1" in
            start) start_jaeger ;;
            stop) stop_jaeger ;;
            remove) remove_jaeger ;;
            *) err "Unknown jaeger command: $1"; exit 1 ;;
        esac
        ;;

    dir)
        if [[ $# -lt 1 ]]; then
            err "Usage: $0 dir {start|stop|remove}"
            exit 1
        fi
        case "$1" in
            start) start_directory ;;
            stop) stop_directory ;;
            remove) remove_directory ;;
            *) err "Unknown dir command: $1"; exit 1 ;;
        esac
        ;;

    --help|-h|help)
        usage
        ;;

    *)
        err "Unknown command: $COMMAND"
        usage
        exit 1
        ;;
esac
