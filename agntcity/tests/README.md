# Lungo Test Suite

## Scope

The suite validates:
- Auction Supervisor flows (inventory queries per farm, aggregated inventory, order creation success / failure paths, invalid prompt handling) over multiple message transports (SLIM, NATS).
- Logistics Supervisor flow (multi‑agent fulfillment: logistics-farm + accountant + shipper) currently over SLIM transport.
- Agent process orchestration, startup readiness gating, and HTTP supervisor APIs.
- Cross‑transport parity for auction flows (see TRANSPORT_MATRIX in [`test_auction.py`](coffeeAGNTCY/coffee_agents/lungo/tests/integration/test_auction.py:1)).

## Directory Layout

- Session / infra orchestration fixtures & agent/client fixtures: [`conftest.py`](coffeeAGNTCY/coffee_agents/lungo/tests/integration/conftest.py:1)
- Docker Compose lifecycle helpers (bring up transport and observability components): [`docker_helpers.py`](coffeeAGNTCY/coffee_agents/lungo/tests/integration/docker_helpers.py:1)
- Lightweight subprocess runner used for agent processes: [`process_helper.py`](coffeeAGNTCY/coffee_agents/lungo/tests/integration/process_helper.py:1)
- Auction supervisor integration tests (parametrized SLIM + NATS): [`test_auction.py`](coffeeAGNTCY/coffee_agents/lungo/tests/integration/test_auction.py:1)
- Logistics (order fulfillment) integration test (currently SLIM only): [`test_logistics.py`](coffeeAGNTCY/coffee_agents/lungo/tests/integration/test_logistics.py:1)

## Execution Prerequisites

1. Install dependencies (lungo package root):

```bash
uv sync --extra dev
```

2. Configure environment:

```bash
cp coffeeAGNTCY/coffee_agents/lungo/.env.example .env
# Set LLM settings required by agents
```

3. Ensure Docker runtime is available

## Running Tests

All Lungo tests (auction + logistics):

```bash
uv run pytest -s
```

Auction tests only:

```bash
uv run pytest integration/test_auction.py -s
```

Logistics test only:

```bash
uv run pytest integration/test_logistics.py -s
```

Single auction test (Brazil inventory over both transports):

```bash
uv run pytest integration/test_auction.py::TestAuctionFlows::test_auction_brazil_inventory -s
```

Run only NATS parametrized cases:

```bash
uv run pytest -k NATS integration/test_auction.py -s
```

## Version Overrides
CoffeeAGNTCY serves as a reference environment for multiple integrated components. To support continuous compatibility testing and faster integration validation, we've added functionality that allows remote triggering of CI pipelines with version overrides.

The reusable integration test workflow [`test.yaml`](.github/workflows/test.yaml:1) accepts three optional multiline inputs to test new dependency or container image versions **without changing the repo**:
- `pip_overrides` (exact PEP 508 specs, one per line)
- `pip_constraints` (constraint lines)
- `docker_overrides` (service=image[:tag] mappings applied to the demo docker-compose)

An example caller is provided in [`version-override-test.yaml`](.github/workflows/version-override-test.yaml:1). Trigger it (Workflow Dispatch) or via UI.

Minimal invocation pattern:

```yaml
name: Custom Integration
on:
  workflow_dispatch: {}
jobs:
  integration:
    uses: agntcy/coffeeAgntcy/.github/workflows/test.yaml@integration-hook
    secrets: inherit
    with:
      pip_overrides: |
        httpx==0.27.2
      pip_constraints: |
        grpcio&lt;1.65
      docker_overrides: |
        slim=ghcr.io/agntcy/slim:0.5.0
```