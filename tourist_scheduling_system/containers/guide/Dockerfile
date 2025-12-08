# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
#
# Guide Agent Container
#
# The guide agent is a client that connects to the scheduler to offer tour services.
# It does not expose an A2A endpoint - it uses RemoteA2aAgent to connect to the scheduler.
#
# Build from project root:
#   docker build -f containers/guide/Dockerfile -t guide-agent .
#
# Run:
#   docker run -e AZURE_OPENAI_API_KEY=... \
#     -e SCHEDULER_URL=http://scheduler:10000 \
#     guide-agent --guide-id g1 --categories "culture,history"

FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

# Copy pyproject.toml first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv pip install --system --no-cache -r pyproject.toml

# Create non-root user
RUN adduser --disabled-password --gecos "" agentuser && \
    chown -R agentuser:agentuser /app

# Copy source code
COPY src/ ./src/

# Copy main.py entry point
COPY containers/guide/main.py ./main.py

USER agentuser

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Default scheduler URL (override with -e SCHEDULER_URL=...)
ENV SCHEDULER_URL=http://scheduler:10000

ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
