# A2A Summit Demo - Python Version

Multi-agent real-time tourist scheduling demonstration using Agent-to-Agent communication patterns.

## Overview
This Python implementation mirrors the Go version's architecture, demonstrating:
- 3 agent types (Tourist, Guide, Scheduler) communicating via pub/sub messaging
- Greedy scheduling algorithm matching tourists to activities
- Real-time re-scheduling on late arrivals
- Transport abstraction ready for A2A SDK integration

## Requirements
- Python 3.9+ (uses `asyncio`, `dataclasses`, type hints)
- No external dependencies for core demo (stdlib only)

## Quick Start

```bash
cd a2a-summit-demo
python3 main.py
```

Expected output:
```
A2A Summit Demo: Multi-Agent Real-Time Tourist Scheduling (Python)
[TouristAgent] Published request for t1
[TouristAgent] Published request for t2
[TouristAgent] Published request for t3
[GuideAgent] Published offer a1 (Museum Tour)
...
[TouristAgent] Accepted proposal p-... with N assignments
--- Simulating late tourist arrival ---
[TouristAgent] Published request for t4
[TouristAgent] Accepted proposal p-... with M assignments
--- Final Assignments ---
Tourist t1 -> Museum Tour at 27 Oct 25 16:30 (cost 60)
...
```

## Architecture

### Agents
| Agent | Role | Implementation |
|-------|------|----------------|
| TouristAgent | Represents tourists | Publishes requests, auto-accepts proposals |
| GuideAgent | Represents guides | Publishes activity offers |
| SchedulerAgent | Cloud coordinator | Runs matching algorithm, publishes proposals |

### Transport Layer
- **Bus interface**: Abstract pub/sub contract (`transport.Bus`)
- **MemoryBus**: In-process implementation for local demo
- **A2ABus** (future): Adapter for real A2A protocol SDK

### Message Types
All messages are JSON-serialized dataclass instances:
- `TouristRequest`: availability windows, budget, preferences
- `GuideOffer`: activity details, slots, capacity, cost
- `ScheduleProposal`: list of tourist→activity assignments
- `Assignment`: single booking (tourist, activity, time, cost)

### Scheduling Algorithm
Greedy heuristic with:
1. Preference scoring (tag overlap ratio)
2. Budget feasibility (remaining budget after assignment)
3. Availability checking (slot within tourist windows)
4. Capacity enforcement (per-activity limits)
5. Overlap prevention (no double-booking tourists)

## Files
```
a2a-summit-demo/
├── main.py          # Entry point, agent logic, scheduling engine
├── transport.py     # Bus abstraction (MemoryBus + A2A stub)
├── scripts/
│   └── test-gpt5.sh # Azure OpenAI model testing
├── go.mod           # (legacy Go version)
├── main.go          # (legacy Go version)
└── README.md        # This file
```

## Extending the Demo

### Add more agents
Subclass or define new handler functions, subscribe to relevant topics.

### Improve scheduling
Replace greedy with:
- Bipartite matching (Hungarian algorithm via `scipy.optimize`)
- Integer linear programming (via `pulp` or `ortools`)
- Multi-objective optimization (fairness + preference + cost)

### Integrate A2A SDK
1. Install A2A Python SDK (when available)
2. Implement `A2ABus` class in `transport.py`
3. Swap `bus = MemoryBus()` → `bus = A2ABus(config)` in `main.py`

### Add persistence
- Store `requests`, `offers`, `assignments` in SQLite or Redis
- Enable restart/recovery without losing state

### Add API layer
- Flask/FastAPI endpoints for external tourist/guide registration
- WebSocket for real-time proposal notifications

## Testing
```bash
# Run with verbose output
python3 -u main.py

# Check imports and syntax
python3 -m py_compile main.py transport.py

# (Optional) Add pytest tests for scheduling logic
pip install pytest
pytest tests/
```

## Comparison with Go Version
| Feature | Go | Python |
|---------|----|----|
| Concurrency | Goroutines + channels | asyncio + threads |
| Transport | interface + impl | ABC + impl |
| Message serialization | json.Marshal/Unmarshal | dataclass + json |
| Scheduling | Same greedy algorithm | Same greedy algorithm |
| Performance | ~instant for demo scale | ~instant for demo scale |

Both versions are functionally equivalent. Choose based on:
- **Go**: Better for production scale, lower latency, easier deployment (single binary)
- **Python**: Faster prototyping, richer AI/ML libraries (if integrating LLMs for smarter scheduling)

## License
Exploratory demo. Not production-ready without additional error handling, auth, monitoring, etc.
