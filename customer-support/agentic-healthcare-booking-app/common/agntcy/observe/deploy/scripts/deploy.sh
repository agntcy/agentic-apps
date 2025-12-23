#!/bin/bash
# ====================
# Observability Stack Deployment Script
# ====================
# WARNING: Review and customize this script for your environment before use.
# This script automates the deployment of an observability stack including
# OpenTelemetry Collector, ClickHouse, and Grafana.
# ====================

set -e  # Exit on any error

# Configuration - Override these via environment variables if needed
DATA_DIR="${DATA_DIR:-/opt/observability-stack}"
CLICKHOUSE_PASSWORD_PLACEHOLDER="${CLICKHOUSE_PASSWORD_PLACEHOLDER:-CLICKHOUSE_PASSWORD_PLACEHOLDER}"
GRAFANA_PASSWORD_PLACEHOLDER="${GRAFANA_PASSWORD_PLACEHOLDER:-GRAFANA_PASSWORD_PLACEHOLDER}"

echo "========================================="
echo "Observability Stack Deployment"
echo "========================================="
echo ""

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    echo "Error: This script should not be run as root."
    echo "Please run as a non-root user with sudo privileges."
    exit 1
fi

# Install Docker if not present
install_docker() {
    if ! command -v docker &> /dev/null; then
        echo "Docker not found. Installing Docker..."
        
        # Detect OS and install Docker
        if [ -f /etc/amazon-linux-release ]; then
            # Amazon Linux
            echo "Detected Amazon Linux. Installing Docker..."
            sudo yum update -y
            sudo yum install -y docker
            sudo systemctl start docker
            sudo systemctl enable docker
            sudo usermod -aG docker $USER || true
        
        elif [ -f /etc/debian_version ]; then
            # Ubuntu/Debian
            echo "Detected Debian/Ubuntu. Installing Docker..."
            sudo apt update
            sudo apt install -y docker.io
            sudo systemctl start docker
            sudo systemctl enable docker
            sudo usermod -aG docker $USER || true
            
        else
            # Generic Linux
            echo "Attempting to install Docker via get.docker.com..."
            curl -fsSL https://get.docker.com -o get-docker.sh
            sudo sh get-docker.sh
            sudo usermod -aG docker $USER || true
            rm get-docker.sh
        fi
        
        echo ""
        echo "Docker installed successfully."
        echo "IMPORTANT: Please log out and back in, then run this script again"
        echo "to apply Docker group changes."
        exit 0
    else
        echo "✓ Docker is already installed."
    fi
}

# Install Docker Compose
install_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        echo "Docker Compose not found. Installing..."
        
        # Download latest Docker Compose from GitHub releases
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
            -o /usr/local/bin/docker-compose
        
        sudo chmod +x /usr/local/bin/docker-compose
        
        # Verify installation
        if docker-compose --version &> /dev/null; then
            echo "✓ Docker Compose installed successfully."
        else
            echo "Error: Docker Compose installation failed."
            exit 1
        fi
    else
        echo "✓ Docker Compose is already installed."
    fi
}

# Create required directories
setup_directories() {
    echo ""
    echo "Setting up data directories..."
    
    # Create directory structure
    sudo mkdir -p ${DATA_DIR}/data/{clickhouse,grafana}
    
    # Set ownership to current user
    sudo chown -R $USER:$USER ${DATA_DIR}
    
    echo "✓ Directories created at: ${DATA_DIR}"
    echo "  - ${DATA_DIR}/data/clickhouse"
    echo "  - ${DATA_DIR}/data/grafana"
}

# Update configuration files with secure passwords
update_passwords() {
    echo ""
    echo "Generating secure passwords..."
    
    # Generate cryptographically secure random passwords
    CLICKHOUSE_PASS=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    GRAFANA_PASS=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    
    # Check if .env file exists
    if [ ! -f .env ]; then
        echo "Error: .env file not found in current directory."
        echo "Please ensure .env file exists with password placeholders."
        exit 1
    fi
    
    # Update .env file
    if grep -q "${CLICKHOUSE_PASSWORD_PLACEHOLDER}" .env; then
        sed -i "s/${CLICKHOUSE_PASSWORD_PLACEHOLDER}/${CLICKHOUSE_PASS}/g" .env
        echo "✓ Updated ClickHouse password in .env"
    else
        echo "Warning: ClickHouse password placeholder not found in .env"
    fi
    
    if grep -q "${GRAFANA_PASSWORD_PLACEHOLDER}" .env; then
        sed -i "s/${GRAFANA_PASSWORD_PLACEHOLDER}/${GRAFANA_PASS}/g" .env
        echo "✓ Updated Grafana password in .env"
    else
        echo "Warning: Grafana password placeholder not found in .env"
    fi
    
    # Update ClickHouse users.xml if it exists
    if [ -f clickhouse/users.xml ]; then
        if grep -q "${CLICKHOUSE_PASSWORD_PLACEHOLDER}" clickhouse/users.xml; then
            sed -i "s/${CLICKHOUSE_PASSWORD_PLACEHOLDER}/${CLICKHOUSE_PASS}/g" clickhouse/users.xml
            echo "✓ Updated ClickHouse password in users.xml"
        fi
    fi
    
    # Update Grafana datasource configuration if it exists
    if [ -f grafana/provisioning/datasources/datasources.yml ]; then
        if grep -q "${CLICKHOUSE_PASSWORD_PLACEHOLDER}" grafana/provisioning/datasources/datasources.yml; then
            sed -i "s/${CLICKHOUSE_PASSWORD_PLACEHOLDER}/${CLICKHOUSE_PASS}/g" grafana/provisioning/datasources/datasources.yml
            echo "✓ Updated ClickHouse password in Grafana datasource"
        fi
    fi
    
    echo ""
    echo "========================================="
    echo "Generated Credentials"
    echo "========================================="
    echo "ClickHouse Password: $CLICKHOUSE_PASS"
    echo "Grafana Password:    $GRAFANA_PASS"
    echo "========================================="
    echo ""
    echo "IMPORTANT: These credentials have been saved to ./.credentials"
    echo "Please store them securely and delete the file after saving elsewhere."
    echo ""
    
    # Save credentials to secure file
    cat > .credentials <<EOF
========================================
Observability Stack Credentials
========================================
Generated on: $(date)

ClickHouse Password: $CLICKHOUSE_PASS
Grafana Password:    $GRAFANA_PASS

========================================
IMPORTANT: Delete this file after saving credentials securely!
========================================
EOF
    
    # Restrict file permissions to owner only
    chmod 600 .credentials
}

# Deploy the stack using Docker Compose
deploy_stack() {
    echo ""
    echo "Deploying observability stack..."
    
    # Check if docker-compose.yml exists
    if [ ! -f docker-compose.yml ]; then
        echo "Error: docker-compose.yml not found in current directory."
        exit 1
    fi
    
    # Pull latest images
    echo "Pulling latest Docker images..."
    docker-compose pull
    
    # Start services in detached mode
    echo "Starting services..."
    docker-compose up -d
    
    echo "✓ Services started successfully."
}

# Wait for services to be ready
wait_for_services() {
    echo ""
    echo "Waiting for services to become ready..."
    echo "This may take a few minutes..."
    echo ""
    
    # Wait for ClickHouse
    echo "[1/3] Checking ClickHouse..."
    for i in {1..60}; do
        if docker-compose exec -T clickhouse clickhouse-client --query "SELECT 1" &>/dev/null; then
            echo "✓ ClickHouse is ready."
            break
        fi
        
        if [ $i -eq 60 ]; then
            echo "Error: ClickHouse did not become ready in time (5 minutes)."
            echo "Check logs with: docker-compose logs clickhouse"
            exit 1
        fi
        
        echo "  Waiting for ClickHouse... (${i}/60)"
        sleep 5
    done
    
    # Wait for OpenTelemetry Collector
    echo "[2/3] Checking OpenTelemetry Collector..."
    for i in {1..30}; do
        if curl -sf http://localhost:13133/ &>/dev/null; then
            echo "✓ OpenTelemetry Collector is ready."
            break
        fi
        
        if [ $i -eq 30 ]; then
            echo "Error: OpenTelemetry Collector did not become ready in time (2.5 minutes)."
            echo "Check logs with: docker-compose logs otel-collector"
            exit 1
        fi
        
        echo "  Waiting for OpenTelemetry Collector... (${i}/30)"
        sleep 5
    done
    
    # Wait for Grafana
    echo "[3/3] Checking Grafana..."
    for i in {1..30}; do
        if curl -sf http://localhost:3000/api/health &>/dev/null; then
            echo "✓ Grafana is ready."
            break
        fi
        
        if [ $i -eq 30 ]; then
            echo "Error: Grafana did not become ready in time (2.5 minutes)."
            echo "Check logs with: docker-compose logs grafana"
            exit 1
        fi
        
        echo "  Waiting for Grafana... (${i}/30)"
        sleep 5
    done
    
    echo ""
    echo "✓ All services are up and running!"
}

# Detect public IP for cloud deployments
get_public_ip() {
    local PUBLIC_IP=""
    
    # Try AWS EC2 metadata service
    PUBLIC_IP=$(curl -s --connect-timeout 2 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null)
    
    # If AWS metadata fails, try public IP detection service
    if [ -z "$PUBLIC_IP" ]; then
        PUBLIC_IP=$(curl -s --connect-timeout 2 https://checkip.amazonaws.com 2>/dev/null | tr -d '\n')
    fi
    
    # If still no IP, try another service
    if [ -z "$PUBLIC_IP" ]; then
        PUBLIC_IP=$(curl -s --connect-timeout 2 https://api.ipify.org 2>/dev/null)
    fi
    
    # Fallback to localhost
    if [ -z "$PUBLIC_IP" ]; then
        PUBLIC_IP="localhost"
    fi
    
    echo "$PUBLIC_IP"
}

# Display completion information
show_completion() {
    local PUBLIC_IP=$(get_public_ip)
    
    echo ""
    echo "========================================="
    echo "Deployment Completed Successfully!"
    echo "========================================="
    echo ""
    echo "Service Access Information:"
    echo "----------------------------------------"
    echo "Grafana Dashboard:"
    echo "  URL: http://${PUBLIC_IP}:3000"
    echo "  Username: admin"
    echo "  Password: (see ./.credentials file)"
    echo ""
    echo "OpenTelemetry Endpoints:"
    echo "  HTTP (traces/logs): http://${PUBLIC_IP}:4318"
    echo "  gRPC (metrics):     grpc://${PUBLIC_IP}:4317"
    echo "  Health Check:       http://${PUBLIC_IP}:13133"
    echo ""
    echo "ClickHouse:"
    echo "  Host: ${PUBLIC_IP}:9000"
    echo "  HTTP: http://${PUBLIC_IP}:8123"
    echo "========================================="
    echo ""
    echo "Container Status:"
    echo "----------------------------------------"
    docker-compose ps
    echo ""
    echo "========================================="
    echo "Next Steps:"
    echo "========================================="
    echo ""
    echo "1. Configure Your Application"
    echo "   Set OTLP_HTTP_ENDPOINT to: http://${PUBLIC_IP}:4318"
    echo "   (Use http://localhost:4318 for local development)"
    echo ""
    echo "2. Access Grafana"
    echo "   Open: http://${PUBLIC_IP}:3000"
    echo "   Login with credentials from ./.credentials file"
    echo ""
    echo "3. Start Your Application"
    echo "   Your app will automatically send telemetry data"
    echo ""
    echo "4. Explore Dashboards"
    echo "   View pre-configured dashboards or create custom ones"
    echo ""
    echo "========================================="
    echo "Useful Commands:"
    echo "========================================="
    echo ""
    echo "View all logs:"
    echo "  docker-compose logs -f"
    echo ""
    echo "View specific service logs:"
    echo "  docker-compose logs -f [clickhouse|otel-collector|grafana]"
    echo ""
    echo "Stop all services:"
    echo "  docker-compose down"
    echo ""
    echo "Restart all services:"
    echo "  docker-compose restart"
    echo ""
    echo "Access ClickHouse CLI:"
    echo "  docker-compose exec clickhouse clickhouse-client"
    echo ""
    echo "Check service health:"
    echo "  docker-compose ps"
    echo ""
    echo "========================================="
    echo ""
}

# Main deployment orchestration
main() {
    echo "Starting deployment process..."
    echo ""
    
    # Run deployment steps
    install_docker
    install_docker_compose
    setup_directories
    update_passwords
    deploy_stack
    wait_for_services
    show_completion
    
    echo ""
    echo "✓ Observability stack deployment finished successfully!"
    echo ""
    echo "Remember to:"
    echo "  1. Save credentials from ./.credentials file"
    echo "  2. Delete ./.credentials file after saving"
    echo "  3. Configure firewall/security groups for required ports"
    echo ""
}

# Execute main function
main "$@"
