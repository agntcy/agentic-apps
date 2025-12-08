#!/bin/bash
# Generate and deploy multiple guide and tourist agents
#
# Usage:
#   ./spawn-agents.sh guides 5           # Spawn 5 guide agents
#   ./spawn-agents.sh tourists 10        # Spawn 10 tourist agents
#   ./spawn-agents.sh both 5 10          # Spawn 5 guides and 10 tourists
#   ./spawn-agents.sh clean              # Remove all agent jobs
#   ./spawn-agents.sh status             # Show agent job status
#
# Environment variables:
#   NAMESPACE          - Target namespace (default: lumuscar-jobs)
#   IMAGE_REGISTRY     - Container registry (default: ghcr.io/agntcy)
#   IMAGE_TAG          - Image tag (default: latest)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="${NAMESPACE:-lumuscar-jobs}"
IMAGE_REGISTRY="${IMAGE_REGISTRY:-ghcr.io/agntcy}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Guide categories pool
CATEGORIES=(
    "culture,history"
    "art,architecture"
    "food,wine"
    "nature,adventure"
    "photography,art"
    "history,architecture"
    "food,culture"
    "adventure,nature"
    "music,nightlife"
    "shopping,fashion"
)

# Tourist preferences pool
PREFERENCES=(
    "culture,history"
    "art,food"
    "nature,photography"
    "architecture,history"
    "wine,food"
    "adventure,nature"
    "shopping,culture"
    "nightlife,food"
    "museums,art"
    "beaches,relaxation"
)

# Generate random time within a range
random_hour() {
    local min=$1
    local max=$2
    echo $((min + RANDOM % (max - min + 1)))
}

# Generate a guide job
spawn_guide() {
    local id=$1
    local idx=$((id - 1))

    # Rotate through categories
    local cat_idx=$((idx % ${#CATEGORIES[@]}))
    export GUIDE_ID="g${id}"
    export GUIDE_CATEGORIES="${CATEGORIES[$cat_idx]}"

    # Random availability window
    local start_hour=$(random_hour 8 12)
    local end_hour=$((start_hour + 4 + RANDOM % 4))
    export GUIDE_START="2025-06-01T$(printf '%02d' $start_hour):00:00"
    export GUIDE_END="2025-06-01T$(printf '%02d' $end_hour):00:00"

    # Random rate and group size
    export GUIDE_RATE=$((40 + RANDOM % 60))
    export GUIDE_MAX_GROUP=$((2 + RANDOM % 8))

    log_info "Spawning guide ${GUIDE_ID}: ${GUIDE_CATEGORIES} (${GUIDE_START} - ${GUIDE_END}), \$${GUIDE_RATE}/hr, max ${GUIDE_MAX_GROUP}"

    envsubst < "$SCRIPT_DIR/templates/guide-agent.yaml.tpl" | kubectl apply -f -
}

# Generate a tourist job
spawn_tourist() {
    local id=$1
    local idx=$((id - 1))

    # Rotate through preferences
    local pref_idx=$((idx % ${#PREFERENCES[@]}))
    export TOURIST_ID="t${id}"
    export TOURIST_PREFERENCES="${PREFERENCES[$pref_idx]}"

    # Random availability window
    local start_hour=$(random_hour 8 14)
    local end_hour=$((start_hour + 3 + RANDOM % 5))
    export TOURIST_START="2025-06-01T$(printf '%02d' $start_hour):00:00"
    export TOURIST_END="2025-06-01T$(printf '%02d' $end_hour):00:00"

    # Random budget
    export TOURIST_BUDGET=$((50 + RANDOM % 150))

    log_info "Spawning tourist ${TOURIST_ID}: ${TOURIST_PREFERENCES} (${TOURIST_START} - ${TOURIST_END}), budget \$${TOURIST_BUDGET}"

    envsubst < "$SCRIPT_DIR/templates/tourist-agent.yaml.tpl" | kubectl apply -f -
}

spawn_guides() {
    local count=${1:-5}
    log_info "Spawning ${count} guide agents in namespace ${NAMESPACE}..."

    for i in $(seq 1 $count); do
        spawn_guide $i
    done

    log_info "Spawned ${count} guide agents"
}

spawn_tourists() {
    local count=${1:-10}
    log_info "Spawning ${count} tourist agents in namespace ${NAMESPACE}..."

    for i in $(seq 1 $count); do
        spawn_tourist $i
    done

    log_info "Spawned ${count} tourist agents"
}

clean() {
    log_info "Removing all agent jobs from ${NAMESPACE}..."

    kubectl delete jobs -l app=guide-agent -n "$NAMESPACE" --ignore-not-found
    kubectl delete jobs -l app=tourist-agent -n "$NAMESPACE" --ignore-not-found

    log_info "All agent jobs removed"
}

status() {
    echo -e "${BLUE}=== Guide Agents ===${NC}"
    kubectl get jobs -l app=guide-agent -n "$NAMESPACE" 2>/dev/null || echo "No guide agents found"
    echo ""

    echo -e "${BLUE}=== Tourist Agents ===${NC}"
    kubectl get jobs -l app=tourist-agent -n "$NAMESPACE" 2>/dev/null || echo "No tourist agents found"
    echo ""

    echo -e "${BLUE}=== Running Pods ===${NC}"
    kubectl get pods -l "app in (guide-agent,tourist-agent)" -n "$NAMESPACE" 2>/dev/null || echo "No agent pods running"
    echo ""

    echo -e "${BLUE}=== Summary ===${NC}"
    local guides=$(kubectl get jobs -l app=guide-agent -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l | tr -d ' ')
    local tourists=$(kubectl get jobs -l app=tourist-agent -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l | tr -d ' ')
    local completed=$(kubectl get jobs -l "app in (guide-agent,tourist-agent)" -n "$NAMESPACE" --no-headers 2>/dev/null | grep -c "1/1" || echo "0")
    echo "Guides: ${guides}, Tourists: ${tourists}, Completed: ${completed}"
}

logs() {
    local agent_type=${1:-guide}
    local id=${2:-1}

    kubectl logs -l "app=${agent_type}-agent,${agent_type}-id=${agent_type:0:1}${id}" -n "$NAMESPACE" --tail=100
}

show_usage() {
    echo "Usage: $0 <command> [args]"
    echo ""
    echo "Commands:"
    echo "  guides <count>         Spawn specified number of guide agents (default: 5)"
    echo "  tourists <count>       Spawn specified number of tourist agents (default: 10)"
    echo "  both <guides> <tourists>  Spawn both guides and tourists"
    echo "  clean                  Remove all agent jobs"
    echo "  status                 Show agent job status"
    echo "  logs <type> <id>       Show logs for specific agent (e.g., logs guide 1)"
    echo ""
    echo "Environment Variables:"
    echo "  NAMESPACE        Target namespace (default: lumuscar-jobs)"
    echo "  IMAGE_REGISTRY   Container registry (default: ghcr.io/agntcy)"
    echo "  IMAGE_TAG        Image tag (default: latest)"
    echo ""
    echo "Examples:"
    echo "  $0 guides 10           # Deploy 10 guides"
    echo "  $0 tourists 20         # Deploy 20 tourists"
    echo "  $0 both 5 15           # Deploy 5 guides and 15 tourists"
    echo "  $0 clean               # Remove all agents"
}

# Main
case "${1:-}" in
    guides)
        spawn_guides "${2:-5}"
        ;;
    tourists)
        spawn_tourists "${2:-10}"
        ;;
    both)
        spawn_guides "${2:-5}"
        spawn_tourists "${3:-10}"
        ;;
    clean)
        clean
        ;;
    status)
        status
        ;;
    logs)
        logs "${2:-guide}" "${3:-1}"
        ;;
    -h|--help|help|"")
        show_usage
        ;;
    *)
        log_error "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac
