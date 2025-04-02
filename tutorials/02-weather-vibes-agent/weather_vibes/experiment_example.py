"""
Example script demonstrating how to run experiments using Galileo with the Weather Vibes agent.
This allows you to compare different implementations or configurations.
"""
import os
import asyncio
from dotenv import load_dotenv
from galileo import Experiment, galileo_context

# Import our Weather Vibes Agent
try:
    from agent.weather_vibes_agent import WeatherVibesAgent
except ImportError:
    try:
        from weather_vibes.agent.weather_vibes_agent import WeatherVibesAgent
    except ImportError:
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from agent.weather_vibes_agent import WeatherVibesAgent

# Load environment variables
load_dotenv()

async def compare_model_versions():
    """
    Run an experiment to compare different model versions for the Weather Vibes agent.
    """
    # Create our experiment
    experiment = Experiment(
        name="Model Performance Comparison",
        description="Comparing GPT-4 vs GPT-3.5-Turbo for recommendation quality"
    )
    
    # Request to process
    test_request = {
        "agent_id": "weather_vibes",
        "input": {
            "location": "San Francisco",
            "units": "metric"
        },
        "config": {
            "verbose": True,
            "max_recommendations": 5
        }
    }
    
    # Create an agent with GPT-4o
    agent_gpt4 = WeatherVibesAgent(agent_id="weather_vibes_gpt4")
    # Set model to GPT-4o (this assumes client is set in __init__)
    agent_gpt4.client.chat.completions.create = lambda **kwargs: agent_gpt4.client.chat.completions.create(
        **{**kwargs, "model": "gpt-4o"}
    )
    
    # Create an agent with GPT-3.5-Turbo
    agent_gpt3 = WeatherVibesAgent(agent_id="weather_vibes_gpt3")
    # Set model to GPT-3.5-Turbo
    agent_gpt3.client.chat.completions.create = lambda **kwargs: agent_gpt3.client.chat.completions.create(
        **{**kwargs, "model": "gpt-3.5-turbo"}
    )
    
    # Run the baseline variant with GPT-4o
    with experiment.variant("gpt4o"):
        with galileo_context():
            gpt4_response = await agent_gpt4.process_acp_request(test_request)
            print(f"GPT-4o Response: {gpt4_response}")
    
    # Run the test variant with GPT-3.5-Turbo
    with experiment.variant("gpt35turbo"):
        with galileo_context():
            gpt3_response = await agent_gpt3.process_acp_request(test_request)
            print(f"GPT-3.5-Turbo Response: {gpt3_response}")
    
    print("Experiment completed! Check Galileo dashboard for results.")

async def compare_recommendation_algorithms():
    """
    Run an experiment to compare different recommendation algorithms.
    """
    # Create our experiment
    experiment = Experiment(
        name="Recommendation Algorithm Comparison",
        description="Comparing basic vs. enhanced recommendation algorithms"
    )
    
    # Test with a rainy location
    test_request = {
        "agent_id": "weather_vibes",
        "input": {
            "location": "Seattle",
            "units": "metric"
        },
        "config": {
            "verbose": True,
            "max_recommendations": 5
        }
    }
    
    # Create agents with different recommendation logic
    agent_basic = WeatherVibesAgent(agent_id="weather_vibes_basic")
    agent_enhanced = WeatherVibesAgent(agent_id="weather_vibes_enhanced")
    
    # Modify the enhanced agent's recommendation tool (this is simplified)
    # In a real implementation, you would create a different recommendation tool class
    recommendations_tool = agent_enhanced.tool_registry.get_tool("get_recommendations")
    original_execute = recommendations_tool.execute
    
    async def enhanced_execute(*args, **kwargs):
        """Enhanced recommendation logic with more personalized suggestions"""
        # Get original recommendations
        recommendations = await original_execute(*args, **kwargs)
        
        # Add some premium recommendations
        weather = kwargs.get('weather', {})
        if weather.get('condition') == 'Rain':
            recommendations = ["Premium Umbrella", "Waterproof Boots"] + recommendations
        
        return recommendations[:kwargs.get('max_items', 5)]
    
    # Replace the execute method
    recommendations_tool.execute = enhanced_execute
    
    # Run the baseline variant
    with experiment.variant("basic_algorithm"):
        with galileo_context():
            basic_response = await agent_basic.process_acp_request(test_request)
            print(f"Basic Algorithm Response: {basic_response}")
    
    # Run the enhanced variant
    with experiment.variant("enhanced_algorithm"):
        with galileo_context():
            enhanced_response = await agent_enhanced.process_acp_request(test_request)
            print(f"Enhanced Algorithm Response: {enhanced_response}")
    
    print("Recommendation algorithm experiment completed! Check Galileo dashboard for results.")

async def main():
    """Run all experiments"""
    print("Starting Galileo experiments with Weather Vibes agent...")
    
    await compare_model_versions()
    await compare_recommendation_algorithms()
    
    print("All experiments completed!")

if __name__ == "__main__":
    asyncio.run(main()) 