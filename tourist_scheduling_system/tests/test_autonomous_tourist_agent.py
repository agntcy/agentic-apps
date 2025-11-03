"""Tests autonomous tourist budget & availability heuristics without LLM."""
import sys, os, asyncio
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(PROJECT_ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from agents.autonomous_tourist_agent import AutonomousTouristAgent  # noqa: E402


async def exercise(agent: AutonomousTouristAgent):
    request = await agent.create_tourist_request()
    assert request.budget > 0
    assert request.availability[0].start < request.availability[0].end


def test_autonomous_tourist_request_generation():
    agent = AutonomousTouristAgent("tourist-test", "http://fake")
    agent.llm_available = False
    asyncio.run(exercise(agent))
