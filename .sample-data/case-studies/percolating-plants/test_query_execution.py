#!/usr/bin/env python3
"""Test REM query execution for Percolating Plants.

This script tests query planning AND execution to verify results.
"""

import os
import sys
import asyncio
from pathlib import Path

# Set up environment
TENANT_ID = "percolating-plants"
DB_PATH = os.path.expanduser("~/.p8/percolating-plants-db")

os.environ["P8_DB_PATH"] = DB_PATH
os.environ["P8_TENANT_ID"] = TENANT_ID

# Add percolate to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "percolate" / "src"))

from percolate.mcplib.tools.search import search_knowledge_base
from rem_db import Database


# Select test queries for execution
TEST_QUERIES = [
    # Semantic searches
    ("low maintenance indoor plants", "Semantic search for plant characteristics"),
    ("bright indirect light plants", "Semantic search by light requirements"),
    ("Monstera Deliciosa", "Product name search"),

    # Price filters
    ("plants under 30 pounds", "SQL price filter"),

    # Supplier search
    ("Les Jardins de Provence", "Supplier search"),
]


async def test_query(query: str, description: str, db: Database):
    """Test query planning and execution.

    Args:
        query: Natural language query
        description: Human description
        db: Database instance
    """
    print(f"\n{'='*70}")
    print(f"Query: {query}")
    print(f"Test: {description}")
    print(f"{'='*70}")

    # Step 1: Generate plan
    print(f"\n  [1] Generating query plan...")
    plan = db.plan_query(query, "resources")

    print(f"      Query Type: {plan['query_type']}")
    print(f"      Confidence: {plan['confidence']:.2f}")
    print(f"      Executable: {plan['primary_query']['query_string'][:80]}...")

    # Step 2: Execute search
    print(f"\n  [2] Executing search...")
    result = await search_knowledge_base(
        query=query,
        tenant_id=TENANT_ID,
        limit=5,
        schema="resources"
    )

    print(f"      Results: {result['total']} found")

    # Step 3: Show results
    if result['results']:
        print(f"\n  [3] Top 3 results:")
        for i, item in enumerate(result['results'][:3], 1):
            entity = item['entity']
            score = item['score']

            name = entity.get('name', entity.get('product_code', 'N/A'))
            category = entity.get('category', entity.get('type', 'N/A'))

            print(f"\n      {i}. {name}")
            print(f"         Category: {category}")
            print(f"         Score: {score:.3f}")

            # Show relevant fields
            if 'care_level' in entity:
                print(f"         Care Level: {entity['care_level']}")
            if 'light_requirements' in entity:
                print(f"         Light: {entity['light_requirements']}")
            if 'price_gbp' in entity:
                print(f"         Price: £{entity['price_gbp']}")
            if 'stock_level' in entity:
                print(f"         Stock: {entity['stock_level']}")
    else:
        print(f"\n  [3] No results found")

    print(f"\n  ✓ Test complete")

    return {
        "query": query,
        "plan": plan,
        "result_count": result['total'],
        "success": True
    }


async def main():
    """Run execution tests."""
    print(f"\n{'#'*70}")
    print(f"# REM Query Execution Tests - Percolating Plants")
    print(f"{'#'*70}")
    print(f"Database: {DB_PATH}")
    print(f"Tenant: {TENANT_ID}")

    # Initialize database
    db = Database()

    results = []
    for query, description in TEST_QUERIES:
        try:
            result = await test_query(query, description, db)
            results.append(result)
        except Exception as e:
            print(f"\n  ✗ Error: {e}")
            import traceback
            traceback.print_exc()

    # Summary
    print(f"\n{'#'*70}")
    print(f"# Summary")
    print(f"{'#'*70}")
    print(f"Total queries: {len(TEST_QUERIES)}")
    print(f"Successful: {len(results)}")
    print(f"Failed: {len(TEST_QUERIES) - len(results)}")

    print(f"\n  Result counts:")
    for result in results:
        print(f"    {result['query']}: {result['result_count']} results")

    print(f"\n{'#'*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
