"""OpenTelemetry instrumentation for Percolate.

Provides OTEL setup and attribute management for tracing agent execution.
Disabled by default - enable via settings.otel_enabled=True.
"""

from percolate.otel.setup import setup_instrumentation, set_agent_attributes

__all__ = ["setup_instrumentation", "set_agent_attributes"]
