# Spike: REM Database (RocksDB + Vectors + Predicates)

## Goal

Build a fast, usable RocksDB-based implementation of the REM (Resources-Entities-Moments) memory system with:
- Vector search support using HNSW
- SQL-like predicate queries over metadata
- Complete tenant isolation
- Hybrid search combining semantic and metadata filtering

**Why Python first?** Rapid iteration on API design and data structures before committing to Rust implementation.

## Questions to Answer

### Performance
- [ ] Can we achieve <10ms p50 for simple predicate queries?
- [ ] How does vector search scale with 100k, 1M, 10M vectors per tenant?
- [ ] What's the overhead of tenant isolation (separate RocksDB instances)?
- [ ] Can concurrent writes from multiple threads work safely?
- [ ] What's the memory footprint per tenant?

### API Design
- [ ] What's the most ergonomic Python API for REM operations?
- [ ] How should predicates compose (builder pattern vs functional)?
- [ ] Should vector search be a special predicate or separate operation?
- [ ] How do we handle schema-less entities cleanly?

### Data Model
- [ ] What RocksDB key patterns give best performance?
- [ ] Do we need column families or can we use prefixes?
- [ ] How do we index metadata fields efficiently?
- [ ] What's the best chunking strategy for resources?

### Tenant Isolation
- [ ] Separate RocksDB instances or shared with prefixes?
- [ ] How do we prevent cross-tenant queries?
- [ ] What's the overhead of multiple RocksDB instances?
- [ ] Can we safely evict/load tenant databases?

## Approach

### Phase 1: Core REM Operations (Days 1-2)

Build minimal REM database with:

```python
from rem_db import REMDatabase, Resource, Entity, Moment

# Initialize tenant database
db = REMDatabase(tenant_id="tenant-123", path="./data")

# Resources: Chunked, embedded content
resource_id = db.create_resource(
    content="The quick brown fox...",
    metadata={"source": "document.pdf", "page": 1}
)

# Entities: Graph nodes with properties
entity_id = db.create_entity(
    type="person",
    name="John Doe",
    properties={"role": "engineer", "team": "platform"}
)

# Moments: Temporal classifications
moment_id = db.create_moment(
    timestamp=datetime.now(),
    type="conversation",
    resource_refs=[resource_id],
    entity_refs=[entity_id]
)
```

**Focus:**
- RocksDB key design
- CRUD operations
- Tenant scoping

### Phase 2: Vector Search (Days 2-3)

Add HNSW vector index:

```python
# Add embedding to resource
db.set_embedding(resource_id, embedding_vector)

# Semantic search
results = db.search_similar(
    query_vector=query_embedding,
    top_k=10,
    min_score=0.7
)
```

**Test:**
- Use nomic-embed-text-v1.5 (768 dims)
- 10k vectors, 100k vectors, 1M vectors
- Measure recall@10, latency

### Phase 3: Predicate Queries (Days 3-4)

Implement SQL-like predicates:

```python
from rem_db import Query, Predicate

# Simple predicate
query = Query().filter(
    Predicate.eq("status", "active")
).limit(100)

# Complex predicate
query = Query().filter(
    Predicate.and_([
        Predicate.eq("type", "person"),
        Predicate.in_("team", ["platform", "infra"]),
        Predicate.gt("created_at", datetime(2024, 1, 1))
    ])
).order_by("name", "asc")

entities = db.query_entities(query)
```

**Test:**
- 100k entities with various metadata
- Predicate evaluation performance
- Composite queries

### Phase 4: Hybrid Search (Days 4-5)

Combine vector + predicate search:

```python
# Vector search with metadata filtering
query = Query().filter(
    Predicate.and_([
        Predicate.vector_similar(
            field="embedding",
            query=query_vector,
            top_k=50,
            min_score=0.7
        ),
        Predicate.eq("language", "en"),
        Predicate.in_("tags", ["important", "urgent"])
    ])
).limit(10)

results = db.query_resources(query)
```

**Test:**
- Compare: vector-first vs predicate-first
- Measure precision/recall
- Test with realistic filter selectivity

## Success Criteria

### Must Have
- ✅ <10ms p50 latency for simple queries
- ✅ <50ms p50 latency for hybrid search
- ✅ Complete tenant isolation (no cross-tenant data)
- ✅ Support 1M+ vectors per tenant
- ✅ Clean, type-safe Python API
- ✅ Thread-safe concurrent writes

### Nice to Have
- ✅ <5ms p50 for indexed predicates
- ✅ Support 10M+ vectors
- ✅ Incremental HNSW index building
- ✅ Batch write optimization
- ✅ Query explain/profiling

## Implementation Log

### Day 1: RocksDB Setup & Key Design

**Goal:** Basic CRUD operations for Resources, Entities, Moments

**Key Design:**

```python
# Resource keys
resource:{tenant_id}:{resource_id} -> Resource JSON

# Entity keys
entity:{tenant_id}:{entity_id} -> Entity JSON

# Edge keys (for entity graph)
edge:{tenant_id}:{src_id}:{dst_id}:{edge_type} -> Edge JSON

# Moment keys
moment:{tenant_id}:{moment_id} -> Moment JSON

# Indexes
index:entity:{tenant_id}:{field}:{value} -> [entity_ids]
index:moment:time:{tenant_id}:{timestamp} -> moment_id
```

**Learnings:**
- [Document as you build]

### Day 2: Vector Search with HNSW

**Goal:** Add HNSW index for semantic search

**Library Options:**
1. hnswlib (Python bindings, C++, fast)
2. faiss (Facebook, comprehensive, complex)
3. usearch (Rust, modern, fast)

**Chosen:** hnswlib (proven, simple API)

**Implementation:**

```python
import hnswlib

class VectorIndex:
    def __init__(self, dim: int, max_elements: int):
        self.index = hnswlib.Index(space='cosine', dim=dim)
        self.index.init_index(
            max_elements=max_elements,
            ef_construction=200,
            M=16
        )

    def add(self, ids: List[int], vectors: np.ndarray):
        self.index.add_items(vectors, ids)

    def search(self, query: np.ndarray, k: int):
        labels, distances = self.index.knn_query(query, k=k)
        return labels, distances
```

**Benchmarks:**
- [Add results as you test]

**Learnings:**
- [Document findings]

### Day 3: Predicate Implementation

**Goal:** SQL-like predicates over entity metadata

**Implementation:**

```python
@dataclass
class Predicate:
    """SQL-like predicate for filtering"""

    @staticmethod
    def eq(field: str, value: Any) -> "Predicate":
        """field == value"""
        ...

    @staticmethod
    def in_(field: str, values: List[Any]) -> "Predicate":
        """field IN [values]"""
        ...

    @staticmethod
    def and_(predicates: List["Predicate"]) -> "Predicate":
        """pred1 AND pred2 AND ..."""
        ...

    def evaluate(self, entity: Entity) -> bool:
        """Evaluate predicate against entity"""
        ...
```

**Learnings:**
- [Document findings]

### Day 4-5: Hybrid Search

**Goal:** Combine vector search + predicate filtering

**Strategy Options:**
1. **Vector-first**: Search vectors, then filter results
2. **Predicate-first**: Filter by predicates, then vector search
3. **Parallel**: Run both, merge results

**Chosen:** [To be determined based on testing]

**Learnings:**
- [Document findings]

## Benchmarks

### Setup

- Machine: [Specify specs]
- Dataset: [Describe test data]
- Metrics: p50, p95, p99 latency

### Results

#### Simple Predicate Query

```
Query: entities WHERE type == "person" LIMIT 100
Dataset: 100k entities
```

| Operation | p50 | p95 | p99 |
|-----------|-----|-----|-----|
| Scan (no index) | TBD | TBD | TBD |
| With index | TBD | TBD | TBD |

#### Vector Search

```
Query: top_k=10, vectors=100k
```

| Metric | Value |
|--------|-------|
| Build time | TBD |
| Query latency (p50) | TBD |
| Recall@10 | TBD |
| Memory usage | TBD |

#### Hybrid Search

```
Query: vector_similar(top_k=50) + eq("language", "en") LIMIT 10
Dataset: 1M resources, 50% English
```

| Strategy | p50 | p95 | Precision |
|----------|-----|-----|-----------|
| Vector-first | TBD | TBD | TBD |
| Predicate-first | TBD | TBD | TBD |

## API Examples

### Resource Operations

```python
# Create resource with metadata
resource = Resource(
    content="Long document content...",
    metadata={
        "source": "document.pdf",
        "page": 5,
        "author": "John Doe",
        "language": "en",
        "tags": ["important", "technical"]
    }
)
resource_id = db.create_resource(resource)

# Add embedding
embedding = model.encode(resource.content)
db.set_embedding(resource_id, embedding)

# Search by metadata
results = db.query_resources(
    Query().filter(Predicate.eq("author", "John Doe"))
)

# Semantic search
results = db.search_similar(
    query_vector=query_embedding,
    top_k=10
)

# Hybrid search
results = db.query_resources(
    Query().filter(
        Predicate.and_([
            Predicate.vector_similar(
                query=query_embedding,
                top_k=50,
                min_score=0.7
            ),
            Predicate.eq("language", "en"),
            Predicate.in_("tags", ["important"])
        ])
    ).limit(10)
)
```

### Entity Graph Operations

```python
# Create entities
person_id = db.create_entity(
    type="person",
    name="Alice",
    properties={"role": "engineer"}
)

project_id = db.create_entity(
    type="project",
    name="Percolate",
    properties={"status": "active"}
)

# Create relationship
db.create_edge(
    src=person_id,
    dst=project_id,
    edge_type="works_on",
    properties={"since": "2024-01-01"}
)

# Query graph
related = db.traverse(
    start=person_id,
    edge_type="works_on",
    direction="outgoing",
    max_depth=2
)

# Complex entity query
engineers = db.query_entities(
    Query().filter(
        Predicate.and_([
            Predicate.eq("type", "person"),
            Predicate.eq("role", "engineer"),
            Predicate.exists("team")
        ])
    ).order_by("name", "asc")
)
```

### Moment Queries

```python
# Create moment
moment = db.create_moment(
    timestamp=datetime.now(),
    type="conversation",
    classifications=["technical", "planning"],
    resource_refs=[resource_id],
    entity_refs=[person_id, project_id],
    metadata={"duration_minutes": 30}
)

# Query moments by time
recent = db.query_moments(
    Query().filter(
        Predicate.gte("timestamp", datetime.now() - timedelta(days=7))
    ).order_by("timestamp", "desc")
)

# Query moments by type
conversations = db.query_moments(
    Query().filter(Predicate.eq("type", "conversation"))
)
```

## Key Learnings

### What Worked Well

- [Document successes]

### What Didn't Work

- [Document failures and why]

### Performance Surprises

- [Document unexpected findings]

### API Ergonomics

- [What felt natural vs awkward?]

## Recommendation for Rust Port

### Core Design to Keep

- [What should we preserve in Rust version?]

### Changes to Make

- [What should we do differently in Rust?]

### Performance Targets

- [What should Rust version achieve?]

## Open Questions

- [ ] How do we handle schema migrations?
- [ ] Should we support transactions?
- [ ] How do we backup/restore efficiently?
- [ ] What's the best way to version REM database format?
- [ ] How do we handle index rebuilding on schema changes?

## Next Steps

1. **If spike successful:** Create `docs/components/rem-database.md` with clean spec
2. **Port to Rust:** Implement in `percolate-rust/src/memory/`
3. **Add tests:** Comprehensive test suite based on spike findings
4. **Benchmark:** Compare Rust vs Python performance
5. **Archive spike:** Move to `.spikes/archived/rem-db-YYYYMMDD`

## References

- RocksDB docs: https://github.com/facebook/rocksdb/wiki
- hnswlib: https://github.com/nmslib/hnswlib
- Query layer design: `docs/components/query-layer.md`
- REM memory spec: `docs/02-rem-memory.md`
