# SLIM (Secure Lightweight Inter-agent Messaging) Deployment Guide

This document describes how to deploy and configure SLIM infrastructure for the Tourist Scheduling System.

## Architecture Overview

SLIM provides a secure messaging layer for agent-to-agent (A2A) communication. The architecture consists of:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SLIM Controller                              │
│                       (slim-control)                                │
│                                                                     │
│   ┌────────────────────┐       ┌────────────────────┐              │
│   │  North API :50051  │       │  South API :50052  │◄──────────┐  │
│   │   (Admin/Config)   │       │  (Node Connect)    │           │  │
│   └────────────────────┘       └────────────────────┘           │  │
│                                                                  │  │
└──────────────────────────────────────────────────────────────────┼──┘
                                                                   │
                              gRPC Connection                      │
                                                                   │
┌──────────────────────────────────────────────────────────────────┼──┐
│                          SLIM Node                               │  │
│                      (slim-slim-node)                            │  │
│                                                                  │  │
│   ┌────────────────────┐       ┌────────────────────┐           │  │
│   │  Data Port :46357  │       │ Control Port:46358 │───────────┘  │
│   │    (Agent A2A)     │       │ (Controller conn)  │              │
│   └─────────▲──────────┘       └────────────────────┘              │
│             │                                                       │
└─────────────┼───────────────────────────────────────────────────────┘
              │
              │  Agent connects here
              │
    ┌─────────┴─────────┐
    │   Agent (ADK)     │
    │  scheduler, ui,   │
    │  guide, tourist   │
    └───────────────────┘
```

## Components

### SLIM Controller

The **Controller** is the central management component that:
- Manages node registration and discovery
- Coordinates message routing between nodes
- Stores configuration in a SQLite database
- Provides admin APIs for configuration

**Ports:**
| Port  | API       | Purpose                          |
|-------|-----------|----------------------------------|
| 50051 | North API | Admin and configuration endpoint |
| 50052 | South API | Node connection endpoint         |

### SLIM Node (Data Plane)

The **Node** is the data plane component that:
- Handles actual message routing between agents
- Connects to the controller for coordination
- Provides endpoints for agent connections

**Ports:**
| Port  | Purpose                              |
|-------|--------------------------------------|
| 46357 | Data port - agents connect here      |
| 46358 | Control port - controller connection |

## Deployment

### Prerequisites

- Kubernetes cluster with Helm 3.x
- Namespace with appropriate RBAC permissions
- Access to `ghcr.io/agntcy/slim` container registry

### Scripts

Two deployment scripts are provided in `scripts/`:

#### SLIM Controller (`scripts/slim-controller.sh`)

```bash
# Install SLIM Controller
./scripts/slim-controller.sh install

# Check status
./scripts/slim-controller.sh status

# View logs
./scripts/slim-controller.sh logs

# Uninstall
./scripts/slim-controller.sh uninstall

# Force clean (removes all resources including PVC)
./scripts/slim-controller.sh force-clean
```

#### SLIM Node (`scripts/slim-node.sh`)

```bash
# Install a SLIM node (StatefulSet by default)
./scripts/slim-node.sh install

# Install as DaemonSet
SLIM_STRATEGY=daemonset ./scripts/slim-node.sh install

# Check status
./scripts/slim-node.sh status

# View logs
./scripts/slim-node.sh logs

# Uninstall
./scripts/slim-node.sh uninstall

# Clean
./scripts/slim-node.sh clean
```

### Environment Variables

| Variable               | Default                                           | Description                    |
|------------------------|---------------------------------------------------|--------------------------------|
| `SLIM_NAMESPACE`       | `lumuscar-jobs`                                   | Target Kubernetes namespace    |
| `SLIM_STRATEGY`        | `statefulset`                                     | Deployment strategy (statefulset/daemonset) |
| `SLIM_CONTROLLER_HOST` | `slim-control`                                    | Controller service hostname    |
| `SLIM_CONTROLLER_PORT` | `50052`                                           | Controller south API port      |
| `SPIRE_ENABLED`        | `false`                                           | Enable SPIRE mTLS mode         |
| `SPIRE_SOCKET_PATH`    | `unix:///run/spire/agent-sockets/spire-agent.sock`| SPIRE agent socket path        |
| `SPIRE_TRUST_DOMAIN`   | `example.org`                                     | SPIRE trust domain             |

### SPIRE-Enabled Deployment

To deploy SLIM with SPIRE mTLS:

```bash
# 1. Install SPIRE first
./scripts/spire.sh install

# 2. Install SLIM Controller with SPIRE
# This automatically applies the ClusterSPIFFEID
SPIRE_ENABLED=true ./scripts/slim-controller.sh install

# 3. Install SLIM Node with SPIRE
# This automatically applies the ClusterSPIFFEID
SPIRE_ENABLED=true ./scripts/slim-node.sh install
```

### Helm Charts

The scripts use official AGNTCY Helm charts:

| Chart                  | Version | Purpose           |
|------------------------|---------|-------------------|
| `slim-control-plane`   | v0.7.0  | SLIM Controller   |
| `slim`                 | v0.7.0  | SLIM Node         |

Charts are pulled from: `oci://ghcr.io/agntcy/slim/helm/`

## Configuration

### Node Configuration

The SLIM node ConfigMap contains the following key settings:

```yaml
services:
  slim/0:
    # Unique node identifier (defaults to pod name)
    node_id: ${env:SLIM_SVC_ID}

    controller:
      # Connect TO the controller
      clients:
        - endpoint: http://slim-control:50052
          tls:
            insecure: true
      # Listen FOR controller commands
      servers:
        - endpoint: 0.0.0.0:46358
          tls:
            insecure: true

    dataplane:
      # Listen for agent connections
      servers:
        - endpoint: 0.0.0.0:46357
          tls:
            insecure: true
```

### Controller Configuration

The controller stores its state in a SQLite database at `/db/controlplane.db`.

Key settings:
```yaml
database:
  filePath: /db/controlplane.db

northbound:
  httpHost: 0.0.0.0
  httpPort: '50051'

southbound:
  httpHost: 0.0.0.0
  httpPort: '50052'
```

## Connection Flow

1. **Controller Startup**: Controller starts and listens on ports 50051 (north) and 50052 (south)

2. **Node Registration**: SLIM nodes connect to controller's south API (50052) as clients

3. **Agent Connection**: Agents connect to SLIM node's data port (46357)

4. **Message Routing**:
   - Agent sends message to local SLIM node
   - Node routes message through the SLIM network
   - Controller coordinates routing between nodes
   - Destination node delivers message to target agent

## Verifying the Deployment

### Check Controller Status

```bash
kubectl get pods -n lumuscar-jobs -l app.kubernetes.io/name=slim-control-plane
kubectl logs -n lumuscar-jobs -l app.kubernetes.io/name=slim-control-plane
```

### Check Node Status

```bash
kubectl get pods -n lumuscar-jobs -l app.kubernetes.io/name=slim
kubectl logs -n lumuscar-jobs slim-slim-node-0
```

### Verify Node-Controller Connection

Look for these log messages in the SLIM node:

```
connecting to control plane config.endpoint=http://slim-control:50052
Connection attempt: #1 successful
connected to control plane endpoint=http://slim-control:50052
```

## Agent Integration

To connect an agent to SLIM, configure the agent's A2A transport to use the SLIM node endpoint:

```python
# Example: Connecting an ADK agent to SLIM
slim_endpoint = "http://slim-slim-node:46357"
```

The agent will use SLIM for all inter-agent communication, enabling:
- Secure message routing
- Multi-cluster communication
- Load balancing across nodes

## Troubleshooting

### Controller Database Error

If the controller fails with "unable to open database file":
1. Check PVC is bound: `kubectl get pvc -n lumuscar-jobs slim-control-db`
2. Ensure security context allows writing: `runAsUser: 0`

### Node Connection Failed

If the node can't connect to controller:
1. Verify controller is running: `./scripts/slim-controller.sh status`
2. Check service DNS: `kubectl get svc -n lumuscar-jobs slim-control`
3. Verify network policies allow traffic on port 50052

### Permission Errors

If Helm install fails with RBAC errors, ensure the service account has permissions for:
- `deployments`, `statefulsets`
- `services`, `configmaps`
- `serviceaccounts`, `secrets`
- `persistentvolumeclaims`

### SPIRE mTLS Mode - Southbound Not Starting (Known Issue)

When SPIRE mTLS is enabled, the controller's southbound API may not start, causing nodes to fail to connect.

**Workaround**: Use insecure mode until this issue is resolved:
```bash
./scripts/slim-controller.sh install
./scripts/slim-node.sh install
```

See [issues.md](./issues.md) for full details and reproduction steps.

## SPIRE Integration (mTLS)

SLIM supports [SPIRE](https://spiffe.io/docs/latest/spire-about/) for mutual TLS (mTLS) authentication between components. SPIRE provides:

- **Zero-trust security**: All connections authenticated via SPIFFE IDs
- **Automatic certificate rotation**: No manual certificate management
- **Cross-cluster federation**: Trust domains can be federated for multi-cluster deployments

### Architecture with SPIRE

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SPIRE Server                                │
│                    (Trust Domain Authority)                         │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │  Issues SVIDs (SPIFFE Verifiable Identity Documents)        │  │
│   │  Manages trust bundles for federation                       │  │
│   └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                    SPIRE Agent (per node)
                    Socket: /run/spire/agent-sockets/api.sock
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ SLIM Controller│     │   SLIM Node     │     │   SLIM Node     │
│   (mTLS)      │◄───►│    (mTLS)       │◄───►│    (mTLS)       │
└───────────────┘     └─────────────────┘     └─────────────────┘
```

### Prerequisites for SPIRE

1. **SPIRE Server** deployed in the cluster
2. **SPIRE Agent** running as DaemonSet on each node
3. **Workload registration** for SLIM components

### Enabling SPIRE on SLIM Controller

```bash
helm install slim-controller slim-control-plane-v0.7.0.tgz \
  -n lumuscar-jobs \
  --set config.database.filePath="/db/controlplane.db" \
  --set spire.enabled=true \
  --set "spire.trustedDomains={cluster-a.example.org,cluster-b.example.org}"
```

Controller Helm values for SPIRE:

```yaml
spire:
  enabled: true
  # Trust domains for multi-cluster federation
  trustedDomains:
    - cluster-a.example.org
    - cluster-b.example.org

config:
  southbound:
    httpHost: 0.0.0.0
    httpPort: "50052"
    tls:
      useSpiffe: true
    spire:
      socketPath: "unix:///run/spire/agent-sockets/api.sock"
```

### Enabling SPIRE on SLIM Node

```bash
helm install slim-slim-node slim-v0.7.0.tgz \
  -n lumuscar-jobs \
  --set spire.enabled=true \
  --set "spire.trustedDomains={cluster-a.example.org}"
```

Node configuration with SPIRE (in ConfigMap):

```yaml
services:
  slim/0:
    node_id: ${env:SLIM_SVC_ID}

    dataplane:
      servers:
        - endpoint: "0.0.0.0:46357"
          tls:
            # Use SPIRE for TLS certificates
            source:
              type: spire
              socket_path: unix://tmp/spire-agent/public/api.sock

    controller:
      # Connect to controller with mTLS via SPIRE
      clients:
        - endpoint: "https://slim-control:50052"
          tls:
            cert_file: "/svids/tls.crt"
            key_file: "/svids/tls.key"
            ca_file: "/svids/svid_bundle.pem"

      servers:
        - endpoint: "0.0.0.0:46358"
          tls:
            source:
              type: spire
              socket_path: unix://tmp/spire-agent/public/api.sock
```

### SPIRE Helper Sidecar

When SPIRE is enabled, the Helm chart automatically adds a `spiffe-helper` sidecar container that:

1. Connects to the SPIRE Agent socket
2. Fetches and renews SVIDs (X.509 certificates)
3. Writes certificates to a shared volume at `/svids/`

```yaml
# Automatically configured when spire.enabled=true
spire:
  enabled: true
  helperImage:
    repository: ghcr.io/spiffe/spiffe-helper
    tag: "0.10.1"
```

### Workload Registration

Register SLIM workloads with SPIRE Server:

```bash
# Register SLIM Controller
kubectl exec -n spire spire-server-0 -- \
  /opt/spire/bin/spire-server entry create \
  -spiffeID spiffe://example.org/slim/controller \
  -parentID spiffe://example.org/ns/lumuscar-jobs/sa/slim-control \
  -selector k8s:ns:lumuscar-jobs \
  -selector k8s:sa:slim-control

# Register SLIM Node
kubectl exec -n spire spire-server-0 -- \
  /opt/spire/bin/spire-server entry create \
  -spiffeID spiffe://example.org/slim/node \
  -parentID spiffe://example.org/ns/lumuscar-jobs/sa/slim \
  -selector k8s:ns:lumuscar-jobs \
  -selector k8s:sa:slim
```

### Multi-Cluster Federation

For cross-cluster communication, configure trust domain federation:

```yaml
# Controller in Cluster A
spire:
  enabled: true
  trustedDomains:
    - cluster-b.example.org  # Trust cluster B

# Controller in Cluster B
spire:
  enabled: true
  trustedDomains:
    - cluster-a.example.org  # Trust cluster A
```

This allows SLIM nodes in different clusters to communicate securely via federated trust.

### Verifying SPIRE Integration

Check that SVIDs are being issued:

```bash
# Check spiffe-helper sidecar logs
kubectl logs -n lumuscar-jobs slim-slim-node-0 -c spiffe-helper

# Verify certificates exist
kubectl exec -n lumuscar-jobs slim-slim-node-0 -c slim -- ls -la /svids/
```

Expected files in `/svids/`:
- `tls.crt` - X.509 certificate
- `tls.key` - Private key
- `svid_bundle.pem` - CA bundle for verification

## References

- [AGNTCY SLIM Documentation](https://docs.agntcy.org/pages/slim/)
- [SLIM Kubernetes Deployment](https://docs.agntcy.org/pages/slim/deployment/kubernetes/)
- [SLIM GitHub Repository](https://github.com/agntcy/slim)
- [SPIFFE/SPIRE Documentation](https://spiffe.io/docs/latest/)
- [SPIRE Kubernetes Quickstart](https://spiffe.io/docs/latest/try/getting-started-k8s/)
