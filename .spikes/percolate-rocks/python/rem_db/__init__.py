"""REM Database - High-performance embedded database for semantic search.

This is a thin Python wrapper over the Rust core implementation.
All heavy operations are delegated to Rust for performance.
"""

from rem_db._rust import Database as _RustDatabase
from rem_db.models import Entity, Edge, SearchResult, QueryPlan
from rem_db.async_api import AsyncDatabase

__version__ = "0.1.0"

__all__ = [
    "Database",
    "AsyncDatabase",
    "Entity",
    "Edge",
    "SearchResult",
    "QueryPlan",
]


class Database:
    """REM database interface.

    Thin wrapper over Rust implementation for synchronous operations.

    Example:
        >>> from rem_db import Database
        >>> db = Database(path="./data", tenant_id="default")
        >>> db.register_schema("articles", article_schema)
        >>> entity_id = db.insert("articles", {"title": "...", "content": "..."})
        >>> results = db.search("programming", schema="articles", top_k=5)
    """

    def __init__(self, path: str, tenant_id: str = "default"):
        """Initialize database.

        Args:
            path: Database directory path
            tenant_id: Tenant identifier for isolation
        """
        self._rust_db = _RustDatabase(path, tenant_id)

    def register_schema(self, name: str, schema: dict) -> None:
        """Register Pydantic schema from JSON Schema.

        Args:
            name: Schema name (table name)
            schema: JSON Schema dict (from Pydantic model)

        Raises:
            ValueError: If schema is invalid
        """
        # TODO: Implement schema registration
        pass

    def insert(self, table: str, data: dict) -> str:
        """Insert entity into table.

        Args:
            table: Table/schema name
            data: Entity data

        Returns:
            Entity UUID

        Raises:
            ValueError: If data doesn't match schema
        """
        # TODO: Delegate to Rust
        pass

    def insert_batch(self, table: str, entities: list[dict]) -> list[str]:
        """Batch insert entities.

        Args:
            table: Table/schema name
            entities: List of entity dicts

        Returns:
            List of entity UUIDs

        Note:
            Uses batched embeddings for efficiency (NB from README)
        """
        # TODO: Delegate to Rust
        pass

    def get(self, entity_id: str) -> dict | None:
        """Get entity by ID.

        Args:
            entity_id: Entity UUID

        Returns:
            Entity dict or None if not found
        """
        # TODO: Delegate to Rust
        pass

    def lookup(self, key_value: str) -> list[dict]:
        """Global lookup by key field value.

        Args:
            key_value: Key field value (from uri, key, or name)

        Returns:
            List of matching entities

        Note:
            Uses reverse key index for O(log n) lookup
        """
        # TODO: Delegate to Rust
        pass

    def search(self, query: str, schema: str, top_k: int = 10) -> list[dict]:
        """Semantic search using vector embeddings.

        Args:
            query: Search query text
            schema: Schema name to search
            top_k: Number of results

        Returns:
            List of (entity, score) tuples

        Note:
            Uses HNSW index for 200x speedup
        """
        # TODO: Delegate to Rust
        pass

    def query(self, sql: str) -> list[dict]:
        """Execute SQL query.

        Args:
            sql: SQL SELECT statement

        Returns:
            List of matching entities

        Note:
            Uses native Rust execution for 5-10x speedup
        """
        # TODO: Delegate to Rust
        pass

    def ask(self, question: str, *, execute: bool = True) -> dict | list[dict]:
        """Natural language query using LLM.

        Args:
            question: Natural language question
            execute: Execute query (True) or just return plan (False)

        Returns:
            Query results if execute=True, query plan if execute=False

        Example:
            >>> db.ask("show recent programming articles")
            [{"title": "Rust Performance", ...}, ...]

            >>> db.ask("show recent articles", execute=False)
            {"query": "SELECT * FROM articles ...", "confidence": 0.95, ...}
        """
        # TODO: Delegate to Rust
        pass

    def traverse(
        self, start_id: str, direction: str = "out", depth: int = 2
    ) -> list[str]:
        """Graph traversal from starting entity.

        Args:
            start_id: Starting entity UUID
            direction: Traversal direction ("out", "in", "both")
            depth: Maximum traversal depth

        Returns:
            List of entity UUIDs in traversal order

        Note:
            Uses bidirectional edges for 20x speedup
        """
        # TODO: Delegate to Rust
        pass

    def export(self, table: str, path: str, format: str = "parquet") -> None:
        """Export entities to file.

        Args:
            table: Table name
            path: Output file path
            format: Export format ("parquet", "csv", "jsonl")

        Note:
            Parquet uses parallel encoding for 5x speedup
        """
        # TODO: Delegate to Rust
        pass

    def ingest(self, file_path: str, schema: str) -> list[str]:
        """Ingest document file.

        Args:
            file_path: Document file path (PDF, TXT, etc.)
            schema: Target schema name

        Returns:
            List of created entity UUIDs (chunks)

        Note:
            Automatically chunks documents and generates embeddings
        """
        # TODO: Delegate to Rust
        pass

    def close(self) -> None:
        """Close database and flush data."""
        # TODO: Delegate to Rust
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
