"""
Simple client example to test the Weather Vibes Agent.
"""
import sys
import json
import asyncio
import argparse
import requests

def check_server_health(base_url):
    """Check if the server is running."""
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✅ Server is running!")
            return True
        else:
            print(f"⚠️ Server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running. Please start the server first.")
        return False

def create_run(base_url, location, units="metric", verbose=False, max_recommendations=5):
    """Create a new run for the Weather Vibes agent."""
    payload = {
        "agent_id": "weather_vibes",
        "input": {
            "location": location,
            "units": units
        },
        "config": {
            "verbose": verbose,
            "max_recommendations": max_recommendations
        }
    }
    
    response = requests.post(f"{base_url}/runs", json=payload)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error creating run: {response.status_code} - {response.text}")
        return None

def wait_for_run(base_url, run_id):
    """Wait for a run to complete and get the results."""
    response = requests.get(f"{base_url}/runs/{run_id}/wait")
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error waiting for run: {response.status_code} - {response.text}")
        return None

def print_weather_info(weather):
    """Pretty print weather information."""
    print("\n🌤️  WEATHER INFORMATION")
    print(f"📍 Location: {weather.get('location')}")
    print(f"🌡️  Temperature: {weather.get('temperature')}°")
    print(f"☁️  Condition: {weather.get('condition')}")
    print(f"💧 Humidity: {weather.get('humidity')}%")
    print(f"💨 Wind Speed: {weather.get('wind_speed')} m/s")

def print_recommendations(recommendations):
    """Pretty print recommendations."""
    print("\n🧳 RECOMMENDED ITEMS")
    for item in recommendations:
        print(f"  • {item}")

def print_video(video):
    """Pretty print video information."""
    print("\n🎵 MATCHING YOUTUBE VIDEO")
    print(f"🎬 Title: {video.get('title')}")
    print(f"🔗 URL: {video.get('url')}")
    print(f"📺 Channel: {video.get('channel')}")

def main():
    """Run the client example."""
    parser = argparse.ArgumentParser(description="Weather Vibes Client Example")
    parser.add_argument("location", help="Location to get weather for")
    parser.add_argument("--units", choices=["metric", "imperial"], default="metric", 
                        help="Units for temperature (metric or imperial)")
    parser.add_argument("--verbose", action="store_true", help="Include detailed weather information")
    parser.add_argument("--recommendations", type=int, default=5, 
                        help="Maximum number of recommendations")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    
    args = parser.parse_args()
    base_url = f"http://{args.host}:{args.port}"
    
    # Check if server is running
    if not check_server_health(base_url):
        return
    
    # Create a new run
    print(f"🔍 Getting weather vibes for {args.location}...")
    run_info = create_run(
        base_url, 
        args.location, 
        args.units, 
        args.verbose, 
        args.recommendations
    )
    
    if not run_info:
        return
    
    run_id = run_info.get("id")
    print(f"⏳ Run created with ID: {run_id}, waiting for results...")
    
    # Wait for results
    result = wait_for_run(base_url, run_id)
    
    if not result:
        return
    
    if result.get("type") == "error":
        print(f"❌ Error: {result.get('message')}")
        return
    
    # Print results
    data = result.get("result", {})
    weather = data.get("weather", {})
    recommendations = data.get("recommendations", [])
    video = data.get("video", {})
    
    print_weather_info(weather)
    print_recommendations(recommendations)
    print_video(video)
    
    print("\n✨ Done! This is powered by Galileo for evaluation and monitoring.")

if __name__ == "__main__":
    main() 