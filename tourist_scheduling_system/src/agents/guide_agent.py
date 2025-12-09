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
"""

import asyncio
import logging
import os
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


def create_guide_agent(
    guide_id: str,
    scheduler_url: str = "http://localhost:10000",
):
    """
    Create an ADK-based guide agent.

    The guide agent uses RemoteA2aAgent as a sub-agent to communicate
    with the scheduler.

    Args:
        guide_id: Unique identifier for this guide
        scheduler_url: URL of the scheduler's A2A endpoint

    Returns:
        Configured LlmAgent for the guide
    """
    # Import ADK components at runtime
    from google.adk.agents.llm_agent import LlmAgent
    from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
    from google.adk.models.lite_llm import LiteLlm

    # Create remote scheduler agent reference
    # The agent_card parameter is a URL to the scheduler's agent card
    # Use new endpoint path (/.well-known/agent-card.json) instead of deprecated /.well-known/agent.json
    agent_card_url = f"{scheduler_url.rstrip('/')}/.well-known/agent-card.json"
    scheduler_remote = RemoteA2aAgent(
        name="scheduler",
        description="The tourist scheduling coordinator that handles guide offers",
        agent_card=agent_card_url,
    )

    # Get model configuration from environment
    # Supports Azure OpenAI via LiteLLM
    # Environment variables: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
    # AZURE_OPENAI_API_VERSION, AZURE_OPENAI_DEPLOYMENT_NAME
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
    model_name = os.getenv("GUIDE_MODEL", f"azure/{deployment_name}")
    model = LiteLlm(
        model=model_name,
        api_key=os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY"),
        api_base=os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_API_BASE"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION") or os.getenv("AZURE_API_VERSION", "2024-02-01"),
    )

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

    print(f"[Guide {guide_id}] Starting with ADK...")
    print(f"[Guide {guide_id}] Connecting to scheduler at {scheduler_url}")

    # Create the guide agent
    agent = create_guide_agent(guide_id, scheduler_url)
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
    events = await runner.run_debug(
        user_messages=message,
        verbose=True,
    )

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


if __name__ == "__main__":
    main()
