"""
Weather Vibes Agent implementation using the Simple Agent Framework.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader

from agent_framework.agent import Agent
from agent_framework.state import AgentState
from openai import OpenAI
# from agent_framework.utils.logging import AgentLogger

# Use absolute imports instead of relative imports
# Replace: from ..tools import WeatherTool, RecommendationsTool, YouTubeTool
try:
    # Try direct import first
    from weather_vibes.tools.weather_tool import WeatherTool
    from weather_vibes.tools.recommendations_tool import RecommendationsTool
    from weather_vibes.tools.youtube_tool import YouTubeTool
except ImportError:
    try:
        # Try with testing prefix
        from testing.weather_vibes_agent.weather_vibes.tools.weather_tool import WeatherTool
        from testing.weather_vibes_agent.weather_vibes.tools.recommendations_tool import RecommendationsTool
        from testing.weather_vibes_agent.weather_vibes.tools.youtube_tool import YouTubeTool
    except ImportError:
        # Final fallback - try relative import as a last resort
        try:
            from ..tools.weather_tool import WeatherTool
            from ..tools.recommendations_tool import RecommendationsTool
            from ..tools.youtube_tool import YouTubeTool
        except ImportError:
            # Directly import from the current directory structure
            import sys
            import os.path
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from tools.weather_tool import WeatherTool
            from tools.recommendations_tool import RecommendationsTool
            from tools.youtube_tool import YouTubeTool

from .descriptor import WEATHER_VIBES_DESCRIPTOR

# Configure standard logging
logger = logging.getLogger("weather_vibes_agent")

# Add metadata class methods to tools to match the updated API
# These are manually added here since we can't modify the original tool classes
def create_tool_metadata(name, description, tags=None):
    @classmethod
    def metadata(cls):
        return {
            "name": name, 
            "description": description,
            "tags": tags or []
        }
    return metadata

# Add metadata method to the tool classes if they don't have it
if not hasattr(WeatherTool, 'metadata'):
    WeatherTool.metadata = create_tool_metadata(
        "get_weather", 
        "Get the current weather conditions for a location",
        ["weather", "utility"]
    )

if not hasattr(RecommendationsTool, 'metadata'):
    RecommendationsTool.metadata = create_tool_metadata(
        "get_recommendations", 
        "Get recommendations for items to bring based on weather conditions",
        ["weather", "recommendations"]
    )

if not hasattr(YouTubeTool, 'metadata'):
    YouTubeTool.metadata = create_tool_metadata(
        "find_weather_video", 
        "Find a YouTube video that matches the weather vibe",
        ["youtube", "entertainment"]
    )

class WeatherVibesAgent(Agent):
    """
    Agent that provides weather information, recommendations, and matching videos.
    Implements the Agent Connect Protocol (ACP) for standardized communication.
    """
    
    def __init__(self, agent_id: str = "weather_vibes"):
        super().__init__(agent_id=agent_id)
        
        # Initialize state - the API has changed, so we use direct assignment now
        # Changed from self.state.set() to direct attribute assignment
        self.state = AgentState()
        
        # Default state initialization using direct attributes
        # Instead of self.state.set("search_history", []), use:
        if not hasattr(self.state, "search_history"):
            self.state.search_history = []
        if not hasattr(self.state, "favorite_locations"):
            self.state.favorite_locations = []
        
        # Set up template environment
        template_dir = Path(__file__).parent.parent / "templates"
        self.template_env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Set up OpenAI client instead of OpenAIChat
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Instead of AgentLogger, use standard Python logging
        self.agent_id = agent_id
        logger.info(f"Initialized WeatherVibesAgent with ID: {self.agent_id}")
        
        # Register tools
        self._register_tools()
        
        # Store descriptor
        self.descriptor = WEATHER_VIBES_DESCRIPTOR
        
    def _register_tools(self) -> None:
        """Register agent-specific tools"""
        # First, inspect what type of object tool_registry is
        logger.info(f"Tool registry type: {type(self.tool_registry)}")
        
        # Let's try multiple different approaches
        try:
            # Create tool instances
            weather_tool = WeatherTool()
            recommendations_tool = RecommendationsTool()
            youtube_tool = YouTubeTool()
            
            # Try to figure out what the registry is and how to use it
            if hasattr(self.tool_registry, 'register'):
                # Approach 1: Check if register is a method that takes tool instances
                try:
                    logger.info("Trying direct tool registration with single argument")
                    # Try calling with a single argument
                    self.tool_registry.register(weather_tool)
                    self.tool_registry.register(recommendations_tool)
                    self.tool_registry.register(youtube_tool)
                    logger.info("Direct tool registration successful")
                    return
                except Exception as e:
                    logger.warning(f"Direct tool registration failed: {e}")
                
                # Approach 2: Try with keyword arguments
                try:
                    logger.info("Trying registration with keyword arguments")
                    self.tool_registry.register(tool=weather_tool)
                    self.tool_registry.register(tool=recommendations_tool)
                    self.tool_registry.register(tool=youtube_tool)
                    logger.info("Keyword tool registration successful")
                    return
                except Exception as e:
                    logger.warning(f"Keyword tool registration failed: {e}")
                    
                # Approach 3: Check if it's a dictionary-like registration
                try:
                    logger.info("Trying dictionary-style registration")
                    self.tool_registry.register({"get_weather": weather_tool})
                    self.tool_registry.register({"get_recommendations": recommendations_tool})
                    self.tool_registry.register({"find_weather_video": youtube_tool})
                    logger.info("Dictionary-style registration successful")
                    return
                except Exception as e:
                    logger.warning(f"Dictionary-style registration failed: {e}")

                # Approach 4: Check if the register method is actually a property to set
                try:
                    logger.info("Trying to treat register as a property")
                    # Try setting tools directly into the registry
                    setattr(self.tool_registry, "get_weather", weather_tool)
                    setattr(self.tool_registry, "get_recommendations", recommendations_tool)  
                    setattr(self.tool_registry, "find_weather_video", youtube_tool)
                    logger.info("Direct property setting successful")
                    return
                except Exception as e:
                    logger.warning(f"Property setting failed: {e}")
                    
            # Approach 5: Check if the tool_registry is a dictionary itself
            if hasattr(self.tool_registry, '__setitem__'):
                try:
                    logger.info("Treating tool_registry as a dictionary")
                    self.tool_registry["get_weather"] = weather_tool
                    self.tool_registry["get_recommendations"] = recommendations_tool
                    self.tool_registry["find_weather_video"] = youtube_tool
                    logger.info("Dictionary assignment successful")
                    return
                except Exception as e:
                    logger.warning(f"Dictionary assignment failed: {e}")
                    
            # Approach 6: Desperate attempt - try monkey patching the tool registry
            try:
                logger.info("Attempting to monkey patch the tool registry")
                # Create a simple in-memory tool lookup
                tool_lookup = {
                    "get_weather": weather_tool,
                    "get_recommendations": recommendations_tool,
                    "find_weather_video": youtube_tool
                }
                
                # Override the get_tool method
                def get_tool_override(name):
                    return tool_lookup.get(name)
                
                # Try to replace the method
                self.tool_registry.get_tool = get_tool_override
                logger.info("Monkey patching successful")
                return
            except Exception as e:
                logger.error(f"All tool registration approaches failed: {e}")
                raise ValueError(f"Unable to register tools. Tool registry type: {type(self.tool_registry)}")
        
        except Exception as e:
            logger.error(f"Failed to register tools: {e}")
            raise
    
    async def _generate_system_prompt(self) -> str:
        """Generate the system prompt using the template"""
        template = self.template_env.get_template("system.j2")
        return template.render(
            search_history=getattr(self.state, "search_history", []),
            favorite_locations=getattr(self.state, "favorite_locations", [])
        )
    
    async def _format_result(self, result: Any) -> Dict[str, Any]:
        """
        Format the result from processing.
        
        This is an abstract method required by the Agent base class.
        It formats the raw result into a standard structure.
        
        Args:
            result: The raw result from processing
            
        Returns:
            A formatted result dictionary
        """
        if isinstance(result, dict):
            return result
        elif hasattr(result, 'model_dump'):
            # Handle pydantic models
            return result.model_dump()
        elif hasattr(result, '__dict__'):
            # Handle objects with __dict__
            return result.__dict__
        else:
            # Default case
            return {"result": str(result)}
    
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
        # Replace AgentLogger methods with standard logging
        logger.info(f"Processing ACP request: {json.dumps(request)[:100]}...")
        
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
                logger.error("Invalid input: 'location' field is required")
                return {
                    "error": 400,
                    "message": "Invalid input: 'location' field is required"
                }
            
            # Update search history - use direct attribute access instead of set/get
            if not hasattr(self.state, "search_history"):
                self.state.search_history = []
                
            if location not in self.state.search_history:
                self.state.search_history.append(location)
                # Keep only last 5 items
                if len(self.state.search_history) > 5:
                    self.state.search_history = self.state.search_history[-5:]
            
            # Step 1: Get weather information
            logger.info(f"Getting weather for location: {location}")
            weather_tool = self.tool_registry.get_tool("get_weather")
            weather_result = await weather_tool.execute(location=location, units=units)
            
            if "error" in weather_result:
                logger.error(f"Weather API error: {weather_result['message']}")
                return {
                    "error": 500,
                    "message": f"Weather API error: {weather_result['message']}"
                }
            
            # Step 2: Get recommendations
            logger.info(f"Getting recommendations based on weather")
            recommendations_tool = self.tool_registry.get_tool("get_recommendations")
            recommendations = await recommendations_tool.execute(
                weather=weather_result,
                max_items=max_recommendations
            )
            
            # Step 3: Get matching YouTube video
            logger.info(f"Finding YouTube video matching weather condition: {weather_result['condition']}")
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
                
            logger.info(f"Successfully processed request for location: {location}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            return {
                "error": 500,
                "message": f"Error processing request: {str(e)}"
            }
