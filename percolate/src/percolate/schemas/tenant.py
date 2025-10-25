"""Tenant context model for gateway coordination.

The TenantContext is stored in S3 at `/tenants/<tenant_id>/context.yaml`
and provides fast lookup for distributed REM nodes, recent activity, and
tenant account status.

GDPR Compliance:
- No PII stored (no email, name, phone)
- Only stable tenant_id and tier/status
- Personal details stored in encrypted REM database only
"""

from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ResourceQuotas(BaseModel):
    """Resource quotas for tenant tier."""

    storage_gb: int = Field(description="Storage quota in GB")
    api_calls_per_day: int = Field(description="API calls per day limit")
    max_sessions: int = Field(
        default=1000, description="Maximum concurrent sessions"
    )
    max_parse_jobs_per_hour: int = Field(
        default=100, description="Parse jobs per hour limit"
    )

    model_config = ConfigDict(frozen=True)


class ParseJobStatus(BaseModel):
    """Parse job tracking entry."""

    job_id: str = Field(description="Parse job identifier")
    status: Literal["pending", "processing", "completed", "failed"] = Field(
        description="Job status"
    )
    created_at: datetime = Field(description="Job creation timestamp")
    completed_at: Optional[datetime] = Field(
        default=None, description="Job completion timestamp"
    )


class TenantScratchpad(BaseModel):
    """Tenant scratchpad for informal notes and task tracking.

    Provides a lightweight workspace for tenant-specific context that doesn't
    fit elsewhere. Useful for tracking ongoing work, reminders, and loose notes.
    """

    todos: list[str] = Field(
        default_factory=list,
        description="Informal todo items (not a formal task system)",
    )

    notes: list[str] = Field(
        default_factory=list,
        description="Freeform notes and reminders",
    )

    model_config = ConfigDict(frozen=False)


class TenantContext(BaseModel):
    """Tenant context blob for gateway coordination.

    Stored at: s3://<bucket>/tenants/<tenant_id>/context.yaml

    IMPORTANT: Server MUST encrypt this YAML file using server-managed keys
    (ChaCha20-Poly1305 AEAD) before storing in S3. This protects tenant metadata
    including scratchpad notes, session IDs, and infrastructure details.

    Encryption:
    - Algorithm: ChaCha20-Poly1305 AEAD
    - Key management: Server-side keys (not tenant keys)
    - Nonce: Random per write, stored as prefix in encrypted blob
    - Format: [24-byte nonce][encrypted YAML][16-byte auth tag]

    This context provides fast lookup for:
    - Distributed REM node addresses (peer list)
    - Recent conversation sessions
    - Recent parse job status
    - Tenant tier and account status (no PII)
    - Resource quotas
    - Scratchpad for informal todos and notes

    Tenant deletion protocol:
    1. Remove context entry from S3
    2. Delete RocksDB from each peer node
    3. Remove S3 tenant folder (backups, archives)
    4. Audit log entry for compliance

    Example:
        >>> context = TenantContext(
        ...     tenant_id="tenant_12345678",
        ...     tier="premium",
        ...     account_status="active",
        ...     peer_nodes=["node-1.percolationlabs.ai:9000"],
        ...     recent_sessions=["session_abc123"],
        ...     quotas=ResourceQuotas(
        ...         storage_gb=100,
        ...         api_calls_per_day=10000
        ...     ),
        ...     scratchpad=TenantScratchpad(
        ...         todos=["Review API usage patterns", "Set up monitoring"],
        ...         notes=["Using Claude for doc processing"]
        ...     )
        ... )
    """

    # Tenant identification
    tenant_id: str = Field(description="Tenant identifier (no PII)")

    # Account status
    tier: Literal["premium", "standard", "free"] = Field(
        description="Tenant tier (determines quotas and SLA)"
    )

    account_status: Literal["active", "suspended", "deleted"] = Field(
        description="Account status"
    )

    # Distributed REM nodes
    peer_nodes: list[str] = Field(
        default_factory=list,
        description="REM node addresses (host:port for gRPC)",
    )

    # Recent activity for fast lookups
    recent_sessions: list[str] = Field(
        default_factory=list,
        description="Recent session IDs (last N sessions)",
        max_length=100,
    )

    recent_parse_jobs: list[ParseJobStatus] = Field(
        default_factory=list,
        description="Recent parse jobs (last N jobs)",
        max_length=50,
    )

    # Resource quotas
    quotas: ResourceQuotas = Field(
        description="Resource quotas for tenant tier"
    )

    # Scratchpad for informal notes and todos
    scratchpad: TenantScratchpad = Field(
        default_factory=TenantScratchpad,
        description="Informal workspace for todos and notes",
    )

    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Tenant creation timestamp",
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp",
    )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "tenant_id": "tenant_12345678",
                    "tier": "premium",
                    "account_status": "active",
                    "peer_nodes": [
                        "node-1.percolationlabs.ai:9000",
                        "node-2.percolationlabs.ai:9000",
                    ],
                    "recent_sessions": ["session_abc123", "session_def456"],
                    "recent_parse_jobs": [
                        {
                            "job_id": "parse-job-xyz789",
                            "status": "completed",
                            "created_at": "2024-01-15T10:30:00Z",
                            "completed_at": "2024-01-15T10:31:00Z",
                        }
                    ],
                    "quotas": {
                        "storage_gb": 100,
                        "api_calls_per_day": 10000,
                        "max_sessions": 1000,
                        "max_parse_jobs_per_hour": 100,
                    },
                    "scratchpad": {
                        "todos": [
                            "Review Q4 API usage patterns",
                            "Set up monitoring alerts for storage quota"
                        ],
                        "notes": [
                            "Using Claude for PDF document processing",
                            "Migrated from node-3 to node-2 on 2024-01-10"
                        ]
                    },
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-15T10:30:00Z",
                }
            ]
        },
    )
