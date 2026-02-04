# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Tests for ADK-based agent tools.

These tests verify the scheduling tools work correctly without requiring
the full ADK/LLM infrastructure.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

# Import the tools module
import sys
from pathlib import Path

# src path is added by conftest.py

from agents.tools import (
    register_tourist_request,
    register_guide_offer,
    run_scheduling,
    get_schedule_status,
    clear_scheduler_state,
    _scheduler_state,
)
from src.core.models import (
    TouristRequest,
    GuideOffer,
    Assignment,
    SchedulerState,
    Window,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset scheduler state before each test."""
    clear_scheduler_state()
    yield
    clear_scheduler_state()


@pytest.fixture
def mock_tool_context():
    """Create a mock ToolContext for testing."""
    return MagicMock()


class TestModels:
    """Tests for Pydantic data models."""

    def test_window_creation(self):
        """Test Window model creation."""
        window = Window(
            start=datetime(2025, 6, 1, 9, 0),
            end=datetime(2025, 6, 1, 17, 0),
        )
        assert window.start.hour == 9
        assert window.end.hour == 17

    def test_tourist_request_creation(self):
        """Test TouristRequest model creation."""
        request = TouristRequest(
            tourist_id="t1",
            availability=[
                Window(
                    start=datetime(2025, 6, 1, 9, 0),
                    end=datetime(2025, 6, 1, 17, 0),
                )
            ],
            preferences=["culture", "history"],
            budget=100.0,
        )
        assert request.tourist_id == "t1"
        assert len(request.availability) == 1
        assert "culture" in request.preferences
        assert request.budget == 100.0

    def test_guide_offer_creation(self):
        """Test GuideOffer model creation."""
        offer = GuideOffer(
            guide_id="g1",
            categories=["culture", "history", "food"],
            available_window=Window(
                start=datetime(2025, 6, 1, 10, 0),
                end=datetime(2025, 6, 1, 14, 0),
            ),
            hourly_rate=50.0,
            max_group_size=5,
        )
        assert offer.guide_id == "g1"
        assert len(offer.categories) == 3
        assert offer.hourly_rate == 50.0
        assert offer.max_group_size == 5

    def test_assignment_creation(self):
        """Test Assignment model creation."""
        assignment = Assignment(
            tourist_id="t1",
            guide_id="g1",
            time_window=Window(
                start=datetime(2025, 6, 1, 10, 0),
                end=datetime(2025, 6, 1, 14, 0),
            ),
            categories=["culture", "history"],
            total_cost=200.0,
        )
        assert assignment.tourist_id == "t1"
        assert assignment.guide_id == "g1"
        assert assignment.total_cost == 200.0

    def test_scheduler_state_summary(self):
        """Test SchedulerState summary generation."""
        state = SchedulerState()
        state.tourist_requests.append(
            TouristRequest(
                tourist_id="t1",
                availability=[],
                preferences=[],
                budget=100.0,
            )
        )
        state.guide_offers.append(
            GuideOffer(
                guide_id="g1",
                categories=[],
                available_window=Window(
                    start=datetime(2025, 6, 1, 10, 0),
                    end=datetime(2025, 6, 1, 14, 0),
                ),
                hourly_rate=50.0,
            )
        )

        summary = state.to_summary()
        assert summary["num_tourists"] == 1
        assert summary["num_guides"] == 1
        assert "t1" in summary["tourists"]
        assert "g1" in summary["guides"]


class TestRegisterTouristRequest:
    """Tests for register_tourist_request tool."""

    def test_register_tourist_success(self, mock_tool_context):
        """Test successful tourist registration."""
        result = register_tourist_request(
            tourist_id="t1",
            availability_start="2025-06-01T09:00:00",
            availability_end="2025-06-01T17:00:00",
            preferences=["culture", "history"],
            budget=100.0,
            tool_context=mock_tool_context,
        )

        assert result["status"] == "registered"
        assert result["tourist_id"] == "t1"
        assert result["queue_position"] == 1

    def test_register_tourist_updates_existing(self, mock_tool_context):
        """Test that registering same tourist updates existing entry."""
        # Register first time
        register_tourist_request(
            tourist_id="t1",
            availability_start="2025-06-01T09:00:00",
            availability_end="2025-06-01T17:00:00",
            preferences=["culture"],
            budget=50.0,
            tool_context=mock_tool_context,
        )

        # Register again with different values
        result = register_tourist_request(
            tourist_id="t1",
            availability_start="2025-06-01T10:00:00",
            availability_end="2025-06-01T18:00:00",
            preferences=["culture", "food"],
            budget=100.0,
            tool_context=mock_tool_context,
        )

        assert result["status"] == "registered"
        assert result["queue_position"] == 1  # Still only one tourist

    def test_register_multiple_tourists(self, mock_tool_context):
        """Test registering multiple tourists."""
        register_tourist_request(
            tourist_id="t1",
            availability_start="2025-06-01T09:00:00",
            availability_end="2025-06-01T17:00:00",
            preferences=["culture"],
            budget=100.0,
            tool_context=mock_tool_context,
        )

        result = register_tourist_request(
            tourist_id="t2",
            availability_start="2025-06-01T09:00:00",
            availability_end="2025-06-01T17:00:00",
            preferences=["food"],
            budget=80.0,
            tool_context=mock_tool_context,
        )

        assert result["queue_position"] == 2

    def test_register_tourist_invalid_date(self, mock_tool_context):
        """Test registration with invalid date format."""
        result = register_tourist_request(
            tourist_id="t1",
            availability_start="invalid-date",
            availability_end="2025-06-01T17:00:00",
            preferences=["culture"],
            budget=100.0,
            tool_context=mock_tool_context,
        )

        assert result["status"] == "error"


class TestRegisterGuideOffer:
    """Tests for register_guide_offer tool."""

    def test_register_guide_success(self, mock_tool_context):
        """Test successful guide registration."""
        result = register_guide_offer(
            guide_id="g1",
            categories=["culture", "history", "food"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=50.0,
            max_group_size=5,
            tool_context=mock_tool_context,
        )

        assert result["status"] == "registered"
        assert result["guide_id"] == "g1"
        assert result["total_guides"] == 1

    def test_register_guide_updates_existing(self, mock_tool_context):
        """Test that registering same guide updates existing entry."""
        register_guide_offer(
            guide_id="g1",
            categories=["culture"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=50.0,
            tool_context=mock_tool_context,
        )

        result = register_guide_offer(
            guide_id="g1",
            categories=["culture", "history"],
            available_start="2025-06-01T09:00:00",
            available_end="2025-06-01T15:00:00",
            hourly_rate=60.0,
            tool_context=mock_tool_context,
        )

        assert result["status"] == "registered"
        assert result["total_guides"] == 1

    def test_register_multiple_guides(self, mock_tool_context):
        """Test registering multiple guides."""
        register_guide_offer(
            guide_id="g1",
            categories=["culture"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=50.0,
            tool_context=mock_tool_context,
        )

        result = register_guide_offer(
            guide_id="g2",
            categories=["food"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=40.0,
            tool_context=mock_tool_context,
        )

        assert result["total_guides"] == 2


class TestRunScheduling:
    """Tests for run_scheduling tool."""

    def test_scheduling_no_tourists(self, mock_tool_context):
        """Test scheduling with no tourists."""
        result = run_scheduling(tool_context=mock_tool_context)

        assert result["status"] == "no_tourists"
        assert result["assignments"] == []

    def test_scheduling_no_guides(self, mock_tool_context):
        """Test scheduling with tourists but no guides."""
        register_tourist_request(
            tourist_id="t1",
            availability_start="2025-06-01T09:00:00",
            availability_end="2025-06-01T17:00:00",
            preferences=["culture"],
            budget=100.0,
            tool_context=mock_tool_context,
        )

        result = run_scheduling(tool_context=mock_tool_context)

        assert result["status"] == "no_guides"
        assert result["assignments"] == []

    def test_scheduling_successful_match(self, mock_tool_context):
        """Test successful scheduling with matching tourist and guide."""
        # Register tourist
        register_tourist_request(
            tourist_id="t1",
            availability_start="2025-06-01T09:00:00",
            availability_end="2025-06-01T17:00:00",
            preferences=["culture", "history"],
            budget=100.0,
            tool_context=mock_tool_context,
        )

        # Register guide
        register_guide_offer(
            guide_id="g1",
            categories=["culture", "history", "food"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=50.0,
            max_group_size=5,
            tool_context=mock_tool_context,
        )

        result = run_scheduling(tool_context=mock_tool_context)

        assert result["status"] == "completed"
        assert result["num_assignments"] == 1
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["tourist_id"] == "t1"
        assert result["assignments"][0]["guide_id"] == "g1"

    def test_scheduling_budget_constraint(self, mock_tool_context):
        """Test that budget constraints are respected."""
        # Register tourist with low budget
        register_tourist_request(
            tourist_id="t1",
            availability_start="2025-06-01T09:00:00",
            availability_end="2025-06-01T17:00:00",
            preferences=["culture"],
            budget=30.0,  # Too low for guide
            tool_context=mock_tool_context,
        )

        # Register expensive guide
        register_guide_offer(
            guide_id="g1",
            categories=["culture"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=50.0,  # Above tourist budget
            tool_context=mock_tool_context,
        )

        result = run_scheduling(tool_context=mock_tool_context)

        assert result["status"] == "completed"
        assert result["num_assignments"] == 0  # No match due to budget

    def test_scheduling_preference_matching(self, mock_tool_context):
        """Test that guide with better preference match is chosen."""
        # Register tourist preferring culture
        register_tourist_request(
            tourist_id="t1",
            availability_start="2025-06-01T09:00:00",
            availability_end="2025-06-01T17:00:00",
            preferences=["culture", "history"],
            budget=100.0,
            tool_context=mock_tool_context,
        )

        # Register guide with food specialty (low match)
        register_guide_offer(
            guide_id="g1",
            categories=["food"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=50.0,
            tool_context=mock_tool_context,
        )

        # Register guide with culture specialty (high match)
        register_guide_offer(
            guide_id="g2",
            categories=["culture", "history"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=50.0,
            tool_context=mock_tool_context,
        )

        result = run_scheduling(tool_context=mock_tool_context)

        assert result["status"] == "completed"
        assert result["num_assignments"] == 1
        # Should match with g2 (better preference score)
        assert result["assignments"][0]["guide_id"] == "g2"

    def test_scheduling_capacity_limit(self, mock_tool_context):
        """Test that guide capacity is respected."""
        # Register multiple tourists
        for i in range(3):
            register_tourist_request(
                tourist_id=f"t{i+1}",
                availability_start="2025-06-01T09:00:00",
                availability_end="2025-06-01T17:00:00",
                preferences=["culture"],
                budget=100.0,
                tool_context=mock_tool_context,
            )

        # Register guide with capacity of 2
        register_guide_offer(
            guide_id="g1",
            categories=["culture"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=50.0,
            max_group_size=2,
            tool_context=mock_tool_context,
        )

        result = run_scheduling(tool_context=mock_tool_context)

        assert result["status"] == "completed"
        assert result["num_assignments"] == 2  # Limited by capacity


class TestGetScheduleStatus:
    """Tests for get_schedule_status tool."""

    def test_status_empty(self, mock_tool_context):
        """Test status with empty scheduler."""
        result = get_schedule_status(tool_context=mock_tool_context)

        assert result["status"] == "ok"
        assert result["total_tourists"] == 0
        assert result["total_guides"] == 0
        assert result["total_assignments"] == 0

    def test_status_with_data(self, mock_tool_context):
        """Test status with registered tourists and guides."""
        # Register tourist
        register_tourist_request(
            tourist_id="t1",
            availability_start="2025-06-01T09:00:00",
            availability_end="2025-06-01T17:00:00",
            preferences=["culture"],
            budget=100.0,
            tool_context=mock_tool_context,
        )

        # Register guide
        register_guide_offer(
            guide_id="g1",
            categories=["culture"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=50.0,
            tool_context=mock_tool_context,
        )

        result = get_schedule_status(tool_context=mock_tool_context)

        assert result["total_tourists"] == 1
        assert result["total_guides"] == 1
        assert result["pending_tourists"] == 1
        assert result["available_guides"] == 1

    def test_status_after_scheduling(self, mock_tool_context):
        """Test status after scheduling is run."""
        # Register and schedule
        register_tourist_request(
            tourist_id="t1",
            availability_start="2025-06-01T09:00:00",
            availability_end="2025-06-01T17:00:00",
            preferences=["culture"],
            budget=100.0,
            tool_context=mock_tool_context,
        )
        register_guide_offer(
            guide_id="g1",
            categories=["culture"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=50.0,
            tool_context=mock_tool_context,
        )
        run_scheduling(tool_context=mock_tool_context)

        result = get_schedule_status(tool_context=mock_tool_context)

        assert result["total_assignments"] == 1
        assert result["tourist_satisfaction_pct"] == 100.0
        assert result["guide_utilization_pct"] == 100.0
        assert result["pending_tourists"] == 0


class TestClearSchedulerState:
    """Tests for clear_scheduler_state tool."""

    def test_clear_state(self, mock_tool_context):
        """Test that clear_scheduler_state resets everything."""
        # Add some data
        register_tourist_request(
            tourist_id="t1",
            availability_start="2025-06-01T09:00:00",
            availability_end="2025-06-01T17:00:00",
            preferences=["culture"],
            budget=100.0,
            tool_context=mock_tool_context,
        )
        register_guide_offer(
            guide_id="g1",
            categories=["culture"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=50.0,
            tool_context=mock_tool_context,
        )

        # Clear state
        result = clear_scheduler_state(tool_context=mock_tool_context)

        assert result["status"] == "cleared"

        # Verify state is empty
        status = get_schedule_status(tool_context=mock_tool_context)
        assert status["total_tourists"] == 0
        assert status["total_guides"] == 0
