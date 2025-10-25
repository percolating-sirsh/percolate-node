"""Parse job models for document processing workflow.

IMPORTANT: These models are duplicated for development convenience.
In production, import from percolate-rocks (the Source of Truth).

Source of Truth: percolate-rocks/python/percolate_rocks/parse.py
Protocol Spec: percolate-rocks/docs/parsing.md

TODO: Replace with imports once percolate-rocks is published:
    from percolate_rocks.parse import (
        ParseJob, ParseResult, ParseStatus, ParseStorage,
        ParseContent, ParseQuality, ParseError, StorageStrategy, QualityFlag
    )

This consolidates:
- percolate-rocks protocol spec (SoT)
- percolate-reading implementation
- Quality indicators for iterative parsing
"""

from typing import Optional, Literal, Any
from datetime import datetime
from enum import Enum
from pathlib import Path
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class ParseStatus(str, Enum):
    """Parse job status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class StorageStrategy(str, Enum):
    """Storage location strategy for parse artifacts."""

    DATED = "dated"  # .fs/parsed/yyyy/mm/dd/{job_id}/
    TENANT = "tenant"  # .fs/parsed/{tenant_id}/{job_id}/
    SYSTEM = "system"  # .fs/parsed/system/{job_id}/
    LOCAL = "local"  # Alias for dated (percolate-rocks compat)
    S3 = "s3"  # S3 storage


class QualityFlag(str, Enum):
    """Quality indicators from semantic parsing."""

    MULTI_COLUMN_LAYOUT = "multi_column_layout"
    COMPLEX_TABLE = "complex_table"
    LOW_OCR_CONFIDENCE = "low_ocr_confidence"
    MISSING_STRUCTURE = "missing_structure"
    DATA_LOSS_SUSPECTED = "data_loss_suspected"


class ParseStorage(BaseModel):
    """Storage location for parse artifacts."""

    strategy: StorageStrategy = Field(description="Storage backend")
    base_path: str = Field(description="Base path (local or S3)")

    artifacts: dict[str, str | list[str]] = Field(
        description="Artifact paths relative to base_path",
        examples=[
            {
                "structured_md": "structured.md",
                "tables": ["tables/table_0.csv", "tables/table_1.csv"],
                "images": ["images/image_0.png"],
                "metadata": "metadata.json",
            }
        ],
    )

    model_config = ConfigDict(frozen=True)


class ParseContent(BaseModel):
    """Content statistics from parsing."""

    text_length: int = Field(description="Total text length in characters")
    num_tables: int = Field(default=0, description="Number of tables extracted")
    num_images: int = Field(default=0, description="Number of images extracted")
    num_pages: Optional[int] = Field(
        default=None, description="Number of pages (if applicable)"
    )
    languages: list[str] = Field(
        default_factory=list, description="Detected languages (ISO 639-1)"
    )

    model_config = ConfigDict(frozen=True)


class ParseQuality(BaseModel):
    """Quality assessment for parsed content."""

    overall_score: float = Field(
        ge=0.0, le=1.0, default=1.0, description="Overall quality (0-1)"
    )
    flags: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Quality flags with location and confidence",
        examples=[
            [
                {
                    "type": "COMPLEX_TABLE",
                    "location": "page 5, table 1",
                    "confidence": 0.75,
                    "suggestion": "Verify with visual OCR",
                }
            ]
        ],
    )

    @property
    def needs_verification(self) -> bool:
        """Should this content be verified with additional methods?"""
        return self.overall_score < 0.85 or any(
            f.get("type") in ["COMPLEX_TABLE", "DATA_LOSS_SUSPECTED"]
            for f in self.flags
        )

    model_config = ConfigDict(frozen=True)


class ParseError(BaseModel):
    """Parse error details."""

    code: str = Field(description="Error code")
    message: str = Field(description="Human-readable message")
    details: Optional[str] = Field(default=None, description="Additional details")

    model_config = ConfigDict(frozen=True)


class ParseResult(BaseModel):
    """Structured output from document parsing.

    Nested structure supports archives (ZIP → PDF → tables/images).
    """

    file_name: str = Field(description="Original filename")
    file_type: str = Field(description="MIME type")
    file_size_bytes: int = Field(description="File size in bytes")
    parse_duration_ms: int = Field(description="Parse duration in milliseconds")

    storage: ParseStorage = Field(description="Storage location for artifacts")
    content: ParseContent = Field(description="Content statistics")
    quality: ParseQuality = Field(
        default_factory=ParseQuality, description="Quality assessment"
    )

    warnings: list[str] = Field(
        default_factory=list, description="Non-fatal warnings"
    )

    # Nested results for archives (ZIP → PDFs → tables/images)
    children: list["ParseResult"] = Field(
        default_factory=list,
        description="Nested parse results for archive contents",
    )

    model_config = ConfigDict(frozen=False)


class ParseJob(BaseModel):
    """Parse job with full lifecycle tracking.

    Consolidates protocol from:
    - percolate-rocks: .spikes/percolate-rocks/docs/parsing.md
    - percolate-reading: src/percolate_reading/models/parse.py

    Workflow:
        1. Client uploads document → POST /v1/parse
        2. Server creates job_id → Returns 202 with status_uri
        3. Background worker processes file
        4. Worker updates job status (WebSocket notifications)
        5. Client polls GET /v1/parse/{job_id}
        6. On completion, artifacts stored in .fs/parse-jobs/{job_id}/
        7. Optional webhook callback fired

    Storage conventions:
        - dated: .fs/parsed/yyyy/mm/dd/{job_id}/
        - tenant: .fs/parsed/{tenant_id}/{job_id}/
        - system: .fs/parsed/system/{job_id}/
        - s3: s3://<bucket>/parse-jobs/{tenant_id}/{job_id}/

    Example:
        >>> job = ParseJob(
        ...     job_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        ...     status=ParseStatus.PROCESSING,
        ...     progress=0.45,
        ...     file_name="contract.pdf",
        ...     file_type="application/pdf",
        ...     file_size_bytes=524288
        ... )
    """

    # Job identification
    job_id: UUID = Field(description="Unique job ID")

    # Status tracking
    status: ParseStatus = Field(description="Job status")
    progress: float = Field(
        ge=0.0, le=1.0, default=0.0, description="Progress (0.0-1.0)"
    )
    message: Optional[str] = Field(default=None, description="Status message")

    # File information
    file_name: str = Field(description="Original file name")
    file_type: str = Field(description="MIME type")
    file_size_bytes: int = Field(description="File size in bytes")

    # Storage configuration
    storage_strategy: StorageStrategy = Field(
        default=StorageStrategy.DATED, description="Storage strategy"
    )
    tenant_id: Optional[str] = Field(
        default=None, description="Tenant ID (if tenant strategy)"
    )

    # Result data
    result: Optional[ParseResult] = Field(
        default=None, description="Parse result (if completed)"
    )
    error: Optional[ParseError] = Field(
        default=None, description="Error details (if failed)"
    )

    # Webhook callback
    callback_url: Optional[str] = Field(
        default=None, description="Webhook URL for completion notification"
    )

    # Timestamps
    created_at: datetime = Field(description="Job created timestamp")
    started_at: Optional[datetime] = Field(
        default=None, description="Job started timestamp"
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="Job completed timestamp"
    )
    failed_at: Optional[datetime] = Field(
        default=None, description="Job failed timestamp"
    )

    # Queue position (for pending jobs)
    position_in_queue: Optional[int] = Field(
        default=None, description="Position in queue (pending only)"
    )

    model_config = ConfigDict(
        frozen=False,
        json_schema_extra={
            "examples": [
                {
                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "completed",
                    "progress": 1.0,
                    "file_name": "contract.pdf",
                    "file_type": "application/pdf",
                    "file_size_bytes": 524288,
                    "storage_strategy": "dated",
                    "tenant_id": "tenant_12345678",
                    "result": {
                        "file_name": "contract.pdf",
                        "file_type": "application/pdf",
                        "file_size_bytes": 524288,
                        "parse_duration_ms": 3450,
                        "storage": {
                            "strategy": "dated",
                            "base_path": ".fs/parsed/2025/10/25/550e8400-e29b-41d4-a716-446655440000",
                            "artifacts": {
                                "structured_md": "structured.md",
                                "tables": ["tables/table_0.csv", "tables/table_1.csv"],
                                "images": ["images/image_0.png"],
                                "metadata": "metadata.json",
                            },
                        },
                        "content": {
                            "text_length": 45234,
                            "num_tables": 2,
                            "num_images": 1,
                            "num_pages": 7,
                            "languages": ["en"],
                        },
                        "quality": {
                            "overall_score": 0.85,
                            "flags": [
                                {
                                    "type": "COMPLEX_TABLE",
                                    "location": "page 5, table 1",
                                    "confidence": 0.75,
                                }
                            ],
                        },
                        "warnings": ["Page 5: Low OCR confidence (0.65) - verify manually"],
                    },
                    "created_at": "2025-10-25T10:30:00Z",
                    "started_at": "2025-10-25T10:30:02Z",
                    "completed_at": "2025-10-25T10:30:05Z",
                }
            ]
        },
    )


# Enable recursive model for nested parse results
ParseResult.model_rebuild()
