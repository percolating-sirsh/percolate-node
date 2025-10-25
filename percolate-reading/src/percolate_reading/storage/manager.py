"""Storage manager for parse artifacts.

Supports both local filesystem and S3 storage via FS abstraction.
"""

from pathlib import Path
from uuid import UUID

from percolate_reading.models.parse import StorageStrategy
from percolate_reading.storage.fs import fs
from percolate_reading.storage.strategies import (
    DatedStorageStrategy,
    SystemStorageStrategy,
    TenantStorageStrategy,
)


class StorageManager:
    """Manages artifact storage with configurable strategies.

    Responsibilities:
    - Create job directories
    - Write artifacts (markdown, tables, images, metadata)
    - Generate relative paths for ParseStorage model
    - Support multiple storage strategies (dated/tenant/system)
    """

    def __init__(self, base_dir: Path | str = ".fs/parsed"):
        """Initialize storage manager.

        Args:
            base_dir: Base directory for all parsed files (can be s3:///path or local)
        """
        self.base_dir_str = str(base_dir)

        # Only create local directory if not using S3
        if not self.base_dir_str.startswith("s3://"):
            self.base_dir = Path(base_dir)
            self.base_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.base_dir = Path(base_dir.replace("s3:///", "").replace("s3://", ""))

        # Initialize strategies
        self.strategies = {
            StorageStrategy.DATED: DatedStorageStrategy(self.base_dir),
            StorageStrategy.TENANT: TenantStorageStrategy(self.base_dir),
            StorageStrategy.SYSTEM: SystemStorageStrategy(self.base_dir),
        }

    def get_job_path(
        self, job_id: UUID, strategy: StorageStrategy = StorageStrategy.DATED, tenant_id: str | None = None
    ) -> Path:
        """Get storage path for a job.

        Args:
            job_id: Job ID
            strategy: Storage strategy to use
            tenant_id: Tenant ID (required for tenant strategy)

        Returns:
            Path to job directory

        Example:
            >>> manager = StorageManager()
            >>> path = manager.get_job_path(uuid, StorageStrategy.DATED)
            >>> print(path)
            .fs/parsed/2025/10/25/550e8400-e29b-41d4-a716-446655440000
        """
        strategy_impl = self.strategies[strategy]
        return strategy_impl.get_job_path(job_id, tenant_id)

    def ensure_job_dir(
        self, job_id: UUID, strategy: StorageStrategy = StorageStrategy.DATED, tenant_id: str | None = None
    ) -> Path:
        """Ensure job directory exists.

        Args:
            job_id: Job ID
            strategy: Storage strategy
            tenant_id: Tenant ID (for tenant strategy)

        Returns:
            Path to created job directory
        """
        strategy_impl = self.strategies[strategy]
        return strategy_impl.ensure_job_dir(job_id, tenant_id)

    def write_artifact(
        self,
        job_id: UUID,
        artifact_name: str,
        content: str | bytes,
        strategy: StorageStrategy = StorageStrategy.DATED,
        tenant_id: str | None = None,
    ) -> Path:
        """Write an artifact to storage (local or S3).

        Args:
            job_id: Job ID
            artifact_name: Artifact path relative to job dir (e.g., "structured.md", "tables/table_0.csv")
            content: Content to write (str or bytes)
            strategy: Storage strategy
            tenant_id: Tenant ID (for tenant strategy)

        Returns:
            Path to written artifact

        Example:
            >>> manager = StorageManager()
            >>> path = manager.write_artifact(
            ...     job_id,
            ...     "structured.md",
            ...     "# Document Title\n\nContent..."
            ... )
        """
        job_dir = self.ensure_job_dir(job_id, strategy, tenant_id)
        artifact_path = job_dir / artifact_name

        # Build full path (s3:// or local)
        if self.base_dir_str.startswith("s3://"):
            # S3 path - combine base_dir with relative path
            full_path = f"{self.base_dir_str.rstrip('/')}/{artifact_path}"
        else:
            # Local path
            full_path = str(artifact_path)
            # Ensure parent directory exists for local files
            artifact_path.parent.mkdir(parents=True, exist_ok=True)

        # Write using FS abstraction
        fs.write(full_path, content)

        return artifact_path

    def get_relative_path(self, job_id: UUID, artifact_path: Path, strategy: StorageStrategy = StorageStrategy.DATED, tenant_id: str | None = None) -> str:
        """Get path relative to job directory.

        Args:
            job_id: Job ID
            artifact_path: Absolute path to artifact
            strategy: Storage strategy
            tenant_id: Tenant ID

        Returns:
            Relative path string

        Example:
            >>> manager = StorageManager()
            >>> abs_path = Path(".fs/parsed/2025/10/25/abc-123/structured.md")
            >>> rel_path = manager.get_relative_path(uuid, abs_path)
            >>> print(rel_path)
            structured.md
        """
        job_dir = self.get_job_path(job_id, strategy, tenant_id)
        return str(artifact_path.relative_to(job_dir))

    def cleanup_job(
        self, job_id: UUID, strategy: StorageStrategy = StorageStrategy.DATED, tenant_id: str | None = None
    ) -> None:
        """Remove all artifacts for a job.

        Args:
            job_id: Job ID
            strategy: Storage strategy
            tenant_id: Tenant ID

        Example:
            >>> manager = StorageManager()
            >>> manager.cleanup_job(job_id)  # Remove all files
        """
        job_dir = self.get_job_path(job_id, strategy, tenant_id)
        if job_dir.exists():
            import shutil

            shutil.rmtree(job_dir)
