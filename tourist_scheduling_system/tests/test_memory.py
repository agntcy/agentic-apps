import pytest
import os
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path so we can import src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.memory import FileMemoryService
from google.adk.sessions.session import Session
from google.adk.events.event import Event
from google.genai import types

class TestFileMemoryService:
    @pytest.fixture
    def memory_file(self, tmp_path):
        return str(tmp_path / "test_memory.json")

    @pytest.fixture
    def memory_service(self, memory_file):
        return FileMemoryService(file_path=memory_file)

    def test_init_creates_file(self, memory_file):
        # File shouldn't exist yet (tmp_path exists, but file inside it doesn't)
        assert not os.path.exists(memory_file)
        FileMemoryService(file_path=memory_file)
        assert os.path.exists(memory_file)
        with open(memory_file, 'r') as f:
            data = json.load(f)
            assert data == {}

    def test_user_key(self, memory_service):
        key = memory_service._user_key("app", "user")
        assert key == "app/user"

    @pytest.mark.asyncio
    async def test_add_session_and_search(self, memory_service):
        # Create a dummy session with events
        session = MagicMock(spec=Session)
        session.app_name = "test_app"
        session.user_id = "test_user"
        session.id = "session_1"

        # Construct a real Event object
        event_content = types.Content(
            role="user",
            parts=[types.Part(text="I love hiking in the mountains")]
        )

        event = Event(
            author="user",
            content=event_content
        )

        session.events = [event]

        await memory_service.add_session_to_memory(session)

        # Verify it was saved to file
        with open(memory_service.file_path, 'r') as f:
            data = json.load(f)
            assert "test_app/test_user" in data
            assert "session_1" in data["test_app/test_user"]

        # Test search success
        response = await memory_service.search_memory(
            app_name="test_app",
            user_id="test_user",
            query="hiking"
        )
        assert len(response.memories) == 1
        assert "hiking" in response.memories[0].content.parts[0].text

        # Test search failure
        response = await memory_service.search_memory(
            app_name="test_app",
            user_id="test_user",
            query="swimming"
        )
        assert len(response.memories) == 0

    @pytest.mark.asyncio
    async def test_search_memory_case_insensitive(self, memory_service):
         # Create a dummy session with events
        session = MagicMock(spec=Session)
        session.app_name = "test_app"
        session.user_id = "test_user"
        session.id = "session_1"

        event_content = types.Content(
            role="user",
            parts=[types.Part(text="I love HIKING")]
        )

        event = Event(
            author="user",
            content=event_content
        )

        session.events = [event]
        await memory_service.add_session_to_memory(session)

        response = await memory_service.search_memory(
            app_name="test_app",
            user_id="test_user",
            query="hiking"
        )
        assert len(response.memories) == 1

    def test_load_events_corrupt_file(self, memory_service):
        # Corrupt the file
        with open(memory_service.file_path, 'w') as f:
            f.write("invalid json")

        data = memory_service._load_events()
        assert data == {}

    @pytest.mark.asyncio
    async def test_search_memory_malformed_event(self, memory_service):
        import json

        # Create a valid event with empty parts
        event_content = types.Content(role="user", parts=[])
        event_empty_parts = Event(
            author="user",
            content=event_content,
            timestamp=1704067200
        ).model_dump(mode='json')

        # Write directly to the file backend used by memory_service
        data = {
            "app/user": {
                "sess1": [
                    {"garbage": "data"},
                    event_empty_parts
                ]
            }
        }
        with open(memory_service.file_path, 'w') as f:
            json.dump(data, f)

        # Should not raise exception
        results = await memory_service.search_memory(app_name="app", user_id="user", query="something")
        assert len(results.memories) == 0
