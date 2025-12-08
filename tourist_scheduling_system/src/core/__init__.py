# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""Core components for the A2A Summit Demo."""

from .logging_config import (
    setup_root_logging,
    setup_agent_logging,
    get_log_dir,
)

from .tracing import (
    setup_tracing,
    get_tracer,
    traced,
    create_span,
    add_span_event,
    set_span_attribute,
    OTEL_AVAILABLE,
)

__all__ = [
    # Logging
    "setup_root_logging",
    "setup_agent_logging",
    "get_log_dir",
    # Tracing
    "setup_tracing",
    "get_tracer",
    "traced",
    "create_span",
    "add_span_event",
    "set_span_attribute",
    "OTEL_AVAILABLE",
]