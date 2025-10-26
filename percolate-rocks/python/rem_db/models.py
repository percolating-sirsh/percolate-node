"""Pydantic models for REM Database.

All models use Pydantic v2+ semantics with modern best practices (2025).
Includes: Entity schemas, Sessions, Jobs, Replication, Export, and built-in REM patterns.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ====================================================================
# ENUMERATIONS
# ====================================================================


class EntityType(str, Enum):
    """Entity type enumeration."""

    RESOURCE = "resource"
    ENTITY = "entity"
    MOMENT = "moment"
    AGENTLET = "agentlet"


class EmbeddingProvider(str, Enum):
    """Embedding provider types."""

    LOCAL = "local"
    OPENAI = "openai"
    DEFAULT = "default"


class SessionStatus(str, Enum):
    """Session status."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Background job types."""

    EMBEDDING = "embedding"
    INDEXING = "indexing"
    EXPORT = "export"
    BACKUP = "backup"
    REPLICATION = "replication"


class JobStatus(str, Enum):
    """Background job status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExportFormat(str, Enum):
    """Export file formats."""

    JSONL = "jsonl"
    CSV = "csv"
    TSV = "tsv"
    PARQUET = "parquet"


class ReplicationMode(str, Enum):
    """Replication mode."""

    NONE = "none"
    PRIMARY = "primary"
    REPLICA = "replica"


class SchemaCategory(str, Enum):
    """Schema category."""

    SYSTEM = "system"
    USER = "user"


# ====================================================================
# SYSTEM MODELS (automatically managed by database)
# ====================================================================


class SystemFields(BaseModel):
    """System fields automatically added to all entities.

    NEVER define these fields in your Pydantic models - they are injected by the database.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(description="Entity UUID (deterministic or random)")
    entity_type: str = Field(description="Schema/table name")
    created_at: datetime = Field(description="Creation timestamp (ISO 8601)")
    modified_at: datetime = Field(description="Last modification timestamp")
    deleted_at: Optional[datetime] = Field(
        default=None, description="Soft delete timestamp (null if active)"
    )
    edges: list[str] = Field(
        default_factory=list, description="Graph edge references"
    )


class Entity(BaseModel):
    """Core entity with system fields and user properties.

    This is the returned format from database operations.
    When creating entities, only provide the `properties` dict.
    """

    model_config = ConfigDict(
        extra="allow",  # Allow additional fields
        validate_assignment=True,
    )

    system: SystemFields = Field(description="System-managed fields")
    properties: dict[str, Any] = Field(
        default_factory=dict, description="User-defined properties"
    )

    @field_validator("properties", mode="before")
    @classmethod
    def validate_properties(cls, v: Any) -> dict[str, Any]:
        """Ensure properties is a dictionary."""
        if not isinstance(v, dict):
            raise ValueError("properties must be a dictionary")
        return v


class Edge(BaseModel):
    """Graph edge with relationship type and properties."""

    model_config = ConfigDict(validate_assignment=True)

    src_id: UUID = Field(description="Source entity UUID")
    dst_id: UUID = Field(description="Destination entity UUID")
    edge_type: str = Field(description="Relationship type")
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Edge properties"
    )
    created_at: datetime = Field(description="Creation timestamp")
    bidirectional: bool = Field(
        default=True, description="Create reverse edge automatically"
    )


#  ====================================================================
# BUILT-IN REM PATTERNS (Resources, Entities, Moments)
# ====================================================================


class Resource(BaseModel):
    """Resource schema for chunked documents with embeddings.

    Example of REM "Resource" pattern - chunked documents for semantic search.
    """

    name: str = Field(description="Resource name")
    content: str = Field(description="Resource content")
    uri: str = Field(description="Source URI")
    chunk_ordinal: int = Field(
        default=0, description="Chunk number (0 for single resources)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            # Embedding configuration
            "embedding_fields": ["content"],  # Auto-embed on insert
            "embedding_provider": "default",  # Uses P8_DEFAULT_EMBEDDING
            # Indexing configuration
            "indexed_fields": [],  # Resources use vector search, not SQL indexes
            # Key field (Precedence: uri -> key -> name)
            "key_field": "uri",  # Deterministic UUID from URI + chunk_ordinal
            # Schema metadata
            "fully_qualified_name": "rem_db.models.Resource",
            "short_name": "resources",
            "version": "1.0.0",
            "category": "system",
            "description": "Chunked document resources for semantic search",
        }
    )


class Article(BaseModel):
    """Article entity for structured content with embeddings.

    Example of REM "Entity" pattern - structured data with semantic search.
    """

    title: str = Field(description="Article title")
    content: str = Field(description="Full article content")
    category: str = Field(description="Content category")
    tags: list[str] = Field(default_factory=list, description="Article tags")
    author: Optional[str] = Field(default=None, description="Author name")

    model_config = ConfigDict(
        json_schema_extra={
            "embedding_fields": ["content"],
            "embedding_provider": "default",
            "indexed_fields": ["category"],
            "key_field": "title",
            "fully_qualified_name": "rem_db.models.Article",
            "short_name": "articles",
            "version": "1.0.0",
            "category": "user",
            "description": "Technical articles and tutorials",
        }
    )


class Person(BaseModel):
    """Person entity for structured data without embeddings.

    Example of REM "Entity" pattern - structured data with SQL queries only.
    """

    name: str = Field(description="Person name")
    email: str = Field(description="Email address")
    role: str = Field(description="Role/title")
    bio: Optional[str] = Field(default=None, description="Biography")

    model_config = ConfigDict(
        json_schema_extra={
            "embedding_fields": [],
            "indexed_fields": ["email", "role"],
            "key_field": "email",
            "fully_qualified_name": "rem_db.models.Person",
            "short_name": "people",
            "version": "1.0.0",
            "category": "user",
            "description": "People and users",
        }
    )


class Sprint(BaseModel):
    """Sprint moment for temporal classifications.

    Example of REM "Moment" pattern - temporal classifications with time-range queries.
    """

    name: str = Field(description="Sprint name")
    start_time: datetime = Field(description="Sprint start timestamp")
    end_time: datetime = Field(description="Sprint end timestamp")
    classifications: list[str] = Field(
        default_factory=list, description="Classification tags"
    )
    description: Optional[str] = Field(default=None, description="Sprint description")

    model_config = ConfigDict(
        json_schema_extra={
            "embedding_fields": [],
            "indexed_fields": ["start_time", "end_time"],
            "key_field": "name",
            "fully_qualified_name": "rem_db.models.Sprint",
            "short_name": "sprints",
            "version": "1.0.0",
            "category": "user",
            "description": "Sprint temporal classifications",
        }
    )


# ====================================================================
# AGENT-LET MODELS
# ====================================================================


class MCPToolConfig(BaseModel):
    """MCP tool configuration."""

    model_config = ConfigDict(validate_assignment=True)

    mcp_server: str = Field(description="MCP server name (e.g., 'carrier')")
    tool_name: str = Field(description="Tool name (e.g., 'search_knowledge_base')")
    usage: Optional[str] = Field(
        default=None, description="Usage description for the agent"
    )


class MCPResourceConfig(BaseModel):
    """MCP resource configuration."""

    model_config = ConfigDict(validate_assignment=True)

    uri: str = Field(description="Resource URI (e.g., 'cda://field-definitions')")
    usage: Optional[str] = Field(
        default=None, description="Usage description for the agent"
    )


class AgentletSchema(BaseModel):
    """Agent-let JSON Schema definition."""

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "embedding_fields": ["description"],
            "embedding_provider": "default",
            "indexed_fields": ["short_name", "version"],
            "key_field": "name",
            "category": "system",
        },
    )

    title: str = Field(description="Agent title")
    name: str = Field(
        description="Fully qualified agent name (e.g., 'carrier.agents.cda_mapper')"
    )
    short_name: str = Field(description="Short name for CLI/API")
    version: str = Field(description="Semantic version")
    description: str = Field(description="System prompt / agent description")

    # MCP configuration
    tools: list[MCPToolConfig] = Field(
        default_factory=list, description="MCP tools available to agent"
    )
    resources: list[MCPResourceConfig] = Field(
        default_factory=list, description="MCP resources available to agent"
    )

    # Output schema
    output_schema: dict[str, Any] = Field(
        description="JSON Schema for structured output"
    )


# ====================================================================
# QUERY MODELS
# ====================================================================


class QueryPlan(BaseModel):
    """Natural language query execution plan."""

    model_config = ConfigDict(validate_assignment=True)

    intent: str = Field(
        description="Detected intent (select, search, traverse, aggregate)"
    )
    query: str = Field(description="Generated query (SQL or SEARCH syntax)")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    reasoning: str = Field(description="Reasoning explanation")
    requires_search: bool = Field(description="Whether semantic search is required")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Suggested parameters"
    )


class SearchResult(BaseModel):
    """Vector search result with similarity score."""

    model_config = ConfigDict(validate_assignment=True)

    entity: dict[str, Any] = Field(description="Matched entity (as dict)")
    score: float = Field(ge=0.0, le=1.0, description="Similarity score (0-1)")
    distance: Optional[float] = Field(default=None, description="Vector distance")


# ====================================================================
# SESSION MODELS
# ====================================================================


class Session(BaseModel):
    """User session for tracking work."""

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "indexed_fields": ["status", "user_id", "created_at"],
            "category": "system",
        },
    )

    session_id: UUID = Field(description="Session UUID")
    user_id: str = Field(description="User identifier")
    tenant_id: str = Field(description="Tenant identifier")
    status: SessionStatus = Field(description="Session status")
    created_at: datetime = Field(description="Session start time")
    updated_at: datetime = Field(description="Last update time")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Session metadata"
    )


# ====================================================================
# CHAT SESSION MODELS (for percolate chat API)
# ====================================================================


class ChatSession(BaseModel):
    """Conversation session metadata for chat completions.

    Schema defined in percolate-rocks/src/schema/builtin.rs (sessions_table_schema).
    """

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "embedding_fields": [],
            "indexed_fields": ["tenant_id", "agent_uri", "updated_at"],
            "key_field": "session_id",
            "category": "system",
            "fully_qualified_name": "percolate.memory.ChatSession",
            "short_name": "sessions",
            "version": "1.0.0",
        },
    )

    session_id: str = Field(description="Unique session identifier")
    tenant_id: str = Field(description="Tenant scope for isolation")
    agent_uri: Optional[str] = Field(default=None, description="Agent used in session")
    message_count: int = Field(default=0, description="Number of messages")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    created_at: datetime = Field(description="Session creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class ChatMessage(BaseModel):
    """Individual message in a chat conversation.

    Schema defined in percolate-rocks/src/schema/builtin.rs (messages_table_schema).
    """

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "embedding_fields": ["content"],
            "indexed_fields": ["session_id", "tenant_id", "role", "timestamp"],
            "key_field": "message_id",
            "category": "system",
            "fully_qualified_name": "percolate.memory.ChatMessage",
            "short_name": "messages",
            "version": "1.0.0",
        },
    )

    message_id: str = Field(description="Unique message identifier (UUID)")
    session_id: str = Field(description="Parent session identifier")
    tenant_id: str = Field(description="Tenant scope for isolation")
    role: str = Field(description="Message role: user, assistant, or system")
    content: str = Field(description="Message content")
    model: Optional[str] = Field(default=None, description="Model that generated response")
    timestamp: datetime = Field(description="Message timestamp")
    usage: Optional[dict[str, int]] = Field(
        default=None, description="Token usage metrics"
    )
    trace_id: Optional[str] = Field(default=None, description="OTEL trace ID (hex, 32 chars)")
    span_id: Optional[str] = Field(default=None, description="OTEL span ID (hex, 16 chars)")


class ChatFeedback(BaseModel):
    """User feedback on chat interactions.

    Schema defined in percolate-rocks/src/schema/builtin.rs (feedback_table_schema).
    """

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "embedding_fields": ["feedback_text"],
            "indexed_fields": ["session_id", "message_id", "trace_id", "label", "timestamp"],
            "key_field": "feedback_id",
            "category": "system",
            "fully_qualified_name": "percolate.memory.ChatFeedback",
            "short_name": "feedback",
            "version": "1.0.0",
        },
    )

    feedback_id: str = Field(description="Unique feedback identifier (UUID)")
    session_id: str = Field(description="Parent session identifier")
    message_id: Optional[str] = Field(
        default=None, description="Specific message being rated"
    )
    tenant_id: str = Field(description="Tenant scope for isolation")
    trace_id: Optional[str] = Field(default=None, description="OTEL trace ID for linking")
    span_id: Optional[str] = Field(default=None, description="OTEL span ID for linking")
    label: Optional[str] = Field(
        default=None,
        description="Feedback label (any string, e.g., 'thumbs_up', 'helpful')",
    )
    score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Feedback score between 0 and 1 (0=negative, 1=positive)",
    )
    feedback_text: Optional[str] = Field(
        default=None, description="Optional feedback comment"
    )
    user_id: Optional[str] = Field(default=None, description="User providing feedback")
    timestamp: datetime = Field(description="Feedback timestamp")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


# ====================================================================
# JOB MODELS (for async operations)
# ====================================================================


class Job(BaseModel):
    """Background job tracking."""

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "indexed_fields": ["status", "job_type", "created_at"],
            "category": "system",
        },
    )

    job_id: UUID = Field(description="Job UUID")
    job_type: JobType = Field(description="Type of job")
    status: JobStatus = Field(description="Current status")
    tenant_id: str = Field(description="Tenant identifier")
    created_at: datetime = Field(description="Job creation time")
    started_at: Optional[datetime] = Field(default=None, description="Job start time")
    completed_at: Optional[datetime] = Field(
        default=None, description="Job completion time"
    )
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Progress (0-1)")
    total_items: Optional[int] = Field(
        default=None, description="Total items to process"
    )
    processed_items: int = Field(default=0, description="Items processed")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    result: Optional[dict[str, Any]] = Field(
        default=None, description="Job result data"
    )


# ====================================================================
# EXPORT MODELS
# ====================================================================


class ExportConfig(BaseModel):
    """Export operation configuration."""

    model_config = ConfigDict(validate_assignment=True)

    format: ExportFormat = Field(description="Output format")
    output_path: str = Field(description="Output file path")
    table: Optional[str] = Field(default=None, description="Specific table to export")
    include_deleted: bool = Field(
        default=False, description="Include soft-deleted entities"
    )
    compression: Optional[str] = Field(
        default="zstd", description="Compression algorithm (parquet only)"
    )


# ====================================================================
# REPLICATION MODELS
# ====================================================================


class ReplicationStatus(BaseModel):
    """Replication status information."""

    model_config = ConfigDict(validate_assignment=True)

    mode: ReplicationMode = Field(description="Replication mode")
    lag_ms: Optional[int] = Field(
        default=None, description="Replication lag in milliseconds"
    )
    last_sync: Optional[datetime] = Field(
        default=None, description="Last sync timestamp"
    )
    wal_position: Optional[int] = Field(default=None, description="WAL sequence number")
    connected: bool = Field(default=False, description="Connection status")


class WalEntry(BaseModel):
    """Write-Ahead Log entry."""

    model_config = ConfigDict(validate_assignment=True, frozen=True)

    sequence: int = Field(description="WAL sequence number")
    tenant_id: str = Field(description="Tenant identifier")
    operation: str = Field(description="Operation type (insert/update/delete)")
    entity_type: str = Field(description="Entity type")
    entity_id: UUID = Field(description="Entity UUID")
    timestamp: datetime = Field(description="Operation timestamp")
    data: Optional[dict[str, Any]] = Field(default=None, description="Operation data")


class WalStatus(BaseModel):
    """Write-Ahead Log status."""

    model_config = ConfigDict(validate_assignment=True)

    current_sequence: int = Field(description="Current WAL sequence")
    total_entries: int = Field(description="Total WAL entries")
    size_bytes: int = Field(description="WAL size in bytes")
    oldest_entry: Optional[datetime] = Field(
        default=None, description="Oldest entry timestamp"
    )
    newest_entry: Optional[datetime] = Field(
        default=None, description="Newest entry timestamp"
    )


# ====================================================================
# SCHEMA MODELS
# ====================================================================


class SchemaInfo(BaseModel):
    """Schema metadata information."""

    model_config = ConfigDict(validate_assignment=True)

    name: str = Field(description="Schema name")
    short_name: str = Field(description="Short table name")
    version: str = Field(description="Schema version")
    category: SchemaCategory = Field(description="System or user schema")
    indexed_fields: list[str] = Field(
        default_factory=list, description="Indexed fields"
    )
    embedding_fields: list[str] = Field(
        default_factory=list, description="Fields with embeddings"
    )
    key_field: Optional[str] = Field(
        default=None, description="Deterministic UUID key field"
    )
    entity_count: int = Field(default=0, description="Number of entities")
