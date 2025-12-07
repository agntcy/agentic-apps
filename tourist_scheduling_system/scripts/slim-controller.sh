#!/bin/bash
# SLIM Controller deployment script for Kubernetes
# Usage: ./slim-controller.sh [install|uninstall|status|clean|logs]
# SPIRE mode: SPIRE_ENABLED=true ./slim-controller.sh install

set -e

NAMESPACE="${SLIM_NAMESPACE:-lumuscar-jobs}"
RELEASE_NAME="slim-controller"
CHART_VERSION="v0.7.0"
CHART_REPO="oci://ghcr.io/agntcy/slim/helm/slim-control-plane"
CHART_FILE="slim-control-plane-${CHART_VERSION}.tgz"

# SPIRE Configuration
SPIRE_ENABLED="${SPIRE_ENABLED:-false}"
SPIRE_SOCKET_PATH="${SPIRE_SOCKET_PATH:-unix:///run/spire/agent-sockets/spire-agent.sock}"
SPIRE_TRUST_DOMAIN="${SPIRE_TRUST_DOMAIN:-example.org}"

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
        log_info "Downloading SLIM control plane Helm chart ${CHART_VERSION}..."
        helm pull "${CHART_REPO}" --version "${CHART_VERSION}"
    else
        log_info "Chart file ${CHART_FILE} already exists"
    fi
}

# Install SLIM controller
install() {
    log_info "Installing SLIM controller in namespace ${NAMESPACE}..."

    # Download chart if needed
    download_chart

    # Build base Helm values
    HELM_VALUES=(
        --set config.database.filePath="/db/controlplane.db"
        --set securityContext.runAsUser=0
        --set securityContext.runAsGroup=0
    )

    # Add SPIRE values if enabled
    if [[ "${SPIRE_ENABLED}" == "true" ]]; then
        log_info "SPIRE mode enabled - configuring mTLS (hostPath mode)..."
        HELM_VALUES+=(
            --set spire.enabled=true
            --set spire.agentSocketPath="${SPIRE_SOCKET_PATH}"
            --set config.southbound.tls.useSpiffe=true
            --set config.southbound.spire.socketPath="${SPIRE_SOCKET_PATH}"
        )
    else
        log_info "SPIRE mode disabled - using insecure mode"
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

    log_info "Waiting for SLIM controller to be ready..."
    kubectl rollout status deployment/slim-control -n "${NAMESPACE}" --timeout=120s || true

    status
}

# Uninstall SLIM controller
uninstall() {
    log_info "Uninstalling SLIM controller from namespace ${NAMESPACE}..."

    if helm list -n "${NAMESPACE}" | grep -q "${RELEASE_NAME}"; then
        helm uninstall "${RELEASE_NAME}" -n "${NAMESPACE}" || true
    else
        log_warn "Release ${RELEASE_NAME} not found"
    fi

    log_info "SLIM controller uninstalled"
}

# Clean up stuck releases and resources
clean() {
    log_warn "Cleaning up SLIM controller resources in namespace ${NAMESPACE}..."

    # Remove helm release secrets (for stuck releases)
    log_info "Removing Helm release secrets..."
    kubectl delete secret -n "${NAMESPACE}" -l "name=${RELEASE_NAME},owner=helm" 2>/dev/null || true

    # Also try the specific secret pattern
    for secret in $(kubectl get secrets -n "${NAMESPACE}" -o name 2>/dev/null | grep "sh.helm.release.v1.${RELEASE_NAME}"); do
        log_info "Deleting ${secret}..."
        kubectl delete "${secret}" -n "${NAMESPACE}" 2>/dev/null || true
    done

    # Remove slim-control resources directly
    log_info "Removing SLIM controller resources..."
    kubectl delete deployment slim-control -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete service slim-control -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete configmap slim-control -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete serviceaccount slim-control -n "${NAMESPACE}" 2>/dev/null || true

    # Optionally remove PVC (data will be lost)
    read -p "Delete PersistentVolumeClaim slim-control-db? This will delete all data! (y/N): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        kubectl delete pvc slim-control-db -n "${NAMESPACE}" 2>/dev/null || true
        log_info "PVC deleted"
    else
        log_info "PVC preserved"
    fi

    log_info "Cleanup complete"
}

# Force clean without prompts (for CI/CD)
force_clean() {
    log_warn "Force cleaning up all SLIM controller resources in namespace ${NAMESPACE}..."

    # Remove helm release secrets
    for secret in $(kubectl get secrets -n "${NAMESPACE}" -o name 2>/dev/null | grep "sh.helm.release.v1.${RELEASE_NAME}"); do
        kubectl delete "${secret}" -n "${NAMESPACE}" 2>/dev/null || true
    done

    # Remove all resources
    kubectl delete deployment slim-control -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete service slim-control -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete configmap slim-control -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete serviceaccount slim-control -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete pvc slim-control-db -n "${NAMESPACE}" 2>/dev/null || true

    log_info "Force cleanup complete"
}

# Show status
status() {
    log_info "SLIM Controller Status in namespace ${NAMESPACE}:"
    echo ""

    echo "=== Helm Release ==="
    helm list -n "${NAMESPACE}" | grep "${RELEASE_NAME}" || echo "No release found"
    echo ""

    echo "=== Pods ==="
    kubectl get pods -n "${NAMESPACE}" -l "app.kubernetes.io/name=slim-control-plane" 2>/dev/null || echo "No pods found"
    echo ""

    echo "=== Services ==="
    kubectl get svc -n "${NAMESPACE}" -l "app.kubernetes.io/name=slim-control-plane" 2>/dev/null || echo "No services found"
    echo ""

    echo "=== PVC ==="
    kubectl get pvc -n "${NAMESPACE}" slim-control-db 2>/dev/null || echo "No PVC found"
}

# Show logs
logs() {
    log_info "Fetching SLIM controller logs..."
    kubectl logs -n "${NAMESPACE}" -l "app.kubernetes.io/name=slim-control-plane" --tail=100 -f
}

# Port forward for local access
port_forward() {
    log_info "Setting up port forwarding..."
    log_info "North API (gRPC): localhost:50051"
    log_info "South API (gRPC): localhost:50052"

    POD_NAME=$(kubectl get pods -n "${NAMESPACE}" -l "app.kubernetes.io/name=slim-control-plane" -o jsonpath="{.items[0].metadata.name}")

    if [ -z "$POD_NAME" ]; then
        log_error "No SLIM controller pod found"
        exit 1
    fi

    kubectl port-forward -n "${NAMESPACE}" "${POD_NAME}" 50051:50051 50052:50052
}

# Show help
usage() {
    echo "SLIM Controller Deployment Script"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  install      Install or upgrade SLIM controller"
    echo "  uninstall    Uninstall SLIM controller (keeps PVC)"
    echo "  clean        Clean up all resources (interactive)"
    echo "  force-clean  Force clean all resources (non-interactive)"
    echo "  status       Show deployment status"
    echo "  logs         Stream SLIM controller logs"
    echo "  port-forward Set up port forwarding for local access"
    echo ""
    echo "Environment variables:"
    echo "  SLIM_NAMESPACE       Target namespace (default: lumuscar-jobs)"
    echo "  SPIRE_ENABLED        Enable SPIRE mTLS (default: false)"
    echo "  SPIRE_SOCKET_PATH    SPIRE agent socket (default: unix:///run/spire/agent-sockets/spire-agent.sock)"
    echo "  SPIRE_TRUST_DOMAIN   SPIRE trust domain (default: example.org)"
    echo ""
    echo "Examples:"
    echo "  $0 install                          # Install without SPIRE"
    echo "  SPIRE_ENABLED=true $0 install       # Install with SPIRE mTLS"
    echo "  SLIM_NAMESPACE=my-namespace $0 install"
    echo "  $0 clean"
}

# Main
case "${1:-}" in
    install)
        install
        ;;
    uninstall)
        uninstall
        ;;
    clean)
        clean
        ;;
    force-clean)
        force_clean
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
    -h|--help|help)
        usage
        ;;
    *)
        usage
        exit 1
        ;;
esac
