# Observability Troubleshooting Guide

This guide provides common troubleshooting steps for issues related to Docker/Compose deployments, environment configuration, networking, and the observability stack.

---

## Table of Contents

1.  [Docker/Compose – Deployment Issues](#dockercompose--deployment-issues)
    *   [Port Conflicts](#port-conflicts)
    *   [Containers Flapping/Restarting](#containers-flappingrestarting)
    *   [Compose as Root](#compose-as-root)
    *   [Clean Slate](#clean-slate)
2.  [Environment & Configuration](#environment--configuration)
    *   [Missing/Incorrect Environment Variables](#missingincorrect-environment-variables)
    *   [Verify .env is Read by Compose](#verify-env-is-read-by-compose)
3.  [Networking & OS](#networking--os)
    *   [Firewall Blocks](#firewall-blocks)
    *   [DNS in Containers](#dns-in-containers)
    *   [TLS Misconfiguration](#tls-misconfiguration)
4.  [Observability Stack – Deployment Issues](#observability-stack--deployment-issues)
    *   [ClickHouse Not Reachable](#clickhouse-not-reachable)
    *   [OTEL Collector Down](#otel-collector-down)
    *   [Grafana Up But No Data](#grafana-up-but-no-data)

---

## 1. Docker/Compose – Deployment Issues

### Port Conflicts

If services fail to start due to ports already being in use (e.g., 5432, 8000, 3000).

*   **Troubleshooting:**
    *   Check which process is using a specific port:
        ```bash
        sudo lsof -i :5432
        ```
    *   Stop the conflicting process or re-map the port in your `docker-compose.yml` file.

### Containers Flapping/Restarting

Containers repeatedly starting and stopping.

*   **Troubleshooting:**
    *   View all containers and their status:
        ```bash
        docker ps -a
        ```
    *   Inspect logs for a specific container to identify the cause of restarts:
        ```bash
        docker logs <container_name>
        ```
    *   Verify that environment files are correctly mounted and not empty.
    *   Check the `restart: policy` in your `docker-compose.yml` for unexpected behavior.

### Compose as Root

If there's a requirement to run Docker Compose with root privileges.

*   **Troubleshooting:**
    *   Switch to the root user:
        ```bash
        sudo su -
        ```
    *   Navigate to your project directory and run Docker Compose:
        ```bash
        docker compose up -d
        ```

### Clean Slate

To completely remove all containers, networks, volumes, and images to start fresh.

*   **Troubleshooting:**
    *   Stop and remove containers, networks, and anonymous volumes defined in `docker-compose.yml`:
        ```bash
        docker compose down -v
        ```
    *   Remove all unused Docker data (containers, images, networks, build cache):
        ```bash
        docker system prune -a
        ```
    *   Remove all unused local volumes:
        ```bash
        docker volume prune -f
        ```

---

## 2. Environment & Configuration

### Missing/Incorrect Environment Variables

Leads to runtime failures if critical environment variables are not set or have incorrect values.

*   **Troubleshooting:**
    *   Print masked environment variables to check their values (adjust grep pattern as needed):
        ```bash
        env | grep -E 'DB_|A2A_|CLIENT_|OTEL|CLICKHOUSE|GRAFANA'
        ```
    *   Ensure no secrets are hard-coded directly in your application or `docker-compose.yml`. Prefer using `.env` files and ensure they are not committed to version control.

### Verify .env is Read by Compose

Confirm that your `docker-compose.yml` is correctly reading variables from your `.env` file.

*   **Troubleshooting:**
    *   Confirm the location of your `.env` file (it should typically be in the same directory as `docker-compose.yml`).
    *   Use `docker compose config` to see the resolved configuration, including environment variables:
        ```bash
        docker compose --env-file .env config | sed -n '1,120p'
        ```

---

## 3. Networking & OS

### Firewall Blocks

Operating system firewalls can prevent services from communicating.

*   **Troubleshooting:**
    *   Check the status of your firewall (e.g., UFW on Ubuntu):
        ```bash
        sudo ufw status
        ```
    *   Open required ports or ensure you are using internal Docker networking for container-to-container communication.

### DNS in Containers

Containers might have issues resolving hostnames of other services.

*   **Troubleshooting:**
    *   Execute a command inside a container to test DNS resolution for another service:
        ```bash
        docker exec -it <service_name> getent hosts <other-service-name>
        ```

### TLS Misconfiguration

Issues with SSL/TLS certificates, especially for reverse proxies.

*   **Troubleshooting:**
    *   For reverse proxies, verify the paths and ownership of your certificate and key files.
    *   Test TLS connectivity with `openssl`:
        ```bash
        openssl s_client -connect host:443 -servername host
        ```
        (Replace `host` and `443` with your actual hostname and port).

---

## 4. Observability Stack – Deployment Issues

### ClickHouse Not Reachable

Problems connecting to the ClickHouse database.

*   **Troubleshooting:**
    *   Check if the ClickHouse HTTP interface is responding:
        ```bash
        curl -sS http://localhost:8123/ping
        ```
    *   Inspect ClickHouse container logs for errors:
        ```bash
        docker logs clickhouse
        ```

### OTEL Collector Down

OpenTelemetry Collector not running or not accessible.

*   **Troubleshooting:**
    *   Check the health endpoint of the OTEL Collector (default port 13133 for health checks):
        ```bash
        curl -sS http://localhost:13133/
        ```
    *   Inspect OTEL Collector container logs for errors:
        ```bash
        docker logs otel-collector
        ```

### Grafana Up But No Data

Grafana is running, but dashboards are empty or show no metrics/logs.

*   **Troubleshooting:**
    *   Check the health endpoint of Grafana:
        ```bash
        curl -sS http://localhost:3000/api/health
        ```
    *   Verify the data source configuration within the Grafana UI (e.g., ensure the ClickHouse or Prometheus data source is correctly configured and reachable from Grafana).

---  
 
