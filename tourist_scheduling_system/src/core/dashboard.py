#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Web Dashboard for ADK UI Agent

Provides a real-time HTML dashboard with WebSocket support for monitoring
the tourist scheduling system. This is extracted from the original UI agent
to be used with ADK agents.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Set

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket
from starlette.requests import Request

# Set up file logging
try:
    from core.logging_config import setup_agent_logging
    logger = setup_agent_logging("adk_dashboard")
except ImportError:
    logger = logging.getLogger(__name__)

# Load HTML template from external file
_TEMPLATE_DIR = Path(__file__).parent / "templates"
_HTML_TEMPLATE_PATH = _TEMPLATE_DIR / "dashboard.html"
_HTML_TEMPLATE_CACHE = None


def _load_html_template() -> str:
    """Load the HTML template from file, with caching."""
    global _HTML_TEMPLATE_CACHE
    if _HTML_TEMPLATE_CACHE is None:
        if _HTML_TEMPLATE_PATH.exists():
            _HTML_TEMPLATE_CACHE = _HTML_TEMPLATE_PATH.read_text(encoding="utf-8")
            logger.info(f"[ADK UI] Loaded HTML template from {_HTML_TEMPLATE_PATH}")
        else:
            logger.error(f"[ADK UI] HTML template not found: {_HTML_TEMPLATE_PATH}")
            _HTML_TEMPLATE_CACHE = "<html><body><h1>Dashboard template not found</h1></body></html>"
    return _HTML_TEMPLATE_CACHE


def reload_html_template():
    """Force reload of the HTML template (useful for development)."""
    global _HTML_TEMPLATE_CACHE
    _HTML_TEMPLATE_CACHE = None
    return _load_html_template()

# WebSocket clients for real-time updates
_ws_clients: Set[WebSocket] = set()

# Reference to dashboard state (will be set from ui_agent)
_dashboard_state = None
_transport_mode = "http"


def set_dashboard_state(state):
    """Set the dashboard state reference."""
    global _dashboard_state
    _dashboard_state = state


def set_transport_mode(mode: str):
    """Set the transport mode for display."""
    global _transport_mode
    _transport_mode = mode


async def broadcast_to_clients(message: dict):
    """Broadcast a message to all connected WebSocket clients."""
    logger.info(f"[ADK UI] Broadcasting to {len(_ws_clients)} clients: {message.get('type', 'unknown')}")

    if not _ws_clients:
        logger.warning("[ADK UI] No WebSocket clients connected, broadcast skipped")
        return

    data = json.dumps(message)
    disconnected = set()
    sent_count = 0

    for client in _ws_clients:
        try:
            await client.send_text(data)
            sent_count += 1
        except Exception as e:
            logger.warning(f"[ADK UI] Failed to send to client: {e}")
            disconnected.add(client)

    # Remove disconnected clients
    _ws_clients.difference_update(disconnected)
    logger.info(f"[ADK UI] Broadcast complete: sent to {sent_count}, disconnected {len(disconnected)}")


async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections for real-time updates."""
    await websocket.accept()
    _ws_clients.add(websocket)
    logger.info(f"[ADK UI] WebSocket client connected, total clients: {len(_ws_clients)}")

    try:
        # Send initial state
        if _dashboard_state:
            initial_state = {
                "type": "initial_state",
                "data": {
                    **_dashboard_state.to_dict(),
                    "transport_mode": _transport_mode,
                    "active_agents": [],  # Will be populated as agents connect
                }
            }
            await websocket.send_text(json.dumps(initial_state))

        # Keep connection alive and receive messages
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Handle ping/pong or other messages
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send keepalive
                try:
                    await websocket.send_text(json.dumps({"type": "keepalive"}))
                except Exception:
                    break
    except Exception as e:
        logger.debug(f"[ADK UI] WebSocket error: {e}")
    finally:
        _ws_clients.discard(websocket)
        logger.info(f"[ADK UI] WebSocket client disconnected, total clients: {len(_ws_clients)}")


async def health_endpoint(request):
    """Health check endpoint."""
    return JSONResponse({"status": "ok", "agent": "adk_ui_dashboard"})


async def api_state_endpoint(request):
    """REST endpoint to get current system state."""
    if _dashboard_state:
        return JSONResponse(_dashboard_state.to_dict())
    return JSONResponse({"error": "No state available"})


async def api_update_endpoint(request):
    """
    REST endpoint for receiving updates from the scheduler.

    This endpoint receives JSON updates and broadcasts them to WebSocket clients.
    It also updates the dashboard state if available.
    """
    try:
        body = await request.json()
        logger.info(f"[ADK UI] Received update: {body.get('type', 'unknown')}")
        logger.debug(f"[ADK UI] Update data: {body}")

        # Update dashboard state if available
        if _dashboard_state:
            update_type = body.get("type")
            if update_type == "tourist_request":
                tourist_id = body.get("tourist_id")
                if tourist_id:
                    _dashboard_state.tourist_requests[tourist_id] = body
                    logger.info(f"[ADK UI] Added tourist: {tourist_id}, total: {len(_dashboard_state.tourist_requests)}")
                _dashboard_state.update_metrics()
            elif update_type == "guide_offer":
                guide_id = body.get("guide_id")
                if guide_id:
                    _dashboard_state.guide_offers[guide_id] = body
                    logger.info(f"[ADK UI] Added guide: {guide_id}, total: {len(_dashboard_state.guide_offers)}")
                _dashboard_state.update_metrics()
            elif update_type == "assignment":
                _dashboard_state.assignments.append(body)
                logger.info(f"[ADK UI] Added assignment, total: {len(_dashboard_state.assignments)}")
                _dashboard_state.update_metrics()
            elif update_type == "metrics":
                _dashboard_state.metrics.total_tourists = body.get("total_tourists", 0)
                _dashboard_state.metrics.total_guides = body.get("total_guides", 0)
                _dashboard_state.metrics.total_assignments = body.get("total_assignments", 0)
                _dashboard_state.metrics.satisfied_tourists = body.get("satisfied_tourists", 0)
                _dashboard_state.metrics.guide_utilization = body.get("guide_utilization", 0)
                _dashboard_state.metrics.avg_assignment_cost = body.get("avg_assignment_cost", 0)
            elif update_type == "communication_event":
                # Store communication event
                if not hasattr(_dashboard_state, 'communication_events'):
                    _dashboard_state.communication_events = []
                _dashboard_state.communication_events.append(body)
                # Keep only last 50 events
                if len(_dashboard_state.communication_events) > 50:
                    _dashboard_state.communication_events = _dashboard_state.communication_events[-50:]
                logger.info(f"[ADK UI] Added communication event: {body.get('source_agent')} -> {body.get('target_agent')}")

        # Broadcast to WebSocket clients
        await broadcast_to_clients(body)

        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"[ADK UI] Error processing update: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def dashboard_endpoint(request):
    """Serve the dashboard HTML."""
    return HTMLResponse(_load_html_template())


async def chat_endpoint(request):
    """Handle chat requests from GenUI frontend."""
    try:
        data = await request.json()
        message = data.get("message", "")

        # Get the UI agent
        from src.agents.ui_agent import get_ui_agent
        agent = get_ui_agent()

        # Run the agent
        response_text = agent.run(message)

        text_part = response_text
        a2ui_part = []

        if "---a2ui_JSON---" in response_text:
            parts = response_text.split("---a2ui_JSON---")
            text_part = parts[0].strip()
            try:
                a2ui_part = json.loads(parts[1].strip())
            except json.JSONDecodeError:
                logger.error("[ADK UI] Failed to parse A2UI JSON")

        return JSONResponse({
            "text": text_part,
            "a2ui": a2ui_part
        })
    except Exception as e:
        logger.error(f"[ADK UI] Chat error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


def create_dashboard_app():
    """Create the Starlette dashboard application."""
    routes = [
        Route("/", dashboard_endpoint),
        Route("/health", health_endpoint),
        Route("/api/state", api_state_endpoint),
        Route("/api/update", api_update_endpoint, methods=["POST"]),
        Route("/api/chat", chat_endpoint, methods=["POST"]),
        WebSocketRoute("/ws", websocket_endpoint),
    ]
    return Starlette(routes=routes)
