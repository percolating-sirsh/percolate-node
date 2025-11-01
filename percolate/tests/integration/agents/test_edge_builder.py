"""Test EdgeBuilder agent for REM indexing.

Tests:
1. Extract edges from sample document
2. Verify edge format (dst, rel_type, properties, created_at)
3. Test lookup_entity integration
4. Verify edge merging when appending to resource
"""

import asyncio
import json
import uuid
from pathlib import Path

import pytest

from percolate.agents import AgentContext, create_agent


@pytest.fixture
def sample_document():
    """Sample document content for edge extraction."""
    return """
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


@pytest.fixture
def sample_schema_definitions():
    """Known entities that might be referenced."""
    return [
        {"name": "Design Doc 001", "uuid": "550e8400-e29b-41d4-a716-446655440001"},
        {"name": "RFC-2024-001", "uuid": "550e8400-e29b-41d4-a716-446655440002"},
        {"name": "Platform Team", "uuid": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"},
        {"name": "Database Evolution V1", "uuid": "550e8400-e29b-41d4-a716-446655440003"},
        {"name": "Pydantic-First Design", "uuid": "550e8400-e29b-41d4-a716-446655440004"},
        {"name": "Testing Guidelines", "uuid": "550e8400-e29b-41d4-a716-446655440005"},
    ]


@pytest.mark.asyncio
async def test_edge_builder_basic(sample_document):
    """Test basic edge extraction from document."""
    # Load EdgeBuilder agent schema
    agent_file = Path(__file__).parent.parent.parent.parent / "schema" / "agentlets" / "edge-builder.json"

    if not agent_file.exists():
        pytest.skip(f"EdgeBuilder schema not found at {agent_file}")

    with open(agent_file) as f:
        agent_schema = json.load(f)

    # Create agent context
    ctx = AgentContext(
        tenant_id="test",
        session_id=str(uuid.uuid4()),
        default_model="claude-sonnet-4-20250514",
    )

    # Create agent
    agent = await create_agent(
        context=ctx,
        agent_schema_override=agent_schema,
    )

    # Run edge extraction
    prompt = f"""Extract relationship edges from the following document:

{sample_document}

Focus on clear, explicit relationships like:
- References to other documents
- Authorship information
- Dependencies
- Related documents

Generate edges in the inline edge format."""

    result = await agent.run(prompt)

    # Verify result structure
    assert hasattr(result, 'output'), "Result should have output attribute"
    output = result.output.model_dump()

    # Check required fields
    assert 'edges' in output, "Output should contain 'edges' array"
    assert 'summary' in output, "Output should contain 'summary' object"

    edges = output['edges']
    summary = output['summary']

    # Verify edges were extracted
    assert len(edges) > 0, "Should extract at least one edge"
    print(f"\n✓ Extracted {len(edges)} edges")

    # Verify edge format
    for i, edge in enumerate(edges):
        print(f"\nEdge {i+1}:")
        print(f"  dst: {edge['dst']}")
        print(f"  rel_type: {edge['rel_type']}")
        print(f"  properties: {edge.get('properties', {})}")
        print(f"  created_at: {edge['created_at']}")

        # Validate required fields
        assert 'dst' in edge, "Edge must have dst field"
        assert 'rel_type' in edge, "Edge must have rel_type field"
        assert 'created_at' in edge, "Edge must have created_at field"

        # Validate dst is UUID format
        try:
            uuid.UUID(edge['dst'])
        except ValueError:
            pytest.fail(f"Edge dst must be valid UUID, got: {edge['dst']}")

        # Validate rel_type is from allowed list
        valid_rel_types = [
            "references", "authored_by", "depends_on", "implements",
            "extends", "supersedes", "related_to", "part_of",
            "mentions", "cites", "derived_from"
        ]
        assert edge['rel_type'] in valid_rel_types, f"Invalid rel_type: {edge['rel_type']}"

        # Validate properties (optional but should be dict if present)
        if 'properties' in edge:
            assert isinstance(edge['properties'], dict), "Edge properties must be dict"

            # Check for confidence score
            if 'confidence' in edge['properties']:
                conf = edge['properties']['confidence']
                assert 0.0 <= conf <= 1.0, f"Confidence must be 0.0-1.0, got: {conf}"

    # Verify summary
    assert 'total_edges' in summary, "Summary must have total_edges"
    assert 'relationship_types' in summary, "Summary must have relationship_types"
    assert 'avg_confidence' in summary, "Summary must have avg_confidence"

    assert summary['total_edges'] == len(edges), "Summary total_edges should match edges array length"
    assert 0.0 <= summary['avg_confidence'] <= 1.0, "Average confidence must be 0.0-1.0"

    print(f"\n✓ Summary:")
    print(f"  Total edges: {summary['total_edges']}")
    print(f"  Relationship types: {summary['relationship_types']}")
    print(f"  Average confidence: {summary['avg_confidence']:.2f}")


@pytest.mark.asyncio
async def test_edge_appending():
    """Test appending edges to an existing resource."""
    from rem_db import Database

    db = Database()

    # Create a sample resource
    resource_data = {
        "name": "Architecture Decision: Use REM Database",
        "content": "This document describes our decision...",
        "uri": "docs/architecture/rem-database.md",
        "chunk_ordinal": 0,
    }

    # Insert resource
    resource_id = db.insert("resources", resource_data)
    print(f"\n✓ Created resource: {resource_id}")

    # Simulate edges extracted by EdgeBuilder agent
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
    assert resource is not None, "Resource should exist"

    # Append edges to resource (merge with existing)
    existing_edges = resource.get("edges", [])
    resource["edges"] = existing_edges + extracted_edges

    # Save updated resource (upsert with edge merging)
    resource_id_2 = db.insert("resources", resource)

    # Verify UUID unchanged (upsert worked)
    assert resource_id == resource_id_2, "UUID should be unchanged (deterministic upsert)"
    print(f"✓ UUID unchanged: {resource_id}")

    # Verify edges were saved
    updated_resource = db.get(resource_id)
    assert updated_resource is not None

    saved_edges = updated_resource.get("edges", [])
    assert len(saved_edges) == len(extracted_edges), f"Should have {len(extracted_edges)} edges"

    print(f"✓ Saved {len(saved_edges)} edges:")
    for edge in saved_edges:
        print(f"  - {edge['rel_type']} → {edge['dst'][:8]}...")


if __name__ == "__main__":
    # Run basic test
    asyncio.run(test_edge_builder_basic("""
# Architecture Decision: Use REM Database

## References
- Design Doc 001: Initial database requirements
- RFC-2024-001: Knowledge graph specification

## Authored By
Platform Team
"""))

    # Run appending test
    asyncio.run(test_edge_appending())
