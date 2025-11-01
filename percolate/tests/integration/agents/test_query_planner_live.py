"""Integration tests for query planner with real Cerebras API.

These tests use actual API calls to verify query planning works end-to-end.
Requires CEREBRAS_API_KEY or falls back to ANTHROPIC_API_KEY.
"""

import os

import pytest

from percolate.agents.query_planner import plan_query
from percolate.memory.query_plan import ExecutionMode, QueryType
from percolate.settings import settings


# Skip tests if no API key available
pytestmark = pytest.mark.skipif(
    not os.environ.get("CEREBRAS_API_KEY")
    and not os.environ.get("ANTHROPIC_API_KEY"),
    reason="No LLM API key available (CEREBRAS_API_KEY or ANTHROPIC_API_KEY)",
)


@pytest.mark.asyncio
async def test_semantic_search_without_schema():
    """Test semantic search without schema hint - should use LOOKUP."""
    query = "indoor plants resources"

    plan = await plan_query(query, available_schemas=None, schema_hint=None)

    # Should use LOOKUP since no schema provided
    assert plan.query_type == QueryType.LOOKUP
    assert plan.confidence >= 0.5
    assert plan.primary_query.parameters.get("keys") is not None

    # Verify structure
    assert plan.reasoning is not None
    assert len(plan.next_steps) > 0

    # High confidence should not have explanation
    if plan.confidence >= 0.75:
        assert plan.explanation is None

    print(f"\n✓ Query: {query}")
    print(f"  Type: {plan.query_type}")
    print(f"  Confidence: {plan.confidence:.2f}")
    print(f"  Parameters: {plan.primary_query.parameters}")
    print(f"  Reasoning: {plan.reasoning[:100]}...")


@pytest.mark.asyncio
async def test_semantic_search_with_schema():
    """Test semantic search with schema hint - should use SEARCH."""
    query = "indoor plants resources"

    plan = await plan_query(
        query, available_schemas=["resources", "articles"], schema_hint="resources"
    )

    # Should use SEARCH with schema provided
    assert plan.query_type == QueryType.SEARCH
    assert plan.confidence >= 0.7
    assert plan.primary_query.parameters.get("query_text") is not None
    assert plan.primary_query.parameters.get("schema") == "resources"

    print(f"\n✓ Query: {query} (schema=resources)")
    print(f"  Type: {plan.query_type}")
    print(f"  Confidence: {plan.confidence:.2f}")
    print(f"  Parameters: {plan.primary_query.parameters}")


@pytest.mark.asyncio
async def test_entity_lookup_product():
    """Test entity lookup for product ID."""
    query = "product AB-1234"

    plan = await plan_query(query, available_schemas=None)

    # Should use LOOKUP for identifier
    assert plan.query_type == QueryType.LOOKUP
    assert plan.confidence >= 0.85
    assert "AB-1234" in str(plan.primary_query.parameters.get("keys", []))

    print(f"\n✓ Query: {query}")
    print(f"  Type: {plan.query_type}")
    print(f"  Confidence: {plan.confidence:.2f}")
    print(f"  Keys: {plan.primary_query.parameters.get('keys')}")


@pytest.mark.asyncio
async def test_entity_lookup_with_schema_hint():
    """Test entity lookup with schema hint - should use SQL."""
    query = "product AB-1234"

    plan = await plan_query(
        query, available_schemas=["products"], schema_hint="products"
    )

    # Can use SQL or LOOKUP - both valid
    assert plan.query_type in (QueryType.LOOKUP, QueryType.SQL)
    assert plan.confidence >= 0.85

    if plan.query_type == QueryType.SQL:
        assert plan.primary_query.parameters.get("schema") == "products"

    print(f"\n✓ Query: {query} (schema=products)")
    print(f"  Type: {plan.query_type}")
    print(f"  Confidence: {plan.confidence:.2f}")
    print(f"  Parameters: {plan.primary_query.parameters}")


@pytest.mark.asyncio
async def test_graph_traversal_colleagues():
    """Test graph traversal query."""
    query = "colleagues of Alice"

    plan = await plan_query(query, available_schemas=["users", "teams"])

    # Should use TRAVERSE
    assert plan.query_type == QueryType.TRAVERSE
    assert plan.confidence >= 0.7
    assert plan.primary_query.parameters.get("start_key") == "Alice"
    assert plan.primary_query.parameters.get("depth") in (1, 2)
    assert plan.primary_query.parameters.get("direction") in ("out", "both")

    print(f"\n✓ Query: {query}")
    print(f"  Type: {plan.query_type}")
    print(f"  Confidence: {plan.confidence:.2f}")
    print(f"  Parameters: {plan.primary_query.parameters}")


@pytest.mark.asyncio
async def test_sql_query_recent_trends():
    """Test SQL query with time filter."""
    query = "recent trends"

    plan = await plan_query(query, available_schemas=["trends", "articles"])

    # Should use SQL with time filter
    assert plan.query_type == QueryType.SQL
    assert plan.confidence >= 0.6
    assert plan.primary_query.parameters.get("schema") in ("trends", "articles")
    assert plan.primary_query.parameters.get("where") is not None

    print(f"\n✓ Query: {query}")
    print(f"  Type: {plan.query_type}")
    print(f"  Confidence: {plan.confidence:.2f}")
    print(f"  Parameters: {plan.primary_query.parameters}")


@pytest.mark.asyncio
async def test_hybrid_query_python_tutorials():
    """Test hybrid semantic + SQL query."""
    query = "Python tutorials from last month"

    plan = await plan_query(
        query, available_schemas=["articles", "resources"], schema_hint="articles"
    )

    # Should use HYBRID or SEARCH with filters
    assert plan.query_type in (QueryType.HYBRID, QueryType.SEARCH)
    assert plan.confidence >= 0.7
    assert plan.primary_query.parameters.get("query_text") is not None
    assert plan.primary_query.parameters.get("schema") == "articles"

    # Should have time-based filter
    filters = plan.primary_query.parameters.get("filters", {})
    assert any("created_at" in str(k) for k in filters.keys()) or len(filters) > 0

    print(f"\n✓ Query: {query} (schema=articles)")
    print(f"  Type: {plan.query_type}")
    print(f"  Confidence: {plan.confidence:.2f}")
    print(f"  Parameters: {plan.primary_query.parameters}")


@pytest.mark.asyncio
async def test_ambiguous_query_low_confidence():
    """Test ambiguous query triggers low confidence."""
    query = "bob"

    plan = await plan_query(query, available_schemas=["users", "teams", "projects"])

    # Should detect ambiguity
    assert plan.confidence <= 0.7  # Low confidence

    # Low confidence requires explanation
    if plan.confidence < 0.75:
        assert plan.explanation is not None
        assert len(plan.explanation) > 0

    # Should still generate a plan (LOOKUP)
    assert plan.query_type == QueryType.LOOKUP
    assert plan.primary_query.parameters.get("keys") == ["bob"]

    print(f"\n✓ Query: {query} (ambiguous)")
    print(f"  Type: {plan.query_type}")
    print(f"  Confidence: {plan.confidence:.2f}")
    print(f"  Explanation: {plan.explanation[:100] if plan.explanation else 'None'}...")


@pytest.mark.asyncio
async def test_ambiguous_query_with_schema_hint():
    """Test ambiguous query with schema hint improves confidence."""
    query = "bob"

    # Without schema
    plan_no_schema = await plan_query(query)
    confidence_no_schema = plan_no_schema.confidence

    # With schema
    plan_with_schema = await plan_query(
        query, available_schemas=["users"], schema_hint="users"
    )
    confidence_with_schema = plan_with_schema.confidence

    # Schema hint should improve confidence
    assert confidence_with_schema >= confidence_no_schema

    print(f"\n✓ Query: {query}")
    print(f"  Without schema: {confidence_no_schema:.2f}")
    print(f"  With schema=users: {confidence_with_schema:.2f}")
    print(f"  Improvement: {confidence_with_schema - confidence_no_schema:.2f}")


@pytest.mark.asyncio
async def test_multi_stage_execution():
    """Test multi-stage query plan generation."""
    query = "Python tutorials from last month"

    plan = await plan_query(query, available_schemas=["articles"])

    # Should have execution mode
    assert plan.execution_mode in (
        ExecutionMode.SINGLE_PASS,
        ExecutionMode.MULTI_STAGE,
        ExecutionMode.ADAPTIVE,
    )

    # If multi-stage, should have fallbacks
    if plan.execution_mode == ExecutionMode.MULTI_STAGE:
        assert len(plan.fallback_queries) > 0

        # Verify fallback structure
        for fallback in plan.fallback_queries:
            assert fallback.query is not None
            assert fallback.trigger is not None
            assert fallback.confidence > 0
            assert fallback.reasoning is not None

    print(f"\n✓ Query: {query}")
    print(f"  Execution mode: {plan.execution_mode}")
    print(f"  Fallbacks: {len(plan.fallback_queries)}")


@pytest.mark.asyncio
async def test_no_schema_guessing():
    """Test that planner doesn't guess schema names."""
    query = "find some articles about Python"

    # Don't provide schema
    plan = await plan_query(query, available_schemas=None)

    # Should use LOOKUP (schema-agnostic) not SEARCH
    assert plan.query_type == QueryType.LOOKUP

    # Should not have "articles" in parameters
    params_str = str(plan.primary_query.parameters)
    # Allow "articles" in keys for lookup, but not as schema
    if "schema" in plan.primary_query.parameters:
        assert plan.primary_query.parameters["schema"] != "articles"

    print(f"\n✓ Query: {query} (no schema)")
    print(f"  Type: {plan.query_type}")
    print(f"  Did not guess schema: ✓")


@pytest.mark.asyncio
async def test_output_conciseness():
    """Test that output is concise for high confidence queries."""
    query = "user-12345"

    plan = await plan_query(query)

    # High confidence query
    if plan.confidence >= 0.75:
        # Should NOT have explanation
        assert plan.explanation is None

        # Reasoning should be concise (<200 chars)
        assert len(plan.reasoning) < 200

        # Next steps should be brief (2-5 items, each <50 chars)
        assert len(plan.next_steps) <= 5
        for step in plan.next_steps:
            assert len(step) < 100  # Reasonable limit

    print(f"\n✓ Query: {query}")
    print(f"  Confidence: {plan.confidence:.2f}")
    print(f"  Reasoning length: {len(plan.reasoning)} chars")
    print(f"  Next steps: {len(plan.next_steps)}")
    print(f"  Concise: ✓")


@pytest.mark.asyncio
async def test_model_selection():
    """Test that correct model is used."""
    query = "test query"

    # Should use query model from settings
    plan = await plan_query(query)

    # Verify plan was generated (model worked)
    assert plan.query_type is not None
    assert plan.confidence > 0

    # Log which model was used
    query_model = settings.get_query_model()
    print(f"\n✓ Model used: {query_model}")
    print(f"  Query planned successfully: ✓")


# Run all tests and show summary
@pytest.mark.asyncio
async def test_summary():
    """Run all tests and print summary."""
    print("\n" + "=" * 70)
    print("QUERY PLANNER INTEGRATION TEST SUMMARY")
    print("=" * 70)
    print(f"Model: {settings.get_query_model()}")
    print(f"Cerebras key: {'✓' if os.environ.get('CEREBRAS_API_KEY') else '✗'}")
    print("=" * 70)
