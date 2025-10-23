"""Data models for REM database."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Get current UTC time with timezone."""
    return datetime.now(UTC)


class Resource(BaseModel):
    """Chunked, embedded content from documents."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: str}
    )

    id: UUID = Field(default_factory=uuid4)
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class Entity(BaseModel):
    """Domain knowledge node with properties and relationships."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: str}
    )

    id: UUID = Field(default_factory=uuid4)
    type: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


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
