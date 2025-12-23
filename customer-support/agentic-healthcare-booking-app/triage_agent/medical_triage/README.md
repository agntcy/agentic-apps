# A2A Medical Triage Agent - Deployment Guide

## Overview

This is a comprehensive deployment guide for the **A2A Protocol Compliant Medical Triage Agent** - an advanced AI-powered medical triage system that uses dynamic LLM-generated questions and follows the Agent2Agent (A2A) protocol specification for seamless agent-to-agent communication.

## Features

### ✅ Enhanced Capabilities
- **Dynamic LLM Questioning**: Generates intelligent, contextual follow-up questions using advanced AI
- **A2A Protocol Compliant**: Full compliance with A2A v0.3.0 specification
- **Multi-Stage Triage**: Initial assessment → Generic questions → AI-generated specific questions → Final assessment
- **Emergency Detection**: Real-time identification of life-threatening conditions
- **Agent Discovery**: Standardized Agent Card for multi-agent ecosystems

### ✅ A2A Protocol Features
- JSON-RPC 2.0 over HTTP(S)
- Agent Card for discovery (`/./agent-card.json`)
- Task lifecycle management
- Streaming support (SSE)
- Structured message and artifact handling
- Enterprise-ready security

### ✅ Medical Specializations
- General symptom triage
- Emergency condition assessment  
- Pediatric symptom evaluation
- Chronic condition monitoring
- Medication interaction checking

## Quick Start

### 1. Prerequisites

```bash
# Required
- Docker & Docker Compose
- OpenAI API access (Azure OpenAI or OpenAI)
- Domain name (for production)

# Optional
- Traefik for reverse proxy
- Prometheus/Grafana for monitoring
- Redis for session storage
```

### 2. Environment Setup

Create a `.env` file:

```bash
# Required Configuration
OPENAI_URL=https://your-azure-openai.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-02-15-preview
OPENAI_API_KEY=your-openai-api-key

# Optional Configuration
OPENAI_MODEL=gpt-4o
OPENAI_PROVIDER=Azure-OpenAI
PORT=8080
HOST=0.0.0.0
DEBUG=false

# Security
API_KEY=your-secure-api-key

# Domain
EXTERNAL_PORT=8080
ACME_EMAIL=admin@domain.com

# Monitoring
GRAFANA_PASSWORD=secure-grafana-password
REDIS_PASSWORD=secure-redis-password
```

### 3. Quick Deployment

```bash
# Clone or download the files
git clone <repository> && cd triage_agent

# Start the basic service
docker-compose up -d triage_agent

# Or start with all services (proxy, monitoring, cache)
docker-compose --profile proxy --profile monitoring --profile cache up -d
```

### 4. Verify Deployment

```bash
# Check health
curl http://localhost:8080/health

# Get Agent Card
curl http://localhost:8080/./agent-card.json

# Test A2A endpoint
curl -X POST http://localhost:8080/a2a/v1 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "I have a severe headache"}],
        "messageId": "test-123"
      }
    },
    "id": 1
  }'
```

## Production Deployment

### Security Configuration

1. **API Keys**: Set strong API keys in environment variables
2. **HTTPS**: Enable TLS termination via Traefik or load balancer
3. **Network Security**: Use private networks and firewall rules
4. **Authentication**: Configure security schemes in Agent Card

### Scaling Considerations

```yaml
# docker-compose.override.yml for scaling
version: '3.8'
services:
  triage-agent:
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'
```

### Domain Setup

1. **DNS Configuration**: Point your domain to the server
2. **SSL Certificates**: Automatic via Let's Encrypt (Traefik)
3. **Agent Card URL**: Update URL in agent card to production domain

## A2A Protocol Integration

### Agent Discovery

Other A2A agents can discover this triage agent via:

```bash
# URI
GET https://domain.com/.triage_agentcard.json

# Returns the Agent Card with capabilities and endpoints
```

### Supported A2A Methods

| Method | Description | Status |
|--------|-------------|--------|
| `message/send` | Send message to agent | ✅ Implemented |
| `message/stream` | Send message with SSE streaming | ✅ Implemented |
| `tasks/get` | Get task status and results | ✅ Implemented |
| `tasks/cancel` | Cancel running task | ✅ Implemented |
| `tasks/pushNotificationConfig/*` | Push notification config | 🚧 Future |

### Example A2A Integration

```python
# Example: Another agent calling this triage agent
import requests

# Discover agent capabilities
agent_card = requests.get("https://triage.domain.com/.triage_agentcard.json").json()

# Send triage request
response = requests.post(
    agent_card["url"],
    json={
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "Patient reports chest pain"}],
                "messageId": "supervisor-request-456"
            },
            "configuration": {
                "acceptedOutputModes": ["application/json"],
                "blocking": True
            }
        },
        "id": 1
    }
)

triage_result = response.json()["result"]
```

## Monitoring and Observability

### Health Checks

```bash
# Basic health check
curl http://localhost:8080/health

# Detailed status
curl http://localhost:8080/docs
```

### Prometheus Metrics

Access metrics at: `http://localhost:9090`

Key metrics to monitor:
- Task completion rates
- Response times
- Error rates
- Emergency detection frequency

### Grafana Dashboards

Access dashboards at: `http://localhost:3000`

Pre-configured dashboards for:
- A2A Protocol metrics
- Medical triage statistics
- System performance
- Error tracking

## Advanced Configuration

### Custom Medical AI Models

```python
# Configure different AI models
OPENAI_MODEL=gpt-4o-mini  # For cost optimization
OPENAI_MODEL=gpt-4o       # For maximum accuracy
```

### Extended Agent Card

```json
{
  "supportsAuthenticatedExtendedCard": true,
  "additionalSkills": [
    {
      "id": "custom-specialty",
      "name": "Custom Medical Specialty",
      "description": "Specialized assessment for specific conditions"
    }
  ]
}
```

### Integration with MCP (Model Context Protocol)

The agent is designed to work alongside MCP for tool integration:

```python
# MCP for tools, A2A for agent communication
# Agent uses MCP to access medical databases
# Agent exposes A2A interface for other agents
```

## Troubleshooting

### Common Issues

1. **OpenAI API Errors**
   ```bash
   # Check API key and endpoint
   curl -H "Authorization: Bearer $OPENAI_API_KEY" $OPENAI_URL
   ```

2. **Docker Issues**
   ```bash
   # Check logs
   docker-compose logs triage-agent
   
   # Restart services
   docker-compose restart
   ```

3. **A2A Protocol Errors**
   ```bash
   # Validate JSON-RPC requests
   # Check Agent Card accessibility
   # Verify protocol version compatibility
   ```

### Support and Maintenance

- **Logs**: Available in `./logs/` directory
- **Data**: Persistent in `./data/` directory
- **Configuration**: Modify via environment variables
- **Updates**: Pull new image and restart

## Architecture Diagram

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   A2A Client    │────│  Load Balancer   │────│ Triage Agent    │
│   (Other Agent) │    │    (Traefik)     │    │   (Flask App)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │  Medical AI     │
                                                │   (OpenAI)      │
                                                └─────────────────┘
```

## Security Best Practices

1. **Environment Variables**: Never commit secrets to version control
2. **Network Isolation**: Use Docker networks and firewalls
3. **TLS Encryption**: Always use HTTPS in production
4. **API Rate Limiting**: Implement rate limiting for API endpoints
5. **Input Validation**: Validate all incoming A2A requests
6. **Audit Logging**: Log all medical triage sessions
7. **Regular Updates**: Keep dependencies and base images updated

## Compliance and Legal

⚠️ **Important**: This is a demonstration system. For production medical use:

- Ensure compliance with HIPAA, GDPR, and local medical regulations
- Implement proper medical record handling
- Add medical professional oversight
- Include appropriate disclaimers
- Obtain necessary medical software certifications

## Contributing

1. Fork the repository
2. Create feature branches
3. Follow A2A protocol specifications
4. Add tests for new functionality
5. Submit pull requests

## Support

- **Documentation**: `/docs` endpoint
- **Health Status**: `/health` endpoint  
- **Agent Card**: `/.well-known/agent-card.json`
- **Issues**: GitHub Issues
- **A2A Protocol**: https://a2a-protocol.org/

## References

1. https://github.com/Lucanyc/TriageAgent
2. https://github.com/souvikmajumder26/Multi-Agent-Medical-Assistant
