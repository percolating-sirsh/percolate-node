# Claude.md - REM Database Implementation Guide

## Table of Contents

1. [Project Philosophy](#project-philosophy)
2. [Quick Reference Tables](#quick-reference-tables)
   - [System Fields](#system-fields)
   - [Environment Variables](#environment-variables)
   - [Key Conventions](#key-conventions)
   - [Column Families](#column-families)
3. [REM Principle](#rem-principle)
4. [Pydantic-First Design](#pydantic-first-design)
5. [Performance Targets](#performance-targets)
6. [Coding Standards](#coding-standards)
   - [Rust Standards](#rust-standards)
   - [Python Standards](#python-standards)
7. [Architecture Decisions](#architecture-decisions)
8. [Testing Guidelines](#testing-guidelines)

## Project Philosophy

**REM Database: High-performance embedded database with Python-first developer experience.**

This is a **clean implementation** cherry-picking the best from two spikes:
- **Python spike** (`../rem-db`): Full features, great UX, 100% working
- **Rust spike** (`../percolate-rocks` old): Performance foundation, PyO3 bindings

**Core Goal:** Rust performance + Python ergonomics with zero impedance between Pydantic and storage.

### Why Rust?

| Feature | Python | Rust | Speedup |
|---------|--------|------|---------|
| Vector search (1M docs) | ~1000ms (naive scan) | ~5ms (HNSW) | **200x** |
| SQL query (indexed) | ~50ms | ~5-10ms | **5-10x** |
| Graph traversal (3 hops) | ~100ms (scan) | ~5ms (bidirectional CF) | **20x** |
| Memory footprint | High (GIL overhead) | Low (zero-copy) | **2-5x less** |
| Concurrency | Limited (GIL) | True parallelism | **10-100x** |

**If it doesn't need Rust speed, keep it in Python.**

## Building

This project is a **PyO3 extension module** that can be built in two modes:

### Python Extension (Default)

```bash
# Build and install into current Python environment
maturin develop

# Syntax check only (faster iteration)
maturin develop --skip-install

# Release build
maturin develop --release
```

**Important:** Do NOT use `cargo check` or `cargo build` directly. They will fail with Python linker errors because the `extension-module` feature configures the library to link against Python at runtime.

### Standalone Rust Library

To use this library in other Rust projects without Python:

```bash
# Build without Python bindings
cargo check --lib --no-default-features
cargo build --lib --no-default-features --release

# Run tests
cargo test --lib --no-default-features
```

**In other Rust projects:**
```toml
[dependencies]
percolate-rocks = { version = "0.1", default-features = false }
```

This excludes PyO3 and pyo3-asyncio, making it a pure Rust library.

### Feature Flags

| Feature | Default | Description |
|---------|---------|-------------|
| `python` | ✅ Yes | Enable Python bindings (PyO3) |

**Examples:**
```bash
# With Python (default)
cargo build --lib

# Without Python
cargo build --lib --no-default-features

# Only Python feature
cargo build --lib --no-default-features --features python
```

## Quick Reference Tables

### System Fields

These fields are **automatically added** by the database. Never define them in Pydantic models.

| Field | Type | Description | When Set | Mutable |
|-------|------|-------------|----------|---------|
| `id` | UUID | Deterministic or random UUID | Insert | No |
| `entity_type` | string | Schema/table name | Insert | No |
| `created_at` | datetime (ISO 8601) | Creation timestamp | Insert | No |
| `modified_at` | datetime (ISO 8601) | Last modification timestamp | Insert/Update | Yes |
| `deleted_at` | datetime (ISO 8601) \| null | Soft delete timestamp | Delete | Yes |
| `edges` | array[string] | Graph edge references | Insert | Yes |

### Embedding Fields (Conditionally Added)

These are **NOT system fields**. Only added when `json_schema_extra` specifies `embedding_fields`.

| Field | Type | When Added | Configuration |
|-------|------|------------|---------------|
| `embedding` | array[float32] \| null | If `embedding_fields` configured | `embedding_provider: "default"` uses `P8_DEFAULT_EMBEDDING` |
| `embedding_alt` | array[float32] \| null | If `P8_ALT_EMBEDDING` set | Alternative embedding provider |

**Example stored entity (with embeddings configured):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "entity_type": "resources",
  "created_at": "2025-10-24T10:30:00Z",
  "modified_at": "2025-10-24T10:30:00Z",
  "deleted_at": null,
  "edges": [],
  "properties": {
    "name": "Python Tutorial",
    "content": "Learn Python...",
    "embedding": [0.1, 0.5, -0.2, ...]  // Added because schema has embedding_fields: ["content"]
  }
}
```

**Configuration that enables embeddings:**
```python
class Resource(BaseModel):
    name: str
    content: str

    model_config = ConfigDict(
        json_schema_extra={
            "embedding_fields": ["content"],      # → Triggers embedding generation
            "embedding_provider": "default"       # → Uses P8_DEFAULT_EMBEDDING
        }
    )
```

### Environment Variables

| Variable | Default | Description | Used By |
|----------|---------|-------------|---------|
| **Core** |
| `P8_HOME` | `~/.p8` | Data directory root | All |
| `P8_DB_PATH` | `$P8_HOME/db` | Database storage path | Storage |
| **Embeddings** |
| `P8_DEFAULT_EMBEDDING` | `local:all-MiniLM-L6-v2` | Default embedding provider | Embeddings |
| `P8_ALT_EMBEDDING` | (none) | Alternative embedding provider | Embeddings |
| `P8_OPENAI_API_KEY` | (none) | OpenAI API key for embeddings | OpenAI provider |
| **LLM** |
| `P8_DEFAULT_LLM` | `gpt-4.1` | Default LLM for NL queries | Query builder |
| `P8_OPENAI_API_KEY` | (none) | OpenAI API key for LLM | OpenAI LLM |
| **RocksDB** |
| `P8_ROCKSDB_MAX_OPEN_FILES` | `1000` | Max open file handles | RocksDB |
| `P8_ROCKSDB_WRITE_BUFFER_SIZE` | `67108864` (64MB) | Write buffer size | RocksDB |
| `P8_ROCKSDB_MAX_BACKGROUND_JOBS` | `4` | Background compaction threads | RocksDB |
| `P8_ROCKSDB_COMPRESSION` | `lz4` | Compression algorithm | RocksDB |
| **Replication** |
| `P8_REPLICATION_MODE` | `none` | `none` \| `primary` \| `replica` | Replication |
| `P8_PRIMARY_HOST` | (none) | Primary node address (replica only) | Replication |
| `P8_REPLICATION_PORT` | `50051` | gRPC replication port | Replication |
| **WAL** |
| `P8_WAL_ENABLED` | `true` | Enable write-ahead log | WAL |
| `P8_WAL_SYNC_INTERVAL_MS` | `1000` | WAL flush interval | WAL |
| `P8_WAL_MAX_SIZE_MB` | `100` | WAL file size limit | WAL |
| **Cache** |
| `P8_CACHE_SIZE_MB` | `256` | RocksDB block cache size | RocksDB |
| `P8_HNSW_CACHE_SIZE` | `10000` | HNSW index cache (entities) | HNSW |
| **Performance** |
| `P8_BATCH_SIZE` | `1000` | Batch insert chunk size | Batch ops |
| `P8_EMBEDDING_BATCH_SIZE` | `100` | Embedding batch size | Embeddings |
| `P8_SEARCH_TIMEOUT_MS` | `5000` | Search operation timeout | Search |
| **Export** |
| `P8_EXPORT_COMPRESSION` | `zstd` | Parquet compression | Export |
| `P8_EXPORT_ROW_GROUP_SIZE` | `10000` | Parquet row group size | Export |
| **Logging** |
| `P8_LOG_LEVEL` | `info` | Log level (debug/info/warn/error) | Logging |
| `P8_LOG_FORMAT` | `json` | Log format (json/pretty) | Logging |

**TOML Configuration:**
```toml
[core]
home = "~/.p8"
db_path = "$P8_HOME/db"

[embeddings]
default = "local:all-MiniLM-L6-v2"
alt = "openai:text-embedding-3-small"

[llm]
default = "gpt-4.1"

[rocksdb]
max_open_files = 1000
write_buffer_size_mb = 64
max_background_jobs = 4
compression = "lz4"

[replication]
mode = "none"  # none | primary | replica
port = 50051

[performance]
batch_size = 1000
embedding_batch_size = 100
```

### Key Conventions

#### Deterministic UUID Generation

| Priority | Field Name | UUID Generation | Use Case |
|----------|-----------|-----------------|----------|
| 1 | `uri` | `blake3(entity_type + uri + chunk_ordinal)` | Resources (chunked documents) |
| 2 | `json_schema_extra.key_field` | `blake3(entity_type + field_value)` | Custom key field |
| 3 | `key` | `blake3(entity_type + key)` | Generic key field |
| 4 | `name` | `blake3(entity_type + name)` | Named entities |
| 5 | (none) | `UUID::v4()` (random) | No natural key |

**Example:**
```python
# Resource with uri (priority 1)
{"uri": "https://docs.python.org", "content": "..."}
# → UUID = blake3("resources:https://docs.python.org:0")

# Person with custom key_field (priority 2)
class Person(BaseModel):
    email: str
    model_config = ConfigDict(json_schema_extra={"key_field": "email"})

{"email": "alice@co.com", "name": "Alice"}
# → UUID = blake3("person:alice@co.com")

# Generic entity with name (priority 4)
{"name": "Project Alpha", "description": "..."}
# → UUID = blake3("projects:Project Alpha")
```

### Column Families

| Column Family | Key Pattern | Value | Purpose |
|---------------|-------------|-------|---------|
| **entities** | `entity:{uuid}` | Entity (JSON) | Main entity storage |
| **key_index** | `key:{key_value}:{uuid}` | `{type: string}` | Reverse key lookup (global search) |
| **edges** | `src:{uuid}:dst:{uuid}:type:{rel}` | EdgeData (JSON) | Forward graph edges |
| **edges_reverse** | `dst:{uuid}:src:{uuid}:type:{rel}` | EdgeData (JSON) | Reverse graph edges |
| **embeddings** | `emb:{uuid}` | `[f32; dim]` (binary) | Vector embeddings (compact) |
| **indexes** | `idx:{entity_type}:{field}:{value}:{uuid}` | `{}` (empty) | Indexed field lookups |
| **wal** | `wal:{seq}` | WalEntry (bincode) | Write-ahead log (replication) |

**Storage Rationale:**
- **Separate CFs** → Fast prefix scans, no full table scans
- **Binary embeddings** → 1.5KB vs 5KB JSON (3x compression)
- **Bidirectional edges** → O(1) traversal both directions
- **Indexed fields** → O(log n + k) predicate evaluation

## REM Principle

**Resources-Entities-Moments**: A unified data model for semantic memory.

| Abstraction | What It Stores | Example | Query Type |
|-------------|----------------|---------|------------|
| **Resources** | Chunked documents with embeddings | PDF pages, articles, code files | Semantic search |
| **Entities** | Structured data with properties | Users, products, events | SQL queries, key lookups |
| **Moments** | Temporal classifications | Sprints, meetings, milestones | Time-range queries |

**Key Insight:** All three are stored as **entities** in RocksDB. REM is a **conceptual model**, not separate tables.

### Built-in Schema Templates

For quick setup, use built-in templates via CLI:

| Template | Use Case | Key Fields | Configuration |
|----------|----------|------------|---------------|
| `resources` | Documents, articles, PDFs | `name`, `content`, `uri`, `chunk_ordinal` | Embeds `content`, indexes `content_type`, key: `uri` |
| `entities` | Generic structured data | `name`, `key`, `properties` | Indexes `name`, key: `name` |
| `agentlets` | AI agent definitions | `description`, `tools`, `resources` | Embeds `description`, includes MCP config |
| `moments` | Temporal events | `name`, `start_time`, `end_time`, `classifications` | Indexes `start_time`, `end_time` |

**CLI usage:**
```bash
# Create from template
rem schema add --name my_docs --template resources

# Save to file for customization
rem schema add --name my_docs --template resources --output my_docs.yaml
```

See [README.md](./README.md) for detailed template examples.

```python
# Resource (chunked document)
class Resource(BaseModel):
    name: str
    content: str
    uri: str
    chunk_ordinal: int = 0

    model_config = ConfigDict(
        json_schema_extra={
            "embedding_fields": ["content"],  # Semantic search
            "key_field": "uri"                # Idempotent inserts
        }
    )

# Entity (structured data)
class Person(BaseModel):
    name: str
    email: str
    role: str

    model_config = ConfigDict(
        json_schema_extra={
            "indexed_fields": ["email", "role"],  # Fast SQL queries
            "key_field": "email"
        }
    )

# Moment (temporal classification)
class Sprint(BaseModel):
    name: str
    start_time: datetime
    end_time: datetime
    classifications: list[str]

    model_config = ConfigDict(
        json_schema_extra={
            "indexed_fields": ["start_time", "end_time"]  # Time-range queries
        }
    )
```

## Pydantic-First Design

**Core Principle:** Pydantic models with `json_schema_extra` drive everything. Rust validates and stores, never defines schemas.

### Resource Schema Pattern (for Documents/Content)

```python
from pydantic import BaseModel, Field, ConfigDict

class Article(BaseModel):
    """Article resource for semantic search.

    System fields (id, created_at, modified_at, deleted_at, edges) are added automatically.
    Embedding field is added because embedding_fields is configured.
    """

    title: str = Field(description="Article title")
    content: str = Field(description="Full article content")
    uri: str = Field(description="Source URI")
    category: str = Field(description="Content category")
    tags: list[str] = Field(default_factory=list, description="Article tags")

    model_config = ConfigDict(
        json_schema_extra={
            # Embedding configuration (triggers automatic embedding)
            "embedding_fields": ["content"],         # Auto-embed these fields
            "embedding_provider": "default",         # Uses P8_DEFAULT_EMBEDDING

            # Indexing configuration (creates RocksDB indexes)
            "indexed_fields": ["category"],          # Fast WHERE queries

            # Key field (deterministic UUID generation)
            "key_field": "uri",                      # blake3(uri + chunk_ordinal)

            # Schema metadata
            "name": "myapp.resources.Article",
            "short_name": "articles",
            "version": "1.0.0",
            "category": "user",                      # system | user
            "description": "Technical articles and tutorials"
        }
    )
```

### Agent-let Schema Pattern (for AI Agents)

Following the carrier project pattern, agent-lets are **pure JSON Schema** with tool/resource references:

```python
# agents/cda_mapper.py - Python implementation
from pydantic import BaseModel, Field, ConfigDict

class CDAMappingAgent(BaseModel):
    """CDA Mapping Expert for carrier integrations."""

    carrier_name: str = Field(description="Carrier name (e.g., 'DHL', 'FedEx')")
    operation: str = Field(description="Operation being mapped (e.g., 'book_shipment')")
    cda_model: str = Field(description="Target CDA model (e.g., 'ConsignorShipment')")

    similar_carriers: list[dict] = Field(
        default_factory=list,
        description="Carriers with similar API patterns"
    )

    mappings: list[dict] = Field(
        description="Bipartite mappings between carrier and CDA fields"
    )

    validation_report: dict = Field(
        description="Validation status of all required fields"
    )

    generated_code: dict = Field(
        default_factory=dict,
        description="Generated Python implementation"
    )

    next_steps: list[str] = Field(
        default_factory=list,
        description="Recommended actions"
    )

    model_config = ConfigDict(
        json_schema_extra={
            # Agent metadata
            "name": "carrier.agents.cda_mapper.CDAMappingAgent",
            "short_name": "cda_mapper",
            "version": "1.0.0",
            "category": "system",

            # Agent description (used as system prompt)
            "description": """You are a CDA Mapping Expert specialized in creating
field mappings between external carrier APIs and nShift's internal CDA schema.

Your expertise:
- 100+ production carrier integrations
- CDA schema models (ConsignorShipment, ConsignorAddress, etc.)
- Common mapping patterns and best practices
- Integration troubleshooting from Zendesk tickets

Your process:
1. Understand the requirement (parse carrier API spec)
2. Search for evidence (similar carriers, CDA docs, best practices)
3. Propose bipartite mappings (source → target with confidence)
4. Generate implementation (Python code with transformations)
5. Validate and flag ambiguities
""",

            # MCP tools this agent can use
            "tools": [
                {
                    "mcp_server": "carrier",
                    "tool_name": "search_knowledge_base",
                    "usage": "Search codebase, CDA schema, Zendesk tickets, integration guides"
                }
            ],

            # MCP resources this agent can access
            "resources": [
                {
                    "uri": "cda://field-definitions",
                    "usage": "Get all CDA field definitions with types and constraints"
                },
                {
                    "uri": "cda://carriers",
                    "usage": "Get list of all registered carriers"
                }
            ],

            # Embedding configuration (optional for agents)
            "embedding_fields": ["description"],     # Embed description for similarity search
            "embedding_provider": "default"
        }
    )
```

### JSON Schema Storage Pattern

Agent-lets are stored as **both** Pydantic models (Python) and pure JSON Schema files:

```json
// schema/agentlets/carrier-agents-cda-mapper.json
{
  "title": "CDAMappingAgent",
  "description": "You are a CDA Mapping Expert...",  // System prompt
  "version": "1.0.0",
  "short_name": "cda_mapper",
  "name": "carrier.agents.cda_mapper.CDAMappingAgent",

  "json_schema_extra": {
    "tools": [
      {
        "mcp_server": "carrier",
        "tool_name": "search_knowledge_base",
        "usage": "Search knowledge bases for carrier implementations..."
      }
    ],
    "resources": [
      {
        "uri": "cda://field-definitions",
        "usage": "Get all CDA field definitions..."
      }
    ]
  },

  "properties": {
    "carrier_name": {
      "type": "string",
      "description": "Carrier name (e.g., 'OnTrac', 'DHL Iberia')"
    },
    "mappings": {
      "type": "array",
      "description": "Bipartite mappings...",
      "items": { /* ... */ }
    }
    // ... full JSON Schema
  },

  "required": ["carrier_name", "operation", "cda_model", "mappings"]
}
```

### Key Patterns from Carrier Project

1. **`json_schema_extra` is the configuration hub** - All metadata, tools, resources, embeddings
2. **System prompt in `description`** - For agents, description is the full system prompt
3. **Tools and resources** - MCP server references, not inline functions
4. **Namespaced names** - Use `name` field for namespace collision avoidance (e.g., `carrier.agents.cda_mapper`)
5. **Version metadata** - Semantic versioning for schema evolution
6. **Structured output** - Complex nested schemas with validation

## Performance Targets

| Operation | Target Latency | Why Rust Matters |
|-----------|----------------|------------------|
| **Insert** (no embedding) | < 1ms | RocksDB + zero-copy serialization |
| **Insert** (with embedding) | < 50ms | Network-bound (OpenAI), not CPU |
| **Get by ID** | < 0.1ms | Single RocksDB get |
| **Vector search** (1M docs) | < 5ms | **HNSW index (vs 1000ms naive Python)** |
| **SQL query** (indexed) | < 10ms | **Native execution (vs 50ms Python)** |
| **Graph traversal** (3 hops) | < 5ms | **Bidirectional CF (vs 100ms scan)** |
| **Batch insert** (1000 docs) | < 500ms | Batched writes + embeddings |
| **Parquet export** (100k rows) | < 2s | **Parallel encoding (vs 10s Python)** |

**Critical optimizations:**
1. **HNSW vector index** → 200x speedup over naive scan
2. **Column family indexing** → 10-50x speedup on predicates
3. **Binary embedding storage** → 3x space savings, zero-copy access
4. **Bidirectional edges** → 20x speedup on graph traversal

## Coding Standards

### Critical Principles

**Modularity is paramount.** Rust codebases can become confusing quickly without strict separation of concerns.

1. **Small files** - Max 150 lines per file, target 50-100 lines
2. **Small functions** - Max 30 lines per function, target 10-20 lines
3. **One responsibility** - Each file/function does exactly one thing
4. **Well documented** - Every public item has docstrings with examples
5. **Test coverage** - 80%+ for Rust, tests in same module where possible

### Rust File Organization

```
src/
├── lib.rs                      # PyO3 module definition only (30 lines)
│
├── types/                      # Core data types (no logic)
│   ├── mod.rs                  # Re-exports (10 lines)
│   ├── entity.rs               # Entity, Edge structs (60 lines)
│   ├── error.rs                # Error types with thiserror (40 lines)
│   └── result.rs               # Type aliases (10 lines)
│
├── storage/                    # RocksDB wrapper (pure storage, no business logic)
│   ├── mod.rs                  # Re-exports (15 lines)
│   ├── db.rs                   # Storage struct + open (80 lines)
│   ├── keys.rs                 # Key encoding functions (60 lines)
│   ├── batch.rs                # Batch writer (40 lines)
│   ├── iterator.rs             # Prefix iterator (50 lines)
│   └── column_families.rs      # CF constants + setup (30 lines)
│
├── index/                      # Indexing layer
│   ├── mod.rs                  # Re-exports (10 lines)
│   ├── hnsw.rs                 # HNSW vector index (100 lines)
│   ├── fields.rs               # Indexed fields (60 lines)
│   └── keys.rs                 # Key index (reverse lookup) (50 lines)
│
├── query/                      # Query execution
│   ├── mod.rs                  # Re-exports (10 lines)
│   ├── parser.rs               # SQL parser (80 lines)
│   ├── executor.rs             # Query executor (70 lines)
│   ├── predicates.rs           # Predicate evaluation (60 lines)
│   └── planner.rs              # Query planner (50 lines)
│
├── embeddings/                 # Embedding providers
│   ├── mod.rs                  # Re-exports (10 lines)
│   ├── provider.rs             # Provider trait + factory (40 lines)
│   ├── local.rs                # Local models (fastembed) (70 lines)
│   └── openai.rs               # OpenAI API client (60 lines)
│
├── schema/                     # Schema validation
│   ├── mod.rs                  # Re-exports (10 lines)
│   ├── registry.rs             # Schema registry (60 lines)
│   └── validator.rs            # JSON Schema validation (50 lines)
│
├── graph/                      # Graph operations
│   ├── mod.rs                  # Re-exports (10 lines)
│   ├── edges.rs                # Edge CRUD (50 lines)
│   └── traversal.rs            # BFS/DFS traversal (80 lines)
│
└── bindings/                   # PyO3 Python bindings
    ├── mod.rs                  # Re-exports (10 lines)
    ├── database.rs             # Database wrapper (100 lines)
    ├── types.rs                # Type conversions (60 lines)
    └── errors.rs               # Error conversions (40 lines)
```

**Total: ~1800 lines Rust in ~30 files = avg 60 lines/file**

### Rust Function Design

```rust
/// Get entity by ID.
///
/// # Arguments
///
/// * `entity_id` - UUID of entity
///
/// # Returns
///
/// `Some(Entity)` if found, `None` if not found
///
/// # Errors
///
/// Returns `DatabaseError::StorageError` if RocksDB fails
///
/// # Example
///
/// ```
/// let entity = db.get_entity(uuid)?;
/// assert_eq!(entity.unwrap().entity_type, "articles");
/// ```
pub fn get_entity(&self, entity_id: Uuid) -> Result<Option<Entity>> {
    let key = encode_entity_key(entity_id);
    let bytes = self.storage.get(CF_ENTITIES, &key)?;

    match bytes {
        Some(data) => Ok(Some(serde_json::from_slice(&data)?)),
        None => Ok(None),
    }
}
```

**Rules:**
- **10-30 lines max** per function
- **Docstring required** for all public functions
- **Example in docstring** for non-trivial functions
- **Early returns** to reduce nesting
- **No unwrap()** in library code (only tests/examples)

### Rust Error Handling

```rust
// ✅ Good - explicit Result, thiserror
use thiserror::Error;

#[derive(Error, Debug)]
pub enum DatabaseError {
    #[error("Entity not found: {0}")]
    EntityNotFound(Uuid),

    #[error("Schema validation failed: {0}")]
    ValidationError(String),

    #[error("Storage error: {0}")]
    StorageError(#[from] rocksdb::Error),

    #[error("JSON error: {0}")]
    JsonError(#[from] serde_json::Error),
}

pub type Result<T> = std::result::Result<T, DatabaseError>;

// ✅ Good - propagate with ?
pub fn insert(&self, entity: &Entity) -> Result<()> {
    let key = encode_key(entity.id);
    let value = serde_json::to_vec(entity)?;  // Auto-converts with #[from]
    self.storage.put(&key, &value)?;
    Ok(())
}

// ❌ Bad - unwrap in library
pub fn insert(&self, entity: &Entity) {
    let value = serde_json::to_vec(entity).unwrap();  // Never do this!
    self.storage.put(&key, &value).unwrap();
}
```

### Rust Testing

```rust
// Tests in same file (unit tests)
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_encode_entity_key() {
        let key = encode_entity_key(Uuid::nil());
        assert!(key.starts_with(b"entity:"));
    }

    #[test]
    fn test_roundtrip_encoding() {
        let original = Uuid::new_v4();
        let encoded = encode_entity_key(original);
        let decoded = decode_entity_key(&encoded).unwrap();
        assert_eq!(decoded, original);
    }
}
```

**Testing rules:**
- **Unit tests** in same file under `#[cfg(test)]`
- **Integration tests** in `tests/` directory
- **One assertion** per test (or closely related assertions)
- **Descriptive names** - `test_what_when_expected`
- **80% coverage minimum**

### Rust Zero-Copy Performance

```rust
// ✅ Good - return slice (zero-copy)
pub fn get_embedding(&self, id: Uuid) -> Result<&[f32]> {
    self.embeddings.get(&id)
        .ok_or(DatabaseError::EntityNotFound(id))
}

// ✅ Good - borrow when possible
pub fn validate(&self, schema_name: &str, data: &serde_json::Value) -> Result<()> {
    let schema = self.schemas.get(schema_name)?;
    schema.validate(data)
}

// ❌ Bad - unnecessary clone
pub fn get_embedding(&self, id: Uuid) -> Result<Vec<f32>> {
    Ok(self.embeddings.get(&id)
        .ok_or(DatabaseError::EntityNotFound(id))?
        .to_vec())  // Unnecessary copy!
}
```

### Python Bindings (Minimal)

```python
# Keep Python layer thin - delegate to Rust immediately

from pydantic import BaseModel, ConfigDict

# ✅ Good - minimal, delegates to Rust
class Article(BaseModel):
    title: str
    content: str

    model_config = ConfigDict(
        json_schema_extra={
            "embedding_fields": ["content"],
            "key_field": "title"
        }
    )

# ✅ Good - thin wrapper
def insert(db: Database, table: str, data: dict) -> str:
    """Insert entity, return UUID."""
    return db._rust_insert(table, data)  # Rust does all the work

# ❌ Bad - logic in Python
def insert(db: Database, table: str, data: dict) -> str:
    # Don't do validation, embedding, etc. in Python!
    # That's what Rust is for!
```

### Module Documentation

Every `mod.rs` should have module-level documentation:

```rust
//! Entity storage operations.
//!
//! This module provides CRUD operations for entities with tenant isolation.
//! All operations are scoped to a tenant ID to ensure data isolation.
//!
//! # Example
//!
//! ```
//! use rem_db::storage::EntityStore;
//!
//! let store = EntityStore::new(storage);
//! store.insert("tenant1", &entity)?;
//! let entity = store.get("tenant1", entity_id)?;
//! ```

pub mod entities;
pub mod schema;

pub use entities::EntityStore;
pub use schema::SchemaRegistry;
```

## Architecture Decisions

### Why Column Families Over Multi-Get?

| Approach | Table Scan | Global Key Lookup | Storage Overhead | Trade-off |
|----------|-----------|-------------------|------------------|-----------|
| **Column Families** (chosen) | O(log n + k) | O(log n + k) | +10% | Fast both ways |
| Multi-Get | O(log n + k) | O(types) | 0% | Slow for many types |

**Decision:** Column families are default for reverse key lookups. Multi-get only if <5 schemas and storage critical.

### Why Binary Embeddings?

| Format | Size (384 dims) | Access Time | Trade-off |
|--------|----------------|-------------|-----------|
| **Binary** (`[f32]`) | 1.5 KB | 0.01ms (zero-copy) | Fast, compact |
| JSON array | 5 KB | 0.5ms (parse) | Slow, large |

**Decision:** Binary storage in separate CF. 3x space savings + zero-copy access.

### Why HNSW Over Naive Scan?

| Approach | Search Time (1M docs) | Index Build | Memory |
|----------|---------------------|-------------|--------|
| **HNSW** (chosen) | 5ms | 30s | 50 MB |
| Naive scan | 1000ms | 0 | 0 |

**Decision:** HNSW mandatory for >10k documents. 200x speedup justifies build time.

## Testing Guidelines

### Rust Tests
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deterministic_uuid() {
        let db = Database::open_temp("test").unwrap();
        let id1 = db.insert("table", json!({"name": "Alice"})).unwrap();
        let id2 = db.insert("table", json!({"name": "Alice"})).unwrap();
        assert_eq!(id1, id2);  // Same name → same UUID
    }

    #[tokio::test]
    async fn test_vector_search() {
        let db = Database::open_temp("test").unwrap();
        db.register_schema(/* schema with embeddings */).unwrap();

        db.insert("docs", json!({"content": "Rust is fast"})).await.unwrap();
        let results = db.search("docs", "performance", 5).await.unwrap();

        assert!(!results.is_empty());
    }
}
```

### Python Tests
```python
import pytest
from rem_db import Database

@pytest.fixture
def db(tmp_path):
    return Database(path=str(tmp_path))

def test_deterministic_uuid(db):
    id1 = db.insert("table", {"name": "Alice"})
    id2 = db.insert("table", {"name": "Alice"})
    assert id1 == id2  # Idempotent

@pytest.mark.asyncio
async def test_vector_search(db):
    # Register schema with embeddings
    # Insert documents
    results = await db.search("docs", "Rust performance", top_k=5)
    assert len(results) > 0
```

**Coverage target: 80% Rust, 90% Python**

---

**Total implementation target: ~2000 lines Rust, ~800 lines Python**
