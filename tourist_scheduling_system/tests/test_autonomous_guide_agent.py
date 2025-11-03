"""Tests autonomous guide pricing & availability heuristics without LLM."""
import sys, os, asyncio
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(PROJECT_ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from agents.autonomous_guide_agent import AutonomousGuideAgent  # noqa: E402


async def exercise(agent: AutonomousGuideAgent):
    offer = await agent.create_guide_offer()
    assert offer.hourly_rate > 0
    assert offer.available_window.start < offer.available_window.end


def test_autonomous_guide_offer_generation(monkeypatch):
    # Force no LLM regardless of environment
    agent = AutonomousGuideAgent("guide-test", "http://fake")
    agent.llm_available = False
    asyncio.run(exercise(agent))

