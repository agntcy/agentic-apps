#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Autonomous Tourist Server - exposes A2A endpoint to generate dynamic TouristRequest artifacts.

Supports both HTTP and SLIM transports via --transport option.

Request pattern (JSON-RPC message/send):
  params.message.parts[0].text or data JSON:
    {
      "action": "generate_request",
      "tourist_id": "tourist-ai-1"      # optional override
    }

Response Artifact (DataPart):
    {
      "type": "TouristRequest",
      "tourist_id": "tourist-ai-1",
      "availability": [{"start": "ISO", "end": "ISO"}],
      "preferences": ["culture", "history"],
      "budget": 200.0
    }
"""

import json
import logging
import asyncio
from datetime import datetime

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

from core.messages import TouristRequest
from core.slim_transport import (
    SLIMConfig,
    check_slim_available,
    create_slim_server,
    config_from_env,
)
from autonomous_tourist_agent import AutonomousTouristAgent  # reuse LLM + heuristic logic

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class TouristRequestExecutor(AgentExecutor):
    """Generates TouristRequest artifacts based on persona + trip context decisions."""

    def __init__(self, tourist_id: str):
        self.tourist_id = tourist_id
        self.agent = AutonomousTouristAgent(tourist_id=tourist_id, scheduler_url="http://localhost")

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.info(f"[TouristRequestServer] Received task: {context.task_id}")
        task = context.current_task
        if not task:
            if not context.message:
                logger.error("[TouristRequestServer] Missing message")
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
        if action != "generate_request":
            await updater.update_status(
                TaskState.failed,
                message=updater.new_agent_message([Part(root=TextPart(text=f"Unsupported action: {action}"))])
            )
            return

        await updater.update_status(
            TaskState.working,
            message=updater.new_agent_message([Part(root=TextPart(text="Generating tourist request..."))])
        )

        try:
            request = await self.agent.create_tourist_request()
            request_dict = request.to_dict()
            request_dict["type"] = "TouristRequest"
            await updater.add_artifact([Part(root=DataPart(data=request_dict))], name="tourist_request")
            await updater.complete()
        except Exception as e:
            logger.error(f"[TouristRequestServer] Error generating request: {e}")
            await updater.update_status(
                TaskState.failed,
                message=updater.new_agent_message([Part(root=TextPart(text=str(e)))])
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.info(f"[TouristRequestServer] Cancel task: {context.task_id}")
        task = context.current_task
        if not task:
            return
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.cancel()


@click.command()
@click.option("--host", default="localhost", help="Server host")
@click.option("--port", default=10021, type=int, help="Server port")
@click.option("--tourist-id", default="tourist-ai-1", help="Tourist ID")
@click.option("--transport", default="http", type=click.Choice(["http", "slim"]), help="Transport protocol")
@click.option("--slim-endpoint", default=None, help="SLIM gateway endpoint")
@click.option("--slim-local-id", default=None, help="SLIM local agent ID")
def main(host: str, port: int, tourist_id: str, transport: str, slim_endpoint: str, slim_local_id: str):
    skill = AgentSkill(
        id="dynamic_request_generation",
        name="Dynamic Tourist Request Generation",
        description="Generates a dynamic TouristRequest with availability, preferences and budget decisions.",
        tags=["tourist", "request", "preferences", "budget"],
        examples=[
            '{"action": "generate_request"}',
            "Returns TouristRequest artifact with dynamic availability & budget"
        ],
    )

    agent_card = AgentCard(
        name="Autonomous Tourist Agent",
        description="Autonomous tourist server generating dynamic travel requests on demand.",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["application/json", "text"],
        default_output_modes=["application/json", "text"],
        skills=[skill],
    )

    executor = TouristRequestExecutor(tourist_id=tourist_id)
    request_handler = DefaultRequestHandler(agent_executor=executor, task_store=InMemoryTaskStore())

    if transport == "slim":
        if not check_slim_available():
            logger.error("[TouristRequestServer] SLIM transport requested but slimrpc/slima2a not installed")
            raise SystemExit(1)

        slim_config = config_from_env(prefix="TOURIST_")
        if slim_endpoint:
            slim_config.endpoint = slim_endpoint
        if slim_local_id:
            slim_config.local_id = slim_local_id
        else:
            slim_config.local_id = f"agntcy/tourist_scheduling/{tourist_id}"

        logger.info(f"[TouristRequestServer] Starting SLIM server: {slim_config.local_id} -> {slim_config.endpoint}")
        start_server = create_slim_server(slim_config, agent_card, request_handler)

        async def run_slim():
            server = await start_server()
            logger.info("[TouristRequestServer] SLIM server running")
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass

        try:
            asyncio.run(run_slim())
        except KeyboardInterrupt:
            logger.info("[TouristRequestServer] Shutting down...")
    else:
        app = A2AStarletteApplication(agent_card=agent_card, http_handler=request_handler).build()
        logger.info(f"[TouristRequestServer] Starting autonomous tourist server on {host}:{port}")
        uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    main()
