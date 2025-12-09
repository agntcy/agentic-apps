# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
#
# UI Dashboard Agent Container for GKE/Kubernetes deployment
# Following ADK deployment patterns: https://google.github.io/adk-docs/deploy/gke/
#
# Build from project root:
#   docker build -f containers/ui/Dockerfile -t ui-agent .
#
# Run locally:
#   docker run -p 10021:10021 ui-agent

FROM python:3.12-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

# Copy pyproject.toml first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies using uv (faster than pip)
RUN uv pip install --system --no-cache -r pyproject.toml

# Create non-root user for security
RUN adduser --disabled-password --gecos "" agentuser && \
    chown -R agentuser:agentuser /app

# Copy source code
COPY src/ ./src/

# Copy only the UI agent card (served via /.well-known/agent.json)
COPY a2a_cards/ui_agent.json ./a2a_cards/

# Copy main.py entry point for UI agent
COPY containers/ui/main.py ./main.py

# Switch to non-root user
USER agentuser

# Set Python path to include src
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Default port for UI agent dashboard
ENV PORT=10021

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

EXPOSE 10021

# Run the UI agent with dashboard
CMD ["sh", "-c", "python main.py --host 0.0.0.0 --port $PORT --dashboard"]
