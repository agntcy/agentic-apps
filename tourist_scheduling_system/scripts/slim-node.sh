#!/bin/bash
# SLIM Node (Data Plane) deployment script for Kubernetes
# Usage: ./slim-node.sh [install|uninstall|status|clean|logs] [node-name]
# SPIRE mode: SPIRE_ENABLED=true ./slim-node.sh install

set -e

NAMESPACE="${SLIM_NAMESPACE:-lumuscar-jobs}"
NODE_NAME="${2:-slim-node}"
RELEASE_NAME="slim-${NODE_NAME}"
CHART_VERSION="v0.7.0"
CHART_REPO="oci://ghcr.io/agntcy/slim/helm/slim"
CHART_FILE="slim-${CHART_VERSION}.tgz"

# SLIM Controller connection
CONTROLLER_HOST="${SLIM_CONTROLLER_HOST:-slim-control}"
CONTROLLER_PORT="${SLIM_CONTROLLER_PORT:-50052}"

# SPIRE Configuration
SPIRE_ENABLED="${SPIRE_ENABLED:-false}"
SPIRE_NAMESPACE="${SPIRE_NAMESPACE:-lumuscar-spire}"
SPIRE_TRUST_DOMAIN="${SPIRE_TRUST_DOMAIN:-example.org}"
SPIRE_CLUSTER_NAME="${SPIRE_CLUSTER_NAME:-slim-cluster}"

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

# Download the Helm chart if not present
download_chart() {
    if [ ! -f "$CHART_FILE" ]; then
        log_info "Downloading SLIM Helm chart ${CHART_VERSION}..."
        helm pull "${CHART_REPO}" --version "${CHART_VERSION}"
    else
        log_info "Chart file ${CHART_FILE} already exists"
    fi
}

# Register SLIM node workload with SPIRE
register_with_spire() {
    log_info "Registering SLIM node workload with SPIRE..."

    # Check if SPIRE server is available in SPIRE namespace
    if ! kubectl get pod -n "${SPIRE_NAMESPACE}" -l app.kubernetes.io/name=server -o name | grep -q "pod/"; then
        log_warn "SPIRE server not found in namespace ${SPIRE_NAMESPACE}, skipping registration"
        return 0
    fi

    local SPIRE_SERVER_POD
    SPIRE_SERVER_POD=$(kubectl get pod -n "${SPIRE_NAMESPACE}" -l app.kubernetes.io/name=server -o jsonpath='{.items[0].metadata.name}')

    log_info "Using SPIRE Server pod: ${SPIRE_SERVER_POD} in namespace ${SPIRE_NAMESPACE}"

    # Register SLIM Node
    log_info "Registering SLIM Node '${NODE_NAME}'..."
    kubectl exec -n "${SPIRE_NAMESPACE}" "${SPIRE_SERVER_POD}" -c spire-server -- \
        /opt/spire/bin/spire-server entry create \
        -spiffeID "spiffe://${SPIRE_TRUST_DOMAIN}/slim/node/${NODE_NAME}" \
        -parentID "spiffe://${SPIRE_TRUST_DOMAIN}/spire/agent/k8s_psat/${SPIRE_CLUSTER_NAME}" \
        -selector "k8s:ns:${NAMESPACE}" \
        -selector "k8s:sa:slim" \
        -dns "${NODE_NAME}" \
        -dns "${NODE_NAME}.${NAMESPACE}.svc.cluster.local" \
        2>/dev/null || log_warn "Node entry may already exist"

    log_info "SPIRE registration complete"
}

# Install SLIM node
install() {
    log_info "Installing SLIM node '${NODE_NAME}' in namespace ${NAMESPACE}..."
    log_info "Controller: ${CONTROLLER_HOST}:${CONTROLLER_PORT}"

    # Download chart if needed
    download_chart

    # Determine endpoint protocol based on SPIRE mode
    if [[ "${SPIRE_ENABLED}" == "true" ]]; then
        ENDPOINT_PROTOCOL="https"
        log_info "SPIRE mode enabled - using mTLS connection to controller"
    else
        ENDPOINT_PROTOCOL="http"
        log_info "SPIRE mode disabled - using insecure connection"
    fi

    # Build base Helm values
    HELM_VALUES=(
        --set slim.fullnameOverride="${NODE_NAME}"
        --set slim.config.services.slim/0.controller.clients[0].endpoint="${ENDPOINT_PROTOCOL}://${CONTROLLER_HOST}:${CONTROLLER_PORT}"
    )

    # Add SPIRE values if enabled
    if [[ "${SPIRE_ENABLED}" == "true" ]]; then
        HELM_VALUES+=(
            --set slim.config.services.slim/0.controller.clients[0].tls.insecure=false
            --set slim.config.services.slim/0.controller.clients[0].tls.useSpiffe=true
            --set spire.enabled=true
            --set spire.useCSIDriver=true
        )
    else
        HELM_VALUES+=(
            --set slim.config.services.slim/0.controller.clients[0].tls.insecure=true
        )
    fi

    # Check if release already exists
    if helm list -n "${NAMESPACE}" | grep -q "${RELEASE_NAME}"; then
        log_warn "Release ${RELEASE_NAME} already exists, upgrading..."
        helm upgrade "${RELEASE_NAME}" "${CHART_FILE}" \
            -n "${NAMESPACE}" \
            "${HELM_VALUES[@]}"
    else
        log_info "Installing new release..."
        helm install "${RELEASE_NAME}" "${CHART_FILE}" \
            -n "${NAMESPACE}" \
            "${HELM_VALUES[@]}"
    fi

    # Register with SPIRE if enabled
    if [[ "${SPIRE_ENABLED}" == "true" ]]; then
        register_with_spire
    fi

    log_info "Waiting for SLIM node to be ready..."
    kubectl rollout status statefulset/"${RELEASE_NAME}" -n "${NAMESPACE}" --timeout=120s || true

    status
}

# Clean all SLIM node resources
clean() {
    log_warn "Cleaning up all SLIM node '${NODE_NAME}' resources in namespace ${NAMESPACE}..."

    # Uninstall helm release
    if helm list -n "${NAMESPACE}" | grep -q "${RELEASE_NAME}"; then
        log_info "Uninstalling Helm release ${RELEASE_NAME}..."
        helm uninstall "${RELEASE_NAME}" -n "${NAMESPACE}" --wait 2>/dev/null || true
    fi

    # Remove helm release secrets (try multiple patterns)
    log_info "Removing Helm release secrets..."
    for secret in $(kubectl get secrets -n "${NAMESPACE}" -o name 2>/dev/null | grep -E "sh.helm.release.v1.${RELEASE_NAME}|sh.helm.release.v1.slim-${NODE_NAME}"); do
        log_info "Deleting ${secret}..."
        kubectl delete "${secret}" -n "${NAMESPACE}" 2>/dev/null || true
    done

    # Remove all resources - try multiple naming patterns
    # Pattern 1: NODE_NAME (from fullnameOverride)
    log_info "Removing resources with name '${NODE_NAME}'..."
    kubectl delete statefulset "${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete service "${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete configmap "${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete serviceaccount "${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true

    # Pattern 2: slim-NODE_NAME (helm release naming)
    kubectl delete statefulset "slim-${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete service "slim-${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete configmap "slim-${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete serviceaccount "slim-${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true

    # Pattern 3: default 'slim' (chart default name)
    kubectl delete statefulset "slim" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete service "slim" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete configmap "slim" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete serviceaccount "slim" -n "${NAMESPACE}" 2>/dev/null || true

    log_info "Cleanup complete"
}

# Show status
status() {
    log_info "SLIM Node '${NODE_NAME}' Status in namespace ${NAMESPACE}:"
    echo ""

    echo "=== Helm Release ==="
    helm list -n "${NAMESPACE}" | grep "${RELEASE_NAME}" || echo "No release found"
    echo ""

    echo "=== Pods ==="
    kubectl get pods -n "${NAMESPACE}" -l "app.kubernetes.io/instance=${RELEASE_NAME}" 2>/dev/null || echo "No pods found"
    echo ""

    echo "=== Services ==="
    kubectl get svc -n "${NAMESPACE}" "${RELEASE_NAME}" 2>/dev/null || echo "No services found"
    echo ""

    echo "=== StatefulSet ==="
    kubectl get statefulset -n "${NAMESPACE}" "${RELEASE_NAME}" 2>/dev/null || echo "No statefulset found"
}

# Show logs
logs() {
    log_info "Fetching SLIM node '${NODE_NAME}' logs..."
    kubectl logs -n "${NAMESPACE}" -l "app.kubernetes.io/instance=${RELEASE_NAME}" --tail=100 -f
}

# Port forward for local access
port_forward() {
    log_info "Setting up port forwarding for SLIM node '${NODE_NAME}'..."
    log_info "Data port: localhost:46357"
    log_info "Control port: localhost:46358"

    POD_NAME=$(kubectl get pods -n "${NAMESPACE}" -l "app.kubernetes.io/instance=${RELEASE_NAME}" -o jsonpath="{.items[0].metadata.name}")

    if [ -z "$POD_NAME" ]; then
        log_error "No SLIM node pod found"
        exit 1
    fi

    kubectl port-forward -n "${NAMESPACE}" "${POD_NAME}" 46357:46357 46358:46358
}

# List all SLIM nodes
list() {
    log_info "Listing all SLIM nodes in namespace ${NAMESPACE}:"
    echo ""

    echo "=== Helm Releases ==="
    helm list -n "${NAMESPACE}" | grep "slim-" || echo "No SLIM releases found"
    echo ""

    echo "=== Pods ==="
    kubectl get pods -n "${NAMESPACE}" -l "app.kubernetes.io/name=slim" 2>/dev/null || echo "No SLIM pods found"
}

# Show help
usage() {
    echo "SLIM Node (Data Plane) Deployment Script"
    echo ""
    echo "Usage: $0 <command> [node-name]"
    echo ""
    echo "Commands:"
    echo "  install [name]      Install or upgrade SLIM node (default: slim-node)"
    echo "  clean [name]        Remove all SLIM node resources"
    echo "  status [name]       Show deployment status"
    echo "  logs [name]         Stream SLIM node logs"
    echo "  port-forward [name] Set up port forwarding for local access"
    echo "  list                List all SLIM nodes in namespace"
    echo ""
    echo "Environment variables:"
    echo "  SLIM_NAMESPACE        Target namespace (default: lumuscar-jobs)"
    echo "  SLIM_CONTROLLER_HOST  Controller hostname (default: slim-control)"
    echo "  SLIM_CONTROLLER_PORT  Controller port (default: 50052)"
    echo "  SPIRE_ENABLED         Enable SPIRE mTLS (default: false)"
    echo "  SPIRE_TRUST_DOMAIN    SPIRE trust domain (default: example.org)"
    echo "  SPIRE_CLUSTER_NAME    SPIRE cluster name (default: slim-cluster)"
    echo ""
    echo "Examples:"
    echo "  $0 install"
    echo "  $0 install scheduler-node"
    echo "  SPIRE_ENABLED=true $0 install"
    echo "  $0 list"
}

# Main
case "${1:-}" in
    install)
        install
        ;;
    clean)
        clean
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    port-forward)
        port_forward
        ;;
    list)
        list
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        usage
        exit 1
        ;;
esac
