# SecOps Agent Guide

## Overview
The SecOps agent scans allowlisted repositories, generates LLM-written security
reports, and can optionally remediate critical vulnerabilities by opening PRs via
`gh` CLI. It operates as a standalone local agent or as an A2A server behind SLIM.

All GitHub operations use the `gh` CLI authenticated via `GH_TOKEN` from SHADI —
no raw token headers, no interactive prompts.

## Key environment variables
| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `SHADI_OPERATOR_PRESENTATION` | **Yes** | — | SHADI session identity proof |
| `SHADI_SECOPS_CONFIG` | No | `secops.toml` | Path to agent config TOML |
| `SHADI_TMP_DIR` | No | `./.tmp` | Base dir for workspace and memory |
| `SHADI_AGENT_ID` | No | — | Agent-specific subdirectory suffix |
| `SHADI_SECRET_BACKEND` | No | `keychain` | `onepassword` to use 1Password |
| `SHADI_OP_ACCOUNT` | No | `my.1password.com` | 1Password account identifier |
| `SHADI_HUMAN_GITHUB` | No | — | GitHub handle for fork/PR ownership (fallback if not in config) |
| `SHADI_SECOPS_MEMORY_DB` | No | auto-derived | Override SQLCipher memory DB path |
| `SLIM_TLS_CERT` | No* | auto-derived | mTLS client certificate (*required when `slim_tls_insecure=false`) |
| `SLIM_TLS_KEY` | No* | auto-derived | mTLS client key |
| `SLIM_TLS_CA` | No* | auto-derived | mTLS CA certificate |
| `SHADI_OTEL_CONSOLE` | No | — | Set `1` to print OpenTelemetry spans to stdout |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | — | OTLP endpoint for trace export |

## SLIM A2A command interface

The A2A server listens on a SLIM channel. Commands are plain text or JSON objects.

### Commands

#### `scan` (or `run_scan`)
Collect Dependabot alerts + security-labeled issues, generate LLM report, save to memory.

```json
{
  "command": "scan",
  "labels": "security,cve,vulnerability",
  "provider": "google",
  "report_name": "secops_security_report.md"
}
```
All fields except `command` are optional.

#### `remediate` (or `run_remediate`)
Run `scan` then attempt patch commits and optionally open PRs.

For **each** allowlisted repository (or the subset specified by `repos`) the agent will:
1. Fork the upstream repo via `gh api repos/{repo}/forks` (skipped if fork already exists).
2. Sync the fork's default branch with `git fetch upstream && git reset --hard upstream/HEAD`.
3. Clone the fork locally under the workspace directory.
4. Search the local clone's filesystem for Dockerfiles matching the affected image or service name.
5. For container CVEs, prefer rebuilding the image and, when the scan indicates the issue comes from the base image lineage, refresh the `FROM` image/tag instead of adding ad-hoc package upgrade lines.
6. If a container finding only needs rebuild guidance, record that guidance in the remediation output or issue rather than mutating the `Dockerfile`.
7. Commit safe source changes on a dated branch `secops/remediate-YYYYMMDD` and push to the fork.

Fork names follow `{fork_owner}/{repo-name}`. Branch names follow `secops/remediate-YYYYMMDD`.

```json
{
  "command": "remediate",
  "labels": "security,cve,vulnerability",
  "provider": "google",
  "report_name": "secops_security_report.md",
  "create_prs": false,
  "human_github": "alice",
  "repos": "agntcy/agentic-apps"
}
```

- `create_prs=false` — pushes changes to fork, queues PRs in `secops_pending_prs.json`
- `create_prs=true` — opens PRs immediately via `gh api repos/{repo}/pulls`
- `human_github` — overrides `SHADI_HUMAN_GITHUB` and config `secops.human_github`
- `repos` — **optional** comma-separated `owner/name` list; when set only those repos are
  scanned and remediated (must be a subset of the configured allowlist). Omit to operate
  on all allowlisted repos.

#### `approve_prs` (or `approve`)
Read `secops_pending_prs.json`, open PRs for all queued entries.

```json
{"command": "approve_prs"}
```

#### `report` (or `get_report`)
Return the raw text of the latest report file.

```json
{"command": "report", "report_name": "secops_security_report.md"}
```

#### `status` (or `info`)
Show current SLIM + workspace config and allowlist.

```json
{"command": "status"}
```

#### `allowlist` (or `repos`)
List the allowlisted repositories.

```json
{"command": "allowlist"}
```

#### `help` (or `commands`)
Return the full command reference with example payloads.

```json
{"command": "help"}
```

## Memory structure
- **SQLCipher DB**: `$SHADI_TMP_DIR/$SHADI_AGENT_ID/shadi-secops/secops_memory.db`
  - Encrypted with key `secops/memory_key` from SHADI.
  - Scope `secops`, entry keys: `security_report`, `security_report_YYYY-MM-DD`.
- **ADK memory**: sessions auto-saved via `after_agent_callback` in `agent.py`.
- **Pending PRs**: `$workspace/secops_pending_prs.json` (deleted after `approve_prs`).

## Notes
- Workspace defaults to `$SHADI_TMP_DIR/$SHADI_AGENT_ID/shadi-secops` unless
  overridden in `secops.toml` via `secops.workspace_key`.
- Memory DB defaults to `<workspace>/secops_memory.db` unless overridden by
  `SHADI_SECOPS_MEMORY_DB` or `SHADI_MEMORY_DB`.
