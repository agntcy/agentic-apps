# Step 3: Creating the Tools

Now, let's implement the tools our agent needs. 

(As before, don't want to scroll too much? find a link to all of the tools in the [project repo](https://github.com/agntcy/agentic-apps/blob/main/tutorials/02-weather-vibes-agent/tools))

First, create weather_vibes/tools/weather_tool.py:

```
"""
Weather tool for fetching current weather conditions using OpenWeatherMap API.
"""
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel
from agent_framework.tools.base import BaseTool
import requests

class WeatherInput(BaseModel):
    """Input schema for the weather tool"""
    location: str
    units: str = "metric"

class WeatherTool(BaseTool):
    """Tool for fetching weather information"""
    name = "get_weather"
    description = "Get the current weather conditions for a location"
    tags = ["weather", "utility"]
    input_schema = WeatherInput.model_json_schema()
    
    def __init__(self):
        self.api_key = os.getenv("OPENWEATHERMAP_API_KEY")
        if not self.api_key:
            raise ValueError("OpenWeatherMap API key not found in environment")
        self.base_url = "http://api.openweathermap.org/data/2.5/weather"
    
    async def execute(self, location: str, units: str = "metric") -> Dict[str, Any]:
        """
        Execute the tool to get current weather.
        
        Args:
            location: The location to get weather for (city name, zip code, etc.)
            units: Unit system for temperature (metric or imperial)
            
        Returns:
            Dictionary containing weather information
        """
        params = {
            "q": location,
            "units": units,
            "appid": self.api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Extract relevant weather information
            weather_info = {
                "location": data["name"],
                "temperature": data["main"]["temp"],
                "condition": data["weather"][0]["main"],
                "description": data["weather"][0]["description"],
                "humidity": data["main"]["humidity"],
                "wind_speed": data["wind"]["speed"],
                "icon": data["weather"][0]["icon"],
                "feels_like": data["main"]["feels_like"]
            }
            
            return weather_info
        except Exception as e:
            return {
                "error": str(e),
                "message": f"Failed to get weather for location: {location}"
            }
```


This tool uses the OpenWeatherMap API to fetch weather information for a given location.

Next, create a recommendation tool in weather_vibes/tools/recommendation_tool.py:

```
"""
Tool for generating item recommendations based on weather conditions.
"""
from typing import Dict, Any, List
from pydantic import BaseModel
from agent_framework.tools.base import BaseTool

class RecommendationsInput(BaseModel):
    """Input schema for recommendations tool"""
    weather: Dict[str, Any]
    max_items: int = 5

class RecommendationsTool(BaseTool):
    """Tool for generating weather-based recommendations"""
    name = "get_recommendations"
    description = "Get recommendations for items to bring based on weather conditions"
    tags = ["weather", "recommendations"]
    input_schema = RecommendationsInput.model_json_schema()
    
    async def execute(self, weather: Dict[str, Any], max_items: int = 5) -> List[str]:
        """
        Execute the tool to get recommendations.
        
        Args:
            weather: Weather information dictionary
            max_items: Maximum number of recommendations to provide
            
        Returns:
            List of recommended items
        """
        recommendations = []
        
        # Basic recommendation logic based on weather conditions
        condition = weather.get("condition", "").lower()
        temp = weather.get("temperature", 0)
        description = weather.get("description", "").lower()
        
        # Rain-related recommendations
        if any(x in condition.lower() or x in description.lower() for x in ["rain", "drizzle", "shower"]):
            recommendations.extend(["☔", "🧥" ])
        
        # Sun-related recommendations
        if any(x in condition.lower() or x in description.lower() for x in ["clear", "sun"]):
            recommendations.extend(["🕶️", "🧴", "🧢"])
        
        # Temperature-based recommendations
        if temp < 5:  # Cold
            recommendations.extend(["🎿", "🧤", "🧣", "🥶"])
        elif temp < 15:  # Cool
            recommendations.extend(["👖", "🧦", "🌫️"])
        elif temp < 25:  # Warm
            recommendations.extend(["👕", "🩳", "☀️"])
        else:  # Hot
            recommendations.extend(["🥵", "👙", "🌴", "🩴"])
        
        # Wind-related recommendations
        if weather.get("wind_speed", 0) > 20:
            recommendations.append("🌬️", "🪁")
        
        # Return unique recommendations, limited to max_items
        unique_recommendations = list(set(recommendations))
        return unique_recommendations[:max_items]
```

This tool generates recommendations based on weather conditions.

Next, create weather_vibes/tools/youtube_tool.py:


```
"""
Tool for finding YouTube videos that match the weather vibe.
"""
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel
from agent_framework.tools.base import BaseTool
from googleapiclient.discovery import build

class YouTubeInput(BaseModel):
    """Input schema for YouTube tool"""
    weather_condition: str
    mood_override: Optional[str] = None

class YouTubeTool(BaseTool):
    """Tool for finding YouTube videos based on weather conditions"""
    name = "find_weather_video"
    description = "Find a YouTube video that matches the weather vibe"
    tags = ["youtube", "entertainment"]
    input_schema = YouTubeInput.model_json_schema()
    
    def __init__(self):
        self.api_key = os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError("YouTube API key not found in environment")
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
    
    async def execute(self, weather_condition: str, mood_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the tool to find a weather-matching YouTube video.
        
        Args:
            weather_condition: Current weather condition
            mood_override: Optional mood to override search query
            
        Returns:
            Dictionary containing video information
        """
        try:
            # Generate search query based on weather condition and optional mood
            if mood_override:
                query = f"{weather_condition} {mood_override} music"
            else:
                # Map weather conditions to vibes
                vibe_mapping = {
                    "clear": "sunny day vibes music",
                    "sun": "sunny afternoon music",
                    "clouds": "cloudy day chill music",
                    "rain": "rainy day lofi music",
                    "drizzle": "light rain ambience",
                    "thunderstorm": "thunderstorm cozy music",
                    "snow": "snowy day peaceful music",
                    "mist": "foggy morning ambient music",
                    "fog": "foggy atmosphere music"
                }
                
                # Find the closest matching vibe
                for condition_key, vibe_phrase in vibe_mapping.items():
                    if condition_key in weather_condition.lower():
                        query = vibe_phrase
                        break
                else:
                    query = f"{weather_condition} music vibes"
            
            # Execute search
            search_response = self.youtube.search().list(
                q=query,
                part="snippet",
                maxResults=1,
                type="video"
            ).execute()
            
            # Extract video information
            if search_response.get("items"):
                video = search_response["items"][0]
                video_id = video["id"]["videoId"]
                
                return {
                    "title": video["snippet"]["title"],
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "thumbnail": video["snippet"]["thumbnails"]["high"]["url"],
                    "channel": video["snippet"]["channelTitle"],
                    "query": query
                }
            else:
                return {"error": "No videos found", "query": query}
        
        except Exception as e:
            return {
                "error": str(e),
                "message": "Failed to find a matching YouTube video"
            }
```

This tool uses the YouTube API to find a video that matches the weather condition and mood.

Finally, create an __init__.py file in the weather_vibes/tools directory:

```
from .weather_tool import WeatherTool
from .recommendations_tool import RecommendationsTool
from .youtube_tool import YouTubeTool

```

When complete, move on to the next step where we'll create the agent.

