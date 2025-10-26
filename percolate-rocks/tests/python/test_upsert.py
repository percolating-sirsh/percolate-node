"""Test upsert functionality with Pydantic model collections."""

import json
import pytest
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Create Database with environment configuration."""
    # Set environment variables for test database
    db_path = tmp_path / "test_db"
    db_path.mkdir()

    monkeypatch.setenv("P8_DB_PATH", str(db_path))
    monkeypatch.setenv("P8_TENANT_ID", "test")

    # Import after environment is set
    from rem_db import Database

    db = Database()

    # Register Session schema - convert to JSON string
    db.register_schema("Session", json.dumps(Session.model_json_schema()))

    # Register Resource schema - convert to JSON string
    db.register_schema("Resource", json.dumps(Resource.model_json_schema()))

    return db


class Session(BaseModel):
    """Session model for testing."""
    session_id: str = Field(description="Session ID")
    user_id: str = Field(description="User ID")
    start_time: str = Field(description="Session start time")

    model_config = ConfigDict(
        json_schema_extra={
            "key_field": "session_id",
            "indexed_fields": ["user_id"],
            "name": "Session",
            "short_name": "sessions",
            "version": "1.0.0",
            "category": "user"
        }
    )


class Resource(BaseModel):
    """Resource model for testing."""
    name: str = Field(description="Resource name")
    content: str = Field(description="Resource content")
    uri: str = Field(description="Resource URI")

    model_config = ConfigDict(
        json_schema_extra={
            "key_field": "uri",
            "indexed_fields": ["name"],
            "embedding_fields": ["content"],
            "name": "Resource",
            "short_name": "resources",
            "version": "1.0.0",
            "category": "user"
        }
    )


def test_upsert_sessions(db):
    """Test upserting a collection of Session models."""
    # Create collection of sessions
    sessions = [
        Session(session_id="s1", user_id="u1", start_time="2025-10-26T10:00:00Z"),
        Session(session_id="s2", user_id="u1", start_time="2025-10-26T11:00:00Z"),
        Session(session_id="s3", user_id="u2", start_time="2025-10-26T12:00:00Z"),
    ]

    # Upsert sessions - pass model instances directly
    uuids = db.upsert(sessions)

    # Verify UUIDs returned
    assert len(uuids) == 3
    assert all(isinstance(uuid, str) for uuid in uuids)

    # Verify each session can be retrieved
    for uuid in uuids:
        entity = db.get(uuid)
        assert entity is not None
        assert "session_id" in entity
        assert "user_id" in entity


def test_upsert_resources(db):
    """Test upserting a collection of Resource models."""
    # Create collection of resources
    resources = [
        Resource(
            name="Python Tutorial",
            content="Learn Python programming basics",
            uri="https://docs.python.org/tutorial"
        ),
        Resource(
            name="Rust Book",
            content="The Rust programming language book",
            uri="https://doc.rust-lang.org/book"
        ),
        Resource(
            name="FastAPI Docs",
            content="FastAPI web framework documentation",
            uri="https://fastapi.tiangolo.com"
        ),
    ]

    # Upsert resources - pass model instances directly
    uuids = db.upsert(resources)

    # Verify UUIDs returned
    assert len(uuids) == 3
    assert all(isinstance(uuid, str) for uuid in uuids)

    # Verify each resource can be retrieved
    for uuid in uuids:
        entity = db.get(uuid)
        assert entity is not None
        assert "name" in entity
        assert "content" in entity
        assert "uri" in entity


@pytest.mark.skip(reason="Deterministic UUID generation not yet implemented")
def test_upsert_idempotency(db):
    """Test that upserting same data twice produces same UUIDs.

    NOTE: This test is skipped because deterministic UUID generation
    based on key_field is not yet implemented. Currently, UUIDs are random.
    """
    # Create session
    session = Session(
        session_id="idempotent_test",
        user_id="u1",
        start_time="2025-10-26T10:00:00Z"
    )

    # First upsert - pass model instance directly
    uuids1 = db.upsert([session])

    # Second upsert (same data) - pass model instance directly
    uuids2 = db.upsert([session])

    # Verify same UUID returned (deterministic UUID generation)
    assert uuids1 == uuids2
    assert len(uuids1) == 1

    # Verify only one entity exists
    entity = db.get(uuids1[0])
    assert entity is not None


def test_upsert_mixed_models(db):
    """Test upserting mixed model types in single call."""
    # Create mixed collection - pass model instances directly
    models = [
        Session(session_id="s1", user_id="u1", start_time="2025-10-26T10:00:00Z"),
        Resource(name="Doc", content="Content", uri="https://example.com"),
        Session(session_id="s2", user_id="u2", start_time="2025-10-26T11:00:00Z"),
    ]

    # Upsert mixed models
    uuids = db.upsert(models)

    # Verify correct number of UUIDs
    assert len(uuids) == 3

    # Verify entity types are correct by checking fields
    entity1 = db.get(uuids[0])
    assert "session_id" in entity1 and "user_id" in entity1

    entity2 = db.get(uuids[1])
    assert "name" in entity2 and "uri" in entity2

    entity3 = db.get(uuids[2])
    assert "session_id" in entity3 and "user_id" in entity3


def test_upsert_empty_collection(db):
    """Test upserting empty collection."""
    uuids = db.upsert([])
    assert uuids == []


@pytest.mark.skip(reason="Deterministic UUID generation not yet implemented")
def test_upsert_updates_existing(db):
    """Test that upsert updates existing entity with same key.

    NOTE: This test is skipped because deterministic UUID generation
    based on key_field is not yet implemented. Currently, each upsert
    creates a new entity with a random UUID instead of updating the existing one.
    """
    # Create session
    session_v1 = Session(
        session_id="update_test",
        user_id="u1",
        start_time="2025-10-26T10:00:00Z"
    )

    # First upsert - pass model instance directly
    uuid1 = db.upsert([session_v1])[0]
    entity1 = db.get(uuid1)
    assert entity1["user_id"] == "u1"

    # Update session (same session_id, different user_id)
    session_v2 = Session(
        session_id="update_test",
        user_id="u2",  # Changed
        start_time="2025-10-26T10:00:00Z"
    )

    # Second upsert - pass model instance directly
    uuid2 = db.upsert([session_v2])[0]

    # Verify same UUID (key-based deterministic generation)
    assert uuid1 == uuid2

    # Verify entity was updated
    entity2 = db.get(uuid2)
    assert entity2["user_id"] == "u2"
