"""Percolate Rocks - REM Database with Rust backend.

A high-performance REM (Resources-Entities-Moments) database with:
- RocksDB storage backend
- Automatic embedding generation
- Vector similarity search
- JSON Schema validation
- Multi-tenant support

Example:
    ```python
    from percolate_rocks import REMDatabase

    # Create database
    db = REMDatabase(tenant_id="default", path="./my-db")

    # Register schema
    db.register_schema(
        "resources",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "content": {"type": "string"}
            }
        },
        embedding_fields=["content"]
    )

    # Insert with automatic embedding
    import asyncio
    entity_id = asyncio.run(db.insert_with_embedding(
        "resources",
        {
            "name": "Test Document",
            "content": "This is a test document about Python programming"
        }
    ))

    # Query entities
    entities = db.scan()
    ```
"""

from percolate_rocks._core import REMDatabase

__version__ = "0.1.0"
__all__ = ["REMDatabase"]
