import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from google.adk.events.event import Event
from google.adk.memory.base_memory_service import BaseMemoryService, SearchMemoryResponse
from google.adk.memory.memory_entry import MemoryEntry
from shadi import SqlCipherMemoryStore


_UNKNOWN_SESSION_ID = "__unknown_session_id__"


def _extract_words_lower(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z]+", text.lower()))


class ShadiBackedMemoryService(BaseMemoryService):
    def __init__(
        self,
        *,
        app_name: str,
        user_id: str,
        db_path: str,
        key_name: str,
        scope: str = "adk",
        entry_key: str | None = None,
        memory_bin: str | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._app_name = app_name
        self._user_id = user_id
        self._db_path = db_path
        self._key_name = key_name
        self._scope = scope
        self._entry_key = entry_key or f"adk_memory/{app_name}/{user_id}"
        self._session_events: dict[str, list[Event]] = {}
        self._store = self._open_store()
        self._load_from_shadi()

    def _open_store(self) -> SqlCipherMemoryStore | None:
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            return SqlCipherMemoryStore(self._db_path, None, self._key_name)
        except Exception:
            return None

    def _load_from_shadi(self) -> None:
        if not self._store:
            return
        entry = self._store.get_latest(self._scope, self._entry_key)
        if not entry:
            return
        try:
            data = json.loads(entry.payload)
        except json.JSONDecodeError:
            return
        sessions = data.get("sessions", {}) if isinstance(data, dict) else {}
        for session_id, events_data in sessions.items():
            if not isinstance(events_data, list):
                continue
            loaded_events = []
            for event_data in events_data:
                try:
                    loaded_events.append(Event.model_validate(event_data))
                except Exception:
                    continue
            if loaded_events:
                self._session_events[session_id] = loaded_events

    def _persist(self) -> None:
        if not self._store:
            return
        payload = {
            "app_name": self._app_name,
            "user_id": self._user_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "sessions": {
                session_id: [
                    event.model_dump(mode="json", by_alias=True, exclude_none=True)
                    for event in events
                ]
                for session_id, events in self._session_events.items()
            },
        }
        self._store.put(
            self._scope,
            self._entry_key,
            json.dumps(payload, separators=(",", ":")),
        )

    async def add_session_to_memory(self, session) -> None:
        user_key = session.id or _UNKNOWN_SESSION_ID
        with self._lock:
            self._session_events[user_key] = [
                event
                for event in session.events
                if event.content and event.content.parts
            ]
            self._persist()

    async def add_events_to_memory(
        self,
        *,
        app_name: str,
        user_id: str,
        events: Sequence[Event],
        session_id: str | None = None,
        custom_metadata: Mapping[str, object] | None = None,
    ) -> None:
        _ = custom_metadata
        scoped_session_id = session_id or _UNKNOWN_SESSION_ID
        events_to_add = [
            event for event in events if event.content and event.content.parts
        ]
        with self._lock:
            existing_events = self._session_events.get(scoped_session_id, [])
            existing_ids = {event.id for event in existing_events}
            for event in events_to_add:
                if event.id not in existing_ids:
                    existing_events.append(event)
                    existing_ids.add(event.id)
            self._session_events[scoped_session_id] = existing_events
            self._persist()

    async def search_memory(
        self, *, app_name: str, user_id: str, query: str
    ) -> SearchMemoryResponse:
        response = SearchMemoryResponse()
        words_in_query = _extract_words_lower(query)
        with self._lock:
            session_event_lists = list(self._session_events.values())
        for session_events in session_event_lists:
            for event in session_events:
                if not event.content or not event.content.parts:
                    continue
                words_in_event = _extract_words_lower(
                    " ".join([part.text for part in event.content.parts if part.text])
                )
                if not words_in_event:
                    continue
                if any(query_word in words_in_event for query_word in words_in_query):
                    response.memories.append(
                        MemoryEntry(
                            content=event.content,
                            author=event.author,
                            timestamp=datetime.fromtimestamp(event.timestamp, tz=timezone.utc).isoformat(),
                        )
                    )
        return response
