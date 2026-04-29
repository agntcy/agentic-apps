---
name: secops
description: Collects security alerts and issues for allowlisted GitHub repos, writes a report, and supports remediation planning. Use when you need a SecOps agent to monitor Dependabot alerts or security-labeled issues under SHADI sandbox constraints.
license: Apache-2.0
compatibility: Requires git, gh CLI, internet access to api.github.com, SHADI Python extension, and a GitHub token stored in SHADI.
metadata:
  framework: google-adk
  version: "1.1"
---

# SecOps Autonomous Remediation (Google ADK)

## Overview
This skill enables a SecOps agent to monitor GitHub security alerts for an
allowlist of repositories, generate remediation plans, and open pull requests
using credentials stored in SHADI. The agent is designed to run locally inside
SHADI sandbox constraints.

All GitHub CLI operations (`gh`) use `GH_TOKEN` injected from SHADI — no
interactive login is required.

## Tools

The skill exposes seven focused tools. The LLM chains them based on AGENTS.md
and this file — no single "do everything" function.

### `fetch_security_alerts(labels="security,cve,vulnerability", repos=None)`
Fetch Dependabot alerts, GitHub Code Scanning alerts (Trivy/SARIF), and
labeled issues for all allowlisted repos. Saves raw JSON to
`secops_raw_alerts.json` in the workspace. **Call this first.**

Code Scanning alerts are fetched via `gh api repos/{repo}/code-scanning/alerts`
(requires `security_events` read scope). Repos with Advanced Security disabled
return an empty list (not an error).

`repos` — optional comma-separated `owner/name` string (or list for JSON callers).
Must be a subset of the configured allowlist. When omitted, all allowlisted repos
are scanned.

Returns: `{status, dependabot_alerts, code_scanning_alerts, labeled_issues, repos, raw_data_path}`

### `generate_security_report(report_name="secops_security_report.md", provider=None, human_github_handle=None)`
Read the saved raw data, call the LLM, write a Markdown report, and save a
memory entry. Must be called after `fetch_security_alerts`.

Returns: `{status, report_path, dependabot_alerts, labeled_issues, memory}`

### `remediate_vulnerabilities(human_github_handle=None, create_prs=False, repos=None)`
Patch critical/high alerts from the saved raw data. Handles two classes of
findings:

`repos` — optional comma-separated `owner/name` string (or list for JSON callers).
Filters the saved alert data to only the specified repos. Use this when the user
asks to remediate a specific repo rather than everything in the allowlist.

**Dependency alerts (Dependabot):** updates `requirements.txt`, `package.json`,
or lock files where a safe patched version is available.

**Container CVE alerts (Code Scanning / Trivy):** for each repo the agent will:
1. Fork the upstream repo via `gh api repos/{repo}/forks` (or reuse an existing fork).
2. Sync the fork: `git fetch upstream && git reset --hard upstream/HEAD`.
3. Clone the fork locally into the workspace directory.
4. Enumerate all `Dockerfile`s in the local clone (skips `.git`, `node_modules`, `vendor`).
5. Match each Trivy alert to the correct Dockerfile using the service/image name extracted
   from the SARIF artifact path, alert location, or rule description.
6. Prefer a clean image refresh path:
  - rebuilding the image is usually enough for CVEs to disappear on the next scan,
  - if the scan indicates the vulnerable package comes from the base image lineage, update the `FROM` image/tag and rebuild,
  - do not add ad-hoc OS package installation or upgrade lines to the `Dockerfile` just to silence the scan.
7. If a container finding requires follow-up but does not produce a safe code change, the agent opens or recommends a remediation issue instead of polluting the `Dockerfile`.
8. Commit on `secops/remediate-YYYYMMDD` branch only when there is an actual safe source change, push to fork, optionally open PR.

Must be called after `fetch_security_alerts`.

Returns: `{status, remediation}` — see status codes below.

### `approve_queued_prs()`
Open PRs for all entries in `secops_pending_prs.json` after human review.

Returns: `{repo: {status, pr_url, ...}, ...}`

### `get_latest_report(report_name="secops_security_report.md")`
Return the text of the latest saved report. Use instead of re-scanning when
the user asks to "show the report" or "read the findings."

Returns: `{status, path, report}`

### `get_allowlist()`
Return the configured repo allowlist from `secops.toml`.

Returns: `{status, allowlist}`

### `get_agent_status()`
Return workspace path, allowlist, and SLIM connection config.

Returns: `{status, config, workspace, allowlist, slim_endpoint, slim_identity}`

### `lookup_cve(cve_id="", package_name="", max_results=5)`
Query the [NIST NVD](https://nvd.nist.gov/) database for a specific CVE or a
package-name keyword. Returns CVSS score and severity, full description, CWE
weakness IDs, and reference URLs (vendor advisories, patch releases).

Use this to enrich scan results with authoritative remediation guidance:
- Prefer `cve_id` when a Dependabot alert already contains a CVE identifier.
- Use `package_name` (e.g. `"requests 2.28"`) for keyword searches.
- `max_results` caps keyword results (1–20, default 5).
- Set `NVD_API_KEY` env var to raise the rate limit from 5 to 50 req/30 s.

Returns:
```
{
  "status": "ok" | "not_found" | "error" | "rate_limited",
  "cves": [
    {
      "id": str,
      "published": str,
      "last_modified": str,
      "description": str,
      "cvss_v3": {"score": float, "severity": str, "vector": str} | null,
      "cvss_v2": {"score": float, "severity": str} | null,
      "cwe": [str],
      "references": [str]
    }
  ],
  "total_results": int
}
```

## Decision guide for the LLM

| User intent | Tools to call (in order) |
|-------------|--------------------------|
| "scan", "check alerts", "run report" | `fetch_security_alerts` → `generate_security_report` |
| "remediate", "patch vulnerabilities" | `fetch_security_alerts` → `generate_security_report` → `remediate_vulnerabilities` |
| "remediate and open PRs" | same as above with `create_prs=True` |
| "fix container CVEs", "patch Dockerfiles" | `fetch_security_alerts` → `remediate_vulnerabilities` (produces rebuild/base-image guidance and only updates `FROM` lines when the scan clearly supports it) |
| "remediate only agentic-apps" (specific repo) | `fetch_security_alerts(repos="agntcy/agentic-apps")` → `remediate_vulnerabilities(repos="agntcy/agentic-apps")` |
| "approve PRs" | `approve_queued_prs` |
| "show report", "latest findings" | `get_latest_report` (no re-scan needed) |
| "what repos are monitored" | `get_allowlist` |
| "status", "configuration" | `get_agent_status` |
| "look up CVE-XXXX", "what is CVE-XXXX" | `lookup_cve(cve_id="CVE-XXXX")` |
| "CVE details for <package>" | `lookup_cve(package_name="<package>")` |
| scan result has CVE IDs → enrich with NVD | `lookup_cve` once per unique CVE ID in alerts |
## Remediation status codes per repo

| Code | Meaning |
|------|---------|
| `no_actionable_alerts` | No critical/high Dependabot or Code Scanning alerts |
| `no_changes` | Patch applied but diff was empty |
| `pr_created` | PR opened via `gh pr create`; `pr_url` present |
| `pending_pr_approval` | Branch `fix/secops-remediate-YYYYMMDD` pushed to fork; PR queued for `approve_queued_prs` |
| `fork_sync_failed` | Could not resolve upstream base branch |
| `pr_failed` | `gh pr create` failed; `error` has details |

### Container CVE remediation status codes (per alert)

| Code | Meaning |
|------|---------|
| `base_image_refresh_recommended` | Rebuild the image and prefer a base-image tag refresh over package-layer Dockerfile edits |
| `base_image_review_required` | Dockerfile found, but the base image could not be resolved cleanly; review the scan and image lineage manually |
| `no_package` | Trivy message did not include a parseable package name |
| `no_dockerfile_found` | Could not locate a Dockerfile for this image in the repo (checked: direct path, `**/service-name/Dockerfile`, fuzzy parent-dir match, SARIF artifact parent) |
| `analysis_error` | Filesystem or analysis error while deriving remediation guidance; `error` field has details — other alerts continue |

## Parameter guidance

| Parameter | Default | When to set |
|-----------|---------|-------------|
| `labels` | `"security,cve,vulnerability"` | Pass through; user can override |
| `report_name` | `"secops_security_report.md"` | Change only if user asks for custom filename |
| `provider` | `None` (reads from SHADI) | Pass only if user explicitly names a provider |
| `human_github_handle` | `None` (reads from config/env) | Pass only if user specifies a GitHub handle |
| `create_prs` | `False` | `True` only when user explicitly says "create PRs" |

## Scope
- Repo allowlist only (no org-wide access).
- Security signals:
  - Dependabot alerts (GitHub Dependabot API, `state=open`).
  - GitHub Code Scanning alerts (SARIF/Trivy, `state=open`) — container image CVEs.
- Actionable severity: `critical`, `high`, `error`, and `warning` for Code Scanning.
- Actions: report, triage, plan; optional PR creation for safe dependency upgrades and base-image updates.
- Human-in-the-loop: required before merge; never auto-merge.

## Inputs

### SHADI secrets (resolved automatically — do not ask the user for these)
| Key | Purpose |
|-----|---------|
| `secops/github_token` | GitHub API + gh CLI authentication |
| `secops/workspace_dir` | Base path for clones and reports |
| `secops/llm/provider` | LLM provider name (`openai`, `google`, `anthropic`, `azure`) |
| `secops/llm/openai_api_key` | OpenAI or proxy API key |
| `secops/llm/openai_endpoint` | OpenAI-compatible base URL |
| `secops/llm/openai_model` | Model name (e.g. `gpt-4o`, `vertex_ai/gemini-3-pro`) |
| `secops/llm/google_api_key` | Google-native API key |
| `secops/llm/google_model` | Google model name |
| `secops/llm/claude_api_key` | Anthropic API key |
| `secops/llm/claude_model` | Claude model name |
| `secops/llm/azure_openai_api_key` | Azure OpenAI API key |
| `secops/llm/azure_openai_endpoint` | Azure OpenAI endpoint |
| `secops/llm/azure_openai_deployment_name` | Azure deployment name |
| `secops/llm/azure_openai_api_version` | Azure API version |
| `secops/memory_key` | Encryption key for SQLCipher memory DB |
| `secops/slim_shared_secret` | SLIM channel shared secret |

### Config file (`secops.toml` or `$SHADI_SECOPS_CONFIG`)
```toml
[secops]
allowlist = ["org/repo1", "org/repo2"]
human_github = "alice"        # GitHub handle for fork/PR ownership
auto_remediate = false        # Set true to remediate on every scan
auto_pr = false               # Set true to always create PRs

# Git identity for commits created by the agent (optional, falls back to
# SHADI_GIT_NAME / SHADI_GIT_EMAIL / global git config)
git_name  = "Alice SecOps Bot"
git_email = "alice@example.com"

# SSH public key for commit signing via 1Password (gpg.format = ssh).
# OPTIONAL — defaults to reading user.signingkey / gpg.format / gpg.ssh.program
# from the user's global git config, so no entry here is needed if the global
# git config already has 1Password SSH signing configured (commit.gpgsign=true).
# Override only if you need a different key or path for the agent's commits.
# git_signing_key = "ssh-ed25519 AAAA..."  # leave unset to inherit from global git config

[github]
api_base = "https://api.github.com"

[secops.slim]
identity = "agntcy/secops/agent"
endpoint = "http://localhost:47357"
```

### Environment (required at startup)
- `SHADI_OPERATOR_PRESENTATION` — must be non-empty to verify the SHADI session
- `SHADI_HUMAN_GITHUB` — fallback for fork/PR ownership if not in config
- `SLIM_TLS_CERT`, `SLIM_TLS_KEY`, `SLIM_TLS_CA` — mTLS material for SLIM

## Outputs
- `secops_security_report.md` in the workspace directory (LLM-generated Markdown).
- Remediation PRs on GitHub (when `remediate=True` and `create_prs=True`).
- Remediation issue per repo linked to each PR via `Fixes #N`.
- `secops_pending_prs.json` in workspace (when `create_prs=False` but changes are pushed).
- Memory entry saved to the SQLCipher store for recall in future sessions.

## Preconditions
- SHADI Python extension installed in the runtime environment.
- `gh` CLI installed and reachable on `$PATH`.
- GitHub token has: `repo` scope for allowlisted repos, `security_events` read.
- Operator presentation is set in `SHADI_OPERATOR_PRESENTATION`.

## Permissions
- GitHub API: read Dependabot alerts, read/write issues, read/write pull requests.
- GitHub Code Scanning API: read `security_events` (required for container CVE alerts).
- Fork access: create and update forks under `human_github_handle`.
- `gh` CLI: uses `GH_TOKEN` from SHADI — no interactive prompt.
- Clones repos via `gh repo clone <owner/repo> <absolute-path>` to the workspace.

## Safety & Policy
- **Never** operate on repos outside the allowlist.
- **Never** merge PRs automatically — require explicit human approval.
- **Never** write secrets to disk or include them in commit messages.
- **Always** use Conventional Commits format for automated commits.
- **Always** sign commits with `--signoff`.
- All actions are traced via OpenTelemetry spans attached to `tracer`.

## Workflow
1. Load config (`secops.toml`) and establish a SHADI session (`SHADI_OPERATOR_PRESENTATION`).
2. Retrieve GitHub token, workspace path, and LLM settings from SHADI secrets.
3. Fetch open Dependabot alerts (`state=open`) for each repo on the allowlist.
4. Fetch security-labeled issues for each repo.
5. Resolve `human_github_handle`: function arg → `secops.human_github` in config → `SHADI_HUMAN_GITHUB` env var.
6. Optionally look up `github/<handle>/did` in SHADI (non-throwing; skip if absent).
7. Call the LLM to generate a Markdown report with executive summary, critical findings, and per-repo remediation plan.
8. Write the report to `<workspace>/<report_name>`.
9. If `remediate=True`:
   a. For each repo with critical/high alerts that have a patch version:
      1. **Fork** — check if a fork already exists under `human_github_handle`:
         - Query `gh api repos/{fork_owner}/{repo}`. If found, use it.
         - If not found, check for a renamed fork: `gh api repos/{upstream}/forks --jq`.
         - If still not found, create via `gh api repos/{upstream}/forks --method POST`.
         - Wait up to 10 s for the fork to be ready.
      2. **Sync fork with upstream** — if already cloned locally:
         - `git fetch origin` (update fork remote)
         - `git fetch upstream` then `git reset --hard upstream/<base>` then `git push origin <base> --force`
         - Abort with `skipped_dirty_repo` if the working tree is dirty.
         - If not yet cloned: `gh repo clone {fork_owner}/{repo} <workspace_dir>`
      3. **Create fix branch** — `git checkout -b fix/secops-remediate-YYYYMMDD`
      4. **Apply patches** — `Cargo.toml` bumps + `cargo update`, `package.json` bumps + `npm install`, `uv.lock` bumps via `uv lock --upgrade-package`, `FROM` line updates in Dockerfiles when the remediation is a base-image refresh.
      5. **Commit** — `git add -A` then `git commit -s -S -m "chore(secops): remediate critical vulnerabilities"` using Conventional Commits format. `-s` adds a `Signed-off-by` trailer; `-S` GPG-signs the commit.
      6. **Push** — `git push origin fix/secops-remediate-YYYYMMDD` (push to fork).
      7. **Open remediation issue** on the upstream repo via `gh api repos/{upstream}/issues`.
      8. **Create PR** — if `create_prs=True`:
         `gh pr create --repo {upstream} --head {fork_owner}:fix/secops-remediate-YYYYMMDD --base {base_branch} --title "..." --body "Fixes #{issue_number}"`
         - If `create_prs=False`: write PR metadata to `secops_pending_prs.json` for later `approve_queued_prs`.
10. Save a summary to the SQLCipher memory store under scope `secops`, keys `security_report` and `security_report_YYYY-MM-DD`.

## Memory

- After `generate_security_report`, a summary is saved to the encrypted SQLCipher
  store (scope `secops`, key `security_report`).
- Use the `PreloadMemoryTool` and `load_memory` tools to recall prior runs.
- Do not ask the user for memory DB paths — resolved automatically from env and config.

## LLM provider resolution

Provider is read from SHADI secret `secops/llm/provider`. If the provider is
`google` or `anthropic` but an `openai_api_key` is also present, the OpenAI-
compatible proxy path is used automatically.

Supported values: `openai`, `google`, `anthropic`, `claude`, `azure`, `azure_openai`.

## Error handling guidance

| Error message | Likely cause | What to tell the user |
|---------------|-------------|----------------------|
| `SHADI_OPERATOR_PRESENTATION must be set` | Missing env var | `export SHADI_OPERATOR_PRESENTATION="local-operator"` |
| `Missing GitHub token in SHADI` | Secrets not imported | `uv run agents/secops/import_secops_secrets.py` |
| `No alert data found. Call fetch_security_alerts first` | Wrong tool call order | Call `fetch_security_alerts` before `generate_security_report` or `remediate_vulnerabilities` |
| `gh CLI is required` | `gh` not on PATH | Install GitHub CLI (`brew install gh`) |
| `fork not ready for <owner>/<repo>` | GitHub fork creation delay | Transient; suggest retrying |
| `pr_failed` in remediation | PR already exists or branch conflict | Show the `error` field from the result |
| `skipped_dirty_repo` | Fork clone has uncommitted changes | `git -C <dir> checkout -- .` |
| `status: rate_limited` from `lookup_cve` | NVD public rate limit (5 req/30 s) | Set `NVD_API_KEY` env var; free key at nvd.nist.gov/developers/request-an-api-key |
| `status: not_found` from `lookup_cve` | CVE ID not in NVD yet | CVE may be under review; use `package_name` search instead |

## Notes for ADK integration
- All 8 tools are registered directly in `agent.py` — the LLM picks them autonomously.
- The agent instruction is built by concatenating `AGENTS.md` + `SKILL.md` at startup.
- Do not duplicate workflow logic in the instruction string; rely on this file.
- Require operator confirmation before setting `create_prs=True`.
- The `after_agent_callback` in `agent.py` auto-saves each session to ADK memory.

## Evals

Test cases are in `evals/evals.json`. Each eval has:
- `name` — what behaviour it tests (maps to a row in the decision guide above)
- `expected_tool_chain` — the ordered list of tools the agent should call
- `assertions` — verifiable checks on tool call args and response content

To run a test case, send its `prompt` to the avatar agent and verify the agent
calls the tools listed in `expected_tool_chain` in the order shown, with the
args described in `assertions`. Ten test cases cover all 8 tools:

| Eval | Intent tested |
|------|--------------|
| `scan-and-report` | Fresh scan → report |
| `remediate-no-prs` | Remediate without opening PRs |
| `remediate-and-open-prs` | Remediate with `create_prs=True` |
| `show-latest-report` | Read saved report, no re-scan |
| `approve-queued-prs` | Flush pending PR queue |
| `lookup-cve-by-id` | NVD lookup by CVE ID |
| `lookup-cve-by-package` | NVD lookup by package name |
| `get-allowlist` | List monitored repos only |
| `agent-status` | Return config/workspace/SLIM info |
| `scan-then-enrich-cves` | Scan + enrich each CVE with NVD |
