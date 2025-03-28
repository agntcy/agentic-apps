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
