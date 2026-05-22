#!/bin/bash

# SLIM OpenTelemetry Demo - Quick Start Script
# This script helps run the complete demo with Grafana visualization

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Infrastructure Setup"
echo "================================"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi
echo "✅ Docker is running"

# Check if collector image exists
if ! docker image inspect slim-otelcol:latest > /dev/null 2>&1; then
    echo "❌ Collector Docker image not found. Please build it first:"
    echo "   task collector:docker:build"
    exit 1
fi
echo "✅ Collector image found"

# Start SLIM, Collector, Prometheus and Grafana
echo ""
echo "📊 Starting SLIM, Collector, Prometheus and Grafana..."
cd "$SCRIPT_DIR"
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
MAX_WAIT=30
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    if docker-compose ps | grep -q "Up"; then
        # Give services a bit more time to fully initialize
        sleep 2
        break
    fi
    sleep 1
    ELAPSED=$((ELAPSED + 1))
done

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo "✅ SLIM running on http://localhost:46357"
    echo "✅ Collector running (Metrics: http://localhost:8889)"
    echo "✅ Prometheus running on http://localhost:9090"
    echo "✅ Grafana running on http://localhost:3000 (admin/admin)"
else
    echo "❌ Services failed to start after ${MAX_WAIT}s"
    docker-compose logs
    exit 1
fi

echo ""
echo "================================"
echo "✅ Infrastructure Ready!"
echo "================================"

echo ""
echo "To stop infrastructure:"
echo " task infra:stop"
echo ""
