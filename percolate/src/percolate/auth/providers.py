"""OAuth provider interface and implementations.

This module provides a pluggable authentication provider system supporting:
- P8FS mobile device flow (custom, Ed25519-based)
- OIDC external providers (Microsoft Entra ID, Google, GitHub)
"""

from abc import ABC, abstractmethod
from typing import Any, Protocol

from pydantic import BaseModel, Field


class User(BaseModel):
    """Authenticated user from token validation.

    Represents a validated user across all provider types.
    Providers map their token claims to this common model.
    """

    user_id: str = Field(description="User ID (sub claim)")
    email: str | None = Field(default=None, description="User email")
    name: str | None = Field(default=None, description="User display name")
    tenant_id: str | None = Field(default=None, description="Tenant identifier")
    scopes: list[str] = Field(default_factory=list, description="Granted scopes")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific metadata",
    )


class OAuthProvider(ABC):
    """Abstract OAuth provider interface.

    All authentication providers must implement this interface.
    Supports both token-based (OIDC) and device-based (P8FS) flows.
    """

    @abstractmethod
    async def validate_token(self, token: str) -> User:
        """Validate bearer token and return user.

        Args:
            token: Bearer token string (JWT or opaque)

        Returns:
            User with validated claims

        Raises:
            ValueError: Token invalid or expired
        """
        pass

    @abstractmethod
    async def get_discovery_metadata(self, base_url: str) -> dict[str, Any]:
        """Get OAuth/OIDC discovery metadata.

        Args:
            base_url: API base URL for endpoint construction

        Returns:
            Discovery document with endpoints and capabilities
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider identifier.

        Returns:
            Provider name (e.g., 'p8fs', 'oidc', 'microsoft')
        """
        pass
