#!/bin/bash
# Deploy Tourist Scheduling System to Kubernetes
#
# Usage:
#   ./deploy.sh                    # Deploy with HTTP transport
#   ./deploy.sh slim               # Deploy with SLIM transport
#   ./deploy.sh clean              # Remove all resources
#
# Environment variables:
#   NAMESPACE          - Target namespace (default: lumuscar-jobs)
#   IMAGE_REGISTRY     - Container registry (default: ghcr.io/agntcy/apps)
#   IMAGE_TAG          - Image tag (default: latest)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Export all variables for envsubst
export NAMESPACE="${NAMESPACE:-lumuscar-jobs}"
export IMAGE_REGISTRY="${IMAGE_REGISTRY:-ghcr.io/agntcy/apps}"
export IMAGE_TAG="${IMAGE_TAG:-latest}"
export TRANSPORT_MODE="${TRANSPORT_MODE:-http}"
export MODEL_PROVIDER="${MODEL_PROVIDER:-}"
export MODEL_NAME="${MODEL_NAME:-}"
export SLIM_GATEWAY_HOST="${SLIM_GATEWAY_HOST:-slim-slim-node}"
export SLIM_GATEWAY_PORT="${SLIM_GATEWAY_PORT:-46357}"
export SCHEDULER_URL="${SCHEDULER_URL:-http://scheduler-agent:10000}"
export UI_DASHBOARD_URL="${UI_DASHBOARD_URL:-http://ui-dashboard-agent:10021}"

# Proxy configuration (optional - for environments requiring proxy for external access)
export HTTP_PROXY="${HTTP_PROXY:-}"
export HTTPS_PROXY="${HTTPS_PROXY:-}"

# Ensure NO_PROXY includes necessary internal services
DEFAULT_NO_PROXY="localhost,127.0.0.1,.cluster.local,slim-slim-node,scheduler-agent,ui-dashboard-agent"
if [[ -n "${NO_PROXY:-}" ]]; then
    # Avoid leading comma if NO_PROXY is set
    export NO_PROXY="${NO_PROXY},${DEFAULT_NO_PROXY}"
else
    export NO_PROXY="${DEFAULT_NO_PROXY}"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_usage() {
    echo "Usage: $0 [http|slim|clean|status]"
    echo ""
    echo "Commands:"
    echo "  http    Deploy with HTTP transport (default)"
    echo "  slim    Deploy with SLIM transport (requires SLIM infrastructure)"
    echo "  clean   Remove all deployed resources"
    echo "  status  Show deployment status"
    echo ""
    echo "Environment Variables:"
    echo "  NAMESPACE                    Target namespace (default: lumuscar-jobs)"
    echo "  IMAGE_REGISTRY               Container registry (default: ghcr.io/agntcy/apps)"
    echo "  IMAGE_TAG                    Image tag (default: latest)"
    echo "  MODEL_PROVIDER               Model provider: azure or google"
    echo "  MODEL_NAME                   Specific model name (optional)"
    echo "  AZURE_OPENAI_API_KEY         Azure OpenAI API key (required for azure)"
    echo "  AZURE_OPENAI_ENDPOINT        Azure OpenAI endpoint URL (required for azure)"
    echo "  AZURE_OPENAI_DEPLOYMENT_NAME Azure OpenAI deployment name (default: gpt-4o)"
    echo "  AZURE_OPENAI_API_VERSION     Azure OpenAI API version (default: 2024-10-21)"
    echo "  GOOGLE_API_KEY               Google API key (required for google)"
}

# Create or update the google-credentials secret from environment variables
ensure_google_secret() {
    if [[ -n "${GOOGLE_API_KEY:-}" ]]; then
        log_info "Creating/updating google-credentials secret..."
        kubectl create secret generic google-credentials \
            --namespace "$NAMESPACE" \
            --from-literal=api-key="${GOOGLE_API_KEY}" \
            --dry-run=client -o yaml | kubectl apply -f -
    fi
}

# Create or update the azure-openai-credentials secret from environment variables
ensure_azure_secret() {
    if [[ -z "${AZURE_OPENAI_API_KEY:-}" ]]; then
        if [[ "$MODEL_PROVIDER" == "google" ]]; then
            return 0
        fi
        log_error "AZURE_OPENAI_API_KEY environment variable is not set"
        log_error "Please set the required environment variables:"
        echo "  export AZURE_OPENAI_API_KEY='your-api-key'"
        echo "  export AZURE_OPENAI_ENDPOINT='https://your-resource.openai.azure.com/'"
        echo "  export AZURE_OPENAI_DEPLOYMENT_NAME='gpt-4o'"
        exit 1
    fi

    if [[ -z "${AZURE_OPENAI_ENDPOINT:-}" ]]; then
        log_error "AZURE_OPENAI_ENDPOINT environment variable is not set"
        exit 1
    fi

    local deployment_name="${AZURE_OPENAI_DEPLOYMENT_NAME:-gpt-4o}"

    log_info "Creating/updating azure-openai-credentials secret..."
    kubectl create secret generic azure-openai-credentials \
        --namespace "$NAMESPACE" \
        --from-literal=api-key="${AZURE_OPENAI_API_KEY}" \
        --from-literal=endpoint="${AZURE_OPENAI_ENDPOINT}" \
        --from-literal=deployment-name="${deployment_name}" \
        --dry-run=client -o yaml | kubectl apply -f -
}

deploy_http() {
    log_info "Deploying Tourist Scheduling System with HTTP transport..."
    log_info "Namespace: $NAMESPACE"
    log_info "Image Registry: $IMAGE_REGISTRY"
    log_info "Image Tag: $IMAGE_TAG"

    # Set transport mode to HTTP
    export TRANSPORT_MODE=http
    export SCHEDULER_URL="http://scheduler-agent:10000"
    export UI_DASHBOARD_URL="http://ui-dashboard-agent:10021"

    # Verify namespace exists
    if ! kubectl get namespace "$NAMESPACE" &>/dev/null; then
        log_error "Namespace '$NAMESPACE' does not exist. Please create it first:"
        echo "  kubectl create namespace $NAMESPACE"
        exit 1
    fi

    # Create/update azure credentials secret
    ensure_azure_secret

    # Deploy configmap
    log_info "Deploying configmap..."
    envsubst < "$SCRIPT_DIR/configmap.yaml" | kubectl apply -f -

    # Patch configmap with proxy values if set
    if [[ -n "$HTTP_PROXY" || -n "$HTTPS_PROXY" ]]; then
        log_info "Patching agent-config ConfigMap with proxy values..."
        kubectl patch configmap agent-config -n "$NAMESPACE" --type merge -p '{"data":{"HTTP_PROXY":"'${HTTP_PROXY}'","HTTPS_PROXY":"'${HTTPS_PROXY}'","NO_PROXY":"'${NO_PROXY}'"}}'
    fi

    # Deploy scheduler agent
    log_info "Deploying scheduler agent..."
    envsubst < "$SCRIPT_DIR/scheduler-agent.yaml" | kubectl apply -f -

    # Deploy UI dashboard agent
    log_info "Deploying UI dashboard agent..."
    envsubst < "$SCRIPT_DIR/ui-agent.yaml" | kubectl apply -f -

    log_info "Deployment complete!"
    log_info ""
    log_info "To deploy guide agents:"
    log_info "  NAMESPACE=$NAMESPACE IMAGE_REGISTRY=$IMAGE_REGISTRY envsubst < deploy/k8s/guide-agent.yaml | kubectl apply -f -"
    log_info ""
    log_info "To deploy tourist agents:"
    log_info "  NAMESPACE=$NAMESPACE IMAGE_REGISTRY=$IMAGE_REGISTRY envsubst < deploy/k8s/tourist-agent.yaml | kubectl apply -f -"
}

deploy_slim() {
    log_info "Deploying Tourist Scheduling System with SLIM transport..."
    log_info "Namespace: $NAMESPACE"
    log_info "Image Registry: $IMAGE_REGISTRY"
    log_info "Image Tag: $IMAGE_TAG"

    # Check if SLIM is installed
    if ! kubectl get pods -l app.kubernetes.io/name=slim-node -n "$NAMESPACE" &>/dev/null; then
        log_warn "SLIM node not found in namespace '$NAMESPACE'"
        log_warn "Please install SLIM infrastructure first."
        log_warn "See scripts/slim-node.sh for installation."
    fi

    # Set transport mode to SLIM
    export TRANSPORT_MODE=slim
    export SLIM_GATEWAY_HOST="${SLIM_GATEWAY_HOST:-slim-slim-node}"
    export SLIM_GATEWAY_PORT="${SLIM_GATEWAY_PORT:-46357}"
    # For SLIM mode, agents communicate via gateway, not direct HTTP
    export SCHEDULER_URL="http://scheduler-agent:10000"
    export UI_DASHBOARD_URL="http://ui-dashboard-agent:10021"

    # Verify namespace exists
    if ! kubectl get namespace "$NAMESPACE" &>/dev/null; then
        log_error "Namespace '$NAMESPACE' does not exist. Please create it first:"
        echo "  kubectl create namespace $NAMESPACE"
        exit 1
    fi

    # Create/update azure credentials secret
    ensure_azure_secret

    # Deploy configmap
    log_info "Deploying configmap..."
    envsubst < "$SCRIPT_DIR/configmap.yaml" | kubectl apply -f -

    # Patch configmap with proxy values if set
    if [[ -n "$HTTP_PROXY" || -n "$HTTPS_PROXY" ]]; then
        log_info "Patching agent-config ConfigMap with proxy values..."
        kubectl patch configmap agent-config -n "$NAMESPACE" --type merge -p '{"data":{"HTTP_PROXY":"'${HTTP_PROXY}'","HTTPS_PROXY":"'${HTTPS_PROXY}'","NO_PROXY":"'${NO_PROXY}'"}}'
    fi

    # Deploy scheduler agent
    log_info "Deploying scheduler agent..."
    envsubst < "$SCRIPT_DIR/scheduler-agent.yaml" | kubectl apply -f -

    # Deploy UI dashboard agent
    log_info "Deploying UI dashboard agent..."
    envsubst < "$SCRIPT_DIR/ui-agent.yaml" | kubectl apply -f -

    log_info "Deployment complete with SLIM transport!"
    log_info ""
    log_info "Agents will communicate via SLIM gateway at:"
    log_info "  Host: $SLIM_GATEWAY_HOST"
    log_info "  Port: $SLIM_GATEWAY_PORT"
}

clean() {
    log_info "Removing Tourist Scheduling System resources from $NAMESPACE..."

    # Delete jobs first
    kubectl delete jobs -l app.kubernetes.io/part-of=tourist-scheduling -n "$NAMESPACE" --ignore-not-found

    # Delete deployments
    kubectl delete deployments -l app.kubernetes.io/part-of=tourist-scheduling -n "$NAMESPACE" --ignore-not-found

    # Delete services
    kubectl delete services -l app.kubernetes.io/part-of=tourist-scheduling -n "$NAMESPACE" --ignore-not-found

    # Delete configmap
    kubectl delete configmap agent-config -n "$NAMESPACE" --ignore-not-found

    log_info "Resources removed. Namespace and secrets preserved."
    log_info "To delete namespace: kubectl delete namespace $NAMESPACE"
}

status() {
    log_info "Tourist Scheduling System Status in $NAMESPACE"
    echo ""

    echo "=== Pods ==="
    kubectl get pods -l app.kubernetes.io/part-of=tourist-scheduling -n "$NAMESPACE" -o wide 2>/dev/null || echo "No pods found"
    echo ""

    echo "=== Services ==="
    kubectl get svc -l app.kubernetes.io/part-of=tourist-scheduling -n "$NAMESPACE" 2>/dev/null || echo "No services found"
    echo ""

    echo "=== Jobs ==="
    kubectl get jobs -l app.kubernetes.io/part-of=tourist-scheduling -n "$NAMESPACE" 2>/dev/null || echo "No jobs found"
    echo ""

    echo "=== ConfigMap ==="
    kubectl get configmap agent-config -n "$NAMESPACE" -o yaml 2>/dev/null | grep -A20 "^data:" || echo "ConfigMap not found"
}

# Main
case "${1:-http}" in
    http)
        deploy_http
        ;;
    slim)
        deploy_slim
        ;;
    clean)
        clean
        ;;
    status)
        status
        ;;
    -h|--help|help)
        show_usage
        ;;
    *)
        log_error "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac
