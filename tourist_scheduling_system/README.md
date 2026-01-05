# Tourist Scheduling System - ADK Multi-Agent Demo

The **Tourist Scheduling System** is a reference implementation of a multi-agent system built with Google's **Agent Development Kit (ADK)**. It demonstrates how autonomous agents—representing Tourists, Guides, and a Scheduler—can collaborate to solve complex coordination problems in real-time.

This application showcases advanced patterns for building production-ready agentic workflows, including:
*   **Dynamic Service Discovery**: Agents publish their capabilities (A2A Cards) to a central **Agent Directory**, enabling runtime discovery without brittle point-to-point configuration.
*   **Secure Agent-to-Agent (A2A) Communication**: Uses **SLIM (Secure Layer for Intelligent Messaging)** to establish encrypted, authenticated channels between agents.
*   **Observability**: Full integration with **OpenTelemetry** and **Jaeger** to trace requests and tool executions across distributed agent processes.
*   **Human-in-the-Loop**: A real-time **Dashboard** provides visibility into the negotiation and scheduling process.

<img src="docs/tss-demo.gif" alt="TSS Demo" width="800">

## 📑 Table of Contents

- [Features](#-features)
- [Integrations](#-integrations)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [Architecture](#-architecture)
- [SLIM Transport](#-slim-transport)
- [Kubernetes Deployment](#-kubernetes-deployment)
- [Distributed Tracing](#-distributed-tracing)
- [Dashboard Features](#-dashboard-features)
- [CLI Reference](#-cli-reference)
- [Development](#-development)
- [License](#-license)

## ✨ Features

- **Multi-Agent Coordination**: Scheduler, guides, and tourists working together
- **Dynamic Discovery**: Agents register and discover capabilities via the Agent Directory
- **A2A Communication**: Full A2A compliance with SLIM transport support
- **Real-Time Dashboard**: Live monitoring with WebSocket updates
- **Distributed Tracing**: OpenTelemetry integration with Jaeger visualization
- **LLM-Powered Agents**: Azure OpenAI and Google Gemini integration via LiteLLM

## 🔌 Integrations

This application leverages several key integrations to provide a robust, production-ready agent ecosystem:

- **[Agent Directory](https://github.com/agntcy/agent-directory)**: A centralized registry where agents publish their A2A Cards (capabilities) and endpoints. This enables dynamic discovery, allowing the Scheduler to find available Guides and Tourists at runtime.
- **[SLIM Transport](https://github.com/agntcy/slim)**: Secure Layer for Intelligent Messaging. Provides encrypted, authenticated communication channels between agents, ensuring data privacy and integrity.
- **[OpenTelemetry](https://opentelemetry.io/) & [Jaeger](https://www.jaegertracing.io/)**: Comprehensive observability stack. Traces requests across agent boundaries, visualizing the full lifecycle of a scheduling task from Tourist request to Guide assignment.
- **LLM Providers**: Flexible integration with **Azure OpenAI** and **Google Gemini** via LiteLLM, powering the intelligent decision-making of the agents.
- **[FastAPI](https://fastapi.tiangolo.com/)**: High-performance web framework used for the Agent Directory and agent HTTP interfaces.

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [UV](https://github.com/astral-sh/uv) package manager
- Docker (for SLIM transport and tracing)
- Azure OpenAI API key or Google Gemini API key

### Installation

```bash
# Clone the repository
git clone https://github.com/agntcy/agentic-apps.git
cd agentic-apps/tourist_scheduling_system

# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv sync

# Configure Azure OpenAI
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com"

# Or Configure Google Gemini
export MODEL_PROVIDER="gemini"
export GOOGLE_GEMINI_API_KEY="your-google-api-key"
# Optional: Specify model (default: gemini/gemini-3-pro-preview)
export MODEL_NAME="gemini/gemini-3-pro-preview"
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

### Running the Frontend (Optional)

The system includes a modern Flutter-based frontend for a richer user experience.

**Prerequisites:**
- [Flutter SDK](https://docs.flutter.dev/get-started/install) installed

**Launch Instructions:**

1.  Ensure the backend agents are running (see "Run the Demo" above).
2.  Open a new terminal window.
3.  Navigate to the frontend directory and launch the app:

```bash
cd frontend
./setup.sh
flutter run -d web-server
```

4.  Open the URL provided by Flutter (typically `http://localhost:web-port`) in your browser.

## 📁 Project Structure

```
tourist_scheduling_system/
├── src/
│   ├── agents/                  # Agent implementations
│   │   ├── scheduler_agent.py   # Main scheduler (A2A server, port 10000)
│   │   ├── ui_agent.py          # Dashboard web app (A2A server, port 10021)
│   │   ├── guide_agent.py       # Tour guide agent (A2A client)
│   │   ├── tourist_agent.py     # Tourist agent (A2A client)
│   │   └── tools.py             # ADK tools (register, match, etc.)
│   └── core/                    # Core utilities
│       ├── a2a_cards.py         # Agent A2A card definitions
│       ├── dashboard.py         # Starlette dashboard app
│       ├── models.py            # Pydantic data models
│       ├── slim_transport.py    # SLIM transport adapter
│       ├── tracing.py           # OpenTelemetry setup
│       ├── messages.py          # Message types
│       └── logging_config.py    # Logging configuration
├── scripts/                     # Shell scripts for infrastructure
│   ├── spire.sh                 # SPIRE server/agent deployment
│   ├── slim-controller.sh       # SLIM controller deployment
│   ├── slim-node.sh             # SLIM data plane node deployment
│   ├── directory.sh             # Agent Directory deployment
│   ├── run_adk_demo.py          # Main demo runner (Python CLI)
│   ├── slim-control-csid.yaml.tpl # SPIRE ID template for Controller
│   ├── slim-node-csid.yaml.tpl    # SPIRE ID template for Node
│   └── *-values.yaml            # Helm values files
├── deploy/
│   └── k8s/                     # Kubernetes manifests
│       ├── namespace.yaml       # Namespace and ConfigMap
│       ├── scheduler-agent.yaml # Scheduler Deployment
│       ├── ui-agent.yaml        # UI Dashboard Deployment
│       ├── guide-agent.yaml     # Sample guide agent Jobs
│       ├── tourist-agent.yaml   # Sample tourist agent Jobs
│       ├── deploy.sh            # Deployment helper script
│       ├── spawn-agents.sh      # Scale multiple guides/tourists
│       ├── templates/           # Job templates for dynamic generation
│       └── README.md            # K8s deployment docs
├── setup.sh                     # Local infrastructure management
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
| **Directory** | 8888 | Service registry for agent discovery |

### Communication Flow

```
                                   ┌──────────────┐
                                   │   Directory  │
                                   │  (port 8888) │
                                   └──────▲───────┘
                                          │ Register/Lookup
                                          │
┌──────────────┐     A2A/SLIM      ┌──────▼───────┐
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
./setup.sh slim start

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

## ☸️ Kubernetes Deployment

Deploy the Tourist Scheduling System to Kubernetes with support for both HTTP and SLIM transport modes.

### Prerequisites

- Kubernetes cluster (MicroK8s, GKE, EKS, etc.)
- `kubectl` configured
- `envsubst` (comes with gettext)
- Container images pushed to registry

### Quick Deploy

```bash
cd deploy/k8s

# Set environment
export NAMESPACE=lumuscar-jobs
export IMAGE_REGISTRY=ghcr.io/agntcy/apps
export IMAGE_TAG=latest

# Deploy with HTTP transport (default)
./deploy.sh http

# Or deploy with SLIM transport (requires SLIM infrastructure)
./deploy.sh slim

# Create secrets
kubectl create secret generic azure-openai-credentials \
  --from-literal=api-key=$AZURE_OPENAI_API_KEY \
  --from-literal=endpoint=$AZURE_OPENAI_ENDPOINT \
  --from-literal=deployment-name=${AZURE_OPENAI_DEPLOYMENT_NAME:-gpt-4o} \
  -n $NAMESPACE

# Check status
./deploy.sh status
```

### SLIM Infrastructure Setup

For SLIM transport with mTLS authentication (via SPIRE):

```bash
# Install SPIRE (identity provider)
./scripts/spire.sh install

# Install SLIM controller (with SPIRE enabled)
export SPIRE_ENABLED=true
./scripts/slim-controller.sh install

# Install SLIM node (with SPIRE enabled)
# Default strategy is StatefulSet
export SPIRE_ENABLED=true
./scripts/slim-node.sh install

# Or install SLIM node as DaemonSet
export SLIM_STRATEGY=daemonset
export SPIRE_ENABLED=true
./scripts/slim-node.sh install

# Install Agent Directory (optional)
./scripts/directory.sh install

# Verify
./scripts/spire.sh status
./scripts/slim-controller.sh status
./scripts/slim-node.sh status
```

### Manual Deployment

```bash
# Using envsubst for variable substitution
export NAMESPACE=lumuscar-jobs
export IMAGE_REGISTRY=ghcr.io/agntcy/apps
export IMAGE_TAG=latest
export TRANSPORT_MODE=http  # or slim

# Apply manifests
envsubst < deploy/k8s/namespace.yaml | kubectl apply -f -
envsubst < deploy/k8s/scheduler-agent.yaml | kubectl apply -f -
envsubst < deploy/k8s/ui-agent.yaml | kubectl apply -f -

# Run client agents (Jobs)
envsubst < deploy/k8s/guide-agent.yaml | kubectl apply -f -
envsubst < deploy/k8s/tourist-agent.yaml | kubectl apply -f -
```

### Scaling Multiple Agents

Spawn many guides and tourists with randomized configurations:

```bash
cd deploy/k8s

# Spawn 10 guides and 50 tourists
./spawn-agents.sh guides 10
./spawn-agents.sh tourists 50

# Or spawn both at once
./spawn-agents.sh both 10 50

# Check status
./spawn-agents.sh status

# Clean up
./spawn-agents.sh clean
```

See [deploy/k8s/README.md](deploy/k8s/README.md) for full documentation.

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
--provider NAME           # Model provider: azure (default) or google
--tracing                 # Enable OpenTelemetry tracing
--scheduler-port N        # Scheduler port (default: 10000)
--ui-port N               # Dashboard port (default: 10021)
--guides N                # Number of guides (default: 2)
--tourists N              # Number of tourists (default: 3)
--duration N              # Duration in minutes (0=single run)
--interval N              # Delay between requests (default: 1.
--real-agents             # Use real ADK guide/tourist agents instead of simulation0s)
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
# Required (Choose one provider)
export AZURE_OPENAI_API_KEY="your-key"
# OR
export GOOGLE_GEMINI_API_KEY="your-google-api-key"

# Optional
export MODEL_PROVIDER="openai"                 # or "gemini"
export MODEL_NAME="gemini/gemini-3-pro-preview" # for Gemini
export AZURE_OPENAI_ENDPOINT="https://..."
export TRANSPORT=slim                          # Default transport
export SLIM_ENDPOINT=http://localhost:46357    # SLIM node URL
export SLIM_SHARED_SECRET=your-secret          # SLIM auth secret
export SCHED_PORT=10000                        # Scheduler port
export UI_PORT=10021                           # Dashboard port
export DIR_PORT=8888                           # Agent Directory port
export DIRECTORY_CLIENT_SERVER_ADDRESS=localhost:8888 # Directory address
```

## 🧪 Development

### Running Tests

uv sync
./setup.sh install        # Ensure dependencies
uv run pytest tests/
```

### Adding New Agents

1. Create agent in `src/agents/`
2. Define A2A card in `src/core/a2a_cards.py`
3. Add tools in `src/agents/tools.py`
4. Update `run_adk_demo.py` to spawn agent

### Logs

Logs are written to `logs/` directory:
- `scheduler_agent.log`
- `ui_agent.log`
- OpenTelemetry trace files (`.json`)

## 📄 License

Apache 2.0 - See [LICENSE](../LICENSE)
