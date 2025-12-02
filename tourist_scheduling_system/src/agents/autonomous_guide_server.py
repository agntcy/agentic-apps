#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Autonomous Guide Server - exposes A2A endpoint to generate dynamic GuideOffer artifacts.

This complements the autonomous guide client logic by allowing other agents to request
on-demand guide offers without needing to simulate autonomous operation loops.

Supports both HTTP and SLIM transports via --transport option.

Request pattern (JSON-RPC message/send):
  params.message.parts[0].text or data JSON:
    {
      "action": "generate_offer",
      "guide_id": "guide-ai-1"            # optional override
    }

Response Artifact (DataPart):
    {
      "type": "GuideOffer",
      "guide_id": "guide-ai-1",
      "categories": [...],
      "available_window": {"start": "ISO", "end": "ISO"},
      "hourly_rate": 85.0,
      "max_group_size": 6
    }
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Optional

import uvicorn
import click

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.utils.task import new_task
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Part,
    TaskState,
    TextPart,
    DataPart,
)

from core.messages import GuideOffer, Window
from core.slim_transport import (
    SLIMConfig,
    check_slim_available,
    create_slim_server,
    config_from_env,
)
from autonomous_guide_agent import AutonomousGuideAgent  # reuse LLM + heuristic logic

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class GuideOfferExecutor(AgentExecutor):
    """Generates GuideOffer artifacts in response to A2A messages."""

    def __init__(self, guide_id: str):
        self.guide_id = guide_id
        # Reuse autonomous guide logic for pricing + availability decisions
        # scheduler_url not needed here; pass dummy
        self.agent = AutonomousGuideAgent(guide_id=guide_id, scheduler_url="http://localhost")

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:  # noqa: D401
        logger.info(f"[GuideOfferServer] Received task: {context.task_id}")
        task = context.current_task
        if not task:
            if not context.message:
                logger.error("[GuideOfferServer] Missing message")
                return
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)

        # Extract JSON payload
        payload = None
        raw_text = None
        if context.message and context.message.parts:
            for part in context.message.parts:
                root = getattr(part, "root", None)
                if isinstance(root, DataPart):
                    payload = root.data
                    break
                if isinstance(root, TextPart):
                    raw_text = root.text
        if payload is None and raw_text:
            try:
                payload = json.loads(raw_text)
            except json.JSONDecodeError:
                payload = None

        if payload is None:
            await updater.update_status(
                TaskState.failed,
                message=updater.new_agent_message([Part(root=TextPart(text="No JSON payload provided"))])
            )
            return

        action = payload.get("action")
        if action != "generate_offer":
            await updater.update_status(
                TaskState.failed,
                message=updater.new_agent_message([Part(root=TextPart(text=f"Unsupported action: {action}"))])
            )
            return

        await updater.update_status(
            TaskState.working,
            message=updater.new_agent_message([Part(root=TextPart(text="Generating guide offer..."))])
        )

        try:
            offer = await self.agent.create_guide_offer()
            offer_dict = offer.to_dict()
            offer_dict["type"] = "GuideOffer"
            await updater.add_artifact([Part(root=DataPart(data=offer_dict))], name="guide_offer")
            await updater.complete()
        except Exception as e:
            logger.error(f"[GuideOfferServer] Error generating offer: {e}")
            await updater.update_status(
                TaskState.failed,
                message=updater.new_agent_message([Part(root=TextPart(text=str(e)))])
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:  # noqa: D401
        logger.info(f"[GuideOfferServer] Cancel task: {context.task_id}")
        task = context.current_task
        if not task:
            return
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.cancel()


@click.command()
@click.option("--host", default="localhost", help="Server host")
@click.option("--port", default=10020, type=int, help="Server port")
@click.option("--guide-id", default="guide-ai-1", help="Guide ID")
@click.option("--transport", default="http", type=click.Choice(["http", "slim"]), help="Transport protocol")
@click.option("--slim-endpoint", default=None, help="SLIM gateway endpoint")
@click.option("--slim-local-id", default=None, help="SLIM local agent ID")
def main(host: str, port: int, guide_id: str, transport: str, slim_endpoint: str, slim_local_id: str):
    skill = AgentSkill(
        id="dynamic_offer_generation",
        name="Dynamic Guide Offer Generation",
        description="Generates a dynamic GuideOffer with availability and pricing decisions.",
        tags=["guide", "offer", "pricing", "availability"],
        examples=[
            '{"action": "generate_offer"}',
            "Returns GuideOffer artifact with dynamic window & rate"
        ],
    )

    agent_card = AgentCard(
        name="Autonomous Guide Agent",
        description="Autonomous guide server generating dynamic tour offers on demand.",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["application/json", "text"],  # fallback text
        default_output_modes=["application/json", "text"],
        skills=[skill],
    )

    executor = GuideOfferExecutor(guide_id=guide_id)
    request_handler = DefaultRequestHandler(agent_executor=executor, task_store=InMemoryTaskStore())

    if transport == "slim":
        if not check_slim_available():
            logger.error("[GuideOfferServer] SLIM transport requested but slimrpc/slima2a not installed")
            raise SystemExit(1)

        slim_config = config_from_env(prefix="GUIDE_")
        if slim_endpoint:
            slim_config.endpoint = slim_endpoint
        if slim_local_id:
            slim_config.local_id = slim_local_id
        else:
            slim_config.local_id = f"agntcy/tourist_scheduling/{guide_id}"

        logger.info(f"[GuideOfferServer] Starting SLIM server: {slim_config.local_id} -> {slim_config.endpoint}")
        start_server = create_slim_server(slim_config, agent_card, request_handler)

        async def run_slim():
            server = await start_server()
            logger.info("[GuideOfferServer] SLIM server running")
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass

        try:
            asyncio.run(run_slim())
        except KeyboardInterrupt:
            logger.info("[GuideOfferServer] Shutting down...")
    else:
        app = A2AStarletteApplication(agent_card=agent_card, http_handler=request_handler).build()
        logger.info(f"[GuideOfferServer] Starting autonomous guide server on {host}:{port}")
        uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    main()
