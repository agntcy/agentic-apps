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
