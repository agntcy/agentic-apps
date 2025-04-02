# Adding Galileo Evaluation to Weather Vibes Agent

In this final step, we'll integrate [Galileo](https://galileo.ai) to monitor, evaluate, and improve our agent's performance. Galileo is a powerful tool for AI evaluation that helps you identify and fix issues with your AI responses.

## What is Galileo?

Galileo is an AI Evaluation Platform that helps you monitor, troubleshoot, and optimize your AI applications. It provides:

- **Metrics & Analytics**: Track AI performance and quality
- **Issue Detection**: Identify problematic responses
- **Root Cause Analysis**: Trace exactly where problems occur
- **Experimentation**: Test different approaches to improve performance

## Implementing Galileo in our Agent

### Step 1: Install the Galileo SDK

First, let's add Galileo to our requirements:

```bash
pip install galileo
```

Or add it to your `requirements.txt`:

```
# Add to existing requirements.txt
galileo
```

### Step 2: Add Environment Variables

Update your `.env` file with Galileo credentials:

```
# Existing variables
OPENAI_API_KEY=your_openai_api_key
OPENWEATHERMAP_API_KEY=your_openweathermap_key
YOUTUBE_API_KEY=your_youtube_api_key

# Add Galileo variables
GALILEO_API_KEY=your_galileo_api_key
GALILEO_PROJECT=weather_vibes
GALILEO_LOG_STREAM=production
```

### Step 3: Modify the Agent Implementation

We need to modify our `weather_vibes_agent.py` file to use Galileo's OpenAI wrapper and context manager. This will allow Galileo to automatically log and track our agent's interactions with the OpenAI API.

Let's open `weather_vibes/agent/weather_vibes_agent.py` and make the following changes:

```python
# Import Galileo
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader

# Import Galileo components
from galileo import galileo_context
from galileo.openai import openai  # Galileo's OpenAI wrapper

from agent_framework.agent import Agent
from agent_framework.state import AgentState

# Import tools
from ..tools import WeatherTool, RecommendationsTool, YouTubeTool
from .descriptor import WEATHER_VIBES_DESCRIPTOR
```

Then in the `__init__` method, replace the OpenAI client initialization:

```python
def __init__(self, agent_id: str = "weather_vibes"):
    super().__init__(agent_id=agent_id)
    
    # Initialize state
    self.state = AgentState()
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
    
    # Replace regular OpenAI client with Galileo's wrapped version
    self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Standard logging
    self.agent_id = agent_id
    logger.info(f"Initialized WeatherVibesAgent with ID: {self.agent_id}")
    
    # Register tools
    self._register_tools()
    
    # Store descriptor
    self.descriptor = WEATHER_VIBES_DESCRIPTOR
```

### Step 4: Modify the Process Request Method

Now let's update the `process_acp_request` method to use Galileo's context manager:

```python
async def process_acp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process an ACP request and generate a response.
    This implements the ACP run execution capability.
    
    Args:
        request: The ACP request payload
        
    Returns:
        An ACP response payload
    """
    # Use Galileo's context manager to automatically track this request
    with galileo_context():
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
            
            # Rest of the method remains the same...
            # ...
            
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
```

### Step 5: Add Metrics in Galileo Dashboard

After running your application with Galileo integration, visit the Galileo dashboard to:

1. Set up custom metrics to measure:
   - Response quality
   - Weather API accuracy
   - YouTube recommendation relevance
   - Tool selection accuracy

2. Create custom thresholds for alerts:
   - Response latency over X seconds
   - Error rates above Y%
   - Hallucination detection

## Benefits of Using Galileo with Weather Vibes Agent

By integrating Galileo, you'll gain:

1. **Visibility**: See exactly how your agent is performing in production
2. **Quality Control**: Identify when your agent gives incorrect or low-quality responses
3. **Improvement Opportunities**: Pinpoint specific areas where prompt engineering or tool upgrades would help
4. **User Satisfaction Tracking**: Monitor if users are getting valuable responses

## Running Experiments

Galileo allows you to run experiments to compare different versions of your agent. For example, you could:

1. Test different prompts for the YouTube recommendation tool
2. Compare performance between different OpenAI models
3. Evaluate new weather data sources or APIs

To run an experiment:

```python
# Example experiment code
from galileo import Experiment

experiment = Experiment(
    name="YouTube Recommendation Improvement",
    description="Testing more specific weather-to-mood mappings"
)

with experiment.variant("baseline"):
    # Original implementation
    with galileo_context():
        # Run your agent with the current implementation
        response = agent.process_acp_request(request)

with experiment.variant("improved_mapping"):
    # Modified implementation with better weather-to-mood mapping
    with galileo_context():
        # Run your agent with the improved implementation
        response = agent.process_acp_request(request)
```

## Conclusion

By implementing Galileo in the Weather Vibes agent, you've added powerful monitoring and evaluation capabilities that will help you continuously improve the agent's performance and user experience.

Remember to regularly check the Galileo dashboard to identify issues, track improvements, and ensure your agent is delivering high-quality responses. 

Curious about how to use Galileo to evaluate your own agents? [Sign up for a free Galileo account](https://galileo.ai), open a GitHub issue, or reach out to the Galileo DevRel team at [devrel@galileo.ai](mailto:devrel@galileo.ai).