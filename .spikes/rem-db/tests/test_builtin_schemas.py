"""Tests for built-in system schemas (Resource, Agent, Session, Message)."""

import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from rem_db import REMDatabase, Agent, Session, Message, Resource


def test_builtin_schemas_auto_registered():
    """Test that built-in schemas are automatically registered."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="test-tenant", path=tmpdir)

        # Check built-in schemas are registered
        schemas = db.list_schemas()
        assert "resources" in schemas
        assert "agents" in schemas
        assert "sessions" in schemas
        assert "messages" in schemas


def test_builtin_schemas_categories():
    """Test that built-in schemas have correct categories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="test-tenant", path=tmpdir)

        # Check system category
        system_schemas = db.list_schemas_by_category("system")
        assert "resources" in system_schemas
        assert "agents" in system_schemas
        assert "sessions" in system_schemas
        assert "messages" in system_schemas

        # Check categories exist
        categories = db.get_categories()
        assert "system" in categories
        assert "agents" in categories
        assert "public" in categories
        assert "user" in categories


def test_resource_insert():
    """Test inserting a Resource entity."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="test-tenant", path=tmpdir)

        # Insert resource
        resource_id = db.insert("resources", {
            "name": "Test Document",
            "content": "This is test content",
            "category": "documentation",
            "metadata": {"source": "test"},
            "uri": "file:///test.md"
        })

        # Query it back
        resource = db.get_resource(resource_id)
        assert resource is not None
        assert resource.name == "Test Document"
        assert resource.content == "This is test content"
        assert resource.category == "documentation"
        assert resource.metadata["source"] == "test"


def test_agent_insert():
    """Test inserting an Agent entity."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="test-tenant", path=tmpdir)

        # Insert agent
        agent_id = db.insert("agents", {
            "name": "test-agent",
            "category": "user",
            "description": "Test agent for validation",
            "output_schema": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"}
                }
            },
            "tools": [
                {
                    "mcp_server": "test",
                    "tool_name": "search",
                    "usage": "Search for information"
                }
            ]
        })

        # Query it back via SQL
        results = db.sql("SELECT * FROM agents WHERE name = 'test-agent'")
        assert len(results) == 1
        assert results[0]["name"] == "test-agent"
        assert results[0]["category"] == "user"
        assert results[0]["description"] == "Test agent for validation"


def test_session_and_messages():
    """Test inserting Session and Message entities."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="test-tenant", path=tmpdir)

        # Insert session
        session_id = db.insert("sessions", {
            "name": "Test Session",
            "query": "What is the capital of France?",
            "agent": "test-agent",
            "session_type": "chat"
        })

        # Insert messages
        msg1_id = db.insert("messages", {
            "session_id": str(session_id),
            "role": "user",
            "content": "What is the capital of France?"
        })

        msg2_id = db.insert("messages", {
            "session_id": str(session_id),
            "role": "assistant",
            "content": "The capital of France is Paris.",
            "trace_id": "trace-123"
        })

        # Query messages by session
        results = db.sql(f"SELECT * FROM messages WHERE session_id = '{session_id}' ORDER BY created_at")
        assert len(results) == 2
        assert results[0]["role"] == "user"
        assert results[1]["role"] == "assistant"
        assert results[1]["trace_id"] == "trace-123"


def test_system_fields_present():
    """Test that all entities have system fields (created_at, modified_at, deleted_at, edges)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="test-tenant", path=tmpdir)

        # Insert resource
        resource_id = db.insert("resources", {
            "name": "Test",
            "content": "Content",
        })

        # Get resource and check system fields
        resource = db.get_resource(resource_id)
        assert resource.id is not None
        assert resource.created_at is not None
        assert resource.modified_at is not None
        assert resource.deleted_at is None  # Not soft-deleted
        assert isinstance(resource.edges, list)
        assert len(resource.edges) == 0  # No edges yet


def test_embedding_field_on_resource():
    """Test that Resource supports embedding field."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="test-tenant", path=tmpdir)

        # Create resource with embedding
        embedding = [0.1] * 768  # 768-dimensional embedding

        resource_id = db.insert("resources", {
            "name": "Test Document",
            "content": "This is test content",
            "embedding": embedding
        })

        # Get resource and verify embedding
        resource = db.get_resource(resource_id)
        assert resource.embedding is not None
        assert len(resource.embedding) == 768
        assert resource.embedding[0] == 0.1


def test_category_filtering_sql():
    """Test filtering schemas by category in SQL queries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="test-tenant", path=tmpdir)

        # Insert agents in different categories
        db.insert("agents", {
            "name": "system-agent",
            "category": "system",
            "description": "System agent",
            "output_schema": {}
        })

        db.insert("agents", {
            "name": "user-agent",
            "category": "user",
            "description": "User agent",
            "output_schema": {}
        })

        # Query by category
        system_agents = db.sql("SELECT * FROM agents WHERE category = 'system'")
        assert len(system_agents) == 1
        assert system_agents[0]["name"] == "system-agent"

        user_agents = db.sql("SELECT * FROM agents WHERE category = 'user'")
        assert len(user_agents) == 1
        assert user_agents[0]["name"] == "user-agent"
