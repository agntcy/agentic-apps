#!/usr/bin/env python3
"""
Test script for UI Agent

This script demonstrates how the UI Agent works by sending sample messages
to test the real-time dashboard functionality.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
import httpx

from messages import TouristRequest, GuideOffer, ScheduleProposal, Assignment, Window


async def test_ui_agent():
    """Test the UI agent by sending sample messages"""

    ui_agent_url = "http://localhost:10002"  # A2A port for UI agent

    print("🧪 Testing UI Agent Real-time Dashboard")
    print("=====================================")

    # Wait for UI agent to be ready
    print("⏳ Waiting for UI Agent to start...")
    for i in range(10):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{ui_agent_url}/health", timeout=5.0)
                if response.status_code == 200:
                    break
        except Exception:
            pass
        await asyncio.sleep(1)
    else:
        print("❌ UI Agent not responding, make sure it's running on port 10002")
        return

    print("✅ UI Agent is ready!")
    print("📊 Dashboard available at: http://localhost:10001")
    print()

    # Create sample data
    now = datetime.now()

    # Sample tourist requests
    tourists = [
        TouristRequest(
            tourist_id="t1",
            availability=[Window(start=now, end=now + timedelta(hours=8))],
            budget=200,
            preferences=["culture", "food"]
        ),
        TouristRequest(
            tourist_id="t2",
            availability=[Window(start=now + timedelta(hours=1), end=now + timedelta(hours=10))],
            budget=150,
            preferences=["outdoors", "adventure"]
        ),
        TouristRequest(
            tourist_id="t3",
            availability=[Window(start=now + timedelta(minutes=30), end=now + timedelta(hours=6))],
            budget=300,
            preferences=["culture", "relax"]
        )
    ]

    # Sample guide offers
    guides = [
        GuideOffer(
            guide_id="g1",
            categories=["culture", "food"],
            available_window=Window(start=now, end=now + timedelta(hours=4)),
            hourly_rate=80.0,
            max_group_size=6
        ),
        GuideOffer(
            guide_id="g2",
            categories=["outdoors", "adventure"],
            available_window=Window(start=now + timedelta(hours=1), end=now + timedelta(hours=5)),
            hourly_rate=100.0,
            max_group_size=4
        ),
        GuideOffer(
            guide_id="g3",
            categories=["culture", "relax"],
            available_window=Window(start=now + timedelta(minutes=30), end=now + timedelta(hours=3)),
            hourly_rate=60.0,
            max_group_size=8
        )
    ]

    async def send_message(message_data: dict):
        """Send a message to the UI agent"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{ui_agent_url}/execute",
                    json={
                        "message": {
                            "parts": [{
                                "text": json.dumps(message_data)
                            }]
                        }
                    },
                    timeout=10.0
                )
                return response.status_code == 200
            except Exception as e:
                print(f"❌ Error sending message: {e}")
                return False

    # Send tourist requests
    print("👥 Sending tourist requests...")
    for i, tourist in enumerate(tourists, 1):
        print(f"   📤 Sending tourist {tourist.tourist_id}")
        success = await send_message(tourist.to_dict())
        if success:
            print(f"   ✅ Tourist {tourist.tourist_id} sent successfully")
        else:
            print(f"   ❌ Failed to send tourist {tourist.tourist_id}")
        await asyncio.sleep(1)

    print()

    # Send guide offers
    print("🗺️  Sending guide offers...")
    for guide in guides:
        print(f"   📤 Sending guide {guide.guide_id}")
        success = await send_message(guide.to_dict())
        if success:
            print(f"   ✅ Guide {guide.guide_id} sent successfully")
        else:
            print(f"   ❌ Failed to send guide {guide.guide_id}")
        await asyncio.sleep(1)

    print()

    # Create and send a sample schedule proposal
    print("📋 Sending schedule proposal...")
    assignments = [
        Assignment(
            tourist_id="t1",
            guide_id="g1",
            time_window=Window(start=now, end=now + timedelta(hours=2)),
            categories=["culture", "food"],
            total_cost=160.0
        ),
        Assignment(
            tourist_id="t2",
            guide_id="g2",
            time_window=Window(start=now + timedelta(hours=1), end=now + timedelta(hours=3)),
            categories=["outdoors", "adventure"],
            total_cost=200.0
        ),
    ]

    proposal = ScheduleProposal(
        proposal_id=f"test-proposal-{int(time.time())}",
        assignments=assignments
    )

    success = await send_message(proposal.to_dict())
    if success:
        print("   ✅ Schedule proposal sent successfully")
    else:
        print("   ❌ Failed to send schedule proposal")

    print()
    print("🎉 Test complete!")
    print("📊 Check the dashboard at http://localhost:10001 to see the updates")
    print("💡 The dashboard should show real-time metrics and data")


if __name__ == "__main__":
    asyncio.run(test_ui_agent())