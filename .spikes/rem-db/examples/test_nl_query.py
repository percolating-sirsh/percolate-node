"""Test natural language query builder."""

import os
from pathlib import Path

from rem_db import REMDatabase

# Set up test database
db_path = Path("/tmp/test_nl_query")
if db_path.exists():
    import shutil
    shutil.rmtree(db_path)

db = REMDatabase(tenant_id="default", path=str(db_path))

# Insert test data
print("Inserting test data...")
resources = [
    {
        "name": "Python Tutorial",
        "content": "Learn Python programming from scratch. Variables, functions, classes.",
    },
    {
        "name": "Rust Guide",
        "content": "Systems programming with Rust. Memory safety and performance.",
    },
    {
        "name": "JavaScript Basics",
        "content": "Web development with JavaScript. DOM manipulation and async programming.",
    },
]

for res in resources:
    resource_id = db.insert("resources", res)
    print(f"  Inserted: {res['name']} (id: {resource_id})")

# Wait for embeddings to be generated
print("\nWaiting for embeddings...")
db.wait_for_worker(timeout=10.0)

# Test queries
test_queries = [
    # Semantic search
    "find resources about programming languages",

    # Simple field lookup
    "get resource with name Python Tutorial",

    # Key-value lookup (if user provides ID)
    f"get resource {resource_id}",

    # Conceptual query
    "resources about web development",
]

# Check if API key is set
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("\n❌ OPENAI_API_KEY not set - skipping LLM tests")
    print("Set OPENAI_API_KEY to test natural language queries\n")
    db.close()
    exit(0)

print("\n" + "="*60)
print("Testing Natural Language Queries")
print("="*60)

for query in test_queries:
    print(f"\nQuery: '{query}'")
    print("-" * 60)

    try:
        result = db.query_natural_language(query, "resources")

        print(f"Generated SQL: {result['query']}")
        print(f"Query Type: {result['query_type']}")
        print(f"Confidence: {result['confidence']:.2f}")

        if result['explanation']:
            print(f"Explanation: {result['explanation']}")

        print(f"Results ({len(result['results'])}):")
        for row in result['results']:
            print(f"  - {row.get('name', 'N/A')}")
            if '_score' in row:
                print(f"    Score: {row['_score']:.4f}")

        print(f"Stages: {result['stages']}")

    except Exception as e:
        print(f"❌ Error: {e}")

db.close()
print("\n✅ Tests complete!")
