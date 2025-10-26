"""Utilities for capturing OTEL trace context."""

from opentelemetry import trace
from loguru import logger


def get_current_trace_context() -> dict[str, str | None]:
    """Get the current OTEL trace and span IDs.

    Returns:
        Dictionary with trace_id and span_id as hex strings, or None if not available

    Example:
        >>> context = get_current_trace_context()
        >>> context
        {
            "trace_id": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            "span_id": "1234567890abcdef"
        }
    """
    try:
        current_span = trace.get_current_span()
        if not current_span or not current_span.is_recording():
            logger.debug("No active OTEL span found")
            return {"trace_id": None, "span_id": None}

        span_context = current_span.get_span_context()
        if not span_context.is_valid:
            logger.debug("Invalid span context")
            return {"trace_id": None, "span_id": None}

        # Convert trace_id and span_id to hex strings
        trace_id = format(span_context.trace_id, "032x")
        span_id = format(span_context.span_id, "016x")

        logger.debug(f"Captured trace context: trace_id={trace_id}, span_id={span_id}")
        return {"trace_id": trace_id, "span_id": span_id}

    except Exception as e:
        logger.debug(f"Failed to get trace context: {e}")
        return {"trace_id": None, "span_id": None}
