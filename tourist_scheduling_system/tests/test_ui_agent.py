#!/usr/bin/env python3
"""Synchronous functional test for UI Agent using FastAPI TestClient.

Avoids spinning up real uvicorn servers; interacts directly with ASGI apps.
"""

import json
import time
import sys
import os
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

TEST_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC_PATH = os.path.join(TEST_ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from core.messages import TouristRequest, GuideOffer, ScheduleProposal, Assignment, Window  # noqa: E402
from agents.ui_agent import UIAgentExecutor, web_app, ui_state  # noqa: E402
from a2a.types import AgentCapabilities, AgentCard, AgentSkill  # noqa: E402
from a2a.server.request_handlers import DefaultRequestHandler  # noqa: E402
from a2a.server.tasks import InMemoryTaskStore  # noqa: E402
from a2a.server.apps import A2AStarletteApplication  # noqa: E402


def build_a2a_app():
    skill = AgentSkill(
        id="real_time_dashboard",
        name="Real-time System Dashboard",
        description="Provides real-time web dashboard for multi-agent tourist scheduling system",
        tags=["dashboard", "ui", "monitoring", "real-time"],
        examples=["Monitor tourist requests and guide availability"],
    )
    agent_card = AgentCard(
        name="UI Agent",
        description="Real-time web dashboard for tourist scheduling system monitoring",
        url="http://testserver/",
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
    return A2AStarletteApplication(agent_card=agent_card, http_handler=request_handler).build()


def reset_state():
    ui_state.tourist_requests.clear()
    ui_state.guide_offers.clear()
    ui_state.assignments.clear()
    ui_state.schedule_proposals.clear()
    ui_state.metrics.total_tourists = 0
    ui_state.metrics.total_guides = 0
    ui_state.metrics.total_assignments = 0
    ui_state.metrics.satisfied_tourists = 0
    ui_state.metrics.guide_utilization = 0
    ui_state.metrics.avg_assignment_cost = 0


def test_ui_agent():
    reset_state()

    # Create TestClients
    web_client = TestClient(web_app)
    a2a_client = TestClient(build_a2a_app())

    # Basic health
    r = web_client.get("/health")
    assert r.status_code == 200

    now = datetime.now()
    offer = GuideOffer(
        guide_id="g-test",
        categories=["culture"],
        available_window=Window(start=now, end=now + timedelta(hours=2)),
        hourly_rate=42.0,
        max_group_size=5,
    )
    request = TouristRequest(
        tourist_id="t-test",
        availability=[Window(start=now, end=now + timedelta(hours=3))],
        budget=150,
        preferences=["culture"],
    )
    assignment = Assignment(
        tourist_id="t-test",
        guide_id="g-test",
        time_window=Window(start=now, end=now + timedelta(hours=1)),
        categories=["culture"],
        total_cost=42.0,
    )
    proposal = ScheduleProposal(
        proposal_id=f"p-{int(time.time())}",
        assignments=[assignment],
    )

    def send(msg_dict):
        payload = {
            "jsonrpc": "2.0",
            "id": f"test-{int(time.time()*1000)}",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [
                        {"kind": "text", "text": json.dumps(msg_dict)}
                    ],
                    "messageId": f"test-msg-{int(time.time()*1000)}"
                }
            }
        }
        r_local = a2a_client.post("/", json=payload)
        assert r_local.status_code == 200, r_local.text

    send(offer.to_dict())
    send(request.to_dict())
    send(proposal.to_dict())

    state_resp = web_client.get("/api/state")
    assert state_resp.status_code == 200
    state = state_resp.json()

    assert any(g["guide_id"] == "g-test" for g in state.get("guide_offers", []))
    assert any(t["tourist_id"] == "t-test" for t in state.get("tourist_requests", []))
    assert state.get("assignments"), "Assignments not recorded in state"
    metrics = state.get("metrics", {})
    assert metrics.get("total_tourists", 0) >= 1
    assert metrics.get("total_guides", 0) >= 1

if __name__ == "__main__":  # pragma: no cover
    import contextlib
    import pytest as _pytest
    _pytest.main([__file__])