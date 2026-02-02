
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
from click.testing import CliRunner
import os

from src.agents import tourist_agent

class TestTouristCLI:

    @pytest.fixture
    def mock_dependencies(self):
        """Mock external dependencies"""

        async def mock_run_debug(*args, **kwargs):
            mock_event = MagicMock()
            mock_event.content.parts = [MagicMock(text="Request received")]
            return [mock_event]

        with patch("google.adk.runners.Runner") as MockRunner, \
             patch("google.adk.agents.llm_agent.LlmAgent") as MockLlmAgent, \
             patch("src.core.model_factory.create_llm_model"), \
             patch("google.adk.agents.remote_a2a_agent.RemoteA2aAgent") as MockRemote, \
             patch("google.adk.artifacts.in_memory_artifact_service.InMemoryArtifactService"), \
             patch("google.adk.sessions.DatabaseSessionService"), \
             patch("src.core.memory.FileMemoryService"), \
             patch("src.agents.tourist_agent.create_tourist_agent", side_effect=tourist_agent.create_tourist_agent) as mock_create_agent:

            # Setup Runner mock
            mock_runner_instance = MagicMock()
            mock_runner_instance.run_debug = AsyncMock(side_effect=mock_run_debug)
            MockRunner.return_value = mock_runner_instance

            yield {
                "MockRunner": MockRunner,
                "MockRemote": MockRemote,
                "mock_create_agent": mock_create_agent
            }

    def test_create_tourist_request_message(self):
        msg = tourist_agent.create_tourist_request_message(
            "t1", "2023-01-01", "2023-01-02", ["history"], 100.0
        )
        assert "t1" in msg
        assert "history" in msg
        assert "$100.0" in msg

    @pytest.mark.asyncio
    async def test_run_tourist_agent_http(self, mock_dependencies):
        with patch.dict(os.environ, {"TRANSPORT_MODE": "http"}):
            await tourist_agent.run_tourist_agent(
                "t1", "http://localhost", ["history"], "start", "end", 100.0
            )

            # Check if RemoteA2aAgent was initialized with URL card
            mock_dependencies["MockRemote"].assert_called_once()
            call_kwargs = mock_dependencies["MockRemote"].call_args.kwargs
            assert "agent_card" in call_kwargs
            assert isinstance(call_kwargs["agent_card"], str)
            assert "http" in call_kwargs["agent_card"]

            # Check runner execution - should be called twice in run_tourist_agent
            mock_runner = mock_dependencies["MockRunner"].return_value
            assert mock_runner.run_debug.call_count == 2
            mock_runner.run_debug.assert_awaited()

    @pytest.mark.asyncio
    async def test_run_tourist_agent_slim(self, mock_dependencies):
        # Mock SLIM specific things
        with patch.dict(os.environ, {"TRANSPORT_MODE": "slim", "SCHEDULER_SLIM_TOPIC": "topic"}), \
             patch("core.slim_transport.create_slim_client_factory", new_callable=AsyncMock) as mock_iso_factory, \
             patch("core.slim_transport.config_from_env") as mock_config, \
             patch("core.slim_transport.minimal_slim_agent_card") as mock_card_helper, \
             patch("src.core.slim_transport.create_slim_client_factory", new_callable=AsyncMock) as mock_iso_factory_src, \
             patch("src.core.slim_transport.config_from_env") as mock_config_src, \
             patch("src.core.slim_transport.minimal_slim_agent_card") as mock_card_helper_src:

            mock_config.return_value = MagicMock(endpoint="slim://", local_id="id", shared_secret="s", tls_insecure=True)
            mock_iso_factory.return_value = MagicMock()
            mock_config_src.return_value = MagicMock(endpoint="slim://", local_id="id", shared_secret="s", tls_insecure=True)
            mock_iso_factory_src.return_value = MagicMock()

            await tourist_agent.run_tourist_agent(
                "t1", "http://localhost", ["history"], "start", "end", 100.0
            )

            # Check if one of them was called
            if mock_card_helper.called:
                mock_card_helper.assert_called_with("topic")
                mock_iso_factory.assert_awaited_once()
            elif mock_card_helper_src.called:
                 mock_card_helper_src.assert_called_with("topic")
                 mock_iso_factory_src.assert_awaited_once()
            else:
                 assert False, "Neither core nor src.core mocks were called"

            # Check logic passed a2a_client_factory
            mock_dependencies["MockRemote"].assert_called_once()
            call_kwargs = mock_dependencies["MockRemote"].call_args.kwargs
            assert "a2a_client_factory" in call_kwargs
            assert call_kwargs["a2a_client_factory"] is not None

    def test_main(self, mock_dependencies):
        runner = CliRunner()
        with patch("sys.exit"), \
             patch("asyncio.run") as mock_run:

            result = runner.invoke(tourist_agent.main, [
                "--tourist-id", "t1",
                "--preferences", "art,history"
            ])

            assert result.exit_code == 0
            mock_run.assert_called_once()
