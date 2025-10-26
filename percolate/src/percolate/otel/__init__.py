"""OpenTelemetry instrumentation for Percolate.

Provides OTEL setup and attribute management for tracing agent execution.
Disabled by default - enable via settings.otel_enabled=True.
"""

from percolate.otel.setup import setup_instrumentation, set_agent_attributes
from percolate.otel.context import get_current_trace_context

__all__ = ["setup_instrumentation", "set_agent_attributes", "get_current_trace_context"]
