"""
A2A Summit Demo: Multi-Agent Real-Time Tourist Scheduling (Python version)

Demonstrates a multi-agent system using Agent-to-Agent communication to match
tourists with guide activities in near real-time, respecting budgets, preferences,
and availability constraints.

Agents:
- TouristAgent (A): Represents tourists, publishes requests, accepts proposals
- GuideAgent (B): Represents guides, publishes activity offers
- SchedulerAgent (C): Cloud coordinator, runs matching algorithms, proposes schedules

Architecture:
- transport.Bus abstraction for pub/sub messaging (in-memory default, A2A SDK ready)
- Greedy scheduling with preference scoring
- Real-time re-scheduling on late arrivals
"""

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict
from transport import MemoryBus, Bus

# ============================================================================
# Message Schemas (dataclasses matching Go structs)
# ============================================================================

@dataclass
class Window:
    start: datetime
    end: datetime

    def to_dict(self):
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat()
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            start=datetime.fromisoformat(d["start"]),
            end=datetime.fromisoformat(d["end"])
        )


@dataclass
class TouristRequest:
    tourist_id: str
    availability: List[Window]
    budget: int
    preferences: List[str]

    def to_dict(self):
        return {
            "tourist_id": self.tourist_id,
            "availability": [w.to_dict() for w in self.availability],
            "budget": self.budget,
            "preferences": self.preferences
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            tourist_id=d["tourist_id"],
            availability=[Window.from_dict(w) for w in d["availability"]],
            budget=d["budget"],
            preferences=d["preferences"]
        )


@dataclass
class GuideOffer:
    guide_id: str
    activity_id: str
    title: str
    tags: List[str]
    duration_minutes: int
    cost_per_person: int
    capacity: int
    slots: List[datetime]

    def to_dict(self):
        return {
            "guide_id": self.guide_id,
            "activity_id": self.activity_id,
            "title": self.title,
            "tags": self.tags,
            "duration_minutes": self.duration_minutes,
            "cost_per_person": self.cost_per_person,
            "capacity": self.capacity,
            "slots": [s.isoformat() for s in self.slots]
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            guide_id=d["guide_id"],
            activity_id=d["activity_id"],
            title=d["title"],
            tags=d["tags"],
            duration_minutes=d["duration_minutes"],
            cost_per_person=d["cost_per_person"],
            capacity=d["capacity"],
            slots=[datetime.fromisoformat(s) for s in d["slots"]]
        )


@dataclass
class Assignment:
    tourist_id: str
    activity_id: str
    start: datetime
    end: datetime
    cost: int
    title: str

    def to_dict(self):
        return {
            "tourist_id": self.tourist_id,
            "activity_id": self.activity_id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "cost": self.cost,
            "title": self.title
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            tourist_id=d["tourist_id"],
            activity_id=d["activity_id"],
            start=datetime.fromisoformat(d["start"]),
            end=datetime.fromisoformat(d["end"]),
            cost=d["cost"],
            title=d["title"]
        )


@dataclass
class ScheduleProposal:
    proposal_id: str
    assignments: List[Assignment]

    def to_dict(self):
        return {
            "proposal_id": self.proposal_id,
            "assignments": [a.to_dict() for a in self.assignments]
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            proposal_id=d["proposal_id"],
            assignments=[Assignment.from_dict(a) for a in d["assignments"]]
        )


# ============================================================================
# Global State
# ============================================================================

bus: Bus = MemoryBus()
requests: Dict[str, TouristRequest] = {}
offers: Dict[str, GuideOffer] = {}
assignments: List[Assignment] = []
budget_used: Dict[str, int] = {}


# ============================================================================
# Agent Functions
# ============================================================================

def tourist_agent_handler(payload: bytes):
    """Handles schedule_proposal messages (auto-accept)."""
    global assignments, budget_used
    prop = ScheduleProposal.from_dict(json.loads(payload))
    assignments = prop.assignments
    for a in prop.assignments:
        budget_used[a.tourist_id] = budget_used.get(a.tourist_id, 0) + a.cost
    print(f"[TouristAgent] Accepted proposal {prop.proposal_id} with {len(prop.assignments)} assignments")


def guide_agent_handler(payload: bytes):
    """Placeholder for guide reactions (currently passive)."""
    pass


# ============================================================================
# Scheduling Engine
# ============================================================================

def preference_score(prefs: List[str], tags: List[str]) -> float:
    """Calculate preference match ratio."""
    if not prefs:
        return 0.0
    match = sum(1 for p in prefs if p in tags)
    return match / len(prefs)


def is_available(req: TouristRequest, start: datetime, end: datetime) -> bool:
    """Check if time slot falls within tourist availability windows."""
    for w in req.availability:
        if start >= w.start and end <= w.end:
            return True
    return False


def times_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """Check if two time ranges overlap."""
    return a_start < b_end and b_start < a_end


def build_schedule(reqs: List[TouristRequest], offs: List[GuideOffer]) -> ScheduleProposal:
    """Greedy scheduling algorithm matching tourists to activities."""
    candidates = []

    # Generate all valid (tourist, activity slot) pairs with scores
    for req in reqs:
        for offer in offs:
            pref_score = preference_score(req.preferences, offer.tags)
            if pref_score == 0:
                continue

            for slot in offer.slots:
                end = slot + timedelta(minutes=offer.duration_minutes)
                if not is_available(req, slot, end):
                    continue

                cost = offer.cost_per_person
                remaining = req.budget - budget_used.get(req.tourist_id, 0) - cost
                if remaining < 0:
                    continue

                score = pref_score + (remaining / (req.budget + 1))
                candidates.append({
                    "assignment": Assignment(
                        tourist_id=req.tourist_id,
                        activity_id=offer.activity_id,
                        start=slot,
                        end=end,
                        cost=cost,
                        title=offer.title
                    ),
                    "score": score,
                    "offer_id": offer.activity_id
                })

    # Sort by score descending
    candidates.sort(key=lambda c: c["score"], reverse=True)

    # Greedy assignment with capacity and overlap checks
    capacity_used = {}
    assigned_per_tourist = {}
    result = []

    for cand in candidates:
        a = cand["assignment"]
        offer_id = cand["offer_id"]

        # Check capacity
        if capacity_used.get(offer_id, 0) >= next(o.capacity for o in offs if o.activity_id == offer_id):
            continue

        # Check overlaps for this tourist
        conflict = False
        for existing in assigned_per_tourist.get(a.tourist_id, []):
            if times_overlap(existing.start, existing.end, a.start, a.end):
                conflict = True
                break

        if conflict:
            continue

        # Accept assignment
        capacity_used[offer_id] = capacity_used.get(offer_id, 0) + 1
        if a.tourist_id not in assigned_per_tourist:
            assigned_per_tourist[a.tourist_id] = []
        assigned_per_tourist[a.tourist_id].append(a)
        result.append(a)

    proposal_id = f"p-{int(time.time() * 1000000)}"
    return ScheduleProposal(proposal_id=proposal_id, assignments=result)


async def scheduler_agent():
    """Periodically recomputes and publishes schedule proposals."""
    while True:
        await asyncio.sleep(1)

        reqs_copy = list(requests.values())
        offs_copy = list(offers.values())

        if not reqs_copy or not offs_copy:
            continue

        prop = build_schedule(reqs_copy, offs_copy)
        if not prop.assignments:
            continue

        payload = json.dumps(prop.to_dict()).encode('utf-8')
        bus.publish("schedule_proposal", payload)


# ============================================================================
# Publishing Helpers
# ============================================================================

def publish_tourist_request(req: TouristRequest):
    """Publish a tourist request and store in state."""
    requests[req.tourist_id] = req
    payload = json.dumps(req.to_dict()).encode('utf-8')
    bus.publish("tourist_request", payload)
    print(f"[TouristAgent] Published request for {req.tourist_id}")


def publish_guide_offer(offer: GuideOffer):
    """Publish a guide offer and store in state."""
    offers[offer.activity_id] = offer
    payload = json.dumps(offer.to_dict()).encode('utf-8')
    bus.publish("guide_offer", payload)
    print(f"[GuideAgent] Published offer {offer.activity_id} ({offer.title})")


# ============================================================================
# Demo Data Seeding
# ============================================================================

def seed_demo_data():
    """Populate initial tourists and guide offers."""
    now = datetime.now()

    # Tourists
    publish_tourist_request(TouristRequest(
        tourist_id="t1",
        availability=[Window(start=now, end=now + timedelta(hours=24))],
        budget=200,
        preferences=["culture", "food"]
    ))

    publish_tourist_request(TouristRequest(
        tourist_id="t2",
        availability=[Window(start=now, end=now + timedelta(hours=36))],
        budget=150,
        preferences=["outdoors", "adventure"]
    ))

    publish_tourist_request(TouristRequest(
        tourist_id="t3",
        availability=[Window(start=now + timedelta(hours=1), end=now + timedelta(hours=30))],
        budget=120,
        preferences=["food", "relax"]
    ))

    # Guide Offers
    base = now + timedelta(minutes=30)
    activities = [
        ("Museum Tour", ["culture"], 90, 60, 5),
        ("Wine Tasting", ["food"], 120, 80, 4),
        ("Mountain Hike", ["outdoors", "adventure"], 240, 100, 6),
        ("Cooking Class", ["food", "culture"], 150, 70, 5),
        ("City Walk", ["culture", "outdoors"], 180, 50, 8),
        ("Beach Yoga", ["relax"], 60, 40, 10),
    ]

    for i, (title, tags, duration, cost, capacity) in enumerate(activities):
        slots = [base + timedelta(hours=i*2 + s) for s in range(4)]
        publish_guide_offer(GuideOffer(
            guide_id=f"g{i+1}",
            activity_id=f"a{i+1}",
            title=title,
            tags=tags,
            duration_minutes=duration,
            cost_per_person=cost,
            capacity=capacity,
            slots=slots
        ))


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Run the multi-agent demo."""
    print("A2A Summit Demo: Multi-Agent Real-Time Tourist Scheduling (Python)")

    # Subscribe agents
    bus.subscribe("schedule_proposal", tourist_agent_handler)
    bus.subscribe("guide_offer", guide_agent_handler)

    # Seed data
    seed_demo_data()

    # Start scheduler
    scheduler_task = asyncio.create_task(scheduler_agent())

    # Run simulation
    await asyncio.sleep(3)
    print("--- Simulating late tourist arrival ---")
    now = datetime.now()
    publish_tourist_request(TouristRequest(
        tourist_id="t4",
        availability=[Window(start=now + timedelta(hours=2), end=now + timedelta(hours=10))],
        budget=180,
        preferences=["culture", "food"]
    ))

    # Allow reschedule
    await asyncio.sleep(2)
    print("--- Final Assignments ---")
    for a in assignments:
        print(f"Tourist {a.tourist_id} -> {a.title} at {a.start.strftime('%d %b %y %H:%M')} (cost {a.cost})")

    scheduler_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
