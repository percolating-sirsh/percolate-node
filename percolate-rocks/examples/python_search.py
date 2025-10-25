#!/usr/bin/env python3
"""Example of using semantic search from Python.

Demonstrates vector embeddings and similarity search.
"""

import asyncio
from pathlib import Path
import json
import os

try:
    from rem_db import Database
    print("✓ Successfully imported rem_db")
except ImportError as e:
    print(f"✗ Failed to import rem_db: {e}")
    print("  Run: maturin develop --release")
    exit(1)


async def main():
    """Demonstrate semantic search operations."""

    # Create/open database
    db_path = Path("./python-search-db")
    print(f"\n1. Opening database at: {db_path}")
    db = Database(str(db_path))

    # Register schema with embeddings
    print("\n2. Registering schema with embedding configuration...")
    schema = {
        "title": "Article",
        "version": "1.0.0",
        "short_name": "articles",
        "description": "Articles for semantic search",
        "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"},
            "category": {"type": "string"},
            "author": {"type": "string"},
        },
        "required": ["title", "content"],
        "json_schema_extra": {
            "embedding_fields": ["content"],  # Embed the content field
            "embedding_provider": "default",  # Uses P8_DEFAULT_EMBEDDING
            "indexed_fields": ["category", "author"],
            "key_field": "title",
            "category": "user"
        }
    }

    schema_file = Path("/tmp/article_schema.json")
    schema_file.write_text(json.dumps(schema, indent=2))
    db.register_schema_from_file(str(schema_file))
    print("✓ Schema registered with embedding support")

    # Insert articles with diverse content
    print("\n3. Inserting articles...")
    articles = [
        {
            "title": "Introduction to Rust",
            "content": "Rust is a systems programming language that runs blazingly fast, prevents segfaults, and guarantees thread safety.",
            "category": "programming",
            "author": "Alice"
        },
        {
            "title": "Python Data Science",
            "content": "Python is widely used for data analysis with libraries like pandas, numpy, and matplotlib for processing datasets.",
            "category": "programming",
            "author": "Bob"
        },
        {
            "title": "Vector Databases Explained",
            "content": "Vector databases use HNSW graphs for approximate nearest neighbor search in high-dimensional spaces for similarity search.",
            "category": "database",
            "author": "Charlie"
        },
        {
            "title": "Machine Learning Basics",
            "content": "Machine learning algorithms learn patterns from data to make predictions without being explicitly programmed.",
            "category": "ml",
            "author": "Diana"
        },
        {
            "title": "Async Programming in Rust",
            "content": "Async programming in Rust uses async/await syntax and tokio runtime for building scalable network applications.",
            "category": "programming",
            "author": "Alice"
        }
    ]

    for article in articles:
        try:
            entity_id = await db.insert_async("default", "articles", article)
            print(f"  Inserted: {article['title']}")
        except Exception as e:
            print(f"  Error inserting {article['title']}: {e}")
            # Fall back to sync insert
            entity_id = db.insert("default", "articles", article)
            print(f"  Inserted (sync): {article['title']}")

    # Check if embedding provider is configured
    has_embeddings = os.getenv("P8_DEFAULT_EMBEDDING") or os.getenv("OPENAI_API_KEY")

    if has_embeddings:
        print("\n4. Performing semantic search...")
        print(f"  Embedding provider: {os.getenv('P8_DEFAULT_EMBEDDING', 'OpenAI')}")

        # Search for content about programming
        query = "systems programming and memory safety"
        print(f"\n  Query: '{query}'")

        try:
            results = await db.search_async("default", "articles", query, top_k=3)
            print(f"\n  Results ({len(results)} found):")
            for idx, (entity, score) in enumerate(results, 1):
                print(f"\n  {idx}. {entity['title']} (score: {score:.4f})")
                print(f"     Author: {entity['author']}")
                print(f"     Category: {entity['category']}")
                print(f"     Content preview: {entity['content'][:80]}...")
        except Exception as e:
            print(f"  Search error: {e}")
            print("  This is expected if embeddings haven't been generated yet")

        # Try another search
        query2 = "data analysis and visualization"
        print(f"\n  Query: '{query2}'")

        try:
            results2 = await db.search_async("default", "articles", query2, top_k=2)
            print(f"\n  Results ({len(results2)} found):")
            for idx, (entity, score) in enumerate(results2, 1):
                print(f"\n  {idx}. {entity['title']} (score: {score:.4f})")
                print(f"     Content preview: {entity['content'][:80]}...")
        except Exception as e:
            print(f"  Search error: {e}")

    else:
        print("\n⚠ Semantic search skipped - no embedding provider configured")
        print("  Set P8_DEFAULT_EMBEDDING=local:all-MiniLM-L6-v2")
        print("  or OPENAI_API_KEY for embeddings")

    # Regular SQL still works
    print("\n5. Regular SQL query...")
    sql = "SELECT title, author FROM articles WHERE category = 'programming'"
    results = db.query_sql("default", sql)
    print(f"  Programming articles ({len(results)}):")
    for article in results:
        print(f"    - {article['title']} by {article['author']}")

    print("\n✓ All operations completed!")
    print(f"\nDatabase location: {db_path}")


if __name__ == "__main__":
    # Check Python version for asyncio compatibility
    import sys
    if sys.version_info < (3, 7):
        print("This example requires Python 3.7+")
        exit(1)

    asyncio.run(main())
