"""Device key storage for P8FS provider.

Manages per-tenant, per-device keypairs for mobile device authentication.

Storage is delegated to TenantStore provider (filesystem or REM database).

Deployment Notes:
- **Kubernetes**: Deploy as StatefulSet with PersistentVolume for tenant data
- **Volume mount**: /data/tenants (filesystem or REM database path)
- **Backup strategy**: Volume backups or REM snapshots
- **Replication**: Read replicas for gateway nodes (read-only instances)
"""

from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from loguru import logger

from percolate.auth.tenant_store import TenantStore
from percolate.auth.tenant_store_factory import get_tenant_store


@dataclass
class DeviceKey:
    """Device key information."""

    device_id: str
    tenant_id: str
    public_key: str  # PEM format
    private_key: str | None = None  # Only set for server-generated keys
    trust_level: str = "unverified"  # unverified | email_verified | trusted
    created_at: str = ""
    metadata: dict[str, Any] | None = None


class DeviceKeyStore:
    """Storage for device keys with tenant isolation.

    Uses TenantStore provider for persistence:
        - Namespace: "device_keys"
        - Key: device_id
        - Value: DeviceKey as dict

    Storage backend is configurable (filesystem, REM database).
    """

    NAMESPACE = "device_keys"

    def __init__(self, store: TenantStore | None = None):
        """Initialize device key store.

        Args:
            store: TenantStore instance (uses factory default if None)
        """
        self.store = store or get_tenant_store()
        logger.info(f"Device key store initialized with {type(self.store).__name__}")

    def register_device_server_generated(
        self,
        tenant_id: str,
        device_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> DeviceKey:
        """Register device with server-generated keypair.

        Server generates ES256 keypair and stores both private and public keys.
        Returns full keypair to device for secure storage.

        Args:
            tenant_id: Tenant identifier
            device_id: Device identifier (UUID)
            metadata: Optional device metadata

        Returns:
            DeviceKey with both private and public keys

        Example:
            >>> store = DeviceKeyStore()
            >>> device = store.register_device_server_generated(
            ...     tenant_id="tenant-123",
            ...     device_id="device-456",
            ...     metadata={"device_name": "Alice's iPhone"}
            ... )
            >>> device.private_key  # Device stores this securely
            '-----BEGIN PRIVATE KEY-----...'
        """
        # Generate ES256 keypair
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()

        # Serialize to PEM
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        from datetime import datetime, timezone

        device_key = DeviceKey(
            device_id=device_id,
            tenant_id=tenant_id,
            public_key=public_pem,
            private_key=private_pem,
            trust_level="unverified",
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )

        # Store on server
        self.store.put(tenant_id, self.NAMESPACE, device_id, self._device_to_dict(device_key))

        logger.info(
            f"Registered device with server-generated keys: tenant={tenant_id}, device={device_id}"
        )
        return device_key

    def register_device_client_generated(
        self,
        tenant_id: str,
        device_id: str,
        public_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> DeviceKey:
        """Register device with client-generated public key.

        Device generates ES256 keypair, keeps private key secure, sends public key.
        Server only stores public key for verification.

        Args:
            tenant_id: Tenant identifier
            device_id: Device identifier (UUID)
            public_key: PEM-encoded public key from device
            metadata: Optional device metadata

        Returns:
            DeviceKey with only public key

        Example:
            >>> store = DeviceKeyStore()
            >>> device = store.register_device_client_generated(
            ...     tenant_id="tenant-123",
            ...     device_id="device-456",
            ...     public_key="-----BEGIN PUBLIC KEY-----...",
            ...     metadata={"device_name": "Bob's Android"}
            ... )
            >>> device.private_key  # None - device keeps it
            None
        """
        from datetime import datetime, timezone

        device_key = DeviceKey(
            device_id=device_id,
            tenant_id=tenant_id,
            public_key=public_key,
            private_key=None,  # Client-generated - server never sees private key
            trust_level="unverified",
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )

        # Store on server
        self.store.put(tenant_id, self.NAMESPACE, device_id, self._device_to_dict(device_key))

        logger.info(
            f"Registered device with client-generated key: tenant={tenant_id}, device={device_id}"
        )
        return device_key

    def get_device_key(self, tenant_id: str, device_id: str) -> DeviceKey | None:
        """Get device key by tenant and device ID.

        Args:
            tenant_id: Tenant identifier
            device_id: Device identifier

        Returns:
            DeviceKey if found, None otherwise
        """
        data = self.store.get(tenant_id, self.NAMESPACE, device_id)
        if not data:
            return None

        return DeviceKey(**data)

    def update_trust_level(
        self, tenant_id: str, device_id: str, trust_level: str
    ) -> bool:
        """Update device trust level.

        Args:
            tenant_id: Tenant identifier
            device_id: Device identifier
            trust_level: New trust level (unverified | email_verified | trusted)

        Returns:
            True if updated, False if device not found
        """
        device = self.get_device_key(tenant_id, device_id)
        if not device:
            return False

        device.trust_level = trust_level
        self.store.put(tenant_id, self.NAMESPACE, device_id, self._device_to_dict(device))
        logger.info(
            f"Updated trust level: tenant={tenant_id}, device={device_id}, level={trust_level}"
        )
        return True

    def list_tenant_devices(self, tenant_id: str) -> list[DeviceKey]:
        """List all devices for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of device keys
        """
        device_ids = self.store.list_keys(tenant_id, self.NAMESPACE)
        devices = []

        for device_id in device_ids:
            data = self.store.get(tenant_id, self.NAMESPACE, device_id)
            if data:
                devices.append(DeviceKey(**data))

        return devices

    def delete_device(self, tenant_id: str, device_id: str) -> bool:
        """Delete device registration.

        Args:
            tenant_id: Tenant identifier
            device_id: Device identifier

        Returns:
            True if deleted, False if not found
        """
        success = self.store.delete(tenant_id, self.NAMESPACE, device_id)
        if success:
            logger.info(f"Deleted device: tenant={tenant_id}, device={device_id}")
        return success

    def _device_to_dict(self, device: DeviceKey) -> dict[str, Any]:
        """Convert DeviceKey to dict for storage.

        Args:
            device: Device key

        Returns:
            Device data as dict
        """
        return {
            "device_id": device.device_id,
            "tenant_id": device.tenant_id,
            "public_key": device.public_key,
            "private_key": device.private_key,
            "trust_level": device.trust_level,
            "created_at": device.created_at,
            "metadata": device.metadata,
        }
