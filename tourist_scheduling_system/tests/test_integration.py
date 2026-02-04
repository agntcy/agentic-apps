# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Integration tests for ADK-based agents.

These tests verify end-to-end functionality of the ADK agents.
Requires google-adk to be installed and properly configured.
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Add src to path for imports
# src path is added by conftest.py

# Check if ADK is available
try:
    from google.adk.agents.llm_agent import LlmAgent
    from google.adk.runners import InMemoryRunner
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False

# Check if API key is available for LLM integration tests
# Supports Azure OpenAI or Google AI
import os
API_KEY_AVAILABLE = bool(
    os.environ.get("AZURE_OPENAI_API_KEY") or
    os.environ.get("GOOGLE_GEMINI_API_KEY")
)


@pytest.fixture(autouse=True)
def reset_scheduler_state():
    """Reset scheduler state before each test."""
    from agents.tools import clear_scheduler_state
    clear_scheduler_state()
    yield
    clear_scheduler_state()


@pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
@pytest.mark.skipif(not API_KEY_AVAILABLE, reason="No API key set (AZURE_OPENAI_API_KEY or GOOGLE_GEMINI_API_KEY)")
class TestSchedulerAgentIntegration:
    """Integration tests for the scheduler agent.

    These tests require a valid API key to run the LLM agent.
    Set one of: AZURE_OPENAI_API_KEY, GOOGLE_GEMINI_API_KEY.

    For Azure OpenAI, also set AZURE_API_BASE and AZURE_API_VERSION.
    """

    @pytest.fixture
    def scheduler_runner(self):
        """Create a runner for the scheduler agent."""
        from agents.scheduler_agent import get_scheduler_agent
        return InMemoryRunner(agent=get_scheduler_agent())

    @pytest.mark.asyncio
    async def test_scheduler_responds_to_tourist_request(self, scheduler_runner):
        """Test that scheduler can process a tourist registration message."""
        events = await scheduler_runner.run_debug(
            user_messages="Register tourist t1 with availability from 2025-06-01T09:00:00 to 2025-06-01T17:00:00, preferences for culture and history, budget $100/hour",
            quiet=True,
        )

        # Should have at least one event
        assert len(events) > 0

        # Check status after registration
        from agents.tools import get_schedule_status
        status = get_schedule_status()
        assert status["total_tourists"] >= 1

    @pytest.mark.asyncio
    async def test_scheduler_responds_to_guide_offer(self, scheduler_runner):
        """Test that scheduler can process a guide offer message."""
        events = await scheduler_runner.run_debug(
            user_messages="Register guide g1 specializing in culture and history, available 2025-06-01T10:00:00 to 2025-06-01T14:00:00, rate $50/hour, max 5 tourists",
            quiet=True,
        )

        assert len(events) > 0

        from agents.tools import get_schedule_status
        status = get_schedule_status()
        assert status["total_guides"] >= 1

    @pytest.mark.asyncio
    async def test_scheduler_runs_scheduling(self, scheduler_runner):
        """Test that scheduler can run the scheduling algorithm."""
        # First register tourist and guide
        await scheduler_runner.run_debug(
            user_messages=[
                "Register tourist t1 with availability from 2025-06-01T09:00:00 to 2025-06-01T17:00:00, preferences for culture and history, budget $100/hour",
                "Register guide g1 specializing in culture and history, available 2025-06-01T10:00:00 to 2025-06-01T14:00:00, rate $50/hour",
            ],
            quiet=True,
        )

        # Now run scheduling
        events = await scheduler_runner.run_debug(
            user_messages="Run the scheduling algorithm to match tourists with guides",
            quiet=True,
        )

        assert len(events) > 0

        from agents.tools import get_schedule_status
        status = get_schedule_status()
        assert status["total_assignments"] >= 1

    @pytest.mark.asyncio
    async def test_scheduler_reports_status(self, scheduler_runner):
        """Test that scheduler can report its status."""
        events = await scheduler_runner.run_debug(
            user_messages="What is the current scheduler status?",
            quiet=True,
        )

        assert len(events) > 0


@pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
class TestMultiAgentInteraction:
    """Tests for multi-agent interactions."""

    @pytest.mark.asyncio
    async def test_guide_agent_creation(self):
        """Test creating and running a guide agent."""
        from agents.guide_agent import create_guide_agent

        agent = await create_guide_agent(
            guide_id="test_guide",
            scheduler_url="http://localhost:10000",
        )

        # Verify agent structure
        assert agent.name == "guide_test_guide"
        assert len(agent.sub_agents) == 1

    @pytest.mark.asyncio
    async def test_tourist_agent_creation(self):
        """Test creating and running a tourist agent."""
        from agents.tourist_agent import create_tourist_agent

        agent = await create_tourist_agent(
            tourist_id="test_tourist",
            scheduler_url="http://localhost:10000",
        )

        # Verify agent structure
        assert agent.name == "tourist_test_tourist"
        assert len(agent.sub_agents) == 1


class TestSchedulingAlgorithm:
    """Tests for the scheduling algorithm logic."""

    def test_greedy_scheduling_basic(self):
        """Test basic greedy scheduling with one tourist and one guide."""
        from agents.tools import (
            register_tourist_request,
            register_guide_offer,
            run_scheduling,
            clear_scheduler_state,
        )

        clear_scheduler_state()

        register_tourist_request(
            tourist_id="t1",
            availability_start="2025-06-01T09:00:00",
            availability_end="2025-06-01T17:00:00",
            preferences=["culture"],
            budget=100.0,
            tool_context=None,
        )

        register_guide_offer(
            guide_id="g1",
            categories=["culture"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=50.0,
            max_group_size=5,
            tool_context=None,
        )

        result = run_scheduling()

        assert result["status"] == "completed"
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["tourist_id"] == "t1"
        assert result["assignments"][0]["guide_id"] == "g1"

    def test_greedy_scheduling_multiple_tourists(self):
        """Test scheduling with multiple tourists."""
        from agents.tools import (
            register_tourist_request,
            register_guide_offer,
            run_scheduling,
            clear_scheduler_state,
        )

        clear_scheduler_state()

        # Register 3 tourists
        for i in range(3):
            register_tourist_request(
                tourist_id=f"t{i+1}",
                availability_start="2025-06-01T09:00:00",
                availability_end="2025-06-01T17:00:00",
                preferences=["culture"],
                budget=100.0,
                tool_context=None,
            )

        # Register 2 guides with capacity 2 each
        for i in range(2):
            register_guide_offer(
                guide_id=f"g{i+1}",
                categories=["culture"],
                available_start="2025-06-01T10:00:00",
                available_end="2025-06-01T14:00:00",
                hourly_rate=50.0,
                max_group_size=2,
                tool_context=None,
            )

        result = run_scheduling()

        assert result["status"] == "completed"
        # Should have 3 assignments (2 from g1, 1 from g2)
        assert len(result["assignments"]) == 3

    def test_greedy_scheduling_preference_priority(self):
        """Test that scheduling prioritizes preference matches."""
        from agents.tools import (
            register_tourist_request,
            register_guide_offer,
            run_scheduling,
            clear_scheduler_state,
        )

        clear_scheduler_state()

        # Tourist prefers culture
        register_tourist_request(
            tourist_id="t1",
            availability_start="2025-06-01T09:00:00",
            availability_end="2025-06-01T17:00:00",
            preferences=["culture", "art"],
            budget=100.0,
            tool_context=None,
        )

        # Guide 1: food only (0 match)
        register_guide_offer(
            guide_id="g1",
            categories=["food"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=40.0,  # Cheaper
            tool_context=None,
        )

        # Guide 2: culture and art (2 matches)
        register_guide_offer(
            guide_id="g2",
            categories=["culture", "art"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=50.0,
            tool_context=None,
        )

        result = run_scheduling()

        # Should choose g2 despite being more expensive (better preference match)
        assert result["assignments"][0]["guide_id"] == "g2"


class TestA2AAppCreation:
    """Tests for A2A application creation."""

    @pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
    def test_create_a2a_app(self):
        """Test that A2A app can be created."""
        from agents.scheduler_agent import create_scheduler_app

        app = create_scheduler_app(host="localhost", port=10000)

        # Should be a Starlette application
        assert hasattr(app, 'routes')

    @pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
    def test_create_a2a_app_custom_port(self):
        """Test A2A app creation with custom port."""
        from agents.scheduler_agent import create_scheduler_app

        app = create_scheduler_app(host="0.0.0.0", port=8080)

        assert app is not None
