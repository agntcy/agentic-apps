# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
#
# Scheduler Agent Container for GKE/Kubernetes deployment
# Following ADK deployment patterns: https://google.github.io/adk-docs/deploy/gke/
#
# Build from project root:
#   docker build -f containers/scheduler/Dockerfile -t scheduler-agent .
#
# Run locally:
#   docker run -p 10000:10000 -e AZURE_OPENAI_API_KEY=... scheduler-agent

FROM python:3.12-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation (pip is build-time only).
RUN python -m pip install --no-cache-dir --upgrade "pip>=26.2.0" uv

# Copy pyproject.toml first for better layer caching
COPY pyproject.toml uv.lock ./

# Install the exact, audited dependency set from uv.lock
RUN uv export --frozen --no-dev --no-editable --no-emit-project --no-emit-workspace \
        > /tmp/requirements.txt && \
    uv pip install --system --no-cache -r /tmp/requirements.txt && \
    rm -f /tmp/requirements.txt && \
    rm -rf /usr/local/lib/python3.12/site-packages/pip \
           /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
           /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.12

# Create non-root user for security
RUN adduser --disabled-password --gecos "" agentuser && \
    chown -R agentuser:agentuser /app

# Copy source code
COPY src/ ./src/

# Copy only the scheduler agent card (served via /.well-known/agent.json)
COPY a2a_cards/scheduler_agent.json ./a2a_cards/

# Copy main.py entry point for scheduler
COPY containers/scheduler/main.py ./main.py

# Switch to non-root user
USER agentuser

# Set Python path to include src
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Default port for scheduler A2A server
ENV PORT=10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/.well-known/agent.json || exit 1

EXPOSE 10000

# Run the scheduler agent
# TRANSPORT_MODE can be 'http' or 'slim' (default: http)
CMD ["sh", "-c", "python main.py --host 0.0.0.0 --port $PORT --mode a2a --transport ${TRANSPORT_MODE:-http}"]
