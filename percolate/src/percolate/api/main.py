"""Percolate API Server - FastAPI application with integrated MCP server.

This module provides the main FastAPI application with integrated MCP server
for agent-let execution and REM memory access.

Running the Server
------------------

Development (with auto-reload):
    uv run percolate serve --reload

Production:
    uv run percolate serve --host 0.0.0.0 --port 8000

Testing the Server
------------------

Health check:
    curl http://localhost:8000/health

Chat completions via API (OpenAI-compatible):
    curl -X POST http://localhost:8000/v1/chat/completions \
      -H "Content-Type: application/json" \
      -H "X-Tenant-Id: tenant-123" \
      -d '{"model": "percolate-test-agent", "messages": [{"role": "user", "content": "What is 2+2?"}]}'

MCP client connection:
    # Use SSE transport
    # MCP endpoint at: http://localhost:8000/mcp

Endpoints
---------
- /                         : API information
- /health                   : Health check with version
- /version                  : Detailed version information
- /v1/chat/completions      : OpenAI-compatible chat completions (agent-lets)
- /mcp                      : MCP endpoint (SSE transport)
- /docs                     : OpenAPI documentation
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from percolate.api.routers.chat import router as chat_router
from percolate.api.routers.device import router as device_router
from percolate.api.routers.health import router as health_router
from percolate.api.routers.oauth import router as oauth_router
from percolate.api.routers.oauth_dev import router as oauth_dev_router
from percolate.mcplib.server import create_mcp_server
from percolate.settings import settings
from percolate.version import __version__


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Percolate API")
    yield
    logger.info("Shutting down Percolate API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    # Create MCP server and get HTTP app
    mcp_server = create_mcp_server()
    mcp_app = mcp_server.http_app()

    # Combine lifespans
    @asynccontextmanager
    async def combined_lifespan(app: FastAPI):
        async with lifespan(app):
            async with mcp_app.router.lifespan_context(mcp_app):
                yield

    app = FastAPI(
        title="Percolate API",
        description="Privacy-first personal AI node - agent-lets and REM memory",
        version=__version__,
        lifespan=combined_lifespan,
    )

    # Define root endpoint BEFORE mounting MCP app
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "Percolate API",
            "version": __version__,
            "mcp_endpoint": "/mcp",
            "docs": "/docs",
            "auth_enabled": settings.auth.enabled,
            "auth_provider": settings.auth.provider if settings.auth.enabled else "disabled",
        }

    @app.get("/version")
    async def version():
        """Version information endpoint."""
        return {
            "version": __version__,
            "python_version": "3.11+",
            "otel_enabled": settings.otel_enabled,
            "auth_enabled": settings.auth.enabled,
        }

    # Register routers (order matters - health/oauth/device are public, chat may require auth)
    app.include_router(health_router)     # /health, /status - public
    app.include_router(oauth_router)      # /oauth/* - public
    app.include_router(oauth_dev_router)  # /oauth/dev/* - dev provider (public)
    app.include_router(device_router)     # /device/* - device registration (public)
    app.include_router(chat_router)       # /v1/chat/* - completions and feedback

    # Mount MCP server at root (creates /mcp endpoint)
    app.mount("/", mcp_app)

    return app


# Create application instance
app = create_app()


# Main entry point for uvicorn
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "percolate.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
