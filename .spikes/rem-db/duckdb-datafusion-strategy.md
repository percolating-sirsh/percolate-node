# DuckDB indexes vs DataFusion strategy

## Two approaches for SQL over RocksDB

### Approach 1: Persist indexes in DuckDB format (alongside RocksDB)
Store structured indexes in DuckDB/Parquet for filtering and aggregations, while keeping entities in RocksDB.

### Approach 2: DataFusion with RocksDB TableProvider (Rust-native)
Implement custom DataFusion TableProvider that reads directly from RocksDB in Rust.

---

## Approach 1: DuckDB as index/analytics layer

### Architecture

```
┌─────────────────────────────────────────────┐
│              REM Database                    │
├─────────────────────────────────────────────┤
│  RocksDB (source of truth)                  │
│  ├── entity:{tenant}:{uuid} → Entity JSON    │
│  ├── schema:{tenant}:{name} → Schema         │
│  └── edge:{tenant}:{src}:{dst} → Edge        │
├─────────────────────────────────────────────┤
│  DuckDB Indexes (for SQL queries)           │
│  ├── resources.parquet (indexed fields)     │
│  ├── agents.parquet (indexed fields)        │
│  └── sessions.parquet (indexed fields)      │
└─────────────────────────────────────────────┘
```

### Storage format options

#### Option A: Parquet files
```
.fs/db/{tenant}/
├── rocksdb/           # Source of truth
│   ├── 000001.sst
│   ├── CURRENT
│   └── MANIFEST
└── indexes/           # DuckDB indexes
    ├── resources.parquet
    ├── agents.parquet
    └── sessions.parquet
```

**Parquet features**:
- Columnar storage (fast aggregations)
- Built-in statistics (min/max, zonemaps)
- Bloom filters (for highly selective queries)
- Compression (save disk space)
- Portable (Apache Arrow ecosystem)

**What gets stored**:
```python
# resources.parquet contains:
{
    "id": UUID,
    "name": str,
    "category": str,
    "status": str,
    "created_at": timestamp,
    "priority": int,
    # ... other indexed fields
}
# NOT stored: content, embedding (stay in RocksDB)
```

#### Option B: DuckDB persistent database
```
.fs/db/{tenant}/
├── rocksdb/           # Source of truth
└── indexes/
    └── indexes.duckdb # DuckDB database file
```

**DuckDB database features**:
- All Parquet features PLUS:
- ART indexes (Adaptive Radix Tree)
- HyperLogLog statistics (better cardinality estimates)
- Zone maps (min/max indexes)
- Persistent indexes on disk

**Performance difference**:
- Parquet: Good for single queries
- DuckDB DB: Better for join-heavy workloads (HyperLogLog stats)

### Implementation strategy

#### Step 1: Schema definition (which fields to index)
```python
# In Pydantic model
class Resource(SystemFields):
    model_config = ConfigDict(
        json_schema_extra={
            "indexed_fields": ["category", "status", "priority", "created_at"],
            # NOT indexed: content (too large), embedding (vector)
        }
    )
```

#### Step 2: Sync RocksDB → DuckDB indexes
```python
class REMDatabase:
    def __init__(self, ...):
        self.db = rocksdict.Rdict(...)  # RocksDB
        self.duckdb = duckdb.connect(f'{path}/indexes/indexes.duckdb')

    def _build_indexes(self, table: str):
        """Build DuckDB indexes for a table."""

        # Get schema
        schema = self.get_schema(table)
        indexed_fields = schema.json_schema_extra.get("indexed_fields", [])

        # Scan RocksDB for all entities of this type
        entities = self.sql(f"SELECT * FROM {table}")

        # Extract indexed fields only
        records = [
            {
                "id": str(e.id),
                **{field: e.properties.get(field) for field in indexed_fields}
            }
            for e in entities
        ]

        # Write to DuckDB
        self.duckdb.execute(f"DROP TABLE IF EXISTS {table}")
        self.duckdb.execute(f"""
            CREATE TABLE {table} AS
            SELECT * FROM records
        """)

        # Create indexes on important fields
        for field in indexed_fields:
            if field in ["category", "status", "priority"]:
                self.duckdb.execute(f"CREATE INDEX idx_{table}_{field} ON {table}({field})")

    def rebuild_indexes(self):
        """Rebuild all indexes from RocksDB."""
        for schema_name in self.list_schemas():
            self._build_indexes(schema_name)
```

#### Step 3: Query routing
```python
def sql(self, query: str) -> list[dict]:
    """Execute SQL query with intelligent routing."""

    parsed = parse_sql(query)

    # Routing decision
    if _needs_aggregation(parsed) or _has_join(parsed):
        # Use DuckDB for aggregations/joins
        return self._query_duckdb(query)
    elif _is_vector_search(parsed):
        # Use RocksDB + HNSW for vector search
        return self._query_vector(parsed)
    else:
        # Use RocksDB for simple filters
        return self._query_rocksdb(parsed)

def _query_duckdb(self, sql: str) -> list[dict]:
    """Execute query via DuckDB indexes."""

    # Query returns only IDs
    result = self.duckdb.execute(sql).fetchall()

    # Hydrate full entities from RocksDB
    entity_ids = [row[0] for row in result]
    entities = [self.get_entity(uuid.UUID(id)) for id in entity_ids]

    return [e.model_dump() for e in entities]
```

#### Step 4: Incremental updates
```python
def insert(self, table: str, data: dict) -> UUID:
    """Insert entity and update indexes."""

    # Insert to RocksDB (source of truth)
    entity_id = self._insert_to_rocksdb(table, data)

    # Update DuckDB index incrementally
    schema = self.get_schema(table)
    indexed_fields = schema.json_schema_extra.get("indexed_fields", [])

    index_record = {
        "id": str(entity_id),
        **{field: data.get(field) for field in indexed_fields}
    }

    self.duckdb.execute(f"INSERT INTO {table} VALUES (?)", [index_record])

    return entity_id

def delete(self, table: str, entity_id: UUID):
    """Delete entity and update indexes."""

    # Soft delete in RocksDB
    self._soft_delete_in_rocksdb(table, entity_id)

    # Remove from DuckDB index
    self.duckdb.execute(f"DELETE FROM {table} WHERE id = ?", [str(entity_id)])
```

### Pros/cons of DuckDB indexes approach

**Pros**:
- **Fast aggregations**: Columnar format optimized for GROUP BY, COUNT, SUM
- **Fast joins**: DuckDB excels at multi-table joins
- **No duplication of large data**: Content and embeddings stay in RocksDB
- **Portable**: Parquet files can be used by other tools
- **Incremental updates**: Can update indexes without full rebuild
- **Python-native**: Easy to integrate
- **Proven**: Production-grade query engine

**Cons**:
- **Dual storage**: Must maintain consistency between RocksDB and DuckDB
- **Sync overhead**: Insert/update/delete must hit both stores
- **Disk space**: Indexes take additional space (~20-30% of RocksDB size)
- **Complexity**: Two storage systems to manage
- **Stale indexes**: Risk of indexes getting out of sync

**When to use**:
- Frequent aggregations (dashboards, analytics)
- Join-heavy workloads
- Need fast GROUP BY queries
- Willing to trade disk space for query speed

---

## Approach 2: DataFusion with RocksDB TableProvider (Rust)

### Architecture

```
┌─────────────────────────────────────────────┐
│         REM Database (Rust)                  │
├─────────────────────────────────────────────┤
│  RocksDB (storage)                          │
│  └── Key-value entities                     │
├─────────────────────────────────────────────┤
│  DataFusion (query engine)                  │
│  └── RocksDBTableProvider (custom)         │
│      ├── scan() → reads from RocksDB        │
│      ├── filter pushdown                    │
│      └── Arrow RecordBatch output           │
└─────────────────────────────────────────────┘
```

### Implementation in Rust

#### Step 1: Create RocksDBTableProvider
```rust
use datafusion::datasource::TableProvider;
use datafusion::arrow::datatypes::SchemaRef;
use datafusion::physical_plan::ExecutionPlan;
use rocksdb::DB;

pub struct RocksDBTableProvider {
    db: Arc<DB>,
    table_name: String,
    schema: SchemaRef,
    tenant_id: String,
}

#[async_trait]
impl TableProvider for RocksDBTableProvider {
    fn as_any(&self) -> &dyn Any {
        self
    }

    fn schema(&self) -> SchemaRef {
        self.schema.clone()
    }

    async fn scan(
        &self,
        ctx: &SessionState,
        projection: Option<&Vec<usize>>,
        filters: &[Expr],
        limit: Option<usize>,
    ) -> Result<Arc<dyn ExecutionPlan>> {
        // Create execution plan that reads from RocksDB
        Ok(Arc::new(RocksDBExec::new(
            self.db.clone(),
            self.table_name.clone(),
            self.schema.clone(),
            projection.cloned(),
            filters.to_vec(),
            limit,
        )))
    }
}
```

#### Step 2: Implement RocksDBExec (execution plan)
```rust
use datafusion::physical_plan::{ExecutionPlan, RecordBatchStream};
use datafusion::arrow::record_batch::RecordBatch;
use rocksdb::DB;

pub struct RocksDBExec {
    db: Arc<DB>,
    table_name: String,
    schema: SchemaRef,
    projection: Option<Vec<usize>>,
    filters: Vec<Expr>,
    limit: Option<usize>,
}

impl ExecutionPlan for RocksDBExec {
    fn as_any(&self) -> &dyn Any {
        self
    }

    fn schema(&self) -> SchemaRef {
        self.schema.clone()
    }

    fn execute(
        &self,
        partition: usize,
        context: Arc<TaskContext>,
    ) -> Result<SendableRecordBatchStream> {
        // Create stream that scans RocksDB
        Ok(Box::pin(RocksDBStream::new(
            self.db.clone(),
            self.table_name.clone(),
            self.schema.clone(),
            self.filters.clone(),
            self.limit,
        )))
    }
}
```

#### Step 3: Implement RocksDBStream (scans RocksDB)
```rust
pub struct RocksDBStream {
    db: Arc<DB>,
    table_name: String,
    schema: SchemaRef,
    filters: Vec<Expr>,
    limit: Option<usize>,
    current_batch: Vec<Entity>,
    done: bool,
}

impl RecordBatchStream for RocksDBStream {
    fn schema(&self) -> SchemaRef {
        self.schema.clone()
    }
}

impl Stream for RocksDBStream {
    type Item = Result<RecordBatch>;

    fn poll_next(
        mut self: Pin<&mut Self>,
        _cx: &mut Context<'_>,
    ) -> Poll<Option<Self::Item>> {
        if self.done {
            return Poll::Ready(None);
        }

        // Scan RocksDB with prefix
        let prefix = format!("entity:{}:", self.table_name);
        let iter = self.db.prefix_iterator(prefix.as_bytes());

        let mut entities = Vec::new();
        for (key, value) in iter {
            // Deserialize entity
            let entity: Entity = serde_json::from_slice(&value)?;

            // Apply filters (predicate pushdown)
            if self.matches_filters(&entity) {
                entities.push(entity);
            }

            // Check limit
            if let Some(limit) = self.limit {
                if entities.len() >= limit {
                    break;
                }
            }
        }

        // Convert entities to Arrow RecordBatch
        let batch = self.entities_to_record_batch(entities)?;

        self.done = true;
        Poll::Ready(Some(Ok(batch)))
    }
}

impl RocksDBStream {
    fn matches_filters(&self, entity: &Entity) -> bool {
        // Evaluate filter expressions against entity
        // This is where predicate pushdown happens
        for filter in &self.filters {
            if !self.evaluate_filter(filter, entity) {
                return false;
            }
        }
        true
    }

    fn entities_to_record_batch(&self, entities: Vec<Entity>) -> Result<RecordBatch> {
        // Convert Vec<Entity> to Arrow RecordBatch
        // This uses Arrow builders to construct columnar data
        use arrow::array::{StringArray, Int64Array};

        let mut id_builder = StringBuilder::new();
        let mut name_builder = StringBuilder::new();
        let mut category_builder = StringBuilder::new();

        for entity in entities {
            id_builder.append_value(entity.id.to_string());
            name_builder.append_value(entity.name);
            category_builder.append_value(
                entity.properties.get("category").unwrap_or("")
            );
        }

        RecordBatch::try_new(
            self.schema.clone(),
            vec![
                Arc::new(id_builder.finish()),
                Arc::new(name_builder.finish()),
                Arc::new(category_builder.finish()),
            ],
        )
    }
}
```

#### Step 4: Register with DataFusion and query
```rust
use datafusion::prelude::*;

pub struct REMDatabase {
    rocksdb: Arc<DB>,
    datafusion_ctx: SessionContext,
}

impl REMDatabase {
    pub fn new(path: &str, tenant_id: &str) -> Result<Self> {
        let rocksdb = Arc::new(DB::open_default(path)?);
        let datafusion_ctx = SessionContext::new();

        // Register tables
        let resources_provider = RocksDBTableProvider::new(
            rocksdb.clone(),
            "resources".to_string(),
            tenant_id.to_string(),
        )?;

        datafusion_ctx.register_table("resources", Arc::new(resources_provider))?;

        Ok(Self {
            rocksdb,
            datafusion_ctx,
        })
    }

    pub async fn sql(&self, query: &str) -> Result<Vec<RecordBatch>> {
        // Execute SQL via DataFusion
        let df = self.datafusion_ctx.sql(query).await?;
        let batches = df.collect().await?;
        Ok(batches)
    }
}

// Usage
let db = REMDatabase::new("./data", "tenant-123")?;

// Complex aggregation
let result = db.sql(r#"
    SELECT category, COUNT(*) as count, AVG(priority) as avg_priority
    FROM resources
    WHERE status = 'active'
    GROUP BY category
    HAVING COUNT(*) > 5
    ORDER BY count DESC
"#).await?;

// Multi-table join
let result = db.sql(r#"
    SELECT u.name, COUNT(i.id) as issue_count
    FROM users u
    LEFT JOIN issues i ON u.id = i.created_by
    GROUP BY u.name
"#).await?;
```

### Filter pushdown optimization
```rust
impl RocksDBStream {
    fn matches_filters(&self, entity: &Entity) -> bool {
        // Predicate pushdown - filters applied during scan
        // More efficient than filtering after loading all entities

        for filter in &self.filters {
            match filter {
                Expr::BinaryExpr(BinaryExpr { left, op, right }) => {
                    // Example: status = 'active'
                    let field = extract_field(left)?;
                    let value = extract_value(right)?;

                    let entity_value = entity.properties.get(field);

                    match op {
                        Operator::Eq => {
                            if entity_value != Some(&value) {
                                return false;
                            }
                        }
                        Operator::Gt => {
                            // ... implement comparison
                        }
                        // ... other operators
                    }
                }
                _ => {}
            }
        }

        true
    }
}
```

### Pros/cons of DataFusion approach

**Pros**:
- **Rust-native**: No Python/Rust boundary overhead
- **Single storage**: Only RocksDB, no dual storage
- **No sync overhead**: Direct reads from RocksDB
- **Vectorized execution**: DataFusion uses SIMD
- **Multi-threaded**: Parallel query execution
- **Filter pushdown**: Efficient predicate evaluation during scan
- **Arrow ecosystem**: Interop with Parquet, Arrow Flight
- **No stale indexes**: Always queries live data

**Cons**:
- **No existing RocksDB provider**: Must implement from scratch
- **Complex implementation**: TableProvider + ExecutionPlan + Stream
- **Full table scans**: Without secondary indexes, must scan all entities
- **No persistent indexes**: Can't build indexes like DuckDB
- **Rust learning curve**: Team needs Rust expertise

**When to use**:
- Migrating to Rust anyway
- Want single storage system
- Need real-time queries (no sync lag)
- Team has Rust expertise
- Performance critical (vectorized execution)

---

## Hybrid approach (recommended)

### Strategy: Start with DuckDB, migrate to DataFusion

**Phase 1: Python + DuckDB indexes** (current)
- Quick to implement (SQLGlot + DuckDB)
- Validates query patterns
- Proves architecture

**Phase 2: Rust migration + dual storage** (3-6 months)
- Port RocksDB layer to Rust
- Keep DuckDB for complex analytics
- Use Rust for entity operations

**Phase 3: DataFusion integration** (6-12 months)
- Implement RocksDBTableProvider in Rust
- Gradually migrate queries from DuckDB to DataFusion
- Keep DuckDB for edge cases (window functions, etc.)

**Phase 4: Full Rust stack** (12+ months)
- Pure DataFusion for all queries
- Remove DuckDB dependency
- Optimize with persistent indexes

---

## Recommendation

### For REM Database

**Short term (next 3 months)**:
Use **DuckDB indexes alongside RocksDB**:
- Fast to implement (Python)
- Proven for aggregations and joins
- Works well with existing Python stack
- Allows quick iteration

**Medium term (3-12 months)**:
**Rust migration** with DataFusion:
- Port core to Rust (RocksDB + entities)
- Implement RocksDBTableProvider
- Keep DuckDB for complex analytics initially

**Long term (12+ months)**:
**Full DataFusion** integration:
- All queries via DataFusion
- Custom indexes in RocksDB (secondary indexes)
- Remove DuckDB dependency

### Storage strategy

**DuckDB indexes store**:
- Only indexed fields (category, status, priority, dates)
- ~20-30% of total data size
- Rebuilt periodically or incrementally updated

**RocksDB stores**:
- Full entities (all fields)
- Content (large text)
- Embeddings (vectors → HNSW)
- Graph edges

**Query routing**:
```python
if has_aggregation or has_join:
    # Use DuckDB indexes
    ids = duckdb.sql(query).fetchall()
    return [get_entity_from_rocksdb(id) for id in ids]
elif is_vector_search:
    # Use HNSW + RocksDB
    return vector_search(query)
else:
    # Simple filter, scan RocksDB directly
    return rocksdb_scan(query)
```

This gives you:
- Fast analytics via DuckDB
- Fast vector search via HNSW
- Fast entity lookups via RocksDB
- Clear migration path to Rust + DataFusion
