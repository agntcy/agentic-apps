#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
ADK-based Guide Agent

A guide agent that communicates with the scheduler to offer tour services.

This agent can:
1. Create and send guide offers to the scheduler
2. Receive assignment confirmations
3. Manage its availability and specialties

Uses ADK's RemoteA2aAgent to communicate with the scheduler's A2A endpoint.
Supports both HTTP and SLIM transport based on TRANSPORT_MODE env var.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Optional, TYPE_CHECKING

import click

# Lazy import of ADK components to allow module to load without ADK installed
if TYPE_CHECKING:
    from google.adk import Agent
    from google.adk.agents.llm_agent import LlmAgent
    from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
    from google.adk.runners import InMemoryRunner
    from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)


def get_transport_mode() -> str:
    """Get the configured transport mode (http or slim)."""
    return os.environ.get("TRANSPORT_MODE", "http").lower()


def create_guide_offer_message(
    guide_id: str,
    categories: list[str],
    available_start: str,
    available_end: str,
    hourly_rate: float,
    max_group_size: int = 1,
) -> str:
    """Create a formatted message for the scheduler agent."""
    return f"""Please register guide offer:
- Guide ID: {guide_id}
- Categories: {', '.join(categories)}
- Available from: {available_start}
- Available until: {available_end}
- Hourly rate: ${hourly_rate}
- Max group size: {max_group_size}"""


async def create_guide_agent(
    guide_id: str,
    scheduler_url: str = "http://localhost:10000",
    a2a_client_factory=None,
):
    """
    Create an ADK-based guide agent.

    The guide agent uses RemoteA2aAgent as a sub-agent to communicate
    with the scheduler. Supports both HTTP and SLIM transport.

    Args:
        guide_id: Unique identifier for this guide
        scheduler_url: URL of the scheduler's A2A endpoint (for HTTP)
        a2a_client_factory: Optional A2A client factory (for SLIM transport)

    Returns:
        Configured LlmAgent for the guide
    """
    # Import ADK components at runtime
    from google.adk.agents.llm_agent import LlmAgent
    from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
    from google.adk.models.lite_llm import LiteLlm

    transport_mode = get_transport_mode()
    logger.info(f"[Guide {guide_id}] Creating agent with transport mode: {transport_mode}")

    # Create remote scheduler agent reference based on transport mode
    if transport_mode == "slim" and a2a_client_factory is not None:
        # For SLIM transport, use minimal agent card with slimrpc transport
        from core.slim_transport import minimal_slim_agent_card

        # The scheduler's SLIM topic (must match scheduler's local_id)
        scheduler_topic = os.environ.get(
            "SCHEDULER_SLIM_TOPIC",
            "agntcy/tourist_scheduling/scheduler/0"
        )
        agent_card = minimal_slim_agent_card(scheduler_topic)

        scheduler_remote = RemoteA2aAgent(
            name="scheduler",
            description="The tourist scheduling coordinator that handles guide offers",
            agent_card=agent_card,
            a2a_client_factory=a2a_client_factory,
        )
        logger.info(f"[Guide {guide_id}] Using SLIM transport to scheduler topic: {scheduler_topic}")
    else:
        # HTTP transport - use URL-based agent card
        agent_card_url = f"{scheduler_url.rstrip('/')}/.well-known/agent-card.json"
        scheduler_remote = RemoteA2aAgent(
            name="scheduler",
            description="The tourist scheduling coordinator that handles guide offers",
            agent_card=agent_card_url,
        )
        logger.info(f"[Guide {guide_id}] Using HTTP transport to scheduler: {agent_card_url}")

    # Get model configuration from environment
    from core.model_factory import create_llm_model
    model = create_llm_model("guide")

    guide_agent = LlmAgent(
        name=f"guide_{guide_id}",
        model=model,
        description=f"Tour guide {guide_id} offering services to tourists",
        instruction=f"""You are Tour Guide {guide_id}.

Your role is to:
1. Offer your tour guide services to the scheduling system
2. Specify your categories of expertise (e.g., culture, history, food, art)
3. Set your availability windows
4. Communicate your rates and group capacity

You have access to the scheduler agent which coordinates between tourists and guides.
When you want to offer your services, communicate with the scheduler sub-agent.

Be helpful and professional in describing your tour offerings.""",
        sub_agents=[scheduler_remote],
    )

    return guide_agent


async def run_guide_agent(
    guide_id: str,
    scheduler_url: str,
    categories: list[str],
    available_start: str,
    available_end: str,
    hourly_rate: float,
    max_group_size: int = 1,
):
    """
    Run the guide agent to send an offer to the scheduler.

    Args:
        guide_id: Unique identifier for the guide
        scheduler_url: Scheduler's A2A endpoint
        categories: Guide's specialties
        available_start: Start of availability (ISO format)
        available_end: End of availability (ISO format)
        hourly_rate: Hourly rate in dollars
        max_group_size: Maximum tourists per tour
    """
    # Import ADK runner at runtime
    from google.adk.runners import InMemoryRunner

    transport_mode = get_transport_mode()
    print(f"[Guide {guide_id}] Starting with ADK (transport: {transport_mode})...")

    # Set up SLIM client factory if using SLIM transport
    a2a_client_factory = None
    if transport_mode == "slim":
        try:
            from core.slim_transport import (
                create_slim_client_factory,
                config_from_env,
                SLIMConfig,
            )

            # Create SLIM config for this guide agent
            # Override local_id to be unique for this guide
            base_config = config_from_env()
            guide_local_id = f"agntcy/tourist_scheduling/guide_{guide_id}"

            config = SLIMConfig(
                endpoint=base_config.endpoint,
                local_id=guide_local_id,
                shared_secret=base_config.shared_secret,
                tls_insecure=base_config.tls_insecure,
            )

            print(f"[Guide {guide_id}] Connecting to SLIM at {config.endpoint}")
            print(f"[Guide {guide_id}] Using SLIM ID: {config.local_id}")

            a2a_client_factory = await create_slim_client_factory(config)
            print(f"[Guide {guide_id}] SLIM client factory created successfully")
        except ImportError as e:
            print(f"[Guide {guide_id}] SLIM not available, falling back to HTTP: {e}")
            transport_mode = "http"
        except Exception as e:
            print(f"[Guide {guide_id}] Failed to create SLIM client: {e}")
            raise
    else:
        print(f"[Guide {guide_id}] Connecting to scheduler at {scheduler_url}")

    # Create the guide agent
    agent = await create_guide_agent(guide_id, scheduler_url, a2a_client_factory)
    runner = InMemoryRunner(agent=agent)

    # Create offer message
    message = create_guide_offer_message(
        guide_id=guide_id,
        categories=categories,
        available_start=available_start,
        available_end=available_end,
        hourly_rate=hourly_rate,
        max_group_size=max_group_size,
    )

    print(f"[Guide {guide_id}] Sending offer...")

    # Run the agent with the offer
    events = []
    max_retries = 30
    retry_delay = 10

    for attempt in range(max_retries):
        try:
            events = await runner.run_debug(
                user_messages=message,
                verbose=True,
            )
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[Guide {guide_id}] Attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
            else:
                print(f"[Guide {guide_id}] All attempts failed.")
                raise

    # Process response
    for event in events:
        if hasattr(event, 'content') and event.content:
            for part in event.content.parts:
                if hasattr(part, 'text'):
                    print(f"[Guide {guide_id}] Response: {part.text}")

    print(f"[Guide {guide_id}] Done")


@click.command()
@click.option("--scheduler-url", default="http://localhost:10000",
              help="Scheduler A2A server URL")
@click.option("--guide-id", default="g1", help="Guide ID")
@click.option("--categories", default="culture,history,food",
              help="Comma-separated list of categories")
@click.option("--available-start", default="2025-06-01T10:00:00",
              help="Start of availability (ISO format)")
@click.option("--available-end", default="2025-06-01T14:00:00",
              help="End of availability (ISO format)")
@click.option("--hourly-rate", default=50.0, help="Hourly rate in dollars")
@click.option("--max-group-size", default=5, help="Maximum group size")
def main(
    scheduler_url: str,
    guide_id: str,
    categories: str,
    available_start: str,
    available_end: str,
    hourly_rate: float,
    max_group_size: int,
):
    """Run the ADK-based guide agent."""
    logging.basicConfig(level=logging.INFO)

    categories_list = [c.strip() for c in categories.split(",")]

    asyncio.run(run_guide_agent(
        guide_id=guide_id,
        scheduler_url=scheduler_url,
        categories=categories_list,
        available_start=available_start,
        available_end=available_end,
        hourly_rate=hourly_rate,
        max_group_size=max_group_size,
    ))
    sys.exit(0)


if __name__ == "__main__":
    main()
