"""Basic usage example for percolate_rocks Python bindings."""

import asyncio
import tempfile
from percolate_rocks import REMDatabase


async def main():
    """Demonstrate basic database operations."""

    # Create temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        print("Creating database...")
        db = REMDatabase(tenant_id="demo", path=tmpdir)
        print(f"✓ Database created at {tmpdir}")
        print(f"  Has embeddings: {db.has_embeddings()}\n")

        # Register schema
        print("Registering schema...")
        db.register_schema(
            "articles",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "author": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["title", "content", "author"]
            },
            indexed_fields=["title", "author"],
            embedding_fields=["content"]
        )
        print("✓ Schema registered\n")

        # Insert articles with embeddings
        print("Inserting articles with embeddings...")

        articles = [
            {
                "title": "Introduction to Rust",
                "content": "Rust is a systems programming language that runs blazingly fast, prevents segfaults, and guarantees thread safety.",
                "author": "Alice",
                "tags": ["rust", "programming", "systems"]
            },
            {
                "title": "Python for Data Science",
                "content": "Python has become the lingua franca of data science, with libraries like NumPy, Pandas, and Scikit-learn.",
                "author": "Bob",
                "tags": ["python", "data-science", "ml"]
            },
            {
                "title": "Building with RocksDB",
                "content": "RocksDB is an embeddable persistent key-value store for fast storage, optimized for flash and RAM.",
                "author": "Charlie",
                "tags": ["rocksdb", "database", "storage"]
            }
        ]

        article_ids = []
        for article in articles:
            entity_id = await db.insert_with_embedding("articles", article)
            article_ids.append(entity_id)
            print(f"  ✓ Inserted: {article['title']} ({entity_id})")

        print()

        # Retrieve and display articles
        print("Retrieving articles...")
        for i, entity_id in enumerate(article_ids):
            entity = db.get(entity_id)
            title = entity["properties"]["title"]
            author = entity["properties"]["author"]
            embedding_len = len(entity["properties"]["embedding"])
            print(f"  {i+1}. {title} by {author}")
            print(f"     Embedding: {embedding_len} dimensions")

        print()

        # Scan all articles
        all_articles = db.scan_by_type("articles")
        print(f"Total articles in database: {len(all_articles)}")

        print()

        # List schemas
        schemas = db.list_schemas()
        print(f"Registered schemas: {schemas}")

        print()

        # Get schema details
        schema = db.get_schema("articles")
        print(f"Schema 'articles':")
        print(f"  Name: {schema['name']}")
        print(f"  Indexed fields: {schema['indexed_fields']}")
        print(f"  Embedding fields: {schema['embedding_fields']}")
        print(f"  Required properties: {schema['json_schema']['required']}")

        print()

        # Delete an article
        print(f"Deleting article: {articles[0]['title']}...")
        db.delete(article_ids[0])
        deleted = db.get(article_ids[0])
        print(f"  ✓ Deleted at: {deleted['deleted_at']}")

        print()
        print("✓ Demo complete!")


if __name__ == "__main__":
    asyncio.run(main())
