"""Pydantic models for built-in schemas.

Example schemas demonstrating REM patterns (Resources, Entities, Moments).
"""

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class Entity(BaseModel):
    """Base entity with system fields.

    Note: System fields (id, created_at, etc.) are added automatically by Rust.
    Never define these in your Pydantic models.
    """

    # User properties only (no system fields)
    pass


class Resource(BaseModel):
    """Resource schema for chunked documents with embeddings.

    Example of REM "Resource" pattern - chunked documents for semantic search.
    """

    name: str = Field(description="Resource name")
    content: str = Field(description="Resource content")
    uri: str = Field(description="Source URI")
    chunk_ordinal: int = Field(default=0, description="Chunk number (0 for single resources)")

    model_config = ConfigDict(
        json_schema_extra={
            # Embedding configuration (NB: from README - fields can take json_schema_extra)
            "embedding_fields": ["content"],  # Auto-embed on insert
            "embedding_provider": "default",  # Uses P8_DEFAULT_EMBEDDING

            # Indexing configuration
            "indexed_fields": [],  # Resources use vector search, not SQL indexes

            # Key field (NB: Precedence - uri -> key -> name)
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
    author: str | None = Field(default=None, description="Author name")

    model_config = ConfigDict(
        json_schema_extra={
            # Embedding configuration
            "embedding_fields": ["content"],  # Embed content for semantic search
            "embedding_provider": "default",

            # Indexing configuration
            "indexed_fields": ["category"],  # Fast WHERE category = 'programming'

            # Key field
            "key_field": "title",  # Deterministic UUID from title

            # Schema metadata
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
    bio: str | None = Field(default=None, description="Biography")

    model_config = ConfigDict(
        json_schema_extra={
            # No embeddings - SQL queries only
            "embedding_fields": [],

            # Indexing configuration
            "indexed_fields": ["email", "role"],  # Fast WHERE email = '...'

            # Key field (NB: Precedence - uri -> key -> name)
            "key_field": "email",  # Deterministic UUID from email

            # Schema metadata
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
    description: str | None = Field(default=None, description="Sprint description")

    model_config = ConfigDict(
        json_schema_extra={
            # No embeddings for moments (time-based queries)
            "embedding_fields": [],

            # Indexing configuration for time-range queries
            "indexed_fields": ["start_time", "end_time"],

            # Key field
            "key_field": "name",  # Deterministic UUID from sprint name

            # Schema metadata
            "fully_qualified_name": "rem_db.models.Sprint",
            "short_name": "sprints",
            "version": "1.0.0",
            "category": "user",
            "description": "Sprint temporal classifications",
        }
    )


class Edge(BaseModel):
    """Graph edge model (for reference only - edges managed internally)."""

    src: str = Field(description="Source entity UUID")
    dst: str = Field(description="Destination entity UUID")
    rel_type: str = Field(description="Relationship type")


class SearchResult(BaseModel):
    """Search result with entity and similarity score."""

    entity: dict = Field(description="Matched entity")
    score: float = Field(description="Similarity score")


class QueryPlan(BaseModel):
    """Natural language query plan."""

    intent: str = Field(description="Detected intent (select, search, traverse, aggregate)")
    query: str = Field(description="Generated query (SQL or SEARCH syntax)")
    confidence: float = Field(description="Confidence score (0.0 - 1.0)")
    reasoning: str = Field(description="Reasoning explanation")
    requires_search: bool = Field(description="Whether semantic search is required")
    parameters: dict = Field(default_factory=dict, description="Suggested parameters")
