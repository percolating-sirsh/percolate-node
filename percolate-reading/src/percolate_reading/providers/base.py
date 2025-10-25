"""Base provider abstraction for document parsing.

Pattern from carrier.parsers with async support and job tracking.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Callable
from uuid import UUID

from loguru import logger

from percolate_reading.models.parse import ParseResult, ParseJob, ParseStatus
from percolate_reading.storage.manager import StorageManager


class ParseProvider(ABC):
    """Base class for all parse providers.

    Responsibilities:
    - Accept file input and parse to structured output
    - Generate ParseResult with quality assessment
    - Store artifacts in configured location
    - Report progress for long-running operations

    Subclasses implement:
    - _parse(): Core parsing logic
    - supported_types: MIME types this provider handles
    """

    def __init__(self, storage_manager: StorageManager):
        """Initialize provider.

        Args:
            storage_manager: Storage manager for artifacts
        """
        self.storage = storage_manager
        self._current_job: ParseJob | None = None

    @property
    @abstractmethod
    def supported_types(self) -> list[str]:
        """MIME types this provider can handle.

        Returns:
            List of MIME types (e.g., ["application/pdf"])
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider name for logging/tracking.

        Returns:
            Provider name (e.g., "kreuzberg_pdf")
        """
        pass

    @abstractmethod
    async def _parse(
        self,
        file_path: Path,
        job_id: UUID,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> ParseResult:
        """Core parsing logic (implemented by subclasses).

        Args:
            file_path: Path to file to parse
            job_id: Job ID for artifact storage
            progress_callback: Optional callback for progress updates (progress, message)

        Returns:
            ParseResult with structured output

        Raises:
            Exception: On parsing failure
        """
        pass

    async def parse(
        self,
        file_path: Path,
        job: ParseJob,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> ParseResult:
        """Parse file and store artifacts.

        This is the main entry point - handles:
        1. Validation
        2. Calling _parse() implementation
        3. Logging and error handling

        Args:
            file_path: Path to file
            job: Parse job (for metadata and storage config)
            progress_callback: Optional progress callback

        Returns:
            ParseResult with artifacts

        Raises:
            ValueError: If file type not supported
            Exception: On parsing failure
        """
        # Validate file type
        if job.file_type not in self.supported_types:
            raise ValueError(
                f"Unsupported file type: {job.file_type}. "
                f"Supported: {', '.join(self.supported_types)}"
            )

        # Validate file exists
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(
            f"Parsing {job.file_name} with {self.provider_name} "
            f"(job_id={job.job_id})"
        )

        start_time = datetime.now()

        try:
            # Store job context for providers to access
            self._current_job = job

            # Call provider implementation
            result = await self._parse(file_path, job.job_id, progress_callback)

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            result.parse_duration_ms = duration_ms

            logger.success(
                f"Parsed {job.file_name} in {duration_ms}ms "
                f"({result.content.num_pages} pages, "
                f"{result.content.num_tables} tables, "
                f"quality={result.quality.overall_score:.2f})"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to parse {job.file_name}: {e}")
            raise
        finally:
            # Clear job context
            self._current_job = None

    def get_job_path(self, job_id: UUID) -> Path:
        """Get storage path for current job.

        Uses job's storage strategy and tenant_id from context.

        Args:
            job_id: Job ID

        Returns:
            Path to job directory

        Example:
            >>> path = self.get_job_path(job_id)
            >>> # Returns .fs/parse-jobs/2025/10/25/{job_id}/ (dated)
            >>> # or .fs/parse-jobs/{tenant_id}/{job_id}/ (tenant)
        """
        if self._current_job:
            return self.storage.get_job_path(
                job_id,
                self._current_job.storage_strategy,
                self._current_job.tenant_id,
            )
        return self.storage.get_job_path(job_id)

    def write_artifact(
        self, job_id: UUID, artifact_name: str, content: str | bytes
    ) -> Path:
        """Write artifact using current job's storage strategy.

        Args:
            job_id: Job ID
            artifact_name: Artifact filename (e.g., "transcript.txt")
            content: Content to write

        Returns:
            Path to written artifact

        Example:
            >>> path = self.write_artifact(job_id, "structured.md", "# Title\\n...")
        """
        if self._current_job:
            return self.storage.write_artifact(
                job_id,
                artifact_name,
                content,
                self._current_job.storage_strategy,
                self._current_job.tenant_id,
            )
        return self.storage.write_artifact(job_id, artifact_name, content)


class ProviderRegistry:
    """Registry for parse providers with automatic routing by MIME type.

    Example:
        >>> registry = ProviderRegistry(storage_manager)
        >>> registry.register(PDFProvider(storage_manager))
        >>> provider = registry.get_provider("application/pdf")
    """

    def __init__(self, storage_manager: StorageManager):
        """Initialize registry.

        Args:
            storage_manager: Storage manager to pass to providers
        """
        self.storage_manager = storage_manager
        self._providers: dict[str, ParseProvider] = {}

    def register(self, provider: ParseProvider) -> None:
        """Register a provider for its supported types.

        Args:
            provider: Provider instance
        """
        for mime_type in provider.supported_types:
            if mime_type in self._providers:
                logger.warning(
                    f"Overriding provider for {mime_type}: "
                    f"{self._providers[mime_type].provider_name} → {provider.provider_name}"
                )
            self._providers[mime_type] = provider
            logger.debug(f"Registered {provider.provider_name} for {mime_type}")

    def get_provider(self, mime_type: str) -> ParseProvider:
        """Get provider for MIME type.

        Args:
            mime_type: MIME type

        Returns:
            Provider instance

        Raises:
            ValueError: If no provider registered for type
        """
        if mime_type not in self._providers:
            raise ValueError(
                f"No provider registered for {mime_type}. "
                f"Supported: {', '.join(self._providers.keys())}"
            )
        return self._providers[mime_type]

    def list_supported_types(self) -> list[str]:
        """List all supported MIME types.

        Returns:
            List of supported MIME types
        """
        return list(self._providers.keys())
