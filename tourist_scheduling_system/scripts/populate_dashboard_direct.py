#!/usr/bin/env python3
"""
Direct dashboard population test - sends data directly to UI Agent
to demonstrate real-time dashboard functionality
"""
import json
import requests
import time
from datetime import datetime, timedelta
from messages import TouristRequest, GuideOffer, ScheduleProposal, Assignment, Window

def populate_dashboard_directly():
    """Send data directly to UI Agent to show dashboard working"""

    ui_agent_url = "http://localhost:10012"  # UI Agent A2A port

    print("🎯 Populating Dashboard with Live Data")
    print("=====================================")

    # Test data
    now = datetime.now()

    # Guide offers
    guides = [
        GuideOffer(
            guide_id="guide-001",
            categories=["culture", "history"],
            available_window=Window(start=now, end=now + timedelta(hours=4)),
            hourly_rate=75.0,
            max_group_size=6
        ),
        GuideOffer(
            guide_id="guide-002",
            categories=["food", "culture"],
            available_window=Window(start=now + timedelta(hours=1), end=now + timedelta(hours=5)),
            hourly_rate=85.0,
            max_group_size=4
        ),
        GuideOffer(
            guide_id="guide-003",
            categories=["outdoors", "adventure"],
            available_window=Window(start=now + timedelta(hours=2), end=now + timedelta(hours=6)),
            hourly_rate=95.0,
            max_group_size=8
        )
    ]

    # Tourist requests
    tourists = [
        TouristRequest(
            tourist_id="tourist-001",
            availability=[Window(start=now, end=now + timedelta(hours=6))],
            budget=300,
            preferences=["culture", "history"]
        ),
        TouristRequest(
            tourist_id="tourist-002",
            availability=[Window(start=now + timedelta(hours=1), end=now + timedelta(hours=7))],
            budget=250,
            preferences=["food", "culture"]
        ),
        TouristRequest(
            tourist_id="tourist-003",
            availability=[Window(start=now + timedelta(hours=2), end=now + timedelta(hours=8))],
            budget=400,
            preferences=["outdoors", "adventure"]
        )
    ]

    def send_message(data_dict):
        """Send message to UI Agent"""
        try:
            response = requests.post(
                f"{ui_agent_url}/",
                json={
                    "jsonrpc": "2.0",
                    "id": f"test-{int(time.time())}",
                    "method": "message/send",
                    "params": {
                        "message": {
                            "role": "user",
                            "parts": [{"kind": "text", "text": json.dumps(data_dict)}],
                            "messageId": f"msg-{int(time.time())}"
                        }
                    }
                },
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False

    # Send guide offers
    print("🗺️ Sending Guide Offers...")
    for guide in guides:
        print(f"   📤 {guide.guide_id}: {', '.join(guide.categories)} (${guide.hourly_rate}/hr)")
        success = send_message(guide.to_dict())
        if success:
            print("      ✅ Sent successfully")
        time.sleep(0.5)

    print()

    # Send tourist requests
    print("👥 Sending Tourist Requests...")
    for tourist in tourists:
        print(f"   📤 {tourist.tourist_id}: {', '.join(tourist.preferences)} (${tourist.budget} budget)")
        success = send_message(tourist.to_dict())
        if success:
            print("      ✅ Sent successfully")
        time.sleep(0.5)

    print()

    # Create and send assignments
    print("📋 Creating Schedule Assignments...")
    assignments = [
        Assignment(
            tourist_id="tourist-001",
            guide_id="guide-001",
            time_window=Window(start=now, end=now + timedelta(hours=2)),
            categories=["culture", "history"],
            total_cost=150.0
        ),
        Assignment(
            tourist_id="tourist-002",
            guide_id="guide-002",
            time_window=Window(start=now + timedelta(hours=1), end=now + timedelta(hours=3)),
            categories=["food", "culture"],
            total_cost=170.0
        ),
        Assignment(
            tourist_id="tourist-003",
            guide_id="guide-003",
            time_window=Window(start=now + timedelta(hours=2), end=now + timedelta(hours=4)),
            categories=["outdoors", "adventure"],
            total_cost=190.0
        )
    ]

    proposal = ScheduleProposal(
        proposal_id=f"demo-proposal-{int(time.time())}",
        assignments=assignments
    )

    print(f"   📤 Proposal with {len(assignments)} assignments")
    success = send_message(proposal.to_dict())
    if success:
        print("      ✅ Sent successfully")

    print()
    print("🎉 Dashboard Population Complete!")
    print("📊 Check http://localhost:10011 to see the live updates!")
    print()
    print("Expected Dashboard Data:")
    print(f"   📈 Total Tourists: {len(tourists)}")
    print(f"   📈 Available Guides: {len(guides)}")
    print(f"   📈 Active Assignments: {len(assignments)}")
    print(f"   📈 Satisfaction Rate: 100% ({len(assignments)}/{len(tourists)})")
    print(f"   📈 Average Cost: ${sum(a.total_cost for a in assignments)/len(assignments):.0f}")

if __name__ == "__main__":
    populate_dashboard_directly()