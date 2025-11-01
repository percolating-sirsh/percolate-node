"""Test query plan data models and test case validation."""

import yaml
from pathlib import Path

import pytest

from percolate.memory.query_plan import (
    ExecutionMode,
    FallbackQuery,
    FallbackTrigger,
    Query,
    QueryDialect,
    QueryMetadata,
    QueryPlan,
    QueryType,
)


@pytest.fixture
def test_cases_file():
    """Load test cases YAML file."""
    # From tests/unit/memory/test_query_plan.py → percolation/ → percolate-rocks/test/data/
    test_data_dir = Path(__file__).parent.parent.parent.parent.parent
    yaml_file = (
        test_data_dir
        / "percolate-rocks"
        / "test"
        / "data"
        / "query_plan_test_cases.yaml"
    )
    assert yaml_file.exists(), f"Test cases file not found: {yaml_file}"

    with open(yaml_file) as f:
        return yaml.safe_load(f)


def test_query_plan_schema_validation():
    """Test that QueryPlan model validates correctly."""
    plan = QueryPlan(
        query_type=QueryType.SEARCH,
        confidence=0.85,
        primary_query=Query(
            dialect=QueryDialect.REM_SQL,
            query_string="SEARCH 'test' IN articles",
            parameters={"query_text": "test", "schema": "articles"},
        ),
        execution_mode=ExecutionMode.SINGLE_PASS,
        schema_hints=["articles"],
        reasoning="Test query plan",
    )

    assert plan.query_type == QueryType.SEARCH
    assert plan.confidence == 0.85
    assert plan.execution_mode == ExecutionMode.SINGLE_PASS


def test_low_confidence_requires_explanation():
    """Test that low confidence (<0.6) requires explanation field."""
    # Should raise validation error
    with pytest.raises(ValueError, match="Explanation required"):
        QueryPlan(
            query_type=QueryType.LOOKUP,
            confidence=0.45,  # Below 0.6
            primary_query=Query(
                dialect=QueryDialect.REM_SQL,
                query_string="LOOKUP 'test'",
            ),
            execution_mode=ExecutionMode.ADAPTIVE,
            reasoning="Low confidence query",
            # Missing explanation field!
        )

    # Should succeed with explanation
    plan = QueryPlan(
        query_type=QueryType.LOOKUP,
        confidence=0.45,
        primary_query=Query(
            dialect=QueryDialect.REM_SQL,
            query_string="LOOKUP 'test'",
        ),
        execution_mode=ExecutionMode.ADAPTIVE,
        reasoning="Low confidence query",
        explanation="Query is ambiguous: could be user, team, or project",
    )
    assert plan.explanation is not None


def test_fallback_query_structure():
    """Test fallback query structure."""
    fallback = FallbackQuery(
        query=Query(
            dialect=QueryDialect.STANDARD_SQL,
            query_string="SELECT * FROM users WHERE name = 'test'",
        ),
        trigger=FallbackTrigger.NO_RESULTS,
        confidence=0.70,
        reasoning="Try broader search if primary fails",
    )

    assert fallback.trigger == FallbackTrigger.NO_RESULTS
    assert fallback.confidence == 0.70


def test_tc001_semantic_search_validation(test_cases_file):
    """Test Case 1: Semantic search for indoor plants resources."""
    tc = next(
        tc
        for tc in test_cases_file["test_cases"]
        if tc["id"] == "TC001"
    )
    expected = tc["expected_plan"]

    # Build QueryPlan from test case
    primary_query = Query(
        dialect=QueryDialect.REM_SQL,
        query_string=expected["primary_query"]["query_string"],
        parameters=expected["primary_query"]["parameters"],
    )

    fallback_queries = [
        FallbackQuery(
            query=Query(
                dialect=QueryDialect.REM_SQL,
                query_string=fb["query"]["query_string"],
            ),
            trigger=FallbackTrigger(fb["trigger"]),
            confidence=fb["confidence"],
            reasoning=fb["reasoning"],
        )
        for fb in expected["fallback_queries"]
    ]

    plan = QueryPlan(
        query_type=QueryType(expected["query_type"]),
        confidence=expected["confidence"],
        primary_query=primary_query,
        fallback_queries=fallback_queries,
        execution_mode=ExecutionMode(expected["execution_mode"]),
        schema_hints=expected["schema_hints"],
        reasoning=expected["reasoning"],
        next_steps=expected["next_steps"],
        metadata=QueryMetadata(**expected["metadata"]),
    )

    # Validate structure
    assert plan.query_type == QueryType.SEARCH
    assert plan.confidence == 0.75
    assert plan.execution_mode == ExecutionMode.MULTI_STAGE
    assert len(plan.fallback_queries) == 2
    assert plan.schema_hints == ["resources", "articles"]
    assert plan.metadata.requires_embedding is True


def test_tc002_entity_lookup_validation(test_cases_file):
    """Test Case 2: Entity lookup for product AB-1234."""
    tc = next(
        tc
        for tc in test_cases_file["test_cases"]
        if tc["id"] == "TC002"
    )
    expected = tc["expected_plan"]

    plan = QueryPlan(
        query_type=QueryType(expected["query_type"]),
        confidence=expected["confidence"],
        primary_query=Query(
            dialect=QueryDialect.REM_SQL,
            query_string=expected["primary_query"]["query_string"],
            parameters=expected["primary_query"]["parameters"],
        ),
        fallback_queries=[
            FallbackQuery(
                query=Query(
                    dialect=QueryDialect.STANDARD_SQL,
                    query_string=expected["fallback_queries"][0]["query"][
                        "query_string"
                    ],
                ),
                trigger=FallbackTrigger(
                    expected["fallback_queries"][0]["trigger"]
                ),
                confidence=expected["fallback_queries"][0]["confidence"],
                reasoning=expected["fallback_queries"][0]["reasoning"],
            )
        ],
        execution_mode=ExecutionMode(expected["execution_mode"]),
        schema_hints=expected["schema_hints"],
        reasoning=expected["reasoning"],
        next_steps=expected["next_steps"],
        metadata=QueryMetadata(**expected["metadata"]),
    )

    assert plan.query_type == QueryType.LOOKUP
    assert plan.confidence == 0.95
    assert plan.execution_mode == ExecutionMode.SINGLE_PASS
    assert plan.primary_query.parameters["keys"] == ["AB-1234"]
    assert plan.metadata.estimated_time_ms == 5


def test_tc003_graph_traversal_validation(test_cases_file):
    """Test Case 3: Graph traversal for colleagues of Alice."""
    tc = next(
        tc
        for tc in test_cases_file["test_cases"]
        if tc["id"] == "TC003"
    )
    expected = tc["expected_plan"]

    plan = QueryPlan(
        query_type=QueryType(expected["query_type"]),
        confidence=expected["confidence"],
        primary_query=Query(
            dialect=QueryDialect.REM_SQL,
            query_string=expected["primary_query"]["query_string"],
            parameters=expected["primary_query"]["parameters"],
        ),
        fallback_queries=[
            FallbackQuery(
                query=Query(
                    dialect=QueryDialect.REM_SQL,
                    query_string=fb["query"]["query_string"],
                ),
                trigger=FallbackTrigger(fb["trigger"]),
                confidence=fb["confidence"],
                reasoning=fb["reasoning"],
            )
            for fb in expected["fallback_queries"]
        ],
        execution_mode=ExecutionMode(expected["execution_mode"]),
        schema_hints=expected["schema_hints"],
        reasoning=expected["reasoning"],
        next_steps=expected["next_steps"],
        metadata=QueryMetadata(**expected["metadata"]),
    )

    assert plan.query_type == QueryType.TRAVERSE
    assert plan.confidence == 0.80
    assert len(plan.fallback_queries) == 2
    assert "users" in plan.schema_hints
    assert "teams" in plan.schema_hints


def test_tc006_ambiguous_query_validation(test_cases_file):
    """Test Case 6: Ambiguous query 'bob' with low confidence."""
    tc = next(
        tc
        for tc in test_cases_file["test_cases"]
        if tc["id"] == "TC006"
    )
    expected = tc["expected_plan"]

    plan = QueryPlan(
        query_type=QueryType(expected["query_type"]),
        confidence=expected["confidence"],
        primary_query=Query(
            dialect=QueryDialect.REM_SQL,
            query_string=expected["primary_query"]["query_string"],
            parameters=expected["primary_query"]["parameters"],
        ),
        fallback_queries=[
            FallbackQuery(
                query=Query(
                    dialect=QueryDialect.REM_SQL,
                    query_string=fb["query"]["query_string"],
                ),
                trigger=FallbackTrigger(fb["trigger"]),
                confidence=fb["confidence"],
                reasoning=fb["reasoning"],
            )
            for fb in expected["fallback_queries"]
        ],
        execution_mode=ExecutionMode(expected["execution_mode"]),
        schema_hints=expected["schema_hints"],
        reasoning=expected["reasoning"],
        explanation=expected[
            "explanation"
        ],  # Required for low confidence
        next_steps=expected["next_steps"],
        metadata=QueryMetadata(**expected["metadata"]),
    )

    assert plan.confidence == 0.50
    assert plan.explanation is not None  # Required for confidence < 0.6
    assert "ambiguous" in plan.explanation.lower()
    assert plan.execution_mode == ExecutionMode.ADAPTIVE


def test_all_test_cases_validate(test_cases_file):
    """Validate all test cases conform to QueryPlan schema."""
    errors = []

    for tc in test_cases_file["test_cases"]:
        tc_id = tc["id"]
        tc_name = tc["name"]
        expected = tc["expected_plan"]

        try:
            # Build primary query
            primary_query = Query(
                dialect=QueryDialect(
                    expected["primary_query"]["dialect"]
                ),
                query_string=expected["primary_query"]["query_string"],
                parameters=expected["primary_query"].get(
                    "parameters", {}
                ),
            )

            # Build fallback queries
            fallback_queries = []
            for fb in expected.get("fallback_queries", []):
                fallback_queries.append(
                    FallbackQuery(
                        query=Query(
                            dialect=QueryDialect(
                                fb["query"].get("dialect", "rem_sql")
                            ),
                            query_string=fb["query"]["query_string"],
                            parameters=fb["query"].get("parameters", {}),
                        ),
                        trigger=FallbackTrigger(fb["trigger"]),
                        confidence=fb["confidence"],
                        reasoning=fb["reasoning"],
                    )
                )

            # Build full plan
            plan = QueryPlan(
                query_type=QueryType(expected["query_type"]),
                confidence=expected["confidence"],
                primary_query=primary_query,
                fallback_queries=fallback_queries,
                execution_mode=ExecutionMode(expected["execution_mode"]),
                schema_hints=expected.get("schema_hints", []),
                reasoning=expected["reasoning"],
                explanation=expected.get("explanation"),
                next_steps=expected.get("next_steps", []),
                metadata=QueryMetadata(**expected.get("metadata", {})),
            )

            # Validation succeeded
            print(f"✓ {tc_id}: {tc_name}")

        except Exception as e:
            errors.append(f"{tc_id} ({tc_name}): {e}")

    # Report all errors at once
    if errors:
        pytest.fail(
            f"Test case validation failed:\n" + "\n".join(errors)
        )
