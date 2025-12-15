# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Google ADK-based agent implementations for the Tourist Scheduling System.

This package contains agent implementations using the Google Agent Development Kit (ADK).
These agents can be exposed via A2A protocol using ADK's built-in utilities.

Agents:
    - scheduler_agent: Central coordinator for matching tourists with guides
    - guide_agent: Represents tour guides offering services
    - tourist_agent: Represents tourists requesting tours
    - ui_agent: Dashboard for monitoring the system

Entry points:
    scheduler  - Run the scheduler agent (console or A2A server)
    guide      - Run the guide agent
    tourist    - Run the tourist agent
    ui         - Run the UI dashboard agent

Example usage:
    # Console demo
    python -m agents.scheduler_agent --mode console

    # A2A server mode
    python -m agents.scheduler_agent --mode a2a --port 10000
"""

# Lazy imports to avoid requiring ADK when not using this module
def __getattr__(name):
    """Lazy loading of ADK components."""
    if name == "scheduler_agent":
        from .scheduler_agent import scheduler_agent
        return scheduler_agent
    elif name == "get_scheduler_agent":
        from .scheduler_agent import get_scheduler_agent
        return get_scheduler_agent
    elif name == "create_scheduler_app":
        from .scheduler_agent import create_scheduler_app
        return create_scheduler_app
    elif name == "get_ui_agent":
        from .ui_agent import get_ui_agent
        return get_ui_agent
    elif name == "create_ui_app":
        from .ui_agent import create_ui_app
        return create_ui_app
    elif name in ("register_tourist_request", "register_guide_offer",
                  "run_scheduling", "get_schedule_status"):
        from . import tools
        return getattr(tools, name)
    elif name in ("create_guide_agent", "create_guide_offer_message"):
        from .guide_agent import create_guide_agent, create_guide_offer_message
        if name == "create_guide_agent":
            return create_guide_agent
        return create_guide_offer_message
    elif name in ("create_tourist_agent", "create_tourist_request_message"):
        from .tourist_agent import create_tourist_agent, create_tourist_request_message
        if name == "create_tourist_agent":
            return create_tourist_agent
        return create_tourist_request_message
    elif name == "a2a_cards":
        from src.core import a2a_cards
        return a2a_cards
    elif name in ("load_agent_card", "get_scheduler_card", "get_guide_card",
                  "get_tourist_card", "get_ui_card", "list_available_cards"):
        from src.core import a2a_cards
        return getattr(a2a_cards, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Scheduler
    "scheduler_agent",
    "get_scheduler_agent",
    "create_scheduler_app",
    # UI Dashboard
    "get_ui_agent",
    "create_ui_app",
    # Guide
    "create_guide_agent",
    "create_guide_offer_message",
    # Tourist
    "create_tourist_agent",
    "create_tourist_request_message",
    # Tools
    "register_tourist_request",
    "register_guide_offer",
    "run_scheduling",
    "get_schedule_status",
    # A2A Cards
    "a2a_cards",
    "load_agent_card",
    "get_scheduler_card",
    "get_guide_card",
    "get_tourist_card",
    "get_ui_card",
    "list_available_cards",
]

