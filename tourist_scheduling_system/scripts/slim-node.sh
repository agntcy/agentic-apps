#!/bin/bash
# SLIM Node (Data Plane) deployment script for Kubernetes
# Usage: ./slim-node.sh [install|uninstall|status|clean|logs] [node-name]
# Strategy: SLIM_STRATEGY=daemonset ./slim-node.sh install (default: statefulset)
# SPIRE mode: SPIRE_ENABLED=true ./slim-node.sh install

set -e

NAMESPACE="${SLIM_NAMESPACE:-lumuscar-jobs}"
NODE_NAME="${2:-slim-node}"
RELEASE_NAME="slim-${NODE_NAME}"
CHART_VERSION="v0.7.0"
CHART_REPO="oci://ghcr.io/agntcy/slim/helm/slim"
CHART_FILE="slim-${CHART_VERSION}.tgz"

# Deployment Strategy
SLIM_STRATEGY="${SLIM_STRATEGY:-statefulset}"

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
    log_info "Applying ClusterSPIFFEID for SLIM Node '${NODE_NAME}'..."

    local TEMPLATE_FILE="slim-node-csid.yaml.tpl"
    if [ ! -f "$TEMPLATE_FILE" ]; then
        log_error "Template file $TEMPLATE_FILE not found"
        return 1
    fi

    # Export variables for envsubst
    export NODE_NAME
    export NAMESPACE
    export SPIRE_TRUST_DOMAIN

    if command -v envsubst >/dev/null 2>&1; then
        envsubst < "$TEMPLATE_FILE" | kubectl apply -f -
    else
        # Fallback to sed if envsubst is not available
        sed -e "s/\${NODE_NAME}/${NODE_NAME}/g" \
            -e "s/\${NAMESPACE}/${NAMESPACE}/g" \
            -e "s/\${SPIRE_TRUST_DOMAIN}/${SPIRE_TRUST_DOMAIN}/g" \
            "$TEMPLATE_FILE" | kubectl apply -f -
    fi

    log_info "ClusterSPIFFEID applied"
}

# Install SLIM node
install() {
    log_info "Installing SLIM node '${NODE_NAME}' in namespace ${NAMESPACE} using strategy: ${SLIM_STRATEGY}..."
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

    # Select values file based on strategy
    local SCRIPT_DIR
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local VALUES_TEMPLATE

    if [[ "${SLIM_STRATEGY}" == "daemonset" ]]; then
        VALUES_TEMPLATE="${SCRIPT_DIR}/daemonset-values.yaml"
    else
        VALUES_TEMPLATE="${SCRIPT_DIR}/statefulset-values.yaml"
    fi

    # Prepare values file with env substitution
    export SLIM_SVC_ID="${NODE_NAME}"

    if command -v envsubst >/dev/null 2>&1; then
        envsubst < "${VALUES_TEMPLATE}" > "${SCRIPT_DIR}/values-processed.yaml"
    else
        sed "s/\${SLIM_SVC_ID}/${SLIM_SVC_ID}/g" "${VALUES_TEMPLATE}" > "${SCRIPT_DIR}/values-processed.yaml"
    fi

    # Build base Helm values
    HELM_VALUES=(
        -f "${SCRIPT_DIR}/values-processed.yaml"
        --set fullnameOverride="${NODE_NAME}"
        --set slim.config.services.slim/0.controller.clients[0].endpoint="${ENDPOINT_PROTOCOL}://${CONTROLLER_HOST}:${CONTROLLER_PORT}"
    )

    # Add SPIRE values if enabled
    if [[ "${SPIRE_ENABLED}" == "true" ]]; then
        HELM_VALUES+=(
            --set slim.config.services.slim/0.controller.clients[0].tls.insecure=false
            --set slim.config.services.slim/0.controller.clients[0].tls.source.type=spire
            --set slim.config.services.slim/0.controller.clients[0].tls.source.socket_path="unix:/tmp/spire-agent/public/spire-agent.sock"
            --set slim.config.services.slim/0.controller.clients[0].tls.ca_source.type=spire
            --set slim.config.services.slim/0.controller.clients[0].tls.ca_source.socket_path="unix:/tmp/spire-agent/public/spire-agent.sock"
            --set slim.config.services.slim/0.controller.clients[0].tls.ca_source.trust_domains[0]="${SPIRE_TRUST_DOMAIN}"
            --set slim.config.services.slim/0.controller.clients[0].tls.insecure_skip_verify=true
            --set spire.enabled=true
            --set spire.useCSIDriver=true
            --set spire.socketPath="/run/spire/agent-sockets/spire-agent.sock"
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

    rm "${SCRIPT_DIR}/values-processed.yaml"

    # Register with SPIRE if enabled
    if [[ "${SPIRE_ENABLED}" == "true" ]]; then
        register_with_spire
    fi

    log_info "Waiting for SLIM node to be ready..."
    if [[ "${SLIM_STRATEGY}" == "daemonset" ]]; then
        kubectl rollout status daemonset/"${RELEASE_NAME}-${NODE_NAME}" -n "${NAMESPACE}" --timeout=120s || kubectl rollout status daemonset/"${NODE_NAME}" -n "${NAMESPACE}" --timeout=120s || true
    else
        kubectl rollout status statefulset/"${RELEASE_NAME}-${NODE_NAME}" -n "${NAMESPACE}" --timeout=120s || kubectl rollout status statefulset/"${NODE_NAME}" -n "${NAMESPACE}" --timeout=120s || true
    fi

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
    kubectl delete daemonset "${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete service "${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete configmap "${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete serviceaccount "${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true

    # Pattern 2: slim-NODE_NAME (helm release naming)
    kubectl delete statefulset "slim-${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete daemonset "slim-${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete service "slim-${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete configmap "slim-${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete serviceaccount "slim-${NODE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true

    # Pattern 3: default 'slim' (chart default name)
    kubectl delete statefulset "slim" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete daemonset "slim" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete service "slim" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete configmap "slim" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete serviceaccount "slim" -n "${NAMESPACE}" 2>/dev/null || true

    kubectl delete clusterspiffeid "slim-node-${NODE_NAME}" 2>/dev/null || true

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
    kubectl get svc -n "${NAMESPACE}" -l "app.kubernetes.io/instance=${RELEASE_NAME}" 2>/dev/null || echo "No services found"
    echo ""
}

# Show logs
logs() {
    log_info "Fetching logs for SLIM node '${NODE_NAME}'..."
    kubectl logs -n "${NAMESPACE}" -l "app.kubernetes.io/instance=${RELEASE_NAME}" --tail=100 -f
}

# Main execution
case "$1" in
    install)
        install
        ;;
    uninstall)
        log_info "Uninstalling SLIM node '${NODE_NAME}'..."
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
        echo "Usage: $0 {install|uninstall|status|clean|logs} [node-name]"
        exit 1
        ;;
esac
