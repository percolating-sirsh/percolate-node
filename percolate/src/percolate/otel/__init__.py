"""OpenTelemetry instrumentation for Percolate.

Provides OTEL setup and attribute management for tracing agent execution.
Disabled by default - enable via settings.otel.enabled=True.
"""

from percolate.otel.attributes import (
    set_agent_context_attributes,
    set_agent_resource_attributes,
)
from percolate.otel.context import get_current_trace_context
from percolate.otel.setup import setup_instrumentation

__all__ = [
    "setup_instrumentation",
    "set_agent_resource_attributes",
    "set_agent_context_attributes",
    "get_current_trace_context",
]
