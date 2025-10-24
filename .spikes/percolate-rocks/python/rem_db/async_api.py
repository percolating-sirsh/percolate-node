"""Async API wrapper for Python async/await.

Wraps Rust async operations (tokio) for Python asyncio ergonomics.
"""

import asyncio
from typing import Optional
from rem_db._rust import Database as _RustDatabase


class AsyncDatabase:
    """Async database interface for Python async/await.

    Example:
        >>> import asyncio
        >>> from rem_db import AsyncDatabase
        >>>
        >>> async def main():
        ...     db = AsyncDatabase(path="./data", tenant_id="default")
        ...     entity_id = await db.insert("articles", {"title": "...", "content": "..."})
        ...     results = await db.search("programming", schema="articles", top_k=5)
        >>>
        >>> asyncio.run(main())
    """

    def __init__(self, path: str, tenant_id: str = "default"):
        """Initialize async database.

        Args:
            path: Database directory path
            tenant_id: Tenant identifier for isolation
        """
        self._rust_db = _RustDatabase(path, tenant_id)

    async def register_schema(self, name: str, schema: dict) -> None:
        """Register Pydantic schema from JSON Schema (async).

        Args:
            name: Schema name (table name)
            schema: JSON Schema dict

        Raises:
            ValueError: If schema is invalid
        """
        # TODO: Async schema registration
        pass

    async def insert(self, table: str, data: dict) -> str:
        """Insert entity with automatic embedding generation (async).

        Args:
            table: Table/schema name
            data: Entity data

        Returns:
            Entity UUID

        Raises:
            ValueError: If data doesn't match schema

        Note:
            Embedding generation is async (OpenAI API call)
        """
        # TODO: Async insert with embedding
        pass

    async def insert_batch(self, table: str, entities: list[dict]) -> list[str]:
        """Batch insert entities with batched embedding generation (async).

        Args:
            table: Table/schema name
            entities: List of entity dicts

        Returns:
            List of entity UUIDs

        Note:
            Uses batched embeddings for efficiency (NB from README)
            Single OpenAI API call for entire batch
        """
        # TODO: Async batch insert
        pass

    async def get(self, entity_id: str) -> dict | None:
        """Get entity by ID (async).

        Args:
            entity_id: Entity UUID

        Returns:
            Entity dict or None if not found

        Note:
            Fast operation, no network calls
        """
        # TODO: Async get
        pass

    async def search(self, query: str, schema: str, top_k: int = 10) -> list[dict]:
        """Semantic search using vector embeddings (async).

        Args:
            query: Search query text
            schema: Schema name to search
            top_k: Number of results

        Returns:
            List of (entity, score) tuples

        Note:
            Query embedding generation is async (OpenAI API)
            HNSW search is fast (< 5ms)
        """
        # TODO: Async search
        pass

    async def query(self, sql: str) -> list[dict]:
        """Execute SQL query (async).

        Args:
            sql: SQL SELECT statement

        Returns:
            List of matching entities

        Note:
            Fast operation, no network calls
        """
        # TODO: Async query
        pass

    async def ask(
        self, question: str, *, execute: bool = True
    ) -> dict | list[dict]:
        """Natural language query using LLM (async).

        Args:
            question: Natural language question
            execute: Execute query (True) or just return plan (False)

        Returns:
            Query results if execute=True, query plan if execute=False

        Note:
            LLM call is async (OpenAI API)

        Example:
            >>> await db.ask("show recent programming articles")
            [{"title": "Rust Performance", ...}, ...]

            >>> await db.ask("show recent articles", execute=False)
            {"query": "SELECT * FROM articles ...", "confidence": 0.95, ...}
        """
        # TODO: Async ask
        pass

    async def traverse(
        self, start_id: str, direction: str = "out", depth: int = 2
    ) -> list[str]:
        """Graph traversal from starting entity (async).

        Args:
            start_id: Starting entity UUID
            direction: Traversal direction ("out", "in", "both")
            depth: Maximum traversal depth

        Returns:
            List of entity UUIDs in traversal order

        Note:
            Fast operation, no network calls
        """
        # TODO: Async traverse
        pass

    async def export(
        self, table: str, path: str, format: str = "parquet"
    ) -> None:
        """Export entities to file (async).

        Args:
            table: Table name
            path: Output file path
            format: Export format ("parquet", "csv", "jsonl")

        Note:
            I/O operations are async
        """
        # TODO: Async export
        pass

    async def ingest(self, file_path: str, schema: str) -> list[str]:
        """Ingest document file (async).

        Args:
            file_path: Document file path
            schema: Target schema name

        Returns:
            List of created entity UUIDs

        Note:
            Parsing and embedding generation are async
        """
        # TODO: Async ingest
        pass

    async def close(self) -> None:
        """Close database and flush data (async)."""
        # TODO: Async close
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Utility functions for running async code from sync context


def run_sync(coro):
    """Run async coroutine in sync context.

    Args:
        coro: Async coroutine

    Returns:
        Coroutine result

    Example:
        >>> db = AsyncDatabase(path="./data")
        >>> result = run_sync(db.search("query", "articles"))
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(coro)
    else:
        # Event loop exists, use it
        return loop.run_until_complete(coro)
