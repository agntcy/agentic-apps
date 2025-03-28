# Building Your First ACP Client with Simple Agent Framework

In the [previous tutorial](01-intro-to-agp.md), we introduced the Simple Agent Framework and how it can be extended to support the Agent Connect Protocol (ACP). Now, let's build a practical client agent that can communicate with remote agents.

## Client Agent Overview

In this tutorial, we'll create a client agent with the following capabilities:
1. Using the Simple Agent Framework structure
2. Communicating with remote agents via ACP
3. Managing conversations and state
4. Processing user inputs and displaying agent responses

Our client agent will follow the best practices from the Simple Agent Framework while incorporating ACP communication capabilities.

## Prerequisites

Before we begin, make sure you have:

1. Python 3.12+ installed
2. Installed the Simple Agent Framework: `pip install git+https://github.com/rungalileo/simple-agent-framework.git`
3. Set up necessary environment variables (OpenAI API key, etc.)
4. Installed ACP dependencies: `pip install agp-api`
5. A gateway service running if using AGP (typically on port 46357)

## Step 1: Project Setup

Let's start by creating a new directory for our client agent:

```bash
mkdir acp_client_agent
cd acp_client_agent
```

Create the following directory structure:

```
acp_client_agent/
├── __init__.py
├── agent.py           # Main agent implementation
├── templates/         # Agent-specific templates
│   └── system.j2      # System prompt template
├── logging/           # Logging configuration
│   └── logger.py      # Custom logger
└── tools/             # Agent tools
    ├── __init__.py
    └── acp_tools.py   # ACP communication tools
```

Create a `.env` file in the root directory:

```
OPENAI_API_KEY=your_openai_api_key_here
GALILEO_API_KEY=your_galileo_api_key_here  # For logging (optional)
AGP_GATEWAY_ENDPOINT=http://localhost:46357
AGP_GATEWAY_INSECURE=true
AGP_REMOTE_AGENT=server
```

## Step 2: Implementing ACP Communication Tools

First, let's create the tools our agent will use to communicate with remote agents. Create `tools/acp_tools.py`:

```python
# tools/acp_tools.py
import json
import asyncio
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from agent_framework.tools.base import BaseTool

class RemoteAgentInput(BaseModel):
    """Input schema for communicating with remote agents"""
    agent_id: str
    message: str
    metadata: Optional[Dict[str, Any]] = None

class ACPCommunicationTool(BaseTool):
    """Tool for communicating with remote agents via ACP"""
    name = "remote_agent_call"
    description = "Send a message to a remote agent and get a response"
    tags = ["communication", "acp"]
    input_schema = RemoteAgentInput.model_json_schema()
    
    def __init__(self, gateway_endpoint: str, insecure: bool = True):
        self.gateway_endpoint = gateway_endpoint
        self.insecure = insecure
        # In a real implementation, we would initialize ACP/AGP client here
        # For this tutorial, we'll use a simplified implementation
        
    async def execute(self, agent_id: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute the tool by sending a message to a remote agent.
        
        Args:
            agent_id: The ID of the remote agent to communicate with
            message: The message to send to the remote agent
            metadata: Optional metadata to include with the request
            
        Returns:
            Dict containing the remote agent's response
        """
        print(f"Sending message to remote agent '{agent_id}': {message}")
        
        # In a real implementation, we would:
        # 1. Format the request according to ACP standards
        # 2. Send it through the ACP gateway
        # 3. Wait for and parse the response
        
        # For this tutorial, we'll simulate a response
        await asyncio.sleep(1)  # Simulate network delay
        
        # Simulate a response from the remote agent
        return {
            "status": "success",
            "agent_id": agent_id,
            "response": f"Remote agent '{agent_id}' response: I received your message: '{message}'"
        }

# For a more realistic implementation with AGP:
class AGPCommunicationTool(BaseTool):
    """Tool for communicating with remote agents via AGP gateway"""
    name = "agp_communicate"
    description = "Send a message to a remote agent through AGP gateway"
    tags = ["communication", "agp", "acp"]
    input_schema = RemoteAgentInput.model_json_schema()
    
    def __init__(self, gateway_endpoint: str, insecure: bool = True):
        from agp_api.gateway.gateway_container import GatewayContainer
        from agp_api.agent.agent_container import AgentContainer
        
        self.gateway_container = GatewayContainer()
        self.agent_container = AgentContainer()
        
        # Configure the gateway connection
        self.gateway_container.set_config(
            endpoint=gateway_endpoint,
            insecure=insecure
        )
        self.connected = False
        
    async def _ensure_connected(self):
        """Ensure gateway connection is established"""
        if not self.connected:
            await self.gateway_container.connect_with_retry(
                agent_container=self.agent_container,
                max_duration=10,
                initial_delay=1
            )
            self.connected = True
        
    async def execute(self, agent_id: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the tool by sending a message through the AGP gateway"""
        await self._ensure_connected()
        
        # Create payload for the remote agent
        payload = {
            "agent_id": agent_id,
            "input": {
                "messages": [
                    {"role": "user", "content": message}
                ]
            },
            "metadata": metadata or {},
            "route": "/api/v1/runs",  # API route for agent execution
        }
        
        # Send the message and get response
        await self.gateway_container.publish_messsage(
            payload, 
            agent_container=self.agent_container, 
            remote_agent=agent_id
        )
        
        # Wait for response
        _, recv = await self.gateway_container.gateway.receive()
        response_data = json.loads(recv.decode("utf8"))
        
        # Check for errors
        error_code = response_data.get("error")
        if error_code is not None:
            return {
                "status": "error",
                "error_code": error_code,
                "message": response_data.get("message", "Unknown error")
            }
        
        # Process successful response
        output = response_data.get("output", {})
        messages = output.get("messages", [])
        
        if messages:
            content = messages[-1].get("content", "")
            return {
                "status": "success",
                "agent_id": agent_id,
                "response": content
            }
        else:
            return {
                "status": "success",
                "agent_id": agent_id,
                "response": "Received empty response from agent"
            }
```

Now, create the tools initialization file `tools/__init__.py`:

```python
# tools/__init__.py
from .acp_tools import ACPCommunicationTool, AGPCommunicationTool

__all__ = ["ACPCommunicationTool", "AGPCommunicationTool"]
```

## Step 3: Creating the Prompt Template

Let's create a system prompt template for our agent. Create `templates/system.j2`:

```jinja
You are an ACP client agent that can communicate with other agents.

You have access to remote agents with different capabilities. You can send messages to these remote agents using the tools provided.

Available remote agents:
{% for agent in remote_agents %}
- {{ agent.id }}: {{ agent.description }}
{% endfor %}

When you need to consult a remote agent, use the appropriate tool to communicate with it.

Remember to:
1. Consider which remote agent would be most helpful for the current query
2. Clearly formulate your question or request to the remote agent
3. Explain to the user which remote agent you're consulting and why
4. Share the remote agent's response with the user

Current conversation:
{% for message in conversation %}
{{ message.role }}: {{ message.content }}
{% endfor %}
```

## Step 4: Setting Up Logging

Create `logging/logger.py` for logging agent activities:

```python
# logging/logger.py
from agent_framework.utils.logging import AgentLogger
from typing import Any, List, Optional, Dict

class ACPClientLogger(AgentLogger):
    """Custom logger for the ACP client agent"""
    
    def __init__(self, agent_id: str):
        super().__init__(agent_id)
        # Initialize any additional logging systems here (e.g., Galileo)
        
    async def on_agent_start(self, input_data: Any) -> None:
        """Log when the agent starts processing a request"""
        print(f"🟢 Agent {self.agent_id} starting with input: {input_data}")
        
    async def on_tool_start(self, tool_name: str, tool_input: Dict[str, Any]) -> None:
        """Log when a tool execution starts"""
        print(f"🔧 Agent {self.agent_id} starting tool: {tool_name} with input: {tool_input}")
        
    async def on_tool_end(self, tool_name: str, output: Any) -> None:
        """Log when a tool execution completes"""
        print(f"✅ Agent {self.agent_id} completed tool: {tool_name} with output: {output}")
        
    async def on_tool_error(self, tool_name: str, error: Exception) -> None:
        """Log when a tool execution encounters an error"""
        print(f"❌ Agent {self.agent_id} tool error in {tool_name}: {error}")
        
    async def on_agent_end(self, output: Any) -> None:
        """Log when the agent completes processing"""
        print(f"🏁 Agent {self.agent_id} completed with output: {output}")
```

## Step 5: Implementing the Agent

Now, let's create the main agent implementation in `agent.py`:

```python
# agent.py
import os
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

from agent_framework.agent import Agent
from agent_framework.state import AgentState
from agent_framework.utils.llm import OpenAIChat
from logging.logger import ACPClientLogger
from tools import ACPCommunicationTool, AGPCommunicationTool

# Load environment variables
load_dotenv()

class ACPClientAgent(Agent):
    """
    Client agent that can communicate with remote agents using ACP.
    """
    
    def __init__(self, agent_id: str = "acp_client"):
        super().__init__(agent_id=agent_id)
        
        # Initialize state
        self.state = AgentState()
        self.state.set("conversation", [])
        self.state.set("remote_agents", [
            {"id": "server", "description": "General purpose assistant"},
            {"id": "calculator", "description": "Mathematical calculations"},
            {"id": "weather", "description": "Weather information"},
        ])
        
        # Set up template environment
        template_dir = Path(__file__).parent / "templates"
        self.template_env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Set up LLM
        self.llm = OpenAIChat(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4"
        )
        
        # Set up logger
        self.logger = ACPClientLogger(agent_id=self.agent_id)
        
        # Register tools
        self._register_tools()
        
    def _register_tools(self) -> None:
        """Register agent-specific tools"""
        # Register the simple ACP communication tool
        self.tool_registry.register(
            metadata=ACPCommunicationTool.get_metadata(),
            implementation=ACPCommunicationTool(
                gateway_endpoint=os.getenv("AGP_GATEWAY_ENDPOINT", "http://localhost:46357"),
                insecure=os.getenv("AGP_GATEWAY_INSECURE", "true").lower() == "true"
            )
        )
        
        # Optionally register the AGP communication tool
        # Uncomment this to use the real AGP implementation
        """
        self.tool_registry.register(
            metadata=AGPCommunicationTool.get_metadata(),
            implementation=AGPCommunicationTool(
                gateway_endpoint=os.getenv("AGP_GATEWAY_ENDPOINT", "http://localhost:46357"),
                insecure=os.getenv("AGP_GATEWAY_INSECURE", "true").lower() == "true"
            )
        )
        """
        
    async def _generate_system_prompt(self) -> str:
        """Generate the system prompt using the template"""
        template = self.template_env.get_template("system.j2")
        return template.render(
            remote_agents=self.state.get("remote_agents"),
            conversation=self.state.get("conversation")
        )
        
    async def process_message(self, message: str) -> str:
        """
        Process a user message and return a response.
        
        Args:
            message: The user's message
            
        Returns:
            The agent's response
        """
        # Update conversation state with user message
        conversation = self.state.get("conversation")
        conversation.append({"role": "user", "content": message})
        
        # Generate system prompt
        system_prompt = await self._generate_system_prompt()
        
        # Call LLM with tool support
        response = await self.llm.generate_with_tools(
            system_prompt=system_prompt,
            messages=conversation,
            tools=self.tool_registry.get_openai_tools(),
            tool_choice="auto"
        )
        
        # Handle tool calls if present
        if response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call.function.name
                try:
                    # Parse tool arguments
                    tool_args = tool_call.function.arguments
                    if isinstance(tool_args, str):
                        import json
                        tool_args = json.loads(tool_args)
                    
                    # Execute the tool
                    tool = self.tool_registry.get_tool(tool_name)
                    await self.logger.on_tool_start(tool_name, tool_args)
                    tool_result = await tool.execute(**tool_args)
                    await self.logger.on_tool_end(tool_name, tool_result)
                    
                    # Add tool result to conversation
                    conversation.append({
                        "role": "function",
                        "name": tool_name,
                        "content": str(tool_result)
                    })
                    
                except Exception as e:
                    # Log tool error
                    await self.logger.on_tool_error(tool_name, e)
                    conversation.append({
                        "role": "function",
                        "name": tool_name,
                        "content": f"Error: {str(e)}"
                    })
            
            # Get final response after tool calls
            system_prompt = await self._generate_system_prompt()
            response = await self.llm.generate(
                system_prompt=system_prompt,
                messages=conversation
            )
        
        # Add assistant response to conversation
        conversation.append({"role": "assistant", "content": response.content})
        
        # Return the response
        return response.content

async def main():
    """
    Main function to run the agent interactively.
    """
    # Create the agent
    agent = ACPClientAgent()
    
    print("ACP Client Agent initialized. Type 'exit' to quit.")
    print("This agent can communicate with remote agents using ACP.")
    
    # Interactive loop
    while True:
        # Get user input
        user_input = input("\nYou: ")
        
        if user_input.lower() == "exit":
            break
            
        # Process the message
        print("\nAgent is thinking...")
        response = await agent.process_message(user_input)
        
        # Display the response
        print(f"\nAgent: {response}")

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())
```

## Step 6: Running the Client Agent

To run your ACP client agent, execute:

```bash
python agent.py
```

You should see:

```
ACP Client Agent initialized. Type 'exit' to quit.
This agent can communicate with remote agents using ACP.

You: 
```

Now you can chat with your agent and have it communicate with remote agents!

## Understanding the Implementation

Let's break down the key components of our ACP client agent:

### Agent Structure

Our `ACPClientAgent` follows the Simple Agent Framework pattern:

1. It inherits from the base `Agent` class
2. It manages its state using `AgentState`
3. It uses a template system for generating prompts
4. It registers custom tools for communication
5. It provides logging for monitoring agent behavior

### ACP Communication

The agent uses specialized tools for ACP communication:

1. `ACPCommunicationTool`: A simplified implementation for demonstration
2. `AGPCommunicationTool`: A more complete implementation using the AGP client libraries

These tools handle:
- Formatting requests according to ACP standards
- Sending requests to remote agents (via gateway or direct)
- Processing responses and handling errors

### Conversation Flow

The agent's conversation flow works as follows:

1. User sends a message to the agent
2. Agent updates its conversation state
3. Agent generates a system prompt using templates
4. Agent calls the LLM with tool definitions
5. If the LLM decides to use a tool (to contact a remote agent):
   - The tool is executed with appropriate parameters
   - The result is added to the conversation
   - The LLM is called again to generate a final response
6. The agent's response is returned to the user

## Advanced Usage

### Supporting Multiple Remote Agents

You can expand the agent's capabilities by registering multiple remote agents:

```python
self.state.set("remote_agents", [
    {"id": "server", "description": "General purpose assistant"},
    {"id": "calculator", "description": "Mathematical calculations"},
    {"id": "weather", "description": "Weather information"},
    {"id": "code_assistant", "description": "Programming and coding help"},
    {"id": "data_analyst", "description": "Data analysis and visualization"},
])
```

### Implementing Real AGP Communication

For real AGP communication, uncomment the AGP tool registration in the `_register_tools` method and ensure you have the gateway service running.

### Adding Authentication

For secure agent communication, add authentication to your AGP configuration:

```python
self.gateway_container.set_config(
    endpoint=gateway_endpoint,
    insecure=insecure,
    auth_token=os.getenv("AGP_AUTH_TOKEN")  # Add authentication token
)
```

## Troubleshooting

### Connection Issues

If you have trouble connecting to remote agents:

1. Check that your gateway service is running (if using AGP)
2. Verify your environment variables are correctly set
3. Ensure the remote agent ID matches a registered agent on the server
4. Check network connectivity between your client and the gateway

### Tool Execution Errors

If tools fail to execute:

1. Check the tool's input parameters match what the LLM is providing
2. Verify the tool implementation handles errors gracefully
3. Look at the logs for specific error messages

## Next Steps

Congratulations! You've built an ACP client agent using the Simple Agent Framework. In the next tutorial, we'll explore how to implement server-side agents that can handle requests from client agents.

Additional ways to enhance your client agent:
1. Add more sophisticated tools for specialized tasks
2. Implement more advanced conversation management
3. Add streaming response support
4. Create a web interface for your agent

For the complete code of this tutorial, check the repository's examples directory.

## Additional Resources

- [Simple Agent Framework Documentation](https://github.com/rungalileo/simple-agent-framework#readme)
- [OpenAI Tool Calling Guide](https://platform.openai.com/docs/guides/function-calling)
- [Jinja2 Template Documentation](https://jinja.palletsprojects.com/) 