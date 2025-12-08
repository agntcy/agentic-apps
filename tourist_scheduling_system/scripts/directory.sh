#!/bin/bash
# Agent Directory deployment script for Kubernetes
# Usage: ./directory.sh [install|uninstall|status|clean|logs]
#
# NOTE: When using SPIRE authentication, Directory MUST be installed in a
# different namespace than SPIRE. SPIRE's fallback ClusterSPIFFEID excludes
# the SPIRE namespace, so workloads there won't get SPIFFE identities.

set -e

NAMESPACE="${DIR_NAMESPACE:-lumuscar-jobs}"
RELEASE_NAME="${DIR_RELEASE_NAME:-dir}"
CHART_VERSION="v0.5.6"
CHART_REPO="oci://ghcr.io/agntcy/dir/helm-charts/dir"
CHART_FILE="dir-${CHART_VERSION}.tgz"

# Service configuration
SERVICE_TYPE="${DIR_SERVICE_TYPE:-ClusterIP}"
METRICS_ENABLED="${DIR_METRICS_ENABLED:-true}"

# Database configuration
DB_PERSISTENCE="${DIR_DB_PERSISTENCE:-false}"
DB_STORAGE_SIZE="${DIR_DB_STORAGE_SIZE:-1Gi}"

# SPIRE/Authentication configuration
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
        log_info "Downloading Agent Directory Helm chart ${CHART_VERSION}..."
        helm pull "${CHART_REPO}" --version "${CHART_VERSION}"
    else
        log_info "Chart file ${CHART_FILE} already exists"
    fi
}

# Register directory workload with SPIRE
register_with_spire() {
    log_info "Registering directory workload with SPIRE..."

    # Check if SPIRE server is available in SPIRE namespace
    if ! kubectl get pod -n "${SPIRE_NAMESPACE}" -l app.kubernetes.io/name=server -o name | grep -q "pod/"; then
        log_warn "SPIRE server not found in namespace ${SPIRE_NAMESPACE}, skipping registration"
        return 0
    fi

    local SPIRE_SERVER_POD
    SPIRE_SERVER_POD=$(kubectl get pod -n "${SPIRE_NAMESPACE}" -l app.kubernetes.io/name=server -o jsonpath='{.items[0].metadata.name}')

    log_info "Using SPIRE Server pod: ${SPIRE_SERVER_POD} in namespace ${SPIRE_NAMESPACE}"

    # Register Directory apiserver
    log_info "Registering Directory apiserver..."
    kubectl exec -n "${SPIRE_NAMESPACE}" "${SPIRE_SERVER_POD}" -c spire-server -- \
        /opt/spire/bin/spire-server entry create \
        -spiffeID "spiffe://${SPIRE_TRUST_DOMAIN}/dir/apiserver" \
        -parentID "spiffe://${SPIRE_TRUST_DOMAIN}/spire/agent/k8s_psat/${SPIRE_CLUSTER_NAME}" \
        -selector "k8s:ns:${NAMESPACE}" \
        -selector "k8s:sa:default" \
        -dns "${RELEASE_NAME}-apiserver" \
        -dns "${RELEASE_NAME}-apiserver.${NAMESPACE}.svc.cluster.local" \
        2>/dev/null || log_warn "Directory entry may already exist"

    log_info "SPIRE registration complete"
}

# Install Agent Directory
install() {
    log_info "Installing Agent Directory in namespace ${NAMESPACE}..."

    # Download chart if needed
    download_chart

    # Build base Helm values
    HELM_VALUES=(
        --set apiserver.service.type="${SERVICE_TYPE}"
        --set apiserver.metrics.enabled="${METRICS_ENABLED}"
        --set apiserver.config.store.oci.registry_address="${RELEASE_NAME}-zot.${NAMESPACE}.svc.cluster.local:5000"
    )

    # Database persistence
    if [[ "${DB_PERSISTENCE}" == "true" ]]; then
        log_info "Database persistence enabled (${DB_STORAGE_SIZE})"
        HELM_VALUES+=(
            --set apiserver.database.pvc.enabled=true
            --set apiserver.database.pvc.size="${DB_STORAGE_SIZE}"
            --set apiserver.database.sqlite.dbPath="/var/lib/dir/database/dir.db"
            --set apiserver.strategy.type=Recreate
        )
    fi

    # Authentication configuration (requires SPIRE)
    if [[ "${SPIRE_ENABLED}" == "true" ]]; then
        log_info "SPIRE authentication enabled (CSI driver mode)"
        # Note: socket_path override required - Helm chart default is wrong for CSI driver
        HELM_VALUES+=(
            --set apiserver.spire.enabled=true
            --set apiserver.spire.trustDomain="${SPIRE_TRUST_DOMAIN}"
            --set apiserver.spire.useCSIDriver=true
            --set apiserver.config.authn.enabled=true
            --set apiserver.config.authn.mode="x509"
            --set apiserver.config.authn.socket_path="unix:///run/spire/agent-sockets/spire-agent.sock"
        )
    else
        log_info "Authentication disabled"
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

    # Register with SPIRE if authentication is enabled
    if [[ "${SPIRE_ENABLED}" == "true" ]]; then
        register_with_spire
    fi

    log_info "Waiting for Agent Directory to be ready..."
    kubectl rollout status deployment/${RELEASE_NAME}-apiserver -n "${NAMESPACE}" --timeout=120s || true

    status
}

# Clean all directory resources
clean() {
    log_warn "Cleaning up all Agent Directory resources in namespace ${NAMESPACE}..."

    # First try helm uninstall
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

    # Remove all resources by label
    log_info "Removing resources by label..."
    kubectl delete deployment,service,configmap,secret,pvc,serviceaccount -n "${NAMESPACE}" \
        -l "app.kubernetes.io/instance=${RELEASE_NAME}" 2>/dev/null || true

    # Remove specific resources by name pattern
    log_info "Removing resources by name..."
    kubectl delete deployment "${RELEASE_NAME}-apiserver" "${RELEASE_NAME}-zot" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete service "${RELEASE_NAME}-apiserver" "${RELEASE_NAME}-apiserver-routing" "${RELEASE_NAME}-zot" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete configmap "${RELEASE_NAME}-apiserver" "${RELEASE_NAME}-zot" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete secret "${RELEASE_NAME}-apiserver" "${RELEASE_NAME}-zot" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete serviceaccount "${RELEASE_NAME}-apiserver" "${RELEASE_NAME}-zot" -n "${NAMESPACE}" 2>/dev/null || true

    # Clean up extra secrets from previous installations
    kubectl delete secret "${RELEASE_NAME}-secret" "agent-directory-secret" -n "${NAMESPACE}" 2>/dev/null || true

    # Delete PVCs
    log_info "Removing PVCs..."
    kubectl delete pvc "${RELEASE_NAME}-zot-config" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete pvc "${RELEASE_NAME}-apiserver-db" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete pvc "${RELEASE_NAME}-apiserver-routing" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete pvc -l "app.kubernetes.io/instance=${RELEASE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true

    log_info "Cleanup complete"
}

# Show status
status() {
    log_info "Agent Directory Status in namespace ${NAMESPACE}:"
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

    echo "=== PVC ==="
    kubectl get pvc -n "${NAMESPACE}" -l "app.kubernetes.io/instance=${RELEASE_NAME}" 2>/dev/null || echo "No PVC found"
}

# Show logs
logs() {
    log_info "Fetching Agent Directory logs..."
    kubectl logs -n "${NAMESPACE}" -l "app.kubernetes.io/instance=${RELEASE_NAME}" --tail=100 -f
}

# Port forward for local access
port_forward() {
    log_info "Setting up port forwarding..."
    log_info "API Server: localhost:8888"
    log_info "Metrics: localhost:9090"

    POD_NAME=$(kubectl get pods -n "${NAMESPACE}" -l "app.kubernetes.io/instance=${RELEASE_NAME}" -o jsonpath="{.items[0].metadata.name}")

    if [ -z "$POD_NAME" ]; then
        log_error "No Agent Directory pod found"
        exit 1
    fi

    kubectl port-forward -n "${NAMESPACE}" "${POD_NAME}" 8888:8888 9090:9090
}

# Show help
usage() {
    echo "Agent Directory Deployment Script"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  install      Install or upgrade Agent Directory"
    echo "  clean        Remove all Agent Directory resources"
    echo "  status       Show deployment status"
    echo "  logs         Stream Agent Directory logs"
    echo "  port-forward Set up port forwarding for local access"
    echo ""
    echo "Environment variables:"
    echo "  DIR_NAMESPACE        Target namespace (default: lumuscar-jobs)"
    echo "  DIR_SERVICE_TYPE     Service type: ClusterIP, NodePort, LoadBalancer (default: ClusterIP)"
    echo "  DIR_METRICS_ENABLED  Enable Prometheus metrics (default: true)"
    echo "  DIR_DB_PERSISTENCE   Enable database persistence (default: false)"
    echo "  DIR_DB_STORAGE_SIZE  PVC size for database (default: 1Gi)"
    echo "  SPIRE_ENABLED        Enable SPIRE authentication (default: false)"
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
