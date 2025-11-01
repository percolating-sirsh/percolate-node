#!/usr/bin/env python3
"""Verify Percolating Plants database and test MCP tools."""

import os
import sys
import asyncio
from pathlib import Path

# Set up environment for percolating-plants tenant
TENANT_ID = "percolating-plants"
DB_PATH = os.path.expanduser("~/.p8/percolating-plants-db")

os.environ["P8_DB_PATH"] = DB_PATH
os.environ["P8_TENANT_ID"] = TENANT_ID

# Check for API keys in environment (don't override if already set)
if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("P8_OPENAI_API_KEY"):
    print("ERROR: OPENAI_API_KEY not found in environment")
    print("Please set it first: export OPENAI_API_KEY='your-key'")
    sys.exit(1)

# Add parent directory to path to import percolate modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "percolate" / "src"))

from percolate.mcplib.tools.search import search_knowledge_base


async def test_search_tools():
    """Test search_knowledge_base MCP tool with percolating-plants data."""
    print(f"\n{'='*70}")
    print(f"Testing MCP Tools with Percolating Plants Database")
    print(f"{'='*70}")
    print(f"Database: {DB_PATH}")
    print(f"Tenant: {TENANT_ID}\n")

    # Test 1: Search for low maintenance plants
    print("Test 1: Search for low maintenance plants...")
    result1 = await search_knowledge_base(
        query="low maintenance indoor plants easy care",
        tenant_id=TENANT_ID,
        limit=5,
        schema="resources"
    )
    print(f"  Found {result1['total']} results")
    if result1['results']:
        print(f"  Top result: {result1['results'][0]['entity'].get('name', 'N/A')}")
        print(f"  Score: {result1['results'][0]['score']:.4f}")
        if 'care_level' in result1['results'][0]['entity']:
            print(f"  Care level: {result1['results'][0]['entity']['care_level']}")
    print()

    # Test 2: Search for Monstera product
    print("Test 2: Search for Monstera Deliciosa...")
    result2 = await search_knowledge_base(
        query="Monstera Deliciosa large statement plant",
        tenant_id=TENANT_ID,
        limit=5,
        schema="resources"
    )
    print(f"  Found {result2['total']} results")
    if result2['results']:
        print(f"  Top result: {result2['results'][0]['entity'].get('name', 'N/A')}")
        print(f"  Score: {result2['results'][0]['score']:.4f}")
        if 'price_gbp' in result2['results'][0]['entity']:
            print(f"  Price: £{result2['results'][0]['entity']['price_gbp']}")
    print()

    # Test 3: Search for bright indirect light plants
    print("Test 3: Search for bright indirect light plants...")
    result3 = await search_knowledge_base(
        query="bright indirect light plants",
        tenant_id=TENANT_ID,
        limit=5,
        schema="resources"
    )
    print(f"  Found {result3['total']} results")
    if result3['results']:
        print(f"  Top result: {result3['results'][0]['entity'].get('name', 'N/A')}")
        print(f"  Score: {result3['results'][0]['score']:.4f}")
    print()

    # Test 4: Search for suppliers
    print("Test 4: Search for suppliers...")
    result4 = await search_knowledge_base(
        query="supplier nursery",
        tenant_id=TENANT_ID,
        limit=3,
        schema="resources"
    )
    print(f"  Found {result4['total']} results")
    if result4['results']:
        print(f"  Top result: {result4['results'][0]['entity'].get('name', 'N/A')}")
        print(f"  Score: {result4['results'][0]['score']:.4f}")
    print()

    # Test 5: Search for Pink Princess (rare plant)
    print("Test 5: Search for Pink Princess rare plant...")
    result5 = await search_knowledge_base(
        query="Pink Princess Philodendron rare",
        tenant_id=TENANT_ID,
        limit=3,
        schema="resources"
    )
    print(f"  Found {result5['total']} results")
    if result5['results']:
        print(f"  Top result: {result5['results'][0]['entity'].get('name', 'N/A')}")
        print(f"  Score: {result5['results'][0]['score']:.4f}")
        if 'price_gbp' in result5['results'][0]['entity']:
            print(f"  Price: £{result5['results'][0]['entity']['price_gbp']}")
        if 'stock_level' in result5['results'][0]['entity']:
            print(f"  Stock: {result5['results'][0]['entity']['stock_level']} units")
    print()

    print(f"{'='*70}")
    print(f"All MCP tool tests completed!")
    print(f"{'='*70}\n")


def main():
    """Run all tests."""
    asyncio.run(test_search_tools())


if __name__ == "__main__":
    main()
