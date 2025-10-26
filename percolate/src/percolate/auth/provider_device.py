"""Percolate mobile device authorization provider.

Implements custom mobile-first authentication with:
- Device authorization flow (RFC 8628)
- Ed25519 public key cryptography
- Progressive trust levels
- QR code + manual approval flow
"""

from typing import Any

from percolate.auth.providers import OAuthProvider, User
from percolate.auth.jwt_simple import JWTManager
from percolate.settings import settings


class DeviceProvider(OAuthProvider):
    """Percolate device authorization provider.

    Custom OAuth provider using device flow with Ed25519 signatures.
    Designed for mobile-first authentication where devices register
    their public keys and gain progressive trust.

    Flow:
    1. Device generates Ed25519 keypair (private key never leaves device)
    2. Device registers public key → gets device_id
    3. Device initiates flow → gets user_code (XXXX-YYYY)
    4. User approves via trusted device (QR scan or manual code entry)
    5. Device polls token endpoint → receives JWT access token
    """

    def __init__(self):
        """Initialize device provider with JWT manager."""
        self.jwt_manager = JWTManager(
            private_key=settings.auth.jwt_private_key,
            public_key=settings.auth.jwt_public_key,
            algorithm=settings.auth.jwt_algorithm,
        )

    async def validate_token(self, token: str) -> User:
        """Validate JWT access token issued by device provider.

        Args:
            token: JWT access token

        Returns:
            User with tenant and device claims

        Raises:
            ValueError: Token invalid or expired
        """
        try:
            payload = self.jwt_manager.decode_token(token)

            return User(
                user_id=payload.get("sub", ""),
                tenant_id=payload.get("tenant"),
                email=payload.get("email"),
                name=payload.get("name"),
                scopes=payload.get("scope", []),
                metadata={
                    "device_id": payload.get("device"),
                    "provider": "device",
                },
            )
        except Exception as e:
            raise ValueError(f"Token validation failed: {e}") from e

    async def get_discovery_metadata(self, base_url: str) -> dict[str, Any]:
        """Get Percolate device OAuth discovery document.

        Args:
            base_url: API base URL

        Returns:
            OAuth 2.1 discovery document with device flow endpoints
        """
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
            "id_token_signing_alg_values_supported": [settings.auth.jwt_algorithm],
            "scopes_supported": ["read", "write", "admin"],
            "token_endpoint_auth_methods_supported": ["none"],
            "claims_supported": ["sub", "tenant", "device", "scope", "email", "name"],
            "code_challenge_methods_supported": ["S256"],
        }

    def get_provider_name(self) -> str:
        """Get provider name.

        Returns:
            Provider identifier
        """
        return "device"
