#!/usr/bin/env python3
"""
Scheduler Agent - A2A Server

Multi-agent tourist scheduling coordinator that:
1. Receives TouristRequests from tourist agents
2. Receives GuideOffers from guide agents
3. Runs greedy scheduling algorithm to match tourists to guides
4. Sends ScheduleProposals back to requesting tourists

This is implemented as an A2A server using the official a2a-sdk.
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime

import click
import uvicorn
import requests
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


async def send_to_ui_agent(message_data: dict):
    """Send data to UI agent for dashboard updates"""
    try:
        response = requests.post(
            "http://localhost:10012/",
            json={
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
            },
            timeout=2
        )
        if response.status_code == 200:
            logger.info("[Scheduler] Sent update to UI agent")
    except Exception as e:
        logger.warning(f"[Scheduler] Failed to send update to UI agent: {e}")


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

            # Check conflicts with existing bookings
            conflict = False
            for booking in guide_bookings[guide.guide_id]:
                if not (
                    guide.available_window.end <= booking.start
                    or guide.available_window.start >= booking.end
                ):
                    conflict = True
                    break

            if conflict:
                continue

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
            guide_bookings[best_guide.guide_id].append(
                best_guide.available_window
            )

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

        # Extract message content
        message_text = None
        if context.message and context.message.parts:
            for part in context.message.parts:
                if isinstance(part, Part) and part.root:
                    if isinstance(part.root, TextPart):
                        message_text = part.root.text
                        break

        if not message_text:
            logger.warning("[Scheduler] No text content in message")
            await updater.complete()
            return

        try:
            # Update status to working
            await updater.update_status(
                TaskState.working,
                message=updater.new_agent_message([Part(root=TextPart(text="Processing message..."))])
            )

            # Parse message as JSON
            data = json.loads(message_text)
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

                # Send proposal to UI agent
                await send_to_ui_agent(proposal.to_dict())

                # Send response as artifact
                await updater.add_artifact(
                    [Part(root=TextPart(text=proposal.to_json()))],
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
                ack_message = json.dumps({
                    "type": "Acknowledgment",
                    "message": f"Guide {offer.guide_id} registered",
                })
                await updater.add_artifact(
                    [Part(root=TextPart(text=ack_message))],
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
def main(host: str, port: int):
    """Start the Scheduler A2A server"""
    logger.info(f"[Scheduler] Starting A2A server on {host}:{port}")

    # Define scheduler agent capabilities
    skill = AgentSkill(
        id="tourist_scheduling",
        name="Tourist Scheduling Coordinator",
        description="Matches tourists with tour guides based on availability, budget, and preferences",
        tags=["scheduling", "coordination", "matching"],
        examples=[
            "Match tourist with guide for city tour",
            "Schedule museum visit with available guide",
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
        skills=[skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=SchedulerAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )

    logger.info("[Scheduler] Agent card configured, starting uvicorn...")
    uvicorn.run(server.build(), host=host, port=port)


if __name__ == "__main__":
    main()
