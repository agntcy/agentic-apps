import json
import os
import threading
from typing import Any, Dict, List

from google.adk.memory.base_memory_service import BaseMemoryService, SearchMemoryResponse
from google.adk.memory.memory_entry import MemoryEntry
from google.adk.sessions.session import Session
from google.adk.events.event import Event
from google.adk.memory import _utils

class FileMemoryService(BaseMemoryService):
    """A persistent file-based memory service."""

    def __init__(self, file_path: str = "agent_memory.json"):
        self.file_path = file_path
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump({}, f)

    def _load_events(self) -> Dict[str, Dict[str, List[Dict]]]:
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_events(self, data: Dict[str, Dict[str, List[Dict]]]):
        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _user_key(self, app_name: str, user_id: str):
        return f'{app_name}/{user_id}'

    async def add_session_to_memory(self, session: Session):
        user_key = self._user_key(session.app_name, session.user_id)

        # Serialize events
        serialized_events = []
        for event in session.events:
            if event.content and event.content.parts:
                # Use model_dump(mode='json') for serialization friendly dict
                serialized_events.append(event.model_dump(mode='json'))

        with self._lock:
            data = self._load_events()
            if user_key not in data:
                data[user_key] = {}
            data[user_key][session.id] = serialized_events
            self._save_events(data)

    async def search_memory(self, *, app_name: str, user_id: str, query: str) -> SearchMemoryResponse:
        user_key = self._user_key(app_name, user_id)

        with self._lock:
            data = self._load_events()
            user_sessions = data.get(user_key, {})

        response = SearchMemoryResponse()

        # Simple keyword search (same as InMemoryMemoryService)
        query_words = set(query.lower().split())

        for session_id, events_data in user_sessions.items():
            for event_dict in events_data:
                try:
                    event = Event.model_validate(event_dict)
                except Exception:
                    continue

                if not event.content or not event.content.parts:
                    continue

                text = ' '.join([p.text for p in event.content.parts if p.text])
                text_lower = text.lower()

                if any(w in text_lower for w in query_words):
                    response.memories.append(
                        MemoryEntry(
                            content=event.content,
                            author=event.author,
                            timestamp=_utils.format_timestamp(event.timestamp)
                        )
                    )
        return response
