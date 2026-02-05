# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Pytest fixtures using the simple ProcessRunner.
Replace prior xprocess usage with these.
"""
import os
import re
import time
import sys
import pytest
from pathlib import Path

from fastapi.testclient import TestClient
from tests.integration.docker_helpers import up, down

from tests.integration.process_helper import ProcessRunner 

LUNGO_DIR = Path(__file__).resolve().parents[2]
print("LUNGO_DIR:", LUNGO_DIR)

AGENTS = {
    # auction agents
    "brazil-farm": {
        "cmd": ["python", "-m", "agents.farms.brazil.farm_server", "--no-reload"],
        "ready_pattern": r"Transport initialized with tracing enabled",
    },
    "colombia-farm": {
        "cmd": ["python", "-m", "agents.farms.colombia.farm_server", "--no-reload"],
        "ready_pattern": r"Transport initialized with tracing enabled",
    },
    "vietnam-farm": {
        "cmd": ["python", "-m", "agents.farms.vietnam.farm_server", "--no-reload"],
        "ready_pattern": r"Transport initialized with tracing enabled",
    },
    "weather-mcp": {
        "cmd": ["uv", "run", "-m", "agents.mcp_servers.weather_service"],
        "ready_pattern": r"Transport initialized with tracing enabled",
    },
    # logistics agents
    "logistics-farm": {
        "cmd": ["python", "-m", "agents.logistics.farm.server", "--no-reload"],
        "ready_pattern": r"Transport initialized with tracing enabled",
    },
    "accountant": {
        "cmd": ["python", "-m", "agents.logistics.accountant.server", "--no-reload"],
        "ready_pattern": r"Transport initialized with tracing enabled",
    },
    "shipper": {
        "cmd": ["python", "-m", "agents.logistics.shipper.server", "--no-reload"],
        "ready_pattern": r"Transport initialized with tracing enabled",
    },
    "helpdesk": {
        "cmd": ["python", "-m", "agents.logistics.helpdesk.server", "--no-reload"],
        "ready_pattern": r"Transport initialized with tracing enabled",
    }
}

_ACTIVE_RUNNERS = []

# ---------------- utils ----------------

def _base_env():
    return {
        **os.environ,
        "PYTHONPATH": str(LUNGO_DIR),
        "ENABLE_HTTP": "true",
        "FARM_BROADCAST_TOPIC": "farm_broadcast",
        "PYTHONUNBUFFERED": "1",
        "PYTHONFAULTHANDLER": "1",
    }

def _purge_modules(prefixes):
    to_delete = [m for m in list(sys.modules)
                 if any(m == p or m.startswith(p + ".") for p in prefixes)]
    for m in to_delete:
        sys.modules.pop(m, None)

# ---------------- session infra ----------------
files = ["docker-compose.yaml"]
if Path("docker-compose.override.yaml").exists():
    files.append("docker-compose.override.yaml")

@pytest.fixture(scope="session", autouse=True)
def orchestrate_session_services():
    print("\n--- Setting up session level service integrations ---")
    setup_transports()
    setup_observability()
    setup_identity()
    print("--- Session level service setup complete. Tests can now run ---")
    yield
    down(files)

def setup_transports():
    _startup_slim()
    _startup_nats()

def setup_observability():
    _startup_otel_collector()
    _startup_clickhouse()
    _startup_grafana()

def setup_identity():
    pass

def _startup_slim():
    up(files, ["slim"])

def _startup_nats():
    up(files, ["nats"])

def _startup_grafana():
    up(files, ["grafana"])

def _startup_clickhouse():
    up(files, ["clickhouse-server"])

def _startup_otel_collector():
    up(files, ["otel-collector"])
    time.sleep(10)

# ---------------- per-test config ----------------

@pytest.fixture(scope="function")
def transport_config(request):
    return dict(getattr(request, "param", {}) or {})

@pytest.fixture(scope="function")
def agent_specs(request):
    """
    Select agents via @pytest.mark.agents([...])

    Each entry can be:
      - dict: {"name": str, "cmd": list[str], "ready_pattern": str?}
      - string module path: "agents.supervisors.auction.main" (runs with python -m)
    """
    m = request.node.get_closest_marker("agents")
    if not m:
        return []
    specs = m.args[0] if m.args else m.kwargs.get("specs", [])
    return [_normalize_agent_spec(s) for s in specs]

def _normalize_agent_spec(spec):
    """
    Return a dict: {"name": str, "cmd": list[str], "ready_pattern": str}
    """
    if isinstance(spec, dict):
        name = spec.get("name")
        cmd = spec.get("cmd")
        if not name:
            # try to derive a name from cmd or module
            name = _derive_name_from_spec(spec)
        ready = "Started server process"
        return {"name": name, "cmd": cmd, "ready_pattern": ready}

    if isinstance(spec, str):
        # If it's a python module path like "a.b.c", run it via python -m
        if re.match(r"^[a-zA-Z_][\w\.]*$", spec):
            return {
                "name": spec.split(".")[-1],
                "cmd": ["python", "-m", spec],
                "ready_pattern": "Transport initialized with tracing enabled",
            }
        raise ValueError(f"Unrecognized agent spec string: {spec!r}")

    raise TypeError(f"Agent spec must be dict or module string, got: {type(spec)}")

def _derive_name_from_spec(spec: dict) -> str:
    if "name" in spec and spec["name"]:
        return spec["name"]
    if "cmd" in spec and spec["cmd"]:
        # e.g., ["python", "-m", "agents.foo.bar"] → "bar"
        parts = list(spec["cmd"])
        try:
            if "-m" in parts:
                mod = parts[parts.index("-m") + 1]
                return mod.split(".")[-1]
        except Exception:
            pass
        # fallback to first arg
        return Path(parts[0]).name
    return "agent"

# ---------------- generic agent fixture ----------------

@pytest.fixture(scope="function")
def agents_up(request, transport_config):
    """
    Start one or more registered agents via @pytest.mark.agents([...]).
    Example:
        @pytest.mark.agents(["brazil-farm", "weather-mcp"])
        def test_things(agents_up): ...
    """
    m = request.node.get_closest_marker("agents")
    agent_names = (m.args[0] if m and m.args else m.kwargs.get("names", [])) if m else []

    runners: list[ProcessRunner] = []

    for name in agent_names:
        spec = AGENTS.get(name)
        if not spec:
            raise ValueError(f"Unknown agent: {name!r}. Add it to AGENTS dict.")

        env = _base_env()
        env.update(transport_config or {})

        print(f"\n--- Starting {name} ---")
        runner = ProcessRunner(
            name=name,
            cmd=spec["cmd"],
            cwd=str(LUNGO_DIR),
            env=env,
            ready_pattern=spec.get("ready_pattern", r"Transport initialized with tracing enabled"),
            timeout_s=60.0,
            log_dir=Path(LUNGO_DIR) / ".pytest-logs",
        ).start()
        _ACTIVE_RUNNERS.append(runner)

        try:
            runner.wait_ready()
        except TimeoutError:
            print(f"--- {name} logs: {runner.log_path}")
            runner.stop()
            raise

        print(f"--- {name} ready (logs: {runner.log_path}) ---")
        runners.append(runner)

    try:
        yield
    finally:
        for r in runners:
            print(f"--- Stopping {r.name} ---")
            r.stop()

# ---------------- http client ----------------

@pytest.fixture
def auction_supervisor_client(transport_config, monkeypatch):
    for k, v in _base_env().items():
        monkeypatch.setenv(k, str(v))
    for k, v in transport_config.items():
        monkeypatch.setenv(k, v)

    _purge_modules([
        "agents.supervisors.auction",
        "config.config",
    ])

    import agents.supervisors.auction.main as auction_main
    import importlib
    importlib.reload(auction_main)

    app = auction_main.app
    with TestClient(app) as client:
        yield client

@pytest.fixture
def logistics_supervisor_client(transport_config, monkeypatch):
    for k, v in _base_env().items():
        monkeypatch.setenv(k, str(v))
    for k, v in transport_config.items():
        monkeypatch.setenv(k, v)

    _purge_modules([
        "agents.supervisors.logistics",
        "config.config",
    ])

    import agents.supervisors.logistics.main as logistics_main
    import importlib
    importlib.reload(logistics_main)

    app = logistics_main.app
    with TestClient(app) as client:
        yield client

@pytest.fixture
def helpdesk_client(transport_config, monkeypatch):
    for k, v in _base_env().items():
        monkeypatch.setenv(k, str(v))
    for k, v in transport_config.items():
        monkeypatch.setenv(k, v)

    _purge_modules([
        "agents.logistics.helpdesk",
        "config.config",
    ])

    import importlib
    import agents.logistics.helpdesk.server as helpdesk_server
    importlib.reload(helpdesk_server)

    from fastapi.testclient import TestClient
    app = helpdesk_server.app
    with TestClient(app) as client:
        yield client

@pytest.fixture
def logistics_shipper_client(transport_config, monkeypatch):
    for k, v in _base_env().items():
        monkeypatch.setenv(k, str(v))
    for k, v in transport_config.items():
        monkeypatch.setenv(k, v)

    _purge_modules([
        "agents.logistics.shipper",
        "config.config",
    ])

    import importlib
    import agents.logistics.shipper.server as shipper_server
    importlib.reload(shipper_server)

    from fastapi.testclient import TestClient
    app = shipper_server.app
    with TestClient(app) as client:
        yield client


@pytest.fixture
def logistics_farm_client(transport_config, monkeypatch):
    for k, v in _base_env().items():
        monkeypatch.setenv(k, str(v))
    for k, v in transport_config.items():
        monkeypatch.setenv(k, v)

    _purge_modules([
        "agents.logistics.farm",
        "config.config",
    ])

    import importlib
    import agents.logistics.farm.server as farm_server
    importlib.reload(farm_server)

    from fastapi.testclient import TestClient
    app = farm_server.app
    with TestClient(app) as client:
        yield client



@pytest.fixture
def logistics_accountant_client(transport_config, monkeypatch):
    for k, v in _base_env().items():
        monkeypatch.setenv(k, str(v))
    for k, v in transport_config.items():
        monkeypatch.setenv(k, v)

    _purge_modules([
        "agents.logistics.farm",
        "config.config",
    ])

    import importlib
    import agents.logistics.accountant.server as accountant_server
    importlib.reload(accountant_server)

    from fastapi.testclient import TestClient
    app = accountant_server.app
    with TestClient(app) as client:
        yield client
