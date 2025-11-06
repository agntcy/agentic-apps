# A2A Medical Triage Service

A standalone Agent-to-Agent (A2A) protocol service that provides medical symptom triage and assessment capabilities using AI-powered clinical protocols with AGNTCY Identity Task-Based Access Control (TBAC) integration.

## Overview

This service implements the A2A protocol specification to enable secure, standardized communication between AI agents for medical triage operations. It acts as a specialized medical assessment agent that can be discovered and invoked by other agents in an A2A ecosystem.

## Architecture

### Core Components

1. **A2A Protocol Implementation**: Full JSON-RPC 2.0 based Agent-to-Agent protocol support
2. **TBAC Authorization**: Bidirectional Task-Based Access Control for secure agent communication
3. **External Triage API Integration**: Connects to Infermedica's medical triage APIs for assessment
4. **Observability**: Built-in instrumentation with IOA Observe SDK
5. **Task Management**: Stateful conversation and task tracking

### Technical Stack

- **Framework**: Flask (Python web framework)
- **Protocol**: JSON-RPC 2.0 over HTTP
- **Security**: TBAC (Task-Based Access Control) + Shared Key Authentication
- **Observability**: IOA Observe SDK with decorators
- **External Integration**: RESTful API client for medical triage service

## Features

### A2A Protocol Compliance

- **Agent Discovery Card** (`.well-known/agent-card.json`): Standardized agent capability declaration
- **JSON-RPC 2.0 Endpoints**: Full protocol implementation with proper error handling
- **Task State Management**: Supports all A2A task states (SUBMITTED, WORKING, INPUT_REQUIRED, COMPLETED, FAILED, etc.)
- **Message History**: Complete conversation tracking with role-based message storage
- **Artifact Support**: Structured data output for triage results

### Security Features

#### TBAC (Task-Based Access Control)
- Bidirectional authorization between agents
- Client-to-A2A service authorization flow
- A2A-to-client authorization flow
- Token-based authentication using IdentityServiceSDK

#### Shared Key Authentication
- Additional layer of security via `X-Shared-Key` header
- Required for all protected endpoints

### Medical Triage Capabilities

- **Demographic Extraction**: Automatic parsing of age and sex from natural language
- **Session Management**: Stateful triage sessions with external API
- **Progressive Assessment**: Multi-turn conversation support for symptom collection
- **Urgency Classification**: Returns urgency levels and recommended doctor types
- **Comprehensive Results**: Structured artifacts with assessment outcomes

## API Endpoints

### Public Endpoints

#### `GET /.well-known/agent-card.json`
Returns the agent discovery card with capabilities, skills, and metadata.

#### `GET /docs`
Basic API documentation endpoint.

### Protected Endpoints (Require Authentication)

#### `POST /` (Main JSON-RPC Endpoint)
Handles all A2A protocol methods:

- **`message/send`**: Process incoming messages and manage triage conversations
- **`tasks/get`**: Retrieve task details and history
- **`tasks/cancel`**: Cancel active tasks

#### `GET /health`
Health check endpoint with TBAC status and active task count.

## Message Flow

### 1. Initial Message
```json
{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "message": {
      "parts": [{
        "kind": "text",
        "text": "I'm a 35 year old male with chest pain"
      }]
    }
  },
  "id": "msg-001"
}
```

### 2. Triage Session Creation
- Extracts demographics (age, sex)
- Creates new task with unique ID
- Initiates external triage API session
- Returns INPUT_REQUIRED state with follow-up questions

### 3. Conversation Loop
- Accepts user responses
- Sends to external triage API
- Tracks conversation history
- Continues until assessment complete

### 4. Completion
- Returns COMPLETED state
- Includes structured artifact with:
  - Urgency level
  - Recommended doctor type
  - Clinical notes
  - Assessment timestamp

## Task States

The service implements the full A2A task state machine:

- **SUBMITTED**: Initial task creation
- **WORKING**: Processing in progress
- **INPUT_REQUIRED**: Awaiting user response
- **COMPLETED**: Assessment finished successfully
- **FAILED**: Error during processing
- **CANCELED**: Task cancelled by request
- **REJECTED**: Task rejected (not implemented)
- **AUTH_REQUIRED**: Authorization needed

## Configuration

### Environment Variables

#### Required External API Configuration
```bash
TRIAGE_APP_ID=your_triage_app_id
TRIAGE_APP_KEY=your_triage_app_key
TRIAGE_INSTANCE_ID=your_instance_id
TRIAGE_TOKEN_URL=https://api.triage.example.com/oauth/token
TRIAGE_BASE_URL=https://api.triage.example.com/v1
```

#### TBAC Configuration
```bash
CLIENT_AGENT_API_KEY=client_agent_api_key
CLIENT_AGENT_ID=client_agent_id
A2A_SERVICE_API_KEY=a2a_service_api_key
A2A_SERVICE_ID=a2a_service_id
```

#### Security
```bash
SHARED_KEY=your_shared_secret_key
```

## Installation

### Prerequisites
- Python 3.8+
- pip package manager

### Setup

1. Clone the repository
```bash
git clone <repository_url>
cd infermedica
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Configure environment variables
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the service
```bash
python main.py
```

### Command Line Options
```bash
python main.py [options]

Options:
  --host HOST          Host to bind to (default: 0.0.0.0)
  --port PORT          Port to bind to (default: 8887)
  --debug              Enable debug mode
  --disable-tbac       Disable TBAC authorization
```

## Observability

The service includes comprehensive observability features:

### Decorators
- `@agent`: Service-level instrumentation
- `@workflow`: Workflow tracking (e.g., triage sessions)
- `@task`: Individual task monitoring
- `@tool`: Tool-level instrumentation (e.g., demographic extraction)

### Instrumentation
- A2A protocol instrumentation via `A2AInstrumentor`
- Request/response timing
- Error tracking and logging
- Task state transitions

## Error Handling

The service implements JSON-RPC 2.0 error codes:

- `-32600`: Invalid Request
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error
- `-32001`: Task not found (custom)
- `-32002`: Task cannot be continued/cancelled (custom)

## Security Considerations

1. **TBAC Authorization**: Ensures only authorized agents can communicate
2. **Shared Key**: Additional authentication layer for API access
3. **Input Validation**: All inputs are validated before processing
4. **Error Sanitization**: Sensitive information is not exposed in error messages
5. **Demographic Extraction**: Limited to age and sex only for privacy

## Integration Guide

### As a Client Agent

1. Obtain TBAC credentials from the identity service
2. Configure shared key for authentication
3. Discover service via agent card endpoint
4. Send messages using JSON-RPC protocol
5. Handle task states and continue conversations
6. Process completed assessment artifacts

### As a Service Provider

1. Deploy service with proper environment configuration
2. Register with identity service for TBAC
3. Configure external triage API credentials
4. Monitor health and observability endpoints
5. Scale horizontally as needed (stateless design)

## Response Structure

### Success Response
```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "result": {
    "id": "task-uuid",
    "status": {
      "state": "input-required",
      "timestamp": "2025-01-01T12:00:00Z"
    },
    "artifacts": [...],
    "goto": "healthcare_voice_agent",
    "success": true,
    "action": "triage_continuing"
  }
}
```

### Error Response
```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "error": {
    "code": -32603,
    "message": "Internal error",
    "data": {...}
  },
  "goto": "healthcare_voice_agent",
  "success": false,
  "error": true
}
```

## Contributing

Please ensure all contributions:
- Maintain A2A protocol compliance
- Include proper error handling
- Add appropriate observability decorators
- Follow existing code structure
- Include tests for new features

## Acknowledgments

- Built on the A2A (Agent-to-Agent) protocol specification
- Uses AGNTCY Observe SDK for observability
- Integrates with Infermedica's medical triage API
