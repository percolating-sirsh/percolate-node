#!/usr/bin/env python3
"""Test REM query planning for ACME Alpha investment analysis database.

This script tests natural language → query plan translation for investment
analysis queries.

Run:
    source ~/.bash_profile
    python test_query_planning.py
"""

import os
import sys

# Set up environment
TENANT_ID = "felix-prime"
DB_PATH = os.path.expanduser("~/.p8/acme-alpha-db")

os.environ["P8_DB_PATH"] = DB_PATH
os.environ["P8_TENANT_ID"] = TENANT_ID

try:
    from rem_db import Database
    print("Using Rust query planner (rem_db)")
except ImportError:
    print("rem_db not available")
    sys.exit(1)


# Test queries for investment analysis
TEST_QUERIES = {
    "Market Data Semantic Search": [
        ("Denver multifamily cap rates", "resources"),
        ("apartment construction starts in Texas", "resources"),
        ("office market trends post-pandemic", "resources"),
        ("industrial warehouse demand", "resources"),
    ],
    "Geographic Entity Lookup": [
        ("CBSA 31080", None),  # Denver-Aurora-Lakewood
        ("Dallas-Fort Worth metro", None),
        ("Phoenix market", None),
    ],
    "Sponsor/Lender Lookup": [
        ("Greenline Renewables track record", None),
        ("sponsor SPON-001", None),
        ("Berkshire Lending underwriting", None),
    ],
    "Time-Based Queries": [
        ("Q4 2024 cap rate trends", "resources"),
        ("recent energy PPA rates", "resources"),
        ("latest NCREIF data", "resources"),
    ],
    "Hybrid Queries (Semantic + Filters)": [
        ("Denver apartments with cap rates above 5%", "resources"),
        ("Texas industrial construction since 2023", "resources"),
        ("office properties under 50M valuation", "resources"),
    ],
    "Relationship Queries": [
        ("projects sponsored by Greenline Renewables", "resources"),
        ("markets where Berkshire Lending is active", "resources"),
        ("analysts covering multifamily", "resources"),
    ],
}


def test_query_plan(query: str, schema: str | None, db: Database):
    """Test a single query plan generation."""
    print(f"\n{'='*70}")
    print(f"Query: {query}")
    if schema:
        print(f"Schema: {schema}")
    print(f"{'='*70}")

    # Generate query plan
    plan = db.plan_query(query, schema)

    # Print results
    print(f"\n  Query Type: {plan['query_type']}")
    print(f"  Confidence: {plan['confidence']:.2f}")
    print(f"  Execution Mode: {plan['execution_mode']}")

    print(f"\n  Primary Query:")
    primary = plan['primary_query']
    print(f"    Dialect: {primary['dialect']}")
    query_str = primary['query_string']
    if len(query_str) > 200:
        print(f"    Query: {query_str[:200]}...")
    else:
        print(f"    Query: {query_str}")

    if primary['parameters']:
        print(f"    Parameters:")
        for key, value in primary['parameters'].items():
            if isinstance(value, str) and len(value) > 60:
                print(f"      {key}: {value[:60]}...")
            else:
                print(f"      {key}: {value}")

    reasoning = plan['reasoning']
    if len(reasoning) > 200:
        print(f"\n  Reasoning: {reasoning[:200]}...")
    else:
        print(f"\n  Reasoning: {reasoning}")

    if plan.get('fallback_queries'):
        print(f"\n  Fallbacks: {len(plan['fallback_queries'])}")
        for i, fallback in enumerate(plan['fallback_queries'][:3], 1):
            print(f"    {i}. Trigger: {fallback['trigger']}, Confidence: {fallback['confidence']:.2f}")

    print(f"\n  ✓ Query plan generated")

    return plan


def main():
    """Run all query planning tests."""
    print(f"\n{'#'*70}")
    print(f"# REM Query Planning Tests - ACME Alpha Investment Analysis")
    print(f"{'#'*70}")
    print(f"Database: {DB_PATH}")
    print(f"Tenant: {TENANT_ID}")
    print(f"Available Schemas: resources")
    print(f"Data: 2,299 market data points, 44 entities")

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
                import traceback
                traceback.print_exc()

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
