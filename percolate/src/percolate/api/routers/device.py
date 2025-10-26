"""Device registration endpoints for P8FS provider.

Handles device registration with both server-generated and client-generated keys.
"""

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger

from percolate.auth.device_keys import DeviceKeyStore
from percolate.settings import settings


router = APIRouter(prefix="/device", tags=["Device Registration"])


class DeviceRegistrationRequest(BaseModel):
    """Device registration request."""

    tenant_id: str = Field(description="Tenant identifier")
    device_id: str | None = Field(default=None, description="Device ID (generated if not provided)")
    public_key: str | None = Field(
        default=None, description="Client-generated public key (PEM format)"
    )
    device_name: str | None = Field(default=None, description="Human-readable device name")
    device_type: str | None = Field(default=None, description="Device type (mobile, desktop, etc.)")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata")


class DeviceRegistrationResponse(BaseModel):
    """Device registration response."""

    device_id: str = Field(description="Device identifier")
    tenant_id: str = Field(description="Tenant identifier")
    public_key: str = Field(description="Public key (PEM format)")
    private_key: str | None = Field(
        default=None, description="Private key (PEM format) - only if server-generated"
    )
    jwt_signing_key: str = Field(description="JWT signing key for this device")
    trust_level: str = Field(description="Trust level")
    mode: str = Field(description="server_generated | client_generated")
    message: str = Field(description="Instructions for device")


class TrustLevelUpdate(BaseModel):
    """Trust level update request."""

    trust_level: str = Field(description="New trust level (unverified | email_verified | trusted)")


@router.post("/register", response_model=DeviceRegistrationResponse)
async def register_device(request: DeviceRegistrationRequest) -> DeviceRegistrationResponse:
    """Register a new device.

    Two modes:
    1. **Server-generated keys** (default): Server generates keypair, returns both keys to device
    2. **Client-generated keys**: Device generates keypair, sends public key only

    The mode is determined by AUTH__P8FS_SERVER_STORED_KEYS setting and presence of public_key.

    Args:
        request: Device registration details

    Returns:
        Device registration response with keys

    Example (server-generated):
        ```
        POST /device/register
        {
            "tenant_id": "tenant-123",
            "device_name": "Alice's iPhone"
        }
        ```

    Example (client-generated):
        ```
        POST /device/register
        {
            "tenant_id": "tenant-123",
            "device_id": "device-456",
            "public_key": "-----BEGIN PUBLIC KEY-----...",
            "device_name": "Bob's Android"
        }
        ```
    """
    store = DeviceKeyStore()

    # Generate device_id if not provided
    device_id = request.device_id or str(uuid4())

    # Prepare metadata
    metadata = request.metadata or {}
    if request.device_name:
        metadata["device_name"] = request.device_name
    if request.device_type:
        metadata["device_type"] = request.device_type

    # Determine mode
    server_generated = settings.auth.device_server_stored_keys and not request.public_key

    if server_generated:
        # Server-generated mode
        logger.info(
            f"Registering device (server-generated): tenant={request.tenant_id}, device={device_id}"
        )
        device = store.register_device_server_generated(
            tenant_id=request.tenant_id,
            device_id=device_id,
            metadata=metadata,
        )

        return DeviceRegistrationResponse(
            device_id=device.device_id,
            tenant_id=device.tenant_id,
            public_key=device.public_key,
            private_key=device.private_key,  # Return to device for secure storage
            jwt_signing_key=device.private_key or "",  # Device uses this to sign requests
            trust_level=device.trust_level,
            mode="server_generated",
            message="IMPORTANT: Store private_key securely on device. Server will not return it again.",
        )
    else:
        # Client-generated mode
        if not request.public_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="public_key required when AUTH__P8FS_SERVER_STORED_KEYS=false",
            )

        logger.info(
            f"Registering device (client-generated): tenant={request.tenant_id}, device={device_id}"
        )
        device = store.register_device_client_generated(
            tenant_id=request.tenant_id,
            device_id=device_id,
            public_key=request.public_key,
            metadata=metadata,
        )

        return DeviceRegistrationResponse(
            device_id=device.device_id,
            tenant_id=device.tenant_id,
            public_key=device.public_key,
            private_key=None,  # Client keeps private key
            jwt_signing_key="",  # Client already has it
            trust_level=device.trust_level,
            mode="client_generated",
            message="Device registered successfully. Use your private key to sign requests.",
        )


@router.get("/list/{tenant_id}")
async def list_devices(tenant_id: str) -> list[dict[str, Any]]:
    """List all devices for a tenant.

    Args:
        tenant_id: Tenant identifier

    Returns:
        List of devices
    """
    store = DeviceKeyStore()
    devices = store.list_tenant_devices(tenant_id)

    return [
        {
            "device_id": d.device_id,
            "tenant_id": d.tenant_id,
            "public_key": d.public_key[:50] + "...",  # Truncate for display
            "trust_level": d.trust_level,
            "created_at": d.created_at,
            "metadata": d.metadata,
        }
        for d in devices
    ]


@router.get("/{tenant_id}/{device_id}")
async def get_device(tenant_id: str, device_id: str) -> dict[str, Any]:
    """Get device information.

    Args:
        tenant_id: Tenant identifier
        device_id: Device identifier

    Returns:
        Device information (without private key)
    """
    store = DeviceKeyStore()
    device = store.get_device_key(tenant_id, device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device not found: {device_id}",
        )

    return {
        "device_id": device.device_id,
        "tenant_id": device.tenant_id,
        "public_key": device.public_key,
        "trust_level": device.trust_level,
        "created_at": device.created_at,
        "metadata": device.metadata,
    }


@router.put("/{tenant_id}/{device_id}/trust")
async def update_trust_level(
    tenant_id: str, device_id: str, update: TrustLevelUpdate
) -> dict[str, str]:
    """Update device trust level.

    Args:
        tenant_id: Tenant identifier
        device_id: Device identifier
        update: Trust level update

    Returns:
        Success message
    """
    store = DeviceKeyStore()
    success = store.update_trust_level(tenant_id, device_id, update.trust_level)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device not found: {device_id}",
        )

    return {
        "message": f"Trust level updated to {update.trust_level}",
        "device_id": device_id,
        "tenant_id": tenant_id,
    }


@router.delete("/{tenant_id}/{device_id}")
async def delete_device(tenant_id: str, device_id: str) -> dict[str, str]:
    """Delete device registration.

    Args:
        tenant_id: Tenant identifier
        device_id: Device identifier

    Returns:
        Success message
    """
    store = DeviceKeyStore()
    success = store.delete_device(tenant_id, device_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device not found: {device_id}",
        )

    return {
        "message": "Device deleted successfully",
        "device_id": device_id,
        "tenant_id": tenant_id,
    }
