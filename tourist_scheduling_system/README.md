# Multi-Agent Tourist Scheduling System

A multi-agent tourist scheduling system built with **Google ADK** (Agent Development Kit) and **Azure OpenAI via LiteLLM**. Features real-time dashboard, SLIM encrypted transport, and OpenTelemetry distributed tracing.

## 🌟 Features

- **Google ADK Agents**: LLM-powered agents using Google's Agent Development Kit
- **Azure OpenAI Integration**: GPT-4o via LiteLLM for model abstraction
- **Real-time Web Dashboard**: Live monitoring with WebSocket updates and network topology visualization
- **A2A Protocol**: Full implementation using official A2A Python SDK
- **SLIM Transport**: Encrypted agent-to-agent messaging via MLS protocol
- **OpenTelemetry Tracing**: Distributed tracing with Jaeger visualization
- **Greedy Matching Algorithm**: Intelligent tourist-guide matching based on preferences, budgets, and availability

## 📁 Project Structure

```
tourist_scheduling_system/
├── src/
│   ├── agents/                      # Agent implementations (Google ADK)
│   │   ├── scheduler_agent.py       # Central coordinator with LiteLLM
│   │   ├── guide_agent.py           # Tour guide agent
│   │   ├── tourist_agent.py         # Tourist agent
│   │   ├── ui_agent.py              # Dashboard with network topology
│   │   ├── dashboard.py             # Web dashboard server
│   │   ├── tools.py                 # Shared scheduling tools
│   │   ├── models.py                # Data models
│   │   └── templates/               # HTML templates
│   └── core/                        # Core components
│       ├── slim_transport.py        # SLIM transport layer
│       ├── logging_config.py        # Centralized logging
│       ├── tracing.py               # OpenTelemetry tracing
│       └── messages.py              # Message schemas
├── scripts/
│   └── run_adk_demo.py              # Demo launcher
├── tests/                           # Unit tests
├── a2a_cards/                       # A2A agent cards
├── logs/                            # Runtime logs
├── traces/                          # OpenTelemetry traces
├── setup.sh                         # Infrastructure management
├── run.sh                           # Demo runner
├── slim-config.yaml                 # SLIM configuration
└── pyproject.toml                   # Project dependencies
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker (for SLIM and Jaeger)
- Azure OpenAI API credentials (optional, falls back to heuristics)

### Installation

```bash
# Clone and navigate
git clone https://github.com/agntcy/agentic-apps.git
cd agentic-apps/tourist_scheduling_system

# Create virtual environment with uv
uv venv .venv
source .venv/bin/activate

# Install dependencies
uv sync
```

### Configure Azure OpenAI (Optional)

```bash
# Set environment variables
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o"
```

### Run the Demo

```bash
# HTTP transport (default)
./run.sh --guides 2 --tourists 3

# SLIM encrypted transport
./setup.sh start                      # Start SLIM container
./run.sh --transport slim --guides 2 --tourists 3

# With OpenTelemetry tracing
./setup.sh start --tracing            # Start SLIM + Jaeger
./run.sh --tracing --guides 2 --tourists 3

# Stop and cleanup
./run.sh stop
./setup.sh stop
```

### Access the Dashboard

Open http://localhost:10021 to view:
- Real-time agent activity
- Network topology visualization
- Matching metrics and statistics

## 🏗️ Architecture

### Agent Types

| Agent | Role | Description |
|-------|------|-------------|
| **Scheduler** | Coordinator | Central matching engine, A2A server |
| **Guide** | Service Provider | Offers tours with availability and pricing |
| **Tourist** | Consumer | Requests tours with preferences and budget |
| **UI/Dashboard** | Monitor | Real-time visualization and metrics |

### Communication Flow

```
┌─────────────┐     ┌─────────────┐
│   Guides    │────▶│  Scheduler  │◀────│  Tourists   │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Dashboard  │
                    └─────────────┘
```

1. Guides register availability and rates
2. Tourists submit requests with preferences and budgets
3. Scheduler runs matching algorithm
4. Dashboard displays real-time updates

### Matching Algorithm

The greedy scheduler considers:
- **Preference overlap**: Category matching (culture, food, history, etc.)
- **Budget constraints**: Tourist budget vs guide hourly rate
- **Time windows**: Overlapping availability
- **Capacity limits**: Guide maximum group size

## 🔌 SLIM Transport

SLIM provides encrypted agent-to-agent communication via MLS protocol.

### Setup

```bash
# Start SLIM container
./setup.sh start

# Run with SLIM transport
./run.sh --transport slim

# Check status
./setup.sh status

# Stop
./setup.sh stop
```

### Architecture

```
┌─────────────────────────────────────┐
│           SLIM Gateway              │
│        (MLS Encrypted)              │
└─────────────────────────────────────┘
      ▲         ▲         ▲
      │         │         │
┌─────┴───┐ ┌───┴───┐ ┌───┴─────┐
│Scheduler│ │ Guide │ │ Tourist │
└─────────┘ └───────┘ └─────────┘
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SLIM_ENDPOINT` | `http://localhost:46357` | SLIM gateway |
| `SLIM_SHARED_SECRET` | (32+ char key) | MLS encryption key |

## 📈 OpenTelemetry Tracing

Distributed tracing with Jaeger visualization.

### Setup

```bash
# Start with tracing
./setup.sh start --tracing
./run.sh --tracing

# View traces
open http://localhost:16686
```

### Trace Outputs

- **Jaeger UI**: http://localhost:16686
- **File**: `traces/traces_*.jsonl`
- **Console**: Set `OTEL_CONSOLE_EXPORT=true`

## 📊 Dashboard Features

- **Real-time Metrics**: WebSocket live updates
- **Network Topology**: Interactive agent graph (drag-and-drop)
- **Agent Activity**: Communication timeline
- **Matching Statistics**: Success rates, utilization, costs

## 🛠️ Development

### Running Tests

```bash
uv run pytest tests/ -v
```

### Code Quality

```bash
uv run black src/ tests/
uv run isort src/ tests/
uv run mypy src/
```

### Project Commands

```bash
# Run scheduler directly
uv run python -m agents.scheduler_agent --mode a2a --port 10010

# Run UI dashboard
uv run python -m agents.ui_agent --port 10021 --dashboard

# Console demo (no dashboard)
uv run python -m agents.scheduler_agent --mode console
```

## 📝 Logging

Logs are written to `logs/` with automatic rotation:
- `logs/system.log` - Main system log
- `logs/scheduler.log` - Scheduler agent
- `logs/ui_agent.log` - Dashboard agent

```bash
# Tail logs
tail -f logs/*.log

# Search errors
grep ERROR logs/*.log
```

## 🔧 CLI Reference

### run.sh

```bash
./run.sh [options]

Options:
  --transport MODE     Transport: http (default) or slim
  --tracing            Enable OpenTelemetry tracing
  --guides N           Number of guide agents (default: 2)
  --tourists N         Number of tourist agents (default: 3)
  --scheduler-port N   Scheduler port (default: 10010)
  --ui-port N          Dashboard port (default: 10021)
  --no-autonomous      Disable autonomous simulation

Commands:
  stop                 Stop all agents
  clean                Stop agents and cleanup
```

### setup.sh

```bash
./setup.sh [command] [options]

Commands:
  start [--tracing]    Start infrastructure (SLIM, optionally Jaeger)
  stop                 Stop containers
  clean                Remove containers
  status               Show container status
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

Apache License 2.0 - see [LICENSE](../LICENSE)
