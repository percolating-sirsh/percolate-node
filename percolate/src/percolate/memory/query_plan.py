"""Query plan data models for natural language query translation.

This module defines the structured output format for the query planner agent.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class QueryType(str, Enum):
    """Types of queries supported by REM Database."""

    LOOKUP = "lookup"  # Key-based entity lookup
    SEARCH = "search"  # Semantic vector search
    SQL = "sql"  # Standard SQL SELECT
    TRAVERSE = "traverse"  # Graph traversal
    HYBRID = "hybrid"  # Semantic + SQL filters


class ExecutionMode(str, Enum):
    """Query execution strategies."""

    SINGLE_PASS = "single_pass"  # Execute primary query only
    MULTI_STAGE = "multi_stage"  # Try primary then fallbacks
    ADAPTIVE = "adaptive"  # Adjust strategy based on results


class FallbackTrigger(str, Enum):
    """Conditions that trigger fallback query execution."""

    NO_RESULTS = "no_results"  # Primary query returned empty
    ERROR = "error"  # Primary query failed
    LOW_CONFIDENCE = "low_confidence"  # Confidence below threshold


class QueryDialect(str, Enum):
    """SQL dialect for query execution."""

    REM_SQL = "rem_sql"  # Extended REM dialect (LOOKUP, TRAVERSE, SEARCH)
    STANDARD_SQL = "standard_sql"  # Standard SQL SELECT


class Query(BaseModel):
    """Individual query specification."""

    dialect: QueryDialect = Field(description="SQL dialect to use")
    query_string: str = Field(description="The actual query to execute")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Query parameters"
    )


class FallbackQuery(BaseModel):
    """Fallback query with trigger condition."""

    query: Query = Field(description="The fallback query to execute")
    trigger: FallbackTrigger = Field(
        description="Condition that triggers this fallback"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in this fallback query"
    )
    reasoning: str = Field(description="Why this fallback is appropriate")


class QueryMetadata(BaseModel):
    """Additional metadata about query execution."""

    estimated_rows: Optional[int] = Field(
        None, description="Expected number of result rows"
    )
    estimated_time_ms: Optional[int] = Field(
        None, description="Expected execution time in milliseconds"
    )
    requires_embedding: bool = Field(
        False, description="Whether query needs embedding generation"
    )
    uses_index: bool = Field(
        True, description="Whether query can use indexes"
    )
    schemas_searched: list[str] = Field(
        default_factory=list, description="Schemas that will be searched"
    )


class QueryPlan(BaseModel):
    """Complete query execution plan with fallback strategies.

    This is the structured output from the query planner agent.
    """

    query_type: QueryType = Field(description="Primary query type")

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in query correctness (0.0-1.0)",
    )

    primary_query: Query = Field(description="Main query to execute first")

    fallback_queries: list[FallbackQuery] = Field(
        default_factory=list,
        description="Ordered fallback queries if primary fails",
    )

    execution_mode: ExecutionMode = Field(
        description="How to execute this query plan"
    )

    schema_hints: list[str] = Field(
        default_factory=list,
        description="Suggested schemas to search (in priority order)",
    )

    reasoning: str = Field(
        description="Explanation of query plan decisions"
    )

    explanation: Optional[str] = Field(
        None,
        description="Required for low confidence (<0.6) - why query is ambiguous",
    )

    next_steps: list[str] = Field(
        default_factory=list,
        description="Suggestions if query fails or returns no results",
    )

    metadata: QueryMetadata = Field(
        default_factory=QueryMetadata,
        description="Additional query metadata",
    )

    @model_validator(mode="after")
    def explanation_required_for_low_confidence(self) -> "QueryPlan":
        """Ensure explanation is provided when confidence is low."""
        if self.confidence < 0.6 and not self.explanation:
            raise ValueError(
                f"Explanation required for low confidence ({self.confidence:.2f})"
            )
        return self


class QueryResult(BaseModel):
    """Result of query execution with metadata."""

    results: list[dict[str, Any]] = Field(
        description="Query results (entities)"
    )

    query: str = Field(description="Executed query string")

    query_type: QueryType = Field(description="Type of query executed")

    confidence: float = Field(
        ge=0.0, le=1.0, description="Query confidence score"
    )

    stages: int = Field(
        default=1, description="Number of stages executed"
    )

    stage_results: list[int] = Field(
        default_factory=list,
        description="Result counts per stage (for multi-stage)",
    )

    total_time_ms: int = Field(
        description="Total execution time in milliseconds"
    )

    execution_mode: ExecutionMode = Field(
        description="Execution mode used"
    )

    reasoning: Optional[str] = Field(
        None, description="Explanation of results"
    )

    fallback_used: bool = Field(
        default=False, description="Whether fallback query was used"
    )


class QueryIntent(BaseModel):
    """Detected intent from natural language query.

    This is an intermediate representation before generating the full QueryPlan.
    """

    query_type: QueryType = Field(description="Detected query type")

    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in intent detection"
    )

    entities: list[str] = Field(
        default_factory=list, description="Detected entity references"
    )

    schemas: list[str] = Field(
        default_factory=list, description="Detected schema references"
    )

    filters: dict[str, Any] = Field(
        default_factory=dict, description="Detected filter conditions"
    )

    semantic_query: Optional[str] = Field(
        None, description="Extracted semantic search query"
    )

    time_range: Optional[tuple[datetime, datetime]] = Field(
        None, description="Detected time range filter"
    )

    relationships: list[str] = Field(
        default_factory=list, description="Detected relationship types"
    )

    is_ambiguous: bool = Field(
        default=False, description="Whether query is ambiguous"
    )

    ambiguity_reasons: list[str] = Field(
        default_factory=list, description="Why query is ambiguous"
    )
