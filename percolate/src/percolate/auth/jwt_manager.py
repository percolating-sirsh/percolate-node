"""JWT signing and verification with ES256."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
import jwt

from percolate.auth.models import TokenPayload


class JWTKeyManager:
    """ES256 JWT key management with rotation support.

    Manages ECDSA P-256 keypairs for JWT signing and verification.
    Supports zero-downtime key rotation by maintaining multiple
    active keys with unique key IDs.

    Attributes:
        issuer: JWT issuer claim (iss)
        audience: JWT audience claim (aud)
        access_token_ttl: Access token lifetime in seconds
        refresh_token_ttl: Refresh token lifetime in seconds
    """

    def __init__(
        self,
        issuer: str = "https://auth.percolate.app",
        audience: str = "https://api.percolate.app",
        access_token_ttl: int = 3600,
        refresh_token_ttl: int = 2592000,
    ):
        """Initialize JWT key manager.

        Args:
            issuer: JWT issuer claim
            audience: JWT audience claim
            access_token_ttl: Access token TTL (seconds)
            refresh_token_ttl: Refresh token TTL (seconds)
        """
        self.issuer = issuer
        self.audience = audience
        self.access_token_ttl = access_token_ttl
        self.refresh_token_ttl = refresh_token_ttl
        self._keys: dict = {}
        self._current_key_id: str | None = None

    def _generate_keypair(self) -> tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
        """Generate ES256 (P-256) keypair.

        Returns:
            Tuple of (private_key, public_key)
        """
        private_key = ec.generate_private_key(
            ec.SECP256R1(),  # P-256 curve for ES256
            default_backend(),
        )
        public_key = private_key.public_key()
        return private_key, public_key

    def _ensure_current_key(self) -> None:
        """Ensure at least one signing key exists.

        Generates initial keypair if none exists.
        """
        if not self._current_key_id:
            self._rotate_key()

    def _rotate_key(self) -> None:
        """Rotate to new signing key.

        Generates new keypair and sets as current key.
        Old keys remain for verification during rotation period.
        """
        # Generate new key
        key_id = str(uuid4())
        private_key, public_key = self._generate_keypair()

        self._keys[key_id] = {
            "private_key": private_key,
            "public_key": public_key,
            "created_at": datetime.now(timezone.utc),
        }
        self._current_key_id = key_id

    async def create_access_token(
        self,
        tenant_id: str,
        device_id: str | None = None,
        scope: list[str] | None = None,
    ) -> str:
        """Create JWT access token with ES256 signing.

        Args:
            tenant_id: Tenant identifier (becomes sub claim)
            device_id: Optional device identifier
            scope: Optional list of granted scopes

        Returns:
            Signed JWT access token

        Example:
            >>> manager = JWTKeyManager()
            >>> token = await manager.create_access_token(
            ...     tenant_id="tenant-123",
            ...     scope=["read", "write"]
            ... )
            >>> token.startswith("eyJ")
            True
        """
        self._ensure_current_key()
        current_key = self._keys[self._current_key_id]
        private_key = current_key["private_key"]

        now = datetime.now(timezone.utc)
        claims = {
            # Standard JWT claims
            "iss": self.issuer,
            "aud": self.audience,
            "exp": now + timedelta(seconds=self.access_token_ttl),
            "iat": now,
            "jti": str(uuid4()),
            # Percolate claims
            "sub": tenant_id,
            "tenant": tenant_id,
            "device": device_id,
            "scope": scope or ["read", "write"],
        }

        # Sign with ES256
        token = jwt.encode(
            claims,
            private_key,
            algorithm="ES256",
            headers={"kid": self._current_key_id},
        )
        return token

    async def verify_token(self, token: str) -> TokenPayload:
        """Verify JWT token and extract payload.

        Validates signature, expiration, and claims.
        Tries all available public keys for verification.

        Args:
            token: JWT token string

        Returns:
            Validated token payload

        Raises:
            jwt.ExpiredSignatureError: If token expired
            jwt.InvalidTokenError: If token invalid

        Example:
            >>> payload = await manager.verify_token(token)
            >>> payload.tenant
            'tenant-123'
        """
        # Extract key ID from header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        # Try to verify with specified key first
        if kid and kid in self._keys:
            public_key = self._keys[kid]["public_key"]
            try:
                claims = jwt.decode(
                    token,
                    public_key,
                    algorithms=["ES256"],
                    audience=self.audience,
                    issuer=self.issuer,
                )
                return TokenPayload(**claims)
            except jwt.InvalidTokenError:
                pass

        # Try all available keys (for rotation period)
        for key_data in self._keys.values():
            try:
                claims = jwt.decode(
                    token,
                    key_data["public_key"],
                    algorithms=["ES256"],
                    audience=self.audience,
                    issuer=self.issuer,
                )
                return TokenPayload(**claims)
            except jwt.InvalidTokenError:
                continue

        raise jwt.InvalidTokenError("Token verification failed with all keys")

    def get_jwks(self) -> dict:
        """Get JSON Web Key Set for public key discovery.

        Returns:
            JWKS document with all active public keys

        Example:
            >>> jwks = manager.get_jwks()
            >>> len(jwks["keys"]) >= 1
            True
        """
        # TODO: Implement JWKS export
        raise NotImplementedError("JWKS export not yet implemented")
