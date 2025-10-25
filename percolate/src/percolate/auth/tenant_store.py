"""Abstract tenant storage provider interface.

Defines the contract for tenant data storage with multiple backend implementations:
- FileSystemTenantStore: JSON files on disk (dev/testing)
- RemTenantStore: percolate-rocks REM database (production - future)
"""

from abc import ABC, abstractmethod
from typing import Any


class TenantStore(ABC):
    """Abstract interface for tenant data storage.

    Provides key-value storage scoped by tenant ID.
    Implementations handle persistence, caching, and replication.

    Storage pattern:
        tenant_id -> namespace -> key -> value

    Example namespaces:
        - "device_keys": Device keypairs
        - "sessions": Active sessions
        - "settings": Tenant configuration
    """

    @abstractmethod
    def get(self, tenant_id: str, namespace: str, key: str) -> dict[str, Any] | None:
        """Get value by tenant, namespace, and key.

        Args:
            tenant_id: Tenant identifier
            namespace: Data namespace (e.g., "device_keys")
            key: Item key

        Returns:
            Value dict if found, None otherwise
        """
        pass

    @abstractmethod
    def put(self, tenant_id: str, namespace: str, key: str, value: dict[str, Any]) -> None:
        """Store value by tenant, namespace, and key.

        Args:
            tenant_id: Tenant identifier
            namespace: Data namespace
            key: Item key
            value: Value to store
        """
        pass

    @abstractmethod
    def delete(self, tenant_id: str, namespace: str, key: str) -> bool:
        """Delete value by tenant, namespace, and key.

        Args:
            tenant_id: Tenant identifier
            namespace: Data namespace
            key: Item key

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def list_keys(self, tenant_id: str, namespace: str) -> list[str]:
        """List all keys in namespace for tenant.

        Args:
            tenant_id: Tenant identifier
            namespace: Data namespace

        Returns:
            List of keys
        """
        pass

    @abstractmethod
    def list_namespaces(self, tenant_id: str) -> list[str]:
        """List all namespaces for tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of namespace names
        """
        pass
