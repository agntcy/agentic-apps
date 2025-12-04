#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
ADK Agent Demo Runner

Runs the Google ADK-based tourist scheduling system demo.
This demonstrates multi-agent coordination using:
- Scheduler Agent (A2A server)
- Guide Agents (LLM-powered via RemoteA2aAgent)
- Tourist Agents (LLM-powered via RemoteA2aAgent)
- UI Dashboard Agent (real-time monitoring)

All agents use Azure OpenAI via LiteLLM.

Supports two transport modes:
- HTTP: Standard HTTP-based A2A transport
- SLIM: Encrypted SLIM messaging transport (requires slimrpc/slima2a)
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import click

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Set up file logging
from core.logging_config import setup_root_logging, get_log_dir

setup_root_logging(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log startup info
log_dir = get_log_dir()
logger.info(f"Logs will be written to: {log_dir}")

# Set up OpenTelemetry tracing
from core.tracing import setup_tracing, get_tracer, create_span, traced

tracing_provider = setup_tracing(
    service_name="tourist-scheduling-demo",
    file_export=True,
    console_export=os.environ.get("OTEL_CONSOLE_EXPORT", "").lower() == "true",
)
if tracing_provider:
    logger.info("OpenTelemetry tracing enabled")


class AgentProcess:
    """Manages a subprocess for an agent."""

    def __init__(self, name: str, command: list, env: dict = None):
        self.name = name
        self.command = command
        self.env = env or {}
        self.process = None

    def start(self):
        """Start the agent process."""
        full_env = os.environ.copy()
        full_env.update(self.env)
        full_env["PYTHONPATH"] = str(src_path) + ":" + full_env.get("PYTHONPATH", "")

        logger.info(f"Starting {self.name}...")
        self.process = subprocess.Popen(
            self.command,
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return self

    def stop(self):
        """Stop the agent process."""
        if self.process:
            logger.info(f"Stopping {self.name}...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def is_running(self):
        """Check if process is still running."""
        return self.process and self.process.poll() is None


@traced("demo_simulation")
async def run_demo_simulation(
    scheduler_port: int = 10000,
    ui_port: int = 10021,
    num_guides: int = 2,
    num_tourists: int = 3,
):
    """
    Run a demo simulation that sends requests to the scheduler via A2A.
    This simulates guide and tourist agents registering and getting matched.
    The scheduler's tools send updates to the dashboard automatically.
    """
    import httpx
    import uuid
    from core.tracing import add_span_event, set_span_attribute

    set_span_attribute("scheduler.port", scheduler_port)
    set_span_attribute("ui.port", ui_port)
    set_span_attribute("num_guides", num_guides)
    set_span_attribute("num_tourists", num_tourists)

    scheduler_url = f"http://localhost:{scheduler_port}"
    dashboard_url = f"http://localhost:{ui_port}"

    # Wait for dashboard to be ready
    print("🔄 Waiting for dashboard to be ready...")
    for attempt in range(30):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{dashboard_url}/health")
                if response.status_code == 200:
                    print("✅ Dashboard is ready")
                    break
        except Exception:
            pass
        await asyncio.sleep(1)
    else:
        print("⚠️ Dashboard not ready after 30 seconds, continuing anyway...")

    # Guide profiles for simulation
    guide_profiles = [
        {"id": "marco", "categories": ["culture", "history"], "rate": 50, "max_group": 4},
        {"id": "florence", "categories": ["food", "wine"], "rate": 75, "max_group": 6},
        {"id": "lucia", "categories": ["art", "museums"], "rate": 60, "max_group": 5},
        {"id": "giovanni", "categories": ["adventure", "nature"], "rate": 45, "max_group": 8},
        {"id": "sophia", "categories": ["nightlife", "entertainment"], "rate": 80, "max_group": 10},
    ]

    # Tourist profiles for simulation
    tourist_profiles = [
        {"id": "alice", "preferences": ["culture", "history"], "budget": 80},
        {"id": "bob", "preferences": ["food", "wine"], "budget": 120},
        {"id": "charlie", "preferences": ["art", "museums"], "budget": 100},
        {"id": "diana", "preferences": ["adventure", "nature"], "budget": 60},
        {"id": "eve", "preferences": ["nightlife", "entertainment"], "budget": 150},
    ]

    async def send_a2a_message(message: str) -> str:
        """Send a message to the scheduler via A2A protocol."""
        task_id = str(uuid.uuid4())

        # Create A2A JSON-RPC request using message/send method
        request = {
            "jsonrpc": "2.0",
            "id": task_id,
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": message}],
                    "messageId": task_id,
                }
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    scheduler_url,
                    json=request,
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code == 200:
                    result = response.json()
                    # Extract text from A2A response
                    if "result" in result:
                        res = result["result"]
                        # Check for parts in the result
                        if isinstance(res, dict) and "parts" in res:
                            for part in res["parts"]:
                                if "text" in part:
                                    return part["text"]
                        # Check for artifacts
                        if isinstance(res, dict) and "artifacts" in res:
                            for artifact in res["artifacts"]:
                                if "parts" in artifact:
                                    for part in artifact["parts"]:
                                        if "text" in part:
                                            return part["text"]
                        return str(res)
                    elif "error" in result:
                        return f"Error: {result['error']}"
                    return str(result)
                else:
                    return f"Error: {response.status_code}"
            except Exception as e:
                return f"Error: {e}"

    async def send_to_dashboard(data: dict):
        """Send update directly to dashboard."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(f"{dashboard_url}/api/update", json=data)
                if response.status_code == 200:
                    logger.debug(f"Dashboard updated: {data.get('type')}")
        except Exception as e:
            logger.debug(f"Failed to update dashboard: {e}")

    # Register guides
    guides_to_register = guide_profiles[:num_guides]
    print(f"📝 Registering {len(guides_to_register)} guides...")
    for guide in guides_to_register:
        message = (
            f"Register guide {guide['id']} specializing in {', '.join(guide['categories'])}, "
            f"available 2025-06-01T08:00:00 to 2025-06-01T18:00:00, "
            f"rate ${guide['rate']}/hour, max {guide['max_group']} tourists"
        )
        print(f"   🗺️ Guide {guide['id']}: {', '.join(guide['categories'])} @ ${guide['rate']}/hr")
        result = await send_a2a_message(message)
        logger.debug(f"Guide registration result: {result[:100]}...")

        # Send update directly to dashboard
        await send_to_dashboard({
            "type": "guide_offer",
            "guide_id": guide['id'],
            "categories": guide['categories'],
            "hourly_rate": guide['rate'],
            "max_group_size": guide['max_group'],
            "availability": {"start": "2025-06-01T08:00:00", "end": "2025-06-01T18:00:00"}
        })
        await asyncio.sleep(1.0)

    print()

    # Register tourists
    tourists_to_register = tourist_profiles[:num_tourists]
    print(f"📝 Registering {len(tourists_to_register)} tourists...")
    for tourist in tourists_to_register:
        message = (
            f"Register tourist {tourist['id']} with availability from 2025-06-01T09:00:00 to 2025-06-01T17:00:00, "
            f"preferences for {', '.join(tourist['preferences'])}, budget ${tourist['budget']}/hour"
        )
        print(f"   🧳 Tourist {tourist['id']}: {', '.join(tourist['preferences'])} @ ${tourist['budget']}/hr budget")
        result = await send_a2a_message(message)
        logger.debug(f"Tourist registration result: {result[:100]}...")

        # Send update directly to dashboard
        await send_to_dashboard({
            "type": "tourist_request",
            "tourist_id": tourist['id'],
            "preferences": tourist['preferences'],
            "budget": tourist['budget'],
            "availability": {"start": "2025-06-01T09:00:00", "end": "2025-06-01T17:00:00"}
        })
        await asyncio.sleep(1.0)

    print()

    # Run scheduling
    print("🔄 Running scheduling algorithm...")
    result = await send_a2a_message(
        "Run the scheduling algorithm to match tourists with guides based on their preferences and budgets."
    )
    print(f"   {result[:200]}..." if len(result) > 200 else f"   {result}")

    # Create assignments and send to dashboard
    for i, tourist in enumerate(tourists_to_register):
        if i < len(guides_to_register):
            guide = guides_to_register[i]
            await send_to_dashboard({
                "type": "assignment",
                "tourist_id": tourist['id'],
                "guide_id": guide['id'],
                "categories": guide['categories'],
                "total_cost": guide['rate'] * 8,
                "time_window": {"start": "2025-06-01T09:00:00", "end": "2025-06-01T17:00:00"}
            })
            await asyncio.sleep(0.5)

    print()

    # Get final status
    print("📊 Getting final status...")
    result = await send_a2a_message("Show me the final schedule status with all assignments.")
    print(f"   {result[:500]}..." if len(result) > 500 else f"   {result}")


async def run_console_demo():
    """Run an interactive console demo of the scheduler agent."""
    from google.adk.runners import InMemoryRunner
    from agents.scheduler_agent import get_scheduler_agent
    from agents.tools import clear_scheduler_state

    # Clear state for fresh demo
    clear_scheduler_state()

    print("=" * 70)
    print("🎯 ADK Tourist Scheduling Demo - Console Mode")
    print("=" * 70)
    print()
    print("This demo shows the scheduler agent processing requests and offers")
    print("using Azure OpenAI via LiteLLM.")
    print()

    runner = InMemoryRunner(agent=get_scheduler_agent())

    # Demo scenario
    demo_steps = [
        {
            "description": "📝 Registering Tourist Alice (culture enthusiast, $80/hr budget)",
            "message": "Register tourist alice with availability from 2025-06-01T09:00:00 to 2025-06-01T17:00:00, preferences for culture and history, budget $80/hour",
        },
        {
            "description": "📝 Registering Tourist Bob (food lover, $120/hr budget)",
            "message": "Register tourist bob with availability from 2025-06-01T10:00:00 to 2025-06-01T18:00:00, preferences for food and wine, budget $120/hour",
        },
        {
            "description": "🗺️ Registering Guide Marco (culture & history expert, $50/hr)",
            "message": "Register guide marco specializing in culture and history, available 2025-06-01T08:00:00 to 2025-06-01T16:00:00, rate $50/hour, max 4 tourists",
        },
        {
            "description": "🗺️ Registering Guide Florence (food & wine expert, $75/hr)",
            "message": "Register guide florence specializing in food, wine, and gastronomy, available 2025-06-01T11:00:00 to 2025-06-01T19:00:00, rate $75/hour, max 6 tourists",
        },
        {
            "description": "📊 Checking current scheduler status",
            "message": "What's the current scheduler status? Show me all tourists and guides.",
        },
        {
            "description": "🔄 Running the scheduling algorithm",
            "message": "Run the scheduling algorithm to match tourists with guides based on their preferences and budgets.",
        },
        {
            "description": "📋 Final status after scheduling",
            "message": "Show me the final schedule status with all assignments.",
        },
    ]

    for i, step in enumerate(demo_steps, 1):
        print(f"\n{'─' * 70}")
        print(f"Step {i}/{len(demo_steps)}: {step['description']}")
        print(f"{'─' * 70}")
        print(f">> {step['message']}")
        print()

        events = await runner.run_debug(
            user_messages=step["message"],
            quiet=True,
        )

        # Extract and print agent response
        for event in events:
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        print(f"🤖 Agent: {part.text}")

        # Brief pause between steps
        await asyncio.sleep(0.5)

    print()
    print("=" * 70)
    print("✅ Demo Complete!")
    print("=" * 70)
    print()
    print("The scheduler successfully:")
    print("  1. Registered tourist requests with preferences and budgets")
    print("  2. Registered guide offers with specialties and rates")
    print("  3. Matched tourists to guides based on compatibility")
    print()


async def run_a2a_server_demo(
    port: int = 10000,
    host: str = "localhost",
    transport: str = "http",
    slim_endpoint: str = None,
):
    """Run the scheduler as an A2A server for multi-agent demo."""
    import uvicorn
    from agents.scheduler_agent import create_scheduler_app, create_scheduler_a2a_components

    if transport == "slim":
        from core.slim_transport import (
            SLIMConfig,
            create_slim_server,
            config_from_env,
        )

        print("=" * 70)
        print("🌐 ADK Tourist Scheduling Demo - SLIM A2A Server Mode")
        print("=" * 70)
        print()
        print(f"Starting ADK Scheduler Agent with SLIM transport")

        # Load SLIM config
        slim_config = config_from_env(prefix="SCHEDULER_")
        if slim_endpoint:
            slim_config.endpoint = slim_endpoint
        slim_config.local_id = "agntcy/tourist_scheduling/adk_scheduler"

        print(f"  SLIM Endpoint: {slim_config.endpoint}")
        print(f"  SLIM Local ID: {slim_config.local_id}")
        print()
        print("Other SLIM-enabled agents can now connect to this scheduler.")
        print("Press Ctrl+C to stop.")
        print()

        # Create A2A components
        agent_card, request_handler = create_scheduler_a2a_components(host=host, port=port)

        # Create and run SLIM server
        start_server = create_slim_server(slim_config, agent_card, request_handler)
        server, local_app, server_task = await start_server()
        print(f"✅ SLIM server running")

        try:
            await server_task
        except asyncio.CancelledError:
            print("🛑 SLIM server stopped")
    else:
        print("=" * 70)
        print("🌐 ADK Tourist Scheduling Demo - A2A Server Mode")
        print("=" * 70)
        print()
        print(f"Starting ADK Scheduler Agent A2A Server")
        print(f"  Endpoint: http://{host}:{port}/")
        print(f"  Agent Card: http://{host}:{port}/.well-known/agent.json")
        print()
        print("Other ADK agents can now connect to this scheduler.")
        print("Press Ctrl+C to stop.")
        print()

        app = create_scheduler_app(host=host, port=port)

        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


def run_multi_agent_demo(
    scheduler_port: int = 10000,
    ui_port: int = 10011,
    num_guides: int = 2,
    num_tourists: int = 3,
    transport: str = "http",
    slim_endpoint: str = None,
):
    """Run a full multi-agent demo with all ADK agents."""
    print("=" * 70)
    print("🚀 ADK Multi-Agent Demo")
    print("=" * 70)
    print()
    if transport == "slim":
        print("Starting the complete tourist scheduling system with ADK agents (SLIM):")
    else:
        print("Starting the complete tourist scheduling system with ADK agents:")
    print(f"  • Scheduler Agent (port {scheduler_port})")
    print(f"  • UI Dashboard Agent (port {ui_port})")
    print(f"  • {num_guides} Guide Agents (simulated)")
    print(f"  • {num_tourists} Tourist Agents (simulated)")
    if transport == "slim":
        print(f"  • Transport: SLIM (endpoint: {slim_endpoint or 'default'})")
    print()

    processes = []

    try:
        # Determine transport-specific options
        transport_args = []
        if transport == "slim":
            transport_args = ["--transport", "slim"]
            if slim_endpoint:
                transport_args.extend(["--slim-endpoint", slim_endpoint])

        # Start Scheduler Agent
        scheduler_cmd = [
            sys.executable, "-m", "agents.scheduler_agent",
            "--mode", "a2a", "--port", str(scheduler_port), "--host", "localhost",
        ] + transport_args
        if transport == "slim":
            scheduler_cmd.extend(["--slim-local-id", "agntcy/tourist_scheduling/adk_scheduler"])

        scheduler = AgentProcess(
            "Scheduler Agent",
            scheduler_cmd,
        )
        scheduler.start()
        processes.append(scheduler)
        time.sleep(3)  # Wait for scheduler to be ready

        # Start UI Agent with dashboard
        ui_cmd = [
            sys.executable, "-m", "agents.ui_agent",
            "--port", str(ui_port), "--host", "localhost", "--dashboard",
        ] + transport_args
        if transport == "slim":
            ui_cmd.extend(["--slim-local-id", "agntcy/tourist_scheduling/adk_ui"])

        ui = AgentProcess(
            "UI Dashboard Agent",
            ui_cmd,
        )
        ui.start()
        processes.append(ui)

        # Wait for dashboard to be ready
        print()
        print("⏳ Waiting for dashboard to be ready...")
        dashboard_ready = False
        for _ in range(10):  # Wait up to 10 seconds
            try:
                import httpx
                response = httpx.get(f"http://localhost:{ui_port}/health", timeout=1.0)
                if response.status_code == 200:
                    dashboard_ready = True
                    break
            except Exception:
                pass
            time.sleep(1)

        if not dashboard_ready:
            print("   ⚠️  Dashboard may not be fully ready, continuing anyway...")
        else:
            print("   ✅ Dashboard ready!")

        print()
        print("✅ Core agents started!")
        print(f"   📊 Dashboard: http://localhost:{ui_port}")
        print(f"   🗓️  Scheduler: http://localhost:{scheduler_port}")
        print()

        # Run the demo simulation
        print("🎬 Running demo simulation...")
        print()
        asyncio.run(run_demo_simulation(
            scheduler_port=scheduler_port,
            ui_port=ui_port,
            num_guides=num_guides,
            num_tourists=num_tourists,
        ))

        print()
        print("✅ Demo simulation complete!")
        print(f"   📊 View results at: http://localhost:{ui_port}")
        print()
        print("Press Ctrl+C to stop all agents...")

        # Keep running until interrupted
        while True:
            time.sleep(1)
            # Check if core agents are still running
            if not scheduler.is_running():
                logger.error("Scheduler agent stopped unexpectedly!")
                # Try to get output from the scheduler process
                if scheduler.process and scheduler.process.stdout:
                    try:
                        output = scheduler.process.stdout.read()
                        if output:
                            logger.error(f"Scheduler output: {output}")
                    except Exception as e:
                        logger.error(f"Could not read scheduler output: {e}")
                break

    except KeyboardInterrupt:
        print()
        print("🛑 Stopping all agents...")
    finally:
        for proc in reversed(processes):
            proc.stop()
        print("✅ All agents stopped.")


@click.command()
@click.option("--mode", type=click.Choice(["console", "server", "multi"]),
              default="console",
              help="Demo mode: console (interactive), server (A2A), or multi (all agents)")
@click.option("--port", default=10000, help="Scheduler port")
@click.option("--host", default="localhost", help="Host to bind to")
@click.option("--guides", default=2, help="Number of guide agents (multi mode)")
@click.option("--tourists", default=3, help="Number of tourist agents (multi mode)")
@click.option("--transport", type=click.Choice(["http", "slim"]), default="http",
              help="Transport protocol: http or slim (requires slimrpc/slima2a)")
@click.option("--slim-endpoint", default=None, help="SLIM node endpoint (for slim transport)")
def main(mode: str, port: int, host: str, guides: int, tourists: int,
         transport: str, slim_endpoint: str):
    """
    Run the ADK-based Tourist Scheduling Demo.

    Modes:

    \b
    - console: Interactive demo in the terminal showing the scheduler
               processing requests with Azure OpenAI

    \b
    - server:  Start the scheduler as an A2A server for remote agents
               to connect to

    \b
    - multi:   Full multi-agent demo with scheduler, UI dashboard,
               and multiple guide/tourist agents

    Transport:

    \b
    - http:    Standard HTTP-based A2A transport (default)
    - slim:    Encrypted SLIM messaging transport (requires slimrpc)
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Check for Azure credentials
    if not (os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY")):
        print("⚠️  Warning: No Azure API key found!")
        print("   Set AZURE_OPENAI_API_KEY or source your env file.")
        print()

    # Check SLIM availability if requested
    if transport == "slim":
        try:
            from core.slim_transport import check_slim_available
            if not check_slim_available():
                print("❌ Error: SLIM transport requested but slimrpc/slima2a not installed!")
                print("   Install with: pip install slimrpc slima2a")
                return
        except ImportError:
            print("❌ Error: SLIM transport requested but core.slim_transport not available!")
            return
        print(f"✅ SLIM transport available")

    if mode == "console":
        asyncio.run(run_console_demo())
    elif mode == "server":
        asyncio.run(run_a2a_server_demo(
            port=port,
            host=host,
            transport=transport,
            slim_endpoint=slim_endpoint,
        ))
    elif mode == "multi":
        run_multi_agent_demo(
            scheduler_port=port,
            ui_port=port + 11,  # e.g., 10011 if scheduler is 10000
            num_guides=guides,
            num_tourists=tourists,
            transport=transport,
            slim_endpoint=slim_endpoint,
        )


if __name__ == "__main__":
    main()
