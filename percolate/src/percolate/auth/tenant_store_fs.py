"""Filesystem-based tenant storage implementation.

Stores tenant data as JSON files on disk with tenant isolation.
Suitable for development, testing, and small deployments.

For production with high concurrency, use RemTenantStore (percolate-rocks).
"""

import json
import os
from pathlib import Path
from typing import Any

from loguru import logger

from percolate.auth.tenant_store import TenantStore


class FileSystemTenantStore(TenantStore):
    """Filesystem-based tenant storage.

    Storage layout:
        {base_path}/{tenant_id}/{namespace}/{key}.json

    Example:
        ~/.p8/tenants/tenant-123/device_keys/device-456.json

    Thread-safe: No (use file locking for concurrent writes)
    Performance: O(1) reads, filesystem-limited writes
    Scalability: Suitable for <1000 tenants, <10k keys per tenant
    """

    def __init__(self, base_path: str = "~/.p8/tenants"):
        """Initialize filesystem tenant store.

        Args:
            base_path: Root directory for tenant data
        """
        self.base_path = Path(os.path.expanduser(base_path))
        logger.info(f"FileSystemTenantStore initialized: {self.base_path}")

    def get(self, tenant_id: str, namespace: str, key: str) -> dict[str, Any] | None:
        """Get value by tenant, namespace, and key.

        Args:
            tenant_id: Tenant identifier
            namespace: Data namespace
            key: Item key

        Returns:
            Value dict if found, None otherwise
        """
        path = self._key_path(tenant_id, namespace, key)
        if not path.exists():
            return None

        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return None

    def put(self, tenant_id: str, namespace: str, key: str, value: dict[str, Any]) -> None:
        """Store value by tenant, namespace, and key.

        Args:
            tenant_id: Tenant identifier
            namespace: Data namespace
            key: Item key
            value: Value to store
        """
        path = self._key_path(tenant_id, namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, "w") as f:
                json.dump(value, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write {path}: {e}")
            raise

    def delete(self, tenant_id: str, namespace: str, key: str) -> bool:
        """Delete value by tenant, namespace, and key.

        Args:
            tenant_id: Tenant identifier
            namespace: Data namespace
            key: Item key

        Returns:
            True if deleted, False if not found
        """
        path = self._key_path(tenant_id, namespace, key)
        if not path.exists():
            return False

        try:
            path.unlink()
            return True
        except Exception as e:
            logger.error(f"Failed to delete {path}: {e}")
            return False

    def list_keys(self, tenant_id: str, namespace: str) -> list[str]:
        """List all keys in namespace for tenant.

        Args:
            tenant_id: Tenant identifier
            namespace: Data namespace

        Returns:
            List of keys (without .json extension)
        """
        namespace_dir = self.base_path / tenant_id / namespace
        if not namespace_dir.exists():
            return []

        try:
            return [
                path.stem  # Remove .json extension
                for path in namespace_dir.glob("*.json")
            ]
        except Exception as e:
            logger.error(f"Failed to list keys in {namespace_dir}: {e}")
            return []

    def list_namespaces(self, tenant_id: str) -> list[str]:
        """List all namespaces for tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of namespace names
        """
        tenant_dir = self.base_path / tenant_id
        if not tenant_dir.exists():
            return []

        try:
            return [
                path.name
                for path in tenant_dir.iterdir()
                if path.is_dir()
            ]
        except Exception as e:
            logger.error(f"Failed to list namespaces in {tenant_dir}: {e}")
            return []

    def _key_path(self, tenant_id: str, namespace: str, key: str) -> Path:
        """Get path to key file.

        Args:
            tenant_id: Tenant identifier
            namespace: Data namespace
            key: Item key

        Returns:
            Path to JSON file
        """
        return self.base_path / tenant_id / namespace / f"{key}.json"
