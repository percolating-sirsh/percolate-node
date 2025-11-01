#!/usr/bin/env python3
"""Test REM query planning for Percolating Plants (plan-only, no execution).

This script tests natural language → query plan translation WITHOUT requiring
API keys for search execution. It only tests the query planning logic.

Run:
    python test_query_planning_simple.py
"""

import os
import sys
from pathlib import Path

# Set up environment for percolating-plants tenant
TENANT_ID = "percolating-plants"
DB_PATH = os.path.expanduser("~/.p8/percolating-plants-db")

os.environ["P8_DB_PATH"] = DB_PATH
os.environ["P8_TENANT_ID"] = TENANT_ID

# Try to use rem_db directly (Rust planner)
try:
    from rem_db import Database
    print("Using Rust query planner (rem_db)")
    USE_RUST = True
except ImportError:
    print("rem_db not available, install with: cd percolate-rocks && maturin develop")
    sys.exit(1)


# Test queries organized by category
TEST_QUERIES = {
    "Semantic Search": [
        ("low maintenance indoor plants for beginners", "resources"),
        ("plants that need bright indirect light", "resources"),
        ("rare variegated plants", "resources"),
        ("large statement plants for living room", "resources"),
    ],
    "Entity Lookup": [
        ("product PP-1001-SM", None),
        ("Monstera Deliciosa", None),
        ("supplier SUP-001", None),
        ("Les Jardins de Provence", None),
    ],
    "Relationship Queries": [
        ("who supplies Monstera plants", "resources"),
        ("all products from Les Jardins de Provence", "resources"),
        ("customers who bought Pink Princess", "resources"),
    ],
    "Hybrid Queries (Semantic + Filters)": [
        ("customer emails about plant care from last month", "resources"),
        ("low stock plants under 20 pounds", "resources"),
        ("recent blog posts about Monstera care", "resources"),
    ],
    "SQL Queries": [
        ("all plants in stock", "resources"),
        ("products under 30 pounds", "resources"),
    ],
}


def test_query_plan(query: str, schema: str | None, db: Database):
    """Test a single query plan generation.

    Args:
        query: Natural language query
        schema: Schema hint (or None)
        db: Database instance
    """
    print(f"\n{'='*70}")
    print(f"Query: {query}")
    if schema:
        print(f"Schema: {schema}")
    print(f"{'='*70}")

    # Generate query plan (Rust)
    plan = db.plan_query(query, schema)

    # Print results
    print(f"\n  Query Type: {plan['query_type']}")
    print(f"  Confidence: {plan['confidence']:.2f}")
    print(f"  Execution Mode: {plan['execution_mode']}")

    print(f"\n  Primary Query:")
    primary = plan['primary_query']
    print(f"    Dialect: {primary['dialect']}")
    print(f"    Query: {primary['query_string'][:200]}")
    if primary['parameters']:
        print(f"    Parameters:")
        for key, value in primary['parameters'].items():
            if isinstance(value, str) and len(value) > 60:
                print(f"      {key}: {value[:60]}...")
            else:
                print(f"      {key}: {value}")

    print(f"\n  Reasoning: {plan['reasoning'][:200]}...")

    if plan.get('explanation'):
        print(f"\n  Explanation: {plan['explanation'][:150]}...")

    if plan.get('fallback_queries'):
        print(f"\n  Fallbacks: {len(plan['fallback_queries'])}")
        for i, fallback in enumerate(plan['fallback_queries'][:3], 1):
            print(f"    {i}. Trigger: {fallback['trigger']}, Confidence: {fallback['confidence']:.2f}")

    print(f"\n  ✓ Query plan generated")

    return plan


def main():
    """Run all query planning tests."""
    print(f"\n{'#'*70}")
    print(f"# REM Query Planning Tests - Percolating Plants")
    print(f"{'#'*70}")
    print(f"Database: {DB_PATH}")
    print(f"Tenant: {TENANT_ID}")
    print(f"Available Schemas: resources, documents")
    print(f"API Keys Required: None (plan-only mode)")

    # Initialize database
    db = Database()

    total_tests = 0
    successful = 0

    # Test each category
    for category, queries in TEST_QUERIES.items():
        print(f"\n{'#'*70}")
        print(f"# {category}")
        print(f"{'#'*70}")

        for query, schema in queries:
            try:
                plan = test_query_plan(query, schema, db)
                successful += 1
            except Exception as e:
                print(f"\n  ✗ Error: {e}")

            total_tests += 1

    # Summary
    print(f"\n{'#'*70}")
    print(f"# Summary")
    print(f"{'#'*70}")
    print(f"Total tests: {total_tests}")
    print(f"Successful: {successful}")
    print(f"Failed: {total_tests - successful}")
    print(f"\n{'#'*70}\n")


if __name__ == "__main__":
    main()
