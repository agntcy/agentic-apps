# Demo Walkthrough

This page documents an example multi-agent scenario built on top of SHADI. It
is useful for validating the runtime end to end, but it is not the default
operating model for every SHADI deployment.

The example scenario uses two SecOps agents and one human-facing Avatar agent
in the same SLIM group channel, backed by a local SLIM node.

!!! note

  Use this walkthrough when you want to exercise SHADI with a realistic
  multi-agent workflow. For the core runtime model, start with
  [Getting Started](getting_started.md), [Operations](operations.md), and
  [Architecture](architecture.md).

## Scenario Overview

In this example, SHADI is responsible for:

- storing shared secrets and identity material
- applying sandbox policy before each agent starts
- brokering the local runtime environment for the demo agents

The workload-specific behavior comes from the demo agents themselves:

- Avatar acts as the human-facing entry point
- the SecOps agents perform scanning and remediation planning
- SLIM provides the transport between participants

## 1) Start a local SLIM node

Use the launcher to start the local SLIM instance configured for the demo:

```bash
just launch-slim-example
```

## 2) Seed SLIM shared secret in SHADI

Both SecOps agents and the Avatar agent use the same shared secret stored in
SHADI. Import it once using the bootstrap script:

```bash
export SHADI_OPERATOR_PRESENTATION="local-operator"
export SLIM_SHARED_SECRET="$(openssl rand -hex 32)"

just import-secops-secrets
```

## 3) Run two SecOps agents on the same channel

The demo ships per-agent configs under `./.tmp`. Start each agent in its own
terminal:

```bash
just launch-secops-a2a-example
```

To start a second agent, set `SHADI_AGENT_ID=secops-b` and point
`SHADI_SECOPS_CONFIG` to `./.tmp/secops-b.toml` before running the launcher.

If you want the SecOps side to open PRs, also set:

```bash
export SHADI_HUMAN_GITHUB="your-github-handle"
```

## 4) Connect as a human using the Avatar ADK agent

```bash
just launch-avatar-example
```

In the Avatar prompt, ask for actions like:

```
scan dependabot for the allowlist
report
```

For remediation flows, ask for something like:

```text
scan dependabot for the allowlist and remediate actionable findings
```

Container findings now come back as rebuild or base-image refresh guidance rather than Dockerfile package-layer edits.

## 5) Key and DID utilities

SHADI can ingest OpenPGP keys without shelling out to `gpg`. Store a human
OpenPGP secret key, then derive an agent DID and keypair in the secret store:

```bash
cargo run -p shadictl -- \
  put-key --key human/gpg --in /path/to/human-secret.asc

cargo run -p shadictl -- \
  derive-agent-did \
  --secret human/gpg \
  --name agent-a \
  --prefix agents \
  --out agent-a.did.json
```

You can also create a DID document from a public OpenPGP key file:

```bash
cargo run -p shadictl -- \
  did-from-gpg --in /path/to/human-public.asc --out human.did.json
```

Notes:
- Keys and DIDs are stored in the SHADI secret store.
- OpenPGP parsing uses `sequoia-openpgp`, not the OS `gpg` binary.

## Scenario Notes
- The SecOps A2A servers and Avatar agent share the same SLIM endpoint and
  shared secret in SHADI.
- Adjust `secops.toml` or the per-agent configs if you want different identities
  or endpoints.

## Using 1Password instead of the OS keychain

All steps in this example scenario work with 1Password as the secret backend.
Export the following before running the walkthrough:

```bash
export SHADI_SECRET_BACKEND=onepassword
export SHADI_OP_VAULT=shadi          # optional, default: shadi
```

The `op` CLI (1Password CLI v2) must be installed and authenticated (or set
`OP_SERVICE_ACCOUNT_TOKEN` for headless/CI use). Then run every step above
exactly as written. The bootstrap and launch helpers will store and retrieve
secrets from the 1Password vault instead of the OS keychain.

The launchers pre-read the required 1Password items before entering the sandbox.
This avoids the common failure mode where the `op` background prompt or daemon
startup is blocked by sandbox policy.

## Troubleshooting

- If `launch_secops_a2a.sh` fails under the 1Password backend, confirm that the `op` CLI is authenticated for the selected account and vault.
- If Avatar reports a SLIM session handshake failure, verify that the SecOps A2A server is already running and that both terminals use the same shared secret, identity, endpoint, and TLS files.
