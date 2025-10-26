"""Utility functions for memory operations."""

from datetime import datetime


def utc_timestamp() -> str:
    """Get current UTC timestamp in ISO 8601 format with 'Z' suffix.

    Returns:
        ISO 8601 timestamp string (e.g., "2025-10-26T14:30:00.123456Z")

    Example:
        >>> ts = utc_timestamp()
        >>> ts.endswith("Z")
        True
    """
    return datetime.utcnow().isoformat() + "Z"
