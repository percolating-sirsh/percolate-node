"""Integration tests for Rust query planner with LLM providers.

Tests the Rust-based query planner (`rem_db.Database.plan_query()`) with different
LLM providers (Claude, Cerebras) using environment variables for credentials.

Requirements:
- rem_db package installed (maturin develop)
- LLM API keys in environment:
  - ANTHROPIC_API_KEY for Claude tests
  - CEREBRAS_API_KEY for Cerebras tests
  - P8_DEFAULT_LLM to select provider

Run:
    # Claude only
    export ANTHROPIC_API_KEY="sk-ant-..."
    export P8_DEFAULT_LLM="claude-sonnet-4-5-20250929"
    pytest tests/integration/test_rust_query_planner.py

    # Cerebras only
    export CEREBRAS_API_KEY="csk-..."
    export P8_DEFAULT_LLM="cerebras:qwen-3-32b"
    pytest tests/integration/test_rust_query_planner.py

    # Both (run all tests)
    export ANTHROPIC_API_KEY="sk-ant-..."
    export CEREBRAS_API_KEY="csk-..."
    pytest tests/integration/test_rust_query_planner.py
"""

import os
import pytest
from rem_db import Database


@pytest.fixture
def db():
    """Create database instance for testing."""
    return Database()


@pytest.fixture
def has_claude():
    """Check if Claude credentials are available."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


@pytest.fixture
def has_cerebras():
    """Check if Cerebras credentials are available."""
    return bool(os.environ.get("CEREBRAS_API_KEY"))


class TestQueryPlannerIdentifierLookup:
    """Test identifier lookup detection (pattern matching, no LLM needed)."""

    def test_simple_identifier(self, db):
        """Test simple identifier pattern detection."""
        plan = db.plan_query("111213", None)

        assert plan["query_type"] == "lookup"
        assert plan["confidence"] == 1.0
        assert "LOOKUP" in plan["primary_query"]["query_string"]

    def test_uuid_identifier(self, db):
        """Test UUID pattern detection."""
        plan = db.plan_query("550e8400-e29b-41d4-a716-446655440000", None)

        assert plan["query_type"] == "lookup"
        assert plan["confidence"] == 1.0


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("CEREBRAS_API_KEY"),
    reason="No LLM API key configured (ANTHROPIC_API_KEY or CEREBRAS_API_KEY)"
)
class TestQueryPlannerSemanticSearch:
    """Test semantic search query planning with LLM."""

    def test_semantic_search_with_schema(self, db):
        """Test semantic search query with schema context."""
        question = "find articles about rust programming"
        schema_context = "articles"

        plan = db.plan_query(question, schema_context)

        assert plan["query_type"] in ["search", "hybrid"]
        assert 0.5 <= plan["confidence"] <= 1.0
        assert "articles" in plan["primary_query"]["query_string"].lower()

    def test_complex_query_with_time_filter(self, db):
        """Test complex query with temporal constraints."""
        question = "show me recent articles from the last week"
        schema_context = "articles"

        plan = db.plan_query(question, schema_context)

        assert plan["query_type"] in ["sql", "hybrid"]
        assert 0.5 <= plan["confidence"] <= 1.0
        assert plan["execution_mode"] in ["single_pass", "multi_stage", "adaptive"]


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="Claude API key not configured (ANTHROPIC_API_KEY)"
)
class TestQueryPlannerClaude:
    """Test query planner with Claude Sonnet 4.5."""

    @pytest.fixture(autouse=True)
    def setup_claude(self):
        """Set Claude as default LLM for these tests."""
        original = os.environ.get("P8_DEFAULT_LLM")
        os.environ["P8_DEFAULT_LLM"] = "claude-sonnet-4-5-20250929"
        yield
        if original:
            os.environ["P8_DEFAULT_LLM"] = original
        else:
            os.environ.pop("P8_DEFAULT_LLM", None)

    def test_claude_semantic_search(self, db):
        """Test semantic search with Claude."""
        plan = db.plan_query("find python tutorials", "resources")

        assert plan["query_type"] in ["search", "hybrid"]
        assert "reasoning" in plan
        assert isinstance(plan["reasoning"], str)
        assert len(plan["reasoning"]) > 0


@pytest.mark.skipif(
    not os.environ.get("CEREBRAS_API_KEY"),
    reason="Cerebras API key not configured (CEREBRAS_API_KEY)"
)
class TestQueryPlannerCerebras:
    """Test query planner with Cerebras Qwen-3-32B (strict JSON schema mode)."""

    @pytest.fixture(autouse=True)
    def setup_cerebras(self):
        """Set Cerebras as default LLM for these tests."""
        original = os.environ.get("P8_DEFAULT_LLM")
        os.environ["P8_DEFAULT_LLM"] = "cerebras:qwen-3-32b"
        yield
        if original:
            os.environ["P8_DEFAULT_LLM"] = original
        else:
            os.environ.pop("P8_DEFAULT_LLM", None)

    def test_cerebras_semantic_search(self, db):
        """Test semantic search with Cerebras (tests strict JSON schema)."""
        plan = db.plan_query("find rust programming resources", "articles")

        # Cerebras strict schema mode should return valid structure
        assert plan["query_type"] in ["search", "hybrid"]
        assert "confidence" in plan
        assert isinstance(plan["confidence"], (int, float))
        assert 0.0 <= plan["confidence"] <= 1.0

    def test_cerebras_schema_adherence(self, db):
        """Test that Cerebras returns all required fields."""
        plan = db.plan_query("recent articles", "articles")

        # Required fields per QueryPlan schema
        required_fields = [
            "query_type",
            "confidence",
            "primary_query",
            "fallback_queries",
            "execution_mode",
            "schema_hints",
            "reasoning",
            "next_steps",
            "metadata"
        ]

        for field in required_fields:
            assert field in plan, f"Missing required field: {field}"

        # Validate primary_query structure
        assert "dialect" in plan["primary_query"]
        assert "query_string" in plan["primary_query"]
        assert "parameters" in plan["primary_query"]


@pytest.mark.integration
@pytest.mark.slow
class TestQueryPlannerPerformance:
    """Performance tests for query planning (requires LLM)."""

    @pytest.mark.skipif(
        not os.environ.get("CEREBRAS_API_KEY"),
        reason="Cerebras required for performance testing"
    )
    def test_cerebras_fast_planning(self, db):
        """Test that Cerebras query planning is fast (<2 seconds)."""
        import time

        os.environ["P8_DEFAULT_LLM"] = "cerebras:qwen-3-32b"

        start = time.time()
        plan = db.plan_query("find tutorials", "resources")
        elapsed = time.time() - start

        assert plan["query_type"] in ["search", "lookup", "hybrid"]
        assert elapsed < 2.0, f"Query planning took {elapsed:.2f}s, expected <2s"
