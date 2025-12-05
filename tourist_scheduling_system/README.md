# Tourist Scheduling System - ADK Multi-Agent Demo

A multi-agent scheduling system demonstrating [Agent-to-Agent (A2A)](https://github.com/google/a2a-sdk) communication
patterns using Google's ADK framework. Tour guides and tourists are matched dynamically through an intelligent
scheduler, with optional SLIM transport for encrypted messaging and distributed tracing via OpenTelemetry.

<img src="docs/tss-demo.gif" alt="TSS Demo" width="800">

## 📑 Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [Architecture](#-architecture)
- [SLIM Transport](#-slim-transport)
- [Distributed Tracing](#-distributed-tracing)
- [Dashboard Features](#-dashboard-features)
- [CLI Reference](#-cli-reference)
- [Development](#-development)
- [License](#-license)

## ✨ Features

- **Multi-Agent Coordination**: Scheduler, guides, and tourists working together
- **A2A Communication**: Full A2A compliance with SLIM transport support
- **Real-Time Dashboard**: Live monitoring with WebSocket updates
- **Distributed Tracing**: OpenTelemetry integration with Jaeger visualization
- **LLM-Powered Agents**: Azure OpenAI integration via LiteLLM

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [UV](https://github.com/astral-sh/uv) package manager
- Docker (for SLIM transport and tracing)
- Azure OpenAI API key

### Installation

```bash
# Clone the repository
git clone https://github.com/agntcy/agentic-apps.git
cd agentic-apps/tourist_scheduling_system

# Set up the environment
./setup.sh install

# Configure Azure OpenAI
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com"
```

### Run the Demo

```bash
# Start infrastructure (SLIM + Jaeger)
./setup.sh start

# Run the demo with SLIM transport
source run.sh --transport slim --tracing
```

**Access Points**:
- Dashboard: http://localhost:10021
- Jaeger UI: http://localhost:16686 (when tracing is enabled)

## 📁 Project Structure

```
tourist_scheduling_system/
├── src/
│   ├── agents/                  # Agent implementations
│   │   ├── scheduler_agent.py   # Main scheduler (A2A server, port 10000)
│   │   ├── ui_agent.py          # Dashboard web app (A2A server, port 10021)
│   │   ├── guide_agent.py       # Tour guide agent (A2A client)
│   │   ├── tourist_agent.py     # Tourist agent (A2A client)
│   │   ├── dashboard.py         # Starlette dashboard app
│   │   ├── a2a_cards.py         # Agent A2A card definitions
│   │   ├── models.py            # Pydantic data models
│   │   └── tools.py             # ADK tools (register, match, etc.)
│   └── core/                    # Core utilities
│       ├── slim_transport.py    # SLIM transport adapter
│       ├── tracing.py           # OpenTelemetry setup
│       ├── messages.py          # Message types
│       └── logging_config.py    # Logging configuration
├── scripts/
│   └── run_adk_demo.py          # Main demo runner (Python CLI)
├── setup.sh                     # Infrastructure management
├── run.sh                       # Demo launcher script (sourceable)
├── slim-config.yaml             # SLIM node configuration
└── slim-config-otel.yaml        # SLIM config with OpenTelemetry
```

## 🏗️ Architecture

### Agent Roles

| Agent | Port | Role |
|-------|------|------|
| Scheduler | 10000 | Central coordinator, matches guides to tourists |
| Dashboard | 10021 | Real-time web UI with WebSocket updates |
| Guides | (via A2A) | LLM-powered tour guides with specializations |
| Tourists | (via A2A) | Visitors requesting specific tour experiences |

### Communication Flow

```
┌──────────────┐     A2A/SLIM      ┌──────────────┐
│ Guide Agent  │ ◀───────────────▶ │   Scheduler  │
└──────────────┘                   │    Agent     │
                                   │  (port 10000)│
┌──────────────┐     A2A/SLIM      │              │
│ Tourist Agent│ ◀───────────────▶ │              │
└──────────────┘                   └──────┬───────┘
                                          │
                                          │ HTTP/WS
                                          ▼
                                   ┌──────────────┐
                                   │  Dashboard   │
                                   │  (port 10021)│
                                   └──────────────┘
```

## 🔐 SLIM Transport

SLIM provides encrypted, high-performance messaging:

```bash
# Start SLIM node
./setup.sh slim

# Configure SLIM endpoint
export SLIM_ENDPOINT=http://localhost:46357
export SLIM_SHARED_SECRET=supersecretsharedsecret123456789
export SLIM_TLS_INSECURE=true

# Run with SLIM transport
source run.sh --transport slim
```

### SLIM Configuration

See `slim-config.yaml` for node configuration. Key settings:

```yaml
storage:
  type: InMemory
transport:
  type: HTTP
security:
  shared_secret: ${SLIM_SHARED_SECRET}
```

## 📊 Distributed Tracing

Full OpenTelemetry integration with Jaeger:

```bash
# Start Jaeger
./setup.sh tracing

# Run with tracing
source run.sh --tracing

# View traces
open http://localhost:16686
```

Trace features:
- Request-level spans
- Cross-agent trace propagation
- Tool execution timing
- Error tracking

## 🖥️ Dashboard Features

The real-time dashboard shows:

- **Guide Pool**: Available guides with specializations and ratings
- **Tourist Queue**: Pending tourist requests with preferences
- **Active Assignments**: Current guide-tourist matches in progress
- **Completed Tours**: Historical data with ratings
- **Communication Log**: Agent message history (guide/tourist/system)

WebSocket provides instant updates as the scheduler processes requests.

## 📖 CLI Reference

### `setup.sh` - Infrastructure Management

```bash
./setup.sh install        # Install Python dependencies with UV
./setup.sh start          # Start SLIM + Jaeger containers
./setup.sh stop           # Stop all containers
./setup.sh clean          # Remove containers and data
./setup.sh slim           # Start only SLIM node
./setup.sh tracing        # Start only Jaeger
./setup.sh status         # Show container status
```

### `run.sh` - Demo Launcher

The script can be **sourced** to preserve environment variables or run directly:

```bash
# Source to inherit current shell's env vars (recommended)
source run.sh [options]

# Or run directly
./run.sh [options]

# Options
--transport MODE          # http (default) or slim
--tracing                 # Enable OpenTelemetry tracing
--scheduler-port N        # Scheduler port (default: 10000)
--ui-port N               # Dashboard port (default: 10021)
--guides N                # Number of guides (default: 2)
--tourists N              # Number of tourists (default: 3)
--duration N              # Duration in minutes (0=single run)
--interval N              # Delay between requests (default: 1.0s)
--no-demo                 # Start servers only, no demo traffic

# Control
./run.sh stop             # Stop all agents
./run.sh clean            # Stop agents and clean up
```

### `scripts/run_adk_demo.py` - Python Demo Runner

For direct Python control:

```bash
# Interactive console demo
.venv/bin/python scripts/run_adk_demo.py --mode console

# Full multi-agent demo (spawns all processes)
.venv/bin/python scripts/run_adk_demo.py --mode multi

# Simulation only (requires agents already running)
.venv/bin/python scripts/run_adk_demo.py --mode sim --port 10000 --ui-port 10021

# With SLIM transport
.venv/bin/python scripts/run_adk_demo.py --mode multi --transport slim

# Options
--mode MODE               # console, server, multi, or sim
--port N                  # Scheduler port (default: 10000)
--ui-port N               # Dashboard port (default: 10021)
--guides N                # Number of guides (default: 2)
--tourists N              # Number of tourists (default: 3)
--transport MODE          # http or slim
--slim-endpoint URL       # SLIM node URL
--tracing/--no-tracing    # Enable OpenTelemetry
--duration N              # Duration in minutes (0=single run)
--interval N              # Delay between requests
--fast/--no-fast          # Skip LLM calls for testing
```

### Environment Variables

```bash
# Required
export AZURE_OPENAI_API_KEY="your-key"

# Optional
export AZURE_OPENAI_ENDPOINT="https://..."
export TRANSPORT=slim                          # Default transport
export SLIM_ENDPOINT=http://localhost:46357    # SLIM node URL
export SLIM_SHARED_SECRET=your-secret          # SLIM auth secret
export SCHED_PORT=10000                        # Scheduler port
export UI_PORT=10021                           # Dashboard port
```

## 🧪 Development

### Running Tests

```bash
./setup.sh install        # Ensure dependencies
uv run pytest tests/
```

### Adding New Agents

1. Create agent in `src/agents/`
2. Define A2A card in `a2a_cards.py`
3. Add tools in `tools.py`
4. Update `run_adk_demo.py` to spawn agent

### Logs

Logs are written to `logs/` directory:
- `scheduler_agent.log`
- `ui_agent.log`
- OpenTelemetry trace files (`.json`)

## 📄 License

Apache 2.0 - See [LICENSE](../LICENSE)
