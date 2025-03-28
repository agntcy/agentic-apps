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
