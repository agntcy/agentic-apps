# Container Deployment

This directory contains Dockerfiles for packaging the tourist scheduling agents as container images,
following the [ADK GKE deployment patterns](https://google.github.io/adk-docs/deploy/gke/).

## Directory Structure

```
containers/
├── scheduler/          # Scheduler agent (A2A server - Deployment)
│   ├── Dockerfile
│   └── main.py
├── ui/                 # UI dashboard agent (A2A server - Deployment)
│   ├── Dockerfile
│   └── main.py
├── guide/              # Guide agent (A2A client - Job)
│   ├── Dockerfile
│   └── main.py
└── tourist/            # Tourist agent (A2A client - Job)
    ├── Dockerfile
    └── main.py
```

## Agent Types

| Agent | Type | K8s Resource | Description |
|-------|------|--------------|-------------|
| scheduler | A2A Server | Deployment | Coordinates tourist-guide matching |
| ui | A2A Server | Deployment | Real-time dashboard |
| guide | A2A Client | Job | Submits guide offers |
| tourist | A2A Client | Job | Submits tour requests |

## Building Images

Build from the `tourist_scheduling_system/` directory:

```bash
# Build all agents
docker-compose build

# Build individual agents
docker build -f containers/scheduler/Dockerfile -t scheduler-agent .
docker build -f containers/ui/Dockerfile -t ui-agent .
docker build -f containers/guide/Dockerfile -t guide-agent .
docker build -f containers/tourist/Dockerfile -t tourist-agent .
```

## Kubernetes Deployment

Each agent has its own manifest in `deploy/k8s/`:

```bash
# Create namespace and secrets first
kubectl apply -f deploy/k8s/namespace.yaml

kubectl create secret generic azure-openai-credentials \
  --from-literal=api-key=$AZURE_OPENAI_API_KEY \
  --from-literal=endpoint=$AZURE_OPENAI_ENDPOINT \
  --from-literal=deployment-name=${AZURE_OPENAI_DEPLOYMENT_NAME:-gpt-4o} \
  -n tourist-scheduling

# Deploy server agents (long-running)
kubectl apply -f deploy/k8s/scheduler-agent.yaml
kubectl apply -f deploy/k8s/ui-agent.yaml

# Run client agents (jobs)
kubectl apply -f deploy/k8s/guide-agent.yaml
kubectl apply -f deploy/k8s/tourist-agent.yaml
```

## Infrastructure

SLIM and Jaeger are infrastructure components that should be deployed separately:

- **SLIM**: Use the [SLIM Helm chart](https://github.com/agntcy/slim/tree/main/helm)
- **Jaeger**: Use the [Jaeger Operator](https://www.jaegertracing.io/docs/latest/operator/) or Helm chart

## Environment Variables

### Server Agents (scheduler, ui)

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | HTTP port | 10000/10021 |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | Required |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint | Required |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Model deployment | gpt-4o |
| `SLIM_ENDPOINT` | SLIM transport | - |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Jaeger endpoint | - |

### Client Agents (guide, tourist)

| Variable | Description | Default |
|----------|-------------|---------|
| `SCHEDULER_URL` | Scheduler A2A endpoint | http://scheduler:10000 |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | Required |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint | Required |

## ADK Compatibility

These containers follow the ADK deployment pattern:

1. **Python package structure**: Agents are importable Python packages
2. **FastAPI/A2A**: Server agents use ADK's `to_a2a()` utility
3. **Health checks**: Server agents expose health endpoints
4. **Non-root user**: Runs as `agentuser` for security
5. **Environment configuration**: All settings via environment variables
