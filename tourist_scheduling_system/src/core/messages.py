# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Shared message schemas for the Multi-Agent Tourist Scheduling System.

All agents import these dataclasses to ensure consistent message format
when communicating via the A2A protocol.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class Window:
    """Time window for tourist availability."""
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
    """Message from tourist agent requesting schedule."""
    tourist_id: str
    availability: List[Window]
    budget: float
    preferences: List[str]

    def to_dict(self):
        return {
            "type": "TouristRequest",
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

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, s: str):
        return cls.from_dict(json.loads(s))


@dataclass
class GuideOffer:
    """Message from guide agent offering services."""
    guide_id: str
    categories: List[str]
    available_window: Window
    hourly_rate: float
    max_group_size: int

    def to_dict(self):
        return {
            "type": "GuideOffer",
            "guide_id": self.guide_id,
            "categories": self.categories,
            "available_window": self.available_window.to_dict(),
            "hourly_rate": self.hourly_rate,
            "max_group_size": self.max_group_size
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, d):
        return cls(
            guide_id=d["guide_id"],
            categories=d["categories"],
            available_window=Window.from_dict(d["available_window"]),
            hourly_rate=d["hourly_rate"],
            max_group_size=d["max_group_size"]
        )

    @classmethod
    def from_json(cls, s: str):
        return cls.from_dict(json.loads(s))


@dataclass
class Assignment:
    """Single tourist-guide assignment."""
    tourist_id: str
    guide_id: str
    time_window: Window
    categories: List[str]
    total_cost: float

    def to_dict(self):
        return {
            "tourist_id": self.tourist_id,
            "guide_id": self.guide_id,
            "time_window": self.time_window.to_dict(),
            "categories": self.categories,
            "total_cost": self.total_cost
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            tourist_id=d["tourist_id"],
            guide_id=d["guide_id"],
            time_window=Window.from_dict(d["time_window"]),
            categories=d["categories"],
            total_cost=d["total_cost"]
        )


@dataclass
class ScheduleProposal:
    """Message from scheduler agent proposing assignments."""
    proposal_id: str
    assignments: List[Assignment]

    def to_dict(self):
        return {
            "type": "ScheduleProposal",
            "proposal_id": self.proposal_id,
            "assignments": [a.to_dict() for a in self.assignments]
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            proposal_id=d["proposal_id"],
            assignments=[Assignment.from_dict(a) for a in d["assignments"]]
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, s: str):
        return cls.from_dict(json.loads(s))
