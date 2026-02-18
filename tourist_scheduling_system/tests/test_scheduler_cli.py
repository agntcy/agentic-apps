
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from click.testing import CliRunner
import asyncio
import uvicorn

# Import the module to be tested
from src.agents import scheduler_agent

class TestSchedulerCLI:

    @pytest.fixture
    def mock_dependencies(self):
        """Mock external dependencies"""
        # Create a mock coroutine for wait()
        async def mock_wait():
            return True

            # Set return value for create_scheduler_a2a_components to return 2 items
            mock_components_val = MagicMock()
            mock_components_val.__iter__.return_value = [MagicMock(), MagicMock()]
            # Or better, just set return value to a tuple
            create_components_mock = patch("src.agents.scheduler_agent.create_scheduler_a2a_components").start()
            create_components_mock.return_value = (MagicMock(), MagicMock())

        with patch("src.agents.scheduler_agent.setup_tracing"), \
             patch("src.agents.scheduler_agent.setup_agent_logging"), \
             patch("src.agents.scheduler_agent.check_slim_available", return_value=True), \
             patch("uvicorn.run"), \
             patch("uvicorn.Server"), \
             patch("src.agents.scheduler_agent.create_scheduler_app"), \
             patch("src.agents.scheduler_agent.create_scheduler_a2a_components", return_value=(MagicMock(), MagicMock())) as mock_create_components, \
             patch("src.agents.scheduler_agent.run_console_demo", new_callable=AsyncMock) as mock_demo, \
             patch("src.agents.scheduler_agent.create_slim_server", new_callable=AsyncMock) as mock_create_slim:

            # Setup SLIM server mock
            mock_server_instance = AsyncMock()
            mock_server_instance.serve = AsyncMock()
            mock_create_slim.return_value = AsyncMock(return_value=(mock_server_instance, MagicMock(), mock_wait()))

            yield {
                "mock_demo": mock_demo,
                "mock_create_slim": mock_create_slim,
                "create_app": scheduler_agent.create_scheduler_app,
                "create_components": mock_create_components,
                "uvicorn_run": uvicorn.run
            }

    def test_main_console_mode(self, mock_dependencies):
        runner = CliRunner()
        result = runner.invoke(scheduler_agent.main, ["--mode", "console"])
        assert result.exit_code == 0
        mock_dependencies["mock_demo"].assert_called_once()

    def test_main_http_mode(self, mock_dependencies):
        runner = CliRunner()
        # Default is console, so we need to override or check default which is http in logic but cli default is console
        # The CLI default is actually "console". Logic says: if mode == "console" ... else: ...

        # Test HTTP path
        with patch("uvicorn.run") as mock_run:
            result = runner.invoke(scheduler_agent.main, ["--mode", "a2a", "--transport", "http"])
            assert result.exit_code == 0
            mock_run.assert_called_once()
            mock_dependencies["create_app"].assert_called_once()

    def test_main_slim_mode(self, mock_dependencies):
        # We need to mock asyncio.run to avoid event loop issues if any,
        # but the main function calls asyncio.run(run_slim_server())

        # Since we mocked create_slim_server which returns an async function (start_server)
        # We need to make sure the structure matches what main expects.

        # main expects: start_server = create_slim_server(...)
        # then await start_server() returns (server, local_app, server_task)

        runner = CliRunner()
        # Mock sys.exit to prevent actual exit if something goes wrong
        with patch("sys.exit"):
            # We need to patch asyncio.run because CliRunner and asyncio can conflict
            # or just let it run if the mocks are async correct.
            # Let's mock asyncio.run for the slim path
            with patch("asyncio.run") as mock_async_run:
                result = runner.invoke(scheduler_agent.main, ["--mode", "a2a", "--transport", "slim"])
                assert result.exit_code == 0
                mock_async_run.assert_called_once()
                # create_scheduler_a2a_components should be called
                mock_dependencies["create_components"].assert_called_once()


class TestSchedulerComponents:

    @pytest.mark.asyncio
    async def test_run_console_demo(self):
        # Mock everything needed for run_console_demo
        with patch("google.adk.runners.Runner") as MockRunner, \
             patch("src.agents.scheduler_agent.get_scheduler_agent"), \
             patch("builtins.print"):

            mock_runner_instance = MagicMock()
            MockRunner.return_value = mock_runner_instance
            mock_runner_instance.run_debug = AsyncMock(return_value=[])

            await scheduler_agent.run_console_demo()

            # Verify runner was created with specific services
            MockRunner.assert_called_once()
            kwargs = MockRunner.call_args.kwargs
            assert "session_service" in kwargs
            assert "memory_service" in kwargs

    def test_create_scheduler_a2a_components(self):
         with patch("src.agents.scheduler_agent.get_scheduler_agent"), \
              patch("src.core.a2a_cards.get_scheduler_card") as mock_get_card, \
              patch("google.adk.runners.Runner") as MockRunner, \
              patch("google.adk.a2a.executor.a2a_agent_executor.A2aAgentExecutor"), \
              patch("a2a.server.request_handlers.DefaultRequestHandler") as MockHandler:

             mock_get_card.return_value = MagicMock(name="card", version="1.0")

             card, handler = scheduler_agent.create_scheduler_a2a_components()

             assert card is not None
             assert handler is not None
             MockRunner.assert_called_once()
             MockHandler.assert_called_once()
