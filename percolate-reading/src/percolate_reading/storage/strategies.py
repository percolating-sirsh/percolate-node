"""Storage path strategies for parse artifacts.

Based on carrier's parse storage patterns with date/tenant/system paths.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from uuid import UUID


class StorageStrategyBase(ABC):
    """Base class for storage path strategies."""

    def __init__(self, base_dir: Path):
        """Initialize storage strategy.

        Args:
            base_dir: Base directory for all parsed files (e.g., .fs/parsed)
        """
        self.base_dir = base_dir

    @abstractmethod
    def get_job_path(self, job_id: UUID, tenant_id: str | None = None) -> Path:
        """Get storage path for a job.

        Args:
            job_id: Job ID
            tenant_id: Optional tenant ID (required for tenant strategy)

        Returns:
            Path to job directory
        """
        pass

    def ensure_job_dir(self, job_id: UUID, tenant_id: str | None = None) -> Path:
        """Ensure job directory exists and return path.

        Args:
            job_id: Job ID
            tenant_id: Optional tenant ID

        Returns:
            Path to job directory
        """
        job_path = self.get_job_path(job_id, tenant_id)
        job_path.mkdir(parents=True, exist_ok=True)
        return job_path

    def get_artifact_path(
        self, job_id: UUID, artifact_name: str, tenant_id: str | None = None
    ) -> Path:
        """Get full path to an artifact.

        Args:
            job_id: Job ID
            artifact_name: Artifact filename (e.g., "structured.md", "tables/table_0.csv")
            tenant_id: Optional tenant ID

        Returns:
            Path to artifact file
        """
        job_path = self.get_job_path(job_id, tenant_id)
        return job_path / artifact_name


class DatedStorageStrategy(StorageStrategyBase):
    """Date-based storage strategy (default).

    Path format: .fs/parsed/yyyy/mm/dd/{job_id}/

    This is the default strategy - organizes by date for easy cleanup
    and archival. Good for general use cases.
    """

    def get_job_path(self, job_id: UUID, tenant_id: str | None = None) -> Path:
        """Get date-based path.

        Args:
            job_id: Job ID
            tenant_id: Ignored for dated strategy

        Returns:
            Path like .fs/parsed/2025/10/25/{job_id}/
        """
        now = datetime.now()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")

        return self.base_dir / year / month / day / str(job_id)


class TenantStorageStrategy(StorageStrategyBase):
    """Tenant-scoped storage strategy.

    Path format: .fs/parsed/{tenant_id}/{job_id}/

    Use this for multi-tenant deployments where you want isolation
    by tenant for easier quota management, billing, or cleanup.
    """

    def get_job_path(self, job_id: UUID, tenant_id: str | None = None) -> Path:
        """Get tenant-scoped path.

        Args:
            job_id: Job ID
            tenant_id: Tenant ID (required)

        Returns:
            Path like .fs/parsed/tenant-123/{job_id}/

        Raises:
            ValueError: If tenant_id is None
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for TenantStorageStrategy")

        return self.base_dir / tenant_id / str(job_id)


class SystemStorageStrategy(StorageStrategyBase):
    """System-wide storage strategy.

    Path format: .fs/parsed/system/{job_id}/

    Use this for shared/system files that aren't tenant-specific.
    Good for reference documents, templates, etc.
    """

    def get_job_path(self, job_id: UUID, tenant_id: str | None = None) -> Path:
        """Get system-wide path.

        Args:
            job_id: Job ID
            tenant_id: Ignored for system strategy

        Returns:
            Path like .fs/parsed/system/{job_id}/
        """
        return self.base_dir / "system" / str(job_id)
