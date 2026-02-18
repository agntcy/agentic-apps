
import pytest
from unittest.mock import MagicMock, patch, AsyncMock, ANY
import asyncio
from click.testing import CliRunner
import os

from src.agents import guide_agent

class TestGuideCLI:

    @pytest.fixture
    def mock_dependencies(self):
        """Mock external dependencies"""
        # Create a mock coroutine for run_debug to avoid coroutine not awaited warning if needed
        async def mock_run_debug(*args, **kwargs):
            mock_event = MagicMock()
            mock_event.content.parts = [MagicMock(text="Offer received")]
            return [mock_event]

        with patch("google.adk.runners.Runner") as MockRunner, \
             patch("google.adk.agents.llm_agent.LlmAgent") as MockLlmAgent, \
             patch("src.core.model_factory.create_llm_model"), \
             patch("google.adk.agents.remote_a2a_agent.RemoteA2aAgent") as MockRemote, \
             patch("google.adk.artifacts.in_memory_artifact_service.InMemoryArtifactService"), \
             patch("google.adk.sessions.DatabaseSessionService"), \
             patch("src.core.memory.FileMemoryService"), \
             patch("src.agents.guide_agent.create_guide_agent", side_effect=guide_agent.create_guide_agent) as mock_create_agent: # We want to test logic inside create_guide

            # Setup Runner mock
            mock_runner_instance = MagicMock()
            mock_runner_instance.run_debug = AsyncMock(side_effect=mock_run_debug)
            MockRunner.return_value = mock_runner_instance

            yield {
                "MockRunner": MockRunner,
                "MockRemote": MockRemote,
                "mock_create_agent": mock_create_agent
            }

    def test_create_guide_offer_message(self):
        msg = guide_agent.create_guide_offer_message(
            "g1", ["art"], "2023-01-01", "2023-01-02", 50.0
        )
        assert "g1" in msg
        assert "art" in msg
        assert "$50.0" in msg

    @pytest.mark.asyncio
    async def test_run_guide_agent_http(self, mock_dependencies):
        with patch.dict(os.environ, {"TRANSPORT_MODE": "http"}):
            await guide_agent.run_guide_agent(
                "g1", "http://localhost", ["art"], "start", "end", 50.0
            )

            # Check if RemoteA2aAgent was initialized with URL card
            mock_dependencies["MockRemote"].assert_called_once()
            call_kwargs = mock_dependencies["MockRemote"].call_args.kwargs
            assert "agent_card" in call_kwargs
            assert isinstance(call_kwargs["agent_card"], str)
            assert "http" in call_kwargs["agent_card"]

            # Check runner execution
            mock_dependencies["MockRunner"].assert_called_once()
            mock_dependencies["MockRunner"].return_value.run_debug.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_guide_agent_slim(self, mock_dependencies):
        # Mock SLIM specific things - patching "core.slim_transport" because guide_agent imports "from core..."
        # If imports are aliased, we need to be careful.
        # We can try strict patching of the object if we can import it, but easier to try the path `core...`

        with patch.dict(os.environ, {"TRANSPORT_MODE": "slim", "SCHEDULER_SLIM_TOPIC": "topic"}), \
             patch("core.slim_transport.create_slim_client_factory", new_callable=AsyncMock) as mock_iso_factory, \
             patch("core.slim_transport.config_from_env") as mock_config, \
             patch("core.slim_transport.minimal_slim_agent_card") as mock_card_helper, \
             patch("src.core.slim_transport.create_slim_client_factory", new_callable=AsyncMock) as mock_iso_factory_src, \
             patch("src.core.slim_transport.config_from_env") as mock_config_src, \
             patch("src.core.slim_transport.minimal_slim_agent_card") as mock_card_helper_src:

            # Setup both mocks just in case
            mock_config.return_value = MagicMock(endpoint="slim://", local_id="id", shared_secret="s", tls_insecure=True)
            mock_iso_factory.return_value = MagicMock()

            mock_config_src.return_value = MagicMock(endpoint="slim://", local_id="id", shared_secret="s", tls_insecure=True)
            mock_iso_factory_src.return_value = MagicMock()

            await guide_agent.run_guide_agent(
                "g1", "http://localhost", ["art"], "start", "end", 50.0
            )

            # Check if either path was called
            if mock_card_helper.called:
                mock_card_helper.assert_called_with("topic")
                mock_iso_factory.assert_awaited_once()
            elif mock_card_helper_src.called:
                mock_card_helper_src.assert_called_with("topic")
                mock_iso_factory_src.assert_awaited_once()
            else:
                 # If neither called, something is wrong
                 assert False, "Neither core nor src.core mocks were called"


    @pytest.mark.asyncio
    async def test_run_guide_agent_slim_import_error(self, mock_dependencies):
        """Test fallback to HTTP when SLIM import fails."""
        with patch.dict(os.environ, {"TRANSPORT_MODE": "slim"}), \
             patch("core.slim_transport.create_slim_client_factory", side_effect=ImportError("No SLIM")), \
             patch("src.core.slim_transport.create_slim_client_factory", side_effect=ImportError("No SLIM")):

            # Should not raise, just log error and fallback to http (which uses RemoteA2aAgent with URL)
            await guide_agent.run_guide_agent(
                 "g1", "http://localhost", ["art"], "start", "end", 50.0
            )

            # Verify fallback to HTTP transport
            mock_dependencies["MockRemote"].assert_called()
            # The agent card should be a string (URL) not an object
            call_kwargs = mock_dependencies["MockRemote"].call_args.kwargs
            assert isinstance(call_kwargs.get("agent_card"), str)

    @pytest.mark.asyncio
    async def test_run_guide_agent_slim_generic_error(self, mock_dependencies):
        """Test exception propagation when SLIM creation fails with generic error."""
        with patch.dict(os.environ, {"TRANSPORT_MODE": "slim"}), \
             patch("core.slim_transport.create_slim_client_factory", side_effect=ValueError("Boom")), \
             patch("core.slim_transport.config_from_env"), \
             patch("src.core.slim_transport.create_slim_client_factory", side_effect=ValueError("Boom")), \
             patch("src.core.slim_transport.config_from_env"):

            with pytest.raises(ValueError, match="Boom"):
                await guide_agent.run_guide_agent(
                     "g1", "http://localhost", ["art"], "start", "end", 50.0
                )

    @pytest.mark.asyncio
    async def test_run_guide_agent_retry_failure(self, mock_dependencies):
        """Test retry logic failure."""
        mock_runner = mock_dependencies["MockRunner"].return_value
        # Make run_debug raise exceptions
        mock_runner.run_debug.side_effect = Exception("Connection failed")

        # Speed up retry delay
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
             with pytest.raises(Exception, match="Connection failed"):
                await guide_agent.run_guide_agent(
                    "g1", "http://localhost", ["art"], "start", "end", 50.0
                )

             # Should have retried multiple times (max_retries=30)
             assert mock_runner.run_debug.call_count == 30
             assert mock_sleep.call_count == 29

    def test_main(self, mock_dependencies):
        runner = CliRunner()
        with patch("sys.exit"), \
             patch("asyncio.run") as mock_run:

            result = runner.invoke(guide_agent.main, [
                "--guide-id", "g1",
                "--categories", "art,history"
            ])

            assert result.exit_code == 0
            mock_run.assert_called_once()
