#!/usr/bin/env python3
"""
Simple synchronous guide offer sender for testing
"""
import json
import os
import sys
import requests
from datetime import datetime, timedelta

# Add src directory to path so we can import our messages
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from a2a_summit_demo.core.messages import GuideOffer, Window

def send_guide_offer():
    """Send a guide offer to the scheduler via HTTP"""

    # Create guide offer
    offer = GuideOffer(
        guide_id="demo-guide-1",
        categories=["culture", "history", "food"],
        available_window=Window(
            start=datetime(2025, 12, 1, 10, 0),
            end=datetime(2025, 12, 1, 16, 0)
        ),
        hourly_rate=85.0,
        max_group_size=8
    )

    print(f"🗺️ Sending Guide Offer: {offer.guide_id}")
    print(f"   Categories: {', '.join(offer.categories)}")
    print(f"   Rate: ${offer.hourly_rate}/hour")
    print(f"   Capacity: {offer.max_group_size} people")

    # Send via HTTP POST (simulating A2A message)
    try:
        response = requests.post(
            "http://localhost:10010/",
            json={
                "jsonrpc": "2.0",
                "id": "guide-test-1",
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": offer.to_json()}],
                        "messageId": "guide-msg-1"
                    }
                }
            },
            timeout=10
        )

        if response.status_code == 200:
            print("✅ Guide offer sent successfully!")
            return True
        else:
            print(f"❌ Failed to send guide offer: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error sending guide offer: {e}")
        return False

if __name__ == "__main__":
    send_guide_offer()