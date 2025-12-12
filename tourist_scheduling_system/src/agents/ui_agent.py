#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
ADK-based UI Agent

A dashboard agent that monitors the tourist scheduling system and provides
real-time visibility into system state. Uses Google ADK with Azure OpenAI
via LiteLLM.

This agent:
1. Connects to the scheduler as a RemoteA2aAgent to receive updates
2. Maintains dashboard state (tourists, guides, assignments, metrics)
3. Can be queried about system status
4. Provides natural language summaries of scheduling activity

The agent can be exposed via A2A protocol using ADK's to_a2a() utility.
Supports both HTTP and SLIM transports.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum

# Initialize tracing early
try:
    from core.tracing import setup_tracing, traced, create_span, add_span_event
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False

# Set up file logging
try:
    from core.logging_config import setup_agent_logging
    logger = setup_agent_logging("adk_ui")
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


class TransportMode(str, Enum):
    """Transport mode for agent communication"""
    HTTP = "http"
    SLIM = "slim"
    UNKNOWN = "unknown"


@dataclass
class DashboardMetrics:
    """Real-time system metrics for dashboard"""
    total_tourists: int = 0
    total_guides: int = 0
    total_assignments: int = 0
    satisfied_tourists: int = 0
    guide_utilization: float = 0.0
    avg_assignment_cost: float = 0.0
    total_messages: int = 0
    last_updated: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "total_tourists": self.total_tourists,
            "total_guides": self.total_guides,
            "total_assignments": self.total_assignments,
            "satisfied_tourists": self.satisfied_tourists,
            "guide_utilization": self.guide_utilization,
            "avg_assignment_cost": self.avg_assignment_cost,
            "total_messages": self.total_messages,
            "last_updated": self.last_updated,
        }


@dataclass
class CommunicationEvent:
    """Represents a communication event between agents"""
    timestamp: str
    source_agent: str
    target_agent: str
    message_type: str
    summary: str

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "message_type": self.message_type,
            "summary": self.summary,
        }


# Dashboard state storage (in-memory)
@dataclass
class DashboardState:
    """Dashboard state storage"""
    tourist_requests: Dict[str, dict] = field(default_factory=dict)
    guide_offers: Dict[str, dict] = field(default_factory=dict)
    assignments: List[dict] = field(default_factory=list)
    communication_events: List[CommunicationEvent] = field(default_factory=list)
    metrics: DashboardMetrics = field(default_factory=DashboardMetrics)

    def update_metrics(self):
        """Recalculate system metrics"""
        self.metrics.total_tourists = len(self.tourist_requests)
        self.metrics.total_guides = len(self.guide_offers)
        self.metrics.total_assignments = len(self.assignments)

        # Calculate satisfied tourists (unique tourists with assignments, capped at total)
        assigned_tourists = set(a.get("tourist_id") for a in self.assignments if a.get("tourist_id"))
        self.metrics.satisfied_tourists = min(len(assigned_tourists), self.metrics.total_tourists)

        # Calculate guide utilization (unique guides with assignments, capped at 1.0)
        if self.guide_offers:
            busy_guides = set(a.get("guide_id") for a in self.assignments if a.get("guide_id"))
            self.metrics.guide_utilization = min(len(busy_guides) / len(self.guide_offers), 1.0)

        # Calculate average assignment cost
        if self.assignments:
            total_cost = sum(a.get("total_cost", 0) for a in self.assignments)
            self.metrics.avg_assignment_cost = total_cost / len(self.assignments)

        self.metrics.last_updated = datetime.now().isoformat()

    def to_dict(self) -> dict:
        """Convert state to dictionary"""
        # Handle communication_events which may be dicts or objects with to_dict()
        comm_events = []
        for e in self.communication_events[-20:]:
            if isinstance(e, dict):
                comm_events.append(e)
            elif hasattr(e, 'to_dict'):
                comm_events.append(e.to_dict())
            else:
                comm_events.append(str(e))

        return {
            "tourist_requests": list(self.tourist_requests.values()),
            "guide_offers": list(self.guide_offers.values()),
            "assignments": self.assignments,
            "communication_events": comm_events,
            "metrics": self.metrics.to_dict(),
        }


# Global dashboard state
_dashboard_state = DashboardState()
_broadcaster = None


def get_dashboard_state() -> DashboardState:
    """Get the global dashboard state."""
    return _dashboard_state


def clear_dashboard_state():
    """Clear the dashboard state (for testing)."""
    global _dashboard_state
    _dashboard_state = DashboardState()


async def broadcast_update():
    """Broadcast state update to dashboard clients."""
    if _broadcaster:
        try:
            await _broadcaster()
        except Exception as e:
            logger.warning(f"[Dashboard] Broadcast failed: {e}")


# ============================================================================
# ADK Tool Functions for Dashboard
# ============================================================================

def record_tourist_request(
    tourist_id: str,
    availability_start: str,
    availability_end: str,
    preferences: str,
    budget: float,
) -> str:
    """
    Record a tourist request in the dashboard.

    Args:
        tourist_id: Unique identifier for the tourist
        availability_start: Start of availability window (ISO format)
        availability_end: End of availability window (ISO format)
        preferences: Comma-separated list of preferences (e.g., "culture, history")
        budget: Maximum hourly budget in dollars

    Returns:
        Confirmation message
    """
    state = get_dashboard_state()

    request = {
        "tourist_id": tourist_id,
        "availability": {
            "start": availability_start,
            "end": availability_end,
        },
        "preferences": [p.strip() for p in preferences.split(",")],
        "budget": budget,
        "recorded_at": datetime.now().isoformat(),
    }

    state.tourist_requests[tourist_id] = request

    # Record communication event
    event = CommunicationEvent(
        timestamp=datetime.now().isoformat(),
        source_agent=tourist_id,
        target_agent="scheduler",
        message_type="TouristRequest",
        summary=f"Tourist {tourist_id} requested schedule (budget: ${budget}/hr)",
    )
    state.communication_events.append(event)
    state.metrics.total_messages += 1
    state.update_metrics()

    # Trigger broadcast
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_update())
    except RuntimeError:
        pass

    logger.info(f"[Dashboard] Recorded tourist request from {tourist_id}")
    return f"Recorded tourist request from {tourist_id}"


def record_guide_offer(
    guide_id: str,
    categories: str,
    available_start: str,
    available_end: str,
    hourly_rate: float,
    max_group_size: int = 1,
) -> str:
    """
    Record a guide offer in the dashboard.

    Args:
        guide_id: Unique identifier for the guide
        categories: Comma-separated list of expertise categories
        available_start: Start of availability window (ISO format)
        available_end: End of availability window (ISO format)
        hourly_rate: Hourly rate in dollars
        max_group_size: Maximum number of tourists the guide can handle

    Returns:
        Confirmation message
    """
    state = get_dashboard_state()

    offer = {
        "guide_id": guide_id,
        "categories": [c.strip() for c in categories.split(",")],
        "availability": {
            "start": available_start,
            "end": available_end,
        },
        "hourly_rate": hourly_rate,
        "max_group_size": max_group_size,
        "recorded_at": datetime.now().isoformat(),
    }

    state.guide_offers[guide_id] = offer

    # Record communication event
    event = CommunicationEvent(
        timestamp=datetime.now().isoformat(),
        source_agent=guide_id,
        target_agent="scheduler",
        message_type="GuideOffer",
        summary=f"Guide {guide_id} offering {categories} at ${hourly_rate}/hr",
    )
    state.communication_events.append(event)
    state.metrics.total_messages += 1
    state.update_metrics()

    # Trigger broadcast
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_update())
    except RuntimeError:
        pass

    logger.info(f"[Dashboard] Recorded guide offer from {guide_id}")
    return f"Recorded guide offer from {guide_id}"


def record_assignment(
    tourist_id: str,
    guide_id: str,
    start_time: str,
    end_time: str,
    total_cost: float,
) -> str:
    """
    Record an assignment in the dashboard.

    Args:
        tourist_id: ID of the assigned tourist
        guide_id: ID of the assigned guide
        start_time: Start time of the assignment (ISO format)
        end_time: End time of the assignment (ISO format)
        total_cost: Total cost of the assignment

    Returns:
        Confirmation message
    """
    state = get_dashboard_state()

    assignment = {
        "tourist_id": tourist_id,
        "guide_id": guide_id,
        "window": {
            "start": start_time,
            "end": end_time,
        },
        "total_cost": total_cost,
        "created_at": datetime.now().isoformat(),
    }

    state.assignments.append(assignment)

    # Record communication event
    event = CommunicationEvent(
        timestamp=datetime.now().isoformat(),
        source_agent="scheduler",
        target_agent=tourist_id,
        message_type="Assignment",
        summary=f"Assigned {tourist_id} to guide {guide_id} (${total_cost})",
    )
    state.communication_events.append(event)
    state.metrics.total_messages += 1
    state.update_metrics()

    # Trigger broadcast
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_update())
    except RuntimeError:
        pass

    logger.info(f"[Dashboard] Recorded assignment: {tourist_id} -> {guide_id}")
    return f"Recorded assignment: {tourist_id} assigned to {guide_id}"


def get_dashboard_summary() -> str:
    """
    Get a summary of the current dashboard state.

    Returns:
        Human-readable summary of the system state
    """
    state = get_dashboard_state()
    state.update_metrics()
    m = state.metrics

    summary = f"""Dashboard Summary (as of {m.last_updated}):

📊 Overview:
- Total Tourists: {m.total_tourists}
- Total Guides: {m.total_guides}
- Total Assignments: {m.total_assignments}
- Satisfied Tourists: {m.satisfied_tourists}

📈 Metrics:
- Guide Utilization: {m.guide_utilization:.1%}
- Average Assignment Cost: ${m.avg_assignment_cost:.2f}
- Total Messages: {m.total_messages}

🧑‍🤝‍🧑 Recent Activity:"""

    # Add recent events
    for event in state.communication_events[-5:]:
        summary += f"\n  • [{event.timestamp[:19]}] {event.summary}"

    if not state.communication_events:
        summary += "\n  • No recent activity"

    return summary


def get_recent_events(count: int = 10) -> str:
    """
    Get recent communication events.

    Args:
        count: Number of recent events to retrieve

    Returns:
        List of recent communication events
    """
    state = get_dashboard_state()
    events = state.communication_events[-count:]

    if not events:
        return "No communication events recorded yet."

    result = f"Last {len(events)} communication events:\n"
    for i, event in enumerate(reversed(events), 1):
        result += f"\n{i}. [{event.timestamp[:19]}] {event.message_type}\n"
        result += f"   From: {event.source_agent} → To: {event.target_agent}\n"
        result += f"   {event.summary}"

    return result


# ============================================================================
# ADK Agent Definition
# ============================================================================

# Lazy-loaded UI agent singleton
_ui_agent = None


def get_ui_agent():
    """
    Get or create the UI dashboard agent.

    Uses lazy initialization to avoid importing google.adk at module load time.

    Returns:
        The UI LlmAgent instance
    """
    global _ui_agent

    if _ui_agent is None:
        # Import ADK components at runtime
        from google.adk.agents.llm_agent import LlmAgent
        from google.adk.models.lite_llm import LiteLlm

        # Get model configuration from environment
        # Supports Azure OpenAI via LiteLLM
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
        model_name = os.getenv("UI_MODEL", f"azure/{deployment_name}")

        # Use LiteLlm for Azure OpenAI support
        model = LiteLlm(
            model=model_name,
            api_key=os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY"),
            api_base=os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_API_BASE"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION") or os.getenv("AZURE_API_VERSION", "2024-02-01"),
        )

        _ui_agent = LlmAgent(
            name="ui_dashboard_agent",
            model=model,
            description=(
                "A dashboard agent that monitors the tourist scheduling system and provides "
                "real-time visibility into tourists, guides, assignments, and system metrics."
            ),
            instruction="""You are the UI Dashboard Agent for the Tourist Scheduling System.

Your role is to:
1. Track and record tourist requests as they come in
2. Track and record guide offers
3. Track and record assignments made by the scheduler
4. Provide summaries and insights about the system state
5. Answer questions about current tourists, guides, and assignments

You have access to the following tools:

1. **record_tourist_request**: Record a tourist's request when notified
2. **record_guide_offer**: Record a guide's offer when notified
3. **record_assignment**: Record an assignment when the scheduler makes a match
4. **get_dashboard_summary**: Get a high-level summary of the system state
5. **get_recent_events**: Get recent communication events

When you receive updates about tourists, guides, or assignments, use the appropriate
recording tool to track them. When asked for status or summaries, use the dashboard
tools to provide accurate information.

Be helpful and provide clear, concise summaries of the scheduling system state.""",
            tools=[
                record_tourist_request,
                record_guide_offer,
                record_assignment,
                get_dashboard_summary,
                get_recent_events,
            ],
        )

    return _ui_agent


def create_ui_app(host: str = "0.0.0.0", port: int = 10011):
    """
    Create an A2A application for the UI dashboard agent.
    Uses the agent card from a2a_cards/ui_agent.json.

    Args:
        host: Host to bind the server to
        port: Port to bind the server to

    Returns:
        FastAPI application configured with A2A endpoints
    """
    from google.adk.a2a.utils.agent_to_a2a import to_a2a

    # Load agent card from a2a_cards directory
    from .a2a_cards import get_ui_card
    agent_card = get_ui_card(host=host, port=port)
    logger.info(f"[ADK UI] Using agent card: {agent_card.name} v{agent_card.version}")

    return to_a2a(
        get_ui_agent(),
        host=host,
        port=port,
        protocol="http",
        agent_card=agent_card,
    )


def create_ui_a2a_components(host: str = "0.0.0.0", port: int = 10011):
    """
    Create A2A components for the UI agent (for SLIM transport).

    Returns the AgentCard and DefaultRequestHandler that can be used
    with SLIM transport. Uses the agent card from a2a_cards/ui_agent.json.

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
    from .a2a_cards import get_ui_card
    agent_card = get_ui_card(host=host, port=port)
    logger.info(f"[ADK UI] Loaded agent card: {agent_card.name} v{agent_card.version}")

    agent = get_ui_agent()

    # Create runner for the agent
    runner = InMemoryRunner(agent=agent)

    # Create A2A executor wrapping the ADK runner
    agent_executor = A2aAgentExecutor(runner=runner)

    # Create request handler
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=InMemoryTaskStore(),
    )

    return agent_card, request_handler


# ============================================================================
# CLI Entry Point
# ============================================================================

if __name__ == "__main__":
    import click
    import uvicorn

    @click.command()
    @click.option("--host", default="0.0.0.0", help="Host to bind to")
    @click.option("--port", default=10011, help="Port to bind to")
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
                from .dashboard import (
                    create_dashboard_app,
                    set_dashboard_state,
                    set_transport_mode,
                    broadcast_to_clients,
                )
                # Use global dashboard state
                set_dashboard_state(_dashboard_state)
                set_transport_mode(transport)
                dashboard_app = create_dashboard_app()

                # Setup broadcaster
                async def broadcaster():
                    state = get_dashboard_state()
                    await broadcast_to_clients({
                        "type": "initial_state",
                        "data": state.to_dict()
                    })

                global _broadcaster
                _broadcaster = broadcaster

                logger.info(f"[ADK UI] Web dashboard enabled at http://{host}:{port}")
            except ImportError as e:
                logger.warning(f"[ADK UI] Dashboard module not available: {e}")
                dashboard = False

        if transport == "slim":
            if not SLIM_AVAILABLE:
                logger.error("[ADK UI] SLIM transport requested but slimrpc/slima2a not installed")
                raise SystemExit(1)

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
                    import uvicorn
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
                    # Wait for all tasks - if any fails, we'll catch it
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

    main()
