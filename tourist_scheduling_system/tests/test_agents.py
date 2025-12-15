# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Tests for ADK-based agents.

These tests verify the agent definitions and basic functionality.
Some tests require the google-adk package to be installed.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))


# Check if ADK is available
try:
    from google.adk.agents.llm_agent import LlmAgent
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False


@pytest.fixture
def mock_adk_imports():
    """Mock ADK imports for testing without ADK installed."""
    if not ADK_AVAILABLE:
        mock_llm_agent = MagicMock()
        mock_llm_agent.LlmAgent = MagicMock()

        mock_runner = MagicMock()
        mock_runner.InMemoryRunner = MagicMock()

        mock_to_a2a = MagicMock()
        mock_remote_agent = MagicMock()

        with patch.dict(sys.modules, {
            'google.adk': MagicMock(),
            'google.adk.agents': MagicMock(),
            'google.adk.agents.llm_agent': mock_llm_agent,
            'google.adk.runners': mock_runner,
            'google.adk.a2a': MagicMock(),
            'google.adk.a2a.utils': MagicMock(),
            'google.adk.a2a.utils.agent_to_a2a': mock_to_a2a,
            'google.adk.agents.remote_a2a_agent': mock_remote_agent,
            'google.adk.tools': MagicMock(),
            'google.adk.tools.tool_context': MagicMock(),
        }):
            yield
    else:
        yield


class TestSchedulerAgentDefinition:
    """Tests for scheduler agent definition."""

    @pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
    def test_scheduler_agent_is_llm_agent(self):
        """Test that scheduler_agent is an LlmAgent instance."""
        from agents.scheduler_agent import get_scheduler_agent

        agent = get_scheduler_agent()
        assert isinstance(agent, LlmAgent)

    @pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
    def test_scheduler_agent_has_required_tools(self):
        """Test that scheduler_agent has all required tools."""
        from agents.scheduler_agent import get_scheduler_agent

        agent = get_scheduler_agent()
        tool_names = [t.__name__ if hasattr(t, '__name__') else str(t) for t in agent.tools]

        assert "register_tourist_request" in tool_names
        assert "register_guide_offer" in tool_names
        assert "run_scheduling" in tool_names
        assert "get_schedule_status" in tool_names

    @pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
    def test_scheduler_agent_has_name(self):
        """Test that scheduler_agent has a name."""
        from agents.scheduler_agent import get_scheduler_agent

        agent = get_scheduler_agent()
        assert agent.name == "scheduler_agent"

    @pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
    def test_scheduler_agent_has_instruction(self):
        """Test that scheduler_agent has an instruction."""
        from agents.scheduler_agent import get_scheduler_agent

        agent = get_scheduler_agent()
        assert agent.instruction is not None
        assert len(agent.instruction) > 0


class TestGuideAgentCreation:
    """Tests for guide agent factory function."""

    @pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
    @pytest.mark.asyncio
    async def test_create_guide_agent(self):
        """Test creating a guide agent."""
        from agents.guide_agent import create_guide_agent

        agent = await create_guide_agent(
            guide_id="g1",
            scheduler_url="http://localhost:10000",
        )

        assert agent.name == "guide_g1"

    @pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
    @pytest.mark.asyncio
    async def test_guide_agent_has_scheduler_subagent(self):
        """Test that guide agent has scheduler as sub-agent."""
        from agents.guide_agent import create_guide_agent

        agent = await create_guide_agent(
            guide_id="g1",
            scheduler_url="http://localhost:10000",
        )

        assert len(agent.sub_agents) == 1
        assert agent.sub_agents[0].name == "scheduler"


class TestTouristAgentCreation:
    """Tests for tourist agent factory function."""

    @pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
    @pytest.mark.asyncio
    async def test_create_tourist_agent(self):
        """Test creating a tourist agent."""
        from agents.tourist_agent import create_tourist_agent

        agent = await create_tourist_agent(
            tourist_id="t1",
            scheduler_url="http://localhost:10000",
        )

        assert agent.name == "tourist_t1"

    @pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
    @pytest.mark.asyncio
    async def test_tourist_agent_has_scheduler_subagent(self):
        """Test that tourist agent has scheduler as sub-agent."""
        from agents.tourist_agent import create_tourist_agent

        agent = await create_tourist_agent(
            tourist_id="t1",
            scheduler_url="http://localhost:10000",
        )

        assert len(agent.sub_agents) == 1
        assert agent.sub_agents[0].name == "scheduler"


class TestMessageCreation:
    """Tests for message creation helper functions."""

    def test_create_guide_offer_message(self):
        """Test guide offer message creation."""
        from agents.guide_agent import create_guide_offer_message

        message = create_guide_offer_message(
            guide_id="g1",
            categories=["culture", "history"],
            available_start="2025-06-01T10:00:00",
            available_end="2025-06-01T14:00:00",
            hourly_rate=50.0,
            max_group_size=5,
        )

        assert "g1" in message
        assert "culture" in message
        assert "history" in message
        assert "$50.0" in message
        assert "5" in message

    def test_create_tourist_request_message(self):
        """Test tourist request message creation."""
        from agents.tourist_agent import create_tourist_request_message

        message = create_tourist_request_message(
            tourist_id="t1",
            availability_start="2025-06-01T09:00:00",
            availability_end="2025-06-01T17:00:00",
            preferences=["culture", "history"],
            budget=100.0,
        )

        assert "t1" in message
        assert "culture" in message
        assert "history" in message
        assert "$100.0" in message


class TestCreateSchedulerApp:
    """Tests for A2A app creation."""

    @pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
    def test_create_scheduler_app(self):
        """Test creating A2A application for scheduler."""
        from agents.scheduler_agent import create_scheduler_app

        app = create_scheduler_app(host="localhost", port=10000)

        # Should return a Starlette app
        assert app is not None


class TestToolFunctionSignatures:
    """Tests for tool function signatures (important for ADK tool calling)."""

    def test_register_tourist_request_signature(self):
        """Test register_tourist_request has correct signature."""
        from agents.tools import register_tourist_request
        import inspect

        sig = inspect.signature(register_tourist_request)
        params = list(sig.parameters.keys())

        assert "tourist_id" in params
        assert "availability_start" in params
        assert "availability_end" in params
        assert "preferences" in params
        assert "budget" in params
        assert "tool_context" in params

    def test_register_guide_offer_signature(self):
        """Test register_guide_offer has correct signature."""
        from agents.tools import register_guide_offer
        import inspect

        sig = inspect.signature(register_guide_offer)
        params = list(sig.parameters.keys())

        assert "guide_id" in params
        assert "categories" in params
        assert "available_start" in params
        assert "available_end" in params
        assert "hourly_rate" in params
        assert "max_group_size" in params
        assert "tool_context" in params

    def test_run_scheduling_signature(self):
        """Test run_scheduling has correct signature."""
        from agents.tools import run_scheduling
        import inspect

        sig = inspect.signature(run_scheduling)
        params = list(sig.parameters.keys())

        assert "tool_context" in params

    def test_get_schedule_status_signature(self):
        """Test get_schedule_status has correct signature."""
        from agents.tools import get_schedule_status
        import inspect

        sig = inspect.signature(get_schedule_status)
        params = list(sig.parameters.keys())

        assert "tool_context" in params


class TestToolDocstrings:
    """Tests for tool docstrings (important for LLM understanding)."""

    def test_register_tourist_request_docstring(self):
        """Test register_tourist_request has meaningful docstring."""
        from agents.tools import register_tourist_request

        assert register_tourist_request.__doc__ is not None
        assert "tourist" in register_tourist_request.__doc__.lower()
        assert "register" in register_tourist_request.__doc__.lower()

    def test_register_guide_offer_docstring(self):
        """Test register_guide_offer has meaningful docstring."""
        from agents.tools import register_guide_offer

        assert register_guide_offer.__doc__ is not None
        assert "guide" in register_guide_offer.__doc__.lower()

    def test_run_scheduling_docstring(self):
        """Test run_scheduling has meaningful docstring."""
        from agents.tools import run_scheduling

        assert run_scheduling.__doc__ is not None
        assert "scheduling" in run_scheduling.__doc__.lower() or "schedule" in run_scheduling.__doc__.lower()

    def test_get_schedule_status_docstring(self):
        """Test get_schedule_status has meaningful docstring."""
        from agents.tools import get_schedule_status

        assert get_schedule_status.__doc__ is not None
        assert "status" in get_schedule_status.__doc__.lower()
