"""Test LLM query builder with mocked responses."""

import json
from unittest.mock import Mock, patch

import pytest

from rem_db.llm_query_builder import QueryBuilder, QueryResult


@pytest.fixture
def sample_schema():
    """Sample resource schema."""
    return {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Unique identifier"},
            "name": {"type": "string", "description": "Resource name"},
            "content": {"type": "string", "description": "Resource content"},
            "embedding": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Vector embedding",
            },
        },
    }


def test_query_result_model():
    """Test QueryResult Pydantic model."""
    result = QueryResult(
        query_type="vector",
        query="SELECT * FROM resources WHERE embedding.cosine('programming') LIMIT 10",
        confidence=0.9,
        explanation=None,
        follow_up_question=None,
        fallback_query=None,
    )

    assert result.query_type == "vector"
    assert result.confidence == 0.9
    assert "embedding.cosine" in result.query


def test_query_result_with_explanation():
    """Test QueryResult with low confidence explanation."""
    result = QueryResult(
        query_type="sql",
        query="SELECT * FROM resources WHERE name LIKE '%Python%'",
        confidence=0.7,
        explanation="Using LIKE pattern matching since exact name unclear",
        follow_up_question="Do you want case-sensitive matching?",
        fallback_query="SELECT * FROM resources WHERE embedding.cosine('Python') LIMIT 10",
    )

    assert result.confidence == 0.7
    assert result.explanation is not None
    assert result.follow_up_question is not None
    assert result.fallback_query is not None


def test_build_prompt(sample_schema):
    """Test prompt building."""
    builder = QueryBuilder(api_key="fake-key")

    prompt = builder._build_prompt(
        natural_language="find resources about programming",
        schema=sample_schema,
        table="resources",
        max_stages=3,
    )

    # Check prompt contains key elements
    assert "find resources about programming" in prompt
    assert "resources" in prompt
    assert "embedding.cosine" in prompt
    assert "key_value" in prompt
    assert "sql" in prompt
    assert "vector" in prompt


@patch("httpx.Client.post")
def test_query_builder_vector_query(mock_post, sample_schema):
    """Test query builder with mocked API response for vector query."""
    # Mock OpenAI API response
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "query_type": "vector",
                            "query": "SELECT * FROM resources WHERE embedding.cosine('programming') LIMIT 10",
                            "confidence": 0.9,
                            "explanation": None,
                            "follow_up_question": None,
                            "fallback_query": "SELECT * FROM resources LIMIT 10",
                        }
                    )
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    builder = QueryBuilder(api_key="fake-key")
    result = builder.build_query(
        natural_language="find resources about programming",
        schema=sample_schema,
        table="resources",
        max_stages=3,
    )

    assert result.query_type == "vector"
    assert result.confidence == 0.9
    assert "embedding.cosine" in result.query
    assert result.fallback_query is not None

    builder.close()


@patch("httpx.Client.post")
def test_query_builder_key_value_query(mock_post, sample_schema):
    """Test query builder with key-value lookup."""
    # Mock response for ID-based lookup
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "query_type": "key_value",
                            "query": "SELECT * FROM resources WHERE id = 'abc-123'",
                            "confidence": 1.0,
                            "explanation": None,
                            "follow_up_question": None,
                            "fallback_query": None,
                        }
                    )
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    builder = QueryBuilder(api_key="fake-key")
    result = builder.build_query(
        natural_language="get resource abc-123",
        schema=sample_schema,
        table="resources",
        max_stages=3,
    )

    assert result.query_type == "key_value"
    assert result.confidence == 1.0
    assert "id = 'abc-123'" in result.query

    builder.close()


@patch("httpx.Client.post")
def test_query_builder_sql_query(mock_post, sample_schema):
    """Test query builder with SQL predicate."""
    # Mock response for field-based query
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "query_type": "sql",
                            "query": "SELECT * FROM resources WHERE name = 'Python Tutorial'",
                            "confidence": 0.95,
                            "explanation": None,
                            "follow_up_question": None,
                            "fallback_query": "SELECT * FROM resources WHERE embedding.cosine('Python Tutorial') LIMIT 10",
                        }
                    )
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    builder = QueryBuilder(api_key="fake-key")
    result = builder.build_query(
        natural_language="resources named Python Tutorial",
        schema=sample_schema,
        table="resources",
        max_stages=3,
    )

    assert result.query_type == "sql"
    assert result.confidence == 0.95
    assert "name = 'Python Tutorial'" in result.query

    builder.close()


def test_query_builder_requires_api_key():
    """Test that QueryBuilder requires API key."""
    with pytest.raises(ValueError, match="OpenAI API key required"):
        QueryBuilder(api_key=None)
