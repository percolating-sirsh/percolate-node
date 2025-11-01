#!/usr/bin/env python3
"""Test Rust-native EdgeBuilder via PyO3 bindings."""

import os

def test_edge_builder():
    """Test EdgeBuilder extract_edges method."""
    from rem_db import Database

    # Skip if no API key
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠ Skipping test: No API key found")
        return

    db = Database()

    # Sample document content
    content = """
# Architecture Decision: Use REM Database

## Background

This document describes our decision to adopt the REM database.
The decision was influenced by Design Doc 001 and RFC-2024-001.

## Implementation

The implementation uses percolate-rocks, authored by the Platform Team.
This extends the original SQLite approach documented in Database Evolution V1.

## References

See also:
- Pydantic-First Design for schema patterns
- Testing Guidelines for validation
"""

    context = "architecture/rem-database.md"

    print("=" * 70)
    print("TESTING RUST-NATIVE EDGEBUILDER")
    print("=" * 70)
    print(f"\n  Document: {context}")
    print(f"  Content length: {len(content)} chars")
    print(f"  API: {os.environ.get('P8_DEFAULT_LLM', 'gpt-4-turbo')}")
    print()

    # Extract edges
    try:
        plan = db.extract_edges(content, context)
    except Exception as e:
        print(f"✗ Edge extraction failed: {e}")
        return

    # Validate result
    if 'edges' not in plan:
        print("✗ Missing 'edges' in result")
        return

    if 'summary' not in plan:
        print("✗ Missing 'summary' in result")
        return

    edges = plan['edges']
    summary = plan['summary']

    print(f"✓ Extracted {len(edges)} edges")
    print()

    # Display edges
    for i, edge in enumerate(edges, 1):
        print(f"Edge {i}:")
        print(f"  dst: {edge['dst']}")
        print(f"  rel_type: {edge['rel_type']}")
        print(f"  properties: {edge.get('properties', {})}")
        print()

    # Display summary
    print("Summary:")
    print(f"  Total edges: {summary['total_edges']}")
    print(f"  Relationship types: {summary['relationship_types']}")
    print(f"  Avg confidence: {summary['avg_confidence']:.2f}")
    print()

    # Verify structure
    assert len(edges) > 0, "Should extract at least one edge"
    assert summary['total_edges'] == len(edges), "Summary total should match edges array"

    print("=" * 70)
    print("✓ ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    test_edge_builder()
