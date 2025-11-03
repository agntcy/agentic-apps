#!/usr/bin/env python3
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
import httpx
from a2a.client import ClientFactory
from a2a.client.client_factory import minimal_agent_card
from a2a.client.helpers import create_text_message_object
from a2a.types import TransportProtocol

from a2a_summit_demo.core.messages import TouristRequest, Window

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@click.command()
@click.option("--scheduler-url", default="http://localhost:10000", help="Scheduler A2A server URL")
@click.option("--tourist-id", default="t1", help="Tourist ID")
async def main(scheduler_url: str, tourist_id: str):
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

    async with httpx.AsyncClient() as httpx_client:
        # Create A2A client using ClientFactory
        client = await ClientFactory.connect(
            agent=minimal_agent_card(scheduler_url),
            client_config=None,
        )

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
                                if hasattr(part.root, "text"):
                                    try:
                                        data = json.loads(part.root.text)
                                        if data.get("type") == "ScheduleProposal":
                                            logger.info(
                                                f"[Tourist {tourist_id}] ✅ Received schedule: {data}"
                                            )
                                    except json.JSONDecodeError:
                                        pass

    logger.info(f"[Tourist {tourist_id}] Done")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main(standalone_mode=False))
