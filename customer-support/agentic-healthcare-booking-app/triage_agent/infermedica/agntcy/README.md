# Observe Integration in A2A Medical Triage Service

This document provides a focused overview of how Observe SDK has been integrated into the A2A Medical Triage Service to enhance observability, tracing, and monitoring.

## Table of Contents

- [Observe Integration in A2A Medical Triage Service](#observe-integration-in-a2a-medical-triage-service)
  - [1. Overview of Observe](#1-overview-of-observe)
  - [2. Implementation Details](#2-implementation-details)
    - [2.1. Initializing Observability](#21-initializing-observability)
    - [2.2. A2A Protocol Instrumentation with `A2AInstrumentor`](#22-a2a-protocol-instrumentation-with-a2ainstrumentor)
    - [2.3. Decorator-Based Instrumentation](#23-decorator-based-instrumentation)
      - [2.3.1. `@agent`](#231-agent)
      - [2.3.2. `@workflow`](#232-workflow)
      - [2.3.3. `@task`](#233-task)
      - [2.3.4. `@tool`](#234-tool)
  - [3. Benefits of Observe Integration](#3-benefits-of-observe-integration)

---

## 1. Overview of Observe

Observe is a comprehensive observability platform that empowers developers and operations teams to gain deep insights into their application's behavior in production. By integrating the Observe SDK, this A2A Medical Triage Service automatically collects and exports various telemetry data, including:

*   **Distributed Traces**: End-to-end execution paths of requests, illustrating how different service components and external interactions contribute to a complete operation.
*   **Metrics**: Quantitative measurements of service performance and health, such as request rates, error counts, latency, and resource utilization. These are collected automatically by the SDK and can be further enriched with custom metrics.
*   **Spans**: Granular units within a trace, representing individual operations (e.g., function calls, HTTP requests) with details like execution time, status, and associated attributes.
*   **Logs**: Structured log messages that are automatically correlated with their respective traces and spans, simplifying debugging and contextual analysis.

This integration is crucial for understanding the flow of complex agent-to-agent interactions and external API calls within the triage service.

## 2. Implementation Details

The Observe SDK is strategically integrated into the A2A Medical Triage Service using a combination of initialization functions, protocol-specific instrumentors, and Python decorators.

### 2.1. Initializing Observability

The first step in enabling Observe is to initialize the SDK. This is typically done at the application's startup.

**Implementation:**
```python
# In the main() entry point function
from agntcy.observe.observe_config import initialize_observability

def main():
    # ...
    initialize_observability("a2a_triage_service")
    # ...
```
The `initialize_observability("a2a_triage_service")` call sets up the necessary OpenTelemetry exporters and processors, configuring the service to send its telemetry data to the Observe backend under the service name "a2a_triage_service".
For observe_config refer https://github.com/techm-2025/customer-support/tree/main/agentic-healthcare-booking-app/common/agntcy/observe/observe_config.py

### 2.2. A2A Protocol Instrumentation with `A2AInstrumentor`

The `ioa_observe.sdk.instrumentations.a2a.A2AInstrumentor` is specifically designed to provide out-of-the-box observability for services adhering to the Agent-to-Agent (A2A) protocol.

**Implementation:**
```python
# In the main() entry point function
from ioa_observe.sdk.instrumentations.a2a import A2AInstrumentor

def main():
    # ...
    A2AInstrumentor().instrument()
    # ...
```
By calling `A2AInstrumentor().instrument()`, the SDK automatically hooks into the A2A communication mechanisms of the service. This ensures that incoming A2A requests (e.g., `message/send`, `tasks/get`, `tasks/cancel`) and outgoing A2A responses are automatically wrapped in spans, providing visibility into the A2A protocol's lifecycle without manual instrumentation for each endpoint. This is a key feature for tracking the agent's interactions.

### 2.3. Decorator-Based Instrumentation

The `ioa_observe.sdk.decorators` module offers a convenient way to instrument specific classes and methods within the service, categorizing them into logical observable units.

#### 2.3.1. `@agent`

The `@agent` decorator is used to mark the primary service class, providing high-level metadata about the agent itself.

**Implementation:**
```python
from ioa_observe.sdk.decorators import agent

@agent(name='a2a_triage_service', description='A2A Medical Triage Service', version='1.0.0', protocol="A2A")
class A2ATriageService:
    # ...
```
This decorator defines the `A2ATriageService` as an observable `agent`, registering its name, description, version, and indicating its adherence to the "A2A" protocol within the Observe platform. This helps in identifying and filtering traces and metrics related to this specific agent.

#### 2.3.2. `@workflow`

The `@workflow` decorator is applied to methods that represent a sequence of operations forming a distinct business process or workflow.

**Implementation:**
```python
from ioa_observe.sdk.decorators import workflow

@workflow(name="medical_triage_workflow", description="complete medical triage workflow", version=1)
def _create_new_task(self, user_text, context_id, request_id, original_message):
    # ...

@workflow(name="start_triage_session", description="start a new triage session with external API", version=1)
def _start_triage_session(self, age, sex, complaint, task):
    # ...
```
Methods like `_create_new_task` and `_start_triage_session` are marked as `workflow` spans. This allows Observe to visualize these multi-step processes as coherent units, making it easier to track the progress and performance of critical operations like initiating a medical triage session.

#### 2.3.3. `@task`

The `@task` decorator designates methods that perform specific, often atomic, units of work within a workflow.

**Implementation:**
```python
from ioa_observe.sdk.decorators import task

@task(name="handle_a2a_message", description="process incoming a2a message from agent", version=1)
def _handle_message_send(self, params, request_id):
    # ...

@task(name="create_triage_survey", description="create a new triage survey session", version=1)
def _create_triage_survey(self, token, age, sex):
    # ...
```
Methods such as `_handle_message_send` and `_create_triage_survey` are instrumented as `task` spans. This provides granular visibility into individual operations, allowing for detailed analysis of their execution time, success rate, and any errors encountered.

#### 2.3.4. `@tool`

The `@tool` decorator is used for methods that represent calls to external services, utility functions, or specific capabilities.

**Implementation:**
```python
from ioa_observe.sdk.decorators import tool

@tool(name="extract_demographics")
def _extract_demographics(self, text):
    # ...

@tool(name="send_triage_message")
def _send_triage_message(self, task, message):
    # ...
```
Methods like `_extract_demographics` and `_send_triage_message` are marked as `tool` spans. This helps in understanding the performance and reliability of auxiliary functions and external integrations, such as parsing user input or communicating with the external medical triage API.

## 3. Benefits of Observe Integration

The comprehensive Observe integration provides significant advantages for the A2A Medical Triage Service:

*   **Enhanced Visibility**: Provides a complete, end-to-end view of request lifecycles, from initial A2A message receipt to external API calls and final response generation.
*   **Performance Diagnostics**: Enables easy identification of performance bottlenecks by analyzing span durations across different components and external dependencies.
*   **Streamlined Debugging**: Correlates logs directly with traces, allowing developers to quickly understand the context of errors and exceptions.
*   **Operational Insights**: Offers a clear understanding of the service's health, throughput, and error rates in real-time.
*   **Proactive Monitoring**: Facilitates the creation of alerts and dashboards based on collected metrics and traces, enabling proactive issue detection and resolution.
*   **Protocol-Aware Observability**: The `A2AInstrumentor` specifically ensures that the unique aspects of the A2A protocol are properly traced, providing contextually relevant observability for agent interactions.
```  
 
