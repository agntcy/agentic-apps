#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
ADK-based Tourist Agent

A tourist agent that communicates with the scheduler to request tour services.

This agent can:
1. Create and send tour requests to the scheduler
2. Receive schedule proposals with matched guides
3. Manage preferences and availability

Uses ADK's RemoteA2aAgent to communicate with the scheduler's A2A endpoint.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

import click

# ADK imports are done lazily inside functions that need them
# to allow importing helper functions without having google.adk installed

logger = logging.getLogger(__name__)


def create_tourist_request_message(
    tourist_id: str,
    availability_start: str,
    availability_end: str,
    preferences: list[str],
    budget: float,
) -> str:
    """Create a formatted message for the scheduler agent."""
    return f"""Please register tourist request:
- Tourist ID: {tourist_id}
- Available from: {availability_start}
- Available until: {availability_end}
- Preferences: {', '.join(preferences)}
- Budget: ${budget}/hour"""


def create_tourist_agent(
    tourist_id: str,
    scheduler_url: str = "http://localhost:10000",
):
    """
    Create an ADK-based tourist agent.

    The tourist agent uses RemoteA2aAgent as a sub-agent to communicate
    with the scheduler.

    Args:
        tourist_id: Unique identifier for this tourist
        scheduler_url: URL of the scheduler's A2A endpoint

    Returns:
        Configured LlmAgent for the tourist
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
        description="The tourist scheduling coordinator that handles tour requests",
        agent_card=agent_card_url,
    )

    # Get model configuration from environment
    # Supports Azure OpenAI via LiteLLM
    # Environment variables: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
    # AZURE_OPENAI_API_VERSION, AZURE_OPENAI_DEPLOYMENT_NAME
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
    model_name = os.getenv("TOURIST_MODEL", f"azure/{deployment_name}")
    model = LiteLlm(
        model=model_name,
        api_key=os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY"),
        api_base=os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_API_BASE"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION") or os.getenv("AZURE_API_VERSION", "2024-02-01"),
    )

    tourist_agent = LlmAgent(
        name=f"tourist_{tourist_id}",
        model=model,
        description=f"Tourist {tourist_id} looking for guided tour services",
        instruction=f"""You are Tourist {tourist_id}.

Your role is to:
1. Request tour guide services from the scheduling system
2. Specify your preferences (e.g., culture, history, food, art)
3. Set your availability windows
4. Communicate your budget constraints

You have access to the scheduler agent which coordinates between tourists and guides.
When you want to request a tour, communicate with the scheduler sub-agent.

After sending your request, you should receive a schedule proposal with matched guides.
Be polite and clear in describing what kind of tour experience you're looking for.""",
        sub_agents=[scheduler_remote],
    )

    return tourist_agent


async def run_tourist_agent(
    tourist_id: str,
    scheduler_url: str,
    preferences: list[str],
    availability_start: str,
    availability_end: str,
    budget: float,
):
    """
    Run the tourist agent to send a request to the scheduler.

    Args:
        tourist_id: Unique identifier for the tourist
        scheduler_url: Scheduler's A2A endpoint
        preferences: Preferred tour categories
        availability_start: Start of availability (ISO format)
        availability_end: End of availability (ISO format)
        budget: Maximum hourly budget in dollars
    """
    # Import ADK runner at runtime
    from google.adk.runners import InMemoryRunner

    print(f"[Tourist {tourist_id}] Starting with ADK...")
    print(f"[Tourist {tourist_id}] Connecting to scheduler at {scheduler_url}")

    # Create the tourist agent
    agent = create_tourist_agent(tourist_id, scheduler_url)
    runner = InMemoryRunner(agent=agent)

    # Create request message
    message = create_tourist_request_message(
        tourist_id=tourist_id,
        availability_start=availability_start,
        availability_end=availability_end,
        preferences=preferences,
        budget=budget,
    )

    print(f"[Tourist {tourist_id}] Sending request...")

    # Run the agent with the request
    events = await runner.run_debug(
        user_messages=message,
        verbose=True,
    )

    # Process response
    for event in events:
        if hasattr(event, 'content') and event.content:
            for part in event.content.parts:
                if hasattr(part, 'text'):
                    print(f"[Tourist {tourist_id}] Response: {part.text}")

    # Ask for scheduling
    print(f"[Tourist {tourist_id}] Requesting schedule...")

    schedule_events = await runner.run_debug(
        user_messages="Please run the scheduling algorithm and show me my assigned guide",
        session_id="tourist_session",  # Same session to continue conversation
    )

    for event in schedule_events:
        if hasattr(event, 'content') and event.content:
            for part in event.content.parts:
                if hasattr(part, 'text'):
                    print(f"[Tourist {tourist_id}] Schedule: {part.text}")

    print(f"[Tourist {tourist_id}] Done")


@click.command()
@click.option("--scheduler-url", default="http://localhost:10000",
              help="Scheduler A2A server URL")
@click.option("--tourist-id", default="t1", help="Tourist ID")
@click.option("--preferences", default="culture,history",
              help="Comma-separated list of preferences")
@click.option("--availability-start", default="2025-06-01T09:00:00",
              help="Start of availability (ISO format)")
@click.option("--availability-end", default="2025-06-01T17:00:00",
              help="End of availability (ISO format)")
@click.option("--budget", default=100.0, help="Maximum hourly budget in dollars")
def main(
    scheduler_url: str,
    tourist_id: str,
    preferences: str,
    availability_start: str,
    availability_end: str,
    budget: float,
):
    """Run the ADK-based tourist agent."""
    logging.basicConfig(level=logging.INFO)

    preferences_list = [p.strip() for p in preferences.split(",")]

    asyncio.run(run_tourist_agent(
        tourist_id=tourist_id,
        scheduler_url=scheduler_url,
        preferences=preferences_list,
        availability_start=availability_start,
        availability_end=availability_end,
        budget=budget,
    ))


if __name__ == "__main__":
    main()
