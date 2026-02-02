#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
ADK-based Scheduler Agent

Multi-agent tourist scheduling coordinator using Google ADK.

This agent:
1. Receives TouristRequests from tourist agents (via tool calls)
2. Receives GuideOffers from guide agents (via tool calls)
3. Runs greedy scheduling algorithm to match tourists to guides
4. Returns ScheduleProposals

The agent can be exposed via A2A protocol using ADK's to_a2a() utility.
Supports both HTTP and SLIM transports.
"""

import asyncio
import logging
import os
from typing import Optional

import click

# Initialize tracing early (before other imports use it)
try:
    from core.tracing import setup_tracing, traced, create_span, add_span_event
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False

# Tools for the scheduler (these don't require ADK at import time)
from .tools import (
    register_tourist_request,
    register_guide_offer,
    run_scheduling,
    get_schedule_status,
    clear_scheduler_state,
)

# Set up file logging
try:
    from core.logging_config import setup_agent_logging
    logger = setup_agent_logging("adk_scheduler")
except ImportError:
    logger = logging.getLogger(__name__)

# Check SLIM availability
try:
    from core.slim_transport import (
        SLIMConfig,
        check_slim_available,
        create_slim_server,
        config_from_env,
    )
    SLIM_AVAILABLE = check_slim_available()
except ImportError:
    SLIM_AVAILABLE = False


# Lazy-loaded scheduler agent singleton
_scheduler_agent = None


def get_scheduler_agent():
    """
    Get or create the scheduler agent.

    Uses lazy initialization to avoid importing google.adk at module load time.

    Returns:
        The scheduler LlmAgent instance
    """
    global _scheduler_agent

    if _scheduler_agent is None:
        # Import ADK components at runtime
        from google.adk.agents.llm_agent import LlmAgent
        from google.adk.models.lite_llm import LiteLlm
        from google.adk.tools import load_memory

        # Get model configuration from environment
        from core.model_factory import create_llm_model
        model = create_llm_model("scheduler")

        _scheduler_agent = LlmAgent(
            name="scheduler_agent",
            model=model,
            description=(
                "A tourist scheduling coordinator that matches tourists with tour guides. "
                "It receives requests from tourists and offers from guides, then runs "
                "a scheduling algorithm to create optimal matches."
            ),
            instruction="""You are a Tourist Scheduling Coordinator Agent.

IMPORTANT: You MUST use the provided tools for ALL operations. Never just respond with text - always call a tool.

Your job is to coordinate between tourists looking for guided tours and tour guides
offering their services. You have access to the following tools:

1. **register_tourist_request**: Register a tourist's request with their availability,
   preferences (like "culture", "history", "food"), and budget.
   REQUIRED parameters: tourist_id, availability_start, availability_end, preferences (list), budget

2. **register_guide_offer**: Register a guide's offer with their categories of expertise,
   availability window, hourly rate, and group capacity.
   REQUIRED parameters: guide_id, availability_start, availability_end, categories (list), hourly_rate, max_group_size

3. **run_scheduling**: Execute the scheduling algorithm to match tourists with guides
   based on availability, budget, and preference matching.

4. **get_schedule_status**: Check the current state of the scheduler including
   pending requests, available guides, and completed assignments.

When you receive a message:
- If it mentions "register guide" or contains guide data -> CALL register_guide_offer
- If it mentions "register tourist" or contains tourist data -> CALL register_tourist_request
- If it mentions "schedule" or "match" or "run" -> CALL run_scheduling
- If it mentions "status" -> CALL get_schedule_status

ALWAYS call the appropriate tool. Extract parameters from the message and call the tool.
Example: "Register guide marco" -> call register_guide_offer with guide_id="marco"
""",
            tools=[
                register_tourist_request,
                register_guide_offer,
                run_scheduling,
                get_schedule_status,
                clear_scheduler_state,
                load_memory,
            ],
        )

    return _scheduler_agent


# For backwards compatibility
@property
def scheduler_agent():
    """Deprecated: Use get_scheduler_agent() instead."""
    return get_scheduler_agent()


def create_scheduler_app(host: str = "localhost", port: int = 10000):
    """
    Create an A2A-enabled Starlette application for the scheduler agent.

    This uses ADK's to_a2a() utility to expose the agent via the A2A protocol,
    making it compatible with existing a2a-sdk clients.
    Uses the agent card from a2a_cards/scheduler_agent.json.

    Args:
        host: Host for the A2A RPC URL
        port: Port for the A2A server

    Returns:
        A Starlette application configured for A2A
    """
    # Import ADK components at runtime
    from google.adk.a2a.utils.agent_to_a2a import to_a2a
    from google.adk.runners import Runner
    from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
    from google.adk.sessions import DatabaseSessionService
    from src.core.memory import FileMemoryService

    # Load agent card from a2a_cards directory
    from src.core.a2a_cards import get_scheduler_card
    agent_card = get_scheduler_card(host=host, port=port)
    logger.info(f"[ADK Scheduler] Using agent card: {agent_card.name} v{agent_card.version}")

    agent = get_scheduler_agent()

    runner = Runner(
        agent=agent,
        app_name="scheduler_agent",
        artifact_service=InMemoryArtifactService(),
        session_service=DatabaseSessionService(db_url="sqlite+aiosqlite:///scheduler_sessions.db"),
        memory_service=FileMemoryService("scheduler_memory.json")
    )

    return to_a2a(
        agent,
        host=host,
        port=port,
        protocol="http",
        agent_card=agent_card,
        runner=runner,
    )


def create_scheduler_a2a_components(host: str = "localhost", port: int = 10000):
    """
    Create A2A components for the scheduler agent (for SLIM transport).

    Returns the AgentCard and DefaultRequestHandler that can be used
    with SLIM transport. Uses the agent card from a2a_cards/scheduler_agent.json.

    Args:
        host: Host for the A2A RPC URL
        port: Port for the A2A server

    Returns:
        Tuple of (agent_card, request_handler)
    """
    from google.adk.runners import InMemoryRunner
    from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
    from a2a.server.request_handlers import DefaultRequestHandler
    from a2a.server.tasks import InMemoryTaskStore

    # Load agent card from a2a_cards directory
    from src.core.a2a_cards import get_scheduler_card
    agent_card = get_scheduler_card(host=host, port=port)
    logger.info(f"[ADK Scheduler] Loaded agent card: {agent_card.name} v{agent_card.version}")

    agent = get_scheduler_agent()

    # Create runner for the agent
    from google.adk.runners import Runner
    from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
    from google.adk.sessions import DatabaseSessionService
    from src.core.memory import FileMemoryService

    runner = Runner(
        agent=agent,
        app_name="scheduler_agent",
        artifact_service=InMemoryArtifactService(),
        session_service=DatabaseSessionService(db_url="sqlite+aiosqlite:///scheduler_sessions.db"),
        memory_service=FileMemoryService("scheduler_memory.json")
    )

    # Create A2A executor wrapping the ADK runner
    agent_executor = A2aAgentExecutor(runner=runner)

    # Create request handler
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=InMemoryTaskStore(),
    )

    return agent_card, request_handler


async def run_console_demo():
    """Run a console demo of the scheduler agent."""
    # Import ADK runner at runtime
    from google.adk.runners import Runner
    from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
    from google.adk.sessions import DatabaseSessionService
    from src.core.memory import FileMemoryService

    print("=" * 60)
    print("ADK Scheduler Agent - Console Demo")
    print("=" * 60)

    runner = Runner(
        agent=get_scheduler_agent(),
        app_name="scheduler_console_demo",
        artifact_service=InMemoryArtifactService(),
        session_service=DatabaseSessionService(db_url="sqlite+aiosqlite:///scheduler_demo_sessions.db"),
        memory_service=FileMemoryService("scheduler_demo_memory.json")
    )

    # Demo messages
    demo_messages = [
        "Register tourist t1 with availability from 2025-06-01T09:00:00 to 2025-06-01T17:00:00, preferences for culture and history, budget $100/hour",
        "Register guide g1 specializing in culture and history, available 2025-06-01T10:00:00 to 2025-06-01T14:00:00, rate $50/hour, max 5 tourists",
        "What's the current scheduler status?",
        "Run the scheduling algorithm to match tourists with guides",
    ]

    for message in demo_messages:
        print(f"\n>> User: {message}")

        events = await runner.run_debug(
            user_messages=message,
            quiet=True,
        )

        # Extract agent response
        for event in events:
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text'):
                        print(f"<< Agent: {part.text}")

    print("\n" + "=" * 60)
    print("Demo complete!")


@click.command()
@click.option("--mode", type=click.Choice(["console", "a2a"]), default="console",
              help="Run mode: console demo or A2A server")
@click.option("--port", default=10000, help="Port for A2A server")
@click.option("--host", default="localhost", help="Host for A2A server")
@click.option("--transport", type=click.Choice(["http", "slim"]), default="http",
              help="Transport protocol: http or slim")
@click.option("--slim-endpoint", default=None, help="SLIM node endpoint")
@click.option("--slim-local-id", default=None, help="SLIM local agent ID")
@click.option("--tracing/--no-tracing", default=False, help="Enable OpenTelemetry tracing")
def main(mode: str, port: int, host: str, transport: str, slim_endpoint: str, slim_local_id: str, tracing: bool):
    """Run the ADK-based scheduler agent."""
    logging.basicConfig(level=logging.INFO)

    # Initialize tracing if enabled
    if tracing and TRACING_AVAILABLE:
        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        setup_tracing(
            service_name="scheduler-agent",
            otlp_endpoint=otlp_endpoint,
            file_export=True,
        )
        logger.info("[ADK Scheduler] OpenTelemetry tracing enabled")

    if mode == "console":
        asyncio.run(run_console_demo())
    elif transport == "slim":
        # SLIM transport mode
        if not SLIM_AVAILABLE:
            logger.error("[ADK Scheduler] SLIM transport requested but slimrpc/slima2a not installed")
            logger.error("[ADK Scheduler] Install with: uv pip install slima2a")
            raise SystemExit(1)

        # Load SLIM config
        slim_config = config_from_env(prefix="SCHEDULER_")
        if slim_endpoint:
            slim_config.endpoint = slim_endpoint
        if slim_local_id:
            slim_config.local_id = slim_local_id
        elif slim_config.local_id == "agntcy/tourist_scheduling/agent":
            # Use consistent default that matches what clients expect
            slim_config.local_id = "agntcy/tourist_scheduling/scheduler"

        logger.info(f"[ADK Scheduler] Starting with SLIM transport")
        logger.info(f"[ADK Scheduler] SLIM endpoint: {slim_config.endpoint}")
        logger.info(f"[ADK Scheduler] SLIM local ID: {slim_config.local_id}")

        # Create A2A components
        agent_card, request_handler = create_scheduler_a2a_components(host=host, port=port)

        # Create SLIM server
        start_server = create_slim_server(slim_config, agent_card, request_handler)

        async def run_slim_server():
            logger.info("[ADK Scheduler] Starting SLIM server...")
            server, local_app, server_task = await start_server()
            logger.info("[ADK Scheduler] SLIM server running")

            tasks = [server_task]

            # Also start HTTP server for local API access (simulation, dashboard, etc.)
            import uvicorn
            http_app = create_scheduler_app(host=host, port=port)
            http_config = uvicorn.Config(
                http_app,
                host=host,
                port=port,
                log_level="warning",
            )
            http_server = uvicorn.Server(http_config)
            http_task = asyncio.create_task(http_server.serve())
            tasks.append(http_task)
            logger.info(f"[ADK Scheduler] HTTP server also running at http://{host}:{port}")
            logger.info("[ADK Scheduler] Press Ctrl+C to stop")

            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                logger.info("[ADK Scheduler] Servers cancelled")
            except Exception as e:
                logger.error(f"[ADK Scheduler] Server error: {e}")

        try:
            asyncio.run(run_slim_server())
        except KeyboardInterrupt:
            logger.info("[ADK Scheduler] Shutting down...")
    else:
        # HTTP transport mode (default)
        import uvicorn

        print(f"Starting ADK Scheduler Agent on {host}:{port}")
        print(f"A2A endpoint: http://{host}:{port}/")

        app = create_scheduler_app(host=host, port=port)
        uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
