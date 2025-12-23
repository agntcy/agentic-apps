# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
import time
from datetime import datetime
from typing import Dict, Optional
from enum import Enum 
from ioa_observe.sdk.logging.logging import LoggerWrapper
from ioa_observe.sdk.metrics.metrics import MetricsWrapper
from ioa_observe.sdk.tracing.tracing import TracerWrapper
from ioa_observe.sdk import Observe


class OtlpHttp(Enum):
    """
    Enum for standard OTLP HTTP receiver ports.
    4318 is typically used for OTLP/HTTP traces and logs.
    4317 is typically used for OTLP/HTTP metrics.
    """
    TRACES_PORT = "4318"
    METRICS_PORT = "4317"

def initialize_observability(service_name):
    """Initialize observability with proper configuration for observe services"""
    try:
        service_name = service_name
        api_endpoint = os.getenv("OTLP_HTTP_ENDPOINT", f"http://localhost:{OtlpHttp.TRACES_PORT.value}")
        service_version = os.getenv("SERVICE_VERSION", "1.0.0")
        environment = os.getenv("ENVIRONMENT", "development")

        print(f"OBSERVE_INIT: Initializing observability for service: {service_name}")

        Observe.init(service_name, api_endpoint=api_endpoint)

        TracerWrapper.set_static_params(
            resource_attributes={
                "service.name": service_name,
                "service.version": service_version,
                "environment": environment,
                "system.type": "Agent"
            },
            enable_content_tracing=True,
            endpoint=api_endpoint,
            headers={}
        )

        LoggerWrapper.set_static_params(
            resource_attributes={
                "service.name": service_name,
                "service.version": service_version,
                "environment": environment
            },
            endpoint=api_endpoint,
            headers={}
        )

        metrics_endpoint = api_endpoint.replace(OtlpHttp.TRACES_PORT.value, OtlpHttp.METRICS_PORT.value)

        MetricsWrapper.set_static_params(
            resource_attributes={
                "service.name": service_name,
                "service.version": service_version
            },
            endpoint=metrics_endpoint,
            headers={}
        )

        MetricsWrapper()

        TracerWrapper()

        LoggerWrapper()

        # Verify initialization
        if not TracerWrapper.verify_initialized():
            raise Exception("TracerWrapper failed to initialize")
        return True
    except Exception as e:
        print(f"OBSERVE_INIT: Error initializing observability: {e}")
        return False