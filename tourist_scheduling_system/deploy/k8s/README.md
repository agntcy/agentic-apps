# Kubernetes Deployment

Kubernetes manifests for deploying the Tourist Scheduling System agents.

## Prerequisites

1. **Container images** built and pushed to a registry
2. **Kubernetes cluster** with access configured
3. **kubectl** configured to access your cluster
4. **envsubst** installed (usually comes with gettext)
5. **Azure OpenAI** or **Google Gemini** credentials
6. **Agent Directory** deployed (optional but recommended for dynamic discovery)

## Transport Modes

The system supports two transport modes:

| Mode | Description | Requirements |
|------|-------------|--------------|
| **HTTP** | Direct HTTP communication between agents | None (default) |
| **SLIM** | Secure communication via SLIM gateway with mTLS | SLIM infrastructure deployed |

## Manifests

| File | Description |
|------|-------------|
| `namespace.yaml` | Namespace and shared ConfigMap |
| `scheduler-agent.yaml` | A2A server for coordination |
| `ui-agent.yaml` | Dashboard A2A server |
| `guide-agent.yaml` | Sample guide agent jobs (2 guides) |
| `tourist-agent.yaml` | Sample tourist agent jobs (2 tourists) |
| `deploy.sh` | Deployment script |
| `spawn-agents.sh` | Scale multiple guides/tourists |
| `templates/` | Job templates for dynamic generation |
| `../scripts/directory.sh` | Script to deploy the Agent Directory |

## Quick Start

### 1. Build and Push Images

```bash
cd tourist_scheduling_system

export IMAGE_REGISTRY=ghcr.io/your-org
export IMAGE_TAG=latest

# Build and push images
docker-compose build
docker tag scheduler-agent:latest $IMAGE_REGISTRY/scheduler-agent:$IMAGE_TAG
docker tag ui-agent:latest $IMAGE_REGISTRY/ui-agent:$IMAGE_TAG
docker push $IMAGE_REGISTRY/scheduler-agent:$IMAGE_TAG
docker push $IMAGE_REGISTRY/ui-agent:$IMAGE_TAG
```

### 2. Deploy Agent Directory (Recommended)

```bash
# Deploy the Agent Directory to the cluster
./scripts/directory.sh install
```

### 3. Deploy with HTTP Transport (Default)

```bash
export NAMESPACE=lumuscar-jobs
export IMAGE_REGISTRY=ghcr.io/your-org
export IMAGE_TAG=latest

# Create namespace and deploy
./deploy/k8s/deploy.sh http

# Create Azure OpenAI credentials secret
kubectl create secret generic azure-openai-credentials \
  --from-literal=api-key=$AZURE_OPENAI_API_KEY \
  --from-literal=endpoint=$AZURE_OPENAI_ENDPOINT \
  --from-literal=deployment-name=${AZURE_OPENAI_DEPLOYMENT_NAME:-gpt-4o} \
  -n $NAMESPACE
```

### 3. Deploy with SLIM Transport

For secure mTLS communication between agents, first install SLIM infrastructure:

```bash
# Install SPIRE and SLIM (see scripts/ folder)
./scripts/spire.sh install
./scripts/slim-controller.sh install
./scripts/slim-node.sh install

# Deploy agents with SLIM transport
export NAMESPACE=lumuscar-jobs
export TRANSPORT_MODE=slim
export SLIM_GATEWAY_HOST=slim-slim-node
export SLIM_GATEWAY_PORT=46357

./deploy/k8s/deploy.sh slim
```

### 4. Deploy Client Agents (Jobs)

```bash
export NAMESPACE=lumuscar-jobs
export IMAGE_REGISTRY=ghcr.io/your-org

# Deploy sample guide and tourist agents (2 each)
envsubst < deploy/k8s/guide-agent.yaml | kubectl apply -f -
envsubst < deploy/k8s/tourist-agent.yaml | kubectl apply -f -
```

## Scaling Multiple Agents

Use `spawn-agents.sh` to deploy many guides and tourists with randomized configurations:

```bash
cd deploy/k8s

# Spawn 10 guide agents
./spawn-agents.sh guides 10

# Spawn 20 tourist agents
./spawn-agents.sh tourists 20

# Spawn both: 5 guides and 15 tourists
./spawn-agents.sh both 5 15

# Check status
./spawn-agents.sh status

# View logs for a specific agent
./spawn-agents.sh logs guide 3
./spawn-agents.sh logs tourist 5

# Clean up all agent jobs
./spawn-agents.sh clean
```

Each spawned agent gets:
- **Guides**: Random categories, availability windows, hourly rates, group sizes
- **Tourists**: Random preferences, availability windows, budgets

### Custom Agent Configuration

For fine-grained control, use the templates directly:

```bash
# Single guide with specific config
export GUIDE_ID=expert1
export GUIDE_CATEGORIES="art,history,architecture"
export GUIDE_START="2025-06-01T08:00:00"
export GUIDE_END="2025-06-01T18:00:00"
export GUIDE_RATE=150
export GUIDE_MAX_GROUP=3

envsubst < deploy/k8s/templates/guide-agent.yaml.tpl | kubectl apply -f -

# Single tourist with specific preferences
export TOURIST_ID=vip1
export TOURIST_PREFERENCES="art,wine,fine-dining"
export TOURIST_START="2025-06-01T10:00:00"
export TOURIST_END="2025-06-01T16:00:00"
export TOURIST_BUDGET=500

envsubst < deploy/k8s/templates/tourist-agent.yaml.tpl | kubectl apply -f -
```

### 5. Verify Deployment

```bash
# Check status
./deploy/k8s/deploy.sh status

# Or manually:
kubectl get pods -l app.kubernetes.io/part-of=tourist-scheduling -n $NAMESPACE
kubectl get svc -l app.kubernetes.io/part-of=tourist-scheduling -n $NAMESPACE
kubectl get jobs -l app.kubernetes.io/part-of=tourist-scheduling -n $NAMESPACE

# View logs
kubectl logs -l app=scheduler-agent -n $NAMESPACE
kubectl logs -l app=guide-agent -n $NAMESPACE
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NAMESPACE` | `lumuscar-jobs` | Target Kubernetes namespace |
| `IMAGE_REGISTRY` | `ghcr.io/agntcy/apps` | Container image registry |
| `IMAGE_TAG` | `latest` | Container image tag |
| `TRANSPORT_MODE` | `http` | Transport mode: `http` or `slim` |
| `SLIM_GATEWAY_HOST` | `slim-slim-node` | SLIM gateway service name |
| `SLIM_GATEWAY_PORT` | `46357` | SLIM gateway port |
| `DIRECTORY_CLIENT_SERVER_ADDRESS` | `localhost:8888` | Address of the Agent Directory (e.g., `dir-service:8888`) |

## Architecture

### HTTP Mode

```
┌─────────────────────────────────────────────────────────────────┐
│ ${NAMESPACE} namespace                                          │
│                                                                 │
│  ┌─────────────────┐    HTTP    ┌─────────────────────┐        │
│  │ scheduler-agent │◄──────────►│  ui-dashboard-agent │        │
│  │  (Deployment)   │            │    (Deployment)     │        │
│  │  Port: 10000    │            │    Port: 10021      │        │
│  └────────▲────────┘            └─────────────────────┘        │
│           │                                                     │
│           │ HTTP A2A Protocol                                   │
│           │                                                     │
│  ┌────────┴────────┐            ┌─────────────────────┐        │
│  │   guide-agent   │            │   tourist-agent     │        │
│  │     (Job)       │            │      (Job)          │        │
│  └─────────────────┘            └─────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

### SLIM Mode (mTLS)

```
┌─────────────────────────────────────────────────────────────────┐
│ ${NAMESPACE} namespace                                          │
│                                                                 │
│  ┌─────────────────┐            ┌─────────────────────┐        │
│  │ scheduler-agent │            │  ui-dashboard-agent │        │
│  │  (Deployment)   │            │    (Deployment)     │        │
│  └────────▲────────┘            └──────────▲──────────┘        │
│           │                                │                    │
│           │ mTLS via SLIM Gateway          │                    │
│           │                                │                    │
│  ┌────────┴────────────────────────────────┴──────────┐        │
│  │              SLIM Gateway (slim-slim-node)         │        │
│  │                    Port: 46357                      │        │
│  └────────▲────────────────────────────────▲──────────┘        │
│           │                                │                    │
│  ┌────────┴────────┐            ┌──────────┴──────────┐        │
│  │   guide-agent   │            │   tourist-agent     │        │
│  │     (Job)       │            │      (Job)          │        │
│  └─────────────────┘            └─────────────────────┘        │
│                                                                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │ SPIRE Agent (CSI Driver)                            │       │
│  │ Provides workload identities & mTLS certificates    │       │
│  └─────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## Cleanup

```bash
# Remove deployed resources (preserves namespace and secrets)
./deploy/k8s/deploy.sh clean

# Or delete entire namespace
kubectl delete namespace $NAMESPACE
```

## Troubleshooting

### Pods not starting

```bash
# Check pod events
kubectl describe pod -l app=scheduler-agent -n $NAMESPACE

# Check if secret exists
kubectl get secret azure-openai-credentials -n $NAMESPACE
```

### SLIM connection issues

```bash
# Check SLIM node is running
kubectl get pods -l app.kubernetes.io/name=slim-node -n $NAMESPACE

# Check SLIM node logs
kubectl logs -l app.kubernetes.io/name=slim-node -n $NAMESPACE

# Verify SPIRE agent
kubectl get pods -l app.kubernetes.io/name=spire-agent -n lumuscar-spire
```

### ConfigMap values

```bash
# View current configuration
kubectl get configmap agent-config -n $NAMESPACE -o yaml
```
