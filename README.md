# Agentic Apps Monorepo

Collection of experimental and reference agent applications built on the A2A protocol and SDK. Each subfolder is a self-contained agent system or demo (some with autonomous LLM behavior, real-time dashboards, or network orchestration).

## Contents

| Project | Description | Key Tech |
|---------|-------------|----------|
| [`tourist_scheduling_system/`](tourist_scheduling_system/README.md) | Multi-agent tourist scheduling with scheduler, UI dashboard, and autonomous guide/tourist agents | A2A SDK, Google ADK, SLIM, FastAPI, WebSockets, OpenTelemetry |
| [`network_of_assistants/`](network_of_assistants/README.md) | Network-of-assistants stack (moderator, math, file, web, user proxy) | FastAPI, Docker, A2A SDK |
| [`weather_vibes_agp/`](weather_vibes_agp/README.md) | Weather plus mood/vibe agent demo | A2A SDK |

## Quick Start (Tourist Scheduling System)

The most feature-complete example lives in `tourist_scheduling_system/`. It demonstrates:

- Scheduler coordination of guide offers and tourist requests
- Real-time UI agent (web + WebSocket)
- Autonomous LLM-powered agents with heuristic fallback when cloud creds absent
- **SLIM transport**: Encrypted group messaging via MLS protocol
- **Google ADK agents**: Alternative implementation using Google's Agent Development Kit
- **OpenTelemetry tracing**: Distributed tracing with Jaeger visualization

### Install

```bash
git clone https://github.com/agntcy/agentic-apps.git
cd agentic-apps/tourist_scheduling_system
uv venv .venv
source .venv/bin/activate  # macOS/Linux
uv sync
```

### Quick Run with Scripts

```bash
cd tourist_scheduling_system

# HTTP transport with original agents (default)
./start.sh

# HTTP transport with Google ADK agents
./start.sh --agent-type adk --guides 2 --tourists 2

# SLIM transport (auto-starts SLIM container)
./start.sh --transport slim

# ADK + SLIM + OpenTelemetry tracing
./start.sh --agent-type adk --transport slim --tracing

# Stop and cleanup
./start.sh clean
```

### Manual Control (Separate Infrastructure)

```bash
cd tourist_scheduling_system

# Start infrastructure (SLIM node + Jaeger for tracing)
./setup.sh start --tracing

# Run the demo
./run.sh --agent-type adk --transport slim --tracing --guides 3 --tourists 3

# Stop agents
./run.sh stop

# Stop infrastructure
./setup.sh stop

# Check status
./setup.sh status
```

### Azure OpenAI (Optional)

Set these before running to enable LLM reasoning; otherwise heuristic fallback is used:
```bash
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_API_VERSION=2024-08-01-preview
export AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
export AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| SLIM container not starting | Docker not running | Start Docker Desktop or daemon |
| Port already in use | Previous run still active | Use `./start.sh clean` or `lsof -i :10010` / kill PID |
| No LLM decisions | Cloud creds not set | Export Azure env vars or ignore (heuristics operate) |
| UI blank page | Wrong port or UI agent not started | Confirm UI is running on specified web port |
| Jaeger not showing traces | Tracing not enabled | Use `--tracing` flag with start.sh or run.sh |

## Development

Format & type check:
```bash
black tourist_scheduling_system/src tourist_scheduling_system/tests
isort tourist_scheduling_system/src tourist_scheduling_system/tests
mypy tourist_scheduling_system/src
pytest tourist_scheduling_system/tests
```

## License

Apache License 2.0 (see `LICENSE`).

## Contributing

See `CONTRIBUTING.md` for guidelines; feel free to open issues or PRs for new agent demos.

