"""Device authorization flow (RFC 8628)."""

import base64
import secrets
from datetime import datetime, timedelta

from percolate.auth.models import DeviceToken, Device, DeviceTrustLevel


async def create_device_authorization(
    client_id: str,
    scope: list[str] | None = None,
) -> DeviceToken:
    """Initiate device authorization flow.

    Generates device code and user code pair for device flow.
    Device code is long random string for security, user code is
    short and human-friendly (XXXX-YYYY format).

    Args:
        client_id: OAuth client identifier
        scope: Optional list of requested scopes

    Returns:
        DeviceToken with codes and verification URIs

    Example:
        >>> token = await create_device_authorization("mobile-app")
        >>> token.user_code
        'A1B2-C3D4'
        >>> token.verification_uri
        'https://auth.percolate.app/device'
    """
    # Generate device code (long random for security)
    device_code = base64.urlsafe_b64encode(
        secrets.token_bytes(32)
    ).decode("utf-8").rstrip("=")

    # Generate user code (short, human-friendly)
    user_code = f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"

    # Build verification URIs
    # TODO: Get base URL from settings
    base_uri = "https://auth.percolate.app"
    verification_uri = f"{base_uri}/device"
    verification_uri_complete = f"{base_uri}/device?user_code={user_code}"

    # Store pending authorization with TTL (10 minutes)
    # TODO: Implement KV storage with TTL
    pending_data = {
        "device_code": device_code,
        "user_code": user_code,
        "client_id": client_id,
        "scope": scope or ["read", "write"],
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
    }

    return DeviceToken(
        device_code=device_code,
        user_code=user_code,
        verification_uri=verification_uri,
        verification_uri_complete=verification_uri_complete,
        expires_in=600,
        interval=5,
    )


async def approve_device_authorization(
    user_code: str,
    tenant_id: str,
    approving_device_id: str,
) -> dict[str, str]:
    """Approve device authorization from trusted device.

    Validates that the approving device is trusted and associates
    the pending authorization with the tenant.

    Args:
        user_code: Human-readable user code (XXXX-YYYY)
        tenant_id: Tenant identifier
        approving_device_id: Device performing approval

    Returns:
        Approval status

    Raises:
        ValueError: If approving device is not trusted

    Example:
        >>> await approve_device_authorization(
        ...     user_code="A1B2-C3D4",
        ...     tenant_id="tenant-123",
        ...     approving_device_id="device-456"
        ... )
        {'status': 'approved'}
    """
    # Normalize user code
    user_code = user_code.upper().replace("-", "")

    # Verify approving device is trusted
    # TODO: Implement device lookup and trust verification
    approving_device = await _get_device(approving_device_id)
    if approving_device.trust_level not in [
        DeviceTrustLevel.EMAIL_VERIFIED,
        DeviceTrustLevel.TRUSTED,
    ]:
        raise ValueError("Approving device not verified")

    # Update pending authorization with tenant
    # TODO: Implement pending authorization update
    await _update_pending_authorization(user_code, tenant_id)

    return {"status": "approved"}


async def poll_device_token(device_code: str) -> dict[str, str] | None:
    """Poll for device authorization completion.

    Called by client to check if user has approved the device.
    Returns tokens if approved, None if still pending.

    Args:
        device_code: Device code from authorization request

    Returns:
        Access and refresh tokens if approved, None if pending

    Raises:
        ValueError: If device code expired or invalid

    Example:
        >>> tokens = await poll_device_token(device_code)
        >>> if tokens:
        ...     tokens["access_token"]
        'eyJ...'
    """
    # Lookup pending authorization
    # TODO: Implement pending authorization lookup
    pending = await _get_pending_authorization(device_code)

    if not pending:
        raise ValueError("Invalid or expired device code")

    # Check if approved
    if not pending.get("tenant_id"):
        return None  # Still pending

    # Issue tokens
    # TODO: Implement token issuance
    return {
        "access_token": "eyJ...",
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": "...",
    }


async def _get_device(device_id: str) -> Device:
    """Retrieve device by ID."""
    # TODO: Implement device storage lookup
    raise NotImplementedError("Device lookup not yet implemented")


async def _update_pending_authorization(user_code: str, tenant_id: str) -> None:
    """Update pending authorization with tenant."""
    # TODO: Implement KV storage update
    raise NotImplementedError("Pending authorization update not yet implemented")


async def _get_pending_authorization(device_code: str) -> dict | None:
    """Retrieve pending authorization by device code."""
    # TODO: Implement KV storage lookup
    raise NotImplementedError("Pending authorization lookup not yet implemented")
