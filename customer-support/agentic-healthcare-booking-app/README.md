# Healthcare Booking Application

A comprehensive healthcare booking and management system built with autonomous agents for insurance verification, medical triage, and voice interactions.

## Project Structure

### `/documentation`
Project documentation and guides. Contains the main README and other supporting documentation files.

### `/insurance-agent`
Insurance verification and benefits checking agent powered by Infinitus API.

- **`infinitus/`** - Core insurance agent implementation
  - `va_mcp.py` - Model Context Protocol integration for Insurance API with voice-agent communication
  - `README.md` - Detailed insurance agent API - MCP documentation

### `/triage_agent`
Medical symptom triage system that assesses patient symptoms and provides preliminary medical assessment and provides recommendations.

- **`infermedica/`** - Symptom triaging powered by Infermedica API
  - **`agntcy/`** - Identity and Observability components
    - **`common/`** -
      - `tbac.py/` - implementation of identity on triage
      - `triage_client/` - triage a2a client
    - **`service/`** - 
        - `triage_service/` - Triage a2a service
    - **`utilities/`** - Testing utilities
      - `tbac_bidirectional.py` - Identity service bidirectional test client
      - `tbac_unidirectional.py` - Identity service unidirectional test client
      - `test_api_util.py` - Triage service test client
    - `main.py` - Identity wrapped A2a service with observability hooks
  
- **`medical-triage/`** - Standalone triage service
  - **`well-known/`** -
    - `agent-card.json` - Agent metadata and capabilities manifest
  - `medical_triage_agent.py` - Core triage logic and API endpoints
  - `Dockerfile` - Containerization configuration
  - `docker-compose.yml` - Service orchestration
  - `requirements.txt` - Python dependencies

### `/voice-agent`
Voice interaction agent for patient communication via phone or voice interface.

- **`agntcy/`** - Voice agent implementation with identity and observe
  - **`agent/`** 
    - `healthcare_agent.py` - voice-agent orchestrator
  - **`models/`** 
    - `session.py` - session management and persistence
  - **`services/`**
    - `a2a_client.py` - A2A protocol client
    - `audio_service.py` - Audio input and output service
    - `insurance_client.py` - Insurance MCP client
    - `llm_client.py` - LLM processing client
  - `main.py` - voice-agent entry point and initialization
  - `README.md` - Detailed voice agent implementation along with identity and observe

### `/common/agntcy/observe`
Observability and metrics collection infrastructure.

- **`deploy/`** - Docker Compose configurations and deployment scripts
  - `docker-compose.yml` - Production stack configuration
  - `docker-compose-build.yml` - Build from source configuration
  - Custom metrics plugin and MCE integration
- **`custom_metrics_plugin/`** - Custom metrics implementation
  - TokenUsage, AgentErrorCount, ToolCallCount, NumberActiveAgents
  
- **`unit-tests/`** - Testing suite
  - `a2a_client.py` - Agent-to-agent communication test client
  - `http_client.py` - HTTP API test client

- **Core MCP Servers:**
  - `va_a2a_mcp.py` - Agent-to-agent,  Model Context Protocol clients with voice-agent communication
  - `va_http_mcp.py` - HTTP-based Medical triage, Model Context Protocol based Insurance clients with voice-agent communication

## Prerequisites

### Environment Variables

Set the following environment variables before running the application:

```bash
# Base paths
export APP_HOME=${APP_HOME:-/Users/xiaodonz/Documents/GitHub/cs1}
export TELEMETRY_HUB_HOME=${TELEMETRY_HUB_HOME:-/Users/xiaodonz/Documents/GitHub/telemetry-hub}

# Observability
export OTLP_HTTP_ENDPOINT="http://localhost:4318"

# LLM Configuration
export JWT_TOKEN="your-jwt-token"
export ENDPOINT_URL="your-endpoint-url"
export PROJECT_ID="your-project-id"
export CONNECTION_ID="your-connection-id"

# MCP Configuration
export MCP_URL="https://mcp.unstable.infinitusai.dev/mcp"
export X_INF_API_KEY="your-api-key"

# A2A Configuration
export A2A_SERVICE_URL="http://localhost:8887"
export A2A_MESSAGE_URL="http://localhost:8887"
export A2A_API_KEY="your-a2a-key"
```

## Getting Started

### 1. Observability Stack

Start the observability services (ClickHouse, OTEL Collector, MCE, Grafana):

```bash
cd common/agntcy/observe/deploy
docker-compose up -d
```

Or use the build version if building from source:

```bash
docker-compose -f docker-compose-build.yml up -d
```

Access Grafana at http://localhost:3000 (admin/admin)

### 2. Voice Agent

```bash
cd voice_agent
source venv/bin/activate
python3 -m agntcy.main
```

See `/voice_agent/README.md` for detailed setup.

### 3. Triage Agent

See `/triage_agent/README.md` and `/triage_agent/medical-triage/README.md`

### 4. Insurance Agent

See `/insurance-agent/README.md`

## Observability

The observability stack includes:

- **OpenTelemetry Collector** - Telemetry ingestion
- **ClickHouse** - Time-series database for traces and metrics
- **Metrics Computation Engine (MCE)** - Computes 17+ metrics including:
  - Custom metrics: TokenUsage, AgentErrorCount, ToolCallCount, NumberActiveAgents
  - Judge metrics: GoalSuccessRate, Groundedness, Consistency, ContextPreservation, etc.
  - Confidence metrics: LLMAverageConfidence, LLMMaximumConfidence, LLMMinimumConfidence
- **Grafana** - Dashboards for visualization

Metrics are automatically collected by the observe SDK. See `/common/agntcy/observe/deploy/` for setup and configuration.

## Key Technologies

- **MCP (Model Context Protocol)** - Agent communication standard
- **Infermedica API** - Medical symptom analysis
- **Infinitus API** - Insurance benefits verification
- **OpenTelemetry** - Distributed tracing and observability
- **ClickHouse** - Analytics database
- **Grafana** - Monitoring dashboards
- **Docker** - Containerization and orchestration
- **Identity** - Task-based Access Control and enforcing policies on agent communication

## Agent Communication

Agents communicate with each other, enabling:
- Model Context Protocol (MCP) tool calls
- Seamless agent-to-agent (A2A) interactions
- Standardized HTTP-based APIs
- Identity management and authentication
- Distributed tracing across agent boundaries
