# Multi-Agent Tourist Scheduling System

Multi-agent tourist scheduling system with real-time UI and autonomous LLM-powered agents using the official A2A Python SDK.

## 🌟 Features

- **Real-time Web Dashboard**: Live monitoring of agent activities with WebSocket updates
- **Autonomous LLM Agents**: GPT-4o powered guide and tourist agents with intelligent decision-making
- **A2A Protocol Compliance**: Full implementation using official A2A Python SDK
- **Multi-Agent Coordination**: Scheduler orchestrates complex agent interactions
- **Dynamic Market Simulation**: Agents adapt pricing and behavior based on market conditions

## 📁 Project Structure

```
tourist_scheduling_system/
├── src/
│   ├── agents/           # Agent implementations
│   │   ├── scheduler_agent.py        # Central coordinator
│   │   ├── guide_agent.py           # Basic guide agent
│   │   ├── tourist_agent.py         # Basic tourist agent
│   │   ├── ui_agent.py              # Real-time dashboard
│   │   ├── autonomous_guide_agent.py # LLM-powered guide
│   │   └── autonomous_tourist_agent.py # LLM-powered tourist
│   └── core/             # Core components
│       └── messages.py   # Message schemas
├── scripts/                  # Demo and utility scripts
├── tests/                    # Test files
└── slides/                   # Presentation materials
```

## 🚀 Quick Start

### Installation

1. Clone the repository:
```bash
git clone https://github.com/agntcy/agentic-apps.git
cd agentic-apps/tourist_scheduling_system
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
```

3. Install the package:
```bash
pip install -e .
```

### Basic Demo

1. **Start the Scheduler**:
```bash
PYTHONPATH=src python src/agents/scheduler_agent.py --host localhost --port 10010
```

2. **Start the Real-time Dashboard**:
```bash
PYTHONPATH=src python src/agents/ui_agent.py --host localhost --port 10011 --a2a-port 10012
```

3. **Send Agent Interactions**:
```bash
PYTHONPATH=src python src/agents/guide_agent.py --scheduler-url http://localhost:10010 --guide-id "florence-guide"
PYTHONPATH=src python src/agents/tourist_agent.py --scheduler-url http://localhost:10010 --tourist-id "alice-tourist"
```

4. **View Dashboard**: Open http://localhost:10011 to see real-time updates

### 🤖 Autonomous LLM Demo

For Azure OpenAI powered autonomous agents:

1. Set up environment variables:
```bash
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_API_VERSION="2024-08-01-preview"
export AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com/"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o"
```

2. Run the full autonomous demo:
```bash
source ~/.env-phoenix  # If using Phoenix environment
python scripts/run_autonomous_demo.py
```

This starts 5 autonomous agents (3 guides + 2 tourists) with unique AI personalities making intelligent decisions for 10 minutes.

### Unified Script Autonomous Mode (run_with_ui.sh)

You can also launch a timed autonomous session directly via the unified demo script that starts (or reuses) the scheduler and UI dashboard and then runs one autonomous guide + one autonomous tourist agent. This is useful for quick smoke tests without the full multi-agent autonomous swarm.

Flags added to `scripts/run_with_ui.sh`:

```
--autonomous              Enable autonomous pair (guide + tourist)
--auto-guide-id TEXT      Guide agent ID (default: ag-auto)
--auto-tourist-id TEXT    Tourist agent ID (default: at-auto)
--auto-duration INT       Duration in minutes (default: 5)
--no-demo                 Skip sending the basic non-autonomous demo interactions
```

Example (1-minute autonomous run, custom IDs, skip standard demo traffic):

```bash
PYTHONPATH=src scripts/run_with_ui.sh \
	--scheduler-port 10010 \
	--ui-web-port 10011 \
	--ui-a2a-port 10012 \
	--autonomous \
	--auto-duration 1 \
	--auto-guide-id guide-neo \
	--auto-tourist-id tourist-trinity \
	--no-demo
```

Then open the dashboard:

```
http://localhost:10011
```

Log files created in the working directory:

```
autonomous_guide.log
autonomous_tourist.log
scheduler_demo.log (or scheduler_agent_<port>.log on reuse)
ui_demo.log (or ui_agent_<port>.log on reuse)
```

Tail logs while it runs:

```bash
tail -f autonomous_guide.log autonomous_tourist.log
```

When the duration elapses the autonomous agents stop; use Ctrl+C once to trigger cleanup (terminating background processes started by the script).

If Azure OpenAI environment variables are not set, the agents automatically fall back to heuristic decision logic (pricing, availability, budget) and emit a warning line like:

```
WARNING:__main__:[Guide ag-auto] Azure OpenAI env vars missing; falling back to heuristic decisions
```

This mode ensures graceful operation in local dev environments without cloud credentials.


## 🏗️ Architecture

### Agent Types

1. **Scheduler Agent** (A2A Server): Central coordinator using greedy matching algorithm
2. **Guide Agents** (A2A Clients): Offer tour services with availability and pricing
3. **Tourist Agents** (A2A Clients): Request tours with preferences and budgets
4. **UI Agent** (Hybrid): Real-time monitoring dashboard with WebSocket updates
5. **Autonomous Agents**: LLM-powered agents with intelligent decision-making

### Communication Flow

1. Guide agents register availability → Scheduler
2. Tourist agents send requests → Scheduler
3. Scheduler runs matching algorithm → Creates proposals
4. All interactions → UI Agent for real-time visualization

### Message Types

- `GuideOffer`: Guide availability, pricing, and specialties
- `TouristRequest`: Tourist preferences, budget, and availability
- `ScheduleProposal`: Matched tours with assignments
- `Assignment`: Individual tourist-guide pairing

## 🧠 LLM-Powered Features

### Autonomous Guide Agents
- **Dynamic Pricing**: AI adjusts rates based on market conditions
- **Personality-Driven**: Different guide types (Cultural, Foodie, Adventure, History)
- **Market Analysis**: Considers demand, competition, and seasonal factors
- **Intelligent Scheduling**: Optimizes availability windows

### Autonomous Tourist Agents
- **Budget Optimization**: AI determines spending based on trip context
- **Persona-Based Decisions**: Different tourist types (Luxury, Budget, Food Enthusiast)
- **Trip Context Awareness**: Considers purpose, duration, group size
- **Proposal Evaluation**: AI decides whether to accept offers

## 📊 Dashboard Features

- **Real-time Metrics**: Live updates via WebSocket
- **Agent Activity**: Visual representation of all agent communications
- **Success Rates**: Matching efficiency and satisfaction tracking
- **Market Dynamics**: Pricing trends and demand patterns

## 🛠️ Development

### Running Tests
```bash
pytest tests/
```

### Code Formatting
```bash
black src/ tests/
isort src/ tests/
```

### Type Checking
```bash
mypy src/
```

## 📚 Documentation

Legacy documentation and examples have been removed for clarity. Refer to git history if needed. Current authoritative sources are inline code docstrings and this README.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](../LICENSE) file for details.