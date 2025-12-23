set -e

BACKUP_DIR="/opt/observability/backups/$(date +%Y%m%d_%H%M%S)"
PROJECT_DIR="/opt/observability"

echo "Creating backup at $BACKUP_DIR"
mkdir -p $BACKUP_DIR

# Backup configurations
echo "Backing up configurations..."
cp -r $PROJECT_DIR/{.env,docker-compose.yml,clickhouse,otel,grafana,nginx} $BACKUP_DIR/

# Backup ClickHouse data
echo "Backing up ClickHouse data..."
docker-compose exec -T clickhouse clickhouse-client --query "BACKUP DATABASE observability TO File('/var/lib/clickhouse/backup_$(date +%Y%m%d_%H%M%S)')"

# Backup Grafana data
echo "Backing up Grafana data..."
docker cp $(docker-compose ps -q grafana):/var/lib/grafana $BACKUP_DIR/grafana_data

echo "Backup completed: $BACKUP_DIR"

# Cleanup old backups (keep last 5)
find /opt/observability/backups -maxdepth 1 -type d -mtime +5 -exec rm -rf {} \; 2>/dev/null || true
