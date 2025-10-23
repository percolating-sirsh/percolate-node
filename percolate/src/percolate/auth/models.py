"""Authentication data models."""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field


class DeviceTrustLevel(str, Enum):
    """Device trust progression levels."""

    UNVERIFIED = "unverified"
    EMAIL_VERIFIED = "email_verified"
    TRUSTED = "trusted"
    REVOKED = "revoked"


class TokenType(str, Enum):
    """OAuth token types."""

    ACCESS = "access"
    REFRESH = "refresh"


class Device(BaseModel):
    """Mobile device registration.

    Represents a registered device with Ed25519 public key for
    cryptographic authentication and progressive trust levels.

    Attributes:
        device_id: Unique device identifier
        public_key: Ed25519 public key (base64-encoded)
        tenant_id: Tenant this device belongs to
        device_name: Optional human-readable name
        trust_level: Current trust level (UNVERIFIED → TRUSTED)
        created_at: Registration timestamp
        last_used_at: Most recent authentication timestamp
    """

    device_id: str = Field(description="Unique device identifier")
    public_key: str = Field(description="Ed25519 public key (base64)")
    tenant_id: str = Field(description="Tenant identifier")
    device_name: str | None = Field(default=None, description="Device name")
    trust_level: DeviceTrustLevel = Field(
        default=DeviceTrustLevel.UNVERIFIED,
        description="Device trust level"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Registration timestamp"
    )
    last_used_at: datetime | None = Field(
        default=None,
        description="Last authentication timestamp"
    )


class AuthToken(BaseModel):
    """OAuth access or refresh token.

    Represents issued tokens with expiration and revocation support.
    Access tokens are JWTs, refresh tokens are opaque random values.

    Attributes:
        token_id: Unique token identifier
        token_type: ACCESS or REFRESH
        token_value: Token string (JWT or opaque)
        tenant_id: Tenant identifier for scoping
        device_id: Device that requested token
        scope: List of granted scopes
        expires_at: Token expiration timestamp
        created_at: Token issuance timestamp
        revoked_at: Optional revocation timestamp
    """

    token_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique token identifier"
    )
    token_type: TokenType = Field(description="Token type (ACCESS or REFRESH)")
    token_value: str = Field(description="Token string")
    tenant_id: str = Field(description="Tenant identifier")
    device_id: str | None = Field(default=None, description="Device identifier")
    scope: list[str] = Field(default_factory=list, description="Granted scopes")
    expires_at: datetime = Field(description="Expiration timestamp")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp"
    )
    revoked_at: datetime | None = Field(
        default=None,
        description="Revocation timestamp"
    )


class DeviceToken(BaseModel):
    """Device authorization flow tokens (RFC 8628).

    Represents the device code and user code pair for device flow.
    User code is human-friendly (XXXX-YYYY format) for manual entry.

    Attributes:
        device_code: Long random device code for polling
        user_code: Short human-readable code (XXXX-YYYY)
        verification_uri: Base verification URL
        verification_uri_complete: URL with embedded user code
        expires_in: Seconds until expiration
        interval: Polling interval in seconds
        tenant_id: Optional tenant if already associated
        approved_at: Optional approval timestamp
    """

    device_code: str = Field(description="Device code for polling")
    user_code: str = Field(description="Human-readable user code")
    verification_uri: str = Field(description="Verification URL")
    verification_uri_complete: str | None = Field(
        default=None,
        description="Complete URL with user code"
    )
    expires_in: int = Field(default=600, description="Expiration seconds")
    interval: int = Field(default=5, description="Polling interval")
    tenant_id: str | None = Field(default=None, description="Tenant ID")
    approved_at: datetime | None = Field(
        default=None,
        description="Approval timestamp"
    )


class TokenPayload(BaseModel):
    """Decoded JWT token payload.

    Represents validated JWT claims after verification.
    Used by middleware for request authorization.

    Attributes:
        sub: Subject (tenant_id)
        tenant: Tenant identifier
        device: Optional device identifier
        scope: List of granted scopes
        exp: Expiration timestamp (Unix epoch)
        iat: Issued-at timestamp (Unix epoch)
    """

    sub: str = Field(description="Subject (tenant ID)")
    tenant: str = Field(description="Tenant identifier")
    device: str | None = Field(default=None, description="Device identifier")
    scope: list[str] = Field(default_factory=list, description="Granted scopes")
    exp: int = Field(description="Expiration timestamp")
    iat: int = Field(description="Issued-at timestamp")
