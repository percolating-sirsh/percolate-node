# Rust REM database implementation plan

## Overview

This document outlines the implementation plan for porting the REM (Resources-Entities-Moments) database from the Python spike to a production-grade Rust implementation with PyO3 bindings.

**Goal**: Build a high-performance, embedded database with:
- Entity storage with JSON schema validation
- REM semantics (Resources, Entities, Moments)
- Natural language query interface
- Built-in embeddings with `fastembed-rs` (Rust port of embedding-anything)
- gRPC replication protocol
- SQL aggregates, filters, and query planning
- HNSW vector search
- Graph traversal

## Learnings from Python spike

### What worked well

**Architecture patterns:**
- Unified entity storage (all tables as entities with `type` field)
- JSON Schema-based table definitions (Pydantic models)
- Dual embedding support (default + alternative)
- Background worker for async embedding generation
- WAL-based replication with watermarks
- Secondary indexes for fast lookups

**Query patterns:**
- SQL with semantic similarity functions (`embedding.cosine(query)`)
- Natural language → SQL via LLM
- Multi-stage queries (SQL → vector → graph)
- Entity lookup for global search

**Performance:**
- Vector search: ~1ms p50 (HNSW, 384-dim)
- Indexed queries: 44% faster than full scan
- Entity lookup: <1ms (direct key access)

### What needs improvement

**Performance bottlenecks:**
- Python overhead for large scans
- Single-threaded execution
- No query parallelization
- Embedding generation blocks (even with worker thread)

**Missing features:**
- JOIN support (planned but not implemented)
- SQL aggregations (COUNT, SUM, AVG, GROUP BY)
- Query optimization and planning
- Streaming results (loads all into memory)

**Replication:**
- Works but needs production hardening
- No encryption (infrastructure ready)
- No authentication
- Limited metrics/observability

## Rust implementation architecture

### Project structure

```
percolate-core/              # Rust crate (PyO3)
├── Cargo.toml
├── build.rs                 # Proto compilation
├── proto/
│   └── replication.proto    # gRPC protocol
├── src/
│   ├── lib.rs              # PyO3 bindings
│   ├── memory/             # REM engine
│   │   ├── mod.rs          # Memory module interface
│   │   ├── database.rs     # Core database operations
│   │   ├── resources.rs    # Resource operations
│   │   ├── entities.rs     # Entity graph operations
│   │   ├── moments.rs      # Temporal indexing
│   │   ├── schema.rs       # JSON Schema registry
│   │   ├── index.rs        # Secondary indexes
│   │   └── wal.rs          # Write-ahead log
│   ├── embeddings/         # Vector operations
│   │   ├── mod.rs          # Embedding module interface
│   │   ├── provider.rs     # Embedding provider trait
│   │   ├── fastembed.rs    # fastembed-rs integration
│   │   ├── index.rs        # HNSW vector index
│   │   └── worker.rs       # Async embedding worker
│   ├── query/              # Query layer
│   │   ├── mod.rs          # Query module interface
│   │   ├── parser.rs       # SQL parser (sqlparser-rs)
│   │   ├── planner.rs      # Query planner
│   │   ├── executor.rs     # Query executor
│   │   ├── aggregations.rs # Aggregation functions
│   │   ├── joins.rs        # Join algorithms
│   │   └── predicates.rs   # Predicate evaluation
│   ├── replication/        # gRPC replication
│   │   ├── mod.rs          # Replication module interface
│   │   ├── server.rs       # gRPC server
│   │   ├── client.rs       # gRPC client
│   │   ├── manager.rs      # Replication manager
│   │   ├── peer.rs         # Peer discovery
│   │   └── proto.rs        # Generated proto code
│   ├── storage/            # RocksDB backend
│   │   ├── mod.rs          # Storage module interface
│   │   ├── rocksdb.rs      # RocksDB wrapper
│   │   ├── keys.rs         # Key encoding/decoding
│   │   └── batch.rs        # Write batches
│   ├── types/              # Core types
│   │   ├── mod.rs          # Types module interface
│   │   ├── entity.rs       # Entity, Edge types
│   │   ├── resource.rs     # Resource type
│   │   ├── moment.rs       # Moment type
│   │   ├── query.rs        # Query types
│   │   └── error.rs        # Error types
│   └── utils/              # Utilities
│       ├── mod.rs
│       ├── codec.rs        # Encoding/decoding
│       └── tracing.rs      # OpenTelemetry
└── tests/
    ├── integration/        # Integration tests
    │   ├── test_crud.rs
    │   ├── test_search.rs
    │   ├── test_replication.rs
    │   └── test_queries.rs
    └── benchmarks/         # Criterion benchmarks
        ├── vector_search.rs
        ├── entity_scan.rs
        └── aggregations.rs
```

### Dependencies (Cargo.toml)

```toml
[package]
name = "percolate-core"
version = "0.1.0"
edition = "2021"

[lib]
name = "percolate_core"
crate-type = ["cdylib", "rlib"]

[dependencies]
# PyO3 bindings
pyo3 = { version = "0.21", features = ["extension-module"] }
pyo3-asyncio = { version = "0.21", features = ["tokio-runtime"] }

# Storage
rocksdb = "0.22"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
bincode = "1.3"

# Embeddings
fastembed = "3.0"  # Rust port of embedding-anything
hnsw = "0.11"      # Or usearch for better performance
ndarray = "0.15"

# Query layer
sqlparser = "0.47"  # SQL parser
datafusion = "37.0" # Optional: for complex analytics
rayon = "1.8"       # Parallel execution

# Replication
tonic = "0.11"      # gRPC framework
tonic-build = "0.11"
prost = "0.12"      # Proto serialization
tokio = { version = "1.36", features = ["full"] }
tokio-stream = "0.1"

# Schema validation
jsonschema = "0.17"
schemars = "0.8"

# Error handling
thiserror = "1.0"
anyhow = "1.0"

# Observability
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
opentelemetry = "0.22"
opentelemetry-otlp = "0.15"

# Utilities
uuid = { version = "1.7", features = ["v4", "serde"] }
chrono = { version = "0.4", features = ["serde"] }
dashmap = "5.5"     # Concurrent hashmap

[dev-dependencies]
criterion = { version = "0.5", features = ["html_reports"] }
proptest = "1.4"
tempfile = "3.10"

[build-dependencies]
tonic-build = "0.11"

[[bench]]
name = "vector_search"
harness = false

[[bench]]
name = "entity_scan"
harness = false
```

## Core implementation details

### 1. Storage layer (RocksDB)

**Key design principles:**
- Tenant isolation via key prefixes
- Column families for logical separation
- Zero-copy operations where possible
- Atomic write batches

**Key patterns:**
```rust
// src/storage/keys.rs

pub enum KeyPrefix {
    Schema,      // schema:{tenant}:{name}
    Entity,      // entity:{tenant}:{uuid}
    Edge,        // edge:{tenant}:{src}:{dst}:{type}
    Index,       // index:{field}:{tenant}:{value}
    Embedding,   // embedding:{tenant}:{id}
    Wal,         // wal:{tenant}:seq
    WalEntry,    // wal:{tenant}:entry:{seq}
}

pub struct EntityKey {
    tenant_id: String,
    entity_id: Uuid,
}

impl EntityKey {
    pub fn encode(&self) -> Vec<u8> {
        format!("entity:{}:{}", self.tenant_id, self.entity_id)
            .into_bytes()
    }

    pub fn decode(bytes: &[u8]) -> Result<Self, KeyError> {
        // Parse "entity:{tenant}:{uuid}"
        // ...
    }
}
```

**Column families:**
```rust
// src/storage/rocksdb.rs

pub struct Storage {
    db: rocksdb::DB,
    cf_entities: rocksdb::ColumnFamily,
    cf_edges: rocksdb::ColumnFamily,
    cf_embeddings: rocksdb::ColumnFamily,
    cf_indexes: rocksdb::ColumnFamily,
    cf_wal: rocksdb::ColumnFamily,
}

impl Storage {
    pub fn open(path: &Path) -> Result<Self, StorageError> {
        let mut opts = rocksdb::Options::default();
        opts.create_if_missing(true);
        opts.create_missing_column_families(true);

        // Optimize for read-heavy workload
        opts.set_level_compaction_dynamic_level_bytes(true);
        opts.set_max_background_jobs(4);

        let cf_descriptors = vec![
            rocksdb::ColumnFamilyDescriptor::new("entities", opts.clone()),
            rocksdb::ColumnFamilyDescriptor::new("edges", opts.clone()),
            rocksdb::ColumnFamilyDescriptor::new("embeddings", opts.clone()),
            rocksdb::ColumnFamilyDescriptor::new("indexes", opts.clone()),
            rocksdb::ColumnFamilyDescriptor::new("wal", opts.clone()),
        ];

        let db = rocksdb::DB::open_cf_descriptors(&opts, path, cf_descriptors)?;

        Ok(Storage {
            cf_entities: db.cf_handle("entities").unwrap(),
            cf_edges: db.cf_handle("edges").unwrap(),
            cf_embeddings: db.cf_handle("embeddings").unwrap(),
            cf_indexes: db.cf_handle("indexes").unwrap(),
            cf_wal: db.cf_handle("wal").unwrap(),
            db,
        })
    }
}
```

### 2. Entity storage with JSON schema

**Schema registry:**
```rust
// src/memory/schema.rs

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Schema {
    pub name: String,
    pub fqn: String,
    pub version: String,
    pub category: SchemaCategory,
    pub json_schema: serde_json::Value,
    pub indexed_fields: Vec<String>,
    pub embedding_fields: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SchemaCategory {
    System,
    Agents,
    Public,
    User,
}

pub struct SchemaRegistry {
    schemas: DashMap<String, Schema>,
    validator_cache: DashMap<String, jsonschema::JSONSchema>,
}

impl SchemaRegistry {
    pub fn register(&self, schema: Schema) -> Result<(), SchemaError> {
        // Compile JSON schema for validation
        let validator = jsonschema::JSONSchema::compile(&schema.json_schema)?;

        self.schemas.insert(schema.name.clone(), schema.clone());
        self.validator_cache.insert(schema.name.clone(), validator);

        Ok(())
    }

    pub fn validate(&self, table: &str, data: &serde_json::Value) -> Result<(), SchemaError> {
        let validator = self.validator_cache
            .get(table)
            .ok_or(SchemaError::NotFound(table.to_string()))?;

        validator.validate(data)?;
        Ok(())
    }
}
```

**Entity operations:**
```rust
// src/memory/entities.rs

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Entity {
    pub id: Uuid,
    pub r#type: String,  // Table name
    pub properties: serde_json::Value,
    pub embedding: Option<Vec<f32>>,
    pub embedding_alt: Option<Vec<f32>>,
    pub edges: Vec<EdgeRef>,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub modified_at: chrono::DateTime<chrono::Utc>,
    pub deleted_at: Option<chrono::DateTime<chrono::Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EdgeRef {
    pub entity_id: Uuid,
    pub edge_type: String,
    pub direction: Direction,
}

impl Database {
    pub async fn insert_entity(
        &self,
        tenant_id: &str,
        table: &str,
        properties: serde_json::Value,
    ) -> Result<Uuid, DatabaseError> {
        // Validate against schema
        self.schema_registry.validate(table, &properties)?;

        let entity_id = Uuid::new_v4();
        let now = chrono::Utc::now();

        let entity = Entity {
            id: entity_id,
            r#type: table.to_string(),
            properties,
            embedding: None,
            embedding_alt: None,
            edges: Vec::new(),
            created_at: now,
            modified_at: now,
            deleted_at: None,
        };

        // Write to RocksDB
        let key = EntityKey { tenant_id: tenant_id.to_string(), entity_id };
        let value = bincode::serialize(&entity)?;

        let mut batch = rocksdb::WriteBatch::default();
        batch.put_cf(&self.storage.cf_entities, key.encode(), value);

        // Update secondary indexes
        let schema = self.schema_registry.get(table)?;
        for field in &schema.indexed_fields {
            if let Some(field_value) = entity.properties.get(field) {
                let index_key = IndexKey {
                    tenant_id: tenant_id.to_string(),
                    field: field.clone(),
                    value: field_value.to_string(),
                    entity_id,
                };
                batch.put_cf(&self.storage.cf_indexes, index_key.encode(), b"");
            }
        }

        // Append to WAL
        self.append_wal(tenant_id, WalOperation::Insert { entity_id, table: table.to_string(), properties: entity.properties.clone() })?;

        // Write atomically
        self.storage.db.write(batch)?;

        // Queue embedding generation
        if !schema.embedding_fields.is_empty() {
            self.embedding_worker.queue_entity(tenant_id, entity_id).await?;
        }

        Ok(entity_id)
    }
}
```

### 3. Embeddings with fastembed-rs

**Embedding provider trait:**
```rust
// src/embeddings/provider.rs

#[async_trait::async_trait]
pub trait EmbeddingProvider: Send + Sync {
    async fn embed(&self, text: &str) -> Result<Vec<f32>, EmbeddingError>;
    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>, EmbeddingError>;
    fn dimensions(&self) -> usize;
    fn metric(&self) -> DistanceMetric;
}

pub enum DistanceMetric {
    Cosine,
    InnerProduct,
    L2,
}
```

**fastembed-rs integration:**
```rust
// src/embeddings/fastembed.rs

use fastembed::{EmbeddingModel, InitOptions, TextEmbedding};

pub struct FastEmbedProvider {
    model: TextEmbedding,
    dimensions: usize,
}

impl FastEmbedProvider {
    pub fn new(model_name: &str) -> Result<Self, EmbeddingError> {
        let model = TextEmbedding::try_new(
            InitOptions::new(EmbeddingModel::from_name(model_name)?).with_show_download_progress(true)
        )?;

        let dimensions = match model_name {
            "all-MiniLM-L6-v2" => 384,
            "nomic-embed-text-v1.5" => 768,
            "text-embedding-3-small" => 1536,
            _ => return Err(EmbeddingError::UnsupportedModel(model_name.to_string())),
        };

        Ok(Self { model, dimensions })
    }
}

#[async_trait::async_trait]
impl EmbeddingProvider for FastEmbedProvider {
    async fn embed(&self, text: &str) -> Result<Vec<f32>, EmbeddingError> {
        let embeddings = self.model.embed(vec![text.to_string()], None)?;
        Ok(embeddings[0].clone())
    }

    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>, EmbeddingError> {
        let embeddings = self.model.embed(texts.to_vec(), None)?;
        Ok(embeddings)
    }

    fn dimensions(&self) -> usize {
        self.dimensions
    }

    fn metric(&self) -> DistanceMetric {
        DistanceMetric::Cosine
    }
}
```

**Background embedding worker:**
```rust
// src/embeddings/worker.rs

use tokio::sync::mpsc;

pub struct EmbeddingWorker {
    tx: mpsc::UnboundedSender<EmbeddingTask>,
}

pub struct EmbeddingTask {
    pub tenant_id: String,
    pub entity_id: Uuid,
}

impl EmbeddingWorker {
    pub fn new(provider: Arc<dyn EmbeddingProvider>, storage: Arc<Storage>) -> Self {
        let (tx, mut rx) = mpsc::unbounded_channel();

        tokio::spawn(async move {
            while let Some(task) = rx.recv().await {
                if let Err(e) = process_embedding_task(&task, &provider, &storage).await {
                    tracing::error!("Embedding task failed: {}", e);
                }
            }
        });

        Self { tx }
    }

    pub async fn queue_entity(&self, tenant_id: &str, entity_id: Uuid) -> Result<(), EmbeddingError> {
        self.tx.send(EmbeddingTask {
            tenant_id: tenant_id.to_string(),
            entity_id,
        })?;
        Ok(())
    }
}

async fn process_embedding_task(
    task: &EmbeddingTask,
    provider: &Arc<dyn EmbeddingProvider>,
    storage: &Arc<Storage>,
) -> Result<(), EmbeddingError> {
    // Load entity
    let key = EntityKey { tenant_id: task.tenant_id.clone(), entity_id: task.entity_id };
    let value = storage.db.get_cf(&storage.cf_entities, key.encode())?
        .ok_or(EmbeddingError::EntityNotFound(task.entity_id))?;

    let mut entity: Entity = bincode::deserialize(&value)?;

    // Extract embedding fields
    let text = extract_embedding_text(&entity)?;

    // Generate embedding
    let embedding = provider.embed(&text).await?;

    // Update entity
    entity.embedding = Some(embedding.clone());
    entity.modified_at = chrono::Utc::now();

    // Write back
    let value = bincode::serialize(&entity)?;
    storage.db.put_cf(&storage.cf_entities, key.encode(), value)?;

    // Update vector index
    storage.db.put_cf(
        &storage.cf_embeddings,
        format!("embedding:{}:{}", task.tenant_id, task.entity_id).as_bytes(),
        bincode::serialize(&embedding)?,
    )?;

    Ok(())
}
```

### 4. HNSW vector search

**Vector index:**
```rust
// src/embeddings/index.rs

use hnsw::Hnsw;

pub struct VectorIndex {
    index: Hnsw<'static, f32, DistCosine>,
    id_map: DashMap<Uuid, usize>,  // entity_id → hnsw_id
    reverse_map: DashMap<usize, Uuid>,  // hnsw_id → entity_id
}

impl VectorIndex {
    pub fn new(dimensions: usize) -> Self {
        let index = Hnsw::new(
            16,   // M (connections per layer)
            200,  // ef_construction
            dimensions,
        );

        Self {
            index,
            id_map: DashMap::new(),
            reverse_map: DashMap::new(),
        }
    }

    pub fn insert(&mut self, entity_id: Uuid, embedding: &[f32]) -> Result<(), VectorError> {
        let hnsw_id = self.index.insert(embedding);
        self.id_map.insert(entity_id, hnsw_id);
        self.reverse_map.insert(hnsw_id, entity_id);
        Ok(())
    }

    pub fn search(&self, query: &[f32], k: usize) -> Result<Vec<(Uuid, f32)>, VectorError> {
        let results = self.index.search(query, k, 50);  // ef_search=50

        let mut scored_entities = Vec::new();
        for (hnsw_id, distance) in results {
            if let Some(entity_id) = self.reverse_map.get(&hnsw_id) {
                let score = 1.0 - distance;  // Convert distance to similarity
                scored_entities.push((*entity_id, score));
            }
        }

        Ok(scored_entities)
    }

    pub fn save(&self, path: &Path) -> Result<(), VectorError> {
        // Serialize index + mappings
        let data = bincode::serialize(&(&self.index, &self.id_map, &self.reverse_map))?;
        std::fs::write(path, data)?;
        Ok(())
    }

    pub fn load(path: &Path) -> Result<Self, VectorError> {
        let data = std::fs::read(path)?;
        let (index, id_map, reverse_map) = bincode::deserialize(&data)?;
        Ok(Self { index, id_map, reverse_map })
    }
}
```

### 5. Query layer with SQL aggregates

**SQL parser:**
```rust
// src/query/parser.rs

use sqlparser::ast::{Expr, Select, Statement};
use sqlparser::dialect::GenericDialect;
use sqlparser::parser::Parser;

pub struct QueryParser {
    dialect: GenericDialect,
}

impl QueryParser {
    pub fn parse(&self, sql: &str) -> Result<QueryPlan, QueryError> {
        let ast = Parser::parse_sql(&self.dialect, sql)?;

        match &ast[0] {
            Statement::Query(query) => {
                self.parse_select(&query.body)?
            }
            _ => Err(QueryError::UnsupportedStatement),
        }
    }

    fn parse_select(&self, body: &SetExpr) -> Result<QueryPlan, QueryError> {
        match body {
            SetExpr::Select(select) => {
                let table = self.extract_table(select)?;
                let projections = self.extract_projections(&select.projection)?;
                let predicates = self.extract_predicates(&select.selection)?;
                let aggregations = self.extract_aggregations(&select.projection)?;
                let group_by = self.extract_group_by(&select.group_by)?;
                let order_by = self.extract_order_by(&select.order_by)?;

                Ok(QueryPlan {
                    table,
                    projections,
                    predicates,
                    aggregations,
                    group_by,
                    order_by,
                    limit: select.limit,
                    offset: select.offset,
                })
            }
            _ => Err(QueryError::UnsupportedQuery),
        }
    }
}
```

**Query planner:**
```rust
// src/query/planner.rs

#[derive(Debug)]
pub struct QueryPlan {
    pub table: String,
    pub projections: Vec<String>,
    pub predicates: Vec<Predicate>,
    pub aggregations: Vec<Aggregation>,
    pub group_by: Vec<String>,
    pub order_by: Vec<OrderBy>,
    pub limit: Option<usize>,
    pub offset: Option<usize>,
}

#[derive(Debug)]
pub enum Predicate {
    Eq { field: String, value: serde_json::Value },
    Ne { field: String, value: serde_json::Value },
    Gt { field: String, value: serde_json::Value },
    Lt { field: String, value: serde_json::Value },
    In { field: String, values: Vec<serde_json::Value> },
    VectorSimilar { field: String, query: Vec<f32>, top_k: usize, min_score: f32 },
    And(Vec<Predicate>),
    Or(Vec<Predicate>),
}

#[derive(Debug)]
pub struct Aggregation {
    pub func: AggregateFunc,
    pub field: Option<String>,
    pub alias: String,
}

#[derive(Debug)]
pub enum AggregateFunc {
    Count,
    Sum,
    Avg,
    Min,
    Max,
}

pub struct Planner {
    schema_registry: Arc<SchemaRegistry>,
}

impl Planner {
    pub fn optimize(&self, plan: QueryPlan) -> Result<ExecutionPlan, PlannerError> {
        // 1. Predicate pushdown
        let pushdown_predicates = self.extract_pushdown_predicates(&plan.predicates)?;

        // 2. Index selection
        let index_scan = self.select_index(&plan.table, &pushdown_predicates)?;

        // 3. Determine execution strategy
        let strategy = if !plan.aggregations.is_empty() {
            ExecutionStrategy::Aggregate {
                group_by: plan.group_by.clone(),
                aggregations: plan.aggregations.clone(),
            }
        } else if plan.predicates.iter().any(|p| matches!(p, Predicate::VectorSimilar { .. })) {
            ExecutionStrategy::VectorSearch
        } else {
            ExecutionStrategy::Scan
        };

        Ok(ExecutionPlan {
            table: plan.table,
            index_scan,
            predicates: plan.predicates,
            strategy,
            projections: plan.projections,
            order_by: plan.order_by,
            limit: plan.limit,
            offset: plan.offset,
        })
    }
}
```

**Query executor:**
```rust
// src/query/executor.rs

pub struct Executor {
    storage: Arc<Storage>,
    schema_registry: Arc<SchemaRegistry>,
    vector_indexes: DashMap<String, Arc<VectorIndex>>,  // tenant_id → index
}

impl Executor {
    pub async fn execute(&self, plan: ExecutionPlan) -> Result<QueryResult, ExecutorError> {
        match plan.strategy {
            ExecutionStrategy::Scan => self.execute_scan(plan).await,
            ExecutionStrategy::VectorSearch => self.execute_vector_search(plan).await,
            ExecutionStrategy::Aggregate { group_by, aggregations } => {
                self.execute_aggregate(plan, group_by, aggregations).await
            }
        }
    }

    async fn execute_aggregate(
        &self,
        plan: ExecutionPlan,
        group_by: Vec<String>,
        aggregations: Vec<Aggregation>,
    ) -> Result<QueryResult, ExecutorError> {
        // Stage 1: Scan and filter
        let entities = self.scan_entities(&plan).await?;

        // Stage 2: Group by
        let groups = self.group_entities(entities, &group_by)?;

        // Stage 3: Apply aggregations
        let results = groups.into_par_iter()  // Rayon parallel iterator
            .map(|(group_key, group_entities)| {
                let mut row = serde_json::Map::new();

                // Add group by fields
                for (i, field) in group_by.iter().enumerate() {
                    row.insert(field.clone(), group_key[i].clone());
                }

                // Apply aggregation functions
                for agg in &aggregations {
                    let value = match agg.func {
                        AggregateFunc::Count => {
                            serde_json::Value::Number(group_entities.len().into())
                        }
                        AggregateFunc::Sum => {
                            let sum: f64 = group_entities.iter()
                                .filter_map(|e| e.properties.get(agg.field.as_ref()?))
                                .filter_map(|v| v.as_f64())
                                .sum();
                            serde_json::Value::Number(sum.into())
                        }
                        AggregateFunc::Avg => {
                            let values: Vec<f64> = group_entities.iter()
                                .filter_map(|e| e.properties.get(agg.field.as_ref()?))
                                .filter_map(|v| v.as_f64())
                                .collect();
                            let avg = values.iter().sum::<f64>() / values.len() as f64;
                            serde_json::Value::Number(avg.into())
                        }
                        AggregateFunc::Min => {
                            // Similar to Sum/Avg
                        }
                        AggregateFunc::Max => {
                            // Similar to Sum/Avg
                        }
                    };
                    row.insert(agg.alias.clone(), value);
                }

                serde_json::Value::Object(row)
            })
            .collect();

        Ok(QueryResult { rows: results })
    }
}
```

### 6. gRPC replication

**Proto definition:**
```protobuf
// proto/replication.proto

syntax = "proto3";

package percolate.replication;

service Replication {
  rpc Subscribe(SubscribeRequest) returns (stream WALEntry);
  rpc GetWatermark(WatermarkRequest) returns (WatermarkResponse);
  rpc Heartbeat(HeartbeatRequest) returns (HeartbeatResponse);
}

message SubscribeRequest {
  string peer_id = 1;
  string tenant_id = 2;
  uint64 watermark = 3;
}

message WALEntry {
  uint64 seq = 1;
  string operation = 2;  // INSERT, UPDATE, DELETE
  bytes key = 3;
  bytes value = 4;
  int64 timestamp = 5;
  string tenant_id = 6;
}

message WatermarkRequest {
  string peer_id = 1;
  string tenant_id = 2;
}

message WatermarkResponse {
  uint64 watermark = 1;
}

message HeartbeatRequest {
  string peer_id = 1;
}

message HeartbeatResponse {
  bool alive = 1;
}
```

**Replication server:**
```rust
// src/replication/server.rs

use tonic::{transport::Server, Request, Response, Status};
use tokio_stream::wrappers::ReceiverStream;

pub struct ReplicationServicer {
    database: Arc<Database>,
    broadcast_tx: broadcast::Sender<WALEntry>,
}

#[tonic::async_trait]
impl Replication for ReplicationServicer {
    type SubscribeStream = ReceiverStream<Result<WALEntry, Status>>;

    async fn subscribe(
        &self,
        request: Request<SubscribeRequest>,
    ) -> Result<Response<Self::SubscribeStream>, Status> {
        let req = request.into_inner();

        tracing::info!(
            "Peer {} subscribing from watermark {}",
            req.peer_id,
            req.watermark
        );

        let (tx, rx) = mpsc::channel(128);

        // Send historical entries first
        let historical = self.database
            .get_wal_entries(&req.tenant_id, req.watermark, None)?;

        for entry in historical {
            tx.send(Ok(entry)).await.map_err(|_| Status::internal("Channel closed"))?;
        }

        // Subscribe to new entries
        let mut broadcast_rx = self.broadcast_tx.subscribe();

        tokio::spawn(async move {
            while let Ok(entry) = broadcast_rx.recv().await {
                if entry.tenant_id == req.tenant_id {
                    if tx.send(Ok(entry)).await.is_err() {
                        break;
                    }
                }
            }
        });

        Ok(Response::new(ReceiverStream::new(rx)))
    }

    async fn get_watermark(
        &self,
        request: Request<WatermarkRequest>,
    ) -> Result<Response<WatermarkResponse>, Status> {
        let req = request.into_inner();
        let watermark = self.database.get_wal_seq(&req.tenant_id)?;

        Ok(Response::new(WatermarkResponse { watermark }))
    }
}
```

**Replication client:**
```rust
// src/replication/client.rs

pub struct ReplicationClient {
    client: ReplicationClient,
    peer_id: String,
    tenant_id: String,
    watermark: Arc<AtomicU64>,
}

impl ReplicationClient {
    pub async fn connect(address: &str, peer_id: String, tenant_id: String) -> Result<Self, ReplicationError> {
        let client = ReplicationClient::connect(address).await?;

        let watermark = Arc::new(AtomicU64::new(0));

        Ok(Self {
            client,
            peer_id,
            tenant_id,
            watermark,
        })
    }

    pub async fn start_sync(&mut self, database: Arc<Database>) -> Result<(), ReplicationError> {
        let current_watermark = self.watermark.load(Ordering::SeqCst);

        let request = SubscribeRequest {
            peer_id: self.peer_id.clone(),
            tenant_id: self.tenant_id.clone(),
            watermark: current_watermark,
        };

        let mut stream = self.client.subscribe(request).await?.into_inner();

        while let Some(entry) = stream.message().await? {
            // Apply entry to local database
            database.apply_wal_entry(&entry).await?;

            // Update watermark
            self.watermark.store(entry.seq, Ordering::SeqCst);

            tracing::debug!("Applied entry seq={} from peer", entry.seq);
        }

        Ok(())
    }
}
```

### 7. PyO3 bindings

**Python API:**
```rust
// src/lib.rs

use pyo3::prelude::*;

#[pyclass]
pub struct REMDatabase {
    inner: Arc<Database>,
    runtime: tokio::runtime::Runtime,
}

#[pymethods]
impl REMDatabase {
    #[new]
    pub fn new(tenant_id: String, path: String) -> PyResult<Self> {
        let runtime = tokio::runtime::Runtime::new()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        let database = runtime.block_on(async {
            Database::open(&path, &tenant_id).await
        }).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        Ok(Self {
            inner: Arc::new(database),
            runtime,
        })
    }

    pub fn insert(&self, table: String, properties: PyObject) -> PyResult<String> {
        let properties: serde_json::Value = Python::with_gil(|py| {
            pythonize::depythonize(properties.as_ref(py))
        })?;

        let entity_id = self.runtime.block_on(async {
            self.inner.insert_entity(&self.inner.tenant_id, &table, properties).await
        }).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        Ok(entity_id.to_string())
    }

    pub fn sql(&self, query: String) -> PyResult<Vec<PyObject>> {
        let results = self.runtime.block_on(async {
            self.inner.execute_sql(&query).await
        }).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        Python::with_gil(|py| {
            results.into_iter()
                .map(|entity| pythonize::pythonize(py, &entity))
                .collect::<Result<Vec<_>, _>>()
        }).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
    }

    pub fn search(&self, query: String, limit: usize) -> PyResult<Vec<PyObject>> {
        let results = self.runtime.block_on(async {
            self.inner.search_resources(&query, limit).await
        }).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        Python::with_gil(|py| {
            results.into_iter()
                .map(|entity| pythonize::pythonize(py, &entity))
                .collect::<Result<Vec<_>, _>>()
        }).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
    }
}

#[pymodule]
fn percolate_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<REMDatabase>()?;
    Ok(())
}
```

## Implementation phases

### Phase 1: Core storage and entities (3-4 weeks)

**Goals:**
- RocksDB storage layer with column families
- Entity CRUD operations
- JSON Schema validation
- Secondary indexes
- WAL for replication

**Deliverables:**
- `src/storage/` module complete
- `src/memory/entities.rs` complete
- `src/memory/schema.rs` complete
- Basic PyO3 bindings for insert/get
- Integration tests for CRUD

### Phase 2: Embeddings and vector search (2-3 weeks)

**Goals:**
- fastembed-rs integration
- Background embedding worker
- HNSW vector index
- Vector search queries

**Deliverables:**
- `src/embeddings/` module complete
- Dual embedding support (default + alt)
- Vector search with `embedding.cosine(query)`
- Benchmark: <5ms p50 for vector search

### Phase 3: Query layer (3-4 weeks)

**Goals:**
- SQL parser (sqlparser-rs)
- Query planner with optimization
- Predicate evaluation
- Aggregations (COUNT, SUM, AVG, GROUP BY)
- Basic joins (INNER, LEFT)

**Deliverables:**
- `src/query/` module complete
- Full SQL support for SELECT
- Parallel execution with Rayon
- Benchmark: aggregations <100ms for 10k entities

### Phase 4: gRPC replication (2-3 weeks)

**Goals:**
- gRPC server and client
- Bidirectional streaming
- Watermark persistence
- Peer discovery

**Deliverables:**
- `src/replication/` module complete
- Multi-peer replication working
- Integration test with 3 instances
- Replication latency <100ms

### Phase 5: Natural language query (1-2 weeks)

**Goals:**
- LLM query builder (port from Python)
- Multi-stage query execution
- Entity lookup (global search)

**Deliverables:**
- Natural language → SQL working
- Query confidence scoring
- Integration with query planner

### Phase 6: Production hardening (2-3 weeks)

**Goals:**
- Error handling and recovery
- Metrics and observability
- Performance optimization
- Security (encryption, auth)

**Deliverables:**
- OpenTelemetry instrumentation
- Comprehensive error types
- Security audit complete
- Production deployment guide

## Performance targets

### Latency (p50)

| Operation | Target | Python Baseline |
|-----------|--------|-----------------|
| Entity insert | <1ms | ~2-5ms |
| Entity get by ID | <0.5ms | <1ms |
| Vector search (k=10) | <5ms | ~1ms |
| Indexed SQL query | <10ms | ~50ms |
| Full scan (10k entities) | <50ms | ~100ms |
| Aggregation (10k entities) | <100ms | N/A |
| Replication latency | <100ms | ~2s |

### Throughput

| Operation | Target |
|-----------|--------|
| Insert | 50k+ ops/sec |
| Get | 100k+ ops/sec |
| Vector search | 10k+ queries/sec |
| SQL queries | 5k+ queries/sec |

### Memory

| Component | Budget |
|-----------|--------|
| Vector index (100k entities, 384-dim) | ~150MB |
| RocksDB cache | 256MB (configurable) |
| Schema registry | <10MB |
| Per-tenant overhead | <20MB |

## Testing strategy

### Unit tests

- All public functions have tests
- Proptest for predicate evaluation
- Error path coverage

### Integration tests

- Full CRUD workflows
- Multi-stage queries
- Replication scenarios
- Schema validation

### Benchmarks

- Criterion for all hot paths
- Compare against Python baseline
- Regression detection in CI

### Stress tests

- Large datasets (1M+ entities)
- High concurrency (1000+ connections)
- Network partition scenarios
- Memory leak detection

## Migration from Python spike

### Data migration

**Export from Python:**
```python
# Export all entities to JSONL
db = REMDatabase(tenant_id="test", path="./data")
with open("export.jsonl", "w") as f:
    for entity in db.scan_all_entities():
        f.write(orjson.dumps(entity.dict()) + b"\n")
```

**Import to Rust:**
```python
# Import from JSONL
db = percolate_core.REMDatabase(tenant_id="test", path="./data-rust")
with open("export.jsonl") as f:
    for line in f:
        entity = json.loads(line)
        db.insert(entity["type"], entity["properties"])
```

### API compatibility

**Keep Python API surface identical:**
```python
# Works with both Python and Rust implementations
db.insert("resources", {"name": "Test", "content": "..."})
results = db.sql("SELECT * FROM resources WHERE status = 'active'")
results = db.search("query text", limit=10)
```

## Success criteria

### Functionality
- [ ] All Python spike features ported
- [ ] Natural language queries working
- [ ] Replication between 3+ instances
- [ ] SQL aggregations and joins

### Performance
- [ ] 10x faster than Python for large scans
- [ ] <5ms vector search (p50)
- [ ] <100ms replication latency
- [ ] Handles 1M+ entities smoothly

### Quality
- [ ] 90%+ code coverage
- [ ] Zero memory leaks (valgrind)
- [ ] Security audit passed
- [ ] Documentation complete

### Production readiness
- [ ] OpenTelemetry instrumentation
- [ ] Graceful error handling
- [ ] Backward compatible migrations
- [ ] Deployment guide

## Next steps

1. **Create Rust project structure** (percolate-core/)
2. **Implement storage layer** (Phase 1)
3. **Add embeddings** (Phase 2)
4. **Build query layer** (Phase 3)
5. **Add replication** (Phase 4)
6. **Port NL query** (Phase 5)
7. **Production hardening** (Phase 6)

**Estimated timeline**: 16-22 weeks for full implementation

**Team size**: 1-2 engineers

**Dependencies**: None (all Rust crates are stable)
