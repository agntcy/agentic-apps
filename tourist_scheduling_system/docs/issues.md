# Known Issues

This document tracks known issues discovered during development and deployment.

---

## SLIM Controller Southbound API Does Not Start with SPIRE mTLS

**Status**: Open
**Discovered**: December 6, 2025
**Component**: SLIM Control Plane
**Severity**: High

### Summary

When enabling SPIRE mTLS on the SLIM controller via the Helm chart, the southbound API service fails to start. The northbound API starts successfully, but no southbound listener is created, causing SLIM nodes to fail to connect.

### Steps to Reproduce

1. Deploy SPIRE server and agents:
   ```bash
   ./scripts/spire.sh install
   ```

2. Register SLIM workloads with SPIRE:
   ```bash
   ./scripts/spire.sh register-slim
   ```

3. Install SLIM controller with SPIRE enabled:
   ```bash
   SPIRE_ENABLED=true ./scripts/slim-controller.sh install
   ```

   Or manually via Helm:
   ```bash
   helm install slim-controller slim-control-plane-v0.7.0.tgz \
     -n lumuscar-jobs \
     --set config.database.filePath="/db/controlplane.db" \
     --set spire.enabled=true \
     --set spire.agentSocketPath="unix:///run/spire/agent-sockets/spire-agent.sock" \
     --set config.southbound.tls.useSpiffe=true \
     --set config.southbound.spire.socketPath="unix:///run/spire/agent-sockets/spire-agent.sock"
   ```

4. Install SLIM node with SPIRE enabled:
   ```bash
   SPIRE_ENABLED=true ./scripts/slim-node.sh install
   ```

5. Check controller logs:
   ```bash
   kubectl logs -n lumuscar-jobs -l app.kubernetes.io/name=slim-control-plane
   ```

### Expected Behavior

Controller starts both APIs:
- Northbound API on port 50051
- Southbound API on port 50052 with mTLS via SPIRE

### Actual Behavior

- Controller logs only show: `Northbound API Service is listening on [::]:50051`
- Southbound service never starts (no log entry)
- No error messages indicating why southbound failed
- SLIM node connection attempts fail with:
  ```
  connecting to control plane config.endpoint=https://slim-control:50052
  Connection attempt: #1 failed: status: 'The service is currently unavailable', self: "tcp connect error"
  Connection attempt: #2 failed: status: 'The service is currently unavailable', self: "tcp connect error"
  ...
  ```

### Controller Configuration (from ConfigMap)

```yaml
database:
  filePath: /db/controlplane.db
logging:
  level: DEBUG
northbound:
  httpHost: 0.0.0.0
  httpPort: '50051'
reconciler:
  maxNumOfParallelReconciles: 1000
  maxRequeues: 15
southbound:
  httpHost: 0.0.0.0
  httpPort: '50052'
  spire:
    socketPath: unix:///run/spire/agent-sockets/spire-agent.sock
  tls:
    useSpiffe: true
```

### Environment

| Component | Version |
|-----------|---------|
| SLIM Control Plane Helm Chart | v0.7.0 |
| SLIM Node Helm Chart | v0.7.0 |
| SPIRE Server/Agent | v1.13.2 |
| SPIRE Helm Chart | v0.27.1 |
| Kubernetes | MicroK8s |
| Trust Domain | example.org |

### Verification Performed

- ✅ SPIRE server running (1 pod)
- ✅ SPIRE agents running on all nodes (6 pods via DaemonSet)
- ✅ SPIRE socket mounted in controller pod at `/run/spire/agent-sockets/`
- ✅ Workload entries registered for `slim-control` and `slim` service accounts:
  ```
  spiffe://example.org/slim/controller -> k8s:sa:slim-control
  spiffe://example.org/slim/node -> k8s:sa:slim
  ```
- ✅ Insecure mode works correctly - controller and node connect successfully

### Controller Pod Volume Mounts

```yaml
volumeMounts:
  - mountPath: /config.yaml
    name: config-volume
    subPath: config.yaml
  - mountPath: /run/spire/agent-sockets
    name: spire-agent-socket
  - mountPath: /db
    name: db-storage

volumes:
  - hostPath:
      path: /run/spire/agent-sockets
      type: Directory
    name: spire-agent-socket
```

### Workaround

Use insecure mode until this issue is resolved:

```bash
# Deploy without SPIRE (works)
./scripts/slim-controller.sh install
./scripts/slim-node.sh install
```

### Related

- SLIM Repository: https://github.com/agntcy/slim
- Issue to be filed: [TBD]

---

## Agent Directory gRPC Server Does Not Start with SPIRE mTLS

**Status**: Open
**Discovered**: December 7, 2025
**Component**: Agent Directory (dir)
**Severity**: High

### Summary

When enabling SPIRE authentication on the Agent Directory via the Helm chart, the gRPC API server on port 8888 fails to start. The pod initializes P2P/routing components but never starts the gRPC listener, causing liveness/readiness probes to fail and the container to restart repeatedly.

### Steps to Reproduce

1. Deploy SPIRE server and agents (if not already running):
   ```bash
   ./scripts/spire.sh install
   ```

2. Install Agent Directory with SPIRE authentication enabled:
   ```bash
   DIR_AUTHN_ENABLED=true ./scripts/directory.sh install
   ```

   Or manually via Helm:
   ```bash
   helm install dir dir-v0.5.6.tgz \
     -n lumuscar-jobs \
     --set apiserver.spire.enabled=true \
     --set apiserver.spire.trustDomain=example.org \
     --set apiserver.spire.useCSIDriver=false \
     --set apiserver.config.authn.enabled=true \
     --set apiserver.config.authn.mode=x509 \
     --set apiserver.config.authn.socket_path="unix:///run/spire/agent-sockets/spire-agent.sock"
   ```

3. Check pod status:
   ```bash
   kubectl get pods -n lumuscar-jobs -l app.kubernetes.io/instance=dir
   ```

4. Check apiserver logs:
   ```bash
   kubectl logs -n lumuscar-jobs -l app.kubernetes.io/name=apiserver
   ```

### Expected Behavior

API server starts with mTLS:
- gRPC API listening on port 8888 with x509/SPIRE authentication
- Metrics endpoint on port 9090
- Pod becomes Ready (1/1)

### Actual Behavior

- Pod shows `0/1 Running` with repeated restarts
- Logs show successful P2P/routing initialization but no gRPC server start
- Liveness and readiness probes fail:
  ```
  Readiness probe failed: dial tcp 10.1.69.244:8888: connect: connection refused
  Liveness probe failed: dial tcp 10.1.69.244:8888: connect: connection refused
  ```
- No error messages indicating why gRPC server failed to start

### Apiserver Logs (truncated at failure point)

```
time=... level=INFO msg="OASF validator configured" component=server ...
time=... level=INFO msg="Connection management configured" component=server ...
time=... level=INFO msg="Metrics enabled" component=server address=:9090
time=... level=INFO msg="Initializing event service" component=events ...
time=... level=INFO msg="mDNS local discovery enabled" component=p2p ...
time=... level=INFO msg="AutoRelay enabled with DHT peer source" component=p2p
time=... level=INFO msg="GossipSub manager initialized" component=routing/pubsub ...
time=... level=INFO msg="GossipSub label announcements enabled" component=routing/remote
time=... level=INFO msg="Started periodic GossipSub mesh peer tagging" ...
# No gRPC server start message - container killed by probe failure
```

### Configuration (from ConfigMap)

```yaml
authn:
  audiences:
  - spiffe://example.org/dir-server
  enabled: true
  mode: x509
  socket_path: unix:///run/spire/agent-sockets/spire-agent.sock
authz:
  enabled: false
  trust_domain: example.org
```

### Environment

| Component | Version |
|-----------|---------|
| Agent Directory Helm Chart | v0.5.6 |
| dir-apiserver image | ghcr.io/agntcy/dir-apiserver:latest |
| SPIRE Server/Agent | v1.13.2 |
| SPIRE Helm Chart | v0.27.1 |
| Kubernetes | MicroK8s |
| Trust Domain | example.org |

### Verification Performed

- ✅ SPIRE server and agents running
- ✅ SPIRE socket mounted in apiserver pod at `/run/spire/agent-sockets/`
- ✅ ClusterSPIFFEID `dir-apiserver` created by Helm chart
- ✅ Insecure mode works correctly - both apiserver and zot pods run successfully (1/1)
- ✅ Zot registry unaffected - runs fine regardless of apiserver SPIRE config

### Apiserver Pod Volume Mounts

```yaml
volumeMounts:
  - mountPath: /config
    name: config-volume
  - mountPath: /run/spire/agent-sockets
    name: spire-agent-socket
  - mountPath: /etc/zot
    name: zot-config-storage

volumes:
  - hostPath:
      path: /run/spire/agent-sockets
      type: Directory
    name: spire-agent-socket
```

### Workaround

Use insecure mode until this issue is resolved:

```bash
# Deploy without SPIRE authentication (works)
./scripts/directory.sh install

# Verify pods are running
./scripts/directory.sh status
```

### Related

- Agent Directory Repository: https://github.com/agntcy/dir
- Similar issue: SLIM Controller Southbound API Does Not Start with SPIRE mTLS (above)
- Issue to be filed: [TBD]

---