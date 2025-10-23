# Memory Engine Component Design

## Responsibility

The Memory Engine is the **Rust core** that implements REM (Resources-Entities-Moments) storage, retrieval, and search operations on top of RocksDB.

## Interface

### Rust API

```rust
pub struct MemoryEngine {
    db: Arc<DB>,
    tenant_id: String,
    embedding_index: Arc<HnswIndex>,
}

impl MemoryEngine {
    /// Initialize memory engine for a tenant
    pub fn new(db_path: &Path, tenant_id: String) -> Result<Self>;

    /// Resource operations
    pub async fn create_resource(&self, resource: Resource) -> Result<ResourceId>;
    pub async fn get_resource(&self, id: &ResourceId) -> Result<Resource>;
    pub async fn search_resources(&self, query: &SearchQuery) -> Result<Vec<ScoredResource>>;
    pub async fn delete_resource(&self, id: &ResourceId) -> Result<()>;

    /// Entity operations
    pub async fn create_entity(&self, entity: Entity) -> Result<EntityId>;
    pub async fn get_entity(&self, id: &EntityId) -> Result<Entity>;
    pub async fn update_entity(&self, id: &EntityId, updates: EntityUpdate) -> Result<()>;
    pub async fn search_entities(&self, query: &str, filter: Option<EntityFilter>) -> Result<Vec<Entity>>;

    /// Graph operations
    pub async fn create_edge(&self, edge: Edge) -> Result<EdgeId>;
    pub async fn get_edges(&self, entity_id: &EntityId, direction: Direction) -> Result<Vec<Edge>>;
    pub async fn traverse(&self, start: &EntityId, traversal: &Traversal) -> Result<Vec<Entity>>;

    /// Moment operations
    pub async fn create_moment(&self, moment: Moment) -> Result<MomentId>;
    pub async fn get_moment(&self, id: &MomentId) -> Result<Moment>;
    pub async fn get_moments_by_time(&self, range: TimeRange) -> Result<Vec<Moment>>;
}
```

### Python Bindings (PyO3)

```python
class MemoryEngine:
    """Rust-backed memory engine exposed to Python."""

    def __init__(self, db_path: str, tenant_id: str) -> None: ...

    def create_resource(self, resource: Resource) -> str: ...
    def get_resource(self, resource_id: str) -> Resource: ...
    def search_resources(self, query: str, limit: int = 10) -> list[ScoredResource]: ...

    def create_entity(self, entity: Entity) -> str: ...
    def get_entity(self, entity_id: str) -> Entity: ...
    def search_entities(self, query: str, entity_type: str | None = None) -> list[Entity]: ...

    def create_edge(self, src: str, dst: str, edge_type: str, properties: dict) -> str: ...
    def get_edges(self, entity_id: str, direction: str = "both") -> list[Edge]: ...
    def traverse(self, start: str, edge_type: str, max_depth: int = 3) -> list[Entity]: ...
```

## Implementation

### RocksDB Schema

**Column Families:**
- `resources` - Resource content and metadata
- `entities` - Entity properties
- `edges` - Graph relationships
- `moments` - Temporal classifications
- `embeddings` - Vector embeddings
- `indexes` - Secondary indexes

**Key Patterns:**
```
resource:{tenant}:{id} → {content, metadata, embedding_id}
entity:{tenant}:{id} → {type, name, properties}
edge:{tenant}:{src}:{dst}:{type} → {properties}
moment:{tenant}:{id} → {timestamp, type, refs}
embedding:{tenant}:{id} → {vector, model}
index:trigram:{tenant}:{trigram} → [entity_ids]
index:time:{tenant}:{timestamp} → [moment_ids]
```

### Search Implementation

**Semantic Search (HNSW):**
```rust
pub struct HnswIndex {
    graph: HashMap<NodeId, Vec<(NodeId, f32)>>,
    vectors: HashMap<NodeId, Vec<f32>>,
    params: HnswParams,
}

impl HnswIndex {
    pub fn search(&self, query: &[f32], k: usize) -> Vec<(NodeId, f32)> {
        // 1. Select entry point
        // 2. Greedy search to layer 0
        // 3. Return k nearest neighbors
    }
}
```

**Fuzzy Search (Trigrams):**
```rust
pub fn fuzzy_search_entities(
    db: &DB,
    tenant_id: &str,
    query: &str,
    threshold: f32
) -> Result<Vec<Entity>> {
    // 1. Generate trigrams from query
    let trigrams = generate_trigrams(query);

    // 2. Lookup entities for each trigram
    let candidates = collect_candidates(db, tenant_id, &trigrams)?;

    // 3. Rank by edit distance
    let ranked = rank_by_similarity(query, candidates, threshold);

    Ok(ranked)
}
```

### Performance Optimizations

**Write Batches:**
```rust
pub async fn batch_create_resources(&self, resources: Vec<Resource>) -> Result<Vec<ResourceId>> {
    let mut batch = WriteBatch::default();

    for resource in resources {
        let id = ResourceId::new();
        let key = format!("resource:{}:{}", self.tenant_id, id);
        batch.put(&key, serialize(&resource)?);
    }

    self.db.write(batch)?;
    Ok(ids)
}
```

**Caching:**
```rust
pub struct MemoryEngine {
    db: Arc<DB>,
    entity_cache: Arc<Cache<EntityId, Entity>>,  // LRU cache
    embedding_cache: Arc<Cache<ResourceId, Vec<f32>>>,
}
```

**Async I/O:**
```rust
// Use tokio for async RocksDB operations
pub async fn get_resource(&self, id: &ResourceId) -> Result<Resource> {
    let db = self.db.clone();
    let key = format!("resource:{}:{}", self.tenant_id, id);

    tokio::task::spawn_blocking(move || {
        db.get(&key).map(|data| deserialize(&data))
    }).await?
}
```

## Dependencies

```toml
[dependencies]
rocksdb = "0.22"
serde = { version = "1.0", features = ["derive"] }
tokio = { version = "1.0", features = ["full"] }
pyo3 = { version = "0.22", features = ["extension-module"] }
thiserror = "1.0"
```

## Testing

**Unit Tests:**
```rust
#[cfg(test)]
mod tests {
    #[tokio::test]
    async fn test_create_resource() {
        let engine = MemoryEngine::new_temp("test-tenant").unwrap();
        let resource = Resource { content: "test".into(), ..Default::default() };
        let id = engine.create_resource(resource).await.unwrap();
        assert!(!id.is_empty());
    }
}
```

**Integration Tests:**
```rust
// tests/integration/memory_test.rs
#[tokio::test]
async fn test_hybrid_search() {
    let engine = setup_test_engine().await;
    // Test semantic + fuzzy + graph search
}
```

**Benchmarks:**
```rust
// benches/memory_bench.rs
use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn benchmark_search(c: &mut Criterion) {
    c.bench_function("semantic_search_k10", |b| {
        b.iter(|| engine.search_resources(black_box(query), 10))
    });
}
```

## Error Handling

```rust
#[derive(thiserror::Error, Debug)]
pub enum MemoryError {
    #[error("Resource not found: {0}")]
    ResourceNotFound(ResourceId),

    #[error("Database error: {0}")]
    DatabaseError(#[from] rocksdb::Error),

    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),

    #[error("Invalid tenant: {0}")]
    InvalidTenant(String),
}

pub type Result<T> = std::result::Result<T, MemoryError>;
```

## Observability

```rust
use tracing::{info, warn, error, instrument};

#[instrument(skip(self))]
pub async fn search_resources(&self, query: &SearchQuery) -> Result<Vec<ScoredResource>> {
    info!("Searching resources with query: {}", query);

    let results = self.execute_search(query).await?;

    info!("Found {} results", results.len());
    Ok(results)
}
```
