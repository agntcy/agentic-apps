# Healthcare Voice + A2A + MCP Agent - Observability README

This document outlines the observability implementation for the Healthcare Voice + A2A + MCP Agent, focusing on how the `ioa_observe.sdk` is used to instrument and monitor the agent's operations, including interactions with A2A and MCP services.

## Table of Contents
1.  [Introduction](#1-introduction)
2.  [Project Structure](#2-project-structure)
3.  [Module Descriptions](#3-module-descriptions)
4.  [Observability Setup](#4-observability-setup)
5.  [Agent, Workflow, Task, and Tool Instrumentation](#5-agent-workflow-task-and-tool-instrumentation)
    *   [`@agent` Decorator](#agent-decorator)
    *   [`@workflow` Decorator](#workflow-decorator)
    *   [`@task` Decorator](#task-decorator)
    *   [`@tool` Decorator](#tool-decorator)
6.  [A2A Protocol Observability](#6-a2a-protocol-observability)
7.  [Metrics](#7-metrics)
8.  [Session Tracing](#8-session-tracing)
9.  [Configuration](#9-configuration)

---

## 1. Introduction

The Healthcare Voice + A2A + MCP Agent is designed to automate healthcare appointment scheduling, integrating with external services for medical assessment (via A2A) and insurance verification (via MCP). To ensure robust monitoring, debugging, and performance analysis, the agent leverages the `ioa_observe.sdk` for comprehensive observability. This includes tracing, metrics, and structured logging across its various components and external interactions.

---

## 2. Project Structure

The agent follows a modular architecture with clear separation of concerns:

```
voice-agent/agntcy/
├── main.py                          # Entry point and initialization
├── models/
│   ├── __init__.py
│   └── session.py                   # Session management and persistence
├── services/
│   ├── __init__.py
│   ├── audio_service.py             # Audio I/O (TTS/STT)
│   ├── a2a_client.py                # A2A protocol client
│   ├── llm_client.py                # LLM processing client
│   └── insurance_client.py          # Insurance MCP client
├── agent/
│   ├── __init__.py
│   └── healthcare_agent.py          # Main agent orchestrator

```

---

## 3. Module Descriptions

### Configuration Module (`config/`)
*   **`settings.py`**: Contains the `load_env()` function that loads environment variables from a `.env` file using `python-dotenv`. This module has no business logic and is solely responsible for environment setup.

### Models Module (`models/`)
*   **`task_state.py`**: Defines the `TaskState` enum that represents all possible states of an A2A task according to the A2A specification (submitted, working, input-required, completed, canceled, failed, rejected, auth-required, unknown).
*   **`session.py`**: Implements the `Session` class that manages conversation state, logs all interactions, and persists complete session data to JSON files in the `sessions/` directory. Each session has a unique ID, tracks triage state, and maintains a complete conversation log with timestamps.

### Services Module (`services/`)
*   **`audio_service.py`**: Implements the `AudioSystem` class that handles speech recognition (using Google Speech API) and text-to-speech (using gTTS and pygame). Automatically falls back to console I/O if audio libraries are unavailable. Methods `listen()` and `speak()` are decorated with `@tool` for observability.
*   **`a2a_client.py`**: Implements the `A2AClient` class for A2A protocol communication. Handles agent discovery, message sending, and task tracking. Uses `A2AInstrumentor` for automatic HTTP instrumentation and includes custom `_timed_request()` method for detailed logging.
*   **`llm_client.py`**: Implements the `LLMClient` class for natural language processing. Sends prompts to an LLM endpoint and parses JSON responses for intent extraction. The `process()` method is decorated with `@tool`.
*   **`insurance_client.py`**: Implements the `InsuranceClient` class for MCP-based insurance operations. Provides `discovery()` for finding insurance information and `eligibility()` for benefits verification. Both methods are decorated with `@tool` and include automatic date/name formatting.

### Agent Module (`agent/`)
*   **`healthcare_agent.py`**: Implements the `HealthcareAgent` class decorated with `@agent`. This is the main orchestrator that coordinates all services, manages the conversation loop, and implements triage workflows decorated with `@workflow`. Handles turn-based interaction, error recovery, and session persistence.

### Entry Point (`main.py`)
*   **`main.py`**: Application entry point that initializes observability, validates configuration, creates the `HealthcareAgent` instance, and starts the conversation loop. Handles graceful shutdown on keyboard interrupt.

---

## 4. Observability Setup

The core observability initialization happens in the `run_agent` function in `main.py` and within the `A2AClient` constructor in `services/a2a_client.py`:

*   **Global Initialization** (`main.py`):
    ```python
    from agntcy.observe.observe_config import initialize_observability
    # ...
    def run_agent():
        # ...
        service_name = "Healthcare_Voice_Agent"
        initialize_observability(service_name)
    ```
    This call sets up the foundational observability configuration for the entire agent, typically configuring OpenTelemetry exporters and resource attributes. 
    For observe_config refer https://github.com/techm-2025/customer-support/tree/main/agentic-healthcare-booking-app/common/agntcy/observe/observe_config.py

*   **A2A Client Specific Initialization** (`services/a2a_client.py`):
    ```python
    from ioa_observe.sdk import Observe
    from ioa_observe.sdk.instrumentations.a2a import A2AInstrumentor
    # ...
    class A2AClient:
        def __init__(self):
            # ...
            api_endpoint = os.getenv('OTLP_ENDPOINT', 'http://localhost:4318')
            Observe.init("A2A_Client", api_endpoint=api_endpoint)
            A2AInstrumentor().instrument()
    ```
    The `A2AClient` explicitly initializes `Observe` for its own operations, specifying a service name "A2A_Client" and an OTLP endpoint. Crucially, `A2AInstrumentor().instrument()` is called here to automatically instrument HTTP requests made by the A2A client, ensuring that A2A protocol interactions are captured as spans in traces.

---

## 5. Agent, Workflow, Task, and Tool Instrumentation

The `ioa_observe.sdk` provides decorators to automatically instrument key components of the agent's logic, turning them into observable units (spans in traces).

### `@agent` Decorator
The main agent class `HealthcareAgent` in `agent/healthcare_agent.py` is decorated with `@agent`. This marks `HealthcareAgent` as a top-level observable entity, making its lifecycle and high-level operations traceable.

```python
@agent(name="healthcare_agent", description="healthcare voice agent", version="1.0.0", protocol="A2A")
class HealthcareAgent:
    # ...
```
This decorator captures the instantiation and execution of the agent, providing metadata like its name, description, version, and the protocol it primarily uses.

### `@workflow` Decorator
Workflows represent a sequence of related operations or a significant business process within the agent. The `_start_integrated_triage` and `_handle_triage_conversation` methods in `agent/healthcare_agent.py` are decorated as workflows:

```python
@workflow(name="integrated_triage_workflow")
async def _start_integrated_triage(self):
    # ...

@workflow(name="triage_conversational_flow")
async def _handle_triage_conversation(self, user_input):
    # ...
```
These decorators ensure that the entire execution flow of starting a triage or handling a triage conversation is captured as a distinct workflow span, allowing for end-to-end tracing of these complex interactions.

### `@task` Decorator
The `@task` decorator is conceptually similar to `@workflow` but typically for smaller, more granular units of work within a workflow. The A2A protocol itself defines "tasks," and the `A2AInstrumentor` will likely create spans for these A2A tasks.

### `@tool` Decorator
Tools represent external capabilities or specific functions the agent can invoke. Several methods across different service modules are decorated as `@tool`:

*   **Audio System Tools** (`services/audio_service.py`):
    ```python
    @tool(name="listening_tool")
    async def listen(self, timeout=5):
        # ...
    @tool(name="speaking_tool")
    async def speak(self, text):
        # ...
    ```
    These capture the agent's interactions with the audio input/output, showing when the agent is listening or speaking.

*   **A2A Message Tool** (`services/a2a_client.py`):
    ```python
    @tool(name="a2a_message_tool")
    async def send_message(self, message_parts, task_id=None, context_id=None):
        # ...
    ```
    This instruments the `send_message` method of the `A2AClient`, making each message sent to the A2A service a traceable tool call.

*   **LLM Tool** (`services/llm_client.py`):
    ```python
    @tool(name="llm_tool")
    async def process(self, user_input, session):
        # ...
    ```
    This instruments calls to the Large Language Model, tracking the prompts sent and responses received.

*   **Insurance Client Tools (MCP Protocol)** (`services/insurance_client.py`):
    ```python
    @tool(name="insurance_discovery_tool")
    async def discovery(self, name, dob, state):
        # ...
    @tool(name="insurance_eligibility_tool")
    async def eligibility(self, name, dob, subscriber_id, payer_name, provider_name):
        # ...
    ```
    These tools instrument the interactions with the Insurance Client, which uses the MCP (Managed Care Protocol) for discovery and eligibility checks. Each call to these methods will be captured as a tool invocation, providing visibility into the MCP service interactions.

---

## 6. A2A Protocol Observability

The `A2AClient` in `services/a2a_client.py` is specifically designed for A2A protocol interactions and includes dedicated instrumentation:

```python
from ioa_observe.sdk.instrumentations.a2a import A2AInstrumentor
# ...
class A2AClient:
    def __init__(self):
        # ...
        A2AInstrumentor().instrument()
```
The `A2AInstrumentor().instrument()` call is crucial. It automatically instruments HTTP requests made by the `requests` library (used by `A2AClient` for `_timed_request`), enriching them with A2A-specific context. This means that when the `A2AClient` sends messages or performs discovery, the underlying HTTP calls are automatically traced, and their spans are linked to the A2A task and message IDs, providing a clear view of the A2A communication flow within the overall trace.

---

## 7. Metrics

The agent also records specific metrics related to its availability and activity in `agent/healthcare_agent.py`:

```python
from ioa_observe.sdk.metrics.agents.availability import agent_availability
# ...
class HealthcareAgent:
    async def start(self):
        # ...
        agent_availability.record_agent_heartbeat("healthcare_voice_agent")
        # ...
        if turn %5 ==0:
            agent_availability.record_agent_heartbeat("healthcare_voice_agent")
        # ...
        agent_availability.record_agent_activity("healthcare_voice_agent", success=False)
        # ...
        agent_availability.record_agent_activity("healthcare_voice_agent", success=True)
```
*   `agent_availability.record_agent_heartbeat("healthcare_voice_agent")`: This metric indicates that the agent is alive and operational. It's recorded at startup and periodically during the conversation (every 5 turns).
*   `agent_availability.record_agent_activity("healthcare_voice_agent", success=True/False)`: This metric tracks the agent's activity and whether a specific interaction was successful or not. It's used after processing user input to indicate successful processing or failures (e.g., unclear audio).

---

## 8. Session Tracing

The `session_start()` function is used within the `A2AClient.send_message` method in `services/a2a_client.py` to mark the beginning of a new session or a significant interaction within a trace.

```python
from ioa_observe.sdk.tracing import session_start
# ...
class A2AClient:
    async def send_message(self, message_parts, task_id=None, context_id=None):
        # ...
        session_start()
        # ...
```
This helps in organizing traces, especially in long-running conversations, by explicitly denoting the start of a new logical session or interaction within the tracing system.

---

## 9. Configuration

### Environment Variables
The agent requires the following environment variables (loaded via `config/settings.py`):

```bash
# LLM Configuration
JWT_TOKEN=your_jwt_token
ENDPOINT_URL=your_llm_endpoint_url
PROJECT_ID=your_project_id
CONNECTION_ID=your_connection_id

# Insurance MCP Configuration
MCP_URL=your_mcp_server_url
X_INF_API_KEY=your_insurance_api_key

# A2A Protocol Configuration
A2A_SERVICE_URL=http://localhost:8887
A2A_MESSAGE_URL=http://localhost:8887
A2A_API_KEY=your_a2a_api_key

# Observability
OTLP_ENDPOINT=http://localhost:4318
```

### Configuration Validation
The `main.py` entry point validates all required environment variables before starting the agent:
```python
jwt_required = ['JWT_TOKEN', 'ENDPOINT_URL', 'PROJECT_ID', 'CONNECTION_ID']
insurance_required = ['MCP_URL', 'X_INF_API_KEY']
a2a_required = ['A2A_SERVICE_URL', 'A2A_MESSAGE_URL', 'A2A_API_KEY']
```
If any required variables are missing, the agent will print an error message and exit gracefully.

---

## Installation & Setup

### Prerequisites
- Python 3.8 or higher
- macOS, Linux, or Windows
- Microphone access (for voice features)

### Quick Start
```bash
# Clone and navigate to project
cd healthcare-booking_app

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with your configuration
cp .env.example .env  # Edit with your credentials

# Run the agent
python main.py
```

---


## Support

For issues or questions, please open troubleshooting documentation in the repository 
https://github.com/techm-2025/customer-support/tree/main/agentic-healthcare-booking-app/documentation/troubleshooting