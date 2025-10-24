"""Test Python bindings for percolate_rocks."""

import asyncio
import tempfile
import shutil
from pathlib import Path

from percolate_rocks import REMDatabase


def test_basic_operations():
    """Test basic database operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create database
        db = REMDatabase(tenant_id="test-tenant", path=tmpdir)
        print("✓ Created database")

        # Register schema
        db.register_schema(
            "resources",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "content": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "content"]
            },
            indexed_fields=["name"],
            embedding_fields=["content"]
        )
        print("✓ Registered schema")

        # List schemas
        schemas = db.list_schemas()
        assert "resources" in schemas
        print(f"✓ Schemas: {schemas}")

        # Get schema
        schema = db.get_schema("resources")
        assert schema["json_schema"]["type"] == "object"
        assert schema["name"] == "resources"
        print("✓ Retrieved schema")

        # Insert entity
        entity_id = db.insert(
            "resources",
            {
                "name": "Test Document",
                "content": "This is a test document about Rust and Python integration",
                "tags": ["test", "demo"]
            }
        )
        print(f"✓ Inserted entity: {entity_id}")

        # Get entity
        entity = db.get(entity_id)
        assert entity is not None
        assert entity["properties"]["name"] == "Test Document"
        print(f"✓ Retrieved entity: {entity['properties']['name']}")

        # Scan all entities
        entities = db.scan()
        assert len(entities) == 1
        print(f"✓ Scanned {len(entities)} entities")

        # Scan by type
        resources = db.scan_by_type("resources")
        assert len(resources) == 1
        print(f"✓ Scanned by type: {len(resources)} resources")

        # Check embeddings
        has_embeddings = db.has_embeddings()
        assert has_embeddings is True
        print(f"✓ Has embeddings: {has_embeddings}")

        # Delete entity
        db.delete(entity_id)
        print(f"✓ Deleted entity: {entity_id}")

        # Verify soft deletion (entity still exists but has deleted_at)
        deleted_entity = db.get(entity_id)
        assert deleted_entity is not None
        assert "deleted_at" in deleted_entity
        print("✓ Verified soft deletion")


async def test_async_embeddings():
    """Test async embedding generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create database
        db = REMDatabase(tenant_id="async-test", path=tmpdir)
        print("\n✓ Created database for async test")

        # Register schema
        db.register_schema(
            "resources",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["name", "content"]
            },
            embedding_fields=["content"]
        )
        print("✓ Registered schema with embedding fields")

        # Insert with automatic embedding
        entity_id = await db.insert_with_embedding(
            "resources",
            {
                "name": "Rust Document",
                "content": "Rust is a systems programming language focused on safety and performance"
            }
        )
        print(f"✓ Inserted entity with embedding: {entity_id}")

        # Verify embedding was generated
        entity = db.get(entity_id)
        assert entity is not None
        assert "embedding" in entity["properties"]
        embedding = entity["properties"]["embedding"]
        assert isinstance(embedding, list)
        assert len(embedding) == 384  # MiniLM-L6-v2 dimension
        print(f"✓ Embedding generated: {len(embedding)} dimensions")

        # Insert another document
        entity_id2 = await db.insert_with_embedding(
            "resources",
            {
                "name": "Python Document",
                "content": "Python is a high-level interpreted language known for simplicity"
            }
        )
        print(f"✓ Inserted second entity: {entity_id2}")

        # Verify both entities exist
        entities = db.scan_by_type("resources")
        assert len(entities) == 2
        print(f"✓ Total entities: {len(entities)}")


def test_validation():
    """Test schema validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="validation-test", path=tmpdir)

        # Register schema
        db.register_schema(
            "strict_schema",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer", "minimum": 0}
                },
                "required": ["name", "age"]
            }
        )
        print("\n✓ Registered strict schema")

        # Valid insert
        entity_id = db.insert(
            "strict_schema",
            {"name": "Alice", "age": 30}
        )
        print(f"✓ Valid insert: {entity_id}")

        # Invalid insert (missing required field)
        try:
            db.insert("strict_schema", {"name": "Bob"})
            assert False, "Should have raised validation error"
        except RuntimeError as e:
            assert "Validation error" in str(e)
            print("✓ Validation caught missing required field")

        # Invalid insert (wrong type)
        try:
            db.insert("strict_schema", {"name": "Charlie", "age": "thirty"})
            assert False, "Should have raised validation error"
        except RuntimeError as e:
            assert "Validation error" in str(e)
            print("✓ Validation caught wrong type")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Python Bindings for percolate-rocks")
    print("=" * 60)

    # Test basic operations
    print("\n[Test 1: Basic Operations]")
    test_basic_operations()

    # Test async embeddings
    print("\n[Test 2: Async Embeddings]")
    asyncio.run(test_async_embeddings())

    # Test validation
    print("\n[Test 3: Schema Validation]")
    test_validation()

    print("\n" + "=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)
