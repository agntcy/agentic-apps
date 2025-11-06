# Multi-stage build for A2A Medical Triage Agent
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create non-root user for security
RUN groupadd -r triageuser && \
    useradd -r -g triageuser -d /app -s /bin/bash triageuser

# Create app directory and set permissions
WORKDIR /app
RUN chown -R triageuser:triageuser /app

# Copy application code
COPY --chown=triageuser:triageuser . .

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs /app/static && \
    chown -R triageuser:triageuser /app/data /app/logs /app/static

# Switch to non-root user
USER triageuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default command
CMD ["python", "triagev2.py"]

# Labels for metadata
LABEL maintainer="Cisco Outshift"
LABEL version="2.0.0"
LABEL description="A2A Protocol Compliant Medical Triage Agent"
LABEL protocol="A2A v0.3.0"
