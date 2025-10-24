"""Basic functionality tests for REM database."""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from rem_db import (
    And,
    Contains,
    Direction,
    Edge,
    Entity,
    Eq,
    Gt,
    In,
    Moment,
    Order,
    Query,
    REMDatabase,
    Resource,
)


@pytest.fixture
def db():
    """Create temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        database = REMDatabase(tenant_id="test-tenant", path=tmpdir)
        yield database
        database.close()


def test_create_and_get_resource(db):
    """Test resource CRUD operations."""
    resource = Resource(
        name="test.txt",
        content="The quick brown fox jumps over the lazy dog.",
        metadata={"source": "test.txt", "author": "Alice"},
    )

    # Create
    resource_id = db.create_resource(resource)
    assert resource_id == resource.id

    # Get
    retrieved = db.get_resource(resource_id)
    assert retrieved is not None
    assert retrieved.content == resource.content
    assert retrieved.name == "test.txt"
    assert retrieved.metadata == resource.metadata

    # Delete
    db.delete_resource(resource_id)
    assert db.get_resource(resource_id) is None


def test_create_and_get_entity(db):
    """Test entity CRUD operations."""
    entity = Entity(
        type="person",
        name="Alice",
        aliases=["Alice Wonder"],
        properties={"role": "engineer", "team": "platform"},
    )

    # Create
    entity_id = db.create_entity(entity)
    assert entity_id == entity.id

    # Get
    retrieved = db.get_entity(entity_id)
    assert retrieved is not None
    assert retrieved.name == "Alice"
    assert retrieved.properties["role"] == "engineer"


def test_query_resources_with_predicates(db):
    """Test predicate queries on resources."""
    # Create multiple resources
    for i in range(10):
        resource = Resource(
            name=f"doc-{i}",
            content=f"Document {i}",
            metadata={"index": i, "even": i % 2 == 0, "author": "Alice" if i < 5 else "Bob"},
        )
        db.create_resource(resource)

    # Query with simple predicate
    query = Query().filter(Eq("author", "Alice"))
    results = db.query_resources(query)
    assert len(results) == 5

    # Query with compound predicate
    query = Query().filter(And([Eq("author", "Alice"), Eq("even", True)]))
    results = db.query_resources(query)
    assert len(results) == 3  # 0, 2, 4

    # Query with range
    query = Query().filter(Gt("index", 5))
    results = db.query_resources(query)
    assert len(results) == 4  # 6, 7, 8, 9

    # Query with IN
    query = Query().filter(In("index", [1, 3, 5, 7]))
    results = db.query_resources(query)
    assert len(results) == 4


def test_query_entities_with_sorting(db):
    """Test entity queries with sorting."""
    # Create entities
    for name in ["Charlie", "Alice", "Bob", "David"]:
        entity = Entity(type="person", name=name, properties={"team": "platform"})
        db.create_entity(entity)

    # Query and sort ascending
    query = Query().sort("name", Order.ASC)
    results = db.query_entities(query)
    names = [e.name for e in results]
    assert names == ["Alice", "Bob", "Charlie", "David"]

    # Query and sort descending
    query = Query().sort("name", Order.DESC)
    results = db.query_entities(query)
    names = [e.name for e in results]
    assert names == ["David", "Charlie", "Bob", "Alice"]


def test_query_with_limit_and_offset(db):
    """Test pagination with limit and offset."""
    # Create 20 entities
    for i in range(20):
        entity = Entity(type="person", name=f"Person {i}", properties={"index": i})
        db.create_entity(entity)

    # Get first page
    query = Query().sort("index", Order.ASC).take(5)
    page1 = db.query_entities(query)
    assert len(page1) == 5
    assert page1[0].properties["index"] == 0

    # Get second page
    query = Query().sort("index", Order.ASC).skip(5).take(5)
    page2 = db.query_entities(query)
    assert len(page2) == 5
    assert page2[0].properties["index"] == 5


def test_entity_edges(db):
    """Test entity graph operations."""
    # Create entities
    alice = Entity(type="person", name="Alice")
    bob = Entity(type="person", name="Bob")
    project = Entity(type="project", name="Percolate")

    alice_id = db.create_entity(alice)
    bob_id = db.create_entity(bob)
    project_id = db.create_entity(project)

    # Create edges
    db.create_edge(Edge(src_id=alice_id, dst_id=project_id, edge_type="works_on"))
    db.create_edge(Edge(src_id=bob_id, dst_id=project_id, edge_type="works_on"))
    db.create_edge(Edge(src_id=alice_id, dst_id=bob_id, edge_type="knows"))

    # Get outgoing edges
    edges = db.get_edges(alice_id, Direction.OUTGOING)
    assert len(edges) == 2

    # Get incoming edges
    edges = db.get_edges(project_id, Direction.INCOMING)
    assert len(edges) == 2

    # Traverse
    related = db.traverse(alice_id, edge_type="works_on", max_depth=1)
    assert len(related) == 1
    assert related[0].name == "Percolate"


def test_moments(db):
    """Test moment creation and querying."""
    # Create resources and entities
    resource = Resource(name="meeting", content="Meeting notes")
    entity = Entity(type="person", name="Alice")

    resource_id = db.create_resource(resource)
    entity_id = db.create_entity(entity)

    # Create moment
    moment = Moment(
        timestamp=datetime.now(UTC),
        type="meeting",
        classifications=["technical", "planning"],
        resource_refs=[resource_id],
        entity_refs=[entity_id],
    )

    moment_id = db.create_moment(moment)

    # Get moment
    retrieved = db.get_moment(moment_id)
    assert retrieved is not None
    assert retrieved.type == "meeting"
    assert len(retrieved.resource_refs) == 1


def test_vector_search(db):
    """Test vector similarity search."""
    # Create resources with embeddings
    vectors = []
    for i in range(10):
        resource = Resource(name=f"doc-{i}", content=f"Document {i}", metadata={"index": i})
        resource_id = db.create_resource(resource)

        # Create random vector
        vector = np.random.rand(768).astype(np.float32)
        vectors.append(vector)
        db.set_embedding(resource_id, vector)

    # Search with first vector (should be most similar to itself)
    query_vector = vectors[0]
    results = db.search_similar(query_vector, top_k=3)

    assert len(results) > 0
    # First result should be the query vector itself (highest score)
    assert results[0][1] > 0.99  # Cosine similarity ~1.0


def test_hybrid_search(db):
    """Test hybrid search: vector + predicate."""
    # Create resources with metadata and embeddings
    for i in range(20):
        resource = Resource(
            name=f"doc-{i}",
            content=f"Document {i}",
            metadata={
                "index": i,
                "language": "en" if i < 15 else "es",
                "tags": ["important"] if i % 2 == 0 else ["regular"],
            },
        )
        resource_id = db.create_resource(resource)

        # Add vector
        vector = np.random.rand(768).astype(np.float32)
        db.set_embedding(resource_id, vector)

    # Create query vector
    query_vector = np.random.rand(768).astype(np.float32)

    # Hybrid search: English documents with "important" tag
    query = Query().filter(And([Eq("language", "en"), In("tags", ["important"])]))

    results = db.search_hybrid(query_vector, query, top_k=50, min_score=0.0)

    # Should only get English docs with important tag
    assert all(r.metadata["language"] == "en" for r, _ in results)
    assert all("important" in r.metadata["tags"] for r, _ in results)


def test_string_predicates(db):
    """Test string-based predicates."""
    # Create resources
    resources = [
        Resource(name="hello_world.txt", content="Hello World", metadata={"title": "hello_world.txt"}),
        Resource(name="goodbye_world.txt", content="Goodbye World", metadata={"title": "goodbye_world.txt"}),
        Resource(name="hello_everyone.txt", content="Hello Everyone", metadata={"title": "hello_everyone.txt"}),
    ]

    for r in resources:
        db.create_resource(r)

    # Test Contains
    query = Query().filter(Contains("content", "Hello"))
    results = db.query_resources(query)
    assert len(results) == 2

    # Test StartsWith (on metadata)
    query = Query().filter(Contains("title", "hello"))
    results = db.query_resources(query)
    assert len(results) == 2


def test_tenant_isolation(db):
    """Test that different tenants are isolated."""
    # Create resource in test-tenant
    resource1 = Resource(name="tenant1-doc", content="Tenant 1 data")
    db.create_resource(resource1)

    # Create another database for different tenant
    db2 = REMDatabase(tenant_id="other-tenant", path=db.path)

    try:
        # Create resource in other-tenant
        resource2 = Resource(name="tenant2-doc", content="Tenant 2 data")
        db2.create_resource(resource2)

        # Query each tenant
        results1 = db.query_resources(Query())
        results2 = db2.query_resources(Query())

        # Each tenant should only see their own data
        assert len(results1) == 1
        assert len(results2) == 1
        assert results1[0].content == "Tenant 1 data"
        assert results2[0].content == "Tenant 2 data"
    finally:
        db2.close()
