"""Dev/dummy authentication provider for testing.

Provides simple click-to-confirm authentication for testing MCP login flows.
NOT FOR PRODUCTION - no real security, just for development/testing.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

from percolate.auth.providers import OAuthProvider, User
from percolate.auth.jwt_simple import JWTManager
from percolate.settings import settings


# In-memory store for pending authorizations (reset on restart)
_pending_auths: dict[str, dict[str, Any]] = {}


class DevProvider(OAuthProvider):
    """Dev/dummy provider for testing MCP login flows.

    Provides minimal OAuth-like flow for testing without real authentication:
    1. Client initiates auth → gets authorization URL
    2. User clicks "Confirm" button → auto-approves
    3. Client polls/redirects → receives token

    WARNING: NOT FOR PRODUCTION USE
    - No password/credential verification
    - Tokens are self-signed (not externally validated)
    - No rate limiting or security hardening
    - In-memory state (lost on restart)

    Use for:
    - Local development
    - MCP client testing
    - Integration testing
    - CI/CD pipelines
    """

    def __init__(self):
        """Initialize dev provider with JWT manager."""
        self.jwt_manager = JWTManager(
            private_key=settings.auth.jwt_private_key,
            public_key=settings.auth.jwt_public_key,
            algorithm=settings.auth.jwt_algorithm,
        )
        logger.warning("Dev provider initialized - NOT FOR PRODUCTION USE")

    async def validate_token(self, token: str) -> User:
        """Validate JWT access token.

        Args:
            token: JWT access token

        Returns:
            User with claims

        Raises:
            ValueError: Token invalid or expired
        """
        try:
            payload = self.jwt_manager.decode_token(token)

            return User(
                user_id=payload.get("sub", "dev-user"),
                tenant_id=payload.get("tenant", "dev-tenant"),
                email=payload.get("email", "dev@example.com"),
                name=payload.get("name", "Dev User"),
                scopes=payload.get("scope", ["read", "write"]),
                metadata={
                    "provider": "dev",
                    "warning": "dev provider - not for production",
                },
            )
        except Exception as e:
            raise ValueError(f"Token validation failed: {e}") from e

    async def get_discovery_metadata(self, base_url: str) -> dict[str, Any]:
        """Get OAuth discovery document for dev provider.

        Args:
            base_url: API base URL

        Returns:
            OAuth discovery document
        """
        return {
            "issuer": base_url,
            "authorization_endpoint": f"{base_url}/oauth/dev/authorize",
            "token_endpoint": f"{base_url}/oauth/dev/token",
            "confirmation_endpoint": f"{base_url}/oauth/dev/confirm",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": [settings.auth.jwt_algorithm],
            "scopes_supported": ["read", "write", "admin"],
            "token_endpoint_auth_methods_supported": ["none"],
            "claims_supported": ["sub", "tenant", "email", "name", "scope"],
            "code_challenge_methods_supported": ["S256"],
            "_warning": "Dev provider - not for production use",
        }

    def get_provider_name(self) -> str:
        """Get provider name.

        Returns:
            Provider identifier
        """
        return "dev"

    def create_authorization(
        self,
        redirect_uri: str,
        state: str | None = None,
        scope: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create authorization request.

        Args:
            redirect_uri: OAuth redirect URI
            state: OAuth state parameter
            scope: Requested scopes

        Returns:
            Authorization details with code and URL
        """
        code = secrets.token_urlsafe(32)
        auth_data = {
            "code": code,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": scope or ["read", "write"],
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=10)
            ).isoformat(),
        }
        _pending_auths[code] = auth_data

        logger.info(f"Created dev authorization: code={code[:8]}...")
        return auth_data

    def approve_authorization(self, code: str) -> bool:
        """Approve authorization (user clicked confirm).

        Args:
            code: Authorization code

        Returns:
            True if approved, False if not found/expired
        """
        auth = _pending_auths.get(code)
        if not auth:
            return False

        # Check expiration
        expires_at = datetime.fromisoformat(auth["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            _pending_auths.pop(code, None)
            return False

        auth["status"] = "approved"
        auth["approved_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"Approved dev authorization: code={code[:8]}...")
        return True

    def exchange_code_for_token(self, code: str) -> dict[str, Any] | None:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code

        Returns:
            Token response or None if not approved/expired
        """
        auth = _pending_auths.get(code)
        if not auth or auth["status"] != "approved":
            return None

        # Create JWT access token
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.auth.access_token_expire_minutes
        )
        payload = {
            "sub": "dev-user",
            "tenant": "dev-tenant",
            "email": "dev@example.com",
            "name": "Dev User",
            "scope": auth["scope"],
            "exp": int(expires_at.timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
        }
        access_token = self.jwt_manager.encode_token(payload)

        # Clean up used code
        _pending_auths.pop(code, None)

        logger.info("Issued dev access token")
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": settings.auth.access_token_expire_minutes * 60,
            "scope": " ".join(auth["scope"]),
        }
