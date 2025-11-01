#!/usr/bin/env python3
"""Test REM query planning for Percolating Plants knowledge base.

This script tests natural language queries and the generated query plans
for the percolating-plants database.

Test coverage:
- Semantic searches (find plants by characteristics)
- Entity lookups (product codes, supplier IDs)
- Relationship queries (supplier relationships)
- Hybrid queries (semantic + time filters)
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import Any

# Set up environment for percolating-plants tenant
TENANT_ID = "percolating-plants"
DB_PATH = os.path.expanduser("~/.p8/percolating-plants-db")

os.environ["P8_DB_PATH"] = DB_PATH
os.environ["P8_TENANT_ID"] = TENANT_ID

# Check for API keys
if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("P8_OPENAI_API_KEY"):
    print("ERROR: OPENAI_API_KEY not found in environment")
    print("Please set it first: export OPENAI_API_KEY='your-key'")
    sys.exit(1)

if not os.environ.get("CEREBRAS_API_KEY"):
    print("WARNING: CEREBRAS_API_KEY not found - using default model for query planning")
    print("For fast query planning, set: export CEREBRAS_API_KEY='your-key'")

# Add parent directory to path to import percolate modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "percolate" / "src"))

from percolate.agents.query_planner import plan_query
from percolate.memory.query_builder import QueryBuilder
from percolate.mcplib.tools.search import search_knowledge_base


# Test queries organized by category
TEST_QUERIES = {
    "semantic_search": [
        {
            "query": "low maintenance indoor plants for beginners",
            "description": "Semantic search for plant characteristics",
            "expected_type": "search",
            "schema": "resources",
        },
        {
            "query": "plants that need bright indirect light",
            "description": "Semantic search by light requirements",
            "expected_type": "search",
            "schema": "resources",
        },
        {
            "query": "rare variegated plants",
            "description": "Semantic search for rarity",
            "expected_type": "search",
            "schema": "resources",
        },
        {
            "query": "large statement plants for living room",
            "description": "Semantic search with size/use context",
            "expected_type": "search",
            "schema": "resources",
        },
    ],
    "entity_lookup": [
        {
            "query": "product PP-1001-SM",
            "description": "Direct product code lookup",
            "expected_type": "lookup",
            "schema": None,
        },
        {
            "query": "Monstera Deliciosa",
            "description": "Product name lookup",
            "expected_type": "lookup",
            "schema": None,
        },
        {
            "query": "supplier SUP-001",
            "description": "Supplier ID lookup",
            "expected_type": "lookup",
            "schema": None,
        },
        {
            "query": "Les Jardins de Provence",
            "description": "Supplier name lookup",
            "expected_type": "lookup",
            "schema": None,
        },
    ],
    "relationship_queries": [
        {
            "query": "who supplies Monstera plants",
            "description": "Find supplier for product (traversal)",
            "expected_type": "traverse",
            "schema": "resources",
        },
        {
            "query": "all products from Les Jardins de Provence",
            "description": "Find products from supplier",
            "expected_type": "traverse",
            "schema": "resources",
        },
        {
            "query": "customers who bought Pink Princess",
            "description": "Customer-product relationships",
            "expected_type": "traverse",
            "schema": "resources",
        },
    ],
    "hybrid_queries": [
        {
            "query": "customer emails about plant care from last month",
            "description": "Semantic + time filter",
            "expected_type": "hybrid",
            "schema": "resources",
        },
        {
            "query": "low stock plants under 20 pounds",
            "description": "Semantic + attribute filter",
            "expected_type": "hybrid",
            "schema": "resources",
        },
        {
            "query": "recent blog posts about Monstera care",
            "description": "Semantic + recency filter",
            "expected_type": "hybrid",
            "schema": "resources",
        },
    ],
    "sql_queries": [
        {
            "query": "all plants in stock",
            "description": "SQL filter by stock status",
            "expected_type": "sql",
            "schema": "resources",
        },
        {
            "query": "products under 30 pounds",
            "description": "SQL price filter",
            "expected_type": "sql",
            "schema": "resources",
        },
    ],
}


async def test_query_plan(
    query: str,
    description: str,
    expected_type: str | None,
    schema: str | None
) -> dict[str, Any]:
    """Test a single query plan generation.

    Args:
        query: Natural language query
        description: Human description of test
        expected_type: Expected query type (or None to skip check)
        schema: Schema hint for the planner

    Returns:
        Dictionary with test results
    """
    print(f"\n{'='*70}")
    print(f"Query: {query}")
    print(f"Test: {description}")
    print(f"{'='*70}")

    # Generate query plan
    plan = await plan_query(
        query,
        available_schemas=["resources", "documents"],
        schema_hint=schema
    )

    # Build executable query
    builder = QueryBuilder()
    try:
        executable_query = builder.build(
            plan.query_type,
            plan.primary_query.parameters
        )
    except Exception as e:
        executable_query = f"ERROR: {e}"

    # Print results
    print(f"\n  Query Type: {plan.query_type}")
    print(f"  Confidence: {plan.confidence:.2f}")
    print(f"  Execution Mode: {plan.execution_mode}")

    print(f"\n  Parameters:")
    for key, value in plan.primary_query.parameters.items():
        if isinstance(value, str) and len(value) > 60:
            print(f"    {key}: {value[:60]}...")
        else:
            print(f"    {key}: {value}")

    print(f"\n  Executable Query:")
    for line in executable_query.split('\n'):
        print(f"    {line}")

    print(f"\n  Reasoning: {plan.reasoning[:150]}...")

    if plan.explanation:
        print(f"\n  Explanation: {plan.explanation[:150]}...")

    if plan.fallback_queries:
        print(f"\n  Fallbacks: {len(plan.fallback_queries)}")
        for i, fallback in enumerate(plan.fallback_queries, 1):
            print(f"    {i}. {fallback.trigger} (conf: {fallback.confidence:.2f})")

    # Check expectation
    if expected_type and plan.query_type != expected_type:
        print(f"\n  ⚠️  WARNING: Expected {expected_type}, got {plan.query_type}")
    else:
        print(f"\n  ✓ Query plan generated successfully")

    return {
        "query": query,
        "description": description,
        "plan": plan,
        "executable_query": executable_query,
        "matches_expectation": not expected_type or plan.query_type == expected_type,
    }


async def test_query_execution(query: str, schema: str = "resources") -> dict[str, Any]:
    """Execute a query and show actual results.

    Args:
        query: Natural language query
        schema: Schema to search

    Returns:
        Search results
    """
    print(f"\n  Executing search...")

    result = await search_knowledge_base(
        query=query,
        tenant_id=TENANT_ID,
        limit=3,
        schema=schema
    )

    print(f"  Results: {result['total']} found")

    if result['results']:
        print(f"\n  Top 3 results:")
        for i, item in enumerate(result['results'][:3], 1):
            entity = item['entity']
            score = item['score']
            name = entity.get('name', entity.get('product_code', 'N/A'))
            content = entity.get('content', '')[:80]
            print(f"    {i}. {name} (score: {score:.3f})")
            print(f"       {content}...")

    return result


async def main():
    """Run all query planning tests."""
    print(f"\n{'#'*70}")
    print(f"# REM Query Planning Tests - Percolating Plants")
    print(f"{'#'*70}")
    print(f"Database: {DB_PATH}")
    print(f"Tenant: {TENANT_ID}")
    print(f"Available Schemas: resources, documents")

    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "by_category": {},
    }

    # Test each category
    for category, queries in TEST_QUERIES.items():
        print(f"\n{'#'*70}")
        print(f"# Category: {category.replace('_', ' ').title()}")
        print(f"{'#'*70}")

        category_results = []

        for test_case in queries:
            result = await test_query_plan(
                query=test_case["query"],
                description=test_case["description"],
                expected_type=test_case.get("expected_type"),
                schema=test_case.get("schema")
            )

            # Execute first query from each category
            if len(category_results) == 0 and test_case.get("schema"):
                await test_query_execution(
                    query=test_case["query"],
                    schema=test_case["schema"]
                )

            category_results.append(result)
            results["total"] += 1
            if result["matches_expectation"]:
                results["passed"] += 1
            else:
                results["failed"] += 1

        results["by_category"][category] = category_results

    # Summary
    print(f"\n{'#'*70}")
    print(f"# Summary")
    print(f"{'#'*70}")
    print(f"Total tests: {results['total']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")

    for category, category_results in results["by_category"].items():
        passed = sum(1 for r in category_results if r["matches_expectation"])
        total = len(category_results)
        print(f"\n{category.replace('_', ' ').title()}: {passed}/{total}")

    print(f"\n{'#'*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
