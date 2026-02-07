# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Tests for ADK UI Dashboard Agent.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime

# Add src to path for imports
# src path is added by conftest.py

# Check if ADK is available
try:
    from google.adk.agents.llm_agent import LlmAgent
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False


class TestUIAgentTools:
    """Test the UI dashboard tool functions."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset dashboard state before each test."""
        from agents.ui_agent import clear_dashboard_state
        clear_dashboard_state()
        yield
        clear_dashboard_state()

    def test_record_tourist_request(self):
        """Test recording a tourist request."""
        from agents.ui_agent import record_tourist_request, get_dashboard_state

        result = record_tourist_request(
            tourist_id="t1",
            availability_start="2025-06-01T09:00:00",
            availability_end="2025-06-01T17:00:00",
            preferences="culture, history",
            budget=100.0,
        )

        assert "t1" in result
        state = get_dashboard_state()
        assert "t1" in state.tourist_requests
        assert state.tourist_requests["t1"]["budget"] == 100.0
        assert state.metrics.total_tourists == 1

    def test_record_guide_offer(self):
        """Test recording a guide offer."""
        from agents.ui_agent import record_guide_offer, get_dashboard_state

        result = record_guide_offer(
            guide_id="g1",
            categories="culture, art",
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T16:00:00",
            hourly_rate=50.0,
            max_group_size=5,
        )

        assert "g1" in result
        state = get_dashboard_state()
        assert "g1" in state.guide_offers
        assert state.guide_offers["g1"]["hourly_rate"] == 50.0
        assert state.metrics.total_guides == 1

    def test_record_assignment(self):
        """Test recording an assignment."""
        from agents.ui_agent import record_assignment, get_dashboard_state

        result = record_assignment(
            tourist_id="t1",
            guide_id="g1",
            start_time="2025-06-01T10:00:00",
            end_time="2025-06-01T14:00:00",
            total_cost=200.0,
        )

        assert "t1" in result
        assert "g1" in result
        state = get_dashboard_state()
        assert len(state.assignments) == 1
        assert state.assignments[0]["total_cost"] == 200.0
        assert state.metrics.total_assignments == 1

    def test_get_dashboard_summary(self):
        """Test getting dashboard summary."""
        from agents.ui_agent import (
            record_tourist_request,
            record_guide_offer,
            record_assignment,
            get_dashboard_summary,
        )

        # Add some data
        record_tourist_request("t1", "2025-06-01T09:00:00", "2025-06-01T17:00:00", "culture", 100.0)
        record_guide_offer("g1", "culture", "2025-06-01T10:00:00", "2025-06-01T16:00:00", 50.0, 5)
        record_assignment("t1", "g1", "2025-06-01T10:00:00", "2025-06-01T14:00:00", 200.0)

        summary = get_dashboard_summary()

        assert "Total Tourists: 1" in summary
        assert "Total Guides: 1" in summary
        assert "Total Assignments: 1" in summary
        assert "Satisfied Tourists: 1" in summary

    def test_get_recent_events(self):
        """Test getting recent events."""
        from agents.ui_agent import (
            record_tourist_request,
            record_guide_offer,
            get_recent_events,
        )

        record_tourist_request("t1", "2025-06-01T09:00:00", "2025-06-01T17:00:00", "culture", 100.0)
        record_guide_offer("g1", "culture", "2025-06-01T10:00:00", "2025-06-01T16:00:00", 50.0, 5)

        events = get_recent_events(count=5)

        assert "TouristRequest" in events
        assert "GuideOffer" in events
        assert "t1" in events
        assert "g1" in events

    def test_communication_events_recorded(self):
        """Test that communication events are recorded."""
        from agents.ui_agent import record_tourist_request, get_dashboard_state

        record_tourist_request("t1", "2025-06-01T09:00:00", "2025-06-01T17:00:00", "culture", 100.0)

        state = get_dashboard_state()
        assert len(state.communication_events) == 1
        event = state.communication_events[0]
        assert event.source_agent == "t1"
        assert event.target_agent == "scheduler"
        assert event.message_type == "TouristRequest"


class TestDashboardMetrics:
    """Test dashboard metrics calculations."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset dashboard state before each test."""
        from agents.ui_agent import clear_dashboard_state
        clear_dashboard_state()
        yield
        clear_dashboard_state()

    def test_guide_utilization(self):
        """Test guide utilization calculation."""
        from agents.ui_agent import (
            record_guide_offer,
            record_assignment,
            get_dashboard_state,
        )

        # Add 2 guides
        record_guide_offer("g1", "culture", "2025-06-01T10:00:00", "2025-06-01T16:00:00", 50.0, 5)
        record_guide_offer("g2", "history", "2025-06-01T10:00:00", "2025-06-01T16:00:00", 60.0, 3)

        # Only one guide has an assignment
        record_assignment("t1", "g1", "2025-06-01T10:00:00", "2025-06-01T14:00:00", 200.0)

        state = get_dashboard_state()
        # 1 out of 2 guides are busy = 50%
        assert state.metrics.guide_utilization == 0.5

    def test_average_assignment_cost(self):
        """Test average assignment cost calculation."""
        from agents.ui_agent import record_assignment, get_dashboard_state

        record_assignment("t1", "g1", "2025-06-01T10:00:00", "2025-06-01T14:00:00", 200.0)
        record_assignment("t2", "g2", "2025-06-01T10:00:00", "2025-06-01T14:00:00", 300.0)

        state = get_dashboard_state()
        # Average of 200 and 300 = 250
        assert state.metrics.avg_assignment_cost == 250.0

    def test_satisfied_tourists(self):
        """Test satisfied tourists calculation."""
        from agents.ui_agent import (
            record_tourist_request,
            record_assignment,
            get_dashboard_state,
        )

        # 3 tourists
        record_tourist_request("t1", "2025-06-01T09:00:00", "2025-06-01T17:00:00", "culture", 100.0)
        record_tourist_request("t2", "2025-06-01T09:00:00", "2025-06-01T17:00:00", "history", 80.0)
        record_tourist_request("t3", "2025-06-01T09:00:00", "2025-06-01T17:00:00", "food", 120.0)

        # Only 2 get assignments
        record_assignment("t1", "g1", "2025-06-01T10:00:00", "2025-06-01T14:00:00", 200.0)
        record_assignment("t2", "g2", "2025-06-01T10:00:00", "2025-06-01T14:00:00", 160.0)

        state = get_dashboard_state()
        assert state.metrics.total_tourists == 3
        assert state.metrics.satisfied_tourists == 2


@pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
class TestUIAgentDefinition:
    """Test the UI agent ADK definition."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset dashboard state before each test."""
        from agents.ui_agent import clear_dashboard_state
        clear_dashboard_state()
        yield
        clear_dashboard_state()

    def test_get_ui_agent_returns_llm_agent(self):
        """Test that get_ui_agent returns an LlmAgent."""
        from agents.ui_agent import get_ui_agent

        agent = get_ui_agent()
        assert isinstance(agent, LlmAgent)

    def test_ui_agent_has_correct_name(self):
        """Test that the UI agent has the correct name."""
        from agents.ui_agent import get_ui_agent

        agent = get_ui_agent()
        assert agent.name == "ui_dashboard_agent"

    def test_ui_agent_has_tools(self):
        """Test that the UI agent has the required tools."""
        from agents.ui_agent import get_ui_agent

        agent = get_ui_agent()
        tool_names = [t.__name__ for t in agent.tools]

        assert "record_tourist_request" in tool_names
        assert "record_guide_offer" in tool_names
        assert "record_assignment" in tool_names
        assert "get_dashboard_summary" in tool_names
        assert "get_recent_events" in tool_names

    def test_ui_agent_has_description(self):
        """Test that the UI agent has a description."""
        from agents.ui_agent import get_ui_agent

        agent = get_ui_agent()
        assert agent.description is not None
        assert "dashboard" in agent.description.lower()


@pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
class TestUIAgentA2AApp:
    """Test A2A app creation for UI agent."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset dashboard state before each test."""
        from agents.ui_agent import clear_dashboard_state
        clear_dashboard_state()
        yield
        clear_dashboard_state()

    def test_create_ui_app(self):
        """Test creating an A2A app for the UI agent."""
        from agents.ui_agent import create_ui_app

        app = create_ui_app(host="127.0.0.1", port=10011)
        assert app is not None

    def test_create_ui_app_custom_port(self):
        """Test creating an A2A app with custom port."""
        from agents.ui_agent import create_ui_app

        app = create_ui_app(host="127.0.0.1", port=9999)
        assert app is not None
