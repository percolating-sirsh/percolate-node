# REM Memory System

Natural language information retrieval with REM.


## Overview

**REM (Resources-Entities-Moments)** is a bio-inspired memory architecture that mirrors human memory systems:
- **Episodic memory**: Specific experiences (Moments)
- **Semantic memory**: Conceptual knowledge (Entities + Resources)
- **Procedural memory**: Learned patterns (Agent-lets stored as Entities)

## Design Principles

### Bio-Inspired
- Memory is not a single flat store
- Different types of memory serve different purposes
- Retrieval strategies vary by memory type
- Temporal and relational context matter

### Hybrid Storage
- Vector embeddings for semantic search
- Graph relationships for context navigation
- Time indexes for chronological retrieval
- Key-value for efficient lookups

### Tenant Scoped
- All memory operations scoped to tenant
- Complete data isolation per user
- No cross-tenant queries or indexes
- Per-tenant encryption at rest

## Memory Types

### Resources

**Definition**: Chunked, embedded content from documents, files, conversations.

**Characteristics:**
- Semantic searchable via vector embeddings
- Deduplicated by content hash
- Metadata: source URI, timestamp, tenant, hash
- Chunking strategy: semantic (respects document structure)

**Storage:**
```
Key: resource:{tenant_id}:{resource_id}
Value: {
  content: string,
  metadata: {
    source_uri: string,
    timestamp: timestamp,
    chunk_index: int,
    total_chunks: int,
    hash: string
  },
  embedding_id: string
}
```

**Operations:**
- `create_resource(content, metadata) -> resource_id`
- `get_resource(resource_id) -> Resource`
- `search_resources(query, limit) -> Vec<Resource>`
- `delete_resource(resource_id)`

### Entities

**Definition**: Domain knowledge nodes with properties and relationships.

**Characteristics:**
- Key-value properties (flexible schema)
- Graph edges (typed relationships)
- Fuzzy searchable on names/aliases
- Entity types: person, concept, organization, agent-let, etc.

**Storage:**
```
Key: entity:{tenant_id}:{entity_id}
Value: {
  type: string,
  name: string,
  aliases: Vec<string>,
  properties: HashMap<string, Value>,
  created_at: timestamp,
  updated_at: timestamp
}

Key: edge:{tenant_id}:{src_id}:{dst_id}:{edge_type}
Value: {
  properties: HashMap<string, Value>,
  created_at: timestamp
}
```

**Operations:**
- `create_entity(type, name, properties) -> entity_id`
- `get_entity(entity_id) -> Entity`
- `update_entity(entity_id, properties)`
- `search_entities(query, type) -> Vec<Entity>`
- `create_edge(src_id, dst_id, edge_type, properties)`
- `get_edges(entity_id, direction) -> Vec<Edge>`
- `traverse(entity_id, edge_type, depth) -> Vec<Entity>`

### Moments

**Definition**: Temporal classifications of existing resources and entities.

**Characteristics:**
- Time-indexed events
- References to resources and entities (does not duplicate)
- Enable chronological memory retrieval
- Moments can be nested (sub-moments)

**Storage:**
```
Key: moment:{tenant_id}:{moment_id}
Value: {
  timestamp: timestamp,
  type: string (e.g., "conversation", "task", "insight"),
  classifications: Vec<string>,
  resource_refs: Vec<resource_id>,
  entity_refs: Vec<entity_id>,
  parent_moment: Option<moment_id>,
  metadata: HashMap<string, Value>
}

Index: moment_by_time:{tenant_id}:{timestamp} -> moment_id
```

**Operations:**
- `create_moment(timestamp, type, refs) -> moment_id`
- `get_moment(moment_id) -> Moment`
- `get_moments_by_time(start, end) -> Vec<Moment>`
- `get_moments_by_type(type) -> Vec<Moment>`

## Search Strategies

### 1. Semantic Search (Vector-based)

**Use Case**: Find conceptually similar content

**Algorithm:**
1. Embed query with same model as resources
2. Perform approximate nearest neighbor search (HNSW)
3. Return top-k results with similarity scores
4. Filter by tenant (enforced at index level)

**Implementation:**
- HNSW index per tenant (isolates search space)
- Cosine similarity for distance metric
- Configurable k (default 10-20)
- Post-filtering for metadata constraints

### 2. Fuzzy Search (Entity-based)

**Use Case**: Find entities by name/alias with typo tolerance

**Algorithm:**
1. Generate trigrams from query
2. Match against entity trigram index
3. Rank by edit distance (Levenshtein)
4. Filter by entity type if specified

**Implementation:**
- Trigram index: `index:trigram:{tenant_id}:{trigram} -> [entity_ids]`
- Prefix index for fast autocomplete
- Configurable similarity threshold (0.7 default)

### 3. Graph Traversal (Relationship-based)

**Use Case**: Discover related entities through relationships

**Algorithm:**
1. Start from seed entity
2. Follow edges of specified type
3. Breadth-first or depth-first traversal
4. Configurable max depth (default 3)

**Implementation:**
- Adjacency list: `edge:{tenant_id}:{src_id}:* -> [edges]`
- Lazy loading (don't load full entities until needed)
- Cycle detection to prevent infinite loops

### 4. Hybrid Search (Combination)

**Use Case**: Best results using multiple retrieval strategies

**Algorithm:**
1. Execute semantic search (vector)
2. Execute entity search (fuzzy)
3. Execute graph traversal from matched entities
4. Merge results with score fusion (RRF - Reciprocal Rank Fusion)
5. Re-rank with cross-encoder (optional, LLM-based)

**Score Fusion (RRF):**
```
score(doc) = Σ(1 / (k + rank_i))
where rank_i is position in i-th result list, k=60
```

## Retrieval Patterns

### Iterated Retrieval

**Concept**: Navigate memory through multiple hops of context.

**Flow:**
1. Initial query matches resources
2. Extract entity references from resources
3. Traverse entity relationships
4. Fetch related resources
5. Repeat for N iterations (default 2)

**Example:**
```
Query: "What did we discuss about pricing?"
  → Matches resources about "pricing"
    → Extracts entities: [Product-A, Competitor-X]
      → Traverses edges: related_to, competes_with
        → Discovers entities: [Market-Segment-Y]
          → Fetches resources referencing Market-Segment-Y
            → Returns enriched context
```

### Temporal Retrieval

**Concept**: Retrieve memory within time windows.

**Flow:**
1. Query specifies time range
2. Index lookup: `moment_by_time:{tenant}:{start}..{end}`
3. Fetch moments in range
4. Resolve resource and entity references
5. Return chronologically ordered results

**Example:**
```
Query: "What happened last week?"
  → Looks up moments from (now - 7 days) to now
    → Fetches all moments in range
      → Resolves references to resources and entities
        → Returns timeline of events
```

### Contextual Retrieval

**Concept**: Use conversation context to improve search.

**Flow:**
1. Extract entities from conversation history
2. Boost search results that reference these entities
3. Filter by recency (recent mentions weighted higher)
4. Consider user preferences (learned patterns)

**Example:**
```
User: "Tell me more about it"
  → "it" is ambiguous
    → Checks recent conversation context
      → Finds last mentioned entity: Project-Alpha
        → Searches for resources about Project-Alpha
```

## RocksDB Schema Design

### Column Families

RocksDB organizes data into column families for performance:

| Column Family | Purpose | Key Pattern |
|---------------|---------|-------------|
| `resources` | Resource content | `resource:{tenant}:{id}` |
| `entities` | Entity properties | `entity:{tenant}:{id}` |
| `edges` | Entity relationships | `edge:{tenant}:{src}:{dst}:{type}` |
| `moments` | Temporal classifications | `moment:{tenant}:{id}` |
| `embeddings` | Vector embeddings | `embedding:{tenant}:{id}` |
| `indexes` | Secondary indexes | `index:{type}:{tenant}:{value}` |

### Key Design Principles

1. **Tenant prefix**: All keys start with `{type}:{tenant_id}`
   - Enables efficient tenant isolation
   - Allows per-tenant iteration
   - Facilitates tenant deletion

2. **Lexicographic ordering**: Keys designed for range queries
   - Time-based keys use sortable timestamps
   - Enables efficient range scans

3. **Denormalization**: Store duplicates for read performance
   - Entity properties stored with entity (not normalized)
   - Metadata embedded in resources
   - Trade space for speed

### Compression

- Default: Snappy compression (fast, reasonable ratio)
- Cold data: Zstd compression (better ratio, slower)
- Hot data: No compression (maximum speed)

### Write Batches

- Group related writes into atomic batches
- Example: Creating resource + embedding + index updates
- Ensures consistency on crash recovery

## Vector Embeddings

### Embedding Model

- Model: `nomic-embed-text-v1.5` (768 dimensions)
- Rationale: Open source, strong performance, commercial friendly
- Alternatives: OpenAI `text-embedding-3-small` (1536 dims)

### HNSW Index

**Parameters:**
- M: 16 (number of connections per layer)
- ef_construction: 200 (search quality during build)
- ef_search: 50 (search quality during query)
- Distance metric: Cosine similarity

**Tenant Isolation:**
- Separate HNSW index per tenant
- Index stored in RocksDB column family
- Lazy loading (load index on first query)

### Embedding Storage

```
Key: embedding:{tenant_id}:{embedding_id}
Value: {
  vector: Vec<f32>,  // 768 dimensions
  model: string,      // "nomic-embed-text-v1.5"
  created_at: timestamp
}
```

## Performance Characteristics

### Read Performance

| Operation | Latency | Throughput |
|-----------|---------|------------|
| Get resource by ID | <1ms | 100k+ ops/sec |
| Semantic search (k=10) | 5-20ms | 1k+ queries/sec |
| Entity fuzzy search | 2-10ms | 5k+ queries/sec |
| Graph traversal (depth=3) | 10-50ms | 500+ queries/sec |
| Hybrid search | 20-100ms | 200+ queries/sec |

### Write Performance

| Operation | Latency | Throughput |
|-----------|---------|------------|
| Create resource | 2-5ms | 20k+ ops/sec |
| Create entity | 1-3ms | 30k+ ops/sec |
| Create edge | 1-2ms | 50k+ ops/sec |
| Batch write (100 ops) | 10-20ms | 5k+ batches/sec |

### Storage Efficiency

- Resources: ~1KB per chunk (average)
- Entities: ~500 bytes per entity (average)
- Embeddings: 3KB per vector (768 dims × 4 bytes)
- Indexes: 20-30% overhead (trigrams, time indexes)

## Query Layer

REM provides a **SQL-like predicate interface** for flexible queries over RocksDB:

### Predicate-Based Queries

```rust
use percolate_rust::{Query, Predicate};

// Simple query
let query = Query::new()
    .filter(Predicate::Eq("status".into(), Value::String("active".into())))
    .filter(Predicate::Gt("age".into(), Value::from(18)))
    .limit(100);

let results = memory.query_entities(query).await?;

// Complex predicates
let query = Query::new()
    .filter(Predicate::And(vec![
        Predicate::Eq("status".into(), Value::String("published".into())),
        Predicate::In("tags".into(), vec![
            Value::String("important".into()),
            Value::String("urgent".into()),
        ]),
    ]))
    .order_by("created_at".into(), Order::Desc)
    .limit(50);

// Vector search with predicates
let query = Query::new()
    .filter(Predicate::VectorSimilar {
        field: "embedding".into(),
        query: embedding_vector,
        top_k: 20,
        min_score: 0.7,
    })
    .filter(Predicate::Eq("language".into(), Value::String("en".into())))
    .limit(10);

let results = memory.query_resources(query).await?;
```

**See:** `docs/components/query-layer.md` for complete predicate reference and optimization strategies.

## API Design (Rust)

### Core Traits

```rust
pub trait MemoryEngine {
    // CRUD operations
    async fn create_resource(&self, resource: Resource) -> Result<ResourceId>;
    async fn get_resource(&self, id: ResourceId) -> Result<Resource>;
    async fn search_resources(&self, query: &SearchQuery) -> Result<Vec<Resource>>;

    async fn create_entity(&self, entity: Entity) -> Result<EntityId>;
    async fn get_entity(&self, id: EntityId) -> Result<Entity>;
    async fn search_entities(&self, query: &str, filter: EntityFilter) -> Result<Vec<Entity>>;

    async fn create_edge(&self, edge: Edge) -> Result<EdgeId>;
    async fn get_edges(&self, entity_id: EntityId, direction: Direction) -> Result<Vec<Edge>>;
    async fn traverse(&self, start: EntityId, traversal: Traversal) -> Result<Vec<Entity>>;

    async fn create_moment(&self, moment: Moment) -> Result<MomentId>;
    async fn get_moments_by_time(&self, range: TimeRange) -> Result<Vec<Moment>>;

    // Query layer (predicate-based)
    async fn query_resources(&self, query: Query) -> Result<Vec<Resource>>;
    async fn query_entities(&self, query: Query) -> Result<Vec<Entity>>;
    async fn query_moments(&self, query: Query) -> Result<Vec<Moment>>;

    // Index management
    async fn create_index(&self, entity_type: &str, field: &str) -> Result<()>;
}
```

### Python Bindings (PyO3)

```python
from percolate_core import MemoryEngine, Resource, Entity, Edge, Moment

# Initialize memory engine
memory = MemoryEngine(db_path="/var/lib/percolate/tenant-123", tenant_id="tenant-123")

# Create resource
resource = Resource(
    content="Annual revenue increased by 25% in Q4...",
    metadata={"source": "earnings-report.pdf", "page": 5}
)
resource_id = memory.create_resource(resource)

# Search semantically
results = memory.search_resources(query="What was our Q4 performance?", limit=10)

# Create entity
entity = Entity(
    type="company",
    name="Acme Corp",
    properties={"industry": "Software", "founded": 2010}
)
entity_id = memory.create_entity(entity)

# Create relationship
edge = Edge(
    src=entity_id,
    dst=another_entity_id,
    edge_type="competes_with",
    properties={"market": "Enterprise SaaS"}
)
memory.create_edge(edge)

# Traverse relationships
related = memory.traverse(entity_id, edge_type="competes_with", max_depth=2)
```

## Future Enhancements

### Phase 1 (Current)
- Basic CRUD operations
- Semantic search (HNSW)
- Entity graph (BFS/DFS)
- Tenant isolation

### Phase 2
- Fuzzy entity search (trigrams)
- Hybrid search (RRF fusion)
- Iterated retrieval
- Temporal queries

### Phase 3
- Automatic entity extraction (LLM-based)
- Cross-encoder re-ranking
- Learned sparse retrieval (SPLADE)
- Query expansion

### Phase 4
- Multi-modal embeddings (text + image)
- Dense + sparse hybrid indexes
- Automatic schema extraction
- Federated search (across tenants with permission)

## References

- Bio-inspired memory: Hippocampal-entorhinal circuits
- HNSW: Malkov & Yashunin (2018)
- RocksDB: https://rocksdb.org
- RRF: Cormack et al. (2009) "Reciprocal Rank Fusion"
- Embedding models: https://huggingface.co/nomic-ai
