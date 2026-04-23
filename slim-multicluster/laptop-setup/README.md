# Laptop Setup for Multicluster Demo

This directory contains the local IT-OPS operator setup for the multicluster scenario. It allows you to run a SPIRE agent on your laptop, authenticate with the remote SLIM dataplane, and interact with cloud-hosted agents using `a2acli` — either directly from the command line or through a GitHub Copilot skill.

## Prerequisites

1. macOS.
2. `go`, `task`, `kubectl`, and `git` installed.
3. Valid credentials with access to the target Kubernetes cluster.

## Step 1: Configure Your Environment

From this directory (`laptop-setup/`):

```bash
cp .env.local.example .env.local
```

Edit `.env.local` with your cluster-specific values (K8s context, SPIRE namespace, trust domain, SLIM endpoint, etc.).

## Step 2: Build and Run the SPIRE Agent

From this directory:

```bash
task build
```

This clones the SPIRE repository and builds the `spire-agent` binary from source (~2 minutes on the first run). The binary is placed in `bin/spire-agent`.

Then start the agent:

```bash
task run
```

`task run` performs the full bootstrap flow:

1. Builds `bin/spire-agent` if it does not already exist.
2. Regenerates the `a2acli` config from `.env.local`.
3. Fetches the SPIRE bootstrap bundle in PEM format from the target cluster.
4. Generates a join token for `spiffe://<trust-domain>/macos/agent/<hostname>`.
5. Renders a local runtime config under `spire/data/agent.conf`.
6. Starts the agent and exposes the Workload API on `/tmp/spire-agent/public/api.sock`.

**Keep `task run` running in a dedicated terminal.**

## Step 3: Register a2acli as a SPIRE Workload

In a **separate terminal**, from this directory:

```bash
task register
```

This registers the local `a2acli` binary as a SPIRE workload. On macOS, the `unix` workload attestor emits `uid`, `user`, `gid`, and `group` selectors so that the `a2acli` process can obtain an SVID from the Workload API.

> **Note:** This only needs to be run once. If the entry already exists, the command will report `AlreadyExists` which is harmless.

To inspect the entries registered for your laptop:

```bash
task show-entries
```

To verify the Workload API is issuing SVIDs:

```bash
task fetch-svid
```

## Step 4: Configure a2acli

Generate the local `a2acli` runtime config:

```bash
task a2acli-config
```

This writes `../a2acli-skill/.a2acli.yaml` from your `.env.local` settings, keeping the SLIM endpoint out of tracked files. Note that `task run` also refreshes this file automatically.

## Step 5: Build and Use a2acli

Move to the `a2acli-skill` directory:

```bash
cd ../a2acli-skill
task build
```

This creates `bin/a2acli`. You can now use it to interact with agents on the remote SLIM dataplane:

```bash
./bin/a2acli list
./bin/a2acli send-message --agent <agent-sha> "What can you do?"
```

The expected outcome is:

1. `a2acli` obtains a SPIRE identity from the local Workload API socket.
2. `a2acli` connects to the SLIM endpoint configured in `.env.local`.
3. The request is routed to the target agent and a response is returned.

For more information in the a2acli check the dedicated README

## Step 6 (Optional): Install the Copilot Skill

If you want to use `a2acli` directly from Copilot CLI, install the Copilot skill from the `a2acli-skill` directory:

```bash
cd ../a2acli-skill
task install-copilot-skill
```

This copies the skill source from `copilot-skills/a2acli/` into `~/.copilot/skills/a2acli` and installs the built `a2acli` binary alongside it.

After installation, open GitHub Copilot and the `a2acli` skill will be available for interacting with remote agents directly from the IDE.

## What Is In This Directory

| File | Description |
|------|-------------|
| `Taskfile.yml` | Task automation for SPIRE agent setup and configuration |
| `.env.local.example` | Template for local environment variables |
| `spire/agent.conf.tmpl` | SPIRE agent configuration template |

## Useful Commands

| Command | Description |
|---------|-------------|
| `task build` | Build the SPIRE agent binary from source |
| `task run` | Start the SPIRE agent (keep running in a dedicated terminal) |
| `task register` | Register a2acli as a SPIRE workload (run once) |
| `task a2acli-config` | Regenerate a2acli config from `.env.local` |
| `task show-entries` | Show workload entries registered for this laptop |
| `task fetch-svid` | Verify the agent can issue SVIDs |
| `task stop` | Stop the running SPIRE agent |
| `task clean` | Remove binary and data (forces full rebuild) |
