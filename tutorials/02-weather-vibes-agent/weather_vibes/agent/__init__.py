"""
Agent module initialization
"""
# Make the descriptor easily importable
try:
    from .descriptor import WEATHER_VIBES_DESCRIPTOR
except ImportError:
    pass  # Handle the case if the file doesn't exist yet

# Agent package
"""Weather Vibes Agent Implementation Package"""

# Import the agent class for easier access
from .weather_vibes_agent import WeatherVibesAgent 