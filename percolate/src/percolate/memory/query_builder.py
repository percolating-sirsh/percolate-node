"""Query builder: Translates QueryPlan parameters to executable REM SQL.

This module provides the translation layer between LLM-generated query plans
and executable database queries. The LLM generates PARAMETERS (what to query),
and QueryBuilder generates SYNTAX (how to query).

Design principles:
- Generic: No hard-coded query generation
- Extensible: Easy to add new query types
- Type-safe: Pydantic validation of parameters
- Testable: Pure functions, no side effects
"""

from typing import Any, Protocol

from pydantic import BaseModel, Field

from percolate.memory.query_plan import Query, QueryDialect, QueryType


class QueryParameters(BaseModel):
    """Base class for query parameters."""

    pass


class LookupParameters(BaseModel):
    """Parameters for LOOKUP queries."""

    keys: list[str] = Field(description="Keys to lookup")
    search_all_schemas: bool = Field(
        default=False, description="Search across all schemas"
    )


class SearchParameters(BaseModel):
    """Parameters for SEARCH queries."""

    query_text: str = Field(description="Semantic search query")
    schema: str = Field(description="Target schema/table")
    top_k: int = Field(default=10, description="Maximum results")
    filters: dict[str, Any] = Field(
        default_factory=dict, description="SQL WHERE filters"
    )


class TraverseParameters(BaseModel):
    """Parameters for TRAVERSE queries."""

    start_key: str | None = Field(
        None, description="Starting entity key (for lookup)"
    )
    start_uuid: str | None = Field(
        None, description="Starting entity UUID"
    )
    depth: int = Field(ge=1, le=10, description="Traversal depth")
    direction: str = Field(
        description="Traversal direction: in, out, both"
    )
    edge_type: str | None = Field(
        None, description="Filter by relationship type"
    )


class SQLParameters(BaseModel):
    """Parameters for SQL SELECT queries."""

    schema: str = Field(description="Target schema/table")
    fields: list[str] = Field(
        default_factory=lambda: ["*"], description="Fields to select"
    )
    where: dict[str, Any] = Field(
        default_factory=dict, description="WHERE conditions"
    )
    order_by: str | None = Field(None, description="ORDER BY field")
    direction: str = Field(default="ASC", description="Sort direction")
    limit: int | None = Field(None, description="Result limit")


class HybridParameters(BaseModel):
    """Parameters for hybrid semantic + SQL queries."""

    query_text: str = Field(description="Semantic search query")
    schema: str = Field(description="Target schema/table")
    top_k: int = Field(default=10, description="Maximum results")
    filters: dict[str, Any] = Field(
        default_factory=dict, description="SQL WHERE filters"
    )
    order_by: str | None = Field(None, description="ORDER BY field")


class QueryBuilder:
    """Translates QueryPlan parameters to executable REM SQL.

    This is the translation layer between LLM planning and database execution.
    The LLM generates WHAT to query (parameters), QueryBuilder generates HOW
    to query (syntax).

    Example:
        >>> builder = QueryBuilder()
        >>> params = {"keys": ["alice", "bob"]}
        >>> query = builder.build_lookup(params)
        >>> print(query)
        "LOOKUP 'alice', 'bob'"
    """

    def build(self, query_type: QueryType, parameters: dict[str, Any]) -> str:
        """Build executable query from type and parameters.

        Args:
            query_type: Type of query to build
            parameters: Query parameters (validated by Pydantic)

        Returns:
            Executable REM SQL query string

        Raises:
            ValueError: If query type is unsupported
        """
        if query_type == QueryType.LOOKUP:
            params = LookupParameters(**parameters)
            return self.build_lookup(params)
        elif query_type == QueryType.SEARCH:
            params = SearchParameters(**parameters)
            return self.build_search(params)
        elif query_type == QueryType.TRAVERSE:
            params = TraverseParameters(**parameters)
            return self.build_traverse(params)
        elif query_type == QueryType.SQL:
            params = SQLParameters(**parameters)
            return self.build_sql(params)
        elif query_type == QueryType.HYBRID:
            params = HybridParameters(**parameters)
            return self.build_hybrid(params)
        else:
            raise ValueError(f"Unsupported query type: {query_type}")

    def build_lookup(self, params: LookupParameters) -> str:
        """Build LOOKUP query.

        Args:
            params: Lookup parameters

        Returns:
            LOOKUP 'key1', 'key2', ...

        Example:
            >>> params = LookupParameters(keys=["alice", "bob"])
            >>> builder.build_lookup(params)
            "LOOKUP 'alice', 'bob'"
        """
        keys_str = ", ".join(f"'{key}'" for key in params.keys)
        return f"LOOKUP {keys_str}"

    def build_search(self, params: SearchParameters) -> str:
        """Build SEARCH query.

        Args:
            params: Search parameters

        Returns:
            SEARCH 'query' IN schema [WHERE ...] LIMIT n

        Example:
            >>> params = SearchParameters(
            ...     query_text="indoor plants",
            ...     schema="resources",
            ...     top_k=10
            ... )
            >>> builder.build_search(params)
            "SEARCH 'indoor plants' IN resources LIMIT 10"
        """
        query = f"SEARCH '{params.query_text}' IN {params.schema}"

        if params.filters:
            where_clauses = self._build_where_clauses(params.filters)
            query += f" WHERE {where_clauses}"

        query += f" LIMIT {params.top_k}"
        return query

    def build_traverse(self, params: TraverseParameters) -> str:
        """Build TRAVERSE query.

        Args:
            params: Traverse parameters

        Returns:
            Multi-line query with LOOKUP (if needed) + TRAVERSE

        Example:
            >>> params = TraverseParameters(
            ...     start_key="alice",
            ...     depth=1,
            ...     direction="out",
            ...     edge_type="colleague"
            ... )
            >>> builder.build_traverse(params)
            "-- Stage 1: Find Alice\\nLOOKUP 'alice'\\n-- Stage 2: Traverse colleagues\\nTRAVERSE FROM <alice_uuid> DEPTH 1 DIRECTION out TYPE 'colleague'"
        """
        query_parts = []

        # Stage 1: Lookup start entity if key provided
        if params.start_key:
            query_parts.append(f"-- Stage 1: Find {params.start_key}")
            query_parts.append(f"LOOKUP '{params.start_key}'")
            query_parts.append(
                f"-- Stage 2: Traverse {params.edge_type or 'relationships'}"
            )
            start_ref = f"<{params.start_key}_uuid>"
        elif params.start_uuid:
            start_ref = f"'{params.start_uuid}'"
        else:
            raise ValueError(
                "Either start_key or start_uuid must be provided"
            )

        # Stage 2: Traverse from start entity
        traverse_query = (
            f"TRAVERSE FROM {start_ref} "
            f"DEPTH {params.depth} "
            f"DIRECTION {params.direction}"
        )

        if params.edge_type:
            traverse_query += f" TYPE '{params.edge_type}'"

        query_parts.append(traverse_query)
        return "\n".join(query_parts)

    def build_sql(self, params: SQLParameters) -> str:
        """Build SQL SELECT query.

        Args:
            params: SQL parameters

        Returns:
            SELECT ... FROM schema [WHERE ...] [ORDER BY ...] [LIMIT n]

        Example:
            >>> params = SQLParameters(
            ...     schema="articles",
            ...     fields=["name", "category"],
            ...     where={"category": "programming"},
            ...     limit=10
            ... )
            >>> builder.build_sql(params)
            "SELECT name, category FROM articles WHERE category = 'programming' LIMIT 10"
        """
        fields_str = ", ".join(params.fields)
        query = f"SELECT {fields_str} FROM {params.schema}"

        if params.where:
            where_clauses = self._build_where_clauses(params.where)
            query += f" WHERE {where_clauses}"

        if params.order_by:
            query += f" ORDER BY {params.order_by} {params.direction}"

        if params.limit:
            query += f" LIMIT {params.limit}"

        return query

    def build_hybrid(self, params: HybridParameters) -> str:
        """Build hybrid semantic + SQL query.

        Args:
            params: Hybrid query parameters

        Returns:
            SEARCH 'query' IN schema WHERE ... LIMIT n

        Example:
            >>> params = HybridParameters(
            ...     query_text="Python tutorials",
            ...     schema="articles",
            ...     filters={"category": "tutorial"},
            ...     top_k=10
            ... )
            >>> builder.build_hybrid(params)
            "SEARCH 'Python tutorials' IN articles WHERE category = 'tutorial' LIMIT 10"
        """
        query = f"SEARCH '{params.query_text}' IN {params.schema}"

        if params.filters:
            where_clauses = self._build_where_clauses(params.filters)
            query += f" WHERE {where_clauses}"

        if params.order_by:
            query += f" ORDER BY {params.order_by}"

        query += f" LIMIT {params.top_k}"
        return query

    def _build_where_clauses(self, filters: dict[str, Any]) -> str:
        """Build WHERE clause from filters dictionary.

        Args:
            filters: Dictionary of field -> value

        Returns:
            WHERE clause string (without WHERE keyword)

        Example:
            >>> builder._build_where_clauses({"status": "active", "role": "admin"})
            "status = 'active' AND role = 'admin'"
        """
        clauses = []
        for field, value in filters.items():
            if isinstance(value, str):
                if value.startswith(">") or value.startswith("<"):
                    # Comparison operator already in value
                    clauses.append(f"{field} {value}")
                else:
                    clauses.append(f"{field} = '{value}'")
            elif isinstance(value, (int, float)):
                clauses.append(f"{field} = {value}")
            elif isinstance(value, bool):
                clauses.append(f"{field} = {str(value).upper()}")
            else:
                # Complex value, try to serialize
                clauses.append(f"{field} = '{value}'")

        return " AND ".join(clauses)


# Convenience functions for common patterns


def lookup(*keys: str) -> dict[str, Any]:
    """Create lookup parameters.

    Example:
        >>> lookup("alice", "bob")
        {"keys": ["alice", "bob"]}
    """
    return {"keys": list(keys)}


def search(
    query_text: str, schema: str, top_k: int = 10, **filters: Any
) -> dict[str, Any]:
    """Create search parameters.

    Example:
        >>> search("Python tutorials", "articles", top_k=5, category="tutorial")
        {"query_text": "Python tutorials", "schema": "articles", "top_k": 5, "filters": {"category": "tutorial"}}
    """
    return {
        "query_text": query_text,
        "schema": schema,
        "top_k": top_k,
        "filters": filters,
    }


def traverse(
    start_key: str,
    depth: int,
    direction: str = "out",
    edge_type: str | None = None,
) -> dict[str, Any]:
    """Create traverse parameters.

    Example:
        >>> traverse("alice", depth=1, direction="out", edge_type="colleague")
        {"start_key": "alice", "depth": 1, "direction": "out", "edge_type": "colleague"}
    """
    return {
        "start_key": start_key,
        "depth": depth,
        "direction": direction,
        "edge_type": edge_type,
    }


def sql(
    schema: str,
    fields: list[str] | None = None,
    limit: int | None = None,
    **where: Any,
) -> dict[str, Any]:
    """Create SQL parameters.

    Example:
        >>> sql("articles", fields=["name", "category"], limit=10, category="programming")
        {"schema": "articles", "fields": ["name", "category"], "limit": 10, "where": {"category": "programming"}}
    """
    return {
        "schema": schema,
        "fields": fields or ["*"],
        "where": where,
        "limit": limit,
    }
