# Agentic Apps Monorepo
[![codecov](https://codecov.io/gh/agntcy/agentic-apps/branch/main/graph/badge.svg)](https://codecov.io/gh/agntcy/agentic-apps)

Collection of experimental and reference agent applications built on the A2A protocol and SDK. Each subfolder is a self-contained agent system or demo (some with autonomous LLM behavior, real-time dashboards, or network orchestration).

## Contents

| Project | Description | Key Tech |
|---------|-------------|----------|
| [`tourist_scheduling_system/`](tourist_scheduling_system/README.md) | Multi-agent tourist scheduling with scheduler, UI dashboard, and autonomous guide/tourist agents | A2A SDK, Google ADK, SLIM, FastAPI, WebSockets, OpenTelemetry |
| [`network_of_assistants/`](network_of_assistants/README.md) | Network-of-assistants stack (moderator, math, file, web, user proxy) | FastAPI, Docker, A2A SDK |
| [`observability_app/`](observability_app/README.md) | AI-powered root cause analysis of application performance issues using SLIM for telemetry distribution and an agent for diagnostics | SLIM, OpenTelemetry |
| [`slim-multicluster/`](slim-multicluster/README.md) | Multicluster customer-remediation scenario with a cloud-hosted troubleshooting agent diagnosing Kubernetes issues across cluster boundaries | SLIM, A2A SDK, Google ADK, MCP, SPIRE, Agent skills |

See each project's README for installation, configuration, and usage instructions.

## License

Apache License 2.0 (see `LICENSE`).

## Contributing

See `CONTRIBUTING.md` for guidelines; feel free to open issues or PRs for new agent demos.

