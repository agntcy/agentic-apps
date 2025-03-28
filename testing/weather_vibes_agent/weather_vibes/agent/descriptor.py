"""
Agent ACP Descriptor for the Weather Vibes agent.
This defines the agent's capabilities, inputs, outputs, and configuration.
"""

WEATHER_VIBES_DESCRIPTOR = {
    "metadata": {
        "ref": {
            "name": "org.example.weathervibes",
            "version": "0.1.0",
            "url": "https://github.com/agntcy/agentic-apps/weather_vibes"
        },
        "description": "An agent that provides weather information, item recommendations, and matching YouTube videos."
    },
    "specs": {
        "capabilities": {
            "threads": True,
            "interrupts": False,
            "callbacks": False,
            "streaming": True
        },
        "input": {
            "type": "object",
            "description": "Input for the Weather Vibes agent",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The location to get weather for (city name, zip code, etc.)"
                },
                "units": {
                    "type": "string",
                    "enum": ["metric", "imperial"],
                    "default": "metric",
                    "description": "Unit system for temperature and measurements"
                }
            },
            "required": ["location"]
        },
        "output": {
            "type": "object",
            "description": "Weather Vibes agent output",
            "properties": {
                "weather": {
                    "type": "object",
                    "description": "Current weather information",
                    "properties": {
                        "location": {"type": "string"},
                        "temperature": {"type": "number"},
                        "condition": {"type": "string"},
                        "humidity": {"type": "number"},
                        "wind_speed": {"type": "number"}
                    }
                },
                "recommendations": {
                    "type": "array",
                    "description": "Items recommended to bring based on the weather",
                    "items": {"type": "string"}
                },
                "video": {
                    "type": "object",
                    "description": "A YouTube video matching the weather vibe",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "thumbnail": {"type": "string"}
                    }
                }
            }
        },
        "config": {
            "type": "object",
            "description": "Configuration for the Weather Vibes agent",
            "properties": {
                "verbose": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to include detailed weather information"
                },
                "max_recommendations": {
                    "type": "integer",
                    "default": 5,
                    "description": "Maximum number of recommendations to provide"
                },
                "video_mood": {
                    "type": "string",
                    "description": "Optional mood override for video selection"
                }
            }
        },
        "thread_state": {
            "type": "object",
            "description": "Thread state for the Weather Vibes agent",
            "properties": {
                "search_history": {
                    "type": "array",
                    "description": "History of previously searched locations",
                    "items": {"type": "string"}
                },
                "favorite_locations": {
                    "type": "array",
                    "description": "User's favorite locations",
                    "items": {"type": "string"}
                }
            }
        }
    }
}
