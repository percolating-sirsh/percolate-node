"""Storage management for parse artifacts.

Implements carrier-style storage strategies:
- dated: .fs/parsed/yyyy/mm/dd/{job_id}/
- tenant: .fs/parsed/{tenant_id}/{job_id}/
- system: .fs/parsed/system/{job_id}/
"""

from percolate_reading.storage.manager import StorageManager
from percolate_reading.storage.strategies import (
    DatedStorageStrategy,
    TenantStorageStrategy,
    SystemStorageStrategy,
)

__all__ = [
    "StorageManager",
    "DatedStorageStrategy",
    "TenantStorageStrategy",
    "SystemStorageStrategy",
]
