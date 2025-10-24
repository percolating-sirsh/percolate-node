"""Integration tests for async API."""

import pytest
from rem_db import AsyncDatabase
from rem_db.models import Article


@pytest.fixture
async def async_db(tmp_path):
    """Create temporary async database for testing."""
    db = AsyncDatabase(path=str(tmp_path), tenant_id="test")
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_async_insert(async_db):
    """Test async insert with embedding generation."""
    # TODO: Insert entity with async embedding generation
    pass


@pytest.mark.asyncio
async def test_async_batch_insert(async_db):
    """Test async batch insert (NB: batched embeddings)."""
    # TODO: Batch insert with batched embedding API call
    pass


@pytest.mark.asyncio
async def test_async_search(async_db):
    """Test async semantic search."""
    # TODO: Search with async query embedding generation
    pass


@pytest.mark.asyncio
async def test_async_ask(async_db):
    """Test async natural language query."""
    # TODO: Ask question with async LLM call
    pass


@pytest.mark.asyncio
async def test_async_ingest(async_db, tmp_path):
    """Test async document ingestion."""
    # TODO: Ingest document with async parsing and embedding
    pass


@pytest.mark.asyncio
async def test_async_context_manager(tmp_path):
    """Test async context manager."""
    # TODO: Test async with statement
    async with AsyncDatabase(path=str(tmp_path), tenant_id="test") as db:
        # TODO: Verify operations work
        pass
