"""JWT manager for dev and p8fs providers.

JWT operations using ES256 (ECDSA with P-256 curve) for keypair encryption.
Suitable for development and P8fs provider where we control token issuance.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as pyjwt


class JWTManager:
    """JWT manager with ES256 keypair signing.

    Uses asymmetric cryptography (ECDSA P-256) for signing/verification.
    Private key signs tokens, public key verifies them.

    For external OIDC providers, use provider_oidc.py instead.
    """

    def __init__(self, private_key: str, public_key: str, algorithm: str = "ES256"):
        """Initialize JWT manager.

        Args:
            private_key: Private key in PEM format for signing
            public_key: Public key in PEM format for verification
            algorithm: JWT algorithm (ES256, ES384, ES512)
        """
        self.private_key = private_key
        self.public_key = public_key
        self.algorithm = algorithm

    def encode_token(self, payload: dict[str, Any]) -> str:
        """Encode JWT token with private key.

        Args:
            payload: Token payload (claims)

        Returns:
            Encoded JWT string

        Example:
            >>> manager = JWTManager(private_key, public_key)
            >>> token = manager.encode_token({"sub": "user-123"})
            >>> token.startswith("eyJ")
            True
        """
        return pyjwt.encode(payload, self.private_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> dict[str, Any]:
        """Decode and verify JWT token with public key.

        Args:
            token: JWT token string

        Returns:
            Decoded payload

        Raises:
            jwt.ExpiredSignatureError: Token expired
            jwt.InvalidTokenError: Token invalid

        Example:
            >>> manager = JWTManager(private_key, public_key)
            >>> payload = manager.decode_token(token)
            >>> payload["sub"]
            'user-123'
        """
        return pyjwt.decode(
            token,
            self.public_key,
            algorithms=[self.algorithm],
            options={"verify_exp": True},
        )

    def create_token(
        self,
        subject: str,
        expires_minutes: int = 60,
        **extra_claims,
    ) -> str:
        """Create JWT token with standard claims.

        Args:
            subject: Subject claim (sub)
            expires_minutes: Token lifetime in minutes
            **extra_claims: Additional claims to include

        Returns:
            Encoded JWT token

        Example:
            >>> manager = JWTManager(private_key, public_key)
            >>> token = manager.create_token(
            ...     subject="user-123",
            ...     expires_minutes=60,
            ...     tenant="tenant-456",
            ...     scope=["read", "write"]
            ... )
        """
        now = datetime.now(timezone.utc)
        payload = {
            "sub": subject,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
            **extra_claims,
        }
        return self.encode_token(payload)
