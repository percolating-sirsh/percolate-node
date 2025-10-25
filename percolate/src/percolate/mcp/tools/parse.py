"""Document parsing MCP tool."""

import mimetypes
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from percolate.settings import settings


async def parse_document(
    file_path: str,
    tenant_id: str | None = None,
    storage_strategy: str = "dated",
    extract_entities: bool = False,
    store_in_memory: bool = False,
) -> dict[str, Any]:
    """Parse document via percolate-reading API.

    Submits file to percolate-reading service for parsing. Supports PDF,
    Excel, audio files, and images.

    Args:
        file_path: Path to document file (local filesystem)
        tenant_id: Optional tenant identifier for scoped storage
        storage_strategy: Storage strategy (dated/tenant/system)
        extract_entities: Whether to extract entities (not yet implemented)
        store_in_memory: Whether to store in REM (not yet implemented)

    Returns:
        Parse result with content, metadata, and quality assessment

    Raises:
        FileNotFoundError: If file doesn't exist
        httpx.HTTPError: If API request fails

    Example:
        >>> result = await parse_document(
        ...     file_path="/tmp/report.pdf",
        ...     tenant_id="user-123",
        ...     storage_strategy="tenant"
        ... )
        >>> result["job_id"]
        '550e8400-e29b-41d4-a716-446655440000'
    """
    # Validate file exists
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Detect MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    logger.info(
        f"Submitting parse job: {file_path_obj.name} "
        f"(type={mime_type}, strategy={storage_strategy}, tenant={tenant_id})"
    )

    # Build API URL
    reading_url = getattr(settings, "percolate_reading_url", "http://localhost:8001")
    api_url = f"{reading_url}/v1/parse"

    # Prepare multipart form data
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Open file and send
        with file_path_obj.open("rb") as f:
            files = {"file": (file_path_obj.name, f, mime_type)}
            data = {"storage_strategy": storage_strategy}
            if tenant_id:
                data["tenant_id"] = tenant_id

            # Add auth header if configured
            headers = {}
            api_token = getattr(settings, "percolate_reading_api_token", None)
            if api_token:
                headers["Authorization"] = f"Bearer {api_token}"

            logger.debug(f"POST {api_url} with file={file_path_obj.name}")

            response = await client.post(api_url, files=files, data=data, headers=headers)
            response.raise_for_status()

            result = response.json()

    logger.success(
        f"Parse job completed: {result.get('job_id')} "
        f"(status={result.get('status')}, duration={result.get('result', {}).get('parse_duration_ms')}ms)"
    )

    # TODO: Implement entity extraction if requested
    if extract_entities:
        logger.warning("Entity extraction not yet implemented")

    # TODO: Implement REM storage if requested
    if store_in_memory:
        logger.warning("REM memory storage not yet implemented")

    return result
