#!/usr/bin/env python3
"""
Guide Agent - A2A Client

Sends GuideOffer messages to the Scheduler Agent server
to register availability and capabilities.

This demonstrates a client using the official a2a-sdk to communicate
with an A2A server.
"""

import json
import logging
from datetime import datetime

import click
import httpx
from a2a.client import ClientFactory
from a2a.client.client_factory import minimal_agent_card
from a2a.client.helpers import create_text_message_object

from a2a_summit_demo.core.messages import GuideOffer, Window

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@click.command()
@click.option("--scheduler-url", default="http://localhost:10000", help="Scheduler A2A server URL")
@click.option("--guide-id", default="g1", help="Guide ID")
async def main(scheduler_url: str, guide_id: str):
    """Send guide offer to scheduler agent"""
    logger.info(f"[Guide {guide_id}] Connecting to scheduler at {scheduler_url}")

    # Create sample guide offer
    offer = GuideOffer(
        guide_id=guide_id,
        categories=["culture", "history", "food"],
        available_window=Window(
            start=datetime(2025, 6, 1, 10, 0),
            end=datetime(2025, 6, 1, 14, 0),
        ),
        hourly_rate=50.0,
        max_group_size=5,
    )

    logger.info(f"[Guide {guide_id}] Sending offer: {offer}")

    # Create A2A client using ClientFactory
    factory = ClientFactory()
    client = factory.create(
        card=minimal_agent_card(scheduler_url)
    )

        # Send message to scheduler
        message = create_text_message_object(
            content=offer.to_json()
        )

        logger.info(f"[Guide {guide_id}] Sending A2A message...")

        # Iterate through responses
        async for response in client.send_message(message):
            logger.info(f"[Guide {guide_id}] Received response: {response}")

            # Extract acknowledgment from response
            if isinstance(response, tuple):
                task, update = response
                if task.history:
                    for msg in task.history:
                        if msg.role.value == "agent" and msg.parts:
                            for part in msg.parts:
                                if hasattr(part.root, "text"):
                                    try:
                                        data = json.loads(part.root.text)
                                        if data.get("type") == "Acknowledgment":
                                            logger.info(
                                                f"[Guide {guide_id}] ✅ {data['message']}"
                                            )
                                    except json.JSONDecodeError:
                                        pass

    logger.info(f"[Guide {guide_id}] Done")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main(standalone_mode=False))
