#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Web Dashboard & A2UI Backend for ADK UI Agent

Provides a real-time dashboard backend with WebSocket support for monitoring
the tourist scheduling system. This service:
1. Serves as the backend for the Flutter-based GenUI frontend.
2. Implements the A2UI protocol to render native widgets (Calendar, Tables) on the client.
3. Manages system state (assignments, metrics, logs) and exposes it via REST APIs.
4. Handles chat interactions using Google ADK runners.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Set

from google.adk.runners import InMemoryRunner
from google.adk.sessions import Session
from google.genai import types
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
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
    logger.info(f"[ADK UI] set_dashboard_state called. State object: {id(state)}")

    # Also update the state in the imported ui_agent module
    # to ensure tools use the correct state when called by the agent
    try:
        from src.agents import ui_agent
        ui_agent._dashboard_state = state
        logger.info(f"[ADK UI] Synced dashboard state to src.agents.ui_agent. Module object: {id(ui_agent._dashboard_state)}")
    except ImportError:
        logger.warning("[ADK UI] Could not sync state to ui_agent module")


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


import time

# Global runner instance
_runner = None
_current_session_id = "genui_session"

def get_runner():
    """Get or create the global InMemoryRunner instance."""
    global _runner, _current_session_id
    if _runner is None:
        from src.agents.ui_agent import get_ui_agent
        agent = get_ui_agent()

        # Initialize runner with app_name matching the agent package
        _runner = InMemoryRunner(agent=agent, app_name="agents")

        # Always reset session on startup to avoid stale state from previous runs
        try:
            if hasattr(_runner, "session_service"):
                # Use a fresh session ID on startup
                _current_session_id = f"genui_session_{int(time.time())}"

                _runner.session_service.create_session_sync(
                    app_name="agents",
                    user_id="genui_user",
                    session_id=_current_session_id
                )
                logger.info(f"[ADK UI] Created fresh global session: {_current_session_id}")
            else:
                logger.warning("[ADK UI] Runner has no session_service attribute")
        except Exception as e:
            logger.error(f"[ADK UI] Error initializing session: {e}")

    return _runner


def reset_session():
    """Reset the genui session to clear any stuck state."""
    global _runner, _current_session_id
    if _runner and hasattr(_runner, "session_service"):
        try:
            # Generate new session ID
            old_session = _current_session_id
            _current_session_id = f"genui_session_{int(time.time())}"

            logger.info(f"[ADK UI] Abandoning stuck session: {old_session}")

            # Create new session
            _runner.session_service.create_session_sync(
                app_name="agents",
                user_id="genui_user",
                session_id=_current_session_id
            )
            logger.info(f"[ADK UI] Created new session: {_current_session_id}")
        except Exception as e:
            logger.error(f"[ADK UI] Error resetting session: {e}")


async def chat_endpoint(request):
    """Handle chat requests from GenUI frontend."""
    try:
        data = await request.json()
        message = data.get("message", "")
        print(f"DEBUG: Chat request received: {message}")
        logger.info(f"[ADK UI] Chat request received: {message}")

        # Get the global runner
        runner = get_runner()
        response_text = ""

        # Create content object
        user_content = types.Content(parts=[types.Part(text=message)])

        # Run async
        print(f"DEBUG: Starting runner execution for session {_current_session_id}")
        logger.info(f"[ADK UI] Starting runner execution for session {_current_session_id}")
        event_count = 0

        # Check if there are pending tool calls in the session history
        # This is a workaround for the "tool_calls must be followed by tool messages" error
        # If the previous run was interrupted or failed, we might have a dangling tool call
        try:
            session = runner.session_service.get_session_sync(session_id=_current_session_id)
            if session and session.events:
                last_event = session.events[-1]
                # If last event was a model turn with tool calls, we might need to clear it or inject a dummy response
                # For now, let's just log it
                logger.info(f"[ADK UI] Last session event: {last_event}")
        except Exception as e:
            logger.warning(f"[ADK UI] Could not inspect session history: {e}")

        try:
            async for event in runner.run_async(
                user_id="genui_user",
                session_id=_current_session_id,
                new_message=user_content
            ):
                event_count += 1
                logger.info(f"[ADK UI] Received event: {type(event)}")
                # Check for model response
                if event.content and event.content.parts:
                    logger.info(f"[ADK UI] Event has content with {len(event.content.parts)} parts")
                    for part in event.content.parts:
                        if part.text:
                            logger.info(f"[ADK UI] Part text: {part.text[:50]}...")
                            response_text += part.text

                if event.error_message:
                    logger.error(f"[ADK UI] Event error: {event.error_message}")
        except Exception as e:
            print(f"DEBUG: Exception during runner execution: {e}")
            if "tool_calls" in str(e) and "must be followed by tool messages" in str(e):
                print(f"DEBUG: Detected stuck tool call state. Resetting session.")
                logger.warning(f"[ADK UI] Detected stuck tool call state: {e}. Resetting session.")
                reset_session()
                return JSONResponse({"text": "I encountered an error with my previous state. I have reset my memory. Please ask your question again.", "a2ui": []})

            if "timeout" in str(e).lower():
                 logger.error(f"[ADK UI] LLM request timed out: {e}")
                 return JSONResponse({"text": "The request to the AI model timed out. Please check your network connection or proxy settings.", "a2ui": []})

            raise e

        print(f"DEBUG: Runner execution finished. Event count: {event_count}. Response text length: {len(response_text)}")
        logger.info(f"[ADK UI] Runner execution finished. Event count: {event_count}. Response text length: {len(response_text)}")

        if not response_text:
            response_text = "I processed your request but have no response. Please check the logs."

        # Generate A2UI messages based on context
        a2ui_messages = []

        # Heuristic: If the user asks for status or assignments, include the table
        lower_msg = message.lower()

        # Normalize assignments for A2UI consistency
        normalized_assignments = []
        print(f"DEBUG: Dashboard state assignments count: {len(_dashboard_state.assignments) if _dashboard_state and _dashboard_state.assignments else 0}")

        if _dashboard_state and _dashboard_state.assignments:
            for a in _dashboard_state.assignments:
                # Create a clean object matching the schema exactly to avoid validation errors
                # with extra fields like 'type' or 'time_window'
                window_data = a.get("window") or a.get("time_window")

                # Ensure window data has string values for start/end if they are None
                # Strictly filter to only start/end to match schema
                clean_window = {"start": "", "end": ""}
                if window_data:
                    clean_window["start"] = str(window_data.get("start") or "")
                    clean_window["end"] = str(window_data.get("end") or "")

                clean_assignment = {
                    "tourist_id": str(a.get("tourist_id", "Unknown")),
                    "guide_id": str(a.get("guide_id", "Unknown")),
                    "categories": [str(c) for c in a.get("categories", [])],
                    "total_cost": float(a.get("total_cost", 0)),
                    "window": clean_window
                }
                normalized_assignments.append(clean_assignment)

        if "visualize" in lower_msg or "schedule" in lower_msg or "calendar" in lower_msg:
            print(f"DEBUG: User requested visualization. Sending widget with {len(normalized_assignments)} assignments.")

            # DEBUG: Inject mock data if empty to verify UI rendering
            final_assignments = normalized_assignments

            surface_id = f"scheduler-calendar-{int(time.time())}"
            component_id = f"calendar-{int(time.time())}"
            a2ui_messages.append({
                "surfaceUpdate": {
                    "surfaceId": surface_id,
                    "components": [
                        {
                            "id": component_id,
                            "component": {
                                "SchedulerCalendar": {
                                    "assignments": final_assignments
                                }
                            },
                            "catalogId": "custom"
                        }
                    ]
                }
            })
            a2ui_messages.append({
                "beginRendering": {
                    "surfaceId": surface_id,
                    "root": component_id,
                    "catalogId": "custom"
                }
            })

        if "status" in lower_msg or "assignment" in lower_msg or "who" in lower_msg:
            # Always show status table, even if empty
            surface_id = f"scheduler-status-{int(time.time())}"
            component_id = f"status-{int(time.time())}"
            a2ui_messages.append({
                "surfaceUpdate": {
                    "surfaceId": surface_id,
                    "components": [
                        {
                            "id": component_id,
                            "component": {
                                "SchedulerStatusTable": {
                                    "assignments": normalized_assignments
                                }
                            },
                            "catalogId": "custom"
                        }
                    ]
                }
            })
            a2ui_messages.append({
                "beginRendering": {
                    "surfaceId": surface_id,
                    "root": component_id,
                    "catalogId": "custom"
                }
            })

        return JSONResponse({
            "text": response_text,
            "a2ui": a2ui_messages
        })
    except Exception as e:
        print(f"DEBUG: Chat error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


def create_dashboard_app():
    """Create the Starlette dashboard application."""
    routes = [
        Route("/", dashboard_endpoint),
        Route("/health", health_endpoint),
        Route("/api/state", api_state_endpoint),
        Route("/api/update", api_update_endpoint, methods=["POST"]),
        Route("/api/chat", chat_endpoint, methods=["POST", "OPTIONS"]),
        WebSocketRoute("/ws", websocket_endpoint),
    ]

    middleware = [
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    ]

    return Starlette(routes=routes, middleware=middleware)
