#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
OpenTelemetry Tracing Configuration for Tourist Scheduling System.

Provides centralized tracing setup that integrates with:
- Google ADK (agent execution traces)
- A2A protocol (message/task traces)
- SLIM transport (MLS message traces)

Supports multiple exporters:
- Console (for development)
- OTLP (for Jaeger, Zipkin, etc.)
- File (for offline analysis)
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Check if OpenTelemetry is available
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SimpleSpanProcessor,
    )
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.propagate import set_global_textmap

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.debug("OpenTelemetry not installed, tracing disabled")

# Try to import OTLP exporter
try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    OTLP_AVAILABLE = True
except ImportError:
    OTLP_AVAILABLE = False


def get_traces_dir() -> Path:
    """Get the traces directory, creating it if necessary."""
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            traces_dir = current / "traces"
            break
        current = current.parent
    else:
        traces_dir = Path.cwd() / "traces"

    traces_dir.mkdir(parents=True, exist_ok=True)
    return traces_dir


class FileSpanExporter:
    """Simple file-based span exporter for offline analysis."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.file = open(file_path, "a", encoding="utf-8")

    def export(self, spans):
        import json
        from datetime import datetime

        for span in spans:
            record = {
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": format(span.context.trace_id, "032x"),
                "span_id": format(span.context.span_id, "016x"),
                "parent_span_id": format(span.parent.span_id, "016x") if span.parent else None,
                "name": span.name,
                "kind": str(span.kind),
                "status": str(span.status.status_code) if span.status else None,
                "start_time": span.start_time,
                "end_time": span.end_time,
                "attributes": dict(span.attributes) if span.attributes else {},
                "events": [
                    {"name": e.name, "timestamp": e.timestamp, "attributes": dict(e.attributes)}
                    for e in span.events
                ] if span.events else [],
            }
            self.file.write(json.dumps(record) + "\n")
            self.file.flush()

        return True

    def shutdown(self):
        self.file.close()

    def force_flush(self, timeout_millis: int = 30000):
        self.file.flush()


_tracer_provider: Optional["TracerProvider"] = None
_initialized = False


def setup_tracing(
    service_name: str = "tourist-scheduling",
    otlp_endpoint: Optional[str] = None,
    console_export: bool = False,
    file_export: bool = True,
) -> Optional["TracerProvider"]:
    """
    Set up OpenTelemetry tracing for the application.

    Args:
        service_name: Name of the service for trace identification
        otlp_endpoint: OTLP collector endpoint (e.g., "http://localhost:4318/v1/traces")
        console_export: Enable console output of traces
        file_export: Enable file export of traces

    Returns:
        TracerProvider if successful, None if OTEL not available
    """
    global _tracer_provider, _initialized

    if _initialized:
        return _tracer_provider

    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available, tracing disabled")
        _initialized = True
        return None

    # Check environment for configuration
    otlp_endpoint = otlp_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    console_export = console_export or os.environ.get("OTEL_CONSOLE_EXPORT", "").lower() == "true"
    # Only use env var if explicitly set and non-empty, otherwise use passed service_name
    env_service_name = os.environ.get("OTEL_SERVICE_NAME", "").strip()
    if env_service_name:
        service_name = env_service_name

    # Ensure OTLP endpoint has the traces path for HTTP protocol
    if otlp_endpoint and not otlp_endpoint.endswith("/v1/traces"):
        otlp_endpoint = otlp_endpoint.rstrip("/") + "/v1/traces"

    # Create resource with service info
    resource = Resource.create({
        SERVICE_NAME: service_name,
        "service.version": "1.0.0",
        "deployment.environment": os.environ.get("ENVIRONMENT", "development"),
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add exporters
    exporters_added = 0

    # OTLP exporter (for Jaeger, Zipkin, etc.)
    if otlp_endpoint and OTLP_AVAILABLE:
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OTLP trace exporter configured: {otlp_endpoint}")
            exporters_added += 1
        except Exception as e:
            logger.warning(f"Failed to configure OTLP exporter: {e}")

    # Console exporter (for development)
    if console_export:
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(console_exporter))
        logger.info("Console trace exporter enabled")
        exporters_added += 1

    # File exporter (always useful for debugging)
    if file_export:
        try:
            traces_dir = get_traces_dir()
            from datetime import datetime
            trace_file = traces_dir / f"traces_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
            file_exporter = FileSpanExporter(trace_file)
            provider.add_span_processor(SimpleSpanProcessor(file_exporter))
            logger.info(f"File trace exporter configured: {trace_file}")
            exporters_added += 1
        except Exception as e:
            logger.warning(f"Failed to configure file exporter: {e}")

    if exporters_added == 0:
        logger.warning("No trace exporters configured, adding console exporter")
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(console_exporter))

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    # Set up context propagation (W3C Trace Context)
    set_global_textmap(TraceContextTextMapPropagator())

    _tracer_provider = provider
    _initialized = True

    logger.info(f"OpenTelemetry tracing initialized for service: {service_name}")
    return provider


def get_tracer(name: str = "tourist-scheduling"):
    """Get a tracer instance for creating spans."""
    if not OTEL_AVAILABLE:
        return None

    return trace.get_tracer(name)


def create_span(name: str, attributes: dict = None):
    """
    Context manager for creating a trace span.

    Usage:
        with create_span("process_request", {"request.id": "123"}):
            # do work
            pass
    """
    if not OTEL_AVAILABLE:
        from contextlib import nullcontext
        return nullcontext()

    tracer = get_tracer()
    return tracer.start_as_current_span(name, attributes=attributes)


def add_span_event(name: str, attributes: dict = None):
    """Add an event to the current span."""
    if not OTEL_AVAILABLE:
        return

    span = trace.get_current_span()
    if span:
        span.add_event(name, attributes=attributes or {})


def set_span_attribute(key: str, value):
    """Set an attribute on the current span."""
    if not OTEL_AVAILABLE:
        return

    span = trace.get_current_span()
    if span:
        span.set_attribute(key, value)


def set_span_error(exception: Exception):
    """Mark the current span as errored."""
    if not OTEL_AVAILABLE:
        return

    span = trace.get_current_span()
    if span:
        span.set_status(Status(StatusCode.ERROR, str(exception)))
        span.record_exception(exception)


def get_trace_context() -> dict:
    """
    Get the current trace context for propagation.

    Returns dict with 'traceparent' and optionally 'tracestate' headers.
    """
    if not OTEL_AVAILABLE:
        return {}

    from opentelemetry.propagate import inject
    carrier = {}
    inject(carrier)
    return carrier


def extract_trace_context(headers: dict):
    """
    Extract trace context from incoming headers.

    Call this at the start of request handling to continue a trace.
    """
    if not OTEL_AVAILABLE:
        return None

    from opentelemetry.propagate import extract
    return extract(headers)


# Convenience decorators
def traced(name: str = None, attributes: dict = None):
    """
    Decorator to automatically trace a function.

    Usage:
        @traced("my_function")
        def my_function(arg1, arg2):
            pass
    """
    def decorator(func):
        span_name = name or func.__name__

        if not OTEL_AVAILABLE:
            return func

        import functools

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(span_name, attributes=attributes or {}):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    set_span_error(e)
                    raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(span_name, attributes=attributes or {}):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    set_span_error(e)
                    raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator
