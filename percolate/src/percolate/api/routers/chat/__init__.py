"""OpenAI-compatible chat completions router."""

from percolate.api.routers.chat.completions import router

# Import feedback to register endpoint
import percolate.api.routers.chat.feedback  # noqa: F401

__all__ = ["router"]
