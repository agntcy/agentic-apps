#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Tourist Agent - A2A Client

Sends TouristRequest messages to the Scheduler Agent server
and receives ScheduleProposal responses.

This demonstrates a client using the official a2a-sdk to communicate
with an A2A server.
"""

import json
import logging
from datetime import datetime, timedelta

import click
from a2a.client import ClientFactory, ClientConfig
from a2a.client.client_factory import minimal_agent_card
from a2a.client.helpers import create_text_message_object
from a2a.types import TransportProtocol

from core.messages import TouristRequest, Window

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def run_tourist_agent(scheduler_url: str, tourist_id: str):
    """Send tourist request to scheduler agent"""
    logger.info(f"[Tourist {tourist_id}] Connecting to scheduler at {scheduler_url}")

    # Create sample tourist request
    request = TouristRequest(
        tourist_id=tourist_id,
        availability=[Window(
            start=datetime(2025, 6, 1, 9, 0),
            end=datetime(2025, 6, 1, 17, 0),
        )],
        preferences=["culture", "history"],
        budget=100,
    )

    logger.info(f"[Tourist {tourist_id}] Sending request: {request}")

    card = minimal_agent_card(scheduler_url)
    factory = ClientFactory(ClientConfig())
    client = factory.create(card)

    # Send message to scheduler
    message = create_text_message_object(
        content=request.to_json()
    )

    logger.info(f"[Tourist {tourist_id}] Sending A2A message...")

    # Iterate through responses
    async for response in client.send_message(message):
        logger.info(f"[Tourist {tourist_id}] Received response: {response}")

        # Extract schedule proposal from response
        if isinstance(response, tuple):
            task, update = response
            if task.history:
                for msg in task.history:
                    if msg.role.value == "agent" and msg.parts:
                        for part in msg.parts:
                            raw_text = getattr(getattr(part, 'root', None), 'text', None)
                            if raw_text:
                                try:
                                    data = json.loads(raw_text)
                                    if data.get("type") == "ScheduleProposal":
                                        logger.info(
                                            f"[Tourist {tourist_id}] ✅ Received schedule: {data}"
                                        )
                                except json.JSONDecodeError:
                                    pass

    logger.info(f"[Tourist {tourist_id}] Done")


@click.command()
@click.option("--scheduler-url", default="http://localhost:10000", help="Scheduler A2A server URL")
@click.option("--tourist-id", default="t1", help="Tourist ID")
def main(scheduler_url: str, tourist_id: str):
    """Send tourist request to scheduler agent"""
    import asyncio
    asyncio.run(run_tourist_agent(scheduler_url, tourist_id))


if __name__ == "__main__":
    main()
