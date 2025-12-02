#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Scheduler Agent - A2A Server

Multi-agent tourist scheduling coordinator that:
1. Receives TouristRequests from tourist agents
2. Receives GuideOffers from guide agents
3. Runs greedy scheduling algorithm to match tourists to guides
4. Sends ScheduleProposals back to requesting tourists

This is implemented as an A2A server using the official a2a-sdk.
Supports both HTTP and SLIM transports via --transport option.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

import click
import uvicorn
import httpx
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
    DataPart,  # Allows structured JSON parts without manual decoding
)

from core.slim_transport import (
    SLIMConfig,
    check_slim_available,
    create_slim_server,
    config_from_env,
)

from core.messages import (
    Assignment,
    GuideOffer,
    ScheduleProposal,
    TouristRequest,
    Window,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# In-memory storage for scheduler state
@dataclass
class SchedulerState:
    """Centralized scheduler state"""

    tourist_requests: list[TouristRequest]
    guide_offers: list[GuideOffer]
    assignments: list[Assignment]

    def __init__(self):
        self.tourist_requests = []
        self.guide_offers = []
        self.assignments = []


state = SchedulerState()


def _discover_ui_ports() -> int:
    """Attempt to discover the UI agent A2A port from written ports file.

    Returns discovered port or default 10012. Non-fatal if file missing.
    """
    default_port = 10012
    try:
        ports_file = Path(__file__).resolve().parent.parent / "ui_agent_ports.json"
        if ports_file.exists():
            data = json.loads(ports_file.read_text())
            a2a_port = int(data.get("a2a_port", default_port))
            return a2a_port
    except Exception as e:
        logger.debug(f"[Scheduler] UI ports file read failed: {e}")
    return default_port

async def send_to_ui_agent(message_data: dict):
    """Send data to UI agent for dashboard updates (non-blocking async)."""
    port = _discover_ui_ports()
    url = f"http://localhost:{port}/"
    payload = {
        "jsonrpc": "2.0",
        "id": f"scheduler-ui-{int(time.time())}",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": json.dumps(message_data)}],
                "messageId": f"scheduler-msg-{int(time.time())}"
            }
        }
    }
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.post(url, json=payload)
        if response.status_code == 200:
            logger.info(f"[Scheduler] Sent update to UI agent on port {port}")
        else:
            logger.warning(f"[Scheduler] UI agent POST returned {response.status_code} on port {port}")
    except Exception as e:  # pragma: no cover - network failures are non-fatal
        logger.warning(f"[Scheduler] Failed to send update to UI agent on port {port}: {e}")


def build_schedule(
    tourist_requests: list[TouristRequest], guide_offers: list[GuideOffer]
) -> list[Assignment]:
    """
    Greedy scheduling algorithm:
    - For each tourist (sorted by earliest available time)
    - Find guides that can accommodate them
    - Assign to the guide with the best preference score
    """
    assignments = []
    guide_capacity = {g.guide_id: g.max_group_size for g in guide_offers}
    # Track bookings only for analytics; allow concurrent tourists per guide window up to capacity
    guide_bookings: dict[str, list[Window]] = {g.guide_id: [] for g in guide_offers}

    # Sort tourists by first available time
    sorted_tourists = sorted(
        tourist_requests,
        key=lambda t: t.availability[0].start if t.availability else datetime.max
    )

    for tourist in sorted_tourists:
        if not tourist.availability:
            continue

        best_guide = None
        best_score = -1

        for guide in guide_offers:
            # Check capacity
            if guide_capacity[guide.guide_id] <= 0:
                continue

            # Check budget
            if tourist.budget < guide.hourly_rate:
                continue

            # Check if any tourist availability window overlaps with guide availability
            has_overlap = False
            for tourist_window in tourist.availability:
                if (tourist_window.start <= guide.available_window.start and
                    tourist_window.end >= guide.available_window.end):
                    has_overlap = True
                    break

            if not has_overlap:
                continue

            # Removed conflict exclusion: allow overlapping usage while capacity>0

            # Calculate preference score
            score = sum(
                1 for cat in tourist.preferences if cat in guide.categories
            )

            if score > best_score:
                best_score = score
                best_guide = guide

        if best_guide:
            assignment = Assignment(
                tourist_id=tourist.tourist_id,
                guide_id=best_guide.guide_id,
                time_window=best_guide.available_window,
                categories=best_guide.categories,
                total_cost=best_guide.hourly_rate
                * (
                    (
                        best_guide.available_window.end
                        - best_guide.available_window.start
                    ).total_seconds()
                    / 3600
                ),
            )
            assignments.append(assignment)

            guide_capacity[best_guide.guide_id] -= 1
            guide_bookings[best_guide.guide_id].append(best_guide.available_window)

    return assignments


class SchedulerAgentExecutor(AgentExecutor):
    """Executes scheduler logic when messages arrive via A2A protocol"""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """Process incoming A2A messages"""
        logger.info(f"[Scheduler] Received task: {context.task_id}")

        # Create or get task
        task = context.current_task
        if not task:
            if not context.message:
                logger.error("[Scheduler] No message in context")
                return
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        # Create task updater for publishing events
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        # Extract message content (prefer DataPart for automatic JSON decoding)
        message_data = None
        raw_text_fallback = None
        if context.message and context.message.parts:
            for part in context.message.parts:
                try:
                    root = part.root
                    if isinstance(root, DataPart):
                        # Already decoded dict provided by A2A layer
                        message_data = root.data
                        break
                    if isinstance(root, TextPart):
                        raw_text_fallback = root.text
                        # Don't break; continue in case a DataPart also exists
                except Exception as e:
                    logger.debug(f"[Scheduler] Part inspection failed: {e}")

        if message_data is None and raw_text_fallback is not None:
            try:
                message_data = json.loads(raw_text_fallback)
            except json.JSONDecodeError as e:
                logger.error(f"[Scheduler] Failed to decode TextPart JSON: {e}")
                await updater.update_status(
                    TaskState.failed,
                    message=updater.new_agent_message([Part(root=TextPart(text=str(e)))]),
                )
                return

        if message_data is None:
            logger.warning("[Scheduler] No usable DataPart or decodable TextPart in message")
            await updater.complete()
            return

        try:
            # Update status to working
            await updater.update_status(
                TaskState.working,
                message=updater.new_agent_message([Part(root=TextPart(text="Processing message..."))])
            )

            # Message already decoded (DataPart) or parsed from TextPart fallback
            data = message_data
            message_type = data.get("type")

            if message_type == "TouristRequest":
                request = TouristRequest.from_dict(data)
                state.tourist_requests.append(request)
                logger.info(
                    f"[Scheduler] Stored TouristRequest from {request.tourist_id}"
                )

                # Send tourist request to UI agent
                await send_to_ui_agent(request.to_dict())

                # Build schedule after receiving request
                assignments = build_schedule(
                    state.tourist_requests, state.guide_offers
                )
                state.assignments = assignments

                # Send proposal back to tourist
                tourist_assignments = [
                    a for a in assignments if a.tourist_id == request.tourist_id
                ]
                proposal = ScheduleProposal(
                    proposal_id=f"proposal-{request.tourist_id}-{int(time.time())}",
                    assignments=tourist_assignments
                )

                # Include type field for downstream agents (UI, tourist) to identify the message
                proposal_dict = proposal.to_dict()
                proposal_dict["type"] = "ScheduleProposal"

                # Send proposal to UI agent
                await send_to_ui_agent(proposal_dict)

                # Send response as structured DataPart artifact (avoids downstream JSON parsing)
                await updater.add_artifact(
                    [Part(root=DataPart(data=proposal_dict))],
                    name="schedule_proposal"
                )
                logger.info(
                    f"[Scheduler] Sent ScheduleProposal with {len(tourist_assignments)} assignments"
                )

            elif message_type == "GuideOffer":
                offer = GuideOffer.from_dict(data)
                state.guide_offers.append(offer)
                logger.info(
                    f"[Scheduler] Stored GuideOffer from {offer.guide_id}"
                )

                # Send guide offer to UI agent
                await send_to_ui_agent(offer.to_dict())

                # Acknowledge receipt
                ack_message = {
                    "type": "Acknowledgment",
                    "message": f"Guide {offer.guide_id} registered",
                    "guide_id": offer.guide_id,
                    "timestamp": int(time.time()),
                }
                await updater.add_artifact(
                    [Part(root=DataPart(data=ack_message))],
                    name="guide_acknowledgment"
                )

            else:
                logger.warning(f"[Scheduler] Unknown message type: {message_type}")

            # Complete the task
            await updater.complete()

        except json.JSONDecodeError as e:
            logger.error(f"[Scheduler] JSON decode error: {e}")
            await updater.update_status(TaskState.failed, message=updater.new_agent_message([Part(root=TextPart(text=str(e)))]))
        except Exception as e:
            logger.error(f"[Scheduler] Error processing message: {e}")
            await updater.update_status(TaskState.failed, message=updater.new_agent_message([Part(root=TextPart(text=str(e)))]))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel a task (required by AgentExecutor interface)"""
        logger.info(f"[Scheduler] Canceling task: {context.task_id}")

        task = context.current_task
        if not task:
            return

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.cancel()


@click.command()
@click.option("--host", default="localhost", help="Server host")
@click.option("--port", default=10000, type=int, help="Server port")
@click.option("--transport", default="http", type=click.Choice(["http", "slim"]), help="Transport protocol")
@click.option("--slim-endpoint", default=None, help="SLIM gateway endpoint (default: from env or localhost:46357)")
@click.option("--slim-local-id", default=None, help="SLIM local agent ID")
def main(host: str, port: int, transport: str, slim_endpoint: str, slim_local_id: str):
    """Start the Scheduler A2A server"""
    logger.info(f"[Scheduler] Starting A2A server on {host}:{port} (transport: {transport})")

    # Define scheduler agent capabilities split into two focused skills
    skill_matching = AgentSkill(
        id="tourist_matching",
        name="Tourist Guide Matching",
        description="Matches tourists with tour guides based on availability, budget, and preferences",
        tags=["scheduling", "matching", "tourist", "guide"],
        examples=[
            '{"type": "TouristRequest", "tourist_id": "t-123", "availability": [{"start": "2025-11-06T09:00:00", "end": "2025-11-06T17:00:00"}], "budget": 150.0, "preferences": ["culture", "history"]}',
            "Produces ScheduleProposal artifacts containing matched Assignment entries"
        ],
    )
    skill_offer_collection = AgentSkill(
        id="guide_offer_collection",
        name="Guide Offer Collection",
        description="Receives guide offers and stores them for future tourist request matching",
        tags=["offers", "guide", "availability", "pricing"],
        examples=[
            '{"type": "GuideOffer", "guide_id": "g-42", "categories": ["culture", "art"], "available_window": {"start": "2025-11-07T10:00:00", "end": "2025-11-07T16:00:00"}, "hourly_rate": 85.0, "max_group_size": 6}',
            "Acknowledges GuideOffer with an Acknowledgment artifact"
        ],
    )

    agent_card = AgentCard(
        name="Scheduler Agent",
        description="Multi-agent tourist scheduling coordinator using greedy algorithm",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
    skills=[skill_matching, skill_offer_collection],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=SchedulerAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    if transport == "slim":
        # Start SLIM transport server
        if not check_slim_available():
            logger.error("[Scheduler] SLIM transport requested but slimrpc/slima2a not installed")
            logger.error("[Scheduler] Install with: uv pip install slima2a")
            raise SystemExit(1)

        # Load SLIM config from env or CLI options
        slim_config = config_from_env(prefix="SCHEDULER_")
        if slim_endpoint:
            slim_config.endpoint = slim_endpoint
        if slim_local_id:
            slim_config.local_id = slim_local_id
        else:
            slim_config.local_id = f"agntcy/tourist_scheduling/scheduler"

        logger.info(f"[Scheduler] SLIM endpoint: {slim_config.endpoint}")
        logger.info(f"[Scheduler] SLIM local ID: {slim_config.local_id}")

        # Create SLIM server start function
        start_server = create_slim_server(slim_config, agent_card, request_handler)

        async def run_slim_server():
            logger.info("[Scheduler] Starting SLIM transport server...")
            server = await start_server()
            logger.info("[Scheduler] SLIM server running, press Ctrl+C to stop")
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass

        try:
            asyncio.run(run_slim_server())
        except KeyboardInterrupt:
            logger.info("[Scheduler] Shutting down SLIM server...")
    else:
        # Start HTTP transport server (default)
        server = A2AStarletteApplication(
            agent_card=agent_card, http_handler=request_handler
        )

        # Build underlying Starlette app and inject a lightweight /health endpoint for launcher scripts
        app = server.build()
        try:
            from starlette.responses import JSONResponse  # provided by a2a-sdk[http-server] extras
            from starlette.routing import Route

            def health(request):  # type: ignore
                return JSONResponse({"status": "ok", "timestamp": int(time.time())})

            # Only add if not already present
            if not any(getattr(r, "path", None) == "/health" for r in app.router.routes):
                app.router.routes.append(Route("/health", endpoint=health, methods=["GET"]))
                logger.info("[Scheduler] Added /health endpoint")
        except Exception as e:
            logger.warning(f"[Scheduler] Failed to add /health endpoint: {e}")

        logger.info("[Scheduler] Agent card configured, starting uvicorn...")
        uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
