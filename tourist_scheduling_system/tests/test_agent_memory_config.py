
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Check if ADK is available
try:
    from google.adk.agents.llm_agent import LlmAgent
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False

@pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not installed")
class TestAgentMemoryConfiguration:

    def test_scheduler_uses_file_memory(self):
        from src.agents.scheduler_agent import create_scheduler_app
        from src.core.memory import FileMemoryService
        from google.adk.sessions import DatabaseSessionService
        from google.adk.runners import Runner

        # Patch where it is defined since it is imported inside the function
        with patch("google.adk.a2a.utils.agent_to_a2a.to_a2a") as mock_to_a2a:
            create_scheduler_app()

            # Check if to_a2a was called
            assert mock_to_a2a.called

            # Get the arguments passed to to_a2a
            call_args = mock_to_a2a.call_args
            kwargs = call_args.kwargs

            # Check if runner was passed
            if "runner" in kwargs and kwargs["runner"] is not None:
                runner = kwargs["runner"]
                assert isinstance(runner.memory_service, FileMemoryService)
                assert runner.memory_service.file_path == "scheduler_memory.json"
                assert isinstance(runner.session_service, DatabaseSessionService)
            else:
                 pytest.fail("runner argument not passed to to_a2a")

    @pytest.mark.asyncio
    async def test_guide_uses_file_memory(self):
        from src.agents.guide_agent import run_guide_agent

        # Mock dependencies
        with patch("google.adk.runners.Runner") as MockRunner, \
             patch("src.core.memory.FileMemoryService") as MockFileMemoryService, \
             patch("google.adk.sessions.DatabaseSessionService") as MockDatabaseSessionService, \
             patch("src.agents.guide_agent.create_guide_agent", new_callable=AsyncMock) as mock_create_agent:

            mock_create_agent.return_value = MagicMock()
            mock_runner_instance = MockRunner.return_value
            mock_runner_instance.run_debug = AsyncMock(return_value=[])

            await run_guide_agent(
                guide_id="g1",
                scheduler_url="http://localhost:8000",
                categories="History",
                available_start="2025-06-01T09:00:00",
                available_end="2025-06-01T17:00:00",
                hourly_rate=50.0
            )

            # Check FileMemoryService usage
            MockFileMemoryService.assert_called_once_with("guide_memory_g1.json")

            # Check DatabaseSessionService usage
            MockDatabaseSessionService.assert_called_once_with(db_url="sqlite+aiosqlite:///guide_sessions_g1.db")

            # Check Runner usage
            _, kwargs = MockRunner.call_args
            assert "memory_service" in kwargs
            assert kwargs["memory_service"] == MockFileMemoryService.return_value
            assert "session_service" in kwargs
            assert kwargs["session_service"] == MockDatabaseSessionService.return_value

    @pytest.mark.asyncio
    async def test_tourist_uses_file_memory(self):
        from src.agents.tourist_agent import run_tourist_agent

        # Mock dependencies
        with patch("google.adk.runners.Runner") as MockRunner, \
             patch("src.core.memory.FileMemoryService") as MockFileMemoryService, \
             patch("google.adk.sessions.DatabaseSessionService") as MockDatabaseSessionService, \
             patch("src.agents.tourist_agent.create_tourist_agent", new_callable=AsyncMock) as mock_create_agent:

            mock_create_agent.return_value = MagicMock()
            mock_runner_instance = MockRunner.return_value
            mock_runner_instance.run_debug = AsyncMock(return_value=[])

            await run_tourist_agent(
                tourist_id="t1",
                scheduler_url="http://localhost:8000",
                availability_start="2025-06-01T09:00:00",
                availability_end="2025-06-01T17:00:00",
                preferences="History",
                budget=100.0
            )

            # Check FileMemoryService usage
            MockFileMemoryService.assert_called_once_with("tourist_memory_t1.json")

            # Check DatabaseSessionService usage
            MockDatabaseSessionService.assert_called_once_with(db_url="sqlite+aiosqlite:///tourist_sessions_t1.db")

            # Check Runner usage
            _, kwargs = MockRunner.call_args
            assert "memory_service" in kwargs
            assert kwargs["memory_service"] == MockFileMemoryService.return_value
            assert "session_service" in kwargs
            assert kwargs["session_service"] == MockDatabaseSessionService.return_value
