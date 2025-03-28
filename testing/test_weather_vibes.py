# test_weather_vibes.py
import requests
import json
import time
import argparse
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class WeatherVibesTest:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.test_results = {}
        self.agent_id = "weather_vibes"
        
    def run_all_tests(self):
        """Run all tests and print summary"""
        print("🧪 Starting Weather Vibes ACP Compliance Tests\n")
        
        self.test_agent_search()
        self.test_agent_descriptor()
        self.test_basic_run()
        
        # Print results summary
        print("\n📊 Test Results Summary:")
        passed = sum(1 for result in self.test_results.values() if result)
        total = len(self.test_results)
        print(f"✅ Passed: {passed}/{total} tests")
        
        if passed == total:
            print("🎉 All tests passed! The agent is ACP compliant.")
        else:
            print("⚠️ Some tests failed. See details above.")
            for test, result in self.test_results.items():
                if not result:
                    print(f"❌ Failed: {test}")
    
    def test_agent_search(self):
        """Test the agent search endpoint"""
        print("🔍 Testing agent search endpoint...")
        
        try:
            response = requests.post(f"{self.base_url}/agents/search", json={})
            response.raise_for_status()
            data = response.json()
            
            # Check if the agent is in the list
            agents = data.get("agents", [])
            found = any(agent["id"] == self.agent_id for agent in agents)
            
            if found:
                print("✅ Agent found in search results")
                self.test_results["agent_search"] = True
            else:
                print("❌ Agent not found in search results")
                self.test_results["agent_search"] = False
                
            return found
        except Exception as e:
            print(f"❌ Error testing agent search: {e}")
            self.test_results["agent_search"] = False
            return False
            
    def test_agent_descriptor(self):
        """Test the agent descriptor endpoint"""
        print("\n📝 Testing agent descriptor endpoint...")
        
        try:
            response = requests.get(f"{self.base_url}/agents/{self.agent_id}/descriptor")
            response.raise_for_status()
            descriptor = response.json()
            
            # Check for required fields in the descriptor
            has_metadata = "metadata" in descriptor
            has_specs = "specs" in descriptor
            has_input_schema = "input" in descriptor.get("specs", {})
            has_output_schema = "output" in descriptor.get("specs", {})
            
            if all([has_metadata, has_specs, has_input_schema, has_output_schema]):
                print("✅ Agent descriptor contains all required fields")
                self.test_results["agent_descriptor"] = True
            else:
                print("❌ Agent descriptor is missing required fields")
                self.test_results["agent_descriptor"] = False
                
            return descriptor
        except Exception as e:
            print(f"❌ Error testing agent descriptor: {e}")
            self.test_results["agent_descriptor"] = False
            return None
            
    def test_basic_run(self):
        """Test a basic run with the agent"""
        print("\n🚀 Testing basic run execution...")
        
        try:
            # Create a run
            payload = {
                "agent_id": self.agent_id,
                "input": {
                    "location": "London",
                    "units": "metric"
                },
                "config": {
                    "verbose": True,
                    "max_recommendations": 3
                }
            }
            
            print("  Creating run...")
            run_response = requests.post(f"{self.base_url}/runs", json=payload)
            run_response.raise_for_status()
            run_data = run_response.json()
            
            run_id = run_data.get("id")
            if not run_id:
                print("❌ No run ID returned")
                self.test_results["run_creation"] = False
                return False
                
            print(f"  Run created with ID: {run_id}")
            self.test_results["run_creation"] = True
            
            # Poll for completion
            print("  Waiting for run completion...")
            max_attempts = 30
            for attempt in range(max_attempts):
                status_response = requests.get(f"{self.base_url}/runs/{run_id}")
                status_data = status_response.json()
                
                if status_data.get("status") != "pending":
                    break
                    
                print(f"  Checking status: {status_data.get('status')} (attempt {attempt+1})")
                time.sleep(1)
            
            # Get results
            print("  Retrieving run results...")
            results_response = requests.get(f"{self.base_url}/runs/{run_id}/wait")
            results_data = results_response.json()
            
            has_result = results_data.get("type") == "result" and "result" in results_data
            has_weather = "weather" in results_data.get("result", {})
            has_recommendations = "recommendations" in results_data.get("result", {})
            has_video = "video" in results_data.get("result", {})
            
            if all([has_result, has_weather, has_recommendations, has_video]):
                print("✅ Run completed successfully with all expected data")
                self.test_results["run_execution"] = True
                
                # Print a sample of the results
                weather = results_data["result"]["weather"]
                recs = results_data["result"]["recommendations"]
                video = results_data["result"]["video"]
                
                print(f"\n📍 Weather for {weather['location']}: {weather['temperature']}°C, {weather['condition']}")
                print(f"🧳 Top recommendations: {', '.join(recs[:3])}")
                print(f"🎵 Suggested video: {video['title']}")
                
                return True
            else:
                print("❌ Run results missing expected data")
                self.test_results["run_execution"] = False
                return False
                
        except Exception as e:
            print(f"❌ Error testing run execution: {e}")
            self.test_results["run_execution"] = False
            return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Weather Vibes ACP Compliance")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the Weather Vibes server")
    args = parser.parse_args()
    
    tester = WeatherVibesTest(base_url=args.url)
    tester.run_all_tests()
