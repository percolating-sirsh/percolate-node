"""Performance benchmarks for REM database."""

import tempfile
import time
from datetime import datetime

import numpy as np
import pytest

from rem_db import And, Eq, Entity, Gt, In, Order, Query, REMDatabase, Resource


@pytest.fixture
def db():
    """Create temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        database = REMDatabase(tenant_id="test-tenant", path=tmpdir)
        yield database
        database.close()


@pytest.fixture
def db_with_entities(db):
    """Database with 10k entities."""
    # Create 10k entities
    for i in range(10000):
        entity = Entity(
            type="person" if i % 3 == 0 else "project",
            name=f"Entity {i}",
            properties={
                "index": i,
                "status": "active" if i % 2 == 0 else "inactive",
                "priority": i % 5,
                "team": ["platform", "infra", "data"][i % 3],
            },
        )
        db.create_entity(entity)
    return db


@pytest.fixture
def db_with_vectors(db):
    """Database with 10k resources and vectors."""
    # Create 10k resources with embeddings
    for i in range(10000):
        resource = Resource(
            content=f"Document {i}",
            metadata={
                "index": i,
                "language": ["en", "es", "fr"][i % 3],
                "status": "published" if i % 2 == 0 else "draft",
            },
        )
        resource_id = db.create_resource(resource)

        # Add vector
        vector = np.random.rand(768).astype(np.float32)
        db.set_embedding(resource_id, vector)

    return db


def test_simple_eq_query_performance(benchmark, db_with_entities):
    """Benchmark simple equality query."""

    def query():
        q = Query().filter(Eq("status", "active"))
        return db_with_entities.query_entities(q)

    results = benchmark(query)
    assert len(results) == 5000  # Half are active


def test_compound_predicate_performance(benchmark, db_with_entities):
    """Benchmark compound AND predicate."""

    def query():
        q = Query().filter(
            And(
                [
                    Eq("type", "person"),
                    Eq("status", "active"),
                    In("team", ["platform", "infra"]),
                ]
            )
        )
        return db_with_entities.query_entities(q)

    results = benchmark(query)
    assert len(results) > 0


def test_range_query_performance(benchmark, db_with_entities):
    """Benchmark range query with sorting."""

    def query():
        q = Query().filter(Gt("index", 5000)).sort("index", Order.ASC).take(100)
        return db_with_entities.query_entities(q)

    results = benchmark(query)
    assert len(results) == 100


def test_vector_search_performance(benchmark, db_with_vectors):
    """Benchmark vector search."""
    query_vector = np.random.rand(768).astype(np.float32)

    def search():
        return db_with_vectors.search_similar(query_vector, top_k=10)

    results = benchmark(search)
    assert len(results) == 10


def test_hybrid_search_performance(benchmark, db_with_vectors):
    """Benchmark hybrid search: vector + predicates."""
    query_vector = np.random.rand(768).astype(np.float32)

    def search():
        q = Query().filter(And([Eq("language", "en"), Eq("status", "published")]))
        return db_with_vectors.search_hybrid(query_vector, q, top_k=50, min_score=0.0)

    results = benchmark(search)
    assert len(results) > 0


def test_write_throughput(db):
    """Test write performance."""
    num_entities = 1000
    start = time.perf_counter()

    for i in range(num_entities):
        entity = Entity(
            type="test", name=f"Entity {i}", properties={"index": i, "batch": "write_test"}
        )
        db.create_entity(entity)

    elapsed = time.perf_counter() - start
    throughput = num_entities / elapsed

    print(f"\nWrite throughput: {throughput:.0f} entities/sec")
    assert throughput > 1000  # Should be >1k writes/sec


def test_read_throughput(db_with_entities):
    """Test read performance."""
    # Get all entity IDs
    all_entities = db_with_entities.query_entities(Query().take(1000))
    entity_ids = [e.id for e in all_entities]

    start = time.perf_counter()

    for entity_id in entity_ids:
        db_with_entities.get_entity(entity_id)

    elapsed = time.perf_counter() - start
    throughput = len(entity_ids) / elapsed

    print(f"\nRead throughput: {throughput:.0f} reads/sec")
    assert throughput > 10000  # Should be >10k reads/sec


def test_scan_performance(db_with_entities):
    """Test full table scan performance."""
    start = time.perf_counter()

    results = db_with_entities.query_entities(Query())

    elapsed = time.perf_counter() - start
    throughput = len(results) / elapsed

    print(f"\nScan throughput: {throughput:.0f} entities/sec")
    print(f"Total scanned: {len(results)} entities in {elapsed:.3f}s")

    assert len(results) == 10000
    assert elapsed < 1.0  # Should scan 10k entities in <1s


def test_vector_index_build_time(db):
    """Test HNSW index build performance."""
    num_vectors = 10000

    start = time.perf_counter()

    for i in range(num_vectors):
        resource = Resource(content=f"Doc {i}")
        resource_id = db.create_resource(resource)

        vector = np.random.rand(768).astype(np.float32)
        db.set_embedding(resource_id, vector)

    elapsed = time.perf_counter() - start
    throughput = num_vectors / elapsed

    print(f"\nVector index build: {throughput:.0f} vectors/sec")
    print(f"Total time: {elapsed:.3f}s for {num_vectors} vectors")

    assert throughput > 500  # Should index >500 vectors/sec


def test_memory_footprint(db_with_entities):
    """Estimate memory footprint."""
    import sys

    # This is approximate - real measurement would need memory_profiler
    # But gives us a sense of the data
    sample_entity = db_with_entities.query_entities(Query().take(1))[0]
    entity_size = sys.getsizeof(sample_entity.model_dump_json())

    print(f"\nApproximate entity size: {entity_size} bytes")
    print(f"Estimated 10k entities: {entity_size * 10000 / 1024 / 1024:.2f} MB")


# Manual latency tests (not benchmarks)
def test_latency_p50_p95(db_with_entities):
    """Measure query latency percentiles."""
    num_queries = 100
    latencies = []

    for _ in range(num_queries):
        start = time.perf_counter()
        q = Query().filter(Eq("status", "active")).take(10)
        db_with_entities.query_entities(q)
        latencies.append((time.perf_counter() - start) * 1000)  # ms

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]

    print(f"\nQuery latency (ms):")
    print(f"  p50: {p50:.2f}")
    print(f"  p95: {p95:.2f}")
    print(f"  p99: {p99:.2f}")

    # Success criteria from spike README
    assert p50 < 10.0  # <10ms p50 latency


def test_vector_search_latency(db_with_vectors):
    """Measure vector search latency percentiles."""
    num_queries = 100
    latencies = []

    for _ in range(num_queries):
        query_vector = np.random.rand(768).astype(np.float32)
        start = time.perf_counter()
        db_with_vectors.search_similar(query_vector, top_k=10)
        latencies.append((time.perf_counter() - start) * 1000)  # ms

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]

    print(f"\nVector search latency (ms):")
    print(f"  p50: {p50:.2f}")
    print(f"  p95: {p95:.2f}")

    # Success criteria from spike README
    assert p50 < 50.0  # <50ms p50 latency for vector search


if __name__ == "__main__":
    # Quick smoke test
    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="perf-test", path=tmpdir)

        print("Creating 1000 test entities...")
        start = time.perf_counter()
        for i in range(1000):
            entity = Entity(type="test", name=f"Entity {i}", properties={"index": i})
            db.create_entity(entity)
        print(f"Created in {time.perf_counter() - start:.3f}s")

        print("\nQuerying...")
        start = time.perf_counter()
        results = db.query_entities(Query().filter(Gt("index", 500)))
        print(f"Queried {len(results)} results in {(time.perf_counter() - start) * 1000:.2f}ms")

        db.close()
