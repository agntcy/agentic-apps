"""
Example client for interacting with the Weather Vibes agent via ACP.
"""
import os
import json
import asyncio
import argparse
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def main(location, units="metric", verbose=False):
    """
    Main function to run the client example.
    """
    # Server URL
    base_url = "http://localhost:8000"
    
    # Step 1: Search for the Weather Vibes agent
    print("🔍 Searching for Weather Vibes agent...")
    search_response = requests.post(f"{base_url}/agents/search", json={})
    search_data = search_response.json()
    
    if not search_data.get("agents"):
        print("❌ No agents found. Is the server running?")
        return
    
    # Get the agent ID
    agent_id = search_data["agents"][0]["id"]
    print(f"✅ Found agent: {agent_id}")
    
    # Step 2: Start a run
    print(f"\n🚀 Starting Weather Vibes request for location: {location}...")
    
    run_payload = {
        "agent_id": agent_id,
        "input": {
            "location": location,
            "units": units
        },
        "config": {
            "verbose": verbose,
            "max_recommendations": 5
        }
    }
    
    run_response = requests.post(f"{base_url}/runs", json=run_payload)
    run_data = run_response.json()
    
    run_id = run_data["id"]
    print(f"✅ Started run with ID: {run_id}")
    
    # Step 3: Wait for run completion
    print("\n⏳ Waiting for results...")
    
    # Poll the run status until complete
    max_attempts = 30
    for attempt in range(max_attempts):
        # Check run status
        status_response = requests.get(f"{base_url}/runs/{run_id}")
        status_data = status_response.json()
        
        if status_data["status"] != "pending":
            break
            
        # Simple progress animation
        print(f"\r⏳ Processing... {'.' * (attempt % 4 + 1)}{' ' * (3 - attempt % 4)}", end="")
        await asyncio.sleep(1)
    
    # Step 4: Get the results
    print("\r", end="")  # Clear the progress line
    results_response = requests.get(f"{base_url}/runs/{run_id}/wait")
    results_data = results_response.json()
    
    if results_data.get("type") == "error":
        print(f"❌ Error: {results_data.get('message', 'Unknown error')}")
        return
    
    # Step 5: Display the results
    print("\n🌤️  Weather Vibes Results 🎵\n")
    
    # Weather information
    weather = results_data["result"]["weather"]
    print(f"📍 Location: {weather['location']}")
    print(f"🌡️  Temperature: {weather['temperature']}°{'C' if units == 'metric' else 'F'}")
    print(f"☁️  Condition: {weather['condition']}")
    print(f"💧 Humidity: {weather['humidity']}%")
    print(f"💨 Wind: {weather['wind_speed']} {'m/s' if units == 'metric' else 'mph'}")
    
    # Recommendations
    print("\n🎒 Recommended Items:")
    for item in results_data["result"]["recommendations"]:
        print(f"  ✓ {item}")
    
    # YouTube video
    video = results_data["result"]["video"]
    print("\n🎵 Matching Weather Vibe:")
    print(f"  🎬 {video['title']}")
    print(f"  🔗 {video['url']}")
    
    print("\n✅ Weather Vibes request complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weather Vibes Client Example")
    parser.add_argument("location", help="Location to get weather for")
    parser.add_argument("--units", choices=["metric", "imperial"], default="metric", help="Units for temperature")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    asyncio.run(main(args.location, args.units, args.verbose))
