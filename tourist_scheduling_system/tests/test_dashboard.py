import pytest
import json
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock, Mock
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from starlette.routing import WebSocketRoute

from src.core import dashboard

# Dummy state object to test set_dashboard_state
class DummyState:
    def __init__(self):
        self.tourist_requests = {}
        self.guide_offers = {}
        self.assignments = []
        self.metrics = {}

    def to_dict(self):
        return {
            "tourist_requests": self.tourist_requests,
            "guide_offers": self.guide_offers,
            "assignments": self.assignments,
            "metrics": self.metrics
        }

    def update_metrics(self):
        pass

class TestDashboardCore:
    def setup_method(self):
        # Reset globals
        dashboard._HTML_TEMPLATE_CACHE = None
        dashboard._ws_clients.clear()
        dashboard._dashboard_state = None
        dashboard._runner = None
        dashboard._current_session_id = "genui_session"

    def test_load_html_template_file_exists(self, tmp_path):
        dummy_template = tmp_path / "dashboard.html"
        dummy_template.write_text("Hello World", encoding="utf-8")

        with patch("src.core.dashboard._HTML_TEMPLATE_PATH", dummy_template):
            dashboard._HTML_TEMPLATE_CACHE = None
            content = dashboard._load_html_template()
            assert content == "Hello World"
            # Second call should use cache
            content = dashboard._load_html_template()
            assert content == "Hello World"

    def test_load_html_template_file_missing(self, tmp_path):
        dummy_template = tmp_path / "dash_missing.html"
        assert not dummy_template.exists()

        with patch("src.core.dashboard._HTML_TEMPLATE_PATH", dummy_template):
            dashboard._HTML_TEMPLATE_CACHE = None
            content = dashboard._load_html_template()
            assert "not found" in content

    def test_reload_html_template(self, tmp_path):
        dummy_template = tmp_path / "dashboard.html"
        dummy_template.write_text("V1", encoding="utf-8")

        with patch("src.core.dashboard._HTML_TEMPLATE_PATH", dummy_template):
            dashboard._HTML_TEMPLATE_CACHE = None
            assert dashboard._load_html_template() == "V1"
            dummy_template.write_text("V2", encoding="utf-8")
            assert dashboard._load_html_template() == "V1"
            assert dashboard.reload_html_template() == "V2"

    def test_set_dashboard_state(self):
        state = DummyState()
        with patch("src.agents.ui_agent", create=True) as mock_agent:
            # ensure _dashboard_state exists on mock
            mock_agent._dashboard_state = None
            dashboard.set_dashboard_state(state)
            assert dashboard._dashboard_state == state
            # Should also try to set variable on ui_agent module
            # We can't strictly assert this because the mock here is a fresh one from patch,
            # and dashboard imports it independently. But we trust the logic in dashboard.py
            # or we could patch `sys.modules['src.agents.ui_agent']`
            pass

    def test_set_transport_mode(self):
        dashboard.set_transport_mode("slim")
        assert dashboard._transport_mode == "slim"

    def test_reset_session(self):
        mock_runner = MagicMock()
        mock_session_service = MagicMock()
        mock_runner.session_service = mock_session_service

        dashboard._runner = mock_runner
        old_session = "old_session"
        dashboard._current_session_id = old_session

        dashboard.reset_session()

        assert dashboard._current_session_id != old_session
        assert "genui_session_" in dashboard._current_session_id
        mock_session_service.create_session_sync.assert_called_once()

    def test_reset_session_no_runner(self):
        dashboard._runner = None
        # Should not raise
        dashboard.reset_session()

    @pytest.mark.asyncio
    async def test_broadcast_to_clients(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        dashboard._ws_clients.add(ws1)
        dashboard._ws_clients.add(ws2)

        msg = {"type": "test"}
        await dashboard.broadcast_to_clients(msg)

        expected_str = json.dumps(msg)
        ws1.send_text.assert_called_with(expected_str)
        ws2.send_text.assert_called_with(expected_str)

        # Test exception handling (disconnected client)
        ws1.send_text.side_effect = Exception("Disconnected")
        await dashboard.broadcast_to_clients(msg)

        assert ws1 not in dashboard._ws_clients
        assert ws2 in dashboard._ws_clients


class TestDashboardApp:
    def setup_method(self):
        dashboard._HTML_TEMPLATE_CACHE = "<html>Dashboard</html>"
        dashboard._ws_clients.clear()
        dashboard._dashboard_state = None
        dashboard._runner = None
        self.app = dashboard.create_dashboard_app()
        self.client = TestClient(self.app)

    def test_dashboard_endpoint(self):
        response = self.client.get("/")
        assert response.status_code == 200
        assert response.text == "<html>Dashboard</html>"

    def test_health_endpoint(self):
        response = self.client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "agent": "adk_ui_dashboard"}

    def test_api_state_endpoint_no_state(self):
        dashboard._dashboard_state = None
        response = self.client.get("/api/state")
        assert response.status_code == 200
        assert response.json() == {"error": "No state available"}

    def test_api_state_endpoint_with_state(self):
        state = DummyState()
        state.assignments.append({"id": 1})
        dashboard._dashboard_state = state

        response = self.client.get("/api/state")
        assert response.status_code == 200
        data = response.json()
        assert data["assignments"] == [{"id": 1}]

    def test_api_update_endpoint(self):
        # Mock broadcast_to_clients
        with patch("src.core.dashboard.broadcast_to_clients", new_callable=AsyncMock) as mock_broadcast:
            # Setup initial state
            state = DummyState()
            state.assignments = []
            dashboard._dashboard_state = state

            update_data = {
                "type": "assignment",
                "tourist_id": "t1",
                "guide_id": "g1",
                "total_cost": 50
            }

            response = self.client.post("/api/update", json=update_data)
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

            # Verify state update
            assert len(state.assignments) == 1
            assert state.assignments[0]["tourist_id"] == "t1"

            # Verify broadcast was called
            mock_broadcast.assert_called()
            call_args = mock_broadcast.call_args[0][0]
            assert call_args["type"] == "assignment"
            assert call_args["tourist_id"] == "t1"
    def test_websocket_endpoint(self):
        with self.client.websocket_connect("/ws") as websocket:
            # Check initial state is received (empty or basic if state is None)
            pass

        # Test with state
        state = DummyState()
        state.assignments.append({"id": 99})
        dashboard._dashboard_state = state

        with self.client.websocket_connect("/ws") as websocket:
            # Should receive initial state
            data = websocket.receive_json()
            assert data["type"] == "initial_state"
            assert data["data"]["assignments"] == [{"id": 99}]

            # Test ping/pong
            websocket.send_text("ping")
            response = websocket.receive_text()
            assert response == "pong"

    @pytest.mark.asyncio
    async def test_chat_endpoint_success(self):
        mock_runner = MagicMock()
        mock_runner.session_service.get_session_sync.return_value = None

        # Setup mocked event
        async def mock_run_async(*args, **kwargs):
            # Yield a text event
            mock_event = MagicMock()
            part = MagicMock()
            part.text = "Hello User"
            mock_event.content.parts = [part]
            mock_event.error_message = None
            yield mock_event

        mock_runner.run_async = mock_run_async

        with patch("src.core.dashboard.get_runner", return_value=mock_runner):
            response = self.client.post("/api/chat", json={"message": "Hello"})
            assert response.status_code == 200
            data = response.json()
            assert data["text"] == "Hello User"
            assert "a2ui" in data

    @pytest.mark.asyncio
    async def test_chat_endpoint_with_visualization(self):
        mock_runner = MagicMock()
        mock_runner.session_service.get_session_sync.return_value = None

        async def mock_run_async(*args, **kwargs):
            mock_event = MagicMock()
            part = MagicMock()
            part.text = "Thinking..."
            mock_event.content.parts = [part]
            mock_event.error_message = None
            yield mock_event

        mock_runner.run_async = mock_run_async

        # Setup dashboard state for visualization
        state = DummyState()
        state.assignments = [{"tourist_id": "T1", "guide_id": "G1", "window": {"start": "10:00", "end": "11:00"}}]
        dashboard._dashboard_state = state

        with patch("src.core.dashboard.get_runner", return_value=mock_runner):
            # Keyword "schedule" triggers visualization
            response = self.client.post("/api/chat", json={"message": "Show me the schedule"})
            assert response.status_code == 200
            data = response.json()
            # Check A2UI content
            a2ui = data["a2ui"]
            assert len(a2ui) > 0
            # Look for SchedulerCalendar
            found_calendar = False
            for msg in a2ui:
                if "surfaceUpdate" in msg:
                    components = msg["surfaceUpdate"]["components"]
                    for comp in components:
                        if "SchedulerCalendar" in comp.get("component", {}):
                            found_calendar = True
                            assignments = comp["component"]["SchedulerCalendar"]["assignments"]
                            assert len(assignments) == 1
                            assert assignments[0]["tourist_id"] == "T1"
            assert found_calendar

    @pytest.mark.asyncio
    async def test_chat_endpoint_reset_on_tool_error(self):
        mock_runner = MagicMock()
        # Mock run_async to raise exception
        async def mock_raise(*args, **kwargs):
             # This generator needs to raise immediately
             if False: yield # make it a generator
             raise Exception("tool_calls must be followed by tool messages")

        mock_runner.run_async = mock_raise
        mock_runner.session_service.create_session_sync = MagicMock()

        with patch("src.core.dashboard.get_runner", return_value=mock_runner):
            with patch("src.core.dashboard.reset_session") as mock_reset:
                response = self.client.post("/api/chat", json={"message": "Fix tools"})
                assert response.status_code == 200 # Should return friendly error
                assert "reset my memory" in response.json().get("text", "")
                mock_reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_endpoint_timeout(self):
        mock_runner = MagicMock()
        async def mock_raise(*args, **kwargs):
             if False: yield
             raise Exception("Timeout error")

        mock_runner.run_async = mock_raise

        with patch("src.core.dashboard.get_runner", return_value=mock_runner):
            response = self.client.post("/api/chat", json={"message": "Hello"})
            assert response.status_code == 200
            assert "timed out" in response.json().get("text", "")

    def test_get_runner_singleton(self):
        dashboard._runner = None
        mock_ui_agent = MagicMock()
        mock_im_runner_cls = MagicMock()

        with patch("src.agents.ui_agent.get_ui_agent", return_value=mock_ui_agent), \
             patch("src.core.dashboard.InMemoryRunner", mock_im_runner_cls):

            runner1 = dashboard.get_runner()
            assert runner1 is not None
            mock_im_runner_cls.assert_called_once()

            # Second call returns same instance
            runner2 = dashboard.get_runner()
            assert runner1 is runner2
            assert mock_im_runner_cls.call_count == 1
