"""Health and status endpoints.

Public endpoints for health checks and system status.
No authentication required.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from percolate.version import __version__
from percolate.settings import settings

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(description="Health status (ok, degraded, down)")
    version: str = Field(description="Application version")


class StatusResponse(BaseModel):
    """System status response."""

    status: str = Field(description="System status")
    version: str = Field(description="Application version")
    auth_enabled: bool = Field(description="Whether authentication is enabled")
    auth_provider: str = Field(description="Authentication provider")
    mcp_enabled: bool = Field(description="Whether MCP server is enabled")


@router.get("/health")
async def health() -> HealthResponse:
    """Health check endpoint.

    Returns basic health status.
    No authentication required.

    Returns:
        HealthResponse with status and version
    """
    return HealthResponse(
        status="ok",
        version=__version__,
    )


@router.get("/status")
async def status() -> StatusResponse:
    """System status endpoint.

    Returns detailed system configuration.
    No authentication required.

    Returns:
        StatusResponse with configuration details
    """
    return StatusResponse(
        status="ok",
        version=__version__,
        auth_enabled=settings.auth.enabled,
        auth_provider=settings.auth.provider if settings.auth.enabled else "disabled",
        mcp_enabled=settings.mcp_enabled,
    )
