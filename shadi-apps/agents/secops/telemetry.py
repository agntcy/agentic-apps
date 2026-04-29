# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
OpenTelemetry setup for the shadi-secops agent.

Configure export with standard OTel env vars:
  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318  (OTLP/HTTP)
  OTEL_SERVICE_NAME=shadi-secops                     (default)

Set SHADI_OTEL_CONSOLE=1 to print spans to stdout when no OTLP endpoint is set.

Without any configuration, all telemetry is a no-op.
"""
import os

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME") or "shadi-secops"

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import SERVICE_NAME as RES_SERVICE_NAME
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    # Use Resource() directly (not Resource.create()) so the SDK's environment
    # detectors cannot override our explicit service.name with "unknown_service".
    _resource = Resource(
        attributes={
            RES_SERVICE_NAME: SERVICE_NAME,
            "service.namespace": "shadi",
            "telemetry.sdk.language": "python",
        }
    )
    _provider = TracerProvider(resource=_resource)

    _endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if _endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            _exporter = OTLPSpanExporter(endpoint=_endpoint.rstrip("/") + "/v1/traces")
            _provider.add_span_processor(BatchSpanProcessor(_exporter))
        except ImportError:
            pass  # OTLP exporter package not installed

    if not _endpoint and os.getenv("SHADI_OTEL_CONSOLE", "").strip() in ("1", "true", "yes"):
        _provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(_provider)
    tracer = trace.get_tracer("shadi.secops")

except ImportError:
    # Graceful no-op when opentelemetry packages are not installed.

    class _Span:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def add_event(self, *_, **__):
            pass

        def set_attribute(self, *_, **__):
            pass

        def record_exception(self, *_, **__):
            pass

        def set_status(self, *_, **__):
            pass

    class _SpanCtx:
        def __init__(self, *_, **__):
            self._span = _Span()

        def __enter__(self):
            return self._span

        def __exit__(self, *_):
            pass

    class _NoOpTracer:
        def start_as_current_span(self, name, *_, **__):
            return _SpanCtx(name)

    tracer = _NoOpTracer()
