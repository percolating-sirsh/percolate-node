"""Factory for tenant storage providers.

Creates appropriate TenantStore implementation based on configuration.
"""

from loguru import logger

from percolate.auth.tenant_store import TenantStore
from percolate.auth.tenant_store_fs import FileSystemTenantStore
from percolate.settings import settings


# Singleton instance
_tenant_store_instance: TenantStore | None = None


def get_tenant_store() -> TenantStore:
    """Get tenant store instance (singleton).

    Returns:
        TenantStore implementation based on AUTH__DEVICE_TENANT_STORE setting

    Raises:
        ValueError: If tenant store type is invalid
    """
    global _tenant_store_instance

    if _tenant_store_instance is not None:
        return _tenant_store_instance

    store_type = settings.auth.device_tenant_store.lower()

    if store_type == "filesystem":
        logger.info("Initializing FileSystemTenantStore")
        _tenant_store_instance = FileSystemTenantStore(
            base_path=settings.auth.device_keys_path
        )
    elif store_type == "rem":
        # Future: RemTenantStore when percolate-rocks is ready
        logger.warning("REM tenant store not yet implemented, falling back to filesystem")
        _tenant_store_instance = FileSystemTenantStore(
            base_path=settings.auth.device_keys_path
        )
    else:
        raise ValueError(
            f"Invalid tenant store type: {store_type}. "
            f"Valid options: filesystem, rem"
        )

    return _tenant_store_instance
