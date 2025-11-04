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

This agent acts as a bridge between the multi-agent system and human operators,
providing visibility into the scheduling process in real-time.
"""

import json
import logging
import asyncio
import socket
from threading import Thread
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Set, Optional

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


@dataclass
class SystemMetrics:
    """Real-time system metrics for dashboard"""
    total_tourists: int = 0
    total_guides: int = 0
    total_assignments: int = 0
    satisfied_tourists: int = 0
    guide_utilization: float = 0.0
    avg_assignment_cost: float = 0.0
    last_updated: Optional[datetime] = None

    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()


@dataclass
class UIState:
    """Centralized UI state tracking all system data"""
    tourist_requests: Dict[str, TouristRequest]
    guide_offers: Dict[str, GuideOffer]
    assignments: List[Assignment]
    schedule_proposals: Dict[str, ScheduleProposal]
    metrics: SystemMetrics
    connected_clients: Set[WebSocket]

    def __init__(self):
        self.tourist_requests = {}
        self.guide_offers = {}
        self.assignments = []
        self.schedule_proposals = {}
        self.metrics = SystemMetrics()
        self.connected_clients = set()

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
        """Broadcast updates to all connected WebSocket clients"""
        if not self.connected_clients:
            return

        message = {
            "type": update_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        message_str = json.dumps(message, default=str)

        # Send to all connected clients
        disconnected = set()
        for client in self.connected_clients:
            try:
                await client.send_text(message_str)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                disconnected.add(client)

        # Remove disconnected clients
        self.connected_clients -= disconnected

    def to_dict(self) -> dict:
        """Convert state to dictionary for JSON serialization"""
        return {
            "tourist_requests": [req.to_dict() for req in self.tourist_requests.values()],
            "guide_offers": [offer.to_dict() for offer in self.guide_offers.values()],
            "assignments": [asdict(assignment) for assignment in self.assignments],
            "schedule_proposals": {pid: prop.to_dict() for pid, prop in self.schedule_proposals.items()},
            "metrics": asdict(self.metrics)
        }


# Global UI state
ui_state = UIState()


class UIAgentExecutor(AgentExecutor):
    """Processes messages from other agents and updates UI state"""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Process incoming A2A messages and update UI state"""
        logger.info(f"[UI Agent] Received task: {context.task_id}")

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

            if message_type == "TouristRequest":
                request = TouristRequest.from_dict(data)
                ui_state.tourist_requests[request.tourist_id] = request
                ui_state.update_metrics()

                await ui_state.broadcast_update("tourist_request", request.to_dict())
                logger.info(f"[UI Agent] Updated tourist request from {request.tourist_id}")

            elif message_type == "GuideOffer":
                offer = GuideOffer.from_dict(data)
                ui_state.guide_offers[offer.guide_id] = offer
                ui_state.update_metrics()

                await ui_state.broadcast_update("guide_offer", offer.to_dict())
                logger.info(f"[UI Agent] Updated guide offer from {offer.guide_id}")

            elif message_type == "ScheduleProposal":
                proposal = ScheduleProposal.from_dict(data)
                ui_state.schedule_proposals[proposal.proposal_id] = proposal
                ui_state.assignments = proposal.assignments
                ui_state.update_metrics()

                await ui_state.broadcast_update("schedule_proposal", proposal.to_dict())
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

    try:
        # Send initial state
        initial_state = ui_state.to_dict()
        await websocket.send_text(json.dumps({
            "type": "initial_state",
            "data": initial_state,
            "timestamp": datetime.now().isoformat()
        }, default=str))

        # Keep connection alive
        while True:
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        ui_state.connected_clients.discard(websocket)
        logger.info("[UI Agent] WebSocket client disconnected")
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
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
        }
        .header {
            background: #2563eb;
            color: white;
            padding: 1rem 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .header h1 {
            font-size: 1.5rem;
            font-weight: 600;
        }
        .main {
            padding: 2rem;
            max-width: 1400px;
            margin: 0 auto;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .metric-card {
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            text-align: center;
        }
        .metric-value {
            font-size: 2rem;
            font-weight: bold;
            color: #2563eb;
            margin-bottom: 0.5rem;
        }
        .metric-label {
            color: #666;
            font-size: 0.9rem;
        }
        .content-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }
        .section {
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .section-header {
            background: #f8fafc;
            padding: 1rem 1.5rem;
            border-bottom: 1px solid #e2e8f0;
        }
        .section-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #374151;
        }
        .section-content {
            padding: 1rem;
            max-height: 400px;
            overflow-y: auto;
        }
        .item {
            padding: 0.75rem;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            margin-bottom: 0.75rem;
            background: #fafafa;
        }
        .item:last-child {
            margin-bottom: 0;
        }
        .item-header {
            font-weight: 600;
            color: #1f2937;
            margin-bottom: 0.25rem;
        }
        .item-details {
            font-size: 0.9rem;
            color: #6b7280;
        }
        .assignments-section {
            grid-column: 1 / -1;
        }
        .assignment {
            background: #ecfdf5;
            border: 1px solid #a7f3d0;
        }
        .status {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
        }
        .status-online {
            background: #dcfce7;
            color: #166534;
        }
        .status-updated {
            background: #dbeafe;
            color: #1d4ed8;
        }
        .timestamp {
            font-size: 0.8rem;
            color: #9ca3af;
            margin-top: 0.5rem;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🗺️ Tourist Scheduling Dashboard</h1>
        <div id="connection-status" class="status status-online">Connected</div>
    </div>

    <div class="main">
        <!-- Metrics -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value" id="total-tourists">0</div>
                <div class="metric-label">Total Tourists</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="total-guides">0</div>
                <div class="metric-label">Available Guides</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="total-assignments">0</div>
                <div class="metric-label">Active Assignments</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="satisfaction-rate">0%</div>
                <div class="metric-label">Satisfaction Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="guide-utilization">0%</div>
                <div class="metric-label">Guide Utilization</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="avg-cost">$0</div>
                <div class="metric-label">Avg Assignment Cost</div>
            </div>
        </div>

        <!-- Content Grid -->
        <div class="content-grid">
            <!-- Tourists -->
            <div class="section">
                <div class="section-header">
                    <div class="section-title">Tourist Requests</div>
                </div>
                <div class="section-content" id="tourists-list">
                    <div class="item">No tourists yet</div>
                </div>
            </div>

            <!-- Guides -->
            <div class="section">
                <div class="section-header">
                    <div class="section-title">Guide Offers</div>
                </div>
                <div class="section-content" id="guides-list">
                    <div class="item">No guides yet</div>
                </div>
            </div>
        </div>

        <!-- Assignments -->
        <div class="content-grid">
            <div class="section assignments-section">
                <div class="section-header">
                    <div class="section-title">Current Assignments</div>
                </div>
                <div class="section-content" id="assignments-list">
                    <div class="item">No assignments yet</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // WebSocket connection
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        const statusEl = document.getElementById('connection-status');

        // Connection status
        ws.onopen = () => {
            statusEl.textContent = 'Connected';
            statusEl.className = 'status status-online';
        };

        ws.onclose = () => {
            statusEl.textContent = 'Disconnected';
            statusEl.className = 'status status-offline';
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            statusEl.textContent = 'Error';
            statusEl.className = 'status status-offline';
        };

        // Message handling
        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);

            if (message.type === 'initial_state') {
                updateFullState(message.data);
            } else if (message.type === 'tourist_request') {
                // Single tourist request object
                updateTouristsList([message.data]);
                updateMetricsIncremental('tourist');
            } else if (message.type === 'guide_offer') {
                // Single guide offer object
                updateGuidesList([message.data]);
                updateMetricsIncremental('guide');
            } else if (message.type === 'schedule_proposal') {
                // Proposal contains assignments array; update assignments list and metrics
                updateAssignmentsList(message.data.assignments || []);
                updateMetrics(message.data.metrics || document.cachedMetrics || {});
            } else if (message.type === 'metrics') {
                updateMetrics(message.data);
                document.cachedMetrics = message.data; // cache latest metrics
            }
        };

        function updateFullState(state) {
            updateMetrics(state.metrics || {});
            updateTouristsList(state.tourist_requests || []);
            updateGuidesList(state.guide_offers || []);
            updateAssignmentsList(state.assignments || []);
            document.cachedMetrics = state.metrics;
        }

        function updateMetricsIncremental(kind) {
            // Lightweight recalculation from DOM counts when individual items arrive
            const tourists = document.querySelectorAll('#tourists-list .item-header').length;
            const guides = document.querySelectorAll('#guides-list .item-header').length;
            const assignments = document.querySelectorAll('#assignments-list .assignment').length;
            const metrics = {
                total_tourists: tourists,
                total_guides: guides,
                total_assignments: assignments,
                satisfied_tourists: assignments, // approximation
                guide_utilization: guides ? (assignments / guides) : 0,
                avg_assignment_cost: document.cachedMetrics ? document.cachedMetrics.avg_assignment_cost : 0
            };
            updateMetrics(metrics);
        }

        function updateMetrics(metrics) {
            document.getElementById('total-tourists').textContent = metrics.total_tourists;
            document.getElementById('total-guides').textContent = metrics.total_guides;
            document.getElementById('total-assignments').textContent = metrics.total_assignments;

            const satisfactionRate = metrics.total_tourists > 0
                ? Math.round((metrics.satisfied_tourists / metrics.total_tourists) * 100)
                : 0;
            document.getElementById('satisfaction-rate').textContent = satisfactionRate + '%';

            document.getElementById('guide-utilization').textContent =
                Math.round(metrics.guide_utilization * 100) + '%';

            document.getElementById('avg-cost').textContent =
                '$' + metrics.avg_assignment_cost.toFixed(0);
        }

        // Maintain maps so incremental updates append/replace individual items instead of wiping entire list.
        const touristsState = new Map();
        const guidesState = new Map();

        function renderCollection(containerId, stateMap, kind) {
            const container = document.getElementById(containerId);
            if (stateMap.size === 0) {
                container.innerHTML = `<div class="item">No ${kind} yet</div>`;
                return;
            }
            const items = Array.from(stateMap.values()).sort((a,b) => (a[`${kind === 'tourists' ? 'tourist_id' : 'guide_id'}`] || '').localeCompare(b[`${kind === 'tourists' ? 'tourist_id' : 'guide_id'}`] || ''));
            container.innerHTML = items.map(obj => {
                if (kind === 'tourists') {
                    return `<div class="item">
                        <div class="item-header">${obj.tourist_id}</div>
                        <div class="item-details">Budget: $${obj.budget} | Preferences: ${obj.preferences.join(', ')} | Windows: ${obj.availability.length}</div>
                    </div>`;
                } else {
                    return `<div class="item">
                        <div class="item-header">${obj.guide_id}</div>
                        <div class="item-details">Rate: $${obj.hourly_rate}/hour | Categories: ${obj.categories.join(', ')} | Max Group: ${obj.max_group_size}</div>
                    </div>`;
                }
            }).join('');
        }

        function updateTouristsList(tourists) {
            // tourists can be full list (initial) or single-item array
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
            const duration = Math.round((end - start) / (1000 * 60)); // minutes
            return `${duration}min (${start.toLocaleTimeString()} - ${end.toLocaleTimeString()})`;
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
def main(host: str, port: int, a2a_port: int, debug: bool):
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
        asyncio.run(start_a2a_server(host, a2a_port))
    except KeyboardInterrupt:
        logger.info("[UI Agent] Shutdown requested (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"[UI Agent] A2A server error: {e}")

    logger.info("[UI Agent] Exiting main process")


async def start_a2a_server(host: str, port: int):
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