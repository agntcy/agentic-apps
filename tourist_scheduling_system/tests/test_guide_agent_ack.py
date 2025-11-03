"""Tests for Guide Agent acknowledgment handling using stub client responses."""
import sys, os, json, asyncio
from types import SimpleNamespace

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(PROJECT_ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from agents.guide_agent import run_guide_agent  # noqa: E402
from core.messages import GuideOffer, Window  # noqa: E402


class StubClient:
    """Stub A2A client that yields a single acknowledgment response."""
    def __init__(self, offer_json: str):
        self.offer_json = offer_json

    async def send_message(self, message):
        # Simulate scheduler sending back acknowledgment artifact
        ack_text = json.dumps({"type": "Acknowledgment", "message": "Guide g1 registered"})
        part = SimpleNamespace(root=SimpleNamespace(text=ack_text))
        task = SimpleNamespace(history=[
            SimpleNamespace(role=SimpleNamespace(value='agent'), parts=[part])
        ])
        yield (task, None)


class StubFactory:
    def __init__(self):
        self.created = False
    def create(self, card):
        self.created = True
        return StubClient("{}")


async def run_with_stub():
    # Monkeypatch ClientFactory inside guide_agent module
    import agents.guide_agent as ga
    original_factory = ga.ClientFactory
    try:
        ga.ClientFactory = lambda config: StubFactory()
        await run_guide_agent("http://fake", "g1")
    finally:
        ga.ClientFactory = original_factory


def test_guide_ack(monkeypatch):
    asyncio.run(run_with_stub())

