# Kubernetes Deployment

Kubernetes manifests for deploying the Tourist Scheduling System agents.

## Prerequisites

1. **Container images** built and pushed to a registry
2. **Kubernetes cluster** with access configured
3. **kubectl** configured to access your cluster
4. **Infrastructure deployed separately**:
   - SLIM: Use the [SLIM Helm chart](https://github.com/agntcy/slim/tree/main/helm)
   - Jaeger: Use the [Jaeger Operator](https://www.jaegertracing.io/docs/latest/operator/)

## Manifests

| File | Agent | Type | Description |
|------|-------|------|-------------|
| `namespace.yaml` | - | Namespace | Creates `tourist-scheduling` namespace |
| `scheduler-agent.yaml` | scheduler | Deployment | A2A server for coordination |
| `ui-agent.yaml` | ui | Deployment | Dashboard A2A server |
| `guide-agent.yaml` | guide | Job | Submits guide offers |
| `tourist-agent.yaml` | tourist | Job | Submits tour requests |

## Quick Start

### 1. Build and Push Images

```bash
cd tourist_scheduling_system

# Build all images
docker-compose build

# Tag and push to your registry
export REGISTRY=ghcr.io/your-org  # or gcr.io/your-project
export TAG=latest

docker tag scheduler-agent:latest $REGISTRY/scheduler-agent:$TAG
docker tag ui-agent:latest $REGISTRY/ui-agent:$TAG
docker tag guide-agent:latest $REGISTRY/guide-agent:$TAG
docker tag tourist-agent:latest $REGISTRY/tourist-agent:$TAG

docker push $REGISTRY/scheduler-agent:$TAG
docker push $REGISTRY/ui-agent:$TAG
docker push $REGISTRY/guide-agent:$TAG
docker push $REGISTRY/tourist-agent:$TAG
```

### 2. Create Namespace and Secrets

```bash
# Create namespace
kubectl apply -f deploy/k8s/namespace.yaml

# Create Azure OpenAI credentials secret
kubectl create secret generic azure-openai-credentials \
  --from-literal=api-key=$AZURE_OPENAI_API_KEY \
  --from-literal=endpoint=$AZURE_OPENAI_ENDPOINT \
  --from-literal=deployment-name=${AZURE_OPENAI_DEPLOYMENT_NAME:-gpt-4o} \
  -n tourist-scheduling
```

### 3. Deploy Infrastructure (Separately)

Deploy SLIM and Jaeger using their official Helm charts:

```bash
# SLIM (example)
helm repo add agntcy https://agntcy.github.io/slim
helm install slim agntcy/slim -n tourist-scheduling

# Jaeger (example)
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
helm install jaeger jaegertracing/jaeger -n tourist-scheduling
```

### 4. Deploy Agents

```bash
# Deploy server agents (long-running Deployments)
kubectl apply -f deploy/k8s/scheduler-agent.yaml
kubectl apply -f deploy/k8s/ui-agent.yaml

# Wait for servers to be ready
kubectl wait --for=condition=available deployment/scheduler-agent -n tourist-scheduling --timeout=120s
kubectl wait --for=condition=available deployment/ui-dashboard-agent -n tourist-scheduling --timeout=120s

# Run client agents (one-time Jobs)
kubectl apply -f deploy/k8s/guide-agent.yaml
kubectl apply -f deploy/k8s/tourist-agent.yaml
```

### 5. Verify

```bash
# Check deployments
kubectl get deployments -n tourist-scheduling

# Check jobs
kubectl get jobs -n tourist-scheduling

# Get dashboard URL
kubectl get svc ui-dashboard-agent -n tourist-scheduling

# View logs
kubectl logs -l app=scheduler-agent -n tourist-scheduling
kubectl logs -l app=guide-agent -n tourist-scheduling
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ tourist-scheduling namespace                                    │
│                                                                 │
│  ┌─────────────────┐           ┌─────────────────────┐         │
│  │ scheduler-agent │◄──────────│  ui-dashboard-agent │         │
│  │  (Deployment)   │           │    (Deployment)     │         │
│  │  Port: 10000    │           │    Port: 10021      │         │
│  └────────▲────────┘           └─────────────────────┘         │
│           │                                                     │
│           │ A2A Protocol                                        │
│           │                                                     │
│  ┌────────┴────────┐           ┌─────────────────────┐         │
│  │   guide-agent   │           │   tourist-agent     │         │
│  │     (Job)       │           │      (Job)          │         │
│  └─────────────────┘           └─────────────────────┘         │
│                                                                 │
│  Infrastructure (deployed separately):                          │
│  ┌─────────────────┐           ┌─────────────────────┐         │
│  │      SLIM       │           │      Jaeger         │         │
│  │  (Helm Chart)   │           │   (Helm Chart)      │         │
│  └─────────────────┘           └─────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

## Cleanup

```bash
# Delete all resources
kubectl delete namespace tourist-scheduling
```
