# Agent Gateway Protocol (AGP) Architecture

## Overview

The Agent Gateway Protocol (AGP) (https://github.com/agntcy/agp) provides a standardized architecture for building distributed agent applications. It enables seamless communication between client applications and remote agent services through a gateway intermediary, allowing for scalable, secure, and flexible AI agent deployments.

```
Client <-----> Gateway <----> Server
```

This architecture creates a clear separation of concerns:

- **Client**: Manages the user interface and agent workflow
- **Gateway**: Handles message routing and protocol conversion
- **Server**: Processes agent requests and executes AI logic

The AGP architecture is ideal for scenarios where agent processing needs to be:
- Offloaded to specialized servers
- Distributed across multiple services
- Isolated for security or performance reasons
- Scaled independently of client applications

## Components

### 1. Client (Remote Agent Client)

The client component is typically built using Langgraph and is responsible for:

- Initializing connections to the gateway
- Creating and managing the state graph for handling requests
- Processing user inputs and displaying agent outputs
- Managing message flow and state transitions

**Key Components:**

```python
# Example client-side graph setup
from langgraph.graph import StateGraph
from typing import TypedDict, List

# Define state structure
class GraphState(TypedDict):
    messages: List[dict]
    session_id: str

# Create nodes for the graph
def node_remote_agp(state: GraphState) -> GraphState:
    """Node that handles communication with remote agent via AGP"""
    # Implementation details for sending/receiving through gateway
    return updated_state

# Build the graph
def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("remote_agent", node_remote_agp)
    # Additional graph configuration
    return graph.compile()
```

### 2. Gateway (Message Broker)

The gateway acts as an intermediary between clients and servers:

- Runs as a service (typically on port 46357)
- Handles message routing and protocol conversion
- Manages connections and message queues
- Provides a secure communication channel between components

**Key Features:**

- **GatewayContainer**: Manages gateway connections and message routing
- **Protocol Conversion**: Translates between different messaging formats
- **Connection Management**: Handles client and server connections
- **Message Queuing**: Ensures reliable message delivery

### 3. Server (Remote Agent Server)

The server component is typically built using FastAPI and is responsible for:

- Processing requests from the gateway
- Implementing the remote agent logic
- Managing agent state and context
- Returning responses to the client via the gateway

**Key Components:**

```python
# Example server implementation using FastAPI
from fastapi import FastAPI, Depends
from pydantic import BaseModel

app = FastAPI()

class AgentRequest(BaseModel):
    messages: List[dict]
    session_id: str

@app.post("/agent/process")
async def process_agent_request(request: AgentRequest):
    # Process the agent request
    # Generate response using AI models
    return {"response": generated_response}
```

## Message Flow

### 1. Client Initiates Request

```
Client -> Gateway
```

The client creates a request payload and sends it to the gateway:

```python
# Client-side code
payload = {
    "messages": [{"role": "user", "content": "Hello, agent!"}],
    "session_id": "unique-session-id"
}

# Send via GatewayContainer
response = await gateway_container.send_and_receive(payload)
```

### 2. Gateway Handles Routing

```
Gateway -> Server
```

The gateway:
- Receives the client message
- Routes it to the appropriate server endpoint
- Manages any protocol conversions
- Handles authentication and security

### 3. Server Processes Request

```
Server -> Gateway -> Client
```

The server:
- Processes the request through FastAPI routes
- Executes agent logic using AI models
- Returns the response through the gateway
- May include streaming responses for real-time interaction

## Security

The AGP architecture includes several security features:

### Connection Security

- TLS/SSL support for encrypted communication
- Configurable insecure connections for development
- Authentication mechanisms for client and server validation

### Data Protection

- Environment variables for sensitive configuration
- CORS protection for web-based clients
- Secure credential management

### Request Validation

- Custom route ID generation for request tracking
- Input validation and sanitization
- Rate limiting and throttling capabilities

## Getting Started

Follow these steps to set up and run an AGP-based application:

### Prerequisites

1. Python 3.12 or higher
2. OpenAI API key (or other LLM provider)
3. Docker (recommended for containerized deployment)

### Installation

1. Set up the client:

```bash
# Navigate to client directory
cd client
# Install dependencies
pip install -r requirements.txt
```

2. Configure environment:

```bash
# Create .env file with your API keys
echo "OPENAI_API_KEY=your_key_here" > .env
```

3. Build and run the gateway:

```bash
# Using Docker
docker compose up gateway
```

4. Start the server:

```bash
# Using Docker
docker compose up server
```

5. Run the client application:

```bash
# Start the client
python client/agp.py
```

### Development with Langgraph Studio

For development with Langgraph Studio:

1. Start the gateway and server components
2. Navigate to the client_studio directory
3. Execute Langgraph development server:

```bash
langgraph dev
```

### Customizing Your Agent

To customize your agent's behavior:

1. Modify the server-side agent implementation
2. Update the client-side graph to handle new capabilities
3. Test your changes with example conversations
4. Deploy updates to your production environment

## Conclusion

The Agent Gateway Protocol architecture provides a flexible foundation for building distributed agent applications. By separating concerns between client, gateway, and server components, it enables scalable and secure agent deployments that can evolve with your application needs.

For more information, refer to the implementation details in the codebase and explore the example applications provided in this repository.

