"""Test natural language query builder - simple validation."""

import json
import os
from pathlib import Path

from rem_db import REMDatabase

# Check if API key is set
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("❌ OPENAI_API_KEY not set - cannot test LLM query builder")
    print("Set OPENAI_API_KEY environment variable to test")
    exit(1)

# Set up test database
db_path = Path("/tmp/test_nl_simple")
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
]

for res in resources:
    resource_id = db.insert("resources", res)
    print(f"  ✓ {res['name']}")

# Wait for embeddings
print("\nGenerating embeddings...")
db.wait_for_worker(timeout=10.0)
print("  ✓ Embeddings ready")

# Test single query
print("\n" + "="*60)
print("Testing Natural Language Query")
print("="*60)

query = "find resources about programming"
print(f"\nQuery: '{query}'")

try:
    result = db.query_natural_language(query, "resources")

    print(f"\n✓ Generated SQL:")
    print(f"  {result['query']}")
    print(f"\n✓ Query Type: {result['query_type']}")
    print(f"✓ Confidence: {result['confidence']:.2f}")

    if result['explanation']:
        print(f"\nExplanation:")
        print(f"  {result['explanation']}")

    print(f"\n✓ Results ({len(result['results'])}):")
    for row in result['results']:
        print(f"  - {row.get('name', 'N/A')}")
        if '_score' in row:
            print(f"    Similarity: {row['_score']:.4f}")

    print(f"\n✓ Execution stages: {result['stages']}")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

db.close()
print("\n✅ Test complete!")
