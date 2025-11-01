#!/usr/bin/env python3
"""Standalone test for EdgeBuilder agent (no pytest dependency).

Tests:
1. Extract edges from sample document
2. Verify edge format
3. Test appending edges to resource
"""

import asyncio
import json
import uuid
from pathlib import Path

# Sample document for testing
SAMPLE_DOCUMENT = """
# Architecture Decision: Use REM Database

## Overview

This document describes our decision to adopt the REM (Resources-Entities-Moments) database
architecture for the Percolate project.

## Background

The decision was influenced by the following documents:
- **Design Doc 001**: Initial database requirements
- **RFC-2024-001**: Knowledge graph specification

## Implementation

The implementation will use percolate-rocks, a Rust-based embedded database.
This was authored by the Platform Team and extends the original SQLite approach
documented in "Database Evolution V1".

## Dependencies

- percolate-rocks library (Rust)
- PyO3 bindings
- RocksDB backend

## References

See also:
- "Pydantic-First Design" for schema patterns
- "Testing Guidelines" for validation approach
"""


async def test_edge_builder():
    """Test EdgeBuilder agent edge extraction."""
    print("=" * 70)
    print("TESTING EDGEBUILDER AGENT")
    print("=" * 70)

    from percolate.agents import AgentContext, create_agent

    # Load EdgeBuilder schema
    schema_path = Path(__file__).parent.parent.parent.parent / "schema" / "agentlets" / "edge-builder.json"

    if not schema_path.exists():
        print(f"\n✗ EdgeBuilder schema not found at: {schema_path}")
        return False

    print(f"\n✓ Found schema: {schema_path}")

    with open(schema_path) as f:
        agent_schema = json.load(f)

    # Create agent context
    ctx = AgentContext(
        tenant_id="test",
        session_id=str(uuid.uuid4()),
        default_model="claude-sonnet-4-20250514",
    )

    print("✓ Created agent context")

    # Create agent
    print("\nCreating EdgeBuilder agent...")
    agent = await create_agent(
        context=ctx,
        agent_schema_override=agent_schema,
    )

    print("✓ Agent created successfully")

    # Run edge extraction
    print("\n" + "=" * 70)
    print("EXTRACTING EDGES FROM SAMPLE DOCUMENT")
    print("=" * 70)

    prompt = f"""Extract relationship edges from the following document:

{SAMPLE_DOCUMENT}

Focus on clear, explicit relationships like:
- References to other documents
- Authorship information
- Dependencies
- Related documents

Generate edges in the inline edge format with valid UUIDs."""

    print("\nRunning agent...")
    result = await agent.run(prompt)

    # Verify result structure
    if not hasattr(result, 'output'):
        print("✗ Result missing output attribute")
        return False

    # Handle both string and structured output
    if isinstance(result.output, str):
        try:
            output = json.loads(result.output)
        except json.JSONDecodeError:
            print(f"✗ Failed to parse output as JSON: {result.output[:200]}")
            return False
    elif hasattr(result.output, 'model_dump'):
        output = result.output.model_dump()
    else:
        print(f"✗ Unknown output type: {type(result.output)}")
        return False

    # Check required fields
    if 'edges' not in output:
        print("✗ Output missing 'edges' array")
        return False

    if 'summary' not in output:
        print("✗ Output missing 'summary' object")
        return False

    edges = output['edges']
    summary = output['summary']

    print(f"\n✓ Extracted {len(edges)} edges")

    if len(edges) == 0:
        print("⚠ Warning: No edges extracted")
        return False

    # Verify edge format
    print("\n" + "=" * 70)
    print("VALIDATING EDGE FORMAT")
    print("=" * 70)

    all_valid = True

    for i, edge in enumerate(edges):
        print(f"\nEdge {i+1}:")
        print(f"  dst: {edge['dst']}")
        print(f"  rel_type: {edge['rel_type']}")
        print(f"  properties: {edge.get('properties', {})}")
        print(f"  created_at: {edge['created_at']}")

        # Validate required fields
        if 'dst' not in edge:
            print(f"  ✗ Missing dst field")
            all_valid = False
            continue

        if 'rel_type' not in edge:
            print(f"  ✗ Missing rel_type field")
            all_valid = False
            continue

        if 'created_at' not in edge:
            print(f"  ✗ Missing created_at field")
            all_valid = False
            continue

        # Validate UUID format
        try:
            uuid.UUID(edge['dst'])
            print(f"  ✓ Valid UUID format")
        except ValueError:
            print(f"  ✗ Invalid UUID: {edge['dst']}")
            all_valid = False
            continue

        # Validate rel_type
        valid_rel_types = [
            "references", "authored_by", "depends_on", "implements",
            "extends", "supersedes", "related_to", "part_of",
            "mentions", "cites", "derived_from"
        ]
        if edge['rel_type'] in valid_rel_types:
            print(f"  ✓ Valid rel_type")
        else:
            print(f"  ✗ Invalid rel_type: {edge['rel_type']}")
            all_valid = False

        # Validate properties (optional)
        if 'properties' in edge:
            if not isinstance(edge['properties'], dict):
                print(f"  ✗ Properties must be dict")
                all_valid = False
            else:
                # Check confidence
                if 'confidence' in edge['properties']:
                    conf = edge['properties']['confidence']
                    if 0.0 <= conf <= 1.0:
                        print(f"  ✓ Valid confidence: {conf:.2f}")
                    else:
                        print(f"  ✗ Invalid confidence: {conf}")
                        all_valid = False

    # Verify summary
    print("\n" + "=" * 70)
    print("VALIDATING SUMMARY")
    print("=" * 70)

    if 'total_edges' not in summary:
        print("✗ Summary missing total_edges")
        all_valid = False
    elif summary['total_edges'] == len(edges):
        print(f"✓ Total edges correct: {summary['total_edges']}")
    else:
        print(f"✗ Total edges mismatch: expected {len(edges)}, got {summary['total_edges']}")
        all_valid = False

    if 'relationship_types' not in summary:
        print("✗ Summary missing relationship_types")
        all_valid = False
    else:
        print(f"✓ Relationship types: {summary['relationship_types']}")

    if 'avg_confidence' not in summary:
        print("✗ Summary missing avg_confidence")
        all_valid = False
    elif 0.0 <= summary['avg_confidence'] <= 1.0:
        print(f"✓ Average confidence: {summary['avg_confidence']:.2f}")
    else:
        print(f"✗ Invalid avg_confidence: {summary['avg_confidence']}")
        all_valid = False

    # Final result
    print("\n" + "=" * 70)
    print("TEST RESULT")
    print("=" * 70)

    if all_valid:
        print("\n✓ All tests passed!")
        print(f"  - Extracted {len(edges)} valid edges")
        print(f"  - All edge formats correct")
        print(f"  - Summary validated")
        return True
    else:
        print("\n✗ Some tests failed")
        return False


async def test_edge_appending():
    """Test appending edges to resource."""
    print("\n" + "=" * 70)
    print("TESTING EDGE APPENDING TO RESOURCE")
    print("=" * 70)

    try:
        from rem_db import Database
    except ImportError:
        print("⚠ rem_db not available, skipping edge appending test")
        return True

    db = Database()

    # Create sample resource
    resource_data = {
        "name": "Architecture Decision: Use REM Database",
        "content": "This document describes our decision...",
        "uri": "docs/architecture/rem-database.md",
        "chunk_ordinal": 0,
    }

    resource_id = db.insert("resources", resource_data)
    print(f"\n✓ Created resource: {resource_id}")

    # Simulate extracted edges
    extracted_edges = [
        {
            "dst": "550e8400-e29b-41d4-a716-446655440001",
            "rel_type": "references",
            "properties": {
                "context": "Background documentation",
                "confidence": 0.95
            },
            "created_at": "2024-01-15T10:00:00Z"
        },
        {
            "dst": "550e8400-e29b-41d4-a716-446655440002",
            "rel_type": "implements",
            "properties": {
                "context": "RFC implementation",
                "confidence": 1.0
            },
            "created_at": "2024-01-15T10:00:00Z"
        }
    ]

    # Get resource and append edges
    resource = db.get(resource_id)
    if resource is None:
        print("✗ Resource not found")
        return False

    # Append edges
    existing_edges = resource.get("edges", [])
    resource["edges"] = existing_edges + extracted_edges

    # Save updated resource
    resource_id_2 = db.insert("resources", resource)

    if resource_id != resource_id_2:
        print(f"✗ UUID changed: {resource_id} → {resource_id_2}")
        return False

    print(f"✓ UUID unchanged (deterministic upsert): {resource_id}")

    # Verify edges saved
    updated_resource = db.get(resource_id)
    if updated_resource is None:
        print("✗ Updated resource not found")
        return False

    saved_edges = updated_resource.get("edges", [])
    if len(saved_edges) != len(extracted_edges):
        print(f"✗ Edge count mismatch: expected {len(extracted_edges)}, got {len(saved_edges)}")
        return False

    print(f"✓ Saved {len(saved_edges)} edges:")
    for edge in saved_edges:
        print(f"  - {edge['rel_type']} → {edge['dst'][:8]}...")

    return True


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("EDGEBUILDER AGENT TEST SUITE")
    print("=" * 70)

    # Test 1: Edge extraction
    test1_passed = await test_edge_builder()

    # Test 2: Edge appending
    test2_passed = await test_edge_appending()

    # Summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    tests_run = 2
    tests_passed = sum([test1_passed, test2_passed])

    print(f"\nTests run: {tests_run}")
    print(f"Tests passed: {tests_passed}")
    print(f"Tests failed: {tests_run - tests_passed}")

    if tests_passed == tests_run:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
