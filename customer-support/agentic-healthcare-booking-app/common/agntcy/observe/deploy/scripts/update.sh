set -e

echo "Updating observability stack..."

# Create backup before update
./scripts/backup.sh

# Pull latest images
docker-compose pull

# Restart services with new images
docker-compose up -d

# Health check
echo "Checking service health..."
sleep 30

if curl -sf http://localhost:13133/ &>/dev/null; then
    echo "OTEL Collector: OK"
else
    echo "OTEL Collector: FAILED"
fi

if curl -sf http://localhost:3000/api/health &>/dev/null; then
    echo "Grafana: OK"
else
    echo "Grafana: FAILED"
fi

echo "Update completed"