# `ioa_observe.sdk` - The Definitive Guide to End-to-End Microservices Observability

This document provides a consolidated, end-to-end guide to integrating and leveraging the `ioa_observe.sdk` for robust observability in microservices, with a specific focus on its application within agent systems like the Healthcare Voice agent + A2A + MCP Agent and the A2A Medical Triage Service. It covers from foundational concepts and setup to advanced instrumentation, deployment, and best practices.

---

## Table of Contents

1.  [Introduction](#1-introduction)
2.  [Key Concepts & SDK Overview](#2-key-concepts--sdk-overview)
    *   [Telemetry Data Types](#telemetry-data-types)
    *   [`ioa_observe.sdk` Decorators](#ioa_observe.sdk-decorators)
3.  [Features](#3-features)
4.  [Prerequisites](#4-prerequisites)
5.  [Installation](#5-installation)
6.  [Configuration](#6-configuration)
    *   [Environment Variables](#environment-variables)
    *   [Local Configuration Files](#local-configuration-files)
7.  [Getting Started (Local Development)](#7-getting-started-local-development)
    *   [Initial Setup](#initial-setup)
    *   [Decorator Integration](#decorator-integration)
    *   [Local Execution Steps](#local-execution-steps)
8.  [Instrumentation Details](#8-instrumentation-details)
    *   [Core Observability Initialization](#core-observability-initialization)
    *   [A2A Protocol Instrumentation with `A2AInstrumentor`](#a2a-protocol-instrumentation-with-a2ainstrumentor)
    *   [Decorator-Based Instrumentation in Practice](#decorator-based-instrumentation-in-practice)
        *   [`@agent` Decorator](#agent-decorator)
        *   [`@workflow` Decorator](#workflow-decorator)
        *   [`@task` Decorator](#task-decorator)
        *   [`@tool` Decorator](#tool-decorator)
    *   [Metrics](#metrics)
    *   [Session Tracing](#session-tracing)
9.  [Cloud Environment Deployment](#9-cloud-environment-deployment)
    *   [Overview](#overview)
    *   [Deployment Guide](#deployment-guide)
    *   [Important Considerations](#important-considerations)
    *   [Required Ports](#required-ports)
10. [Benefits of Observe Integration](#10-benefits-of-observe-integration)
11. [Security Considerations](#11-security-considerations)
12. [Performance Impact](#12-performance-impact)
13. [Error Handling & Verification](#13-error-handling--verification)
14. [Best Practices](#14-best-practices)
15. [Troubleshooting](#15-troubleshooting)
16. [References](#16-references)

---

## 1. Introduction

In modern microservices architectures, robust observability is paramount for understanding application behavior, performance, and potential issues, enabling rapid diagnosis and resolution. The `ioa_observe.sdk` is a powerful toolkit designed to simplify this integration, providing a standardized entry point for setting up unified logging, metrics, and tracing.

This SDK is particularly effective in complex, interactive systems like the Healthcare Voice + A2A + MCP Agent and the A2A Medical Triage Service. It empowers developers and operations teams to gain deep insights into agent-to-agent (A2A) interactions, external service calls, and internal logic, ensuring comprehensive monitoring, debugging, and performance analysis. By integrating with OpenTelemetry, it promotes vendor-agnostic telemetry collection, ensuring operational excellence.

## 2. Key Concepts & SDK Overview

The `ioa_observe.sdk` facilitates "observability by default" by abstracting OpenTelemetry complexities and providing intuitive tools for instrumentation.

### Telemetry Data Types

By integrating the `ioa_observe.sdk`, services automatically collect and export various telemetry data:

*   **Distributed Traces**: End-to-end execution paths of requests, illustrating how different service components and external interactions contribute to a complete operation.
*   **Metrics**: Quantitative measurements of service performance and health, such as request rates, error counts, latency, connection reliability, data transfer accuracy, uptime and availability.
*   **Spans**: Granular units within a trace, representing individual operations (e.g., function calls, HTTP requests) with details like execution time, status, and associated attributes.
*   **Logs**: Structured log messages that are automatically correlated with their respective traces and spans, simplifying debugging and contextual analysis.

### `ioa_observe.sdk` Decorators

The SDK offers specialized decorators to instrument code components with minimal effort, automatically generating telemetry data for key operational units:

*   **`@agent`**: For agent classes or methods representing autonomous AI agents, capturing their execution flow and decisions.
    *   **Usage**: `@agent(name='agent_name', description='agent_description')`
*   **`@workflow`**: For orchestrating multiple tasks, agents, or complex business processes, providing an end-to-end view of a multi-step operation.
    *   **Usage**: `@workflow(name='workflow_name')`
*   **`@task`**: For individual, discrete functions or methods that perform specific, atomic operations within a workflow.
    *   **Usage**: `@task(name='task_name')`
*   **`@tool`**: Applied to functions that act as tools or integrate with external services (e.g., API calls, database interactions, LLM calls).
    *   **Usage**: `@tool(name='tool_name')`

These decorators automatically create spans and contextual information, enriching your traces and making it easier to understand the flow and performance of your application.

## 3. Features

*   **Unified Observability**: Streamlines the initialization of logging, metrics, and tracing functionalities from a single function call.
*   **OpenTelemetry Compatibility**: Exports telemetry data via an OTLP HTTP endpoint, allowing integration with various OpenTelemetry-compatible collectors and observability platforms.
*   **Dynamic Configuration**: Utilizes environment variables for flexible configuration of the API endpoint, service version, and deployment environment.
*   **Service-Specific Attributes**: Automatically enriches telemetry data with essential resource attributes like `service.name`, `service.version`, `environment`, and `system.type` (fixed as "voice_agent" for some contexts).
*   **Robust Initialization**: Includes a verification step to confirm successful initialization of the tracing component and comprehensive error handling.
*   **Decorator-Based Instrumentation**: Simplifies code instrumentation through intuitive decorators, reducing boilerplate and promoting consistent telemetry capture.
*   **A2A Protocol-Aware Instrumentation**: Dedicated `A2AInstrumentor` for automatic tracing of A2A communication, linking spans to A2A task and message IDs.

## 4. Prerequisites

Before using this SDK, ensure you have the following:

*   **Python 3.x**: The SDK requires a compatible Python interpreter.
*   **`ioa_observe.sdk`**: This is an internal or custom SDK. You will need to obtain and install this package from your organization's internal package repository or source.
*   **Observability Backend**: An OpenTelemetry-compatible observability backend (e.g., OpenTelemetry Collector, Jaeger, Prometheus, or a commercial observability platform) must be running and accessible at the configured `OTLP_HTTP_ENDPOINT`.
*   **Docker and Docker Compose**: For local development and testing, `docker-compose` is essential for setting up the OpenTelemetry Collector, ClickHouse, and Grafana.

## 5. Installation

1.  **Python**: Ensure Python 3.x is installed on your system.
2.  **`ioa_observe.sdk`**: Install the `ioa_observe.sdk` package. The exact command will depend on how your organization distributes it.
    *   **From PyPI (if available)**: `pip install ioa_observe_sdk`
    *   **From Git Repository**: `pip install git+https://github.com/agntcy/observe` (or use `uv add` if using `uv` package manager).

## 6. Configuration

The `initialize_observability` function and the local development environment rely on several environment variables for their configuration. These variables should typically be managed via a `.env` file for local development and through secure secrets management systems in production environments.

### Environment Variables

*   **`OTLP_HTTP_ENDPOINT`**: (Optional) The HTTP endpoint for the OpenTelemetry Protocol (OTLP) exporter. This is where your telemetry data will be sent.
    *   **Default**: `http://localhost:4318`
    *   **Example**: `export OTLP_HTTP_ENDPOINT="http://my-otel-collector:4318"`
*   **`SERVICE_NAME`**: (Optional) The name of your service. This is a crucial identifier for your service in the observability backend.
    *   **Default**: `observe_service`
    *   **Example**: `export SERVICE_NAME="my-healthcare-agent"`
*   **`SERVICE_VERSION`**: (Optional) The version of your service. This is included as a resource attribute in all telemetry.
    *   **Default**: `1.0.0`
    *   **Example**: `export SERVICE_VERSION="2.1.0"`
*   **`ENVIRONMENT`**: (Optional) The deployment environment (e.g., `development`, `staging`, `production`). This is included as a resource attribute.
    *   **Default**: `development`
    *   **Example**: `export ENVIRONMENT="production"`

**Note on Metrics Endpoint**: The metrics endpoint is automatically derived from `OTLP_HTTP_ENDPOINT` by replacing port `4318` with `4317` if `4318` is present. This is a common convention in OpenTelemetry setups where traces and logs use `4318` and metrics use `4317`.

### Local Configuration Files

For local development, you will typically set up the following files:

*   **`.env` file**: Stores local secrets and configuration variables.
    *   **Content**: Must contain `OTLP_HTTP_ENDPOINT` and `SERVICE_NAME`. Other variables like `SERVICE_VERSION` and `ENVIRONMENT` are optional but recommended.
    *   **Example**:
        ```
        OTLP_HTTP_ENDPOINT=http://localhost:4318
        SERVICE_NAME=my-healthcare-agent
        SERVICE_VERSION=1.0.0
        ENVIRONMENT=development
        ```
*   **`docker-compose.yml`**: Defines the services required for your local observability stack (OpenTelemetry Collector, ClickHouse, Grafana).
    *   **Purpose**: To run the observability infrastructure locally.
    *   **Commands**: `docker-compose up -d`, `docker-compose down`, `docker-compose logs`.
*   **`otel-collector.yaml`**: Configuration for the OpenTelemetry Collector, specifying how it collects, processes, and exports traces, metrics, and logs (e.g., to ClickHouse).

## 7. Getting Started (Local Development)

This section outlines the steps to set up and integrate observability into your application for local development and testing.

### Initial Setup

1.  **Required Files**: Ensure you have `docker-compose.yml`, `otel-collector.yaml`, and an `observe` initialization file (containing the `initialize_observability` function) in your project.
2.  **`.env` File**: Create a `.env` file in your project root to store local configuration variables.
3.  **Initialize Observe**: It is crucial to initialize the `observe` SDK *before* invoking any agents or decorated functions. This ensures that the observability context is established from the very beginning of your application's execution.

### Decorator Integration

1.  **Import Decorators**: Import the necessary decorators from the `ioa_observe.sdk.decorators` module:
    ```python
    from ioa_observe.sdk.decorators import agent, tool, workflow, task
    ```
2.  **Apply Decorators**: Apply the appropriate decorators to your functions, methods, or classes based on their role:
    ```python
    # Example: A discrete function
    @task(name='process_data')
    def process_data(data):
        # ... logic ...
        return processed_data

    # Example: An external service integration
    @tool(name='call_api')
    def fetch__record(doc_id):
        # ... API call logic ...
        return record_data

    # Example: An AI agent method
    @agent(name='chatbot', description='AI agent for inquiries')
    class Chatbot:
        def __init__(self):
            pass
        # ... agent methods ...

    # Example: A complex business process
    @workflow(name='onboarding_workflow')
    def onboarding_flow(info):
        # ... orchestrate tasks and tools ...
        return onboarding_status
    ```

### Local Execution Steps

1.  **Install SDK**:
    ```bash
    pip install ioa_observe_sdk # or uv add git+https://github.com/agntcy/observe
    ```
2.  **Setup Files**: Ensure `docker-compose.yml`, `otel-collector.yaml`, `.env`, and your observability initialization code are correctly set up.
3.  **Integrate Decorators**: Import and apply the `ioa_observe` decorators to your source code as described above.
4.  **Initialize Observe**: Make sure to call `initialize_observability` early in your application's lifecycle.
    ```python
    import os
    # ... other imports ...

    def initialize_observability(service_name):
        """Initialize observability with proper configuration for healthcare MAS"""
        try:
            from ioa_observe.sdk.logging.logging import LoggerWrapper
            from ioa_observe.sdk.metrics.metrics import MetricsWrapper
            from ioa_observe.sdk.tracing.tracing import TracerWrapper
            from ioa_observe.sdk import Observe

            service_name_actual = os.getenv("SERVICE_NAME", service_name)
            api_endpoint = os.getenv("OTLP_HTTP_ENDPOINT", "http://localhost:4318")

            print(f"OBSERVE_INIT: Initializing observability for service: {service_name_actual}")

            Observe.init(service_name_actual, api_endpoint=api_endpoint)

            TracerWrapper.set_static_params(
                resource_attributes={
                    "service.name": service_name_actual,
                    "service.version": os.getenv("SERVICE_VERSION", "1.0.0"),
                    "environment": os.getenv("ENVIRONMENT", "development"),
                    "system.type": "voice_agent"
                },
                enable_content_tracing=True,
                endpoint=api_endpoint,
                headers={}
            )

            LoggerWrapper.set_static_params(
                resource_attributes={
                    "service.name": service_name_actual,
                    "service.version": os.getenv("SERVICE_VERSION", "1.0.0"),
                    "environment": os.getenv("ENVIRONMENT", "development")
                },
                endpoint=api_endpoint,
                headers={}
            )

            metrics_endpoint = api_endpoint.replace('4318','4317') if "4318" in api_endpoint else api_endpoint
            MetricsWrapper.set_static_params(
                resource_attributes={
                    "service.name": service_name_actual,
                    "service.version": os.getenv("SERVICE_VERSION", "1.0.0")
                },
                endpoint=metrics_endpoint,
                headers={}
            )

            MetricsWrapper()
            TracerWrapper()
            LoggerWrapper()

            if not TracerWrapper.verify_initialized():
                raise Exception("TracerWrapper failed to initialize")
            return True
        except Exception as e:
            print(f"OBSERVE_INIT: Error initializing observability: {e}")
            return False

    # In your main application file:
    if __name__ == "__main__":
        service_name_for_init = "my-application"
        if initialize_observability(service_name_for_init):
            print("Observability initialized. Your application can now send telemetry.")
            # Your main application logic here
        else:
            print("Failed to initialize observability.")
    ```
5.  **Start Docker Compose**:
    ```bash
    docker-compose up -d
    ```
6.  **Run Source Code**: Execute your Python application.
7.  **Check Logs**:
    ```bash
    docker-compose logs
    ```
8.  **Access ClickHouse DB**: To inspect raw telemetry data:
    ```bash
    docker exec -it clickhouse-server clickhouse-client
    ```
9.  **Visualize in Grafana**: Access Grafana at `http://localhost:3000` to view dashboards and explore metrics, traces, and logs.

## 8. Instrumentation Details

The `ioa_observe.sdk` provides a comprehensive approach to instrumenting various components of a microservice, especially within the context of healthcare agents.

### Core Observability Initialization

The foundational setup for observability occurs through the `initialize_observability` function. This function configures OpenTelemetry exporters and resource attributes, establishing the global context for telemetry.

*   **Global Initialization Example (Healthcare Voice Agent)**:
    ```python
    from triage_agent.infermedica.agntcy.observe_config.observe_config import initialize_observability
    # ...
    def run_agent():
        # ...
        service_name = "Healthcare_Voice_Agent"
        initialize_observability(service_name)
    ```
*   **A2A Client Specific Initialization**:
    ```python
    from ioa_observe.sdk import Observe
    from ioa_observe.sdk.instrumentations.a2a import A2AInstrumentor
    # ...
    class A2AClient:
        def __init__(self):
            # ...
            api_endpoint = os.getenv('OTLP_ENDPOINT', 'http://localhost:4318')
            Observe.init("A2A_Client", api_endpoint=api_endpoint)
            A2AInstrumentor().instrument() # Crucial for A2A protocol tracing
    ```
    The `A2AClient` explicitly initializes `Observe` for its own operations, specifying a service name "A2A_Client" and an OTLP endpoint.

### A2A Protocol Instrumentation with `A2AInstrumentor`

The `ioa_observe.sdk.instrumentations.a2a.A2AInstrumentor` is specifically designed for out-of-the-box observability for services adhering to the Agent-to-Agent (A2A) protocol.

*   **Implementation**:
    ```python
    from ioa_observe.sdk.instrumentations.a2a import A2AInstrumentor
    # ...
    # In A2AClient or main entry point
    A2AInstrumentor().instrument()
    ```
    This call automatically hooks into the A2A communication mechanisms (e.g., HTTP requests made by the `requests` library), enriching them with A2A-specific context. This ensures that incoming A2A requests and outgoing A2A responses are automatically wrapped in spans, providing visibility into the A2A protocol's lifecycle and linking traces to A2A task and message IDs.

### Decorator-Based Instrumentation in Practice

The `ioa_observe.sdk` decorators automatically instrument key components, turning them into observable units (spans in traces).

#### `@agent` Decorator

Marks the primary service class, providing high-level metadata about the agent itself.

*   **Healthcare Voice Agent Example**:
    ```python
    @agent(name="healthcare_agent", description="healthcare voice agent", version="1.0.0", protocol="A2A")
    class HealthcareAgent:
        # ...
    ```
*   **A2A Medical Triage Service Example**:
    ```python
    @agent(name='a2a_triage_service', description='A2A Medical Triage Service', version='1.0.0', protocol="A2A")
    class A2ATriageService:
        # ...
    ```

#### `@workflow` Decorator

Applied to methods that represent a sequence of operations forming a distinct business process or workflow.

*   **Healthcare Voice Agent Examples**:
    ```python
    @workflow(name="integrated_triage_workflow")
    async def _start_integrated_triage(self):
        # ...

    @workflow(name="triage_conversational_flow")
    async def _handle_triage_conversation(self, user_input):
        # ...
    ```
*   **A2A Medical Triage Service Examples**:
    ```python
    @workflow(name="medical_triage_workflow", description="complete medical triage workflow", version=1)
    def _create_new_task(self, user_text, context_id, request_id, original_message):
        # ...

    @workflow(name="start_triage_session", description="start a new triage session with external API", version=1)
    def _start_triage_session(self, age, sex, complaint, task):
        # ...
    ```

#### `@task` Decorator

Designates methods that perform specific, often atomic, units of work within a workflow. The `A2AInstrumentor` will also create spans for A2A tasks.

*   **A2A Medical Triage Service Examples**:
    ```python
    @task(name="handle_a2a_message", description="process incoming a2a message from agent", version=1)
    def _handle_message_send(self, params, request_id):
        # ...

    @task(name="create_triage_survey", description="create a new triage survey session", version=1)
    def _create_triage_survey(self, token, age, sex):
        # ...
    ```

#### `@tool` Decorator

Used for methods that represent calls to external services, utility functions, or specific capabilities.

*   **Healthcare Voice Agent Examples**:
    *   **Audio System Tools**: `listen`, `speak`
    *   **A2A Message Tool**: `send_message` (instruments the `A2AClient`'s message sending)
    *   **LLM Tool**: `process` (tracks calls to Large Language Models)
    *   **Insurance Client Tools (MCP Protocol)**: `discovery`, `eligibility` (instruments interactions with the Insurance Client using MCP)
*   **A2A Medical Triage Service Examples**:
    ```python
    @tool(name="extract_demographics")
    def _extract_demographics(self, text):
        # ...

    @tool(name="send_triage_message")
    def _send_triage_message(self, task, message):
        # ...
    ```

### Metrics

The agent records specific metrics related to its availability and activity using `ioa_observe.sdk.metrics.agents.availability`.

*   `agent_availability.record_agent_heartbeat("healthcare_voice_agent")`: Indicates the agent is alive and operational, recorded at startup and periodically.
*   `agent_availability.record_agent_activity("healthcare_voice_agent", success=True/False)`: Tracks the agent's activity and whether an interaction was successful or not.

### Session Tracing

The `session_start()` function (from `ioa_observe.sdk.tracing`) is used to mark the beginning of a new session or a significant interaction within a trace, helping organize traces in long-running conversations.

*   **Example**:
    ```python
    from ioa_observe.sdk.tracing import session_start
    # ...
    class A2AClient:
        async def send_message(self, message_parts, task_id=None, context_id=None):
            # ...
            session_start()
            # ...
    ```

## 9. Cloud Environment Deployment

### Overview

Deploying observability components in a cloud environment (e.g., AWS EC2) requires careful orchestration for secure, scalable, and reliable telemetry collection. This guide outlines setting up the `ioa_observe` observability stack (OpenTelemetry Collector, ClickHouse, Grafana) and integrating your application.

### Deployment Guide

1.  **Access the EC2 Instance**: Establish a secure SSH connection to your designated EC2 cloud server.
    `ssh -i <your-ssh-key.pem> ec2-user@<your-ec2-public-ip>`
2.  **Organize the Environment**: Create a dedicated directory structure on the EC2 instance.
    `mkdir -p ~<folderpath>/observe/deploy && cd ~<folderpath>/observe/deploy`
3.  **Prepare Configuration Files**: Download necessary deployment configuration files (e.g., `docker-compose.yml`, `otel-collector.yaml`) from your repository.
4.  **Configure `.env` File**: Edit the `.env` file to match your environment's requirements, including robust passwords for `CLICKHOUSE_PASSWORD` and `GRAFANA_ADMIN_PASSWORD`.
5.  **Execute Deployment Automation**: Make the deployment script executable and run it.
    `chmod +x deploy.sh && ./deploy.sh`
6.  **Secure Credentials and Endpoints**: Securely store generated credentials and service URLs (ClickHouse, Grafana, OpenTelemetry Collector HTTP endpoint).
7.  **Integrate OpenTelemetry Endpoint**: Update your application's configuration with the provided OpenTelemetry HTTP endpoint (e.g., `OTLP_HTTP_ENDPOINT=http://<your-ec2-private-ip>:4318`).
8.  **Access and Visualize with Grafana**: Navigate to the Grafana URL, log in, configure data sources, and visualize your application's telemetry.

### Important Considerations

*   **Security Group Configuration**: Ensure necessary ports (listed below) are open in your EC2 security group.
*   **Credential Management**: Use secure secrets management solutions; never commit credentials to source control.
*   **Environment Variables**: Update specific environment variables as needed.
*   **Persistent Storage**: Configure `DATA_PATH` for persistent storage (e.g., EBS volume) to prevent data loss.

### Required Ports

*   **Grafana Dashboard**: `3000` (web UI access)
*   **OTEL gRPC endpoint**: `4317` (for gRPC-based telemetry, often metrics)
*   **OTEL HTTP endpoint**: `4318` (for HTTP-based telemetry, often traces and logs)
*   **OTEL Metrics (optional)**: `8888` (if collector exposes Prometheus endpoint)
*   **OTEL Health Check (optional)**: `13133` (for collector health checks)

## 10. Benefits of Observe Integration

The comprehensive `ioa_observe.sdk` integration provides significant advantages:

*   **Enhanced Visibility**: Provides a complete, end-to-end view of request lifecycles, from initial A2A message receipt to external API calls and final response generation.
*   **Performance Diagnostics**: Enables easy identification of performance bottlenecks by analyzing span durations across different components and external dependencies.
*   **Streamlined Debugging**: Correlates logs directly with traces, allowing developers to quickly understand the context of errors and exceptions.
*   **Operational Insights**: Offers a clear understanding of the service's health, throughput, and error rates in real-time.
*   **Proactive Monitoring**: Facilitates the creation of alerts and dashboards based on collected metrics and traces, enabling proactive issue detection and resolution.
*   **Protocol-Aware Observability**: The `A2AInstrumentor` specifically ensures that the unique aspects of the A2A protocol are properly traced, providing contextually relevant observability for agent interactions.

## 11. Security Considerations

*   **Endpoint Security**: Secure the OTLP endpoint with TLS/SSL and restrict network access.
*   **Credential Handling**: Utilize environment variables or secrets management services; never hardcode sensitive credentials.
*   **Data Minimization**: Avoid including Personally Identifiable Information (PII) or Protected Health Information (PHI) in telemetry unless absolutely necessary and properly anonymized/encrypted, adhering to healthcare compliance standards (e.g., HIPAA).
*   **Access Control**: Implement strict access control for your observability backend.

## 12. Performance Impact

The `ioa_observe` SDK is designed to be lightweight and efficient, introducing minimal overhead.

*   **Minimal Overhead**: Optimized for low latency and minimal CPU usage.
*   **Batching and Asynchronous Export**: Telemetry data is typically batched and exported asynchronously.
*   **Configuration Impact**: The volume of data collected and network latency can influence performance. Monitor resource usage and adjust sampling rates if necessary.

## 13. Error Handling & Verification

The `initialize_observability` function includes robust error handling:

*   It is wrapped in a `try-except` block, catching exceptions during initialization.
*   An informative message is printed on error, and the function returns `False`.
*   A `TracerWrapper.verify_initialized()` check ensures the tracing component is successfully set up, raising an `Exception` if it fails, indicating a critical issue.

## 14. Best Practices

*   **Early Initialization**: Always call `initialize_observability` at the very beginning of your application's lifecycle.
*   **Consistent Naming**: Use clear and consistent `service_name`, `task_name`, `tool_name`, `agent_name`, and `workflow_name`.
*   **Contextual Attributes**: Add meaningful attributes to spans and logs (e.g., `user_id`, `patient_id`, `request_id`).
*   **Monitor Observability Stack**: Ensure your OpenTelemetry Collector, ClickHouse, and Grafana instances are themselves monitored.
*   **Sampling**: In high-volume environments, consider trace sampling strategies.
*   **Documentation**: Document custom metrics and log fields.

## 15. Troubleshooting

*   **"TracerWrapper failed to initialize"**: Verify `OTLP_HTTP_ENDPOINT` and ensure the OpenTelemetry Collector is running and accessible.
*   **No Telemetry Data**:
    *   Check `initialize_observability` return value.
    *   Review `docker-compose logs` for errors.
    *   Confirm correct decorator application and network connectivity.
*   **Incorrect Data**:
    *   Review decorator parameters.
    *   Inspect raw data in ClickHouse.
    *   Check `otel-collector.yaml` configuration.
*   **Grafana Issues**:
    *   Ensure Grafana is running.
    *   Verify data source configuration.
    *   Check Grafana logs.

## 16. References

*   [ioa_observe SDK GitHub Repository](https://github.com/agntcy/observe/blob/main/README.md)  
 
