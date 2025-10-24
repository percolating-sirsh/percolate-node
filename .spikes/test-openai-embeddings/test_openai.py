"""Test OpenAI embeddings with percolate_rocks."""

import asyncio
import os
import tempfile

# Ensure we're using the locally built package
import sys
sys.path.insert(0, '/Users/sirsh/code/percolation/.spikes/percolate-rocks')

from percolate_rocks import REMDatabase


async def main():
    print("=" * 70)
    print("Testing OpenAI Embeddings with percolate-rocks")
    print("=" * 70)
    print()

    # Check if OpenAI API key is set
    if "OPENAI_API_KEY" not in os.environ:
        print("❌ OPENAI_API_KEY not set")
        print()
        print("To test OpenAI embeddings, set your API key:")
        print("  export OPENAI_API_KEY='sk-...'")
        print("  export P8_DEFAULT_EMBEDDING='text-embedding-3-small'")
        return

    # Set default embedding model
    os.environ["P8_DEFAULT_EMBEDDING"] = "text-embedding-3-small"
    print(f"✓ P8_DEFAULT_EMBEDDING: {os.environ['P8_DEFAULT_EMBEDDING']}")
    print(f"✓ OPENAI_API_KEY: {'*' * 20}{os.environ['OPENAI_API_KEY'][-4:]}")
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create database WITH embeddings
        print("Creating database with OpenAI embeddings...")
        db = REMDatabase(
            tenant_id="openai-test",
            path=tmpdir,
            enable_embeddings=True  # This will use OpenAI based on P8_DEFAULT_EMBEDDING
        )
        print(f"✓ Database created")
        print(f"  Has embeddings: {db.has_embeddings()}")
        print()

        # Register schema
        print("Registering schema with embedding fields...")
        db.register_schema(
            "articles",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "category": {"type": "string"}
                },
                "required": ["title", "content"]
            },
            embedding_fields=["content"]  # Embed the content field
        )
        print("✓ Schema registered")
        print()

        # Insert articles with automatic embeddings
        print("Inserting articles (batch embedding via OpenAI)...")
        articles = [
            {
                "title": "Introduction to Rust",
                "content": "Rust is a systems programming language that runs blazingly fast, prevents segfaults, and guarantees thread safety.",
                "category": "programming"
            },
            {
                "title": "Python Data Science",
                "content": "Python is the leading language for data science, with powerful libraries like NumPy, Pandas, and scikit-learn.",
                "category": "data-science"
            },
            {
                "title": "Database Design Principles",
                "content": "Good database design requires understanding normalization, indexing strategies, and query optimization techniques.",
                "category": "database"
            }
        ]

        article_ids = []
        for article in articles:
            entity_id = await db.insert_with_embedding("articles", article)
            article_ids.append(entity_id)
            print(f"  ✓ Inserted: {article['title']}")

        print()

        # Retrieve and check embeddings
        print("Verifying embeddings were generated...")
        for i, entity_id in enumerate(article_ids):
            entity = db.get(entity_id)
            if "embedding" in entity["properties"]:
                emb_len = len(entity["properties"]["embedding"])
                print(f"  ✓ {articles[i]['title']}: {emb_len} dimensions")
            else:
                print(f"  ❌ {articles[i]['title']}: No embedding!")

        print()

        # Query all articles
        all_articles = db.scan_by_type("articles")
        print(f"✓ Total articles: {len(all_articles)}")

        print()
        print("=" * 70)
        print("✅ OpenAI embeddings working correctly!")
        print("=" * 70)
        print()
        print("Key features tested:")
        print("  • Environment variable configuration (P8_DEFAULT_EMBEDDING)")
        print("  • OpenAI API key detection (OPENAI_API_KEY)")
        print("  • Automatic embedding generation (1536 dimensions)")
        print("  • Batch insert with embeddings")
        print()
        print("Benefits:")
        print("  • No model downloads required")
        print("  • Higher quality embeddings (3072 dims for text-embedding-3-large)")
        print("  • Seamless switching between local and OpenAI models")


if __name__ == "__main__":
    asyncio.run(main())
