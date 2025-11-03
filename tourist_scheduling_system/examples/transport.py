"""
Transport abstraction for A2A protocol messaging.

Provides a simple pub/sub Bus interface that can be backed by:
- In-memory message passing (MemoryBus, default for single-process demos)
- HTTP-based A2A hub (A2ABus, for multi-process distributed agents)
- Future real A2A SDK adapter (when standardized SDK available)

The Bus abstraction decouples agent logic from transport implementation,
allowing seamless swap between local testing and distributed A2A communication.
"""

import threading
import requests
import json
import time
from typing import Callable, Dict, List
from collections import defaultdict

Handler = Callable[[bytes], None]


class Bus:
    """Abstract bus interface for publish/subscribe messaging."""

    def publish(self, topic: str, payload: bytes):
        """Publish a message to a topic."""
        raise NotImplementedError

    def subscribe(self, topic: str, handler: Handler):
        """Subscribe a handler to receive messages from a topic."""
        raise NotImplementedError

    def start_polling(self):
        """Start background polling for subscribed topics (for pull-based transports)."""
        pass

    def stop_polling(self):
        """Stop background polling."""
        pass


class MemoryBus(Bus):
    """In-memory pub/sub bus for local demo (non-distributed)."""

    def __init__(self):
        self._handlers: Dict[str, List[Handler]] = defaultdict(list)
        self._lock = threading.RLock()

    def publish(self, topic: str, payload: bytes):
        """Synchronously invoke all handlers for the topic."""
        with self._lock:
            handlers = list(self._handlers.get(topic, []))

        # Invoke handlers (in current thread for simplicity; could use ThreadPoolExecutor)
        for handler in handlers:
            try:
                handler(payload)
            except Exception as e:
                print(f"[MemoryBus] Handler error on topic {topic}: {e}")

    def subscribe(self, topic: str, handler: Handler):
        """Register a handler for a topic."""
        with self._lock:
            self._handlers[topic].append(handler)


class A2ABus(Bus):
    """HTTP-based A2A protocol adapter connecting to message broker."""

    def __init__(self, broker_url: str = "http://127.0.0.1:5000", agent_id: str = "agent", poll_interval: float = 0.5):
        """
        Args:
            broker_url: Base URL of the message broker
            agent_id: Unique identifier for this agent
            poll_interval: Seconds between polling attempts
        """
        self.broker_url = broker_url.rstrip('/')
        self.agent_id = agent_id
        self.poll_interval = poll_interval
        self._handlers: Dict[str, List[Handler]] = defaultdict(list)
        self._polling = False
        self._poll_thread = None
        self._lock = threading.RLock()

    def publish(self, topic: str, payload: bytes):
        """Publish message via HTTP POST to broker."""
        try:
            # Convert bytes to dict for JSON transport
            data = json.loads(payload.decode('utf-8'))
            response = requests.post(
                f"{self.broker_url}/publish/{topic}",
                json=data,
                timeout=5
            )
            response.raise_for_status()
        except Exception as e:
            print(f"[A2ABus] Publish error on topic {topic}: {e}")

    def subscribe(self, topic: str, handler: Handler):
        """Register handler and notify broker of subscription."""
        with self._lock:
            self._handlers[topic].append(handler)

        try:
            requests.post(
                f"{self.broker_url}/subscribe/{topic}",
                json={"agent_id": self.agent_id},
                timeout=5
            )
        except Exception as e:
            print(f"[A2ABus] Subscribe error on topic {topic}: {e}")

    def start_polling(self):
        """Start background thread to poll subscribed topics."""
        if self._polling:
            return

        self._polling = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def stop_polling(self):
        """Stop polling thread."""
        self._polling = False
        if self._poll_thread:
            self._poll_thread.join(timeout=2)

    def _poll_loop(self):
        """Background polling loop for all subscribed topics."""
        while self._polling:
            with self._lock:
                topics = list(self._handlers.keys())

            for topic in topics:
                try:
                    response = requests.get(
                        f"{self.broker_url}/poll/{topic}",
                        timeout=2
                    )
                    if response.status_code == 200:
                        data = response.json()
                        messages = data.get("messages", [])

                        for msg in messages:
                            payload = json.dumps(msg).encode('utf-8')
                            handlers = self._handlers[topic]
                            for handler in handlers:
                                try:
                                    handler(payload)
                                except Exception as e:
                                    print(f"[A2ABus] Handler error: {e}")
                except Exception as e:
                    # Silently ignore poll errors (broker might be starting up)
                    pass

            time.sleep(self.poll_interval)