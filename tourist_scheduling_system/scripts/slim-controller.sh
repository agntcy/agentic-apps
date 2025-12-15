#!/bin/bash
# SLIM Controller deployment script for Kubernetes
# Usage: ./slim-controller.sh [install|uninstall|status|clean|logs]
# Strategy: SLIM_STRATEGY=daemonset ./slim-controller.sh install (default: statefulset)
# SPIRE mode: SPIRE_ENABLED=true ./slim-controller.sh install

set -e

NAMESPACE="${SLIM_NAMESPACE:-lumuscar-jobs}"
RELEASE_NAME="slim-controller"
CHART_VERSION="v0.7.0"
CHART_REPO="oci://ghcr.io/agntcy/slim/helm/slim-control-plane"
CHART_FILE="slim-control-plane-${CHART_VERSION}.tgz"

# Deployment Strategy
SLIM_STRATEGY="${SLIM_STRATEGY:-statefulset}"

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
    log_info "Applying ClusterSPIFFEID for SLIM Controller..."

    local TEMPLATE_FILE="slim-control-csid.yaml.tpl"
    if [ ! -f "$TEMPLATE_FILE" ]; then
        log_error "Template file $TEMPLATE_FILE not found"
        return 1
    fi

    # Export variables for envsubst
    export NAMESPACE
    export SPIRE_TRUST_DOMAIN

    if command -v envsubst >/dev/null 2>&1; then
        envsubst < "$TEMPLATE_FILE" | kubectl apply -f -
    else
        # Fallback to sed if envsubst is not available
        sed -e "s/\${NAMESPACE}/${NAMESPACE}/g" \
            -e "s/\${SPIRE_TRUST_DOMAIN}/${SPIRE_TRUST_DOMAIN}/g" \
            "$TEMPLATE_FILE" | kubectl apply -f -
    fi

    log_info "ClusterSPIFFEID applied"
}

# Install SLIM controller
install() {
    log_info "Installing SLIM controller in namespace ${NAMESPACE} using strategy: ${SLIM_STRATEGY}..."

    # Download chart if needed
    download_chart

    local SCRIPT_DIR
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Base values
    HELM_VALUES=(
        -f "${SCRIPT_DIR}/controller-values.yaml"
    )

    # Add SPIRE values if enabled
    if [[ "${SPIRE_ENABLED}" == "true" ]]; then
        log_info "SPIRE mode enabled - configuring mTLS (CSI driver)..."
        HELM_VALUES+=(
            --set spire.enabled=true
            --set spire.useCSIDriver=true
            --set spire.socketPath="/run/spire/agent-sockets/spire-agent.sock"
            --set config.southbound.tls.useSpiffe=true
            --set config.southbound.spire.socketPath="unix:///run/spire/agent-sockets/spire-agent.sock"
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
    log_info "Removing controller resources..."
    kubectl delete deployment slim-control -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete service slim-control -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete configmap slim-control -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete serviceaccount slim-control -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete clusterspiffeid slim-control 2>/dev/null || true

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
    kubectl get pods -n "${NAMESPACE}" -l "app.kubernetes.io/instance=${RELEASE_NAME}" 2>/dev/null || echo "No pods found"
    echo ""

    echo "=== Services ==="
    kubectl get svc -n "${NAMESPACE}" -l "app.kubernetes.io/instance=${RELEASE_NAME}" 2>/dev/null || echo "No services found"
    echo ""
}

# Show logs
logs() {
    log_info "Fetching logs for SLIM controller..."
    kubectl logs -n "${NAMESPACE}" -l app.kubernetes.io/name=slim-control --tail=100 -f
}

# Main execution
case "$1" in
    install)
        install
        ;;
    uninstall)
        log_info "Uninstalling SLIM controller..."
        helm uninstall "${RELEASE_NAME}" -n "${NAMESPACE}"
        ;;
    status)
        status
        ;;
    clean)
        clean
        ;;
    logs)
        logs
        ;;
    *)
        echo "Usage: $0 {install|uninstall|status|clean|logs}"
        exit 1
        ;;
esac
