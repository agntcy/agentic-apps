# Agentic Apps Monorepo

Collection of experimental and reference agent applications built on the A2A protocol and SDK. Each subfolder is a self-contained agent system or demo (some with autonomous LLM behavior, real-time dashboards, or network orchestration).

## Contents

| Project | Description | Key Tech |
|---------|-------------|----------|
| `tourist_scheduling_system/` | Multi-agent tourist scheduling with scheduler, UI dashboard, and autonomous guide/tourist agents | A2A SDK, FastAPI, WebSockets, OpenAI/Azure OpenAI |
| `remote_agent_agp/` | Remote agent gateway & client demos | A2A SDK, Docker Compose |
| `mailcomposer/` | AI-driven email composer workflow | A2A SDK, LangGraph |
| `marketing-campaign/` | Multi-agent marketing campaign planner | A2A SDK |
| `email_reviewer/` | Agent that reviews emails for quality & tone | A2A SDK |
| `network_of_assistants/` | Network-of-assistants stack (moderator, math, file, web, user proxy) | FastAPI, Docker, A2A SDK |
| `weather_vibes_agp/` | Weather plus mood/vibe agent demo | A2A SDK |
| `api_bridge_agent_demos/` | MCP / bridge agent examples | A2A SDK, MCP |

## Quick Start (Tourist Scheduling System)

The most feature-complete example lives in `tourist_scheduling_system/`. It demonstrates:

- Scheduler coordination of guide offers and tourist requests
- Real-time UI agent (web + WebSocket)
- Autonomous LLM-powered agents with heuristic fallback when cloud creds absent

### Install

```bash
git clone https://github.com/agntcy/agentic-apps.git
cd agentic-apps/tourist_scheduling_system
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install -e .
```

### Basic Run

In one terminal start the scheduler:
```bash
PYTHONPATH=src python src/agents/scheduler_agent.py --host localhost --port 10010
```

In a second terminal start the UI dashboard:
```bash
PYTHONPATH=src python src/agents/ui_agent.py --host localhost --port 10011 --a2a-port 10012
```

Send a guide offer and tourist request:
```bash
PYTHONPATH=src python src/agents/guide_agent.py --scheduler-url http://localhost:10010 --guide-id guide-1
PYTHONPATH=src python src/agents/tourist_agent.py --scheduler-url http://localhost:10010 --tourist-id tourist-1
```

Open http://localhost:10011 in your browser to view live activity.

### Unified Script Demo

Use the helper script to orchestrate everything (auto detects running ports and can add autonomous agents):

```bash
cd tourist_scheduling_system
PYTHONPATH=src scripts/run_with_ui.sh --scheduler-port 10010 --ui-web-port 10011 --ui-a2a-port 10012
```

Add autonomous pair for a 1 minute smoke test:
```bash
PYTHONPATH=src scripts/run_with_ui.sh \
	--scheduler-port 10010 \
	--ui-web-port 10011 \
	--ui-a2a-port 10012 \
	--autonomous \
	--auto-duration 1 \
	--auto-guide-id ag-auto \
	--auto-tourist-id at-auto
```

### Azure OpenAI (Optional)

Set these before running autonomous mode to enable LLM reasoning; otherwise heuristic fallback is used:
```bash
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_API_VERSION=2024-08-01-preview
export AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
export AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Exit Code: 127` running agents | Virtual env not active / path mismatch | `source .venv/bin/activate` then rerun; ensure working directory is `tourist_scheduling_system` |
| Import errors after refactor | Missing `PYTHONPATH=src` | Prefix command with `PYTHONPATH=src` or install in editable mode (`pip install -e .`) |
| Port already in use | Previous run still active | Use `lsof -i :10010` / kill PID or rely on script reuse logic |
| No LLM decisions, warning about Azure vars | Cloud creds not set | Export Azure env vars or ignore (heuristics operate) |
| UI blank page | Wrong port or UI agent not started | Confirm `ui_agent.py` running on specified web port |

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

