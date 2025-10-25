# Parsing protocol

**Source of Truth for REM Parse Protocol**

This document defines the canonical parse job protocol for the REM ecosystem.
All implementations (percolate-reading, percolate, etc.) MUST import models
from percolate-rocks for protocol compliance.

## Overview

REM delegates document parsing to external **parse providers** via a standard HTTP API. This separation allows specialized parsing infrastructure (GPU-based OCR, cloud services, distributed processing) without coupling REM to specific implementations.

**Key principles:**
- REM orchestrates, providers execute
- Nested parse results (ZIP → PDF → tables/images)
- Asynchronous job tracking with URIs
- Flexible storage (local filesystem or S3)
- Parse metadata always registered, content ingested on demand
- Quality assessment for iterative verification

**Protocol ownership:**
- Models defined in: `percolate-rocks` Python package
- Imported by: `percolate-reading`, `percolate`, and other consumers
- Protocol versioned with percolate-rocks releases

## Parse provider API

### POST /v1/parse

Submit a file for parsing.

**Request:**
```http
POST /v1/parse HTTP/1.1
Content-Type: multipart/form-data

file: <binary>
extract_types: ["text", "tables", "images", "metadata"]
storage_strategy: "local" | "s3"
storage_path: "optional/custom/path"
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "status_uri": "http://parser.local/v1/parse/550e8400-e29b-41d4-a716-446655440000",
  "estimated_duration_ms": 5000,
  "accepted_at": "2025-10-25T10:30:00Z"
}
```

### GET /v1/parse/{job_id}

Get parse job status and results.

**Response (pending):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "progress": 0.0,
  "message": "Waiting in queue",
  "created_at": "2025-10-25T10:30:00Z"
}
```

**Response (processing):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 0.45,
  "message": "Extracting page 3 of 7",
  "created_at": "2025-10-25T10:30:00Z",
  "started_at": "2025-10-25T10:30:02Z"
}
```

**Response (completed):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 1.0,
  "result": {
    "file_name": "report.pdf",
    "file_type": "application/pdf",
    "file_size_bytes": 1048576,
    "parse_duration_ms": 3450,

    "storage": {
      "strategy": "local",
      "base_path": "/var/parse-jobs/550e8400-e29b-41d4-a716-446655440000",
      "artifacts": {
        "structured_md": "structured.md",
        "tables": ["table_0.csv", "table_1.csv"],
        "images": ["image_0.png", "image_1.png"],
        "metadata": "metadata.json"
      }
    },

    "content": {
      "text_length": 45234,
      "num_tables": 2,
      "num_images": 2,
      "num_pages": 7,
      "languages": ["en"]
    },

    "warnings": [
      "Page 5: Low OCR confidence (0.65) - verify manually"
    ],

    "nested_results": [
      {
        "file_name": "attachment.zip",
        "file_type": "application/zip",
        "children": [
          {
            "file_name": "invoice.pdf",
            "file_type": "application/pdf",
            "storage": {
              "base_path": "/var/parse-jobs/550e8400.../attachment.zip/invoice.pdf",
              "artifacts": {
                "structured_md": "structured.md"
              }
            }
          }
        ]
      }
    ]
  },
  "created_at": "2025-10-25T10:30:00Z",
  "started_at": "2025-10-25T10:30:02Z",
  "completed_at": "2025-10-25T10:30:05Z"
}
```

**Response (failed):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "progress": 0.3,
  "error": {
    "code": "UNSUPPORTED_FORMAT",
    "message": "File format .xyz is not supported",
    "details": "Supported formats: pdf, docx, xlsx, zip, txt, md"
  },
  "created_at": "2025-10-25T10:30:00Z",
  "started_at": "2025-10-25T10:30:02Z",
  "failed_at": "2025-10-25T10:30:03Z"
}
```

## Pydantic models

**IMPORTANT:** All parse protocol models are defined in the `percolate-rocks` Python package
and MUST be imported from there for protocol compliance.

### Installation

```bash
pip install percolate-rocks
```

### Import models

```python
from percolate_rocks.parse import (
    ParseJob,
    ParseResult,
    ParseStatus,
    ParseStorage,
    ParseContent,
    ParseQuality,
    ParseError,
    StorageStrategy,
    QualityFlag,
)
```

### Model definitions

**Models are defined in:** `percolate-rocks/python/percolate_rocks/parse.py`

**Complete protocol:**

```python
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum
from typing import Optional, Any
from uuid import UUID

class ParseStatus(str, Enum):
    """Parse job status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class StorageStrategy(str, Enum):
    """Storage location strategy for parse artifacts."""
    DATED = "dated"    # .fs/parsed/yyyy/mm/dd/{job_id}/
    TENANT = "tenant"  # .fs/parsed/{tenant_id}/{job_id}/
    SYSTEM = "system"  # .fs/parsed/system/{job_id}/
    LOCAL = "local"    # Alias for dated (backward compat)
    S3 = "s3"          # S3 storage

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
        examples=[{
            "structured_md": "structured.md",
            "tables": ["tables/table_0.csv", "tables/table_1.csv"],
            "images": ["images/image_0.png"],
            "metadata": "metadata.json"
        }]
    )

    model_config = ConfigDict(frozen=True)

class ParseContent(BaseModel):
    """Content statistics from parsing."""

    text_length: int = Field(description="Total text length in characters")
    num_tables: int = Field(default=0, description="Number of tables extracted")
    num_images: int = Field(default=0, description="Number of images extracted")
    num_pages: Optional[int] = Field(default=None, description="Number of pages (if applicable)")
    languages: list[str] = Field(default_factory=list, description="Detected languages (ISO 639-1)")

    model_config = ConfigDict(frozen=True)

class ParseQuality(BaseModel):
    """Quality assessment for parsed content."""

    overall_score: float = Field(ge=0.0, le=1.0, default=1.0, description="Overall quality (0-1)")
    flags: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Quality flags with location and confidence",
        examples=[[{
            "type": "COMPLEX_TABLE",
            "location": "page 5, table 1",
            "confidence": 0.75,
            "suggestion": "Verify with visual OCR"
        }]]
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
    """Nested parse result for a single file.

    This structure is recursive - ZIP files contain children,
    each of which can have their own nested results.
    """

    file_name: str = Field(description="Original filename")
    file_type: str = Field(description="MIME type")
    file_size_bytes: int = Field(description="File size in bytes")
    parse_duration_ms: int = Field(description="Parse duration in milliseconds")

    storage: ParseStorage = Field(description="Storage location for artifacts")
    content: ParseContent = Field(description="Content statistics")
    quality: ParseQuality = Field(default_factory=ParseQuality, description="Quality assessment")

    warnings: list[str] = Field(default_factory=list, description="Non-fatal warnings")

    # Nested results (e.g., ZIP contains PDFs)
    children: list["ParseResult"] = Field(
        default_factory=list,
        description="Nested parse results for archive contents"
    )

    model_config = ConfigDict(frozen=False)

class ParseJob(BaseModel):
    """Parse job with full lifecycle tracking.

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
    """

    # Job identification
    job_id: UUID = Field(description="Unique job ID")

    # Status tracking
    status: ParseStatus = Field(description="Job status")
    progress: float = Field(ge=0.0, le=1.0, default=0.0, description="Progress (0.0-1.0)")
    message: Optional[str] = Field(default=None, description="Status message")

    # File information
    file_name: str = Field(description="Original file name")
    file_type: str = Field(description="MIME type")
    file_size_bytes: int = Field(description="File size in bytes")

    # Storage configuration
    storage_strategy: StorageStrategy = Field(
        default=StorageStrategy.DATED,
        description="Storage strategy"
    )
    tenant_id: Optional[str] = Field(default=None, description="Tenant ID (if tenant strategy)")

    # Result data
    result: Optional[ParseResult] = Field(default=None, description="Parse result (if completed)")
    error: Optional[ParseError] = Field(default=None, description="Error details (if failed)")

    # Webhook callback
    callback_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for completion notification"
    )

    # Timestamps
    created_at: datetime = Field(description="Job created timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Job started timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Job completed timestamp")
    failed_at: Optional[datetime] = Field(default=None, description="Job failed timestamp")

    # Queue position (for pending jobs)
    position_in_queue: Optional[int] = Field(
        default=None,
        description="Position in queue (pending only)"
    )

    model_config = ConfigDict(frozen=False)

# Enable recursive model
ParseResult.model_rebuild()
```

**Location in codebase:** `percolate-rocks/python/percolate_rocks/parse.py`

**Consumers MUST import from percolate-rocks:**
- ✅ `from percolate_rocks.parse import ParseJob`
- ❌ DO NOT duplicate models in other packages

## REM integration

### File resource status

Extend file resources with parse job tracking:

```python
from enum import Enum

class FileStatus(str, Enum):
    """File resource status in REM."""
    REGISTERED = "registered"      # Metadata stored, not parsed yet
    PARSING = "parsing"             # Parse job in progress
    PARSED = "parsed"               # Parsed, artifacts available
    INGESTED = "ingested"           # Indexed and searchable
    FAILED = "failed"               # Parse or ingest failed

class FileResource(BaseModel):
    """File resource with parse tracking.

    **Multi-provider merge strategy:**

    When using multiple parsing providers (e.g., Kreuzberg for semantic,
    Claude Vision for verification, custom OCR), use the `parsing_data`
    field to store results from each provider separately. This allows:

    1. Keeping all parse results in a single row
    2. Comparing outputs from different providers
    3. Merging best results from multiple providers
    4. Tracking provider performance over time

    Example:
        {
            "uri": "file://doc.pdf",
            "parsing_data": {
                "kreuzberg": {
                    "provider": "kreuzberg",
                    "parsed_at": "2025-10-25T10:30:00Z",
                    "quality_score": 0.85,
                    "artifacts": {"md": "path/to/structured.md"}
                },
                "claude_vision": {
                    "provider": "claude_vision",
                    "parsed_at": "2025-10-25T10:35:00Z",
                    "quality_score": 0.95,
                    "artifacts": {"verified_tables": ["table_0.md"]}
                }
            }
        }
    """

    name: str = Field(description="File name")
    uri: str = Field(description="Source URI (local path, S3, HTTP)")
    content_type: str = Field(description="MIME type")
    size_bytes: int = Field(description="File size")

    status: FileStatus = Field(default=FileStatus.REGISTERED)
    parse_job_uri: Optional[str] = Field(
        default=None,
        description="Parse job status URI (e.g., http://parser.local/v1/parse/job-id)"
    )

    parsing_data: dict[str, dict] = Field(
        default_factory=dict,
        description="Parse results from each provider (provider_name → result)"
    )

    parsed_at: Optional[datetime] = Field(default=None)
    ingested_at: Optional[datetime] = Field(default=None)

    model_config = ConfigDict(
        json_schema_extra={
            "name": "rem.resources.FileResource",
            "short_name": "files",
            "indexed_fields": ["status", "content_type"],
            "key_field": "uri"
        }
    )
```

### Job entity type

Introduce a generic `Job` entity for async operations:

```python
class JobCategory(str, Enum):
    """Job category."""
    PARSING = "parsing"
    EMBEDDING = "embedding"
    EXPORT = "export"
    REPLICATION = "replication"

class JobSpec(BaseModel):
    """Job specification (input parameters)."""

    category: JobCategory
    provider_uri: str = Field(description="Provider API base URI")
    parameters: dict = Field(description="Job-specific parameters")

class Job(BaseModel):
    """Generic async job entity."""

    name: str = Field(description="Job name")
    category: JobCategory = Field(description="Job category")
    status: str = Field(description="Job status (provider-specific)")

    spec: JobSpec = Field(description="Job specification")
    status_uri: str = Field(description="Job status URI (provider-specific)")

    result: Optional[dict] = Field(default=None, description="Job result (if completed)")
    error: Optional[dict] = Field(default=None, description="Error details (if failed)")

    model_config = ConfigDict(
        json_schema_extra={
            "name": "rem.jobs.Job",
            "short_name": "jobs",
            "indexed_fields": ["category", "status"]
        }
    )
```

## CLI commands

### Parse command

```bash
# Submit parse job (file as positional argument)
rem parse report.pdf --provider http://parser.local

# Output:
# Job submitted: 550e8400-e29b-41d4-a716-446655440000
# Status URI: http://parser.local/v1/parse/550e8400-e29b-41d4-a716-446655440000
# File registered: files/550e8400-e29b-41d4-a716-446655440000

# Check job status (explicit 'status' subcommand)
rem parse status 550e8400-e29b-41d4-a716-446655440000

# Output:
# Job: 550e8400-e29b-41d4-a716-446655440000
# Status: processing
# Progress: 45%
# Message: Extracting page 3 of 7

# Wait for completion and auto-ingest
rem parse report.pdf --provider http://parser.local --wait --ingest

# Output:
# Job submitted: 550e8400-e29b-41d4-a716-446655440000
# Waiting for completion... (3.4s)
# Parse completed: 7 pages, 2 tables, 2 images
# Ingesting to table: resources
# Ingested 7 chunks with embeddings
```

### Implementation

```rust
// src/parse/mod.rs
use reqwest::Client;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

pub struct ParseClient {
    provider_uri: String,
    client: Client,
}

impl ParseClient {
    pub fn new(provider_uri: String) -> Self {
        Self {
            provider_uri,
            client: Client::new(),
        }
    }

    /// Submit file for parsing
    pub async fn submit(&self, file_path: &str) -> Result<ParseJobResponse> {
        let file = tokio::fs::read(file_path).await?;
        let file_name = std::path::Path::new(file_path)
            .file_name()
            .unwrap()
            .to_str()
            .unwrap();

        let form = reqwest::multipart::Form::new()
            .part("file", reqwest::multipart::Part::bytes(file)
                .file_name(file_name.to_string()));

        let url = format!("{}/v1/parse", self.provider_uri);
        let response = self.client.post(&url)
            .multipart(form)
            .send()
            .await?;

        Ok(response.json::<ParseJobResponse>().await?)
    }

    /// Get job status
    pub async fn status(&self, job_id: Uuid) -> Result<ParseJob> {
        let url = format!("{}/v1/parse/{}", self.provider_uri, job_id);
        let response = self.client.get(&url).send().await?;
        Ok(response.json::<ParseJob>().await?)
    }

    /// Wait for job completion
    pub async fn wait(&self, job_id: Uuid, poll_interval_ms: u64) -> Result<ParseJob> {
        loop {
            let job = self.status(job_id).await?;

            match job.status.as_str() {
                "completed" => return Ok(job),
                "failed" => return Err(ParseError::JobFailed(job.error)),
                _ => {
                    tokio::time::sleep(
                        tokio::time::Duration::from_millis(poll_interval_ms)
                    ).await;
                }
            }
        }
    }
}
```

## Storage conventions

### Local filesystem

```
$P8_HOME/parse-jobs/
├── {job_id}/
│   ├── structured.md           # Primary markdown representation
│   ├── metadata.json           # Parse metadata
│   ├── tables/
│   │   ├── table_0.csv
│   │   └── table_1.csv
│   ├── images/
│   │   ├── image_0.png
│   │   └── image_1.png
│   └── nested/                 # Nested archives
│       └── attachment.zip/
│           └── invoice.pdf/
│               └── structured.md
```

### S3 storage

```
s3://{bucket}/parse-jobs/{tenant_id}/{job_id}/
├── structured.md
├── metadata.json
├── tables/
│   ├── table_0.csv
│   └── table_1.csv
└── images/
    ├── image_0.png
    └── image_1.png
```

## Ingest workflow

```python
# 1. Register file resource
file_resource = FileResource(
    name="report.pdf",
    uri="file:///path/to/report.pdf",
    content_type="application/pdf",
    size_bytes=1048576,
    status=FileStatus.REGISTERED
)
db.insert("files", file_resource.model_dump())

# 2. Submit parse job
parse_client = ParseClient("http://parser.local")
job_response = await parse_client.submit("/path/to/report.pdf")

# 3. Update file resource with job URI
db.update("files", file_resource.id, {
    "status": FileStatus.PARSING,
    "parse_job_uri": job_response.status_uri
})

# 4. Store job entity
job = Job(
    name="Parse report.pdf",
    category=JobCategory.PARSING,
    status="pending",
    spec=JobSpec(
        category=JobCategory.PARSING,
        provider_uri="http://parser.local",
        parameters={"file_path": "/path/to/report.pdf"}
    ),
    status_uri=job_response.status_uri
)
db.insert("jobs", job.model_dump())

# 5. Poll for completion (or use webhook)
job_result = await parse_client.wait(job_response.job_id, poll_interval_ms=1000)

# 6. Update file resource and job
db.update("files", file_resource.id, {
    "status": FileStatus.PARSED,
    "parsed_at": datetime.now()
})
db.update("jobs", job.id, {
    "status": "completed",
    "result": job_result.result.model_dump()
})

# 7. Ingest parsed content (optional)
if job_result.status == "completed":
    # Read structured.md
    structured_md = read_artifact(
        job_result.result.storage.base_path,
        job_result.result.storage.artifacts["structured_md"]
    )

    # Chunk and embed
    chunks = chunk_document(structured_md, chunk_size=500)
    for i, chunk in enumerate(chunks):
        resource = Resource(
            name=f"{file_resource.name} (chunk {i})",
            content=chunk,
            uri=file_resource.uri,
            chunk_ordinal=i,
            source_file_id=file_resource.id
        )
        db.insert("resources", resource.model_dump())

    # Mark as ingested
    db.update("files", file_resource.id, {
        "status": FileStatus.INGESTED,
        "ingested_at": datetime.now()
    })
```

## Provider implementation example

**IMPORTANT:** Parse providers MUST import models from percolate-rocks.

Minimal parse provider using FastAPI:

```python
from fastapi import FastAPI, UploadFile, File, HTTPException
from uuid import uuid4, UUID
from datetime import datetime
import asyncio

# Import protocol models from percolate-rocks (SoT)
from percolate_rocks.parse import (
    ParseJob,
    ParseResult,
    ParseStatus,
    ParseStorage,
    ParseContent,
    ParseQuality,
    ParseError,
    StorageStrategy,
)

app = FastAPI()

# In-memory job store (use RocksDB in production)
jobs: dict[UUID, ParseJob] = {}

@app.post("/v1/parse")
async def submit_parse(file: UploadFile = File(...)):
    job_id = uuid4()

    # Create job using percolate-rocks models
    job = ParseJob(
        job_id=job_id,
        status=ParseStatus.PENDING,
        progress=0.0,
        file_name=file.filename,
        file_type=file.content_type,
        file_size_bytes=0,  # Will be updated
        created_at=datetime.utcnow()
    )
    jobs[job_id] = job

    # Start background task
    asyncio.create_task(parse_file(job_id, file))

    return {
        "job_id": str(job_id),
        "status": "pending",
        "status_uri": f"http://parser.local/v1/parse/{job_id}",
        "websocket_uri": f"ws://parser.local/v1/parse/{job_id}/ws",
        "accepted_at": job.created_at.isoformat()
    }

@app.get("/v1/parse/{job_id}")
async def get_status(job_id: UUID):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

async def parse_file(job_id: UUID, file: UploadFile):
    """Background parsing task."""
    job = jobs[job_id]

    try:
        # Update to processing
        job.status = ParseStatus.PROCESSING
        job.started_at = datetime.utcnow()

        # Actual parsing logic here
        # Read file, extract content, generate artifacts...
        content = await file.read()

        # Create result using percolate-rocks models
        job.result = ParseResult(
            file_name=file.filename,
            file_type=file.content_type,
            file_size_bytes=len(content),
            parse_duration_ms=1000,
            storage=ParseStorage(
                strategy=StorageStrategy.DATED,
                base_path=f".fs/parsed/2025/10/25/{job_id}",
                artifacts={
                    "structured_md": "structured.md",
                    "tables": ["tables/table_0.csv"],
                    "images": ["images/image_0.png"],
                    "metadata": "metadata.json"
                }
            ),
            content=ParseContent(
                text_length=5000,
                num_tables=1,
                num_images=1,
                num_pages=3,
                languages=["en"]
            ),
            quality=ParseQuality(
                overall_score=0.95,
                flags=[]
            )
        )

        # Mark as completed
        job.status = ParseStatus.COMPLETED
        job.progress = 1.0
        job.completed_at = datetime.utcnow()

    except Exception as e:
        # Mark as failed
        job.status = ParseStatus.FAILED
        job.failed_at = datetime.utcnow()
        job.error = ParseError(
            code="PARSE_ERROR",
            message=str(e),
            details=str(e.__class__.__name__)
        )
```

**Key points:**
- Import ALL models from `percolate_rocks.parse`
- DO NOT duplicate model definitions
- Use `UUID` for job_id (not string)
- Follow storage conventions (dated, tenant, system, s3)
- Include quality assessment in results

## Design rationale

### Why external providers?

| Concern | Embedded | External Provider |
|---------|----------|-------------------|
| Dependencies | Heavy (PyMuPDF, pytesseract) | Minimal (HTTP client) |
| Scaling | Single-threaded | Distributed queue |
| GPU support | Complex setup | Cloud provider |
| Cost | Fixed compute | Pay-per-use |

**Decision:** External providers for flexibility. Embedded parser can be a provider.

### Why nested parse results?

ZIP files contain PDFs, which contain tables and images. Flat structure loses this hierarchy.

```json
{
  "file_name": "archive.zip",
  "children": [
    {
      "file_name": "invoice.pdf",
      "children": [
        {
          "file_name": "table_0.csv",
          "content": {...}
        }
      ]
    }
  ]
}
```

### Why job entities?

Parsing is one of many async operations (embedding, export, replication). Generic `Job` entity supports all.

## Future extensions

1. **Webhooks** - Provider calls REM on completion (no polling)
2. **Streaming** - Parse large files incrementally
3. **Multi-provider** - Route by file type (PDFs to Anthropic, code to GitHub)
4. **Caching** - Skip re-parsing unchanged files (content hash)
5. **Priorities** - Queue management for urgent files
