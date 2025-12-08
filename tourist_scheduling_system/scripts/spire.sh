#!/bin/bash
# SPIRE deployment script for Kubernetes
# Usage: ./spire.sh [install|clean|status|logs|list-entries]

set -e

NAMESPACE="${SPIRE_NAMESPACE:-lumuscar-jobs}"
RELEASE_NAME="spire"
CHART_VERSION="${SPIRE_CHART_VERSION:-0.27.0}"
SPIRE_VERSION="${SPIRE_VERSION:-1.13.0}"
TRUST_DOMAIN="${SPIRE_TRUST_DOMAIN:-example.org}"
CLUSTER_NAME="${SPIRE_CLUSTER_NAME:-slim-cluster}"
CSI_DRIVER_ENABLED="${SPIRE_CSI_DRIVER_ENABLED:-false}"
# MicroK8s uses a different kubelet path
KUBELET_PATH="${SPIRE_KUBELET_PATH:-/var/snap/microk8s/common/var/lib/kubelet}"

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

# Add Helm repo if not exists
add_repo() {
    if ! helm repo list | grep -q "spiffe"; then
        log_info "Adding SPIFFE Helm repository..."
        helm repo add spiffe https://spiffe.github.io/helm-charts-hardened/
    fi
    helm repo update spiffe
}

# Install SPIRE CRDs first
install_crds() {
    log_info "Installing SPIRE CRDs in namespace ${NAMESPACE}..."
    if helm list -n "${NAMESPACE}" | grep -q "spire-crds"; then
        log_warn "SPIRE CRDs already installed, skipping..."
    else
        helm install spire-crds spiffe/spire-crds \
            -n "${NAMESPACE}"
    fi
}

# Install SPIRE
install() {
    log_info "Installing SPIRE in namespace ${NAMESPACE}..."
    log_info "Trust Domain: ${TRUST_DOMAIN}"
    log_info "Cluster Name: ${CLUSTER_NAME}"

    # Add repo
    add_repo

    # Install CRDs first
    install_crds

    # Check if release already exists
    if helm list -n "${NAMESPACE}" | grep -q "^${RELEASE_NAME}\s"; then
        log_warn "Release ${RELEASE_NAME} already exists, upgrading..."
        helm upgrade "${RELEASE_NAME}" spiffe/spire \
            -n "${NAMESPACE}" \
            --version "${CHART_VERSION}" \
            --reuse-values \
            --set global.installAndUpgradeHooks.enabled=false \
            --set global.deleteHooks.enabled=false \
            --set global.spire.trustDomain="${TRUST_DOMAIN}" \
            --set global.spire.clusterName="${CLUSTER_NAME}" \
            --set global.spire.namespaces.create=false \
            --set global.spire.namespaces.system.name="${NAMESPACE}" \
            --set global.spire.namespaces.server.name="${NAMESPACE}" \
            --set global.spire.recommendations.enabled=false \
            --set global.spire.image.tag="${SPIRE_VERSION}" \
            --set spire-server.enabled=true \
            --set spire-server.controllerManager.enabled="${CSI_DRIVER_ENABLED}" \
            --set spire-agent.enabled=true \
            --set spiffe-csi-driver.enabled="${CSI_DRIVER_ENABLED}" \
            --set spiffe-csi-driver.kubeletPath="${KUBELET_PATH}" \
            --set spiffe-oidc-discovery-provider.enabled=false
    else
        log_info "Installing new release in single namespace mode (no cluster-scoped resources)..."
        helm install "${RELEASE_NAME}" spiffe/spire \
            -n "${NAMESPACE}" \
            --version "${CHART_VERSION}" \
            --set global.installAndUpgradeHooks.enabled=false \
            --set global.deleteHooks.enabled=false \
            --set global.spire.trustDomain="${TRUST_DOMAIN}" \
            --set global.spire.clusterName="${CLUSTER_NAME}" \
            --set global.spire.namespaces.create=false \
            --set global.spire.namespaces.system.name="${NAMESPACE}" \
            --set global.spire.namespaces.server.name="${NAMESPACE}" \
            --set global.spire.recommendations.enabled=false \
            --set global.spire.image.tag="${SPIRE_VERSION}" \
            --set spire-server.enabled=true \
            --set spire-server.controllerManager.enabled="${CSI_DRIVER_ENABLED}" \
            --set spire-agent.enabled=true \
            --set spiffe-csi-driver.enabled="${CSI_DRIVER_ENABLED}" \
            --set spiffe-csi-driver.kubeletPath="${KUBELET_PATH}" \
            --set spiffe-oidc-discovery-provider.enabled=false
    fi

    log_info "Waiting for SPIRE Server to be ready..."
    kubectl rollout status statefulset/spire-server -n "${NAMESPACE}" --timeout=180s || true

    log_info "Waiting for SPIRE Agent to be ready..."
    kubectl rollout status daemonset/spire-agent -n "${NAMESPACE}" --timeout=180s || true

    status
}

# Clean all SPIRE resources
clean() {
    log_warn "Cleaning up all SPIRE resources in namespace ${NAMESPACE}..."

    # Uninstall helm releases
    helm uninstall "${RELEASE_NAME}" -n "${NAMESPACE}" 2>/dev/null || true
    helm uninstall spire-crds -n "${NAMESPACE}" 2>/dev/null || true

    # Remove helm secrets
    for secret in $(kubectl get secrets -n "${NAMESPACE}" -o name 2>/dev/null | grep "sh.helm.release.*spire"); do
        kubectl delete "${secret}" -n "${NAMESPACE}" 2>/dev/null || true
    done

    # Delete SPIRE resources in namespace
    log_info "Deleting SPIRE resources..."
    kubectl delete statefulset spire-server -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete daemonset spire-agent spire-spiffe-csi-driver -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete deployment spire-controller-manager -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete service spire-server spire-server-bundle-endpoint spire-controller-manager-webhook -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete configmap spire-server spire-agent spire-bundle -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete serviceaccount spire-server spire-agent spire-controller-manager -n "${NAMESPACE}" 2>/dev/null || true

    # Delete cluster-scoped resources
    log_info "Deleting cluster-scoped SPIRE resources..."
    kubectl delete clusterrole spire-agent spire-server spire-controller-manager 2>/dev/null || true
    kubectl delete clusterrolebinding spire-agent spire-server spire-controller-manager 2>/dev/null || true
    kubectl delete validatingwebhookconfiguration "${NAMESPACE}-spire-controller-manager-webhook" 2>/dev/null || true

    # Delete CRDs
    log_info "Deleting SPIRE CRDs..."
    kubectl delete crd clusterfederatedtrustdomains.spire.spiffe.io 2>/dev/null || true
    kubectl delete crd clusterspiffeids.spire.spiffe.io 2>/dev/null || true
    kubectl delete crd clusterstaticentries.spire.spiffe.io 2>/dev/null || true
    kubectl delete crd controllermanagerconfigs.spire.spiffe.io 2>/dev/null || true

    log_info "Cleanup complete"
}

# Show status
status() {
    log_info "SPIRE Status in namespace ${NAMESPACE}:"
    echo ""

    echo "=== Helm Releases ==="
    helm list -n "${NAMESPACE}" | grep -E "spire|NAME" || echo "No releases found in ${NAMESPACE}"
    echo ""

    echo "=== SPIRE Server ==="
    kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=server 2>/dev/null || echo "No server pods found"
    echo ""

    echo "=== SPIRE Agent ==="
    kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=agent 2>/dev/null || echo "No agent pods found"
    echo ""

    echo "=== Trust Domain ==="
    log_info "Trust Domain: ${TRUST_DOMAIN}"
}

# Show logs
logs() {
    local component="${2:-server}"

    case "${component}" in
        server)
            log_info "Fetching SPIRE Server logs..."
            kubectl logs -n "${NAMESPACE}" -l app.kubernetes.io/name=server --tail=100 -f
            ;;
        agent)
            log_info "Fetching SPIRE Agent logs..."
            kubectl logs -n "${NAMESPACE}" -l app.kubernetes.io/name=agent --tail=100 -f
            ;;
        *)
            log_error "Unknown component: ${component}. Use 'server' or 'agent'"
            exit 1
            ;;
    esac
}

# List SPIRE entries
list_entries() {
    log_info "Listing SPIRE entries..."

    SPIRE_SERVER_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -z "$SPIRE_SERVER_POD" ]; then
        log_error "SPIRE Server pod not found. Is SPIRE installed?"
        exit 1
    fi

    kubectl exec -n "${NAMESPACE}" "${SPIRE_SERVER_POD}" -- \
        /opt/spire/bin/spire-server entry show
}

# Show help
usage() {
    echo "SPIRE Deployment Script"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  install         Install SPIRE (Server + Agent + CSI driver)"
    echo "  clean           Remove all SPIRE resources"
    echo "  status          Show deployment status"
    echo "  logs [component]  Stream logs (server|agent, default: server)"
    echo "  list-entries    List all SPIRE workload entries"
    echo ""
    echo "Environment variables:"
    echo "  SPIRE_NAMESPACE           Target namespace (default: lumuscar-jobs)"
    echo "  SPIRE_TRUST_DOMAIN        Trust domain (default: example.org)"
    echo "  SPIRE_CLUSTER_NAME        Cluster name (default: slim-cluster)"
    echo "  SPIRE_CHART_VERSION       Helm chart version (default: 0.27.0)"
    echo "  SPIRE_VERSION             SPIRE version (default: 1.13.0)"
    echo "  SPIRE_CSI_DRIVER_ENABLED  Enable SPIFFE CSI driver (default: false)"
    echo ""
    echo "Examples:"
    echo "  $0 install"
    echo "  SPIRE_CSI_DRIVER_ENABLED=true $0 install"
    echo "  $0 logs agent"
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
        logs "$@"
        ;;
    list-entries)
        list_entries
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        usage
        exit 1
        ;;
esac
