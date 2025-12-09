# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
#
# Tourist Agent Container
#
# The tourist agent is a client that connects to the scheduler to request tours.
# It does not expose an A2A endpoint - it uses RemoteA2aAgent to connect to the scheduler.
#
# Build from project root:
#   docker build -f containers/tourist/Dockerfile -t tourist-agent .
#
# Run:
#   docker run -e AZURE_OPENAI_API_KEY=... \
#     -e SCHEDULER_URL=http://scheduler:10000 \
#     tourist-agent --tourist-id t1 --preferences "culture,history"

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

# Note: Tourist agent fetches agent card from scheduler URL, no local cards needed

# Copy main.py entry point
COPY containers/tourist/main.py ./main.py

USER agentuser

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Default scheduler URL (override with -e SCHEDULER_URL=...)
ENV SCHEDULER_URL=http://scheduler:10000

ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
