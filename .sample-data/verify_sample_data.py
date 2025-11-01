#!/usr/bin/env python3
"""Verify ACME Alpha database and test MCP tools."""

import os
import sys
import asyncio
from pathlib import Path

# Set up environment for acme-alpha tenant
TENANT_ID = "felix-prime"
DB_PATH = os.path.expanduser("~/.p8/acme-alpha-db")

os.environ["P8_DB_PATH"] = DB_PATH
os.environ["P8_TENANT_ID"] = TENANT_ID

# Check for API keys in environment (don't override if already set)
if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("P8_OPENAI_API_KEY"):
    print("ERROR: OPENAI_API_KEY not found in environment")
    print("Please set it first: export OPENAI_API_KEY='your-key'")
    sys.exit(1)

# Add parent directory to path to import percolate modules
sys.path.insert(0, str(Path(__file__).parent.parent / "percolate" / "src"))

from percolate.mcplib.tools.search import search_knowledge_base


async def test_search_tools():
    """Test search_knowledge_base MCP tool with acme-alpha data."""
    print(f"\n{'='*70}")
    print(f"Testing MCP Tools with ACME Alpha Database")
    print(f"{'='*70}")
    print(f"Database: {DB_PATH}")
    print(f"Tenant: {TENANT_ID}\n")

    # Test 1: Search for NCREIF apartment data
    print("Test 1: Search for NCREIF apartment cap rates...")
    result1 = await search_knowledge_base(
        query="NCREIF apartment cap rate",
        tenant_id=TENANT_ID,
        limit=5,
        schema="resources"
    )
    print(f"  Found {result1['total']} results")
    if result1['results']:
        print(f"  Top result: {result1['results'][0]['entity'].get('name', 'N/A')}")
        print(f"  Score: {result1['results'][0]['score']:.4f}\n")

    # Test 2: Search for energy market data
    print("Test 2: Search for Wyoming wind energy data...")
    result2 = await search_knowledge_base(
        query="Wyoming wind PPA rates energy",
        tenant_id=TENANT_ID,
        limit=5,
        schema="resources"
    )
    print(f"  Found {result2['total']} results")
    if result2['results']:
        print(f"  Top result: {result2['results'][0]['entity'].get('name', 'N/A')}")
        print(f"  Score: {result2['results'][0]['score']:.4f}\n")

    # Test 3: Search for sponsor entities
    print("Test 3: Search for Greenline Renewables...")
    result3 = await search_knowledge_base(
        query="Greenline Renewables track record",
        tenant_id=TENANT_ID,
        limit=5,
        schema="resources"
    )
    print(f"  Found {result3['total']} results")
    if result3['results']:
        print(f"  Top result: {result3['results'][0]['entity'].get('name', 'N/A')}")
        print(f"  Score: {result3['results'][0]['score']:.4f}\n")

    # Test 4: Search for market metrics
    print("Test 4: Search for Denver population growth...")
    result4 = await search_knowledge_base(
        query="Denver population growth demographics",
        tenant_id=TENANT_ID,
        limit=5,
        schema="resources"
    )
    print(f"  Found {result4['total']} results")
    if result4['results']:
        print(f"  Top result: {result4['results'][0]['entity'].get('name', 'N/A')}")
        print(f"  Score: {result4['results'][0]['score']:.4f}\n")

    print(f"{'='*70}")
    print(f"All MCP tool tests completed successfully!")
    print(f"{'='*70}\n")


def main():
    """Run all tests."""
    asyncio.run(test_search_tools())


if __name__ == "__main__":
    main()
