# Avatar Agent Guide

## Overview
The Avatar agent provides an interactive ADK interface and routes commands to
SecOps over SLIM A2A.

## Key environment variables
- SHADI_OPERATOR_PRESENTATION: Required to access secrets in SHADI.
- SHADI_SECOPS_CONFIG: Path to a secops config TOML (default: secops.toml).
- SHADI_AVATAR_IDENTITY: Agent identity used for SLIM A2A.
- SHADI_TMP_DIR: Base directory for memory defaults (default: ./.tmp).
- SHADI_AGENT_ID: Optional agent-specific suffix for isolation.
- SHADI_ADK_MEMORY_DB: Optional override for ADK memory persistence.
- SLIM_TLS_CERT, SLIM_TLS_KEY, SLIM_TLS_CA: Client TLS material for SLIM.

## Common workflows

### Run the interactive Avatar agent (SHADI-backed memory)
```bash
export SHADI_OPERATOR_PRESENTATION="local-operator"
export SHADI_AGENT_ID="avatar-1"
export SHADI_TMP_DIR="./.tmp"
export SHADI_SECOPS_CONFIG=./.tmp/secops-a.toml
export SHADI_POLICY_PATH=./policies/demo/avatar.json
export SLIM_TLS_CERT=./.tmp/shadi-slim-mtls/client-avatar.crt
export SLIM_TLS_KEY=./.tmp/shadi-slim-mtls/client-avatar.key
export SLIM_TLS_CA=./.tmp/shadi-slim-mtls/ca.crt
./scripts/launch_avatar.sh
```

## Notes
- The Avatar agent expects a running SecOps A2A server on the configured
  SLIM endpoint and shared secret stored in SHADI.
- Memory defaults to $SHADI_TMP_DIR/$SHADI_AGENT_ID/shadi-secops/secops_memory.db
  unless overridden by SHADI_ADK_MEMORY_DB.
- To target a specific repo say "scan agentic-apps" or "remediate agntcy/agentic-apps".
  The avatar will set `repos` in the SecOps command so only that repo is processed.
  Omit the repo name to operate on all allowlisted repos.
