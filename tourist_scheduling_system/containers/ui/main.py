#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
UI Dashboard Agent Entry Point for Container Deployment

This is the main entry point for the UI dashboard agent when deployed as a container.
It follows the ADK GKE deployment pattern.

Usage:
    python main.py --host 0.0.0.0 --port 10021 --dashboard
    python main.py --transport slim --slim-endpoint http://slim:46357
"""

import asyncio
import logging
import os
import sys

import click
import uvicorn

# Add src to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Now we can import from agents and core
import agents.ui_agent as ui_agent_module
from agents.ui_agent import (
    get_ui_agent,
    create_ui_app,
    create_ui_a2a_components,
    get_dashboard_state,
    DashboardState,
    SLIM_AVAILABLE,
    TRACING_AVAILABLE,
)

logger = logging.getLogger(__name__)


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=10021, type=int, help="Port to bind to")
@click.option("--transport", type=click.Choice(["http", "slim"]), default="http",
              help="Transport protocol: http or slim")
@click.option("--slim-endpoint", default=None, help="SLIM node endpoint")
@click.option("--slim-local-id", default=None, help="SLIM local agent ID")
@click.option("--dashboard/--no-dashboard", default=True, help="Enable web dashboard UI")
@click.option("--tracing/--no-tracing", default=False, help="Enable OpenTelemetry tracing")
def main(host: str, port: int, transport: str, slim_endpoint: str, slim_local_id: str, dashboard: bool, tracing: bool):
    """Run the UI Dashboard Agent as an A2A server."""
    logging.basicConfig(level=logging.INFO)

    # Initialize tracing if enabled
    if tracing and TRACING_AVAILABLE:
        from core.tracing import setup_tracing
        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        setup_tracing(
            service_name="ui-dashboard-agent",
            otlp_endpoint=otlp_endpoint,
            file_export=True,
        )
        logger.info("[ADK UI] OpenTelemetry tracing enabled")

    # Set up dashboard if enabled
    dashboard_app = None
    if dashboard:
        try:
            from core.dashboard import (
                create_dashboard_app,
                set_dashboard_state,
                set_transport_mode,
                broadcast_to_clients,
            )
            # Use global dashboard state from agent
            dashboard_state = get_dashboard_state()
            set_dashboard_state(dashboard_state)
            set_transport_mode(transport)
            dashboard_app = create_dashboard_app()

            # Setup broadcaster for agent to notify dashboard
            async def broadcaster():
                # Broadcast current state
                await broadcast_to_clients({
                    "type": "state_update",
                    "data": dashboard_state.to_dict()
                })

            # Hook into agent's broadcaster
            ui_agent_module._broadcaster = broadcaster

            logger.info(f"[ADK UI] Web dashboard enabled at http://{host}:{port}")
        except ImportError as e:
            logger.warning(f"[ADK UI] Dashboard module not available: {e}")
            dashboard = False

    if transport == "slim":
        if not SLIM_AVAILABLE:
            logger.error("[ADK UI] SLIM transport requested but slimrpc/slima2a not installed")
            raise SystemExit(1)

        from core.slim_transport import config_from_env, create_slim_server

        # Load SLIM config
        slim_config = config_from_env(prefix="UI_")
        if slim_endpoint:
            slim_config.endpoint = slim_endpoint
        if slim_local_id:
            slim_config.local_id = slim_local_id
        else:
            slim_config.local_id = "agntcy/tourist_scheduling/adk_ui"

        logger.info(f"[ADK UI] Starting with SLIM transport")
        logger.info(f"[ADK UI] SLIM endpoint: {slim_config.endpoint}")
        logger.info(f"[ADK UI] SLIM local ID: {slim_config.local_id}")

        # Create A2A components
        agent_card, request_handler = create_ui_a2a_components(host=host, port=port)

        # Create SLIM server
        start_server = create_slim_server(slim_config, agent_card, request_handler)

        async def run_slim_server():
            logger.info("[ADK UI] Starting SLIM server...")
            server, local_app, server_task = await start_server()
            logger.info("[ADK UI] SLIM server running")

            tasks = [server_task]

            # If dashboard enabled, also run the dashboard web server
            if dashboard_app:
                dashboard_config = uvicorn.Config(
                    dashboard_app,
                    host=host,
                    port=port,
                    log_level="warning",
                )
                dashboard_server = uvicorn.Server(dashboard_config)
                dashboard_task = asyncio.create_task(dashboard_server.serve())
                tasks.append(dashboard_task)
                logger.info(f"[ADK UI] Dashboard running at http://{host}:{port}")

            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                logger.info("[ADK UI] SLIM server cancelled")

        try:
            asyncio.run(run_slim_server())
        except KeyboardInterrupt:
            logger.info("[ADK UI] Shutting down...")
    else:
        # HTTP transport with dashboard
        if dashboard_app:
            # Mount the A2A app under the dashboard app
            from starlette.routing import Mount
            a2a_app = create_ui_app(host=host, port=port)
            dashboard_app.routes.append(Mount("/a2a", app=a2a_app))
            logger.info(f"[ADK UI] Starting with dashboard on http://{host}:{port}")
            uvicorn.run(dashboard_app, host=host, port=port)
        else:
            # Just A2A server
            logger.info(f"Starting UI Dashboard Agent on {host}:{port}")
            app = create_ui_app(host=host, port=port)
            uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
