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

This project cherry-picks the best from two spikes:
- **Python spike** (`rem-db`): Full features, great UX, 100% working
- **Rust spike** (`percolate-rocks`): Performance foundation, PyO3 bindings

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
| `embedding` | array[float32] \| null | Primary embedding vector | Insert/Update | Yes |
| `embedding_alt` | array[float32] \| null | Alternative embedding vector | Insert/Update | Yes |

**Example stored entity:**
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
    "embedding": [0.1, 0.5, -0.2, ...]
  }
}
```

### Environment Variables

| Variable | Default | Description | Used By |
|----------|---------|-------------|---------|
| **Core** |
| `P8_HOME` | `~/.percolate` | Data directory root | All |
| `P8_DB_PATH` | `$P8_HOME/data` | Database storage path | Storage |
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
home = "~/.percolate"
db_path = "$P8_HOME/data"

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
| 1 | `uri` | `blake3(tenant + uri + chunk_ordinal)` | Resources (chunked documents) |
| 2 | `json_schema_extra.key_field` | `blake3(tenant + field_value)` | Custom key field |
| 3 | `key` | `blake3(tenant + key)` | Generic key field |
| 4 | `name` | `blake3(tenant + name)` | Named entities |
| 5 | (none) | `UUID::v4()` (random) | No natural key |

**Example:**
```python
# Resource with uri (priority 1)
{"uri": "https://docs.python.org", "content": "..."}
# → UUID = blake3("tenant:resources:https://docs.python.org:0")

# Person with custom key_field (priority 2)
class Person(BaseModel):
    email: str
    model_config = ConfigDict(json_schema_extra={"key_field": "email"})

{"email": "alice@co.com", "name": "Alice"}
# → UUID = blake3("tenant:person:alice@co.com")

# Generic entity with name (priority 4)
{"name": "Project Alpha", "description": "..."}
# → UUID = blake3("tenant:table:Project Alpha")
```

### Column Families

| Column Family | Key Pattern | Value | Purpose |
|---------------|-------------|-------|---------|
| **entities** | `entity:{tenant}:{uuid}` | Entity (JSON) | Main entity storage |
| **key_index** | `key:{tenant}:{key_value}:{uuid}` | `{type: string}` | Reverse key lookup (global search) |
| **edges** | `src:{uuid}:dst:{uuid}:type:{rel}` | EdgeData (JSON) | Forward graph edges |
| **edges_reverse** | `dst:{uuid}:src:{uuid}:type:{rel}` | EdgeData (JSON) | Reverse graph edges |
| **embeddings** | `emb:{tenant}:{uuid}` | `[f32; dim]` (binary) | Vector embeddings (compact) |
| **indexes** | `idx:{tenant}:{field}:{value}:{uuid}` | `{}` (empty) | Indexed field lookups |
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

### Schema Definition Pattern

```python
from pydantic import BaseModel, Field, ConfigDict

class Article(BaseModel):
    """User-defined fields only (no system fields)."""

    title: str = Field(description="Article title")
    content: str = Field(description="Full article content")
    category: str = Field(description="Content category")
    tags: list[str] = Field(default_factory=list, description="Article tags")

    model_config = ConfigDict(
        json_schema_extra={
            # Embedding configuration
            "embedding_fields": ["content"],         # Auto-embed these fields
            "embedding_provider": "default",         # P8_DEFAULT_EMBEDDING

            # Indexing configuration
            "indexed_fields": ["category"],          # Fast WHERE queries
            "key_field": "title",                    # Deterministic UUIDs

            # Metadata
            "fully_qualified_name": "myapp.Article",
            "short_name": "articles",
            "version": "1.0.0",
            "category": "user"                       # system | user
        }
    )
```

### What Happens in Rust

```rust
// 1. User registers schema
db.register_schema(
    "articles",
    article_schema_json,  // From Article.model_json_schema()
    vec!["category"],     // indexed_fields
    vec!["content"]       // embedding_fields
)?;

// 2. User inserts entity
let properties = json!({
    "title": "Rust Performance",
    "content": "Rust is fast...",
    "category": "programming",
    "tags": ["rust", "performance"]
});

db.insert("articles", properties).await?;

// 3. Rust automatically:
// - Validates against JSON Schema
// - Generates deterministic UUID from "title" (key_field)
// - Embeds "content" field → stores in embeddings CF
// - Indexes "category" → stores in indexes CF
// - Adds system fields (id, created_at, modified_at)
// - Stores in entities CF
```

### Built-in Schemas

The database ships with three built-in Pydantic models:

```python
# 1. Resource (chunked documents)
class Resource(BaseModel):
    name: str
    content: str
    uri: str
    chunk_ordinal: int = 0
    chunk_total: int = 1

    model_config = ConfigDict(
        json_schema_extra={
            "embedding_fields": ["content"],
            "key_field": "uri"
        }
    )

# 2. File (original file metadata)
class File(BaseModel):
    name: str
    uri: str
    mime_type: str
    size_bytes: int

    model_config = ConfigDict(
        json_schema_extra={"key_field": "uri"}
    )

# 3. Schema (Pydantic schema storage - recursive!)
class Schema(BaseModel):
    fully_qualified_name: str
    short_name: str
    version: str
    category: str
    description: str

    model_config = ConfigDict(
        json_schema_extra={
            "embedding_fields": ["description"],  # For schema auto-detection
            "key_field": "fully_qualified_name"
        }
    )
```

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

### Rust Standards

#### File Organization
```
src/
├── lib.rs              # PyO3 module (50 lines)
├── types/              # Core types (3 files, ~200 lines)
├── storage/            # RocksDB wrapper (5 files, ~400 lines)
├── index/              # HNSW + indexes (3 files, ~300 lines)
├── query/              # SQL parser + executor (4 files, ~400 lines)
├── embeddings/         # Embedding providers (2 files, ~200 lines)
└── bindings/           # PyO3 wrappers (1 file, ~300 lines)
```

**Rule: Max 200 lines per file. One responsibility per file.**

#### Type Safety
```rust
// ✅ Good - explicit Result
pub fn get_entity(&self, id: Uuid) -> Result<Option<Entity>, DatabaseError> {
    self.storage.get(id)
}

// ❌ Bad - unwrap in library
pub fn get_entity(&self, id: Uuid) -> Entity {
    self.storage.get(id).unwrap().unwrap()
}

// ✅ Good - thiserror for errors
#[derive(Error, Debug)]
pub enum DatabaseError {
    #[error("Entity not found: {0}")]
    EntityNotFound(Uuid),

    #[error("Validation failed: {0}")]
    ValidationError(String),
}
```

#### Zero-Copy Patterns
```rust
// ✅ Good - return slice
pub fn get_embedding(&self, id: Uuid) -> Result<&[f32]> {
    self.index.embedding_slice(id)
}

// ❌ Bad - unnecessary clone
pub fn get_embedding(&self, id: Uuid) -> Result<Vec<f32>> {
    self.index.embedding(id).map(|e| e.to_vec())
}
```

### Python Standards

#### Pydantic Models
```python
# ✅ Good - clean model
class Article(BaseModel):
    """User fields only."""
    title: str
    content: str

    model_config = ConfigDict(
        json_schema_extra={
            "embedding_fields": ["content"],
            "key_field": "title"
        }
    )

# ❌ Bad - system fields in model
class Article(BaseModel):
    id: UUID              # Added by database!
    embedding: list[float]  # Added by database!
    created_at: datetime    # Added by database!
```

#### CLI Commands (Typer)
```python
import typer
from rich.console import Console

app = typer.Typer()
console = Console()

@app.command()
def search(
    query: str,
    schema: str = typer.Option(None, "--schema", "-s"),
    top_k: int = typer.Option(10, "--top-k", "-k"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Semantic search across entities."""
    db = get_database()
    results = asyncio.run(db.search(schema or "*", query, top_k))

    if json_output:
        print(json.dumps(results))
    else:
        for entity, score in results:
            console.print(f"[green]{score:.3f}[/green] {entity['name']}")
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
    return Database(tenant_id="test", path=str(tmp_path))

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
