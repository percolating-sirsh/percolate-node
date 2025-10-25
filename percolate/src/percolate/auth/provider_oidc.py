"""OIDC external provider (Microsoft Entra ID, Google, GitHub, etc.).

Validates tokens issued by external OIDC providers via JWKS.
Percolate acts as a RESOURCE SERVER, not an authorization server.

Uses authlib/joserfc for JWT validation (2025 best practice).
"""

import time
from typing import Any

import httpx
from authlib.jose import JsonWebToken, JoseError
from authlib.jose.rfc7517 import JsonWebKey
from loguru import logger

from percolate.auth.providers import OAuthProvider, User
from percolate.settings import settings


class OIDCProvider(OAuthProvider):
    """External OIDC provider.

    Validates bearer tokens issued by external OIDC providers
    (Microsoft Entra ID, Google, GitHub, Okta, Auth0, etc.).

    Percolate is a RESOURCE SERVER that validates tokens, not
    an authorization server that issues them.

    Configuration:
    - PERCOLATE_OIDC_ISSUER_URL: Provider's issuer URL
    - PERCOLATE_OIDC_AUDIENCE: Expected audience claim
    - PERCOLATE_OIDC_CLIENT_ID: OAuth client ID (for flows)
    - PERCOLATE_OIDC_CLIENT_SECRET: OAuth client secret

    Examples:
        Microsoft Entra ID:
            issuer: https://login.microsoftonline.com/{tenant}/v2.0
            audience: api://percolate-api

        Google:
            issuer: https://accounts.google.com
            audience: {client_id}.apps.googleusercontent.com

        GitHub (via OIDC):
            issuer: https://token.actions.githubusercontent.com
            audience: https://github.com/{org}
    """

    def __init__(
        self,
        issuer_url: str | None = None,
        audience: str | None = None,
        jwks_cache_ttl: int | None = None,
    ):
        """Initialize OIDC provider.

        Args:
            issuer_url: OIDC issuer URL (defaults to settings)
            audience: Expected audience claim (defaults to settings)
            jwks_cache_ttl: JWKS cache TTL in seconds (defaults to settings)
        """
        self.issuer_url = (issuer_url or settings.auth.oidc_issuer_url).rstrip("/")
        self.audience = audience or settings.auth.oidc_audience
        self.jwks_cache_ttl = jwks_cache_ttl or settings.auth.oidc_jwks_cache_ttl

        if not self.issuer_url:
            raise ValueError("OIDC issuer URL required (PERCOLATE_OIDC_ISSUER_URL)")

        self._jwks: dict[str, Any] | None = None
        self._jwks_cache_time: float = 0
        self._oidc_config: dict[str, Any] | None = None
        self._jwt = JsonWebToken(["RS256", "RS384", "RS512", "ES256"])

    async def _get_oidc_config(self) -> dict[str, Any]:
        """Fetch OIDC discovery configuration.

        Returns:
            OIDC discovery document

        Raises:
            httpx.HTTPError: Discovery endpoint unavailable
        """
        if self._oidc_config:
            return self._oidc_config

        discovery_url = f"{self.issuer_url}/.well-known/openid-configuration"
        async with httpx.AsyncClient() as client:
            response = await client.get(discovery_url)
            response.raise_for_status()
            self._oidc_config = response.json()
            logger.info(f"Fetched OIDC config from {discovery_url}")
            return self._oidc_config

    async def _get_jwks(self, force_refresh: bool = False) -> dict[str, Any]:
        """Fetch JWKS (JSON Web Key Set) from provider.

        Args:
            force_refresh: Force refresh even if cached

        Returns:
            JWKS dictionary

        Raises:
            httpx.HTTPError: JWKS endpoint unavailable
        """
        now = time.time()

        # Return cached JWKS if still valid
        if (
            not force_refresh
            and self._jwks
            and (now - self._jwks_cache_time) < self.jwks_cache_ttl
        ):
            return self._jwks

        # Fetch JWKS
        config = await self._get_oidc_config()
        jwks_uri = config["jwks_uri"]

        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_uri)
            response.raise_for_status()
            self._jwks = response.json()
            self._jwks_cache_time = now
            logger.info(f"Refreshed JWKS from {jwks_uri}")
            return self._jwks

    async def validate_token(self, token: str) -> User:
        """Validate JWT bearer token from external OIDC provider.

        Uses authlib's JsonWebToken for validation (2025 best practice).

        Args:
            token: JWT bearer token

        Returns:
            User with validated claims

        Raises:
            ValueError: Token validation failed (invalid/expired)
        """
        try:
            # Get JWKS
            jwks = await self._get_jwks()

            # Decode and validate token with authlib
            claims_options = {
                "iss": {"essential": True, "value": self.issuer_url},
                "aud": {"essential": True, "value": self.audience},
                "exp": {"essential": True},
            }

            payload = self._jwt.decode(
                token,
                key=JsonWebKey.import_key_set(jwks),
                claims_options=claims_options,
            )

            logger.debug(f"Token validated for user: {payload.get('sub')}")

            return User(
                user_id=payload.get("sub", ""),
                email=payload.get("email"),
                name=payload.get("name") or payload.get("preferred_username"),
                tenant_id=payload.get("tid"),  # Microsoft Entra tenant
                scopes=self._parse_scopes(payload),
                metadata={
                    "provider": "oidc",
                    "issuer": self.issuer_url,
                    "aud": payload.get("aud"),
                },
            )

        except JoseError as e:
            error_msg = str(e).lower()

            # Handle expired tokens
            if "expired" in error_msg:
                logger.warning("Token expired")
                raise ValueError("token_expired") from e

            # If validation fails due to unknown key ID, refresh JWKS and retry
            if "kid" in error_msg or "key" in error_msg:
                logger.info("Unknown key ID, refreshing JWKS and retrying")
                jwks = await self._get_jwks(force_refresh=True)
                try:
                    payload = self._jwt.decode(
                        token,
                        key=JsonWebKey.import_key_set(jwks),
                        claims_options=claims_options,
                    )
                    logger.debug(f"Token validated after JWKS refresh: {payload.get('sub')}")
                    return User(
                        user_id=payload.get("sub", ""),
                        email=payload.get("email"),
                        name=payload.get("name") or payload.get("preferred_username"),
                        tenant_id=payload.get("tid"),
                        scopes=self._parse_scopes(payload),
                        metadata={
                            "provider": "oidc",
                            "issuer": self.issuer_url,
                        },
                    )
                except JoseError as refresh_e:
                    if "expired" in str(refresh_e).lower():
                        logger.warning("Token expired")
                        raise ValueError("token_expired") from refresh_e
                    raise ValueError("invalid_token") from refresh_e

            logger.warning(f"Token validation failed: {e}")
            raise ValueError("invalid_token") from e

    def _parse_scopes(self, payload: dict[str, Any]) -> list[str]:
        """Parse scopes from token payload.

        Different providers encode scopes differently:
        - Microsoft: space-separated string in 'scp' or 'scope'
        - Google: array in 'scope'
        - GitHub: array in 'scope'

        Args:
            payload: JWT payload

        Returns:
            List of scopes
        """
        # Try common scope claim names
        for claim_name in ["scope", "scp", "scopes"]:
            scopes = payload.get(claim_name)
            if scopes:
                if isinstance(scopes, str):
                    return scopes.split()
                elif isinstance(scopes, list):
                    return scopes
        return []

    async def get_discovery_metadata(self, base_url: str) -> dict[str, Any]:
        """Get OIDC discovery metadata.

        Returns metadata pointing to external provider for token issuance
        and local endpoints for resource access.

        Args:
            base_url: API base URL

        Returns:
            Combined discovery document
        """
        # Fetch external provider config
        external_config = await self._get_oidc_config()

        return {
            # External provider (issues tokens)
            "issuer": self.issuer_url,
            "authorization_endpoint": external_config.get("authorization_endpoint"),
            "token_endpoint": external_config.get("token_endpoint"),
            "jwks_uri": external_config.get("jwks_uri"),
            "device_authorization_endpoint": external_config.get(
                "device_authorization_endpoint"
            ),
            # Local endpoints (resource server)
            "userinfo_endpoint": f"{base_url}/oauth/userinfo",
            # Supported features
            "response_types_supported": external_config.get("response_types_supported", ["code"]),
            "grant_types_supported": external_config.get(
                "grant_types_supported",
                ["authorization_code", "client_credentials", "refresh_token"],
            ),
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": external_config.get(
                "id_token_signing_alg_values_supported", ["RS256"]
            ),
            "scopes_supported": external_config.get(
                "scopes_supported", ["openid", "profile", "email"]
            ),
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": external_config.get(
                "token_endpoint_auth_methods_supported",
                ["client_secret_post", "client_secret_basic"],
            ),
            "claims_supported": external_config.get(
                "claims_supported", ["sub", "email", "name", "scope"]
            ),
        }

    def get_provider_name(self) -> str:
        """Get provider name.

        Returns:
            Provider identifier
        """
        return "oidc"
