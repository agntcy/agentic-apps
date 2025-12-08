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
        log_info "Downloading SLIM control plane Helm chart ${CHART_VERSION}..."
        helm pull "${CHART_REPO}" --version "${CHART_VERSION}"
    else
        log_info "Chart file ${CHART_FILE} already exists"
    fi
}

# Register SLIM controller workload with SPIRE
register_with_spire() {
    log_info "Registering SLIM controller workload with SPIRE..."

    # Check if SPIRE server is available in SPIRE namespace
    if ! kubectl get pod -n "${SPIRE_NAMESPACE}" -l app.kubernetes.io/name=server -o name | grep -q "pod/"; then
        log_warn "SPIRE server not found in namespace ${SPIRE_NAMESPACE}, skipping registration"
        return 0
    fi

    local SPIRE_SERVER_POD
    SPIRE_SERVER_POD=$(kubectl get pod -n "${SPIRE_NAMESPACE}" -l app.kubernetes.io/name=server -o jsonpath='{.items[0].metadata.name}')

    log_info "Using SPIRE Server pod: ${SPIRE_SERVER_POD} in namespace ${SPIRE_NAMESPACE}"

    # Register SLIM Controller
    log_info "Registering SLIM Controller..."
    kubectl exec -n "${SPIRE_NAMESPACE}" "${SPIRE_SERVER_POD}" -c spire-server -- \
        /opt/spire/bin/spire-server entry create \
        -spiffeID "spiffe://${SPIRE_TRUST_DOMAIN}/slim/controller" \
        -parentID "spiffe://${SPIRE_TRUST_DOMAIN}/spire/agent/k8s_psat/${SPIRE_CLUSTER_NAME}" \
        -selector "k8s:ns:${NAMESPACE}" \
        -selector "k8s:sa:slim-control" \
        -dns "slim-control" \
        -dns "slim-control.${NAMESPACE}.svc.cluster.local" \
        2>/dev/null || log_warn "Controller entry may already exist"

    log_info "SPIRE registration complete"
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
        log_info "SPIRE mode enabled - configuring mTLS (CSI driver)..."
        HELM_VALUES+=(
            --set spire.enabled=true
            --set spire.useCSIDriver=true
            --set config.southbound.tls.useSpiffe=true
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

    # Register with SPIRE if enabled
    if [[ "${SPIRE_ENABLED}" == "true" ]]; then
        register_with_spire
    fi

    log_info "Waiting for SLIM controller to be ready..."
    kubectl rollout status deployment/slim-control -n "${NAMESPACE}" --timeout=120s || true

    status
}

# Clean all SLIM controller resources
clean() {
    log_warn "Cleaning up all SLIM controller resources in namespace ${NAMESPACE}..."

    # Uninstall helm release
    if helm list -n "${NAMESPACE}" | grep -q "${RELEASE_NAME}"; then
        log_info "Uninstalling Helm release ${RELEASE_NAME}..."
        helm uninstall "${RELEASE_NAME}" -n "${NAMESPACE}" --wait 2>/dev/null || true
    fi

    # Remove helm release secrets
    log_info "Removing Helm release secrets..."
    for secret in $(kubectl get secrets -n "${NAMESPACE}" -o name 2>/dev/null | grep "sh.helm.release.v1.${RELEASE_NAME}"); do
        log_info "Deleting ${secret}..."
        kubectl delete "${secret}" -n "${NAMESPACE}" 2>/dev/null || true
    done

    # Remove all resources
    log_info "Removing SLIM controller resources..."
    kubectl delete deployment slim-control -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete service slim-control -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete configmap slim-control -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete serviceaccount slim-control -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete pvc slim-control-db -n "${NAMESPACE}" 2>/dev/null || true

    log_info "Cleanup complete"
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
    echo "  clean        Remove all SLIM controller resources"
    echo "  status       Show deployment status"
    echo "  logs         Stream SLIM controller logs"
    echo "  port-forward Set up port forwarding for local access"
    echo ""
    echo "Environment variables:"
    echo "  SLIM_NAMESPACE       Target namespace (default: lumuscar-jobs)"
    echo "  SPIRE_ENABLED        Enable SPIRE mTLS (default: false)"
    echo "  SPIRE_TRUST_DOMAIN   SPIRE trust domain (default: example.org)"
    echo "  SPIRE_CLUSTER_NAME   SPIRE cluster name (default: slim-cluster)"
    echo ""
    echo "Examples:"
    echo "  $0 install"
    echo "  SPIRE_ENABLED=true $0 install"
    echo "  $0 port-forward"
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
    -h|--help|help)
        usage
        ;;
    *)
        usage
        exit 1
        ;;
esac
