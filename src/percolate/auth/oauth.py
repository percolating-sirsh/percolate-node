"""OAuth 2.1 endpoint handlers."""

from typing import Any
from fastapi import Request

from percolate.auth.device import (
    create_device_authorization,
    approve_device_authorization,
    poll_device_token,
)


async def device_authorization_endpoint(
    client_id: str,
    scope: str | None = None,
) -> dict[str, Any]:
    """OAuth 2.0 Device Authorization Grant endpoint (RFC 8628).

    Initiates device flow by generating device code and user code.

    Args:
        client_id: OAuth client identifier
        scope: Space-separated scope list

    Returns:
        Device authorization response with codes and URIs

    Example:
        >>> response = await device_authorization_endpoint("mobile-app")
        >>> response["user_code"]
        'A1B2-C3D4'
    """
    scope_list = scope.split() if scope else ["read", "write"]
    token = await create_device_authorization(client_id, scope_list)

    return {
        "device_code": token.device_code,
        "user_code": token.user_code,
        "verification_uri": token.verification_uri,
        "verification_uri_complete": token.verification_uri_complete,
        "expires_in": token.expires_in,
        "interval": token.interval,
    }


async def token_endpoint(
    grant_type: str,
    client_id: str,
    device_code: str | None = None,
    refresh_token: str | None = None,
) -> dict[str, Any]:
    """OAuth 2.1 token endpoint.

    Handles token issuance for device flow and refresh token grant.

    Args:
        grant_type: Grant type (device_code or refresh_token)
        client_id: OAuth client identifier
        device_code: Device code (for device flow)
        refresh_token: Refresh token (for refresh grant)

    Returns:
        Token response with access and refresh tokens

    Raises:
        ValueError: If grant type invalid or parameters missing

    Example:
        >>> tokens = await token_endpoint(
        ...     grant_type="urn:ietf:params:oauth:grant-type:device_code",
        ...     client_id="mobile-app",
        ...     device_code="abc123"
        ... )
        >>> tokens["access_token"]
        'eyJ...'
    """
    if grant_type == "urn:ietf:params:oauth:grant-type:device_code":
        if not device_code:
            raise ValueError("device_code required for device flow")

        tokens = await poll_device_token(device_code)
        if not tokens:
            # Still pending
            return {
                "error": "authorization_pending",
                "error_description": "User has not yet approved the device",
            }

        return tokens

    elif grant_type == "refresh_token":
        if not refresh_token:
            raise ValueError("refresh_token required for refresh grant")

        # TODO: Implement refresh token grant
        raise NotImplementedError("Refresh token grant not yet implemented")

    else:
        raise ValueError(f"Unsupported grant type: {grant_type}")


async def get_oauth_discovery(request: Request) -> dict[str, Any]:
    """OAuth 2.1 authorization server metadata.

    Returns discovery document for well-known endpoint.
    Provides metadata about supported endpoints and capabilities.

    Args:
        request: FastAPI request (for base URL extraction)

    Returns:
        OAuth discovery document

    Example:
        >>> discovery = await get_oauth_discovery(request)
        >>> discovery["issuer"]
        'https://auth.percolate.app'
    """
    # Extract base URL from request or use configured value
    # TODO: Get base URL from settings
    base_url = "https://auth.percolate.app"

    return {
        "issuer": base_url,
        "device_authorization_endpoint": f"{base_url}/oauth/device_authorization",
        "token_endpoint": f"{base_url}/oauth/token",
        "jwks_uri": f"{base_url}/.well-known/jwks.json",
        "response_types_supported": ["code"],
        "grant_types_supported": [
            "urn:ietf:params:oauth:grant-type:device_code",
            "refresh_token",
        ],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["ES256"],
        "scopes_supported": ["read", "write", "admin"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
        "claims_supported": ["sub", "tenant", "device", "scope"],
    }


async def get_jwks() -> dict[str, Any]:
    """JSON Web Key Set endpoint.

    Returns public keys for JWT verification.

    Returns:
        JWKS document with public keys

    Example:
        >>> jwks = await get_jwks()
        >>> len(jwks["keys"]) >= 1
        True
    """
    # TODO: Implement JWKS from JWT manager
    raise NotImplementedError("JWKS endpoint not yet implemented")
