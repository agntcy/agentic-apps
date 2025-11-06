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
    - `healthcare_agent.py` - voice-agent orchestrartor
  - **`models/`** 
    - `session.py` - session management and persistence
  - **`services/`**
    - `a2a_client.py` - A2A protocol client
    - `audio_service.py` - Audio input and output service
    - `insurance_client.py` - Insurance MCP client
    - `llm_client.py` - LLM processing client
  - `main.py` - voice-agent entry point and intialization
  - `README.md` - Detailed voice agent implementation along with identity and observe
  
- **`unit-tests/`** - Testing suite
  - `a2a_client.py` - Agent-to-agent communication test client
  - `http_client.py` - HTTP API test client

- **Core MCP Servers:**
  - `va_a2a_mcp.py` - Agent-to-agent,  Model Context Protocol clients with voice-agent communication
  - `va_http_mcp.py` - HTTP-based Medical triage, Model Context Protocol based Insurance clients with voice-agent communication

## Getting Started

Each component has its own README with detailed setup instructions:

1. **Insurance Agent** - See `/insurance-agent/README.md`
2. **Triage Agent** - See `/triage_agent/README.md` and `/triage_agent/medical-triage/README.md`
3. **Voice Agent** - See `/voice-agent/README.md`
4. **Observe Stack** - See `/triage_agent/infermedica/agntcy/observe_config/README.md`

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
