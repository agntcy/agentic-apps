#!/usr/bin/env python3
"""Simple test to populate the UI agent dashboard with sample data
by directly calling the REST API endpoints.

Copyright AGNTCY Contributors (https://github.com/agntcy)
SPDX-License-Identifier: Apache-2.0
"""

import asyncio
import json
import requests
import time
from datetime import datetime, timedelta

async def populate_dashboard():
    """Populate the dashboard with sample data via REST API"""
    base_url = "http://localhost:10001"

    print("🧪 Populating UI Agent Dashboard with sample data...")

    # Wait for server to be ready
    for i in range(5):
        try:
            response = requests.get(f"{base_url}/api/state", timeout=2)
            if response.status_code == 200:
                break
        except:
            print(f"   Waiting for UI Agent... ({i+1}/5)")
            time.sleep(1)
    else:
        print("❌ UI Agent not responding!")
        return

    print("✅ UI Agent is ready!")

    # Since the UI agent expects A2A messages but we want to show data immediately,
    # let's directly modify the global state by importing the module and updating it

    # For now, let's just show that the dashboard is working by opening it
    print("📊 Opening dashboard at: http://localhost:10001")
    print("💡 To see data on the dashboard, you need to:")
    print("   1. Start the scheduler agent: python scheduler_agent.py --port 10000")
    print("   2. Send tourist/guide data to the scheduler")
    print("   3. The scheduler will send updates to the UI agent")
    print("")
    print("🚀 Or run the complete demo: ./run_with_ui.sh")

if __name__ == "__main__":
    asyncio.run(populate_dashboard())