# k8s-troubleshooting-agent

An AI agent that diagnoses Kubernetes cluster issues and creates Jira tickets for tracking problems. The agent connects to SLIM and uses MCP servers to inspect Kubernetes state and manage Atlassian Jira issues.

## What It Does

- Inspects Kubernetes cluster state through a Kubernetes MCP server
- Analyzes pod health, logs, and events to identify issues
- Checks for duplicate Jira issues before creating new ones
- Automatically creates detailed Jira tickets with relevant logs and diagnostics
- Responds to A2A (Agent-to-Agent) protocol requests from other systems

## Running Locally

1. **Copy the environment template:**
   ```bash
   cp .env.template .env
   ```

2. **Configure your `.env` file:**
   - Set your LLM provider and API key (e.g., `GEMINI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`)
   - Configure SLIM endpoint and credentials
   - Set MCP server endpoints for Kubernetes and Atlassian integration

3. **Install dependencies:**
   ```bash
   uv sync
   ```

4. **Run the agent:**
   ```bash
   uv run python main.py
   ```

The agent will register itself with SLIM and wait for incoming requests.

## Deploying to Kubernetes

The agent can be deployed using the included Helm chart:

```bash
helm install k8s-troubleshooting-agent ./chart \
  --set slim.url=http://your-slim-endpoint:46357 \
  --set slim.secret=your-shared-secret \
  --set model=gemini/gemini-2.0-flash \
  --set apiKey=your-api-key
```

Review and customize `chart/values.yaml` for additional configuration options including:
- SLIM connection settings
- MCP server endpoints
- SPIRE authentication (optional)
- Resource limits and requests

## Key Files

- `main.py` - Entry point that connects the agent to SLIM and MCP servers
- `k8s_troubleshooting_agent/agent.py` - Agent logic and instructions for troubleshooting and ticketing
- `k8s_troubleshooting_agent/mcp_client.py` - MCP client for communicating with K8s and Atlassian servers
- `chart/values.yaml` - Helm chart configuration for Kubernetes deployment
- `.env.template` - Environment variables template for local development
