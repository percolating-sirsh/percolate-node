"""Percolate API module."""

def __getattr__(name: str):
    """Lazy load app to avoid eager import of FastMCP."""
    if name == "app":
        from percolate.api.main import app
        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["app"]
