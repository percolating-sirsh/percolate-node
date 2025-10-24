"""Demo script showing PyPI-ready installation without model downloads."""

import tempfile
from percolate_rocks import REMDatabase


def demo_without_embeddings():
    """Show database works perfectly without embedding models."""
    print("=" * 70)
    print("Demo: Database WITHOUT embeddings (PyPI install scenario)")
    print("=" * 70)
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create database WITHOUT embeddings - no model downloads!
        print("Creating database with enable_embeddings=False...")
        db = REMDatabase(
            tenant_id="demo",
            path=tmpdir,
            enable_embeddings=False  # Key: no models needed!
        )
        print(f"✓ Database created instantly (no downloads)")
        print(f"  Has embeddings: {db.has_embeddings()}")
        print()

        # Register schema
        print("Registering schema...")
        db.register_schema(
            "documents",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "author": {"type": "string"}
                },
                "required": ["title", "content"]
            },
            indexed_fields=["title", "author"]
        )
        print("✓ Schema registered")
        print()

        # Insert documents
        print("Inserting documents...")
        docs = [
            {
                "title": "Introduction to Python",
                "content": "Python is a high-level programming language...",
                "author": "Alice"
            },
            {
                "title": "Rust Performance",
                "content": "Rust provides memory safety without garbage collection...",
                "author": "Bob"
            },
            {
                "title": "Database Design",
                "content": "Good database design is crucial for application performance...",
                "author": "Charlie"
            }
        ]

        doc_ids = []
        for doc in docs:
            doc_id = db.insert("documents", doc)
            doc_ids.append(doc_id)
            print(f"  ✓ Inserted: {doc['title']}")

        print()

        # Query documents
        print(f"Querying all documents...")
        all_docs = db.scan_by_type("documents")
        print(f"✓ Found {len(all_docs)} documents")
        print()

        # Get individual document
        print("Retrieving specific document...")
        doc = db.get(doc_ids[0])
        print(f"✓ Retrieved: {doc['properties']['title']}")
        print(f"  Author: {doc['properties']['author']}")
        print(f"  Created: {doc['created_at']}")
        print()

        print("=" * 70)
        print("✅ SUCCESS: Full database functionality without any model downloads!")
        print("=" * 70)
        print()
        print("This is perfect for:")
        print("  • Fast pip install from PyPI")
        print("  • Using external embedding services (OpenAI, Cohere, etc.)")
        print("  • Edge deployments with minimal dependencies")
        print("  • Testing and development")
        print()
        print("To enable local embeddings:")
        print("  db = REMDatabase(tenant, path, enable_embeddings=True)")
        print("  # Downloads model (~100MB) to ~/.p8/models/ on first use")


if __name__ == "__main__":
    demo_without_embeddings()
