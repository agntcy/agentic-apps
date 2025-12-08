# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Data models for ADK-based agents.

These models define the structured inputs and outputs for agent tools,
enabling type-safe tool invocations.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class Window(BaseModel):
    """Time window for availability."""

    start: datetime = Field(description="Start time of the window")
    end: datetime = Field(description="End time of the window")


class TouristRequest(BaseModel):
    """Request from a tourist for scheduling."""

    tourist_id: str = Field(description="Unique identifier for the tourist")
    availability: List[Window] = Field(description="Available time windows")
    preferences: List[str] = Field(description="Preferred categories (e.g., culture, food, history)")
    budget: float = Field(description="Maximum budget per hour")


class GuideOffer(BaseModel):
    """Offer from a guide with availability and capabilities."""

    guide_id: str = Field(description="Unique identifier for the guide")
    categories: List[str] = Field(description="Categories the guide specializes in")
    available_window: Window = Field(description="Time window when guide is available")
    hourly_rate: float = Field(description="Guide's hourly rate")
    max_group_size: int = Field(default=1, description="Maximum tourists the guide can handle")


class Assignment(BaseModel):
    """A scheduled assignment matching a tourist to a guide."""

    tourist_id: str = Field(description="Assigned tourist ID")
    guide_id: str = Field(description="Assigned guide ID")
    time_window: Window = Field(description="Scheduled time window")
    categories: List[str] = Field(description="Categories covered")
    total_cost: float = Field(description="Total cost for the assignment")


class ScheduleProposal(BaseModel):
    """Proposal sent back to tourists with their schedule."""

    tourist_id: str = Field(description="Tourist this proposal is for")
    assignments: List[Assignment] = Field(description="List of assignments")
    status: str = Field(default="proposed", description="Status of the proposal")


class SchedulerState(BaseModel):
    """Current state of the scheduler."""

    tourist_requests: List[TouristRequest] = Field(default_factory=list)
    guide_offers: List[GuideOffer] = Field(default_factory=list)
    assignments: List[Assignment] = Field(default_factory=list)

    def to_summary(self) -> dict:
        """Return a summary of the current state."""
        return {
            "num_tourists": len(self.tourist_requests),
            "num_guides": len(self.guide_offers),
            "num_assignments": len(self.assignments),
            "tourists": [t.tourist_id for t in self.tourist_requests],
            "guides": [g.guide_id for g in self.guide_offers],
        }
