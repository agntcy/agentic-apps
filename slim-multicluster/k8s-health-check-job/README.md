# Kubernetes Health Check CronJob

This Kubernetes CronJob automatically monitors the health of the customer cluster by leveraging the `k8s_troubleshooting_agent` through the A2A protocol.

## Overview

The job runs **every 2 minutes** and performs the following actions:

1. Discovers available agents by running `a2acli list`
2. Locates the `k8s_troubleshooting_agent` from the list of available agents
3. Sends a health check request to the agent asking it to:
   - Check the health status of pods in the customer cluster
   - Create a Jira ticket if any issues are found
   - Include relevant logs, k8s events, and pod information in the ticket
   - Check for duplicate issues before creating new ones

## a2acli Image

The job uses the `a2acli` container image, which is available at:
https://github.com/agntcy/slim/pkgs/container/slim%2Fmulticluster-demo%2Fa2acli

Current version: `ghcr.io/agntcy/slim/multicluster-demo/a2acli:0.1.3`

## Configuration

### SLIM Endpoint

The SLIM endpoint can be modified in the environment variables section:

```yaml
env:
- name: SLIM_ENDPOINT
  value: "http://slim-dp-slim-root-mc-demo-dev-argoapp:46357"
```

Update this value to point to your actual SLIM cluster endpoint.

### Customizing the Agent Request

The health check message sent to the `k8s_troubleshooting_agent` can be personalized to fit your specific requirements. The message is defined in the `MESSAGE` variable within the job script:

```bash
MESSAGE="Check the health status of the pods in the cluster. "
MESSAGE="${MESSAGE}If you see any issue, create a Jira ticket to track it. The ticket must be a bug. "
MESSAGE="${MESSAGE}The Jira issue must contain all the relevant logs, the relevant k8s events and the "
MESSAGE="${MESSAGE}information of the faulty pod such as its name and the node where it runs. "
MESSAGE="${MESSAGE}If the log is too long add a file in the issue. The format must be markdown. "
MESSAGE="${MESSAGE}Before creating the ticket, check if a similar issue has already been reported to avoid duplicates."
```

You can customize:
- The scope of health checks (specific namespaces, pod labels, etc.)
- Jira ticket requirements (project key, issue type, labels, components)
- The format and content of the issue report
- Duplicate detection criteria

## Requirements

- The `k8s_troubleshooting_agent` must be registered and available in the SLIM network
- SPIRE agent socket must be available at `/run/spire/agent-sockets/spire-agent.sock`

## Schedule

The job runs with the following schedule configuration:
- **Frequency**: Every 2 minutes (`*/2 * * * *`)
- **Concurrency Policy**: `Forbid` (prevents overlapping executions)
- **History Limits**: 3 successful and 3 failed jobs retained
