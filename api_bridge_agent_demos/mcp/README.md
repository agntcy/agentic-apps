# API Bridge Agent MCP demo

This application demonstrates the use of MCP (Model Context Protocol) in API
Bridge Agent.

The role of this application is to take a Github repository as input, analyze
the repository and then look for related contents on DuckDuckGo search engine.

The setup consists of:
- An application developed with the LlamaIndex framework.
- API Bridge Agent configured with at least the Github API, and the DuckDuckGo
MCP server.

# Configuration

## Pre-requisites

* [uv](https://docs.astral.sh/uv/)
* docker
* [API Bridge Agent](https://github.com/agntcy/api-bridge-agnt)
* Workflow Server Manager (optional)

## API Bridge agent configuration

Use [this MCP configuration file](https://github.com/agntcy/api-bridge-agnt/blob/main/configs/mcp.oas.json) as a starting point.

Edit the file to add the DuckDuckGo MCP server:

```json
"mcpServers": {
  "ddg": {
    "command": "uvx",
    "args": ["duckduckgo-mcp-server"]
  }
}
```

Start API Bridge Agent, configure it with MCP, in initialize the MCP servers:

```shell
curl http://localhost:8080/tyk/apis/oas \
  --header 'x-tyk-authorization: foo' \
  --header 'Content-Type: text/plain' \
  -d@configs/mcp.oas.json

curl http://localhost:8080/tyk/reload/group --header 'x-tyk-authorization: foo'

curl http://localhost:8080/mcp/init
```

# Running the application locally

```shell
$ uv run demo --help
Usage: demo [OPTIONS]

Options:
  --repository TEXT      [required]
  --api-bridge-url TEXT
  --help                 Show this message and exit.
```

Check for pages that are related to the 'agntcy/acp-spec' Github repository:

```shell
uv run demo --repository 'agntcy/acp-spec' --api-bridge-url 'http://localhost:8080'
```

# Running the application with the Workflow Server Manager (`wfsm`)

Install the workflow server manager:
<https://docs.agntcy.org/pages/agws/workflow_server_manager.html#installation>

Deploy the application thanks to the `wfsm` and the manifest file:

```
wfsm deploy --manifestPath ./deploy/api_bridge_mcp_demo_manifest.json
```

This will build and run the application inside a docker container, and show a
similar output to the following:

```
[...]

2025-04-24T17:52:50+02:00 INF ---------------------------------------------------------------------
2025-04-24T17:52:50+02:00 INF ACP agent deployment name: org.agntcy.api_bridge_agent_demo_mcp
2025-04-24T17:52:50+02:00 INF ACP agent running in container: org.agntcy.api_bridge_agent_demo_mcp, listening for ACP requests on: http://127.0.0.1:56587
2025-04-24T17:52:50+02:00 INF Agent ID: d7a2714c-b6bb-4248-8144-ec9c57b0e3ea
2025-04-24T17:52:50+02:00 INF API Key: EXAMPLE-API-KEY
2025-04-24T17:52:50+02:00 INF API Docs: http://127.0.0.1:56587/agents/d7a2714c-b6bb-4248-8144-ec9c57b0e3ea/docs
2025-04-24T17:52:50+02:00 INF ---------------------------------------------------------------------

[...]
```

# Calling the application

From the previous step, extract the ACP listening address, agent ID and API key,
and use them to call the application.
Note that because API Bridge Agent is running on the Host, the url needs to be
`http://host.docker.internal:8080`.

```
curl -X 'POST' 'http://127.0.0.1:56587/runs/wait' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: EXAMPLE-API-KEY' \
  -d '{
  "agent_id": "d7a2714c-b6bb-4248-8144-ec9c57b0e3ea",
  "input": {
    "repository": "agntcy/workflow-srv",
    "api_bridge_url": "http://host.docker.internal:8080"
  },
  "config": {
  }
}'
```
