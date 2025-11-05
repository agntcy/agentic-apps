"""Tests for Tourist Agent proposal receipt using stub client responses.

Copyright AGNTCY Contributors (https://github.com/agntcy)
SPDX-License-Identifier: Apache-2.0
"""
import sys, os, json, asyncio
from types import SimpleNamespace
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(PROJECT_ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from agents.tourist_agent import run_tourist_agent  # noqa: E402
from core.messages import TouristRequest, Window, Assignment, ScheduleProposal  # noqa: E402


class StubClient:
    def __init__(self, proposal_json: str):
        self.proposal_json = proposal_json

    async def send_message(self, message):
        # Simulate scheduler returning schedule proposal artifact
        part = SimpleNamespace(root=SimpleNamespace(text=self.proposal_json))
        task = SimpleNamespace(history=[
            SimpleNamespace(role=SimpleNamespace(value='agent'), parts=[part])
        ])
        yield (task, None)


class StubFactory:
    def __init__(self, proposal_json: str):
        self.proposal_json = proposal_json
    def create(self, card):
        return StubClient(self.proposal_json)


async def run_with_stub():
    import agents.tourist_agent as ta
    now = datetime.now()
    assignment = Assignment(
        tourist_id='t1', guide_id='g1',
        time_window=Window(start=now, end=now + timedelta(hours=2)),
        categories=['culture'], total_cost=100.0
    )
    proposal = ScheduleProposal(proposal_id='proposal-t1-test', assignments=[assignment])
    proposal_json = json.dumps(proposal.to_dict())
    original_factory = ta.ClientFactory
    try:
        ta.ClientFactory = lambda config: StubFactory(proposal_json)
        await run_tourist_agent("http://fake", "t1")
    finally:
        ta.ClientFactory = original_factory


def test_tourist_receives_proposal():
    asyncio.run(run_with_stub())

