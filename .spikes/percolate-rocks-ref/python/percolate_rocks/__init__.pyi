"""Type stubs for percolate_rocks."""

from typing import Any, Dict, List, Optional

class REMDatabase:
    """REM Database with RocksDB backend and optional vector embeddings.

    Args:
        tenant_id: Tenant identifier for multi-tenancy
        path: Path to database directory
        enable_embeddings: Enable automatic embedding generation (default: True)
                          Models are cached to ~/.p8/models/ on first use
    """

    def __init__(self, tenant_id: str, path: str, enable_embeddings: bool = True) -> None: ...

    def insert(self, table: str, properties: Dict[str, Any]) -> str:
        """Insert entity into table (synchronous, no embeddings).

        Args:
            table: Table/schema name
            properties: Entity data as dictionary

        Returns:
            Entity ID as string (UUID)
        """
        ...

    async def insert_with_embedding(
        self, table: str, properties: Dict[str, Any]
    ) -> str:
        """Insert entity with automatic embedding generation.

        Generates embeddings for fields marked in schema.embedding_fields.

        Args:
            table: Table/schema name
            properties: Entity data as dictionary

        Returns:
            Entity ID as string (UUID)
        """
        ...

    def get(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity by ID.

        Args:
            entity_id: UUID string

        Returns:
            Entity data or None if not found
        """
        ...

    def delete(self, entity_id: str) -> None:
        """Delete entity (soft delete).

        Args:
            entity_id: UUID string
        """
        ...

    def scan(self) -> List[Dict[str, Any]]:
        """Scan all entities.

        Returns:
            List of entities
        """
        ...

    def scan_by_type(self, table: str) -> List[Dict[str, Any]]:
        """Scan entities by type/table.

        Args:
            table: Table/schema name

        Returns:
            List of entities of the specified type
        """
        ...

    def register_schema(
        self,
        name: str,
        schema: Dict[str, Any],
        indexed_fields: Optional[List[str]] = None,
        embedding_fields: Optional[List[str]] = None,
    ) -> None:
        """Register JSON Schema for validation.

        Args:
            name: Schema name
            schema: JSON Schema definition
            indexed_fields: Fields to index for fast lookup
            embedding_fields: Fields to automatically embed
        """
        ...

    def get_schema(self, name: str) -> Dict[str, Any]:
        """Get schema by name.

        Args:
            name: Schema name

        Returns:
            Schema definition
        """
        ...

    def list_schemas(self) -> List[str]:
        """List all registered schema names.

        Returns:
            List of schema names
        """
        ...

    def has_embeddings(self) -> bool:
        """Check if embedding provider is enabled.

        Returns:
            True if embeddings are available
        """
        ...
