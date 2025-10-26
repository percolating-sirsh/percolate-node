"""OAuth 2.1 discovery and authentication status endpoints.

Provides OAuth/OIDC discovery metadata and authentication status.
These endpoints are PUBLIC (no auth required) for client bootstrapping.
"""

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from percolate.auth import OptionalUser
from percolate.auth.provider_factory import get_provider_instance
from percolate.auth.providers import OAuthProvider
from percolate.settings import settings

router = APIRouter(prefix="/oauth", tags=["OAuth Discovery"])


class AuthStatus(BaseModel):
    """Authentication status response."""

    enabled: bool = Field(description="Whether authentication is enabled")
    provider: str | None = Field(description="Provider name (device, oidc, disabled)")
    authenticated: bool = Field(description="Whether request is authenticated")
    user_id: str | None = Field(default=None, description="Current user ID if authenticated")


def _get_base_url(request: Request) -> str:
    """Get API base URL from request.

    Args:
        request: FastAPI request

    Returns:
        Base URL (e.g., https://api.percolate.app)
    """
    # Use X-Forwarded-Host if behind proxy (production)
    host = request.headers.get("x-forwarded-host") or request.headers.get(
        "host", "localhost:8000"
    )
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    return f"{scheme}://{host}".rstrip("/")


@router.get("/status")
async def auth_status(user: OptionalUser) -> AuthStatus:
    """Get authentication status.

    Public endpoint that returns current auth configuration and user status.
    No authentication required.

    Returns:
        AuthStatus with provider and user information
    """
    return AuthStatus(
        enabled=settings.auth.enabled,
        provider=settings.auth.provider if settings.auth.enabled else "disabled",
        authenticated=user is not None,
        user_id=user.user_id if user else None,
    )


@router.get("/.well-known/openid-configuration")
async def openid_configuration(
    request: Request,
    provider: OAuthProvider | None = Depends(get_provider_instance),
) -> dict[str, Any]:
    """OpenID Connect discovery endpoint.

    Returns OAuth/OIDC metadata for client configuration.
    No authentication required.

    Returns:
        OIDC discovery document
    """
    if not provider or not settings.auth.enabled:
        return {
            "error": "authentication_disabled",
            "message": "Authentication is disabled",
        }

    base_url = _get_base_url(request)
    return await provider.get_discovery_metadata(base_url)


@router.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server(
    request: Request,
    provider: OAuthProvider | None = Depends(get_provider_instance),
) -> dict[str, Any]:
    """OAuth 2.0 Authorization Server Metadata.

    Alias for OpenID Connect discovery (RFC 8414).
    No authentication required.

    Returns:
        OAuth discovery document
    """
    return await openid_configuration(request, provider)


@router.get("/userinfo")
async def userinfo(user: OptionalUser) -> dict[str, Any]:
    """OpenID Connect UserInfo endpoint.

    Returns information about the authenticated user.
    Requires valid bearer token.

    Returns:
        User claims from token
    """
    if not settings.auth.enabled:
        return {
            "error": "authentication_disabled",
            "message": "Authentication is disabled",
        }

    if not user:
        return {
            "error": "unauthorized",
            "message": "Valid bearer token required",
        }

    return {
        "sub": user.user_id,
        "email": user.email,
        "name": user.name,
        "tenant_id": user.tenant_id,
        "scopes": user.scopes,
    }
