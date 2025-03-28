# Implementing ACP Server Agents with Simple Agent Framework

In the [previous tutorial](02-first-agp-client.md), we built a client agent that can communicate with remote agents using the Agent Connect Protocol (ACP). Now, let's implement the server-side agents that can receive and respond to these requests.

## Server Agent Overview

In this tutorial, we'll create server-side agents with the following capabilities:
1. Receiving and validating ACP requests
2. Processing requests using the Simple Agent Framework
3. Executing agent logic with LLM and tools
4. Sending standardized responses back to clients
5. Handling concurrent requests and maintaining state

## Prerequisites

Before we begin, make sure you have:

1. Python 3.12+ installed
2. Installed the Simple Agent Framework: `pip install git+https://github.com/rungalileo/simple-agent-framework.git`
3. Installed server-side dependencies: `pip install fastapi uvicorn agp-api openai`
4. Set up necessary environment variables (OpenAI API key, etc.)
5. Completed or understood the client tutorial

## Step 1: Project Setup

Let's start by creating a new directory for our server agent implementation:

```bash
mkdir acp_server_agent
cd acp_server_agent
```

Create the following directory structure:

```
acp_server_agent/
├── __init__.py
├── main.py            # FastAPI server application
├── agents/            # Agent implementations
│   ├── __init__.py
│   └── echo_agent.py  # Simple echo agent
├── templates/         # Agent-specific templates
│   └── system.j2      # System prompt template
├── logging/           # Logging configuration
│   └── logger.py      # Custom logger
└── tools/             # Agent tools
    ├── __init__.py
    └── basic_tools.py # Basic agent tools
```

Create a `.env` file in the root directory:

```
OPENAI_API_KEY=your_openai_api_key_here
GALILEO_API_KEY=your_galileo_api_key_here  # For logging (optional)
AGP_GATEWAY_ENDPOINT=http://localhost:46357
AGP_GATEWAY_INSECURE=true
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

## Step 2: Implementing a Basic Tool

First, let's create some basic tools for our server agent. Create `tools/basic_tools.py`:

```python
# tools/basic_tools.py
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from agent_framework.tools.base import BaseTool

class CurrentTimeInput(BaseModel):
    """Input schema for current time tool"""
    timezone: Optional[str] = "UTC"

class CurrentTimeTool(BaseTool):
    """Tool for getting the current time"""
    name = "get_current_time"
    description = "Get the current date and time"
    tags = ["utility", "time"]
    input_schema = CurrentTimeInput.model_json_schema()
    
    async def execute(self, timezone: str = "UTC") -> Dict[str, Any]:
        """
        Execute the tool to get the current time.
        
        Args:
            timezone: The timezone to use (simplified for this example)
            
        Returns:
            Dict containing the current time information
        """
        now = datetime.now()
        return {
            "iso_format": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "timezone": timezone
        }

class EchoInput(BaseModel):
    """Input schema for echo tool"""
    message: str

class EchoTool(BaseTool):
    """Tool for echoing messages"""
    name = "echo"
    description = "Repeat back the given message"
    tags = ["utility", "echo"]
    input_schema = EchoInput.model_json_schema()
    
    async def execute(self, message: str) -> Dict[str, Any]:
        """
        Echo the given message back.
        
        Args:
            message: The message to echo
            
        Returns:
            Dict containing the original message and an echo
        """
        return {
            "original": message,
            "echo": f"Echo: {message}"
        }
```

Create the tools initialization file `tools/__init__.py`:

```python
# tools/__init__.py
from .basic_tools import CurrentTimeTool, EchoTool

__all__ = ["CurrentTimeTool", "EchoTool"]
```

## Step 3: Setting Up Logging

Create `logging/logger.py` for logging agent activities:

```python
# logging/logger.py
import logging
import json
from agent_framework.utils.logging import AgentLogger
from typing import Any, List, Optional, Dict

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

class ServerAgentLogger(AgentLogger):
    """Custom logger for server agents"""
    
    def __init__(self, agent_id: str):
        super().__init__(agent_id)
        self.logger = logging.getLogger(f"agent.{agent_id}")
        
    async def on_agent_start(self, input_data: Any) -> None:
        """Log when the agent starts processing a request"""
        self.logger.info(f"Agent {self.agent_id} starting processing request")
        
    async def on_tool_start(self, tool_name: str, tool_input: Dict[str, Any]) -> None:
        """Log when a tool execution starts"""
        self.logger.info(f"Agent {self.agent_id} executing tool: {tool_name}")
        
    async def on_tool_end(self, tool_name: str, output: Any) -> None:
        """Log when a tool execution completes"""
        self.logger.info(f"Agent {self.agent_id} completed tool: {tool_name}")
        
    async def on_tool_error(self, tool_name: str, error: Exception) -> None:
        """Log when a tool execution encounters an error"""
        self.logger.error(f"Agent {self.agent_id} tool error in {tool_name}: {error}")
        
    async def on_agent_end(self, output: Any) -> None:
        """Log when the agent completes processing"""
        self.logger.info(f"Agent {self.agent_id} completed processing request")
```

## Step 4: Creating the Echo Agent

Now, let's implement a simple echo agent. Create `agents/echo_agent.py`:

```python
# agents/echo_agent.py
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader

from agent_framework.agent import Agent
from agent_framework.state import AgentState
from agent_framework.utils.llm import OpenAIChat
from logging.logger import ServerAgentLogger
from tools import CurrentTimeTool, EchoTool

class EchoAgent(Agent):
    """
    A simple server-side agent that echoes back received messages.
    Can also provide the current time and use LLM for enhanced responses.
    """
    
    def __init__(self, agent_id: str = "echo_agent"):
        super().__init__(agent_id=agent_id)
        
        # Initialize state
        self.state = AgentState()
        
        # Set up template environment
        template_dir = Path(__file__).parent.parent / "templates"
        self.template_env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Set up LLM
        self.llm = OpenAIChat(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-3.5-turbo"  # Using a less expensive model for echo agent
        )
        
        # Set up logger
        self.logger = ServerAgentLogger(agent_id=self.agent_id)
        
        # Register tools
        self._register_tools()
        
    def _register_tools(self) -> None:
        """Register agent-specific tools"""
        # Register the current time tool
        self.tool_registry.register(
            metadata=CurrentTimeTool.get_metadata(),
            implementation=CurrentTimeTool()
        )
        
        # Register the echo tool
        self.tool_registry.register(
            metadata=EchoTool.get_metadata(),
            implementation=EchoTool()
        )
        
    async def _generate_system_prompt(self) -> str:
        """Generate the system prompt using the template"""
        try:
            template = self.template_env.get_template("system.j2")
            return template.render()
        except Exception as e:
            # Fallback to hardcoded system prompt if template loading fails
            return "You are an echo agent that repeats back messages. You can also provide the current time."
        
    async def process_acp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an ACP request and generate a response.
        
        Args:
            request: The ACP request payload
            
        Returns:
            An ACP response payload
        """
        await self.logger.on_agent_start(request)
        
        try:
            # Extract relevant information from the request
            input_data = request.get("input", {})
            messages = input_data.get("messages", [])
            
            # Validate input
            if not messages:
                return {
                    "error": 400,
                    "message": "Invalid input: 'messages' field is required or empty"
                }
            
            # Get the last user message
            last_message = messages[-1]
            if last_message.get("role") != "user":
                last_message = {"role": "user", "content": "Hello"}
            
            user_message = last_message.get("content", "")
            
            # Check if this is a simple echo request
            if "echo" in user_message.lower() or "repeat" in user_message.lower():
                # Use the echo tool directly
                echo_tool = self.tool_registry.get_tool("echo")
                result = await echo_tool.execute(message=user_message)
                response_content = result["echo"]
            elif "time" in user_message.lower():
                # Use the time tool directly
                time_tool = self.tool_registry.get_tool("get_current_time")
                result = await time_tool.execute()
                response_content = f"The current time is {result['time']} on {result['date']} (in {result['timezone']})."
            else:
                # For more complex requests, use the LLM with tools
                system_prompt = await self._generate_system_prompt()
                completion = await self.llm.generate_with_tools(
                    system_prompt=system_prompt,
                    messages=messages,
                    tools=self.tool_registry.get_openai_tools(),
                    tool_choice="auto"
                )
                
                # Handle potential tool calls
                if completion.tool_calls:
                    for tool_call in completion.tool_calls:
                        tool_name = tool_call.function.name
                        try:
                            # Parse tool arguments
                            import json
                            tool_args = json.loads(tool_call.function.arguments)
                            
                            # Execute the tool
                            tool = self.tool_registry.get_tool(tool_name)
                            tool_result = await tool.execute(**tool_args)
                            
                            # Append the tool result to messages
                            messages.append({
                                "role": "function",
                                "name": tool_name,
                                "content": json.dumps(tool_result)
                            })
                        except Exception as e:
                            # Handle tool execution errors
                            await self.logger.on_tool_error(tool_name, e)
                            messages.append({
                                "role": "function",
                                "name": tool_name,
                                "content": f"Error: {str(e)}"
                            })
                    
                    # Get final response after tool calls
                    completion = await self.llm.generate(
                        system_prompt=system_prompt,
                        messages=messages
                    )
                
                response_content = completion.content
            
            # Format response according to ACP standards
            response = {
                "output": {
                    "messages": [
                        {"role": "assistant", "content": response_content}
                    ]
                }
            }
            
            # Add the original agent_id to the response
            if "agent_id" in request:
                response["agent_id"] = request["agent_id"]
                
            # Add metadata if present in the request
            if "metadata" in request:
                response["metadata"] = request["metadata"]
                
            await self.logger.on_agent_end(response)
            return response
            
        except Exception as e:
            await self.logger.on_tool_error("process_request", e)
            return {
                "error": 500,
                "message": f"Error processing request: {str(e)}"
            }
```

Create the agents initialization file `agents/__init__.py`:

```python
# agents/__init__.py
from .echo_agent import EchoAgent

__all__ = ["EchoAgent"]
```

## Step 5: Creating the System Prompt Template

Create `templates/system.j2`:

```jinja
You are an echo agent that repeats back messages with some intelligence.

Your primary function is to echo what users say, but you can also provide the current time when asked.

You have access to the following tools:
- echo: Repeats back a given message
- get_current_time: Retrieves the current date and time

When users ask about the time, use the get_current_time tool rather than making up a time.
When users specifically ask for an echo, use the echo tool.
For other requests, try to be helpful while emphasizing your identity as an echo agent.
```

## Step 6: Implementing the Server Application

Now, let's create the FastAPI application that will serve our agent. Create `main.py`:

```python
# main.py
import os
import json
import asyncio
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from agp_api.gateway.gateway_container import GatewayContainer
from agp_api.agent.agent_container import AgentContainer
from agents import EchoAgent

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("acp_server")

# Initialize FastAPI app
app = FastAPI(title="ACP Server Agent")

# Initialize AGP containers
gateway_container = GatewayContainer()
agent_container = AgentContainer()

# Initialize our Echo Agent
echo_agent = EchoAgent(agent_id="echo_agent")

async def message_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handler function for incoming AGP messages.
    
    Args:
        payload: The message payload from the gateway
        
    Returns:
        A response payload to be sent back through the gateway
    """
    try:
        logger.info(f"Received request: {payload.get('metadata', {}).get('id', 'unknown')}")
        
        # Process the request with our echo agent
        response = await echo_agent.process_acp_request(payload)
        
        logger.info(f"Sending response: {response.get('metadata', {}).get('id', 'unknown')}")
        return response
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return {
            "error": 500,
            "message": f"Internal server error: {str(e)}"
        }

async def setup_gateway() -> None:
    """
    Configure and connect to the gateway.
    """
    # Configure the gateway connection
    gateway_endpoint = os.getenv("AGP_GATEWAY_ENDPOINT", "http://localhost:46357")
    insecure = os.getenv("AGP_GATEWAY_INSECURE", "true").lower() == "true"
    
    logger.info(f"Connecting to gateway at {gateway_endpoint} (insecure: {insecure})")
    
    gateway_container.set_config(
        endpoint=gateway_endpoint,
        insecure=insecure
    )
    
    # Set up the FastAPI app
    gateway_container.set_fastapi_app(app)
    
    # Register the echo agent with AGP
    agent_container.register_agent("echo_agent", message_handler)
    
    # Connect to the gateway with retry mechanism
    await gateway_container.connect_with_retry(
        agent_container=agent_container,
        max_duration=30,
        initial_delay=1
    )
    
    logger.info("Successfully connected to AGP gateway")
    
    # Start the server
    await gateway_container.start_server(agent_container=agent_container)

@app.on_event("startup")
async def startup_event():
    """
    Startup event handler for FastAPI.
    """
    # Start the gateway connection in a background task
    asyncio.create_task(setup_gateway())
    logger.info("Server started and initializing gateway connection")

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok", "agent": echo_agent.agent_id}

@app.post("/api/direct/echo")
async def direct_echo(request: Dict[str, Any]):
    """
    Direct API endpoint for echo agent (without going through AGP).
    This allows testing the agent without using the gateway.
    """
    try:
        # Process the request with our echo agent
        response = await echo_agent.process_acp_request(request)
        return response
    except Exception as e:
        logger.error(f"Error processing direct request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    
    # Run the server
    uvicorn.run("main:app", host=host, port=port, reload=True)
```

## Step 7: Running the Server

To run your ACP server, execute:

```bash
python main.py
```

You should see output similar to:

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:acp_server:Server started and initializing gateway connection
INFO:acp_server:Connecting to gateway at http://localhost:46357 (insecure: true)
INFO:acp_server:Successfully connected to AGP gateway
```

Now your server is running and connected to the gateway!

## Step 8: Testing the Server

### Testing with Direct API

You can test your agent directly via the API endpoint:

```bash
curl -X POST http://localhost:8000/api/direct/echo \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "echo_agent",
    "input": {
      "messages": [
        {"role": "user", "content": "Can you echo this message for me?"}
      ]
    }
  }'
```

### Testing with the Client Agent

You can also test the server using the client agent we built in the previous tutorial. Make sure both the client and server are connecting to the same gateway instance.

## Understanding the Implementation

Let's examine the key components of our server implementation:

### Agent Architecture

The `EchoAgent` follows the Simple Agent Framework design:

1. It inherits from the base `Agent` class
2. It manages its state using `AgentState`
3. It registers tools for specific capabilities
4. It uses templates for generating prompts
5. It processes ACP requests and generates responses

### AGP Integration

Our server connects to the AGP gateway:

1. It initializes the `GatewayContainer` and `AgentContainer`
2. It registers the echo agent with a message handler
3. It establishes a connection to the gateway
4. It processes incoming messages through the agent

### Request Processing

The agent processes ACP requests through these steps:

1. Validate the incoming request
2. Extract messages and other relevant data
3. Decide whether to use simple tool execution or LLM processing
4. Generate a response according to ACP standards
5. Return the response through the gateway

### Direct API Access

We've also provided a direct API endpoint for testing without the gateway, which:

1. Accepts POST requests with the same payload format
2. Passes requests directly to the agent
3. Returns responses in the same format as the AGP endpoint

## Advanced Features and Extensions

### Adding More Agent Types

You can extend this server to support multiple agent types:

```python
# Initialize different agent types
echo_agent = EchoAgent(agent_id="echo_agent")
math_agent = MathAgent(agent_id="math_agent")
weather_agent = WeatherAgent(agent_id="weather_agent")

# Register each agent with AGP
agent_container.register_agent("echo_agent", echo_message_handler)
agent_container.register_agent("math_agent", math_message_handler)
agent_container.register_agent("weather_agent", weather_message_handler)
```

### Implementing Stateful Agents

For agents that need to maintain state between requests:

```python
class StatefulAgent(Agent):
    def __init__(self, agent_id: str):
        super().__init__(agent_id=agent_id)
        self.state = AgentState()
        self.sessions = {}  # Session ID -> State
        
    async def process_acp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        # Extract session ID from metadata
        session_id = request.get("metadata", {}).get("session_id", "default")
        
        # Retrieve or create session state
        if session_id not in self.sessions:
            self.sessions[session_id] = {"history": []}
            
        session_state = self.sessions[session_id]
        
        # Add request to session history
        messages = request.get("input", {}).get("messages", [])
        session_state["history"].extend(messages)
        
        # Process with context of session history
        # ...
        
        # Update session state
        self.sessions[session_id] = session_state
        
        # Return response
        # ...
```

### Adding Authentication

For secure ACP communication:

```python
gateway_container.set_config(
    endpoint=gateway_endpoint,
    insecure=insecure,
    auth_token=os.getenv("AGP_AUTH_TOKEN")  # Add authentication token
)
```

### Implementing Streaming Responses

For streaming responses:

```python
async def process_streaming_request(request: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    # Initial processing...
    
    # Stream OpenAI response
    stream = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=messages,
        stream=True
    )
    
    content = ""
    async for chunk in stream:
        delta = chunk.choices[0].delta
        if "content" in delta and delta.content:
            content += delta.content
            yield {
                "output": {
                    "messages": [{"role": "assistant", "content": content}],
                    "is_complete": False
                }
            }
    
    # Final chunk with complete flag
    yield {
        "output": {
            "messages": [{"role": "assistant", "content": content}],
            "is_complete": True
        }
    }
```

## Troubleshooting

### Gateway Connection Issues

If the server fails to connect to the gateway:

1. Check that the gateway service is running on the specified endpoint
2. Verify the `AGP_GATEWAY_ENDPOINT` and `AGP_GATEWAY_INSECURE` environment variables
3. Check for network connectivity issues between the server and gateway

### Agent Registration Issues

If clients can't find your agent:

1. Make sure the agent ID used by clients matches the registered ID on the server
2. Check the AGP gateway logs for registration issues
3. Verify that the agent registration is successful in the server logs

### Tool Execution Errors

If tools fail to execute:

1. Check the tool implementation and error handling
2. Verify that required arguments are correctly provided
3. Look at the server logs for specific error messages

## Next Steps

Congratulations! You've built an ACP server agent using the Simple Agent Framework. In the next tutorial, we'll explore advanced agent patterns including tool use, multi-agent communication, and more.

Additional ways to enhance your server agent:
1. Add more sophisticated tools for specialized tasks
2. Implement database integration for persistent state
3. Add rate limiting and security features
4. Implement observability and monitoring

For the complete code of this tutorial, check the repository's examples directory.

## Additional Resources

- [Simple Agent Framework Documentation](https://github.com/rungalileo/simple-agent-framework#readme)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference) 