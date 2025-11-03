# UI Agent - Real-time Dashboard

The UI Agent is a new addition to the A2A Summit Demo that provides a real-time web dashboard for monitoring the multi-agent tourist scheduling system.

## Features

### Real-time Monitoring
- **Live Updates**: WebSocket-based real-time updates as the system processes requests
- **System Metrics**: Key performance indicators including tourist satisfaction rate, guide utilization, and average costs
- **Agent Activity**: Monitor tourist requests, guide offers, and schedule assignments in real-time

### Web Dashboard
- **Modern Interface**: Clean, responsive web interface optimized for monitoring
- **Multi-section Layout**: Organized view of tourists, guides, assignments, and system metrics
- **Real-time Charts**: Visual representation of system performance (metrics cards)

### A2A Integration
- **Dual Protocol Support**: Acts as both an A2A agent and web server
- **Message Processing**: Receives and processes messages from other agents in the system
- **Protocol Compliance**: Full A2A protocol implementation for seamless integration

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Tourist       │    │   Scheduler     │    │   Guide         │
│   Agent         │────│   Agent         │────│   Agent         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                │ A2A Messages
                                ▼
                       ┌─────────────────┐
                       │   UI Agent      │
                       │   (A2A + Web)   │
                       └─────────────────┘
                                │
                                │ WebSocket
                                ▼
                       ┌─────────────────┐
                       │   Web Dashboard │
                       │   (Browser)     │
                       └─────────────────┘
```

## Usage

### Starting the UI Agent

#### Option 1: Run with the complete system
```bash
./run_with_ui.sh
```

This script starts:
- UI Agent web dashboard (port 10001)
- UI Agent A2A endpoint (port 10002)
- Scheduler Agent A2A endpoint (port 10000)
- Main demo with tourist and guide agents

#### Option 2: Run UI Agent standalone
```bash
python ui_agent.py --host localhost --port 10001 --a2a-port 10002
```

### Testing the UI Agent
```bash
python test_ui_agent.py
```

This sends sample data to the UI agent to demonstrate real-time updates.

### Accessing the Dashboard

Open your browser and navigate to: `http://localhost:10001`

The dashboard will show:
- **Metrics**: Total tourists, guides, assignments, satisfaction rate, guide utilization, average cost
- **Tourist Requests**: Active tourist requests with budgets and preferences
- **Guide Offers**: Available guides with rates and categories
- **Current Assignments**: Active tourist-guide assignments with costs and timing

## Configuration

### Command Line Options

```bash
python ui_agent.py [OPTIONS]

Options:
  --host TEXT        Server host [default: localhost]
  --port INTEGER     Web dashboard port [default: 10001]
  --a2a-port INTEGER A2A agent port [default: 10002]
  --debug            Enable debug mode
  --help             Show this message and exit
```

### Environment Variables

The UI Agent respects standard A2A environment variables for configuration.

## API Endpoints

### A2A Protocol (port 10002)
- `POST /execute` - Receive messages from other agents
- `GET /health` - Health check endpoint
- `GET /` - Agent card information

### Web API (port 10001)
- `GET /` - Dashboard HTML interface
- `GET /api/state` - Current system state (JSON)
- `WebSocket /ws` - Real-time updates

## Message Types

The UI Agent processes these message types:

### TouristRequest
```json
{
  "type": "TouristRequest",
  "tourist_id": "t1",
  "availability": [...],
  "budget": 200,
  "preferences": ["culture", "food"]
}
```

### GuideOffer
```json
{
  "type": "GuideOffer",
  "guide_id": "g1",
  "categories": ["culture", "food"],
  "available_window": {...},
  "hourly_rate": 80.0,
  "max_group_size": 6
}
```

### ScheduleProposal
```json
{
  "type": "ScheduleProposal",
  "proposal_id": "p-123",
  "assignments": [...]
}
```

## Real-time Features

### WebSocket Updates
The dashboard connects to `/ws` and receives real-time updates:

```javascript
const ws = new WebSocket('ws://localhost:10001/ws');
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  // Handle: tourist_request, guide_offer, schedule_proposal, metrics
};
```

### Update Types
- `initial_state` - Full system state on connection
- `tourist_request` - New tourist request
- `guide_offer` - New guide offer
- `schedule_proposal` - New schedule assignments
- `metrics` - Updated system metrics

## Development

### Dependencies
- FastAPI - Web framework
- WebSockets - Real-time communication
- A2A SDK - Agent protocol implementation
- Uvicorn - ASGI server

### Extending the UI
The dashboard HTML template can be customized in the `HTML_TEMPLATE` variable within `ui_agent.py`. The JavaScript handles WebSocket messages and updates the DOM in real-time.

### Adding New Metrics
Add new metrics to the `SystemMetrics` dataclass and update the `update_metrics()` method to calculate them.

## Troubleshooting

### Common Issues

**Dashboard not updating**
- Check WebSocket connection in browser console
- Verify UI Agent is running on correct ports
- Ensure other agents are sending messages to the UI Agent

**A2A messages not received**
- Verify UI Agent A2A port (10002) is accessible
- Check that other agents are configured to send messages to UI Agent
- Review A2A agent logs for connection issues

**Port conflicts**
- Use different ports with `--port` and `--a2a-port` options
- Check that ports are not already in use

### Debugging
Run with debug mode for detailed logging:
```bash
python ui_agent.py --debug
```

This enables debug-level logging for troubleshooting message processing and WebSocket connections.