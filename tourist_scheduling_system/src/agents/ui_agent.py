#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
UI Agent - Real-time Dashboard

A web-based dashboard agent that:
1. Subscribes to scheduler agent updates
2. Maintains real-time view of system state
3. Publishes a WebSocket-enabled web UI for live updates
4. Shows tourists, guides, assignments, and system metrics
5. Visualizes agent communication topology (HTTP/P2P vs SLIM)

This agent acts as a bridge between the multi-agent system and human operators,
providing visibility into the scheduling process in real-time.
"""

import json
import logging
import asyncio
import socket
import os
import queue
from threading import Thread
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, is_dataclass
from typing import List, Dict, Set, Optional
from enum import Enum

import click
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
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

from core.messages import Assignment, GuideOffer, TouristRequest, ScheduleProposal

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class TransportMode(str, Enum):
    """Transport mode for agent communication"""
    HTTP = "http"      # Direct HTTP/gRPC P2P
    SLIM = "slim"      # Via SLIM node (shared channel)
    UNKNOWN = "unknown"


@dataclass
class CommunicationEvent:
    """Represents a communication event between agents"""
    id: str
    timestamp: datetime
    source_agent: str
    target_agent: str
    message_type: str
    transport: TransportMode
    direction: str  # "inbound" or "outbound"
    summary: str

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "message_type": self.message_type,
            "transport": self.transport.value,
            "direction": self.direction,
            "summary": self.summary,
        }


@dataclass
class SystemMetrics:
    """Real-time system metrics for dashboard"""
    total_tourists: int = 0
    total_guides: int = 0
    total_assignments: int = 0
    satisfied_tourists: int = 0
    guide_utilization: float = 0.0
    avg_assignment_cost: float = 0.0
    total_messages: int = 0
    http_messages: int = 0
    slim_messages: int = 0
    last_updated: Optional[datetime] = None

    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()


# Global transport mode (detected from environment)
_transport_mode: TransportMode = TransportMode.UNKNOWN


def detect_transport_mode() -> TransportMode:
    """Detect current transport mode from environment"""
    global _transport_mode
    if _transport_mode == TransportMode.UNKNOWN:
        slim_endpoint = os.environ.get("SLIM_ENDPOINT", "")
        if slim_endpoint:
            _transport_mode = TransportMode.SLIM
        else:
            _transport_mode = TransportMode.HTTP
    return _transport_mode


@dataclass
class UIState:
    """Centralized UI state tracking all system data"""
    tourist_requests: Dict[str, TouristRequest]
    guide_offers: Dict[str, GuideOffer]
    assignments: List[Assignment]
    schedule_proposals: Dict[str, ScheduleProposal]
    metrics: SystemMetrics
    connected_clients: Set[WebSocket]
    communication_events: List[CommunicationEvent]
    active_agents: Dict[str, dict]  # agent_id -> {name, type, transport, last_seen}
    pending_broadcasts: queue.Queue  # Thread-safe queue for cross-thread broadcasts

    def __init__(self):
        self.tourist_requests = {}
        self.guide_offers = {}
        self.assignments = []
        self.schedule_proposals = {}
        self.metrics = SystemMetrics()
        self.connected_clients = set()
        self.communication_events = []
        self.active_agents = {}
        self.pending_broadcasts = queue.Queue()

    def add_communication_event(self, event: CommunicationEvent):
        """Add a communication event and update metrics"""
        self.communication_events.append(event)
        # Keep only last 100 events
        if len(self.communication_events) > 100:
            self.communication_events = self.communication_events[-100:]

        self.metrics.total_messages += 1
        if event.transport == TransportMode.SLIM:
            self.metrics.slim_messages += 1
        else:
            self.metrics.http_messages += 1

    def register_agent(self, agent_id: str, agent_type: str, transport: TransportMode):
        """Register or update an active agent"""
        self.active_agents[agent_id] = {
            "id": agent_id,
            "type": agent_type,
            "transport": transport.value,
            "last_seen": datetime.now().isoformat(),
        }

    def update_metrics(self):
        """Recalculate system metrics"""
        self.metrics.total_tourists = len(self.tourist_requests)
        self.metrics.total_guides = len(self.guide_offers)
        self.metrics.total_assignments = len(self.assignments)

        # Calculate satisfied tourists (those with assignments)
        assigned_tourists = set(a.tourist_id for a in self.assignments)
        self.metrics.satisfied_tourists = len(assigned_tourists)

        # Calculate guide utilization
        if self.guide_offers:
            busy_guides = set(a.guide_id for a in self.assignments)
            self.metrics.guide_utilization = len(busy_guides) / len(self.guide_offers)

        # Calculate average assignment cost
        if self.assignments:
            total_cost = sum(a.total_cost for a in self.assignments)
            self.metrics.avg_assignment_cost = total_cost / len(self.assignments)

        self.metrics.last_updated = datetime.now()

    async def broadcast_update(self, update_type: str, data: dict):
        """Queue updates for broadcast to all connected WebSocket clients.

        This is thread-safe - messages are queued and processed by the web server's event loop.
        """
        message = {
            "type": update_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        # Put in thread-safe queue for the web server to pick up
        self.pending_broadcasts.put(message)
        logger.info(f"[UI Agent] Queued broadcast: {update_type}, queue size: {self.pending_broadcasts.qsize()}")

    async def process_pending_broadcasts(self):
        """Process pending broadcasts - called from the web server's event loop."""
        if not self.connected_clients:
            # Clear the queue if no clients
            while not self.pending_broadcasts.empty():
                try:
                    self.pending_broadcasts.get_nowait()
                    logger.debug("[UI Agent] Discarding broadcast - no clients connected")
                except queue.Empty:
                    break
            return

        # Process all pending messages
        messages_to_send = []
        while not self.pending_broadcasts.empty():
            try:
                messages_to_send.append(self.pending_broadcasts.get_nowait())
            except queue.Empty:
                break

        if messages_to_send:
            logger.info(f"[UI Agent] Broadcasting {len(messages_to_send)} messages to {len(self.connected_clients)} clients")

        for message in messages_to_send:
            message_str = json.dumps(message, default=str)
            disconnected = set()
            for client in self.connected_clients:
                try:
                    await client.send_text(message_str)
                    logger.debug(f"[UI Agent] Sent broadcast: {message.get('type', 'unknown')}")
                except Exception as e:
                    logger.warning(f"Failed to send to client: {e}")
                    disconnected.add(client)
            # Remove disconnected clients
            self.connected_clients -= disconnected

    def to_dict(self) -> dict:
        """Convert state to dictionary for JSON serialization (supports Pydantic models or dataclasses)."""
        def _convert(obj):
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
                return obj.dict()
            if is_dataclass(obj) and not isinstance(obj, type):
                return asdict(obj)  # type: ignore[arg-type]
            if hasattr(obj, "to_dict") and not isinstance(obj, type):
                return obj.to_dict()  # type: ignore[attr-defined]
            return obj  # fallback raw

        return {
            "tourist_requests": [ _convert(req) for req in self.tourist_requests.values() ],
            "guide_offers": [ _convert(offer) for offer in self.guide_offers.values() ],
            "assignments": [ _convert(assignment) for assignment in self.assignments ],
            "schedule_proposals": { pid: _convert(prop) for pid, prop in self.schedule_proposals.items() },
            "metrics": _convert(self.metrics),
            "communication_events": [ e.to_dict() for e in self.communication_events[-20:] ],  # Last 20 events
            "active_agents": list(self.active_agents.values()),
            "transport_mode": detect_transport_mode().value,
        }


# Global UI state
ui_state = UIState()


class UIAgentExecutor(AgentExecutor):
    """Processes messages from other agents and updates UI state"""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Process incoming A2A messages and update UI state"""
        logger.info(f"[UI Agent] Received task: {context.task_id}")

        # Detect transport mode
        transport = detect_transport_mode()

        # Create or get task
        task = context.current_task
        if not task:
            if not context.message:
                logger.error("[UI Agent] No message in context")
                return
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        # Create task updater
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
            logger.warning("[UI Agent] No text content in message")
            await updater.complete()
            return

        try:
            await updater.update_status(
                TaskState.working,
                message=updater.new_agent_message([Part(root=TextPart(text="Processing UI update..."))])
            )

            # Parse message as JSON
            data = json.loads(message_text)
            message_type = data.get("type")

            # Create communication event
            source_agent = "unknown"
            event_id = f"evt-{datetime.now().strftime('%H%M%S%f')}"

            if message_type == "TouristRequest":
                request = TouristRequest.from_dict(data)
                source_agent = request.tourist_id
                ui_state.tourist_requests[request.tourist_id] = request
                ui_state.update_metrics()

                # Register agent and record event
                ui_state.register_agent(request.tourist_id, "tourist", transport)
                event = CommunicationEvent(
                    id=event_id,
                    timestamp=datetime.now(),
                    source_agent=request.tourist_id,
                    target_agent="scheduler",
                    message_type="TouristRequest",
                    transport=transport,
                    direction="inbound",
                    summary=f"Tourist {request.tourist_id} requested schedule (budget: ${request.budget})"
                )
                ui_state.add_communication_event(event)

                await ui_state.broadcast_update("tourist_request", request.to_dict())
                await ui_state.broadcast_update("communication_event", event.to_dict())
                logger.info(f"[UI Agent] Updated tourist request from {request.tourist_id}")

            elif message_type == "GuideOffer":
                offer = GuideOffer.from_dict(data)
                source_agent = offer.guide_id
                ui_state.guide_offers[offer.guide_id] = offer
                ui_state.update_metrics()

                # Register agent and record event
                ui_state.register_agent(offer.guide_id, "guide", transport)
                event = CommunicationEvent(
                    id=event_id,
                    timestamp=datetime.now(),
                    source_agent=offer.guide_id,
                    target_agent="scheduler",
                    message_type="GuideOffer",
                    transport=transport,
                    direction="inbound",
                    summary=f"Guide {offer.guide_id} offered services (${offer.hourly_rate}/hr)"
                )
                ui_state.add_communication_event(event)

                await ui_state.broadcast_update("guide_offer", offer.to_dict())
                await ui_state.broadcast_update("communication_event", event.to_dict())
                logger.info(f"[UI Agent] Updated guide offer from {offer.guide_id}")

            elif message_type == "ScheduleProposal":
                proposal = ScheduleProposal.from_dict(data)
                ui_state.schedule_proposals[proposal.proposal_id] = proposal
                ui_state.assignments = proposal.assignments
                ui_state.update_metrics()

                # Record scheduler response event
                ui_state.register_agent("scheduler", "scheduler", transport)
                event = CommunicationEvent(
                    id=event_id,
                    timestamp=datetime.now(),
                    source_agent="scheduler",
                    target_agent="tourists",
                    message_type="ScheduleProposal",
                    transport=transport,
                    direction="outbound",
                    summary=f"Scheduler created {len(proposal.assignments)} assignments"
                )
                ui_state.add_communication_event(event)

                await ui_state.broadcast_update("schedule_proposal", proposal.to_dict())
                await ui_state.broadcast_update("communication_event", event.to_dict())
                await ui_state.broadcast_update("metrics", asdict(ui_state.metrics))
                logger.info(f"[UI Agent] Updated schedule proposal {proposal.proposal_id}")

            else:
                logger.warning(f"[UI Agent] Unknown message type: {message_type}")

            await updater.complete()

        except json.JSONDecodeError as e:
            logger.error(f"[UI Agent] JSON decode error: {e}")
            await updater.update_status(TaskState.failed, message=updater.new_agent_message([Part(root=TextPart(text=str(e)))]))
        except Exception as e:
            logger.error(f"[UI Agent] Error processing message: {e}")
            await updater.update_status(TaskState.failed, message=updater.new_agent_message([Part(root=TextPart(text=str(e)))]))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel a task"""
        logger.info(f"[UI Agent] Canceling task: {context.task_id}")
        task = context.current_task
        if not task:
            return
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.cancel()


# FastAPI app for web UI
web_app = FastAPI(title="Tourist Scheduling Dashboard")

@web_app.get("/health")
async def health():
    """Simple health check endpoint for launcher scripts."""
    return {"status": "ok", "timestamp": datetime.now().isoformat(), "connected_clients": len(ui_state.connected_clients)}

@web_app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    ui_state.connected_clients.add(websocket)
    logger.info(f"[UI Agent] WebSocket client connected, total clients: {len(ui_state.connected_clients)}")

    try:
        # Send initial state
        initial_state = ui_state.to_dict()
        await websocket.send_text(json.dumps({
            "type": "initial_state",
            "data": initial_state,
            "timestamp": datetime.now().isoformat()
        }, default=str))

        # Start background task to poll the broadcast queue
        async def poll_broadcasts():
            """Background task to poll and send queued broadcasts."""
            try:
                while True:
                    await ui_state.process_pending_broadcasts()
                    await asyncio.sleep(0.1)  # Check every 100ms
            except asyncio.CancelledError:
                pass

        poll_task = asyncio.create_task(poll_broadcasts())

        try:
            # Keep connection alive by reading (will detect disconnects)
            while True:
                # This will raise WebSocketDisconnect when client leaves
                try:
                    # Use timeout so we can still check for pending broadcasts
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                    # Handle any client messages (like ping/pong)
                    if data == "ping":
                        await websocket.send_text("pong")
                except asyncio.TimeoutError:
                    # No message received, just continue
                    pass
        finally:
            poll_task.cancel()
            await poll_task

    except WebSocketDisconnect:
        ui_state.connected_clients.discard(websocket)
        logger.info(f"[UI Agent] WebSocket client disconnected, remaining clients: {len(ui_state.connected_clients)}")
    except Exception as e:
        logger.error(f"[UI Agent] WebSocket error: {e}")
        ui_state.connected_clients.discard(websocket)


@web_app.get("/api/state")
async def get_state():
    """REST endpoint to get current system state"""
    return ui_state.to_dict()


@web_app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard HTML"""
    return HTML_TEMPLATE


# HTML template for the dashboard
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tourist Scheduling Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        /* Dark scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #1a1a1a;
        }
        ::-webkit-scrollbar-thumb {
            background: #404040;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #525252;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: #e5e5e5;
        }
        .header {
            background: linear-gradient(135deg, #1a1a1a 0%, #0d0d0d 100%);
            color: white;
            padding: 1rem 2rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.5);
            border-bottom: 1px solid #f97316;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            font-size: 1.5rem;
            font-weight: 600;
            color: #f97316;
        }
        .header-right {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        .transport-badge {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .transport-http {
            background: rgba(107, 114, 128, 0.3);
            border: 1px solid #6b7280;
            color: #d1d5db;
        }
        .transport-slim {
            background: rgba(249, 115, 22, 0.2);
            border: 1px solid #f97316;
            color: #fb923c;
        }
        .transport-icon {
            font-size: 1.1rem;
        }
        .main {
            padding: 2rem;
            max-width: 1600px;
            margin: 0 auto;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .metric-card {
            background: linear-gradient(135deg, #1a1a1a 0%, #111111 100%);
            padding: 1.25rem;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            border: 1px solid #2a2a2a;
            text-align: center;
        }
        .metric-value {
            font-size: 1.75rem;
            font-weight: bold;
            color: #f97316;
            margin-bottom: 0.25rem;
        }
        .metric-label {
            color: #9ca3af;
            font-size: 0.8rem;
        }
        .metric-card.transport {
            background: linear-gradient(135deg, #1f1f1f 0%, #171717 100%);
            border: 1px solid #404040;
        }
        .metric-card.transport .metric-value {
            color: #fb923c;
            font-size: 1.25rem;
        }

        /* Network Topology Section */
        .topology-section {
            background: linear-gradient(135deg, #1a1a1a 0%, #111111 100%);
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            border: 1px solid #2a2a2a;
            margin-bottom: 2rem;
            overflow: hidden;
        }
        .topology-header {
            background: #0d0d0d;
            padding: 1rem 1.5rem;
            border-bottom: 1px solid #2a2a2a;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .topology-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #f97316;
        }
        .topology-legend {
            display: flex;
            gap: 1.5rem;
            font-size: 0.8rem;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: #9ca3af;
        }
        .legend-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }
        .legend-dot.http { background: #6b7280; }
        .legend-dot.slim { background: #f97316; }
        .legend-dot.scheduler { background: #fb923c; }
        .topology-content {
            padding: 1.5rem;
            min-height: 200px;
        }
        .network-diagram {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 1rem;
            flex-wrap: wrap;
            min-height: 280px;
            position: relative;
        }
        .network-diagram.star-topology {
            flex-direction: column;
        }
        .network-diagram.svg-topology {
            display: block;
            padding: 0;
        }
        .network-diagram.svg-topology svg {
            display: block;
            margin: 0 auto;
        }
        .svg-node {
            transition: filter 0.2s;
        }
        .svg-node:hover {
            filter: brightness(1.2) drop-shadow(0 0 8px rgba(249, 115, 22, 0.5));
        }
        .svg-node circle {
            transition: stroke-width 0.15s;
        }
        .svg-node:hover circle {
            stroke-width: 3;
        }
        .conn-line {
            transition: stroke-width 0.15s;
        }
        .agent-column {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            align-items: center;
        }
        .agent-row {
            display: flex;
            gap: 1rem;
            align-items: center;
            justify-content: center;
            flex-wrap: wrap;
        }
        .agent-column-title {
            font-size: 0.75rem;
            font-weight: 600;
            color: #9ca3af;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }
        .agent-node {
            width: 70px;
            height: 70px;
            border-radius: 50%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            font-size: 0.65rem;
            font-weight: 500;
            color: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
            transition: transform 0.2s, box-shadow 0.2s;
            position: relative;
        }
        .agent-node:hover {
            transform: scale(1.1);
            box-shadow: 0 4px 16px rgba(249, 115, 22, 0.3);
        }
        .agent-node.tourist { background: linear-gradient(135deg, #f97316 0%, #ea580c 100%); }
        .agent-node.guide { background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%); }
        .agent-node.scheduler { background: linear-gradient(135deg, #fb923c 0%, #f97316 100%); width: 80px; height: 80px; }
        .agent-node.ui-agent { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }
        .agent-node.browser { background: linear-gradient(135deg, #10b981 0%, #059669 100%); width: 60px; height: 60px; }
        .agent-node .icon { font-size: 1.3rem; margin-bottom: 0.2rem; }
        .agent-node.scheduler .icon { font-size: 1.5rem; }

        .connection-hub {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.5rem;
            margin: 1rem 0;
        }
        .hub-node {
            width: 80px;
            height: 80px;
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2rem;
            box-shadow: 0 4px 16px rgba(249, 115, 22, 0.4);
        }
        .hub-node.http {
            background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);
        }
        .hub-node.slim {
            background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
        }
        .hub-label {
            font-size: 0.75rem;
            font-weight: 600;
            color: #f97316;
        }
        .hub-label.http { color: #9ca3af; }

        /* Connection lines for star topology */
        .star-connections {
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .connection-group {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin: 0.25rem 0;
        }
        .connection-label {
            font-size: 0.6rem;
            color: #9ca3af;
            white-space: nowrap;
        }
        .connection-line {
            width: 30px;
            height: 2px;
            background: #404040;
            position: relative;
        }
        .connection-line.vertical {
            width: 2px;
            height: 20px;
        }
        .connection-line::after {
            content: '';
            position: absolute;
            right: -4px;
            top: -3px;
            width: 0;
            height: 0;
            border-left: 6px solid #404040;
            border-top: 4px solid transparent;
            border-bottom: 4px solid transparent;
        }
        .connection-line.vertical::after {
            right: auto;
            top: auto;
            bottom: -4px;
            left: -3px;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 6px solid #404040;
        }
        .connection-line.http { background: #6b7280; }
        .connection-line.http::after { border-left-color: #6b7280; }
        .connection-line.http.vertical::after { border-top-color: #6b7280; border-left-color: transparent; }
        .connection-line.slim { background: #f97316; }
        .connection-line.slim::after { border-left-color: #f97316; }
        .connection-line.slim.vertical::after { border-top-color: #f97316; border-left-color: transparent; }
        .connection-line.websocket { background: #10b981; }
        .connection-line.websocket::after { border-left-color: #10b981; }

        /* Topology labels */
        .topology-row {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            width: 100%;
        }
        .topology-row-label {
            font-size: 0.7rem;
            color: #9ca3af;
            min-width: 60px;
            text-align: right;
        }
        .agents-container {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            justify-content: center;
        }

        .content-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }
        .section {
            background: linear-gradient(135deg, #1a1a1a 0%, #111111 100%);
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            border: 1px solid #2a2a2a;
            overflow: hidden;
        }
        .section-header {
            background: #0d0d0d;
            padding: 1rem 1.5rem;
            border-bottom: 1px solid #2a2a2a;
        }
        .section-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #f97316;
        }
        .section-content {
            padding: 1rem;
            max-height: 300px;
            overflow-y: auto;
        }
        .item {
            padding: 0.75rem;
            border: 1px solid #2a2a2a;
            border-radius: 6px;
            margin-bottom: 0.75rem;
            background: #0d0d0d;
        }
        .item:last-child {
            margin-bottom: 0;
        }
        .item-header {
            font-weight: 600;
            color: #e5e7eb;
            margin-bottom: 0.25rem;
        }
        .item-details {
            font-size: 0.85rem;
            color: #9ca3af;
        }
        .assignments-section {
            grid-column: 1 / -1;
        }
        .assignment {
            background: #1a2e1a;
            border: 1px solid #2d4a2d;
        }

        /* Communication Log */
        .comm-log-section {
            grid-column: 1 / -1;
        }
        .comm-event {
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
            padding: 0.75rem;
            border-left: 3px solid #404040;
            margin-bottom: 0.5rem;
            background: #0d0d0d;
            border-radius: 0 6px 6px 0;
            font-size: 0.85rem;
        }
        .comm-event.http { border-left-color: #6b7280; }
        .comm-event.slim { border-left-color: #f97316; }
        .comm-event.inbound { background: #1a1a2e; }
        .comm-event.outbound { background: #2e2a1a; }
        .comm-time {
            font-size: 0.7rem;
            color: #6b7280;
            white-space: nowrap;
        }
        .comm-icon {
            font-size: 1rem;
        }
        .comm-content {
            flex: 1;
        }
        .comm-agents {
            font-weight: 600;
            color: #e5e7eb;
        }
        .comm-arrow { color: #6b7280; margin: 0 0.25rem; }
        .comm-summary {
            color: #9ca3af;
            margin-top: 0.25rem;
        }
        .comm-transport-tag {
            font-size: 0.65rem;
            padding: 0.15rem 0.4rem;
            border-radius: 4px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .comm-transport-tag.http { background: #374151; color: #9ca3af; }
        .comm-transport-tag.slim { background: #7c2d12; color: #fb923c; }

        .status {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
        }
        .status-online {
            background: rgba(255,255,255,0.2);
            color: white;
        }
        .status-offline {
            background: #7f1d1d;
            color: #fca5a5;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🗺️ Tourist Scheduling Dashboard</h1>
        <div class="header-right">
            <div id="transport-badge" class="transport-badge transport-http">
                <span class="transport-icon">🔗</span>
                <span id="transport-label">HTTP (P2P)</span>
            </div>
            <div id="connection-status" class="status status-online">● Connected</div>
        </div>
    </div>

    <div class="main">
        <!-- Metrics -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value" id="total-tourists">0</div>
                <div class="metric-label">Tourists</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="total-guides">0</div>
                <div class="metric-label">Guides</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="total-assignments">0</div>
                <div class="metric-label">Assignments</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="satisfaction-rate">0%</div>
                <div class="metric-label">Satisfaction</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="guide-utilization">0%</div>
                <div class="metric-label">Utilization</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="avg-cost">$0</div>
                <div class="metric-label">Avg Cost</div>
            </div>
            <div class="metric-card transport">
                <div class="metric-value" id="total-messages">0</div>
                <div class="metric-label">Total Messages</div>
            </div>
            <div class="metric-card transport">
                <div class="metric-value" id="http-messages">0</div>
                <div class="metric-label">HTTP Messages</div>
            </div>
            <div class="metric-card transport">
                <div class="metric-value" id="slim-messages">0</div>
                <div class="metric-label">SLIM Messages</div>
            </div>
        </div>

        <!-- Network Topology -->
        <div class="topology-section">
            <div class="topology-header">
                <div class="topology-title">🌐 Agent Communication Network</div>
                <div class="topology-legend" id="topology-legend">
                    <div class="legend-item">
                        <div class="legend-dot http"></div>
                        <span>HTTP/gRPC</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-dot slim"></div>
                        <span>SLIM (MLS)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-dot" style="background:#10b981;"></div>
                        <span>WebSocket</span>
                    </div>
                </div>
            </div>
            <div class="topology-content">
                <div class="network-diagram" id="network-diagram">
                    <!-- Dynamic network topology will be rendered here -->
                    <div style="color: #9ca3af; text-align: center;">
                        Waiting for agents to connect...
                    </div>
                </div>
            </div>
        </div>

        <!-- Content Grid -->
        <div class="content-grid">
            <!-- Tourists -->
            <div class="section">
                <div class="section-header">
                    <div class="section-title">🧳 Tourist Requests</div>
                </div>
                <div class="section-content" id="tourists-list">
                    <div class="item">No tourists yet</div>
                </div>
            </div>

            <!-- Guides -->
            <div class="section">
                <div class="section-header">
                    <div class="section-title">🎯 Guide Offers</div>
                </div>
                <div class="section-content" id="guides-list">
                    <div class="item">No guides yet</div>
                </div>
            </div>
        </div>

        <!-- Communication Log -->
        <div class="content-grid">
            <div class="section comm-log-section">
                <div class="section-header">
                    <div class="section-title">📡 Communication Log</div>
                </div>
                <div class="section-content" id="comm-log">
                    <div class="item" style="text-align: center; color: #9ca3af;">
                        No communication events yet
                    </div>
                </div>
            </div>
        </div>

        <!-- Assignments -->
        <div class="content-grid">
            <div class="section assignments-section">
                <div class="section-header">
                    <div class="section-title">✅ Current Assignments</div>
                </div>
                <div class="section-content" id="assignments-list">
                    <div class="item">No assignments yet</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // State
        let currentTransport = 'http';
        const commEvents = [];
        const activeAgents = new Map();

        // WebSocket connection
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        const statusEl = document.getElementById('connection-status');

        ws.onopen = () => {
            statusEl.textContent = '● Connected';
            statusEl.className = 'status status-online';
        };

        ws.onclose = () => {
            statusEl.textContent = '● Disconnected';
            statusEl.className = 'status status-offline';
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            statusEl.textContent = '● Error';
            statusEl.className = 'status status-offline';
        };

        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);

            if (message.type === 'initial_state') {
                updateFullState(message.data);
            } else if (message.type === 'tourist_request') {
                updateTouristsList([message.data]);
                updateMetricsIncremental('tourist');
            } else if (message.type === 'guide_offer') {
                updateGuidesList([message.data]);
                updateMetricsIncremental('guide');
            } else if (message.type === 'schedule_proposal') {
                updateAssignmentsList(message.data.assignments || []);
                updateMetrics(message.data.metrics || document.cachedMetrics || {});
            } else if (message.type === 'metrics') {
                updateMetrics(message.data);
                document.cachedMetrics = message.data;
            } else if (message.type === 'communication_event') {
                addCommEvent(message.data);
            }
        };

        function updateFullState(state) {
            // Update transport mode
            if (state.transport_mode) {
                updateTransportBadge(state.transport_mode);
            }

            // Update agents for topology
            if (state.active_agents) {
                state.active_agents.forEach(agent => {
                    activeAgents.set(agent.id, agent);
                });
                renderNetworkTopology();
            }

            // Update communication events
            if (state.communication_events) {
                state.communication_events.forEach(evt => addCommEvent(evt, true));
            }

            updateMetrics(state.metrics || {});
            updateTouristsList(state.tourist_requests || []);
            updateGuidesList(state.guide_offers || []);
            updateAssignmentsList(state.assignments || []);
            document.cachedMetrics = state.metrics;
        }

        function updateTransportBadge(transport) {
            currentTransport = transport;
            const badge = document.getElementById('transport-badge');
            const label = document.getElementById('transport-label');

            if (transport === 'slim') {
                badge.className = 'transport-badge transport-slim';
                label.textContent = 'SLIM Node';
                document.querySelector('.transport-icon').textContent = '🔄';
            } else {
                badge.className = 'transport-badge transport-http';
                label.textContent = 'HTTP (P2P)';
                document.querySelector('.transport-icon').textContent = '🔗';
            }
        }

        // ===== Interactive SVG Network Topology with Drag & Drop =====
        const nodePositions = new Map();  // Store node positions for dragging
        let dragState = null;  // Current drag state

        function renderNetworkTopology() {
            const container = document.getElementById('network-diagram');
            const tourists = Array.from(activeAgents.values()).filter(a => a.type === 'tourist');
            const guides = Array.from(activeAgents.values()).filter(a => a.type === 'guide');
            const hasScheduler = Array.from(activeAgents.values()).some(a => a.type === 'scheduler');

            if (tourists.length === 0 && guides.length === 0 && !hasScheduler) {
                container.innerHTML = '<div style="color: #9ca3af; text-align: center;">Waiting for agents to connect...</div>';
                container.className = 'network-diagram';
                return;
            }

            container.className = 'network-diagram svg-topology';
            const isSlim = currentTransport === 'slim';

            // Calculate SVG dimensions based on container
            const width = 580;
            const height = 350;
            const centerX = width / 2;
            const centerY = height / 2;

            // Build node list with initial positions
            const nodes = [];
            const connections = [];

            if (isSlim) {
                // SLIM: Star topology with central hub
                // Central SLIM node
                const slimNode = { id: 'slim-hub', type: 'slim', icon: '🔄', label: 'SLIM', x: centerX, y: centerY };
                initNodePosition(slimNode);
                nodes.push(slimNode);

                // Scheduler
                const schedulerNode = { id: 'scheduler', type: 'scheduler', icon: '📊', label: 'Scheduler', x: centerX - 120, y: centerY + 100 };
                initNodePosition(schedulerNode);
                nodes.push(schedulerNode);
                connections.push({ from: 'slim-hub', to: 'scheduler', type: 'slim' });

                // UI Agent
                const uiNode = { id: 'ui-agent', type: 'ui', icon: '🖥️', label: 'UI Agent', x: centerX, y: centerY + 100 };
                initNodePosition(uiNode);
                nodes.push(uiNode);
                connections.push({ from: 'slim-hub', to: 'ui-agent', type: 'slim' });

                // Browser
                const browserNode = { id: 'browser', type: 'browser', icon: '🌐', label: 'You', x: centerX, y: centerY + 180 };
                initNodePosition(browserNode);
                nodes.push(browserNode);
                connections.push({ from: 'ui-agent', to: 'browser', type: 'websocket' });

                // Tourists around the top
                tourists.slice(0, 6).forEach((t, i) => {
                    const angle = Math.PI + (Math.PI / (tourists.length + 1)) * (i + 1);
                    const radius = 120;
                    const node = {
                        id: t.id,
                        type: 'tourist',
                        icon: '🧳',
                        label: t.id.replace('tourist-', ''),
                        x: centerX + Math.cos(angle) * radius,
                        y: centerY + Math.sin(angle) * radius
                    };
                    initNodePosition(node);
                    nodes.push(node);
                    connections.push({ from: 'slim-hub', to: t.id, type: 'slim' });
                });

                // Guides on the right
                guides.slice(0, 6).forEach((g, i) => {
                    const node = {
                        id: g.id,
                        type: 'guide',
                        icon: '🎯',
                        label: g.id.replace('guide-', ''),
                        x: centerX + 150,
                        y: centerY - 60 + (i * 50)
                    };
                    initNodePosition(node);
                    nodes.push(node);
                    connections.push({ from: 'slim-hub', to: g.id, type: 'slim' });
                });
            } else {
                // HTTP: P2P mesh with scheduler as hub
                // Scheduler (center)
                const schedulerNode = { id: 'scheduler', type: 'scheduler', icon: '📊', label: 'Scheduler', x: centerX, y: centerY - 50 };
                initNodePosition(schedulerNode);
                nodes.push(schedulerNode);

                // UI Agent (below scheduler)
                const uiNode = { id: 'ui-agent', type: 'ui', icon: '🖥️', label: 'UI Agent', x: centerX, y: centerY + 40 };
                initNodePosition(uiNode);
                nodes.push(uiNode);
                connections.push({ from: 'scheduler', to: 'ui-agent', type: 'http' });

                // Browser (below UI Agent) - WebSocket connection
                const browserNode = { id: 'browser', type: 'browser', icon: '🌐', label: 'You', x: centerX, y: centerY + 130 };
                initNodePosition(browserNode);
                nodes.push(browserNode);
                connections.push({ from: 'ui-agent', to: 'browser', type: 'websocket' });

                // Tourists on the left
                tourists.slice(0, 6).forEach((t, i) => {
                    const node = {
                        id: t.id,
                        type: 'tourist',
                        icon: '🧳',
                        label: t.id.replace('tourist-', ''),
                        x: 80,
                        y: 60 + (i * 55)
                    };
                    initNodePosition(node);
                    nodes.push(node);
                    connections.push({ from: 'scheduler', to: t.id, type: 'http' });
                });

                // Guides on the right
                guides.slice(0, 6).forEach((g, i) => {
                    const node = {
                        id: g.id,
                        type: 'guide',
                        icon: '🎯',
                        label: g.id.replace('guide-', ''),
                        x: width - 80,
                        y: 60 + (i * 55)
                    };
                    initNodePosition(node);
                    nodes.push(node);
                    connections.push({ from: 'scheduler', to: g.id, type: 'http' });
                });
            }

            // Render SVG
            container.innerHTML = renderSVGTopology(width, height, nodes, connections, isSlim);

            // Attach drag event listeners
            attachDragListeners(container, nodes, connections, width, height, isSlim);
        }

        function initNodePosition(node) {
            // Initialize or restore position from saved state
            if (nodePositions.has(node.id)) {
                const saved = nodePositions.get(node.id);
                node.x = saved.x;
                node.y = saved.y;
            } else {
                nodePositions.set(node.id, { x: node.x, y: node.y });
            }
        }

        function renderSVGTopology(width, height, nodes, connections, isSlim) {
            let svg = `<svg width="${width}" height="${height}" class="topology-svg" style="cursor: default;">`;

            // Defs for markers (arrowheads)
            svg += `<defs>
                <marker id="arrow-http" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto" markerUnits="strokeWidth">
                    <path d="M0,0 L0,6 L6,3 z" fill="#6b7280" />
                </marker>
                <marker id="arrow-slim" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto" markerUnits="strokeWidth">
                    <path d="M0,0 L0,6 L6,3 z" fill="#f97316" />
                </marker>
                <marker id="arrow-websocket" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto" markerUnits="strokeWidth">
                    <path d="M0,0 L0,6 L6,3 z" fill="#22c55e" />
                </marker>
            </defs>`;

            // Draw connections first (behind nodes)
            connections.forEach(conn => {
                const fromNode = nodes.find(n => n.id === conn.from);
                const toNode = nodes.find(n => n.id === conn.to);
                if (fromNode && toNode) {
                    const strokeColor = conn.type === 'slim' ? '#f97316' : conn.type === 'websocket' ? '#22c55e' : '#6b7280';
                    const markerId = `arrow-${conn.type}`;
                    // Shorten line to not overlap with node circles
                    const dx = toNode.x - fromNode.x;
                    const dy = toNode.y - fromNode.y;
                    const dist = Math.sqrt(dx*dx + dy*dy);
                    const nodeRadius = 30;
                    const ratio1 = nodeRadius / dist;
                    const ratio2 = (dist - nodeRadius - 5) / dist;
                    const x1 = fromNode.x + dx * ratio1;
                    const y1 = fromNode.y + dy * ratio1;
                    const x2 = fromNode.x + dx * ratio2;
                    const y2 = fromNode.y + dy * ratio2;
                    svg += `<line class="conn-line" data-from="${conn.from}" data-to="${conn.to}"
                            x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"
                            stroke="${strokeColor}" stroke-width="2" marker-end="url(#${markerId})" />`;
                }
            });

            // Draw nodes
            nodes.forEach(node => {
                const nodeClass = `svg-node ${node.type}`;
                const radius = node.type === 'slim' ? 35 : 28;
                const fillColor = getNodeFill(node.type);
                const strokeColor = getNodeStroke(node.type);

                svg += `<g class="${nodeClass}" data-node-id="${node.id}" style="cursor: grab;">
                    <circle cx="${node.x}" cy="${node.y}" r="${radius}" fill="${fillColor}" stroke="${strokeColor}" stroke-width="2" />
                    <text x="${node.x}" y="${node.y - 3}" text-anchor="middle" font-size="18" dominant-baseline="middle">${node.icon}</text>
                    <text x="${node.x}" y="${node.y + 16}" text-anchor="middle" font-size="10" fill="#e5e7eb" dominant-baseline="middle">${node.label}</text>
                </g>`;
            });

            // Hint text
            svg += `<text x="${width - 10}" y="${height - 10}" text-anchor="end" font-size="9" fill="#6b7280">Drag nodes to rearrange</text>`;

            svg += '</svg>';
            return svg;
        }

        function getNodeFill(type) {
            switch(type) {
                case 'slim': return '#7c2d12';
                case 'scheduler': return '#78350f';
                case 'tourist': return '#1e3a5f';
                case 'guide': return '#14532d';
                case 'ui': return '#312e81';
                case 'browser': return '#1f2937';
                default: return '#374151';
            }
        }

        function getNodeStroke(type) {
            switch(type) {
                case 'slim': return '#f97316';
                case 'scheduler': return '#fb923c';
                case 'tourist': return '#3b82f6';
                case 'guide': return '#22c55e';
                case 'ui': return '#818cf8';
                case 'browser': return '#9ca3af';
                default: return '#6b7280';
            }
        }

        function attachDragListeners(container, nodes, connections, width, height, isSlim) {
            const svg = container.querySelector('svg');
            if (!svg) return;

            svg.addEventListener('mousedown', (e) => {
                const nodeGroup = e.target.closest('.svg-node');
                if (!nodeGroup) return;
                const nodeId = nodeGroup.dataset.nodeId;
                const node = nodes.find(n => n.id === nodeId);
                if (!node) return;

                e.preventDefault();
                dragState = {
                    nodeId: nodeId,
                    startX: e.clientX,
                    startY: e.clientY,
                    origX: node.x,
                    origY: node.y
                };
                nodeGroup.style.cursor = 'grabbing';
                svg.style.cursor = 'grabbing';
            });

            svg.addEventListener('mousemove', (e) => {
                if (!dragState) return;
                e.preventDefault();

                const dx = e.clientX - dragState.startX;
                const dy = e.clientY - dragState.startY;
                let newX = dragState.origX + dx;
                let newY = dragState.origY + dy;

                // Clamp to SVG bounds
                newX = Math.max(30, Math.min(width - 30, newX));
                newY = Math.max(30, Math.min(height - 30, newY));

                // Update node position
                const node = nodes.find(n => n.id === dragState.nodeId);
                if (node) {
                    node.x = newX;
                    node.y = newY;
                    nodePositions.set(node.id, { x: newX, y: newY });

                    // Update SVG elements directly for smooth dragging
                    const nodeGroup = svg.querySelector(`.svg-node[data-node-id="${node.id}"]`);
                    if (nodeGroup) {
                        const circle = nodeGroup.querySelector('circle');
                        const texts = nodeGroup.querySelectorAll('text');
                        if (circle) {
                            circle.setAttribute('cx', newX);
                            circle.setAttribute('cy', newY);
                        }
                        if (texts[0]) {
                            texts[0].setAttribute('x', newX);
                            texts[0].setAttribute('y', newY - 3);
                        }
                        if (texts[1]) {
                            texts[1].setAttribute('x', newX);
                            texts[1].setAttribute('y', newY + 16);
                        }
                    }

                    // Update connected lines
                    updateConnectionLines(svg, nodes, connections);
                }
            });

            svg.addEventListener('mouseup', () => {
                if (dragState) {
                    const nodeGroup = svg.querySelector(`.svg-node[data-node-id="${dragState.nodeId}"]`);
                    if (nodeGroup) nodeGroup.style.cursor = 'grab';
                    svg.style.cursor = 'default';
                    dragState = null;
                }
            });

            svg.addEventListener('mouseleave', () => {
                if (dragState) {
                    svg.style.cursor = 'default';
                    dragState = null;
                }
            });
        }

        function updateConnectionLines(svg, nodes, connections) {
            connections.forEach(conn => {
                const fromNode = nodes.find(n => n.id === conn.from);
                const toNode = nodes.find(n => n.id === conn.to);
                const line = svg.querySelector(`.conn-line[data-from="${conn.from}"][data-to="${conn.to}"]`);
                if (fromNode && toNode && line) {
                    const dx = toNode.x - fromNode.x;
                    const dy = toNode.y - fromNode.y;
                    const dist = Math.sqrt(dx*dx + dy*dy);
                    if (dist < 1) return;
                    const nodeRadius = 30;
                    const ratio1 = nodeRadius / dist;
                    const ratio2 = (dist - nodeRadius - 5) / dist;
                    const x1 = fromNode.x + dx * ratio1;
                    const y1 = fromNode.y + dy * ratio1;
                    const x2 = fromNode.x + dx * ratio2;
                    const y2 = fromNode.y + dy * ratio2;
                    line.setAttribute('x1', x1);
                    line.setAttribute('y1', y1);
                    line.setAttribute('x2', x2);
                    line.setAttribute('y2', y2);
                }
            });
        }

        function addCommEvent(evt, silent = false) {
            // Add to local state
            commEvents.unshift(evt);
            if (commEvents.length > 20) commEvents.pop();

            // Update agent registry
            if (evt.source_agent && evt.source_agent !== 'unknown') {
                activeAgents.set(evt.source_agent, {
                    id: evt.source_agent,
                    type: evt.source_agent.includes('tourist') ? 'tourist' :
                          evt.source_agent.includes('guide') ? 'guide' : 'scheduler',
                    transport: evt.transport
                });
            }

            // Re-render
            renderCommLog();
            if (!silent) renderNetworkTopology();
        }

        function renderCommLog() {
            const container = document.getElementById('comm-log');
            if (commEvents.length === 0) {
                container.innerHTML = '<div class="item" style="text-align: center; color: #9ca3af;">No communication events yet</div>';
                return;
            }

            container.innerHTML = commEvents.map(evt => {
                const time = new Date(evt.timestamp).toLocaleTimeString();
                const icon = evt.direction === 'inbound' ? '📥' : '📤';
                const transportClass = evt.transport || 'http';

                return `
                    <div class="comm-event ${transportClass} ${evt.direction}">
                        <div class="comm-time">${time}</div>
                        <div class="comm-icon">${icon}</div>
                        <div class="comm-content">
                            <div class="comm-agents">
                                ${evt.source_agent}
                                <span class="comm-arrow">→</span>
                                ${evt.target_agent}
                                <span class="comm-transport-tag ${transportClass}">${transportClass.toUpperCase()}</span>
                            </div>
                            <div class="comm-summary">${evt.summary}</div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function updateMetricsIncremental(kind) {
            const tourists = document.querySelectorAll('#tourists-list .item-header').length;
            const guides = document.querySelectorAll('#guides-list .item-header').length;
            const assignments = document.querySelectorAll('#assignments-list .assignment').length;
            const metrics = {
                total_tourists: tourists,
                total_guides: guides,
                total_assignments: assignments,
                satisfied_tourists: assignments,
                guide_utilization: guides ? (assignments / guides) : 0,
                avg_assignment_cost: document.cachedMetrics ? document.cachedMetrics.avg_assignment_cost : 0,
                total_messages: document.cachedMetrics ? (document.cachedMetrics.total_messages || 0) : 0,
                http_messages: document.cachedMetrics ? (document.cachedMetrics.http_messages || 0) : 0,
                slim_messages: document.cachedMetrics ? (document.cachedMetrics.slim_messages || 0) : 0
            };
            updateMetrics(metrics);
        }

        function updateMetrics(metrics) {
            document.getElementById('total-tourists').textContent = metrics.total_tourists || 0;
            document.getElementById('total-guides').textContent = metrics.total_guides || 0;
            document.getElementById('total-assignments').textContent = metrics.total_assignments || 0;

            const satisfactionRate = metrics.total_tourists > 0
                ? Math.round((metrics.satisfied_tourists / metrics.total_tourists) * 100)
                : 0;
            document.getElementById('satisfaction-rate').textContent = satisfactionRate + '%';

            document.getElementById('guide-utilization').textContent =
                Math.round((metrics.guide_utilization || 0) * 100) + '%';

            document.getElementById('avg-cost').textContent =
                '$' + (metrics.avg_assignment_cost || 0).toFixed(0);

            // Transport metrics
            document.getElementById('total-messages').textContent = metrics.total_messages || 0;
            document.getElementById('http-messages').textContent = metrics.http_messages || 0;
            document.getElementById('slim-messages').textContent = metrics.slim_messages || 0;
        }

        const touristsState = new Map();
        const guidesState = new Map();

        function renderCollection(containerId, stateMap, kind) {
            const container = document.getElementById(containerId);
            if (stateMap.size === 0) {
                container.innerHTML = `<div class="item">No ${kind} yet</div>`;
                return;
            }
            const idKey = kind === 'tourists' ? 'tourist_id' : 'guide_id';
            const items = Array.from(stateMap.values()).sort((a,b) =>
                (a[idKey] || '').localeCompare(b[idKey] || '')
            );
            container.innerHTML = items.map(obj => {
                if (kind === 'tourists') {
                    return `<div class="item">
                        <div class="item-header">${obj.tourist_id}</div>
                        <div class="item-details">Budget: $${obj.budget} | Preferences: ${obj.preferences.join(', ')} | Windows: ${obj.availability.length}</div>
                    </div>`;
                } else {
                    return `<div class="item">
                        <div class="item-header">${obj.guide_id}</div>
                        <div class="item-details">Rate: $${obj.hourly_rate}/hr | Categories: ${obj.categories.join(', ')} | Max: ${obj.max_group_size}</div>
                    </div>`;
                }
            }).join('');
        }

        function updateTouristsList(tourists) {
            if (Array.isArray(tourists)) {
                tourists.forEach(t => { if (t && t.tourist_id) touristsState.set(t.tourist_id, t); });
            } else if (tourists && tourists.tourist_id) {
                touristsState.set(tourists.tourist_id, tourists);
            }
            renderCollection('tourists-list', touristsState, 'tourists');
        }

        function updateGuidesList(guides) {
            if (Array.isArray(guides)) {
                guides.forEach(g => { if (g && g.guide_id) guidesState.set(g.guide_id, g); });
            } else if (guides && guides.guide_id) {
                guidesState.set(guides.guide_id, guides);
            }
            renderCollection('guides-list', guidesState, 'guides');
        }

        function updateAssignmentsList(assignments) {
            const container = document.getElementById('assignments-list');
            if (!assignments || assignments.length === 0) {
                container.innerHTML = '<div class="item">No assignments yet</div>';
                return;
            }

            container.innerHTML = assignments.map(assignment => `
                <div class="item assignment">
                    <div class="item-header">
                        ${assignment.tourist_id} ↔ ${assignment.guide_id}
                    </div>
                    <div class="item-details">
                        Cost: $${assignment.total_cost.toFixed(0)} |
                        Categories: ${assignment.categories.join(', ')} |
                        Duration: ${formatTimeWindow(assignment.time_window)}
                    </div>
                </div>
            `).join('');
        }

        function formatTimeWindow(window) {
            const start = new Date(window.start);
            const end = new Date(window.end);
            const duration = Math.round((end - start) / (1000 * 60));
            return `${duration}min`;
        }
    </script>
</body>
</html>
"""



@click.command()
@click.option("--host", default="localhost", help="Server host")
@click.option("--port", default=10001, type=int, help="Server port")
@click.option("--a2a-port", default=10002, type=int, help="A2A agent port")
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.option("--transport", default="http", type=click.Choice(["http", "slim"]), help="Transport protocol")
@click.option("--slim-endpoint", default=None, help="SLIM node endpoint (default: from env or localhost:46357)")
@click.option("--slim-local-id", default=None, help="SLIM local agent ID")
def main(host: str, port: int, a2a_port: int, debug: bool, transport: str, slim_endpoint: str, slim_local_id: str):
    """Start the UI Agent with both web dashboard and A2A capabilities.

    Previous implementation attempted to run two uvicorn servers concurrently via
    asyncio.gather. In certain environments one server would start while the other
    silently failed (resulting in ERR_CONNECTION_REFUSED for the web dashboard).

    This revised launcher:
    1. Performs port auto-retry (increment) when a requested port is busy.
    2. Starts the web dashboard in a background thread using uvicorn.run (its own loop).
    3. Runs the A2A server in the main asyncio loop.
    4. Provides clear logging of the final bound ports.
    """
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Resolve / auto-increment ports if occupied
    original_web_port = port
    original_a2a_port = a2a_port
    port = find_available_port(host, port, label="web", max_increment=10)
    a2a_port = find_available_port(host, a2a_port, label="a2a", max_increment=10)

    if port != original_web_port:
        logger.warning(f"[UI Agent] Requested web port {original_web_port} busy, using {port}")
    if a2a_port != original_a2a_port:
        logger.warning(f"[UI Agent] Requested A2A port {original_a2a_port} busy, using {a2a_port}")

    logger.info(f"[UI Agent] Starting web dashboard on {host}:{port}")
    logger.info(f"[UI Agent] Starting A2A agent on {host}:{a2a_port}")
    logger.info(f"[UI Agent] Dashboard available at: http://{host}:{port}/")
    logger.info("[UI Agent] Health endpoint: /health (will report status: ok)")

    # Persist final ports so other processes (scheduler) can discover actual A2A port if it auto-incremented
    try:
        ports_file = Path(__file__).resolve().parent.parent / "ui_agent_ports.json"
        ports_file.write_text(json.dumps({"host": host, "web_port": port, "a2a_port": a2a_port}, indent=2))
        logger.info(f"[UI Agent] Wrote ports file: {ports_file}")
    except Exception as e:
        logger.warning(f"[UI Agent] Failed to write ports file: {e}")

    # Launch web server in thread so uvicorn's internal loop does not conflict
    def _start_web():
        try:
            uvicorn.run(web_app, host=host, port=port, log_level="debug" if debug else "info")
        except Exception as e:
            logger.error(f"[UI Agent] Web server failed: {e}")
    web_thread = Thread(target=_start_web, name="ui-web-thread", daemon=True)
    web_thread.start()
    logger.info("[UI Agent] Web server thread started")

    # Run A2A server in main loop (blocking until shutdown)
    try:
        asyncio.run(start_a2a_server(host, a2a_port, transport, slim_endpoint, slim_local_id))
    except KeyboardInterrupt:
        logger.info("[UI Agent] Shutdown requested (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"[UI Agent] A2A server error: {e}")

    logger.info("[UI Agent] Exiting main process")


async def start_a2a_server(host: str, port: int, transport: str = "http", slim_endpoint: str = None, slim_local_id: str = None):
    """Start the A2A agent server (with port retry already performed in main)."""
    skill = AgentSkill(
        id="real_time_dashboard",
        name="Real-time System Dashboard",
        description="Provides real-time web dashboard for multi-agent tourist scheduling system",
        tags=["dashboard", "ui", "monitoring", "real-time"],
        examples=[
            "Monitor tourist requests and guide availability",
            "Track assignment success rates and system metrics",
        ],
    )

    agent_card = AgentCard(
        name="UI Agent",
        description="Real-time web dashboard for tourist scheduling system monitoring",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=UIAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    if transport == "slim":
        # Use SLIM transport
        try:
            from core.slim_transport import SLIMConfig, create_slim_server
        except ImportError:
            logger.error("[UI Agent] SLIM transport requested but slima2a not installed")
            logger.error("[UI Agent] Install with: uv pip install slima2a")
            return

        # Set global transport mode so message tracking is correct
        global _transport_mode
        _transport_mode = TransportMode.SLIM

        # Resolve SLIM configuration
        import os
        actual_endpoint = slim_endpoint or os.environ.get("SLIM_ENDPOINT", "http://localhost:46357")
        actual_local_id = slim_local_id or os.environ.get("SLIM_LOCAL_ID", "agntcy/tourist_scheduling/ui-agent")
        shared_secret = os.environ.get("SLIM_SHARED_SECRET", "tourist-scheduling-demo-secret-32")
        tls_insecure = os.environ.get("SLIM_TLS_INSECURE", "true").lower() == "true"

        logger.info(f"[UI Agent] SLIM endpoint: {actual_endpoint}")
        logger.info(f"[UI Agent] SLIM local ID: {actual_local_id}")
        logger.info("[UI Agent] Starting SLIM transport server...")

        config = SLIMConfig(
            endpoint=actual_endpoint,
            local_id=actual_local_id,
            shared_secret=shared_secret,
            tls_insecure=tls_insecure,
        )

        start_server = create_slim_server(config, agent_card, request_handler)
        # start_server() returns (server, local_app, server_task) tuple
        server, local_app, server_task = await start_server()
        logger.info("[UI Agent] SLIM A2A server running, awaiting messages...")

        # Wait for server task - it has internal resilience so we just await it
        try:
            await server_task
        except asyncio.CancelledError:
            logger.info("[UI Agent] SLIM A2A server cancelled")
        except Exception as e:
            logger.error(f"[UI Agent] SLIM A2A server exited with error: {e}")
        finally:
            logger.info("[UI Agent] SLIM A2A server exited")
    else:
        # Use HTTP transport
        a2a_app = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )

        config = uvicorn.Config(a2a_app.build(), host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


def find_available_port(host: str, desired_port: int, label: str, max_increment: int = 5) -> int:
    """Return an available port, incrementing if the desired one is busy.

    This avoids hard failures when the UI agent is relaunched while previous A2A
    sockets are still bound. We attempt up to max_increment increments.
    """
    for offset in range(0, max_increment + 1):
        candidate = desired_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, candidate))
                # Successfully bound; release and return
                logger.debug(f"[UI Agent] Port check success for {label} port {candidate}")
                return candidate
            except OSError:
                logger.debug(f"[UI Agent] Port {candidate} busy for {label}")
                continue
    raise RuntimeError(f"[UI Agent] No available {label} port found starting at {desired_port}")


if __name__ == "__main__":
    main()