"""Integration tests for Python API."""

import pytest
from rem_db import Database, AsyncDatabase
from rem_db.models import Article, Person, Sprint


@pytest.fixture
def db(tmp_path):
    """Create temporary database for testing."""
    return Database(path=str(tmp_path), tenant_id="test")


def test_database_creation(db):
    """Test database initialization."""
    # TODO: Verify database created successfully
    pass


def test_register_schema(db):
    """Test schema registration from Pydantic model."""
    # TODO: Register Article schema and verify
    pass


def test_insert_entity(db):
    """Test entity insertion."""
    # TODO: Insert article and verify UUID returned
    pass


def test_deterministic_uuid(db):
    """Test deterministic UUID generation (NB: same key -> same UUID)."""
    # TODO: Insert same key twice, verify same UUID (upsert)
    pass


def test_batch_insert(db):
    """Test batch insert (NB: always use batches when possible)."""
    # TODO: Batch insert multiple entities
    pass


def test_get_entity(db):
    """Test entity retrieval by ID."""
    # TODO: Insert and get entity
    pass


def test_lookup_by_key(db):
    """Test global key lookup."""
    # TODO: Lookup entity by key field value
    pass


def test_search(db):
    """Test semantic search (NB: HNSW index for 200x speedup)."""
    # TODO: Insert entities with embeddings and search
    pass


def test_sql_query(db):
    """Test SQL query execution."""
    # TODO: Query entities with SQL
    pass


def test_graph_traversal(db):
    """Test graph traversal (NB: bidirectional edges for 20x speedup)."""
    # TODO: Create edges and traverse
    pass


def test_export_parquet(db, tmp_path):
    """Test Parquet export."""
    # TODO: Export entities to Parquet
    pass


def test_ingest_document(db, tmp_path):
    """Test document ingestion with chunking."""
    # TODO: Ingest PDF and verify chunks created
    pass
