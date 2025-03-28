# Implementing the Agent

Now, let's create the main agent that will use these tools. 

Create weather_vibes/agent/weather_vibes_agent.py:

```
"""
Weather Vibes Agent implementation using the Simple Agent Framework.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader

from agent_framework.agent import Agent
from agent_framework.state import AgentState
from agent_framework.utils.llm import OpenAIChat
from agent_framework.utils.logging import AgentLogger

from ..tools import WeatherTool, RecommendationsTool, YouTubeTool
from .descriptor import WEATHER_VIBES_DESCRIPTOR

class WeatherVibesAgent(Agent):
    """
    Agent that provides weather information, recommendations, and matching videos.
    Implements the Agent Connect Protocol (ACP) for standardized communication.
    """
    
    def __init__(self, agent_id: str = "weather_vibes"):
        super().__init__(agent_id=agent_id)
        
        # Initialize state
        self.state = AgentState()
        self.state.set("search_history", [])
        self.state.set("favorite_locations", [])
        
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
            model="gpt-4"
        )
        
        # Set up logger
        self.logger = AgentLogger(agent_id=self.agent_id)
        
        # Register tools
        self._register_tools()
        
        # Store descriptor
        self.descriptor = WEATHER_VIBES_DESCRIPTOR
        
    def _register_tools(self) -> None:
        """Register agent-specific tools"""
        self.tool_registry.register(
            metadata=WeatherTool.get_metadata(),
            implementation=WeatherTool()
        )
        
        self.tool_registry.register(
            metadata=RecommendationsTool.get_metadata(),
            implementation=RecommendationsTool()
        )
        
        self.tool_registry.register(
            metadata=YouTubeTool.get_metadata(),
            implementation=YouTubeTool()
        )
    
    async def _generate_system_prompt(self) -> str:
        """Generate the system prompt using the template"""
        template = self.template_env.get_template("system.j2")
        return template.render(
            search_history=self.state.get("search_history"),
            favorite_locations=self.state.get("favorite_locations")
        )
    
    async def get_acp_descriptor(self) -> Dict[str, Any]:
        """
        Return the ACP descriptor for this agent.
        This implements the ACP agent discovery capability.
        """
        return self.descriptor
    
    async def process_acp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an ACP request and generate a response.
        This implements the ACP run execution capability.
        
        Args:
            request: The ACP request payload
            
        Returns:
            An ACP response payload
        """
        await self.logger.on_agent_start(request)
        
        try:
            # Extract relevant information from the request
            input_data = request.get("input", {})
            config = request.get("config", {})
            metadata = request.get("metadata", {})
            
            # Parse input and config
            location = input_data.get("location")
            units = input_data.get("units", "metric")
            verbose = config.get("verbose", False)
            max_recommendations = config.get("max_recommendations", 5)
            video_mood = config.get("video_mood")
            
            # Validate input
            if not location:
                return {
                    "error": 400,
                    "message": "Invalid input: 'location' field is required"
                }
            
            # Update search history
            search_history = self.state.get("search_history", [])
            if location not in search_history:
                search_history.append(location)
                self.state.set("search_history", search_history[-5:])  # Keep last 5
            
            # Step 1: Get weather information
            weather_tool = self.tool_registry.get_tool("get_weather")
            weather_result = await weather_tool.execute(location=location, units=units)
            
            if "error" in weather_result:
                return {
                    "error": 500,
                    "message": f"Weather API error: {weather_result['message']}"
                }
            
            # Step 2: Get recommendations
            recommendations_tool = self.tool_registry.get_tool("get_recommendations")
            recommendations = await recommendations_tool.execute(
                weather=weather_result,
                max_items=max_recommendations
            )
            
            # Step 3: Get matching YouTube video
            youtube_tool = self.tool_registry.get_tool("find_weather_video")
            video_result = await youtube_tool.execute(
                weather_condition=weather_result["condition"],
                mood_override=video_mood
            )
            
            # Prepare the response
            result = {
                "weather": weather_result,
                "recommendations": recommendations,
                "video": video_result
            }
            
            # If not verbose, filter out some weather details
            if not verbose and "weather" in result:
                result["weather"] = {
                    "location": weather_result["location"],
                    "temperature": weather_result["temperature"],
                    "condition": weather_result["condition"],
                    "humidity": weather_result["humidity"],
                    "wind_speed": weather_result["wind_speed"]
                }
            
            # Format response according to ACP standards
            response = {
                "output": result
            }
            
            # Add the original agent_id to the response
            if "agent_id" in request:
                response["agent_id"] = request["agent_id"]
                
            # Add metadata if present in the request
            if metadata:
                response["metadata"] = metadata
                
            await self.logger.on_agent_end(response)
            return response
            
        except Exception as e:
            await self.logger.on_tool_error("process_request", e)
            return {
                "error": 500,
                "message": f"Error processing request: {str(e)}"
            }
```

This agent uses the Simple Agent Framework to process ACP requests and generate responses.

When complete, move on to the next step where we'll create the main application.


