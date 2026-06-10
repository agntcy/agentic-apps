# Avatar agent

Avatar is a human interface agent that uses an LLM to translate natural language
requests into SecOps commands and sends them over SLIM A2A.

## Requirements
- SHADI Python extension available in the runtime.
- SLIM A2A dependencies: `slima2a`, `slimrpc`, `a2a`, `httpx`.
- SecOps A2A server running.
- SHADI secrets set for LLMs under `secops/llm/...`.
- SHADI shared secret for SLIM: `secops/slim_shared_secret` (or override in secops.toml).

## Environment
- `SHADI_OPERATOR_PRESENTATION` (required)
- `SHADI_AVATAR_AGENT_ID` (optional, default `avatar_agent`)
- `SHADI_AVATAR_IDENTITY` (optional, default `agntcy/avatar/client`)

## Run locally
```bash
uv run agents/avatar/adk_agent/run_local.py
```

Example prompt:
```
scan dependabot for the allowlist
```

The agent will translate requests into JSON commands and send them to the SecOps
A2A server.
