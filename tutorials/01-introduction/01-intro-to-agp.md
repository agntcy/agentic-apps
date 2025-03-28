# Introduction to Agent Connect Protocol with Simple Agent Framework

Welcome to the first tutorial in our series on implementing the Agent Connect Protocol (ACP) using the Simple Agent Framework. In this tutorial, we'll explore how to build agents that can communicate with each other using standardized protocols.

## Understanding the Simple Agent Framework

The [Simple Agent Framework](https://github.com/rungalileo/simple-agent-framework) provides a flexible foundation for building AI agents with tool-based capabilities. Each agent in this framework:

* Has its own set of tools
* Manages its own state
* Has its own prompt templates
* Can be configured via environment variables or code
* Supports advanced logging with GalileoLogger

This framework gives us a solid starting point for implementing agents that can communicate via the Agent Connect Protocol.

## Extending Agents for Distributed Communication

While traditional agent frameworks (including the Simple Agent Framework) excel at building standalone agents, modern applications often require agents to communicate across different services, frameworks, and environments. This is where the Agent Connect Protocol (ACP) comes in.

ACP defines standards for enabling agents to:
1. Discover each other's capabilities
2. Communicate using a common message format
3. Invoke actions on remote agents
4. Handle authentication and authorization
5. Manage streaming and asynchronous responses

### The Agent Gateway Protocol (AGP) Pattern

One common pattern for implementing ACP is the Agent Gateway Protocol (AGP), which follows a three-component architecture:

```
Client <-----> Gateway <----> Server
```

This pattern helps separate concerns and enables distributed agent communication:

1. **Client**: The application that interacts with users and sends requests to agents
2. **Gateway**: A message broker that handles routing, protocol conversion, and connections
3. **Server**: The agent service that processes requests and executes AI logic

## Implementing ACP with Simple Agent Framework

Let's explore how we can extend the Simple Agent Framework to implement ACP-compatible agents. We'll do this by:

1. Creating standard agent classes using the framework
2. Adding communication tools to enable agent-to-agent interaction
3. Implementing protocol handlers for ACP compatibility

### Step 1: Setting Up a Basic Agent

First, let's look at how to create a basic agent using the Simple Agent Framework:

```python
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from agent_framework.agent import Agent
from agent_framework.state import AgentState
from agent_framework.config import AgentConfiguration
from agent_framework.factory import AgentFactory

class BasicAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = AgentState()
        
        # Set up template environment
        template_dir = Path(__file__).parent / "templates"
        self.template_env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Register tools
        self._register_tools()
    
    def _register_tools(self) -> None:
        """Register agent-specific tools"""
        # We'll add communication tools here later
        pass

# Load configuration and create the agent
config = AgentConfiguration.from_env(required_keys=["openai"])
factory = AgentFactory(config)
agent = factory.create_agent(agent_class=BasicAgent, agent_id="basic_agent")
```

### Step 2: Adding Communication Tools

Now, let's extend our agent with tools that enable it to communicate with other agents via ACP:

```python
from agent_framework.tools.base import BaseTool
from pydantic import BaseModel
from typing import Dict, Any, Optional

class SendMessageInput(BaseModel):
    agent_id: str
    message: str
    metadata: Optional[Dict[str, Any]] = None

class SendMessageTool(BaseTool):
    name = "send_message"
    description = "Sends a message to another agent"
    tags = ["communication", "acp"]
    input_schema = SendMessageInput.model_json_schema()
    
    async def execute(self, agent_id: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Implementation for sending messages to other agents via ACP
        # This is where we'd integrate with AGP or other ACP implementation
        
        # For now, we'll use a simple placeholder
        print(f"Sending message to agent {agent_id}: {message}")
        
        # In a real implementation, we would:
        # 1. Format the message according to ACP standards
        # 2. Send it through the appropriate channel (e.g., AGP gateway)
        # 3. Wait for and parse the response
        
        return {"status": "sent", "agent_id": agent_id}
```

### Step 3: Implementing Protocol Handlers

To fully support ACP, we need to add protocol handlers that manage the communication details:

```python
class ACPHandler:
    """Handles Agent Connect Protocol communication details"""
    
    def __init__(self, endpoint: str = "http://localhost:46357", insecure: bool = False):
        self.endpoint = endpoint
        self.insecure = insecure
        # Additional configuration for ACP communication
        
    async def send_request(self, agent_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to a remote agent using ACP"""
        # Implementation details for ACP communication
        # In a real implementation, this would connect to a gateway or directly to other agents
        
        # Placeholder implementation
        return {"status": "received", "message": "This is a response from the remote agent"}
        
    async def receive_request(self) -> Dict[str, Any]:
        """Listen for incoming requests from other agents"""
        # Implementation for receiving and parsing ACP requests
        pass
```

### Integrating with a Gateway

For distributed agent applications, we often need to integrate with a message routing gateway. Here's how we could extend our agent to connect to an AGP gateway:

```python
from agent_framework.utils.logging import AgentLogger

class ACPAgent(BasicAgent):
    """Agent with ACP communication capabilities"""
    
    def __init__(self, *args, gateway_endpoint: str = "http://localhost:46357", **kwargs):
        super().__init__(*args, **kwargs)
        self.acp_handler = ACPHandler(endpoint=gateway_endpoint)
        self.logger = AgentLogger(agent_id=self.agent_id)
        
    def _register_tools(self) -> None:
        """Register ACP communication tools"""
        self.tool_registry.register(
            metadata=SendMessageTool.get_metadata(),
            implementation=SendMessageTool
        )
        
        # Add more ACP-specific tools as needed
        
    async def handle_acp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming ACP request"""
        # Extract the relevant information from the request
        messages = request.get("input", {}).get("messages", [])
        
        # Process the request using our agent's capabilities
        # For a simple agent, we might just generate a response using the LLM
        response = await self._process_messages(messages)
        
        # Format the response according to ACP standards
        return {
            "output": {
                "messages": [
                    {"role": "assistant", "content": response}
                ]
            }
        }
        
    async def send_acp_message(self, agent_id: str, message: str) -> Dict[str, Any]:
        """Send a message to another agent using ACP"""
        payload = {
            "agent_id": agent_id,
            "input": {
                "messages": [
                    {"role": "user", "content": message}
                ]
            },
            "metadata": {"sender": self.agent_id}
        }
        
        return await self.acp_handler.send_request(agent_id, payload)
```

## Agent Gateway Protocol (AGP) in Detail

Now that we understand how to extend a Simple Agent Framework agent with ACP capabilities, let's take a closer look at how the Agent Gateway Protocol (AGP) works as a specific implementation of ACP.

### AGP Message Flow

The AGP architecture facilitates communication between agents as follows:

1. **Client Initiates Request**:
   - A client agent creates a request payload
   - The client sends the request to the gateway

2. **Gateway Routes Message**:
   - Gateway receives the client message
   - Gateway determines which server agent should handle the request
   - Gateway forwards the message to the appropriate server

3. **Server Processes Request**:
   - Server agent receives the message from the gateway
   - Server agent processes the request and generates a response
   - Server agent sends the response back through the gateway

4. **Client Receives Response**:
   - Gateway forwards the server's response to the client agent
   - Client agent processes and uses the response

This flow can operate in different modes:
- **Synchronous**: Client waits for a complete response
- **Asynchronous**: Client receives a reference to check for results later
- **Streaming**: Server sends partial results as they become available

### Using the Simple Agent Framework with AGP

To connect a Simple Agent Framework agent to an AGP gateway, we can implement a specialized tool:

```python
class AGPCommunicationTool(BaseTool):
    name = "agp_communicate"
    description = "Communicates with remote agents via AGP gateway"
    tags = ["communication", "agp", "acp"]
    
    def __init__(self, gateway_endpoint: str, insecure: bool = False):
        self.gateway_endpoint = gateway_endpoint
        self.insecure = insecure
        # Initialize connection to gateway
        
    async def execute(self, agent_id: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Format the request according to AGP standards
        payload = {
            "agent_id": agent_id,
            "input": {
                "messages": [
                    {"role": "user", "content": message}
                ]
            },
            "metadata": metadata or {}
        }
        
        # Send the request to the gateway
        # In a real implementation, this would use the appropriate AGP client library
        
        # Placeholder for response handling
        return {"status": "success", "response": "Response from remote agent"}
```

## Setting Up Your Environment

To get started with developing ACP-compatible agents using the Simple Agent Framework:

1. **Install the Framework**:
   ```bash
   pip install git+https://github.com/rungalileo/simple-agent-framework.git
   ```

2. **Set Up Environment Variables**:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   GALILEO_API_KEY=your_galileo_api_key_here  # For logging
   ```

3. **Install Gateway Dependencies** (if using AGP):
   ```bash
   pip install agp-api
   ```

4. **Launch a Gateway** (for AGP implementation):
   ```bash
   docker run -p 46357:46357 ghcr.io/agntcy/agp/gw:0.3.6
   ```

## Practical Example: Echo Agent

Let's implement a simple echo agent that communicates via ACP:

```python
from agent_framework.agent import Agent
from agent_framework.state import AgentState
from agent_framework.config import AgentConfiguration
from agent_framework.factory import AgentFactory
from typing import Dict, Any, List

class EchoAgent(Agent):
    """A simple agent that echoes back messages received via ACP"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = AgentState()
    
    async def handle_acp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process an ACP request by echoing back the message"""
        # Extract messages from the request
        messages = request.get("input", {}).get("messages", [])
        
        # For an echo agent, we just take the last message and echo it back
        last_message = messages[-1] if messages else {"content": "No message received"}
        content = last_message.get("content", "")
        
        # Return the echoed response
        return {
            "output": {
                "messages": [
                    {"role": "assistant", "content": f"Echo: {content}"}
                ]
            }
        }

# Setup and run the agent
config = AgentConfiguration.from_env(required_keys=["openai"])
factory = AgentFactory(config)
echo_agent = factory.create_agent(agent_class=EchoAgent, agent_id="echo_agent")

# In a real application, you would set up an ACP server to receive requests
# For example, using FastAPI with AGP:
"""
from fastapi import FastAPI
from agp_api.gateway.gateway_container import GatewayContainer
from agp_api.agent.agent_container import AgentContainer

app = FastAPI()
gateway_container = GatewayContainer()
agent_container = AgentContainer()

# Configure and connect to gateway
gateway_container.set_config(
    endpoint="http://127.0.0.1:46357", 
    insecure=True
)
gateway_container.set_fastapi_app(app)

# Register the echo agent
agent_container.register_agent("echo_agent", echo_agent.handle_acp_request)

# Start the server
await gateway_container.start_server(agent_container=agent_container)
"""
```

## Relation to Agent Connect Protocol (ACP)

The Simple Agent Framework provides the building blocks for creating intelligent agents, while the Agent Connect Protocol (ACP) defines standards for how these agents communicate. By combining them, we can build distributed agent systems where:

1. Each agent is built with a solid foundation using the Simple Agent Framework
2. Agents can communicate seamlessly using ACP-compatible messages
3. Complex workflows can span multiple specialized agents
4. Agents can discover and use each other's capabilities

The ACP specification includes requirements for:
1. **Authentication and Authorization**: Secure access to agents
2. **Configuration**: How to configure remote agents
3. **Invocation**: Standardized way to invoke agents
4. **Output Retrieval**: Methods for getting results from agents
5. **Capabilities and Schema Definitions**: Mechanisms for discovering agent capabilities
6. **Error Definitions**: Standardized error handling

## Next Steps

In this tutorial, we've introduced the Simple Agent Framework and how it can be extended to support agent communication via the Agent Connect Protocol. We've explored:

1. The core components of the Simple Agent Framework
2. How to extend agents with ACP communication capabilities
3. The AGP pattern as an implementation of ACP
4. Setting up a basic echo agent that handles ACP requests

In the next tutorial, we'll build a complete client application that uses the Simple Agent Framework to communicate with remote agents via the Agent Gateway Protocol.

Ready to try it out? Check out the [Remote Agent example](../remote_agent_agp/README.md) in this repository to see a complete AGP implementation.

## Additional Resources

- [Simple Agent Framework](https://github.com/rungalileo/simple-agent-framework) - The flexible framework for building AI agents
- [AGP GitHub Repository](https://github.com/agntcy/agp) - Reference implementation of Agent Gateway Protocol
- [AGNTCY Documentation](https://docs.agntcy.org) - Comprehensive documentation on Agent Connect Protocol
- [Langgraph Documentation](https://langchain-ai.github.io/langgraph/) - For building advanced agent workflows 