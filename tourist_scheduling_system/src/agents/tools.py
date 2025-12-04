# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Tools for the ADK-based Scheduler Agent.

These tools implement the scheduling logic as callable functions that
the LLM agent can invoke. Each tool modifies the shared scheduler state
and returns structured responses.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING

import httpx

# Set up file logging
try:
    from core.logging_config import setup_agent_logging
    logger = setup_agent_logging("adk_tools")
except ImportError:
    logger = logging.getLogger(__name__)

# Set up tracing
try:
    from core.tracing import traced, create_span, add_span_event, set_span_attribute
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False
    # Create no-op decorator
    def traced(name=None, attributes=None):
        def decorator(func):
            return func
        return decorator

# Conditional import for type hints - allows running without ADK installed
if TYPE_CHECKING:
    from google.adk.tools.tool_context import ToolContext
else:
    # Create a placeholder for ToolContext when ADK is not installed
    ToolContext = Any

from .models import (
    TouristRequest,
    GuideOffer,
    Assignment,
    ScheduleProposal,
    SchedulerState,
    Window,
)

logger = logging.getLogger(__name__)

# Global state (in production, use state from ToolContext)
_scheduler_state = SchedulerState()

# UI Agent notification config
_ui_agent_port = 10021  # Default ADK UI port


def set_ui_agent_port(port: int):
    """Configure the UI agent port for notifications."""
    global _ui_agent_port
    _ui_agent_port = port


def _discover_ui_ports(default_port: int = 10021) -> int:
    """Discover UI agent A2A port from environment or ports file."""
    # Check environment variable first
    env_port = os.environ.get("UI_A2A_PORT")
    if env_port:
        return int(env_port)

    # Check ports file
    try:
        ports_file = Path(__file__).resolve().parent.parent.parent / "ui_agent_ports.json"
        if ports_file.exists():
            data = json.loads(ports_file.read_text())
            return int(data.get("a2a_port", default_port))
    except Exception as e:
        logger.debug(f"[ADK Scheduler] UI ports file read failed: {e}")

    return _ui_agent_port or default_port


async def _send_to_ui_agent_async(message_data: dict):
    """Send data to UI agent dashboard for updates (async version)."""
    port = _discover_ui_ports()
    # Use the dashboard's direct update API endpoint
    url = f"http://localhost:{port}/api/update"
    logger.info(f"[ADK Scheduler] Sending update to dashboard: {url}")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json=message_data)
        if response.status_code == 200:
            logger.info(f"[ADK Scheduler] ✅ Sent update to dashboard on port {port}: {message_data.get('type')}")
        else:
            logger.warning(f"[ADK Scheduler] Dashboard POST returned {response.status_code}")
    except Exception as e:
        logger.warning(f"[ADK Scheduler] Failed to send update to dashboard: {e}")


def send_to_ui_agent(message_data: dict):
    """Send data to UI agent for dashboard updates (sync wrapper)."""
    import threading

    def _send_sync():
        """Run the async send in a new event loop in a thread."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_send_to_ui_agent_async(message_data))
            finally:
                loop.close()
        except Exception as e:
            logger.warning(f"[ADK Scheduler] Thread send failed: {e}")

    # Run in a thread to avoid blocking and event loop issues
    thread = threading.Thread(target=_send_sync, daemon=True)
    thread.start()
    # Wait briefly to ensure the request is sent
    thread.join(timeout=2.0)


@traced("register_tourist_request")
def register_tourist_request(
    tourist_id: str,
    availability_start: str,
    availability_end: str,
    preferences: List[str],
    budget: float,
    tool_context: ToolContext,
) -> Dict[str, Any]:
    """
    Register a tourist's request for scheduling.

    This tool receives a tourist's availability, preferences, and budget,
    and adds them to the scheduling queue.

    Args:
        tourist_id: Unique identifier for the tourist
        availability_start: Start time in ISO format (e.g., "2025-06-01T09:00:00")
        availability_end: End time in ISO format (e.g., "2025-06-01T17:00:00")
        preferences: List of preferred categories (e.g., ["culture", "history"])
        budget: Maximum hourly budget in dollars
        tool_context: ADK tool context for state access

    Returns:
        Confirmation with registration details
    """
    try:
        # Parse availability
        window = Window(
            start=datetime.fromisoformat(availability_start),
            end=datetime.fromisoformat(availability_end),
        )

        request = TouristRequest(
            tourist_id=tourist_id,
            availability=[window],
            preferences=preferences,
            budget=budget,
        )

        # Add to state (check for duplicates)
        existing = next(
            (t for t in _scheduler_state.tourist_requests if t.tourist_id == tourist_id),
            None
        )
        if existing:
            _scheduler_state.tourist_requests.remove(existing)

        _scheduler_state.tourist_requests.append(request)

        logger.info(f"[Scheduler] Registered tourist request: {tourist_id}")

        # Notify UI agent
        send_to_ui_agent({
            "type": "tourist_request",
            "tourist_id": tourist_id,
            "preferences": preferences,
            "budget": budget,
            "availability": {
                "start": availability_start,
                "end": availability_end,
            }
        })

        return {
            "status": "registered",
            "tourist_id": tourist_id,
            "message": f"Tourist {tourist_id} registered with {len(preferences)} preferences and ${budget}/hr budget",
            "queue_position": len(_scheduler_state.tourist_requests),
        }

    except Exception as e:
        logger.error(f"[Scheduler] Failed to register tourist: {e}")
        return {
            "status": "error",
            "message": str(e),
        }


@traced("register_guide_offer")
def register_guide_offer(
    guide_id: str,
    categories: List[str],
    available_start: str,
    available_end: str,
    hourly_rate: float,
    max_group_size: int = 1,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Register a guide's availability and capabilities.

    This tool receives a guide's offer including their specialties,
    availability window, and rates.

    Args:
        guide_id: Unique identifier for the guide
        categories: List of specialties (e.g., ["culture", "history", "food"])
        available_start: Start of availability in ISO format
        available_end: End of availability in ISO format
        hourly_rate: Guide's hourly rate in dollars
        max_group_size: Maximum number of tourists the guide can handle (default: 1)
        tool_context: ADK tool context for state access

    Returns:
        Confirmation with registration details
    """
    try:
        window = Window(
            start=datetime.fromisoformat(available_start),
            end=datetime.fromisoformat(available_end),
        )

        offer = GuideOffer(
            guide_id=guide_id,
            categories=categories,
            available_window=window,
            hourly_rate=hourly_rate,
            max_group_size=max_group_size,
        )

        # Add to state (check for duplicates)
        existing = next(
            (g for g in _scheduler_state.guide_offers if g.guide_id == guide_id),
            None
        )
        if existing:
            _scheduler_state.guide_offers.remove(existing)

        _scheduler_state.guide_offers.append(offer)

        logger.info(f"[Scheduler] Registered guide offer: {guide_id}")

        # Notify UI agent
        send_to_ui_agent({
            "type": "guide_offer",
            "guide_id": guide_id,
            "categories": categories,
            "hourly_rate": hourly_rate,
            "max_group_size": max_group_size,
            "available_window": {
                "start": available_start,
                "end": available_end,
            }
        })

        return {
            "status": "registered",
            "guide_id": guide_id,
            "message": f"Guide {guide_id} registered with {len(categories)} categories at ${hourly_rate}/hr",
            "total_guides": len(_scheduler_state.guide_offers),
        }

    except Exception as e:
        logger.error(f"[Scheduler] Failed to register guide: {e}")
        return {
            "status": "error",
            "message": str(e),
        }


@traced("run_scheduling")
def run_scheduling(tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    Execute the scheduling algorithm to match tourists with guides.

    This tool runs a greedy scheduling algorithm that:
    1. Sorts tourists by earliest availability
    2. Matches each tourist to the best available guide based on:
       - Budget constraints
       - Time overlap
       - Preference matching score
    3. Creates assignments and schedule proposals

    Args:
        tool_context: ADK tool context for state access

    Returns:
        Summary of scheduling results including assignments made
    """
    try:
        tourists = _scheduler_state.tourist_requests
        guides = _scheduler_state.guide_offers

        if not tourists:
            return {
                "status": "no_tourists",
                "message": "No tourist requests to schedule",
                "assignments": [],
            }

        if not guides:
            return {
                "status": "no_guides",
                "message": "No guide offers available",
                "assignments": [],
            }

        assignments = _build_schedule(tourists, guides)
        _scheduler_state.assignments = assignments

        # Create proposals for each tourist
        proposals = []
        for assignment in assignments:
            proposal = ScheduleProposal(
                tourist_id=assignment.tourist_id,
                assignments=[assignment],
                status="proposed",
            )
            proposals.append(proposal.model_dump())

            # Notify UI agent for each assignment
            send_to_ui_agent({
                "type": "assignment",
                "tourist_id": assignment.tourist_id,
                "guide_id": assignment.guide_id,
                "total_cost": assignment.total_cost,
                "categories": assignment.categories,
                "time_window": {
                    "start": assignment.time_window.start.isoformat() if assignment.time_window else None,
                    "end": assignment.time_window.end.isoformat() if assignment.time_window else None,
                }
            })

        # Notify UI agent with final metrics
        assigned_tourists = set(a.tourist_id for a in assignments)
        assigned_guides = set(a.guide_id for a in assignments)
        send_to_ui_agent({
            "type": "metrics",
            "total_tourists": len(tourists),
            "total_guides": len(guides),
            "total_assignments": len(assignments),
            "satisfied_tourists": len(assigned_tourists),
            "guide_utilization": len(assigned_guides) / len(guides) if guides else 0,
            "avg_assignment_cost": sum(a.total_cost for a in assignments) / len(assignments) if assignments else 0,
        })

        logger.info(f"[Scheduler] Created {len(assignments)} assignments")

        return {
            "status": "completed",
            "message": f"Scheduled {len(assignments)} assignments from {len(tourists)} tourists and {len(guides)} guides",
            "num_assignments": len(assignments),
            "assignments": [a.model_dump() for a in assignments],
            "proposals": proposals,
        }

    except Exception as e:
        logger.error(f"[Scheduler] Scheduling failed: {e}")
        return {
            "status": "error",
            "message": str(e),
        }


def get_schedule_status(tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    Get the current status of the scheduler.

    Returns information about:
    - Number of pending tourist requests
    - Number of available guides
    - Number of completed assignments
    - Utilization metrics

    Args:
        tool_context: ADK tool context for state access

    Returns:
        Current scheduler state summary
    """
    state = _scheduler_state

    # Calculate metrics
    total_tourists = len(state.tourist_requests)
    total_guides = len(state.guide_offers)
    total_assignments = len(state.assignments)

    assigned_tourists = set(a.tourist_id for a in state.assignments)
    assigned_guides = set(a.guide_id for a in state.assignments)

    tourist_satisfaction = (
        len(assigned_tourists) / total_tourists * 100 if total_tourists > 0 else 0
    )
    guide_utilization = (
        len(assigned_guides) / total_guides * 100 if total_guides > 0 else 0
    )

    return {
        "status": "ok",
        "total_tourists": total_tourists,
        "total_guides": total_guides,
        "total_assignments": total_assignments,
        "tourist_satisfaction_pct": round(tourist_satisfaction, 1),
        "guide_utilization_pct": round(guide_utilization, 1),
        "pending_tourists": total_tourists - len(assigned_tourists),
        "available_guides": total_guides - len(assigned_guides),
    }


def _build_schedule(
    tourist_requests: List[TouristRequest],
    guide_offers: List[GuideOffer],
) -> List[Assignment]:
    """
    Greedy scheduling algorithm.

    For each tourist (sorted by earliest available time):
    1. Find guides that can accommodate them (budget, time overlap)
    2. Score guides by preference match
    3. Assign to the best scoring guide
    """
    assignments = []
    guide_capacity = {g.guide_id: g.max_group_size for g in guide_offers}

    # Sort tourists by first available time
    sorted_tourists = sorted(
        tourist_requests,
        key=lambda t: t.availability[0].start if t.availability else datetime.max
    )

    for tourist in sorted_tourists:
        if not tourist.availability:
            continue

        best_guide = None
        best_overlap = None
        best_score = -1

        for guide in guide_offers:
            # Check capacity
            if guide_capacity[guide.guide_id] <= 0:
                continue

            # Check budget
            if tourist.budget < guide.hourly_rate:
                continue

            # Check time overlap - find any overlapping time between tourist and guide
            overlap_window = None
            for tourist_window in tourist.availability:
                # Calculate overlap: max of starts to min of ends
                overlap_start = max(tourist_window.start, guide.available_window.start)
                overlap_end = min(tourist_window.end, guide.available_window.end)

                # There's overlap if start is before end
                if overlap_start < overlap_end:
                    overlap_window = Window(start=overlap_start, end=overlap_end)
                    break

            if not overlap_window:
                continue

            # Calculate preference score
            score = sum(
                1 for cat in tourist.preferences if cat in guide.categories
            )

            if score > best_score:
                best_score = score
                best_guide = guide
                best_overlap = overlap_window

        if best_guide and best_overlap:
            duration_hours = (
                best_overlap.end - best_overlap.start
            ).total_seconds() / 3600

            assignment = Assignment(
                tourist_id=tourist.tourist_id,
                guide_id=best_guide.guide_id,
                time_window=best_overlap,
                categories=best_guide.categories,
                total_cost=best_guide.hourly_rate * duration_hours,
            )
            assignments.append(assignment)
            guide_capacity[best_guide.guide_id] -= 1

    return assignments


def clear_scheduler_state(tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    Clear all scheduler state (for testing/reset).

    Args:
        tool_context: ADK tool context

    Returns:
        Confirmation message
    """
    global _scheduler_state
    _scheduler_state = SchedulerState()

    return {
        "status": "cleared",
        "message": "Scheduler state has been reset",
    }
