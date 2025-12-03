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
from a2a.types import TransportProtocol, Task, Message, Part, TextPart, DataPart

# SLIM transport support
try:
    from core.slim_transport import SLIMConfig, create_slim_client_factory, minimal_slim_agent_card
    SLIM_AVAILABLE = True
except ImportError:
    SLIM_AVAILABLE = False

from core.messages import TouristRequest, Window

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def run_tourist_agent(
    scheduler_url: str,
    tourist_id: str,
    transport: str = "http",
    slim_endpoint: str | None = None,
    slim_local_id: str | None = None,
):
    """Send tourist request to scheduler agent"""
    logger.info(f"[Tourist {tourist_id}] Connecting to scheduler at {scheduler_url}")
    if transport == "slim":
        logger.info(f"[Tourist {tourist_id}] Using SLIM transport via {slim_endpoint}")

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

    # Create client based on transport
    if transport == "slim" and SLIM_AVAILABLE:
        if not slim_endpoint or not slim_local_id:
            raise ValueError("SLIM transport requires --slim-endpoint and --slim-local-id")
        slim_config = SLIMConfig(
            endpoint=slim_endpoint,
            local_id=slim_local_id,
        )
        factory = create_slim_client_factory(slim_config)
        card = minimal_slim_agent_card(scheduler_url, slim_endpoint)
        client = factory.create(card)
    else:
        card = minimal_agent_card(scheduler_url)
        factory = ClientFactory(ClientConfig())
        client = factory.create(card)

    # Send message to scheduler
    message = create_text_message_object(
        content=request.to_json()
    )

    logger.info(f"[Tourist {tourist_id}] Sending A2A message...")

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

    # Streaming iterator (actual SDK behavior). Collect Task/Message events and parse parts.
    schedule_found = False
    async for event in client.send_message(message):
        logger.debug(f"[Tourist {tourist_id}] Event type: {type(event)}")
        task_obj = None
        msg_obj = None
        # Handle tuple form (task, update)
        if isinstance(event, tuple) and len(event) == 2:
            task_obj, _update = event
        elif isinstance(event, Task):
            task_obj = event
        elif isinstance(event, Message):
            msg_obj = event
        else:
            # Unknown event type; continue
            continue

        def inspect_message(message_candidate):
            nonlocal schedule_found
            if not message_candidate or not getattr(message_candidate, 'parts', None):
                return
            for part in message_candidate.parts:
                root = getattr(part, 'root', None)
                payload = None
                if isinstance(root, DataPart):
                    payload = root.data
                elif isinstance(root, TextPart):
                    try:
                        payload = json.loads(root.text)
                    except json.JSONDecodeError:
                        continue
                if isinstance(payload, dict) and payload.get('type') == 'ScheduleProposal':
                    logger.info(f"[Tourist {tourist_id}] ✅ Received schedule proposal: {payload}")
                    schedule_found = True
                    return

        if task_obj:
            # First inspect artifacts directly (preferred structured channel)
            artifacts = getattr(task_obj, 'artifacts', []) or []
            for artifact in artifacts:
                if schedule_found:
                    break
                for part in getattr(artifact, 'parts', []) or []:
                    if schedule_found:
                        break
                    root = getattr(part, 'root', None)
                    payload = None
                    if isinstance(root, DataPart):
                        payload = root.data
                    elif isinstance(root, TextPart):
                        try:
                            payload = json.loads(root.text)
                        except json.JSONDecodeError:
                            continue
                    if isinstance(payload, dict) and payload.get('type') == 'ScheduleProposal':
                        assignments = payload.get('assignments', []) or []
                        summary = ", ".join(
                            f"{a.get('tourist_id')}→{a.get('guide_id')}(${int(a.get('total_cost',0))})" for a in assignments
                        ) or 'no assignments'
                        logger.info(
                            f"[Tourist {tourist_id}] ✅ Schedule proposal artifact received ({len(assignments)} assignments): {summary}"
                        )
                        schedule_found = True
                        break
            # Fallback: inspect agent messages in history
            if not schedule_found:
                for history_msg in getattr(task_obj, 'history', []) or []:
                    if schedule_found:
                        break
                    if getattr(history_msg.role, 'value', None) == 'agent':
                        inspect_message(history_msg)
        if msg_obj and not schedule_found:
            inspect_message(msg_obj)

        if schedule_found:
            break

    if not schedule_found:
        logger.info(f"[Tourist {tourist_id}] No schedule proposal found in responses")

    logger.info(f"[Tourist {tourist_id}] Done")


@click.command()
@click.option("--scheduler-url", default="http://localhost:10000", help="Scheduler A2A server URL")
@click.option("--tourist-id", default="t1", help="Tourist ID")
@click.option("--transport", default="http", type=click.Choice(["http", "slim"]), help="Transport protocol")
@click.option("--slim-endpoint", default=None, help="SLIM node endpoint (required for SLIM transport)")
@click.option("--slim-local-id", default=None, help="SLIM local agent ID (required for SLIM transport)")
def main(scheduler_url: str, tourist_id: str, transport: str, slim_endpoint: str, slim_local_id: str):
    """Send tourist request to scheduler agent"""
    import asyncio
    asyncio.run(run_tourist_agent(scheduler_url, tourist_id, transport, slim_endpoint, slim_local_id))


if __name__ == "__main__":
    main()
