#!/usr/bin/env python3
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

from a2a_summit_demo.core.messages import Assignment, GuideOffer, TouristRequest, ScheduleProposal

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
                updateTourists(message.data);
            } else if (message.type === 'guide_offer') {
                updateGuides(message.data);
            } else if (message.type === 'schedule_proposal') {
                updateAssignments(message.data.assignments);
            } else if (message.type === 'metrics') {
                updateMetrics(message.data);
            }
        };

        function updateFullState(state) {
            updateMetrics(state.metrics);
            updateTouristsList(state.tourist_requests);
            updateGuidesList(state.guide_offers);
            updateAssignmentsList(state.assignments);
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

        function updateTouristsList(tourists) {
            const container = document.getElementById('tourists-list');
            if (!tourists || tourists.length === 0) {
                container.innerHTML = '<div class="item">No tourists yet</div>';
                return;
            }

            container.innerHTML = tourists.map(tourist => `
                <div class="item">
                    <div class="item-header">${tourist.tourist_id}</div>
                    <div class="item-details">
                        Budget: $${tourist.budget} |
                        Preferences: ${tourist.preferences.join(', ')} |
                        Windows: ${tourist.availability.length}
                    </div>
                </div>
            `).join('');
        }

        function updateGuidesList(guides) {
            const container = document.getElementById('guides-list');
            if (!guides || guides.length === 0) {
                container.innerHTML = '<div class="item">No guides yet</div>';
                return;
            }

            container.innerHTML = guides.map(guide => `
                <div class="item">
                    <div class="item-header">${guide.guide_id}</div>
                    <div class="item-details">
                        Rate: $${guide.hourly_rate}/hour |
                        Categories: ${guide.categories.join(', ')} |
                        Max Group: ${guide.max_group_size}
                    </div>
                </div>
            `).join('');
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
    """Start the UI Agent with both web dashboard and A2A capabilities"""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info(f"[UI Agent] Starting web dashboard on {host}:{port}")
    logger.info(f"[UI Agent] Starting A2A agent on {host}:{a2a_port}")
    logger.info(f"[UI Agent] Dashboard available at: http://{host}:{port}/")

    async def run_both_servers():
        """Run both the web dashboard and A2A agent"""
        import asyncio

        # Start A2A server in background
        a2a_server_task = asyncio.create_task(start_a2a_server(host, a2a_port))

        # Start web server in background
        web_server_task = asyncio.create_task(start_web_server(host, port, debug))

        # Wait for both
        await asyncio.gather(a2a_server_task, web_server_task)

    asyncio.run(run_both_servers())


async def start_a2a_server(host: str, port: int):
    """Start the A2A agent server"""
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


async def start_web_server(host: str, port: int, debug: bool):
    """Start the web dashboard server"""
    config = uvicorn.Config(
        web_app,
        host=host,
        port=port,
        log_level="debug" if debug else "info"
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    main()