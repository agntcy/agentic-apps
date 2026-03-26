# ADK Demo (SHADI)

This demo shows how to access SHADI secrets from a Python agent process.
Use it as a starting point to integrate a Google ADK agent or a SLIM-enabled
agentic app.

## Notes
- The session uses a local verified flag for demo only.
- Replace the session verification with DID/VC checks in production.
- Build the Python extension and import `shadi` before running the demo.
- The Tourist demo runs the sandbox via Python bindings (no `shadictl` CLI).

## Tourist scheduling system demo

To run the Tourist/Guide agents from agentic-apps with explicitly disclosed demo secrets:

```bash
export AGENTIC_APPS_PATH=/path/to/agentic-apps
export TOURIST_CMD="python your_entrypoint.py"
just demo-tourist
```

## SecOps autonomous agent

This agent runs locally and monitors GitHub security issues, preparing
remediation PRs using credentials stored in SHADI.

Configuration lives in the repo root at secops.toml. You can override the path
with SHADI_SECOPS_CONFIG.

```bash
export GITHUB_TOKEN="$(gh auth token)"
export SHADI_OPERATOR_PRESENTATION="local-operator"
uv run agents/secops/import_secops_secrets.py
uv run agents/secops/secops.py
```
