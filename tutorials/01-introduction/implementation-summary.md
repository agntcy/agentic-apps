# Implementing Agent Connect Protocol with Simple Agent Framework: A Summary

This document provides a comprehensive overview of how the tutorials in this repository demonstrate implementing the Agent Connect Protocol (ACP) using the Simple Agent Framework. It explains the key patterns, integration points, and best practices across the tutorials.

## The Complete Architecture

Across the tutorials, we've built a complete architecture for distributed agent communication:

```
┌───────────────────┐     ┌────────────────────┐     ┌────────────────────┐
│  CLIENT AGENT     │     │      GATEWAY       │     │  SERVER AGENT(S)   │
│                   │     │                    │     │                    │
│  ┌─────────────┐  │     │  ┌──────────────┐  │     │  ┌──────────────┐  │
│  │ Simple Agent │  │     │  │ Message      │  │     │  │ Simple Agent │  │
│  │ Framework    │◄─┼─────┼──┤ Router       │◄─┼─────┼──┤ Framework    │  │
│  └─────────────┘  │     │  └──────────────┘  │     │  └──────────────┘  │
│        │          │     │                    │     │        │           │
│  ┌─────────────┐  │     │                    │     │  ┌──────────────┐  │
│  │ ACP         │  │     │                    │     │  │ ACP          │  │
│  │ Tools       │  │     │                    │     │  │ Request      │  │
│  └─────────────┘  │     │                    │     │  │ Handlers     │  │
│                   │     │                    │     │  └──────────────┘  │
└───────────────────┘     └────────────────────┘     └────────────────────┘
```

## Key Components

### 1. Simple Agent Framework

The [Simple Agent Framework](https://github.com/rungalileo/simple-agent-framework) serves as the foundation for our implementation. Key aspects include:

- **Agent Class**: The base class for all agents, providing core functionality
- **Tools Registry**: Manages the tools available to each agent
- **State Management**: Handles agent state through the `AgentState` class
- **Prompt Templates**: Uses Jinja2 templates for generating system prompts
- **Logging**: Provides detailed logging through the `AgentLogger` class

### 2. Agent Connect Protocol (ACP)

The Agent Connect Protocol defines standards for agent communication:

- **Message Format**: Standardized format for requests and responses
- **Authentication**: Security mechanisms for agent access
- **Invocation Patterns**: How agents are called and responses retrieved
- **Capability Discovery**: How agents discover each other's capabilities
- **Error Handling**: Standardized error reporting

### 3. Integration Patterns

Our tutorials demonstrate several patterns for integrating Simple Agent Framework with ACP:

#### Pattern 1: Custom ACP Communication Tools

We extend agents with custom tools for ACP communication:

```python
class ACPCommunicationTool(BaseTool):
    name = "remote_agent_call"
    description = "Send a message to a remote agent and get a response"
    
    async def execute(self, agent_id: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        # Format request according to ACP standards
        # Send request through appropriate channel
        # Return response
```

#### Pattern 2: ACP Request Handlers

Server-side agents implement handlers for processing ACP requests:

```python
async def process_acp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
    # Extract relevant information from request
    # Process using agent capabilities
    # Return formatted ACP response
```

#### Pattern 3: Gateway Integration

Agents connect to gateways for message routing:

```python
# Configure gateway
gateway_container.set_config(endpoint=gateway_endpoint, insecure=insecure)

# Register agent with gateway
agent_container.register_agent("agent_id", message_handler)

# Connect to gateway
await gateway_container.connect_with_retry(agent_container=agent_container)
```

## Implementation Summary by Tutorial

### Tutorial 1: Introduction to ACP with Simple Agent Framework

- Introduces the Simple Agent Framework architecture
- Explains how it can be extended for ACP communication
- Demonstrates basic patterns for agent-to-agent communication
- Shows how to implement an echo agent with ACP support

### Tutorial 2: Building a Client Agent

- Implements a complete client agent using Simple Agent Framework
- Creates custom tools for ACP communication
- Uses prompt templates to guide the agent's behavior
- Demonstrates interactive agent usage for remote communication

### Tutorial 3: Implementing Server Agents

- Creates server-side agents that handle ACP requests
- Integrates with the AGP gateway for message routing
- Implements FastAPI endpoints for agent access
- Shows both direct API and gateway-based access methods

## Message Flow Across Components

The complete message flow in our architecture works as follows:

1. **User Input to Client Agent**:
   - User provides input to the client agent
   - Client agent updates its state with the user message
   - Client agent generates a system prompt using templates

2. **Client LLM Processing**:
   - LLM processes the user input with available tools
   - LLM may decide to use an ACP communication tool
   - Tool is executed to send a message to a remote agent

3. **Gateway Routing**:
   - ACP tool formats the request according to standards
   - Request is sent to the gateway
   - Gateway identifies the target server agent
   - Gateway forwards the request to the server agent

4. **Server Agent Processing**:
   - Server agent receives the request through its ACP handler
   - Server validates and processes the request
   - Server may use its own tools or LLM to generate a response
   - Server formats the response according to ACP standards

5. **Response Back to Client**:
   - Response is sent back through the gateway
   - Client's ACP tool receives and processes the response
   - Client LLM generates a final response incorporating the remote agent's answer
   - Final response is presented to the user

## Key Benefits of This Approach

Implementing ACP with the Simple Agent Framework provides several benefits:

1. **Modularity**: Each agent is a self-contained module with well-defined interfaces
2. **Extensibility**: New capabilities can be added via tools and template modifications
3. **Distributed Processing**: Computational load can be distributed across multiple agents
4. **Specialization**: Agents can specialize in specific domains or tasks
5. **Scalability**: The architecture can scale by adding more agents and gateways
6. **Standardization**: ACP provides a common language for agent communication

## Advanced Patterns and Extensions

Our tutorials introduce these concepts, which can be extended further:

### Multi-Agent Workflows

Complex workflows can be built by chaining multiple specialized agents:

```python
async def complex_workflow(query: str):
    # First, process with research agent
    research_result = await client.send_acp_message("research_agent", query)
    
    # Then, send to analysis agent with research results
    analysis_result = await client.send_acp_message(
        "analysis_agent", 
        f"Analyze this research: {research_result['response']}"
    )
    
    # Finally, generate a report with the writing agent
    report = await client.send_acp_message(
        "writing_agent",
        f"Create a report based on this analysis: {analysis_result['response']}"
    )
    
    return report
```

### State Management Across Conversations

For agents that need to maintain state across multiple interactions:

```python
# In server agent
self.sessions = {}  # session_id -> state

async def process_with_state(self, request):
    session_id = request.get("metadata", {}).get("session_id")
    if session_id not in self.sessions:
        self.sessions[session_id] = {"history": []}
    
    # Update and use session state
    # ...
```

### Capability Discovery

For dynamic agent discovery and capability exploration:

```python
async def discover_agent_capabilities(agent_id: str):
    response = await client.send_acp_message(
        agent_id,
        "What capabilities do you have?",
        {"request_type": "capability_discovery"}
    )
    return response["capabilities"]
```

## Conclusion

The combination of the Simple Agent Framework and Agent Connect Protocol provides a powerful foundation for building distributed agent systems. By following the patterns demonstrated in these tutorials, you can create sophisticated multi-agent applications with:

- Well-defined agent boundaries and responsibilities
- Standardized communication protocols
- Flexible tool-based capabilities
- Scalable distributed architecture

For further exploration, consider:
1. Adding more specialized agents to your ecosystem
2. Implementing more advanced ACP features like streaming responses
3. Building authentication and authorization mechanisms
4. Creating agent marketplaces and discovery services

These tutorials provide a starting point for your journey into building the Internet of Agents using open standards and flexible frameworks. 