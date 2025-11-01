"""Test QueryBuilder: parameter → executable SQL translation."""

import pytest

from percolate.memory.query_builder import (
    HybridParameters,
    LookupParameters,
    QueryBuilder,
    SQLParameters,
    SearchParameters,
    TraverseParameters,
    lookup,
    search,
    sql,
    traverse,
)
from percolate.memory.query_plan import QueryType


@pytest.fixture
def builder():
    """QueryBuilder instance."""
    return QueryBuilder()


# =================================================================
# LOOKUP Queries
# =================================================================


def test_build_lookup_single_key(builder):
    """Test LOOKUP with single key."""
    params = LookupParameters(keys=["alice"])
    query = builder.build_lookup(params)
    assert query == "LOOKUP 'alice'"


def test_build_lookup_multiple_keys(builder):
    """Test LOOKUP with multiple keys."""
    params = LookupParameters(keys=["alice", "bob", "charlie"])
    query = builder.build_lookup(params)
    assert query == "LOOKUP 'alice', 'bob', 'charlie'"


def test_build_lookup_via_build_method(builder):
    """Test LOOKUP via generic build() method."""
    query = builder.build(QueryType.LOOKUP, {"keys": ["alice"]})
    assert query == "LOOKUP 'alice'"


def test_lookup_helper():
    """Test lookup() helper function."""
    params = lookup("alice", "bob")
    assert params == {"keys": ["alice", "bob"]}


# =================================================================
# SEARCH Queries
# =================================================================


def test_build_search_basic(builder):
    """Test basic SEARCH without filters."""
    params = SearchParameters(
        query_text="indoor plants", schema="resources", top_k=10
    )
    query = builder.build_search(params)
    assert query == "SEARCH 'indoor plants' IN resources LIMIT 10"


def test_build_search_with_filters(builder):
    """Test SEARCH with WHERE filters."""
    params = SearchParameters(
        query_text="Python tutorials",
        schema="articles",
        top_k=5,
        filters={"category": "tutorial", "status": "published"},
    )
    query = builder.build_search(params)

    assert "SEARCH 'Python tutorials' IN articles" in query
    assert "WHERE" in query
    assert "category = 'tutorial'" in query
    assert "status = 'published'" in query
    assert "LIMIT 5" in query


def test_search_helper():
    """Test search() helper function."""
    params = search("Python", "articles", top_k=5, category="tutorial")
    assert params["query_text"] == "Python"
    assert params["schema"] == "articles"
    assert params["top_k"] == 5
    assert params["filters"]["category"] == "tutorial"


# =================================================================
# TRAVERSE Queries
# =================================================================


def test_build_traverse_with_key(builder):
    """Test TRAVERSE starting from entity key."""
    params = TraverseParameters(
        start_key="alice",
        depth=1,
        direction="out",
        edge_type="colleague",
    )
    query = builder.build_traverse(params)

    assert "LOOKUP 'alice'" in query
    assert "TRAVERSE FROM <alice_uuid>" in query
    assert "DEPTH 1" in query
    assert "DIRECTION out" in query
    assert "TYPE 'colleague'" in query


def test_build_traverse_with_uuid(builder):
    """Test TRAVERSE starting from UUID."""
    params = TraverseParameters(
        start_uuid="550e8400-e29b-41d4-a716-446655440000",
        depth=2,
        direction="both",
    )
    query = builder.build_traverse(params)

    assert "LOOKUP" not in query  # No lookup needed
    assert (
        "TRAVERSE FROM '550e8400-e29b-41d4-a716-446655440000'" in query
    )
    assert "DEPTH 2" in query
    assert "DIRECTION both" in query


def test_traverse_requires_start(builder):
    """Test TRAVERSE requires start_key or start_uuid."""
    params = TraverseParameters(depth=1, direction="out")

    with pytest.raises(ValueError, match="start_key or start_uuid"):
        builder.build_traverse(params)


def test_traverse_helper():
    """Test traverse() helper function."""
    params = traverse(
        "alice", depth=2, direction="both", edge_type="colleague"
    )
    assert params["start_key"] == "alice"
    assert params["depth"] == 2
    assert params["direction"] == "both"
    assert params["edge_type"] == "colleague"


# =================================================================
# SQL Queries
# =================================================================


def test_build_sql_select_all(builder):
    """Test SQL SELECT * FROM schema."""
    params = SQLParameters(schema="articles")
    query = builder.build_sql(params)
    assert query == "SELECT * FROM articles"


def test_build_sql_with_fields(builder):
    """Test SQL with specific fields."""
    params = SQLParameters(
        schema="articles", fields=["name", "category", "author"]
    )
    query = builder.build_sql(params)
    assert query == "SELECT name, category, author FROM articles"


def test_build_sql_with_where(builder):
    """Test SQL with WHERE clause."""
    params = SQLParameters(
        schema="articles", where={"category": "programming", "status": "published"}
    )
    query = builder.build_sql(params)

    assert "SELECT * FROM articles WHERE" in query
    assert "category = 'programming'" in query
    assert "status = 'published'" in query


def test_build_sql_with_order_and_limit(builder):
    """Test SQL with ORDER BY and LIMIT."""
    params = SQLParameters(
        schema="articles",
        order_by="created_at",
        direction="DESC",
        limit=10,
    )
    query = builder.build_sql(params)
    assert query == "SELECT * FROM articles ORDER BY created_at DESC LIMIT 10"


def test_build_sql_complete(builder):
    """Test SQL with all options."""
    params = SQLParameters(
        schema="articles",
        fields=["name", "views"],
        where={"category": "programming"},
        order_by="views",
        direction="DESC",
        limit=5,
    )
    query = builder.build_sql(params)

    assert "SELECT name, views FROM articles" in query
    assert "WHERE category = 'programming'" in query
    assert "ORDER BY views DESC" in query
    assert "LIMIT 5" in query


def test_sql_helper():
    """Test sql() helper function."""
    params = sql(
        "articles",
        fields=["name", "category"],
        limit=10,
        category="programming",
    )
    assert params["schema"] == "articles"
    assert params["fields"] == ["name", "category"]
    assert params["limit"] == 10
    assert params["where"]["category"] == "programming"


# =================================================================
# HYBRID Queries
# =================================================================


def test_build_hybrid_basic(builder):
    """Test hybrid semantic + SQL query."""
    params = HybridParameters(
        query_text="Python tutorials",
        schema="articles",
        top_k=10,
        filters={"category": "tutorial"},
    )
    query = builder.build_hybrid(params)

    assert "SEARCH 'Python tutorials' IN articles" in query
    assert "WHERE category = 'tutorial'" in query
    assert "LIMIT 10" in query


def test_build_hybrid_with_order(builder):
    """Test hybrid query with ORDER BY."""
    params = HybridParameters(
        query_text="machine learning",
        schema="articles",
        top_k=20,
        filters={"status": "published"},
        order_by="created_at",
    )
    query = builder.build_hybrid(params)

    assert "SEARCH 'machine learning' IN articles" in query
    assert "WHERE status = 'published'" in query
    assert "ORDER BY created_at" in query
    assert "LIMIT 20" in query


# =================================================================
# WHERE Clause Building
# =================================================================


def test_where_clause_string_values(builder):
    """Test WHERE clause with string values."""
    where = builder._build_where_clauses(
        {"category": "programming", "status": "active"}
    )
    assert "category = 'programming'" in where
    assert "status = 'active'" in where
    assert " AND " in where


def test_where_clause_numeric_values(builder):
    """Test WHERE clause with numeric values."""
    where = builder._build_where_clauses({"views": 1000, "score": 4.5})
    assert "views = 1000" in where
    assert "score = 4.5" in where


def test_where_clause_comparison_operators(builder):
    """Test WHERE clause with comparison operators."""
    where = builder._build_where_clauses(
        {
            "created_at": "> '2024-01-01'",
            "views": "> 1000",
            "score": ">= 4.0",
        }
    )
    assert "created_at > '2024-01-01'" in where
    assert "views > 1000" in where
    assert "score >= 4.0" in where


# =================================================================
# Test Case Integration
# =================================================================


def test_tc001_semantic_search(builder):
    """TC001: Semantic search for indoor plants resources."""
    # LLM generates parameters (not query string!)
    params = {
        "query_text": "indoor plants",
        "schema": "resources",
        "top_k": 10,
    }

    # QueryBuilder translates to executable SQL
    query = builder.build(QueryType.SEARCH, params)

    # Verify generated query matches expected
    assert query == "SEARCH 'indoor plants' IN resources LIMIT 10"


def test_tc002_entity_lookup(builder):
    """TC002: Entity lookup for product AB-1234."""
    # LLM generates parameters
    params = {"keys": ["AB-1234"]}

    # QueryBuilder translates to executable SQL
    query = builder.build(QueryType.LOOKUP, params)

    # Verify
    assert query == "LOOKUP 'AB-1234'"


def test_tc003_graph_traversal(builder):
    """TC003: Graph traversal for colleagues of Alice."""
    # LLM generates parameters
    params = {
        "start_key": "Alice",
        "depth": 1,
        "direction": "both",
        "edge_type": "colleague",
    }

    # QueryBuilder translates to executable SQL
    query = builder.build(QueryType.TRAVERSE, params)

    # Verify
    assert "LOOKUP 'Alice'" in query
    assert "TRAVERSE FROM <Alice_uuid>" in query
    assert "DEPTH 1" in query
    assert "DIRECTION both" in query
    assert "TYPE 'colleague'" in query


def test_tc005_hybrid_query(builder):
    """TC005: Hybrid query with semantic + SQL filters."""
    # LLM generates parameters
    params = {
        "query_text": "Python tutorials",
        "schema": "articles",
        "top_k": 10,
        "filters": {
            "category": "tutorial",
            "created_at": "> datetime('now', '-30 days')",
        },
    }

    # QueryBuilder translates to executable SQL
    query = builder.build(QueryType.HYBRID, params)

    # Verify
    assert "SEARCH 'Python tutorials' IN articles" in query
    assert "WHERE" in query
    assert "category = 'tutorial'" in query
    assert "created_at > datetime('now', '-30 days')" in query
    assert "LIMIT 10" in query


# =================================================================
# Validation and Error Handling
# =================================================================


def test_invalid_query_type(builder):
    """Test build() with invalid query type."""
    with pytest.raises(ValueError, match="Unsupported query type"):
        # Create a mock invalid type
        builder.build("invalid_type", {})  # type: ignore


def test_parameter_validation_lookup():
    """Test Pydantic validation for lookup parameters."""
    # Missing required field
    with pytest.raises(ValueError):
        LookupParameters()  # type: ignore


def test_parameter_validation_search():
    """Test Pydantic validation for search parameters."""
    # Missing required fields
    with pytest.raises(ValueError):
        SearchParameters(query_text="test")  # Missing schema


def test_parameter_validation_traverse():
    """Test Pydantic validation for traverse parameters."""
    # Invalid depth
    with pytest.raises(ValueError):
        TraverseParameters(depth=15, direction="out")  # Depth > 10
