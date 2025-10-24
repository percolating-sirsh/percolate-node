"""Data models for REM database."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Get current UTC time with timezone."""
    return datetime.now(UTC)


class SystemFields(BaseModel):
    """System-managed fields for all entities.

    All tables inherit these fields automatically.
    """

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: str}
    )

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    created_at: datetime = Field(default_factory=utc_now, description="Creation timestamp")
    modified_at: datetime = Field(default_factory=utc_now, description="Last modification timestamp")
    deleted_at: Optional[datetime] = Field(None, description="Soft delete timestamp")
    edges: list[str] = Field(
        default_factory=list,
        description="Graph edges (other entity IDs or qualified keys)"
    )


class Resource(SystemFields):
    """Chunked, embedded content from documents.

    Used for general-purpose document storage with vector embeddings.
    Supports flexible schema via properties dict.
    """

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: str},
        json_schema_extra={
            "fully_qualified_name": "rem.system.Resource",
            "short_name": "resource",
            "version": "1.0.0",
            "indexed_fields": ["category", "name"],
            "category": "system",
            "embedding_provider": "all-MiniLM-L6-v2",
            "embedding_provider_alt": "all-mpnet-base-v2"
        }
    )

    name: str = Field(description="Resource name or title")
    content: str = Field(description="Full text content (auto-embedded)")
    category: Optional[str] = Field(None, description="Resource category/type")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata")
    embedding: Optional[list[float]] = Field(None, description="Vector embedding (384-dim from all-MiniLM-L6-v2)")
    embedding_alt: Optional[list[float]] = Field(None, description="Alternative vector embedding (768-dim from all-mpnet-base-v2)")
    ordinal: Optional[int] = Field(None, description="Ordering within category")
    uri: Optional[str] = Field(None, description="Source URI or reference")


class Entity(SystemFields):
    """Domain knowledge node with properties and relationships.

    Generic entity type for storing typed entities with properties.
    For entities that need embeddings, use properties dict to store
    a 'content' or 'description' field.
    """

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: str}
    )

    type: str = Field(description="Entity type (schema name)")
    name: str = Field(description="Entity name")
    aliases: list[str] = Field(default_factory=list, description="Alternative names")
    properties: dict[str, Any] = Field(default_factory=dict, description="Type-specific properties (can include 'content' for embedding)")
    embedding: Optional[list[float]] = Field(None, description="Vector embedding (default provider)")
    embedding_alt: Optional[list[float]] = Field(None, description="Alternative vector embedding (alt provider)")


class Agent(SystemFields):
    """Agent-let definition with output schema and MCP tools.

    Stores agent-let schemas for trainable AI skills.
    """

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: str},
        json_schema_extra={
            "fully_qualified_name": "rem.system.Agent",
            "short_name": "agent",
            "version": "1.0.0",
            "indexed_fields": ["category", "name"],
            "category": "system",
            "embedding_provider": "all-MiniLM-L6-v2",
            "embedding_provider_alt": "all-mpnet-base-v2"
        }
    )

    name: str = Field(description="Agent name (unique)")
    category: Optional[str] = Field(None, description="Agent category (system, user, public)")
    description: str = Field(description="Agent description/system prompt (auto-embedded)")
    output_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON schema for structured output"
    )
    tools: list[dict[str, Any]] = Field(
        default_factory=list,
        description="MCP tool references [{mcp_server, tool_name, usage}]"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    embedding: Optional[list[float]] = Field(None, description="Vector embedding (384-dim from all-MiniLM-L6-v2)")
    embedding_alt: Optional[list[float]] = Field(None, description="Alternative vector embedding (768-dim from all-mpnet-base-v2)")


class Session(SystemFields):
    """Conversation session for tracking agent interactions.

    Groups related messages and links to cases/projects.
    """

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: str},
        json_schema_extra={
            "fully_qualified_name": "rem.system.Session",
            "short_name": "session",
            "version": "1.0.0",
            "indexed_fields": ["case_id", "agent", "session_type"],
            "category": "system",
            "embedding_provider": "all-MiniLM-L6-v2",
            "embedding_provider_alt": "all-mpnet-base-v2"
        }
    )

    name: Optional[str] = Field(None, description="Session name or title")
    query: str = Field(description="Initial query or prompt (auto-embedded)")
    agent: Optional[str] = Field(None, description="Agent name used in this session")
    case_id: Optional[UUID] = Field(None, description="Related case/project ID")
    parent_session_id: Optional[UUID] = Field(None, description="Parent session for nested conversations")
    session_type: Optional[str] = Field(None, description="Session type (chat, task, eval)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Session metadata")
    session_completed_at: Optional[datetime] = Field(None, description="Session completion timestamp")
    embedding: Optional[list[float]] = Field(None, description="Vector embedding (384-dim from all-MiniLM-L6-v2)")
    embedding_alt: Optional[list[float]] = Field(None, description="Alternative vector embedding (768-dim from all-mpnet-base-v2)")


class Message(SystemFields):
    """Individual message within a session.

    Stores user and assistant messages with tool call tracking.
    """

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: str},
        json_schema_extra={
            "fully_qualified_name": "rem.system.Message",
            "short_name": "message",
            "version": "1.0.0",
            "indexed_fields": ["session_id", "role"],
            "category": "system",
            "embedding_provider": "all-MiniLM-L6-v2",
            "embedding_provider_alt": "all-mpnet-base-v2"
        }
    )

    session_id: UUID = Field(description="Parent session ID")
    role: str = Field(description="Message role (user, assistant, system, tool)")
    content: str = Field(description="Message content (auto-embedded)")
    tool_calls: Optional[list[dict[str, Any]]] = Field(None, description="Tool calls made by assistant")
    trace_id: Optional[str] = Field(None, description="OpenTelemetry trace ID for observability")
    span_id: Optional[str] = Field(None, description="OpenTelemetry span ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Message metadata")
    embedding: Optional[list[float]] = Field(None, description="Vector embedding (384-dim from all-MiniLM-L6-v2)")
    embedding_alt: Optional[list[float]] = Field(None, description="Alternative vector embedding (768-dim from all-mpnet-base-v2)")


class Edge(BaseModel):
    """Relationship between entities."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: str}
    )

    src_id: UUID
    dst_id: UUID
    edge_type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class Moment(BaseModel):
    """Temporal classification of resources and entities."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: str}
    )

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime
    type: str
    classifications: list[str] = Field(default_factory=list)
    resource_refs: list[UUID] = Field(default_factory=list)
    entity_refs: list[UUID] = Field(default_factory=list)
    parent_moment: Optional[UUID] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class Direction(str, Enum):
    """Edge traversal direction."""

    OUTGOING = "outgoing"
    INCOMING = "incoming"
    BOTH = "both"


class Order(str, Enum):
    """Sort order."""

    ASC = "asc"
    DESC = "desc"
