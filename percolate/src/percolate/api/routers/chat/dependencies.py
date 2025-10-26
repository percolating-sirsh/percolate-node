"""FastAPI dependencies for chat endpoints."""

from fastapi import Header

from percolate.memory import SessionStore


def get_session_store(
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> SessionStore | None:
    """Get SessionStore instance if session tracking is enabled.

    Args:
        x_session_id: Optional session ID from request header

    Returns:
        SessionStore instance if session_id provided, None otherwise
    """
    return SessionStore() if x_session_id else None
