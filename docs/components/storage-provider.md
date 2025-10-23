# Storage Provider Abstraction

## Overview

Percolate uses a **pluggable storage provider** architecture to support different database backends while maintaining a consistent interface for REM operations.

**Default:** RocksDB (embedded, single-tenant)
**Enterprise:** PostgreSQL (shared database, multi-tenant with isolation)

## Design Philosophy

### Provider Interface

All storage operations go through a provider interface, making the database backend transparent to higher-level code.

**Benefits:**
- **Flexibility**: Choose backend based on deployment model
- **Testing**: Easy to swap providers for tests
- **Future-proofing**: Add new backends (TiDB, FoundationDB, etc.)
- **Consistency**: Same API regardless of backend

## Storage Providers

### RocksDB Provider (Default)

**Use Cases:**
- Desktop deployment (local node)
- Mobile deployment (embedded)
- Cloud deployment (per-tenant isolation)
- Development and testing

**Characteristics:**
- Embedded (no separate database process)
- High performance (LSM tree)
- Per-tenant database files
- Encrypted at rest
- No network overhead

**Storage:**
```
/var/lib/percolate/{tenant_id}/
  └── rocksdb/
      ├── resources/
      ├── entities/
      ├── moments/
      └── metadata/
```

### PostgreSQL Provider (Enterprise)

**Use Cases:**
- Enterprise deployment (shared infrastructure)
- Multi-tenant with centralized management
- Advanced querying requirements
- Integration with existing PostgreSQL infrastructure

**Characteristics:**
- Client-server architecture
- Robust transaction support
- Advanced indexing (GIN, GIST, pgvector)
- Replication and backup tools
- Row-level security for tenant isolation

**Storage:**
```sql
-- Tenant isolation via schemas
CREATE SCHEMA tenant_alice;
CREATE SCHEMA tenant_bob;

-- Tables per tenant
CREATE TABLE tenant_alice.resources (...);
CREATE TABLE tenant_alice.entities (...);
CREATE TABLE tenant_alice.moments (...);
```

## Provider Interface (Rust)

### Trait Definition

```rust
// percolate-core/src/memory/provider.rs
use async_trait::async_trait;

#[async_trait]
pub trait StorageProvider: Send + Sync {
    /// Initialize provider for tenant
    async fn initialize(&mut self, tenant_id: &str) -> Result<()>;

    /// Resource operations
    async fn create_resource(&self, resource: Resource) -> Result<ResourceId>;
    async fn get_resource(&self, id: &ResourceId) -> Result<Resource>;
    async fn update_resource(&self, id: &ResourceId, resource: Resource) -> Result<()>;
    async fn delete_resource(&self, id: &ResourceId) -> Result<()>;
    async fn search_resources(&self, query: &SearchQuery) -> Result<Vec<ScoredResource>>;

    /// Entity operations
    async fn create_entity(&self, entity: Entity) -> Result<EntityId>;
    async fn get_entity(&self, id: &EntityId) -> Result<Entity>;
    async fn update_entity(&self, id: &EntityId, entity: Entity) -> Result<()>;
    async fn delete_entity(&self, id: &EntityId) -> Result<()>;
    async fn search_entities(&self, query: &str, filter: Option<EntityFilter>) -> Result<Vec<Entity>>;

    /// Graph operations
    async fn create_edge(&self, edge: Edge) -> Result<EdgeId>;
    async fn get_edges(&self, entity_id: &EntityId, direction: Direction) -> Result<Vec<Edge>>;
    async fn delete_edge(&self, id: &EdgeId) -> Result<()>;

    /// Moment operations
    async fn create_moment(&self, moment: Moment) -> Result<MomentId>;
    async fn get_moment(&self, id: &MomentId) -> Result<Moment>;
    async fn get_moments_by_time(&self, range: TimeRange) -> Result<Vec<Moment>>;

    /// Batch operations
    async fn batch_create_resources(&self, resources: Vec<Resource>) -> Result<Vec<ResourceId>>;

    /// Transaction support (optional)
    async fn begin_transaction(&self) -> Result<Box<dyn Transaction>>;
}
```

### RocksDB Implementation

```rust
// percolate-core/src/memory/providers/rocksdb.rs
pub struct RocksDBProvider {
    db: Arc<DB>,
    tenant_id: String,
}

impl RocksDBProvider {
    pub fn new(db_path: &Path, tenant_id: String) -> Result<Self> {
        let mut opts = Options::default();
        opts.create_if_missing(true);
        opts.create_missing_column_families(true);

        let db = DB::open_cf(
            &opts,
            db_path,
            &["resources", "entities", "edges", "moments", "embeddings"]
        )?;

        Ok(Self {
            db: Arc::new(db),
            tenant_id,
        })
    }
}

#[async_trait]
impl StorageProvider for RocksDBProvider {
    async fn initialize(&mut self, tenant_id: &str) -> Result<()> {
        self.tenant_id = tenant_id.to_string();
        Ok(())
    }

    async fn create_resource(&self, resource: Resource) -> Result<ResourceId> {
        let id = ResourceId::new();
        let key = format!("resource:{}:{}", self.tenant_id, id);
        let value = serde_json::to_vec(&resource)?;

        let db = self.db.clone();
        tokio::task::spawn_blocking(move || {
            db.put(&key, value)
        }).await??;

        Ok(id)
    }

    // ... other methods
}
```

### PostgreSQL Implementation

```rust
// percolate-core/src/memory/providers/postgres.rs
use sqlx::{PgPool, Row};

pub struct PostgresProvider {
    pool: PgPool,
    tenant_id: String,
}

impl PostgresProvider {
    pub async fn new(database_url: &str, tenant_id: String) -> Result<Self> {
        let pool = PgPool::connect(database_url).await?;

        Ok(Self {
            pool,
            tenant_id,
        })
    }

    fn schema_name(&self) -> String {
        format!("tenant_{}", self.tenant_id.replace("-", "_"))
    }
}

#[async_trait]
impl StorageProvider for PostgresProvider {
    async fn initialize(&mut self, tenant_id: &str) -> Result<()> {
        self.tenant_id = tenant_id.to_string();

        // Create schema if not exists
        let schema = self.schema_name();
        sqlx::query(&format!("CREATE SCHEMA IF NOT EXISTS {}", schema))
            .execute(&self.pool)
            .await?;

        // Create tables in tenant schema
        self.create_tables().await?;

        Ok(())
    }

    async fn create_resource(&self, resource: Resource) -> Result<ResourceId> {
        let id = ResourceId::new();
        let schema = self.schema_name();

        sqlx::query(&format!(
            "INSERT INTO {}.resources (id, content, metadata, created_at) VALUES ($1, $2, $3, NOW())",
            schema
        ))
        .bind(&id.to_string())
        .bind(&resource.content)
        .bind(serde_json::to_value(&resource.metadata)?)
        .execute(&self.pool)
        .await?;

        Ok(id)
    }

    // ... other methods
}
```

## Provider Factory

### Configuration-Based Provider Selection

```rust
// percolate-core/src/memory/mod.rs
pub enum ProviderType {
    RocksDB,
    PostgreSQL,
}

pub struct ProviderConfig {
    pub provider_type: ProviderType,
    pub connection_string: String,
    pub tenant_id: String,
}

pub async fn create_provider(config: ProviderConfig) -> Result<Box<dyn StorageProvider>> {
    match config.provider_type {
        ProviderType::RocksDB => {
            let provider = RocksDBProvider::new(
                Path::new(&config.connection_string),
                config.tenant_id
            )?;
            Ok(Box::new(provider))
        }
        ProviderType::PostgreSQL => {
            let provider = PostgresProvider::new(
                &config.connection_string,
                config.tenant_id
            ).await?;
            Ok(Box::new(provider))
        }
    }
}
```

### Python Bindings

```python
from percolate_core import MemoryEngine, ProviderType

# RocksDB (default)
memory = MemoryEngine(
    provider="rocksdb",
    connection_string="./data/percolate.db",
    tenant_id="tenant-123"
)

# PostgreSQL (enterprise)
memory = MemoryEngine(
    provider="postgres",
    connection_string="postgresql://user:pass@localhost/percolate",
    tenant_id="tenant-123"
)
```

## Configuration (Pydantic Settings)

```python
# percolate/src/percolate/settings.py
class Settings(BaseSettings):
    # Storage provider
    storage_provider: str = Field(
        default="rocksdb",
        description="Storage provider (rocksdb, postgres)"
    )

    # RocksDB settings
    rocksdb_path: str = Field(
        default="./data/percolate.db",
        description="RocksDB database path"
    )

    # PostgreSQL settings
    postgres_url: str | None = Field(
        default=None,
        description="PostgreSQL connection URL"
    )
    postgres_pool_size: int = Field(
        default=10,
        description="PostgreSQL connection pool size"
    )
```

## Tenant Isolation by Provider

### RocksDB: File-Level Isolation

```
/var/lib/percolate/
├── tenant-alice/
│   └── rocksdb/
├── tenant-bob/
│   └── rocksdb/
└── tenant-carol/
    └── rocksdb/
```

**Isolation:** Complete separation via filesystem
**Encryption:** Per-directory encryption
**Performance:** No cross-tenant overhead

### PostgreSQL: Schema-Level Isolation

```sql
-- Row-Level Security (RLS)
CREATE TABLE tenant_alice.resources (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    content TEXT,
    created_at TIMESTAMPTZ
);

ALTER TABLE tenant_alice.resources ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON tenant_alice.resources
    USING (tenant_id = current_setting('app.current_tenant'));

-- Set tenant context per connection
SET app.current_tenant = 'tenant-alice';
```

**Isolation:** Schema + RLS policies
**Encryption:** PostgreSQL native encryption
**Performance:** Shared connection pool, efficient for many tenants

## Migration Between Providers

### Export from RocksDB

```python
async def export_tenant(tenant_id: str, output_path: Path):
    """Export tenant data to portable format."""
    rocksdb_memory = MemoryEngine(provider="rocksdb", tenant_id=tenant_id)

    # Export resources
    resources = await rocksdb_memory.export_all_resources()

    # Export entities
    entities = await rocksdb_memory.export_all_entities()

    # Export moments
    moments = await rocksdb_memory.export_all_moments()

    # Save as JSON
    with open(output_path, "w") as f:
        json.dump({
            "resources": resources,
            "entities": entities,
            "moments": moments
        }, f)
```

### Import to PostgreSQL

```python
async def import_tenant(tenant_id: str, import_path: Path):
    """Import tenant data from portable format."""
    postgres_memory = MemoryEngine(
        provider="postgres",
        connection_string="postgresql://...",
        tenant_id=tenant_id
    )

    # Initialize schema
    await postgres_memory.initialize()

    # Load data
    with open(import_path, "r") as f:
        data = json.load(f)

    # Import resources
    for resource in data["resources"]:
        await postgres_memory.create_resource(resource)

    # Import entities
    for entity in data["entities"]:
        await postgres_memory.create_entity(entity)

    # Import moments
    for moment in data["moments"]:
        await postgres_memory.create_moment(moment)
```

## Performance Comparison

| Operation | RocksDB | PostgreSQL |
|-----------|---------|------------|
| **Read (single)** | <1ms | 1-2ms |
| **Write (single)** | 1-2ms | 2-3ms |
| **Batch write (1000)** | 10ms | 50ms |
| **Vector search (k=10)** | 5ms | 10-15ms |
| **Graph traversal (depth=3)** | 10ms | 20-30ms |

**RocksDB Advantages:**
- Lower latency
- No network overhead
- Better for single-tenant deployments

**PostgreSQL Advantages:**
- Better for multi-tenant
- Advanced querying (SQL)
- Mature replication and backup
- Better for analytics queries

## Deployment Patterns

### Pattern 1: Pure RocksDB

```
Desktop/Mobile: RocksDB (embedded)
Cloud: RocksDB (per-tenant pods)
```

**Use Case:** Maximum isolation, simple deployment

### Pattern 2: Hybrid

```
Desktop/Mobile: RocksDB (embedded)
Cloud: PostgreSQL (shared database)
```

**Use Case:** Cost optimization, centralized management

### Pattern 3: Pure PostgreSQL

```
All deployments: PostgreSQL (with pgvector)
```

**Use Case:** Enterprise with existing PostgreSQL infrastructure

## Future Providers

The provider interface supports future backends:

- **TiDB**: Distributed SQL with horizontal scalability
- **FoundationDB**: Ordered key-value with ACID transactions
- **Cassandra**: Wide-column store for massive scale
- **Custom**: Any backend implementing the provider trait

## References

- RocksDB: https://rocksdb.org
- PostgreSQL pgvector: https://github.com/pgvector/pgvector
- Row-Level Security: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- SQLx (Rust): https://github.com/launchbadge/sqlx
