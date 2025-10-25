"""FastAPI application for document parsing service.

Implements the parse protocol with:
- Multipart file uploads
- Job-based processing with status tracking
- Optional API token authentication
- Provider-based parsing (PDF, Excel, Audio, Image)
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, Header
from fastapi.responses import JSONResponse
from loguru import logger

from percolate_reading.models.parse import (
    ParseError,
    ParseJob,
    ParseResult,
    ParseStatus,
    StorageStrategy,
)
from percolate_reading.providers.audio import AudioProvider
from percolate_reading.providers.base import ProviderRegistry
from percolate_reading.providers.excel import ExcelProvider
from percolate_reading.providers.image import ImageProvider
from percolate_reading.providers.pdf import PDFProvider
from percolate_reading.settings import settings
from percolate_reading.storage.manager import StorageManager


def verify_token(authorization: Annotated[str | None, Header()] = None) -> None:
    """Verify API token if auth is enabled.

    Args:
        authorization: Authorization header value

    Raises:
        HTTPException: If auth enabled and token invalid
    """
    if not settings.auth_enabled:
        return

    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Extract Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = parts[1]
    if token != settings.api_token:
        raise HTTPException(status_code=401, detail="Invalid API token")


def create_app() -> FastAPI:
    """Create FastAPI application with parse endpoints.

    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="Percolate Reading API",
        description="Document parsing and extraction service",
        version="0.1.0",
    )

    # Initialize storage and provider registry
    storage = StorageManager(base_dir=Path(settings.storage_path))

    registry = ProviderRegistry(storage)

    # Register providers
    registry.register(PDFProvider(storage))
    registry.register(ExcelProvider(storage))
    registry.register(AudioProvider(storage))
    registry.register(ImageProvider(storage))

    @app.get("/health")
    async def health() -> dict:
        """Health check endpoint.

        Returns:
            Health status
        """
        return {
            "status": "healthy",
            "version": "0.1.0",
            "providers": registry.list_supported_types(),
        }

    @app.post("/v1/parse")
    async def parse_file(
        file: UploadFile = File(...),
        storage_strategy: StorageStrategy = StorageStrategy.DATED,
        tenant_id: str | None = None,
        _: None = Depends(verify_token),
    ) -> JSONResponse:
        """Parse uploaded file with appropriate provider.

        Args:
            file: Uploaded file (multipart)
            storage_strategy: Storage strategy (dated/tenant/system)
            tenant_id: Tenant ID (required if strategy=TENANT)

        Returns:
            Parse job status and result

        Raises:
            HTTPException: If file type unsupported or parsing fails
        """
        # Validate tenant_id for TENANT strategy
        if storage_strategy == StorageStrategy.TENANT and not tenant_id:
            raise HTTPException(
                status_code=400,
                detail="tenant_id required for TENANT storage strategy"
            )

        # Detect content type
        content_type = file.content_type or "application/octet-stream"

        # Get provider for content type
        try:
            provider = registry.get_provider(content_type)
        except ValueError as e:
            raise HTTPException(status_code=415, detail=str(e))

        # Read file content to get size
        content = await file.read()
        file_size = len(content)

        # Create job
        job_id = uuid.uuid4()
        job = ParseJob(
            job_id=job_id,
            file_name=file.filename or "unknown",
            file_type=content_type,
            file_size_bytes=file_size,
            status=ParseStatus.PROCESSING,
            progress=0.0,
            storage_strategy=storage_strategy,
            tenant_id=tenant_id,
            created_at=datetime.now(),
        )

        # Save uploaded file to temp location
        temp_dir = Path(settings.storage_path) / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file = temp_dir / f"{job_id}_{file.filename}"

        try:
            # Write uploaded file
            with temp_file.open("wb") as f:
                f.write(content)

            logger.info(f"Parsing {file.filename} with {provider.provider_name}")

            # Parse file
            result = await provider.parse(temp_file, job)

            # Update job status
            job.status = ParseStatus.COMPLETED
            job.completed_at = datetime.now()
            job.result = result

            logger.success(
                f"Parsed {file.filename} successfully "
                f"(job_id={job_id}, duration={result.parse_duration_ms}ms)"
            )

            return JSONResponse(
                status_code=200,
                content={
                    "job_id": str(job_id),
                    "status": job.status.value,
                    "result": {
                        "file_name": result.file_name,
                        "file_type": result.file_type,
                        "parse_duration_ms": result.parse_duration_ms,
                        "storage": result.storage.model_dump(),
                        "content": result.content.model_dump(),
                        "quality": result.quality.model_dump(),
                        "warnings": result.warnings,
                    }
                }
            )

        except Exception as e:
            logger.error(f"Failed to parse {file.filename}: {e}")

            # Update job status
            job.status = ParseStatus.FAILED
            job.error = ParseError(
                code="PARSE_ERROR",
                message=str(e),
                details=str(type(e).__name__)
            )
            job.failed_at = datetime.now()

            raise HTTPException(
                status_code=500,
                detail=f"Parsing failed: {str(e)}"
            )

        finally:
            # Cleanup temp file
            if temp_file.exists():
                temp_file.unlink()

    return app
