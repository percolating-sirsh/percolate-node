# REM Database

**Resources-Entities-Moments (REM):** High-performance embedded database for semantic search, graph queries, and structured data.

**Project Location:** `/Users/sirsh/code/percolation/percolate-rocks`

## Project Goals

Build a production-ready database combining:
- **Rust performance** - HNSW vector search (200x faster), native SQL execution (5-10x faster)
- **Python ergonomics** - Pydantic models drive schemas, natural language queries
- **Zero impedance** - Pydantic `json_schema_extra` → automatic embeddings, indexing, validation

## Quick Start

### Installation

**From PyPI** (published v0.2.0):
```bash
pip install percolate-rocks
```

**From source**:
```bash
cd /Users/sirsh/code/percolation/percolate-rocks
maturin develop --release
```

See [`.release-notes/`](./.release-notes/) for release history.

### Building

This project supports two build modes:

**Python extension (default):**
```bash
# Build and install Python package
maturin develop

# Syntax check only (faster)
maturin develop --skip-install

# Note: cargo check/build will fail - use maturin for Python extensions
```

**Standalone Rust library (no Python):**
```bash
# Build as pure Rust library (no Python bindings)
cargo check --lib --no-default-features
cargo build --lib --no-default-features --release

# Run tests without Python
cargo test --lib --no-default-features

# Use in other Rust projects
# Add to Cargo.toml:
# percolate-rocks = { version = "0.1", default-features = false }
```

### Development Workflow: Using Local percolate-rocks in percolate Project

When developing features that span both `percolate-rocks` (this Rust extension) and `percolate` (the main Python project), you need to install the local development version instead of the PyPI release.

**Project Structure:**
```
percolation/
├── percolate-rocks/         # This project (Rust + PyO3)
│   ├── src/                 # Rust source code
│   ├── python/rem_db/       # Python package with Pydantic models
│   └── Cargo.toml
└── percolate/               # Main project (Python)
    ├── src/percolate/       # Python source
    ├── pyproject.toml       # Depends on: percolate-rocks>=0.3.2
    └── .venv/               # Virtual environment
```

**Method 1: Install from percolate-rocks directory** (recommended):
```bash
cd /Users/sirsh/code/percolation/percolate-rocks

# Install into percolate's venv
uv run --project ../percolate maturin develop

# Or using uv pip directly
cd ../percolate
uv pip install -e ../percolate-rocks
```

**Method 2: Use path dependency** (permanent):
```toml
# In percolate/pyproject.toml
dependencies = [
    # Comment out PyPI version:
    # "percolate-rocks>=0.3.2",

    # Use local development version:
    "percolate-rocks @ file:///Users/sirsh/code/percolation/percolate-rocks",
]
```

**Verify which version is installed:**
```bash
cd percolate
uv run python -c "import rem_db; print(rem_db.__file__)"

# PyPI version shows: .venv/lib/python3.13/site-packages/rem_db/__init__.py
# Dev version shows: ../percolate-rocks/python/rem_db/__init__.py
```

**Development workflow:**
```bash
# 1. Make changes in percolate-rocks/src/*.rs
vim percolate-rocks/src/embeddings/provider.rs

# 2. Rebuild and install into percolate venv
cd percolate-rocks
uv run --project ../percolate maturin develop

# 3. Test changes in percolate
cd ../percolate
uv run python test_something.py

# 4. Iterate quickly (rebuild is ~5-15 seconds with Cargo caching)
```

**Why this is needed:**
- `percolate` depends on `percolate-rocks` from PyPI (v0.3.2)
- When you change Rust code, you need to rebuild the extension
- `maturin develop` builds and installs the extension in editable mode
- Using `--project ../percolate` tells maturin to use percolate's venv, not percolate-rocks' venv

**Common pitfalls:**
```bash
# ❌ Wrong - builds into percolate-rocks/.venv
cd percolate-rocks
maturin develop

# ❌ Wrong - uv run uses current directory's venv
cd percolate
uv run maturin develop -m ../percolate-rocks/Cargo.toml

# ✅ Correct - explicitly target percolate's venv
cd percolate-rocks
uv run --project ../percolate maturin develop
```

### Testing cross-compilation locally

To ensure your local builds will work in CI/GitHub Actions, use Docker to replicate the CI environment:

```bash
# Test ARM64 Linux cross-compilation (what CI does)
docker run --rm -v "$(pwd):/workspace" -w /workspace rust:latest bash -c "
  apt-get update && apt-get install -y gcc-aarch64-linux-gnu pkg-config libclang-dev
  rustup target add aarch64-unknown-linux-gnu
  cargo build --target aarch64-unknown-linux-gnu --release
"
```

**Why local builds might work but CI fails:**

| Environment | Rust Version | Target | OpenSSL | Why It Works |
|-------------|--------------|--------|---------|--------------|
| **Your Mac** | Latest (1.87+) | Native (aarch64-apple-darwin) | System OpenSSL (Homebrew) | Local system libs |
| **GitHub Actions** | Workflow-specified | Cross-compile (aarch64-unknown-linux-gnu) | Vendored (native-tls-vendored feature) | Must compile from source |

**Key differences:**
1. **Rust version**: Mac typically has latest via rustup, CI uses workflow-pinned version
2. **Cross-compilation**: Mac → Linux ARM64 requires vendored dependencies (no system libs available)
3. **Native TLS**: `reqwest` needs `native-tls-vendored` feature for cross-compilation

**If Docker build passes → CI will pass.** This is your local validation gate.

### Basic Workflow

Define your schema using Pydantic (in `models.py`):

```python
from pydantic import BaseModel, Field, ConfigDict

class Article(BaseModel):
    """Article resource for semantic search."""
    title: str = Field(description="Article title")
    content: str = Field(description="Full article content")
    category: str = Field(description="Content category")

    model_config = ConfigDict(
        json_schema_extra={
            "embedding_fields": ["content"],      # Auto-embed on insert
            "indexed_fields": ["category"],       # Fast WHERE queries
            "key_field": "title"                  # Deterministic UUID
        }
    )
```

Use the CLI to work with your data:

```bash
# 1. Generate encryption key (for encryption at rest)
rem key-gen --password "strong_master_password"
# Generates Ed25519 key pair and stores encrypted at ~/.p8/keys/

# 2. Initialize database (defaults to ~/.p8/db/)
rem init

# Or specify custom path
rem init --path ./data

# With encryption at rest (optional)
rem init --path ./data --password "strong_master_password"

# 3. Register schema (JSON/YAML preferred, Python also supported)
rem schema add schema.json  # Preferred: pure JSON Schema
rem schema add schema.yaml  # Preferred: YAML format
rem schema add models.py::Article  # Also supported: Pydantic model

# Or create from template
rem schema add --name my_docs --template resources  # Clone resources schema

# 4. Batch upsert articles (single embedding API call)
cat articles.jsonl | rem insert articles --batch

# 5. Semantic search (HNSW index)
rem search "fast programming languages" --schema=articles --top-k=5

# 6. SQL queries (indexed)
rem query "SELECT * FROM articles WHERE category = 'programming'"
```

### Python API (Recommended for Applications)

For Python applications, use the `rem_db` package directly:

```python
from rem_db import Database

# Initialize database (uses P8_DB_PATH or ~/.p8/db by default)
db = Database()

# Batch insert (efficient, single atomic operation)
articles = [
    {"name": "Python Guide", "content": "...", "category": "programming"},
    {"name": "Rust Guide", "content": "...", "category": "programming"},
]
ids = db.insert_batch("articles", articles)  # Returns list of UUIDs

# Batch get (retrieve multiple by ID)
entities = db.get_batch(ids[:5])  # Get first 5

# Batch lookup (find by natural keys)
results = db.lookup_batch(["Python Guide", "Rust Guide"])

# SQL query
results = db.query("SELECT * FROM articles WHERE category = 'programming'")

# Single operations (available but batch is faster)
single_id = db.insert("articles", {"name": "New Article", "content": "..."})
single_entity = db.get(single_id)
```

**Performance tip:** Always use batch operations (`insert_batch`, `get_batch`, `lookup_batch`) for bulk data - they're 7-10x faster than individual operations, and 50-100x faster with embeddings enabled.

### Try It: Quickstart Example

We've included a complete quickstart example with sample data in `test/data/`:

```bash
# Navigate to test data directory
cd percolate-rocks/test/data

# Run the quickstart example
python quickstart_example.py
```

This example demonstrates:
- Loading data from JSONL files
- Batch insert operations
- Batch get and lookup
- SQL queries
- Performance comparisons

See [test/data/README.md](test/data/README.md) for more details and how to create your own test data.

## CLI Commands

### Setup and Schema Management

| Command | Description | Example |
|---------|-------------|---------|
| `rem key-gen` | Generate encryption key pair (Ed25519) | `rem key-gen --password "strong_password"` (saves to `~/.p8/keys/`) |
| `rem init` | Initialize database (default: `~/.p8/db/`) | `rem init` or `rem init --path ./data` or `rem init --password "..."` (encryption at rest) |
| `rem schema add <file>` | Register schema (JSON/YAML preferred) | `rem schema add schema.json` or `rem schema add models.py::Article` |
| `rem schema add --name <name> --template <template>` | Create schema from built-in template | `rem schema add --name my_docs --template resources` |
| `rem schema list` | List registered schemas | `rem schema list` |
| `rem schema show <name>` | Show schema definition | `rem schema show articles` |
| `rem schema templates` | List available templates | `rem schema templates` |

**Schema template workflow:**

```bash
# List available templates
rem schema templates
# Output:
# Available schema templates:
# - resources: Chunked documents with embeddings (URI-based)
# - entities: Generic structured data (name-based)
# - agentlets: AI agent definitions (with tools/resources)
# - moments: Temporal classifications (time-range queries)

# Create new schema from template
rem schema add --name my_documents --template resources

# This creates and registers:
# - Schema name: my_documents
# - Clones all fields from resources template
# - Updates fully_qualified_name: "user.my_documents"
# - Updates short_name: "my_documents"
# - Preserves embedding/indexing configuration

# Customize the generated schema (optional)
rem schema show my_documents > my_documents.json
# Edit my_documents.json
rem schema add my_documents.json  # Re-register with changes

# Or save to file without registering
rem schema add --name my_docs --template resources --output my_docs.yaml
# Edit my_docs.yaml
rem schema add my_docs.yaml  # Register when ready
```

**Built-in templates:**

| Template | Use Case | Key Fields | Configuration |
|----------|----------|------------|---------------|
| `resources` | Documents, articles, PDFs | `name`, `content`, `uri`, `chunk_ordinal` | Embeds `content`, indexes `content_type`, key: `uri` |
| `entities` | Generic structured data | `name`, `key`, `properties` | Indexes `name`, key: `name` |
| `agentlets` | AI agent definitions | `description`, `tools`, `resources` | Embeds `description`, includes MCP config |
| `moments` | Temporal events | `name`, `start_time`, `end_time`, `classifications` | Indexes `start_time`, `end_time` |

**Example: Creating custom document schema**

```bash
# Start with resources template
rem schema add --name technical_docs --template resources --output technical_docs.yaml

# Edit technical_docs.yaml to add custom fields:
# - difficulty_level: enum["beginner", "intermediate", "advanced"]
# - language: string
# - code_examples: array[object]

# Register customized schema
rem schema add technical_docs.yaml

# Insert documents
cat docs.jsonl | rem insert technical_docs --batch
```

### Data Operations

| Command | Description | Example |
|---------|-------------|---------|
| `rem insert <table> <json>` | Insert entity | `rem insert articles '{"title": "..."}` |
| `rem insert <table> --batch` | Batch insert from stdin | `cat data.jsonl \| rem insert articles --batch` |
| `rem ingest <file>` | Upload and chunk file | `rem ingest tutorial.pdf --schema=articles` |
| `rem get <uuid>` | Get entity by ID | `rem get 550e8400-...` |
| `rem lookup <key>` | Global key lookup | `rem lookup "Python Guide"` |

### Search and Queries

| Command | Description | Example |
|---------|-------------|---------|
| `rem search <query>` | Semantic search | `rem search "async programming" --schema=articles` |
| `rem query "<SQL>"` | SQL query | `rem query "SELECT * FROM articles WHERE category = 'tutorial'"` |
| `rem ask "<question>"` | Natural language query (executes) | `rem ask "show recent programming articles"` |
| `rem ask "<question>" --plan` | Show query plan without executing | `rem ask "show recent articles" --plan` |
| `rem traverse <uuid>` | Graph traversal | `rem traverse <id> --depth=2 --direction=out` |

**Natural language query examples:**

```bash
# Execute query immediately
rem ask "show recent programming articles"
# Output: Query results as JSON

# Show query plan without executing (LLM response only)
rem ask "show recent programming articles" --plan
# Output:
# {
#   "confidence": 0.95,
#   "query": "SELECT * FROM articles WHERE category = 'programming' ORDER BY created_at DESC LIMIT 10",
#   "reasoning": "User wants recent articles filtered by programming category",
#   "requires_search": false
# }

# Complex query with semantic search
rem ask "find articles about Rust performance optimization" --plan
# Output:
# {
#   "confidence": 0.85,
#   "query": "SEARCH articles 'Rust performance optimization' LIMIT 10",
#   "reasoning": "Semantic search needed for conceptual similarity",
#   "requires_search": true
# }
```

### Export and Analytics

| Command | Description | Example |
|---------|-------------|---------|
| `rem export <table>` | Export to Parquet | `rem export articles --output ./data.parquet` |
| `rem export --all` | Export all schemas | `rem export --all --output ./exports/` |

### REM Dreaming (Background Intelligence)

| Command | Description | Example |
|---------|-------------|---------|
| `rem dream` | Run dreaming with default lookback (24h) | `rem dream` |
| `rem dream --lookback-hours <N>` | Custom lookback window | `rem dream --lookback-hours 168` (weekly) |
| `rem dream --dry-run` | Show what would be generated | `rem dream --dry-run --verbose` |
| `rem dream --llm <model>` | Specify LLM provider | `rem dream --llm gpt-4-turbo` |
| `rem dream --start <date> --end <date>` | Specific date range | `rem dream --start "2025-10-20" --end "2025-10-25"` |

**REM Dreaming** uses LLMs to analyze your activity in the background and generate:
- **Moments**: Temporal classifications of what you were working on (with emotions, topics, outcomes)
- **Summaries**: Period recaps and key insights
- **Graph edges**: Automatic connections between related resources and sessions
- **Ontological maps**: Topic relationships and themes

See [`docs/rem-dreaming.md`](docs/rem-dreaming.md) for detailed documentation.

## Core System Schemas

REM Database includes three core schemas for tracking user activity:

### Sessions

**Purpose:** Track conversation sessions with AI agents.

**Key fields:**
- `id` (UUID) - Session identifier
- `case_id` (UUID) - Optional link to project/case
- `user_id` (string) - User identifier
- `metadata` (object) - Session context

**Schema:** [`schema/core/sessions.json`](schema/core/sessions.json)

### Messages

**Purpose:** Individual messages within sessions (user queries, AI responses, tool calls).

**Key fields:**
- `session_id` (UUID) - Parent session
- `role` (enum) - user | assistant | system | tool
- `content` (string) - Message content (embedded for search)
- `tool_calls` (array) - Tool invocations
- `trace_id`, `span_id` (string) - Observability

**Schema:** [`schema/core/messages.json`](schema/core/messages.json)

### Moments

**Purpose:** Temporal classifications generated by REM Dreaming.

**Key fields:**
- `name` (string) - Moment title
- `summary` (string) - Activity description
- `start_time`, `end_time` (datetime) - Time bounds
- `moment_type` (enum) - work_session | learning | planning | communication | reflection | creation
- `tags` (array) - Topic tags (e.g., ["rust", "database", "performance"])
- `emotion_tags` (array) - Emotion/tone tags (e.g., ["focused", "productive"])
- `people` (array) - People mentioned
- `resource_ids`, `session_ids` (arrays) - Related entities

**Schema:** [`schema/core/moments.json`](schema/core/moments.json)

**These schemas are registered automatically on `rem init`.**

## Peer Replication Testing

REM supports primary/replica replication via WAL and gRPC streaming.

### Terminal 1: Primary Node

```bash
# Start primary with WAL enabled
export P8_REPLICATION_MODE=primary
export P8_REPLICATION_PORT=50051
export P8_WAL_ENABLED=true
export P8_DB_PATH=./data/primary  # Override default ~/.p8/db/

rem init
# Register schema (JSON/YAML preferred)
rem schema add schema.json

# Start replication server
rem serve --host 0.0.0.0 --port 50051

# Insert data (will be replicated)
rem insert articles '{"title": "Doc 1", "content": "Test replication", "category": "test"}'

# Check WAL status
rem replication wal-status
# Output:
# WAL sequence: 1
# Entries: 1
# Size: 512 bytes
```

### Terminal 2: Replica 1

```bash
# Start replica pointing to primary
export P8_REPLICATION_MODE=replica
export P8_PRIMARY_HOST=localhost:50051
export P8_DB_PATH=./data/replica1  # Override default ~/.p8/db/

rem init

# Connect and sync from primary
rem replicate --primary=localhost:50051 --follow

# Check replication status
rem replication status
# Output:
# Mode: replica
# Primary: localhost:50051
# WAL position: 1
# Lag: 2ms
# Status: synced

# Query replica (read-only)
rem query "SELECT * FROM articles"
# Output: Same data as primary
```

### Terminal 3: Replica 2

```bash
export P8_REPLICATION_MODE=replica
export P8_PRIMARY_HOST=localhost:50051
export P8_DB_PATH=./data/replica2  # Override default ~/.p8/db/

rem init
rem replicate --primary=localhost:50051 --follow

# Verify sync
rem query "SELECT COUNT(*) FROM articles"
# Output: 1
```

### Testing Failover

**Terminal 1: Simulate Primary Failure**
```bash
^C  # Stop primary server
```

**Terminal 2: Replica Behavior During Outage**
```bash
# Replica continues serving reads
rem query "SELECT * FROM articles"
# Output: Cached data still available

# Check status
rem replication status
# Output:
# Status: disconnected
# Last sync: 45s ago
# Buffered writes: 0 (read-only)
```

**Terminal 1: Primary Restart**
```bash
# Restart primary and insert new data
rem serve --host 0.0.0.0 --port 50051
rem insert articles '{"title": "Doc 2", "content": "After restart", "category": "test"}'
```

**Terminal 2: Automatic Catchup**
```bash
# Replica auto-reconnects and syncs
rem replication status
# Output:
# Status: synced
# Catchup: completed (1 entry, 50ms)
# Lag: 3ms

# Verify new data
rem query "SELECT title FROM articles ORDER BY created_at DESC LIMIT 1"
# Output: Doc 2
```

## Key Implementation Conventions

### REM Principle

**Resources-Entities-Moments** is a unified data model, not separate storage:

- **Resources**: Chunked documents with embeddings → semantic search (HNSW)
- **Entities**: Structured data → SQL queries (indexed fields)
- **Moments**: Temporal classifications → time-range queries

All stored as **entities** in RocksDB. Conceptual distinction only.

### Pydantic-Driven Everything

Configuration flows from `json_schema_extra`:

NB!: While we support adding metadata in config. Fields can also take properties like key-field and embedding_provider as json schema extra and is preferred.

```python
model_config = ConfigDict(
    json_schema_extra={
        "embedding_fields": ["content"],      # → Auto-embed on insert
        "indexed_fields": ["category"],       # → RocksDB index CF
        "key_field": "title"                  # → Deterministic UUID
    }
)
```

NB: Rust can also define schema in equivalent mode classes or schema but we drive things with pydantic aware semantics of the json schema format.

### Deterministic UUIDs (Idempotent Inserts)

NB: Precedence; uri -> key -> name unless specified in config.

| Priority | Field | UUID Generation |
|----------|-------|-----------------|
| 1 | `uri` | `blake3(entity_type + uri + chunk_ordinal)` |
| 2 | `json_schema_extra.key_field` | `blake3(entity_type + value)` |
| 3 | `key` | `blake3(entity_type + key)` |
| 4 | `name` | `blake3(entity_type + name)` |
| 5 | (fallback) | `UUID::v4()` (random) |

Same key → same UUID → upsert semantics.

### System Fields (Always Auto-Added)

**Never** define these in Pydantic models - always added by database:

- `id` (UUID) - Deterministic or random
- `entity_type` (string) - Schema/table name
- `created_at`, `modified_at`, `deleted_at` (ISO 8601) - Timestamps
- `edges` (array[string]) - Graph relationships

### Embedding Fields (Conditionally Added)

**Not system fields** - only added when configured:

- `embedding` (array[float32]) - Added if `embedding_fields` in `json_schema_extra`
- `embedding_alt` (array[float32]) - Added if `P8_ALT_EMBEDDING` environment variable set

```python
# Configuration that triggers embedding generation:
model_config = ConfigDict(
    json_schema_extra={
        "embedding_fields": ["content"],      # → Adds "embedding" field
        "embedding_provider": "default"       # → Uses P8_DEFAULT_EMBEDDING
    }
)
```

### Encryption at Rest

Optional encryption at rest using **Ed25519 key pairs** and **ChaCha20-Poly1305 AEAD**:

1. **Generate key pair** (one-time setup):
   ```bash
   rem key-gen --password "strong_master_password"
   # Stores encrypted key at ~/.p8/keys/private_key_encrypted
   # Stores public key at ~/.p8/keys/public_key
   ```

2. **Initialize database with encryption**:
   ```bash
   rem init --password "strong_master_password"
   # All entity data encrypted before storage
   # Transparent encryption/decryption on get/put
   ```

3. **Sharing across tenants** (future):
   - Encrypt data with recipient's **public key** (X25519 ECDH)
   - End-to-end encryption - even database admin cannot read shared data

4. **Device-to-device sync** (future):
   - WAL entries encrypted before gRPC transmission
   - Defense in depth: mTLS (transport) + encrypted WAL (application layer)

**Key security properties:**
- Private key **never leaves device unencrypted**
- Password-derived key using **Argon2** KDF
- **ChaCha20-Poly1305** AEAD for data encryption
- Public key stored unencrypted for sharing capabilities

See `docs/encryption-architecture.md` for complete design.

### Column Families (Performance)

| CF | Purpose | Speedup vs Scan |
|----|---------|-----------------|
| `key_index` | Reverse key lookup | O(log n) vs O(n) |
| `edges` + `edges_reverse` | Bidirectional graph | 20x faster |
| `embeddings` (binary) | Vector storage | 3x compression |
| `indexes` | Indexed fields | 10-50x faster |
| `keys` | Encrypted tenant keys | - |

### HNSW Vector Index

Rust HNSW index provides **200x speedup** over naive Python scan:
- Python naive: ~1000ms for 1M documents
- Rust HNSW: ~5ms for 1M documents

This is the **primary reason** for Rust implementation.

## Performance Targets

| Operation | Target | Why Rust? |
|-----------|--------|-----------|
| Insert (no embedding) | < 1ms | RocksDB + zero-copy |
| Insert (with embedding) | < 50ms | Network-bound (OpenAI) |
| Get by ID | < 0.1ms | Single RocksDB get |
| Vector search (1M docs) | < 5ms | **HNSW (vs 1000ms naive)** |
| SQL query (indexed) | < 10ms | **Native execution (vs 50ms Python)** |
| Graph traversal (3 hops) | < 5ms | **Bidirectional CF (vs 100ms scan)** |
| Batch insert (1000 docs) | < 500ms | Batched embeddings |
| Parquet export (100k rows) | < 2s | **Parallel encoding** |

NB: WE generally work in batches; batch upserts and batch embeddings. NEVER make individual requests when batches are possible.

## Environment Configuration

```bash
# Core
export P8_HOME=~/.p8
export P8_DB_PATH=$P8_HOME/db

# Embeddings
export P8_DEFAULT_EMBEDDING=local:all-MiniLM-L6-v2
export P8_OPENAI_API_KEY=sk-...  # For OpenAI embeddings

# LLM (natural language queries)
# Note: These are for Rust-based query planner (Database.plan_query())
export ANTHROPIC_API_KEY=sk-ant-...
export CEREBRAS_API_KEY=csk-...
export P8_DEFAULT_LLM=claude-sonnet-4-5-20250929  # Default provider

# For Python-based tools (percolate package)
export PERCOLATE_DEFAULT_MODEL=anthropic:claude-sonnet-4-5-20250929  # General purpose
export PERCOLATE_QUERY_MODEL=cerebras:qwen-3-32b                     # Fast query planning (2400 tok/s)

# RocksDB tuning
export P8_ROCKSDB_WRITE_BUFFER_SIZE=67108864  # 64MB
export P8_ROCKSDB_MAX_BACKGROUND_JOBS=4
export P8_ROCKSDB_COMPRESSION=lz4

# Replication
export P8_REPLICATION_MODE=primary  # or replica
export P8_PRIMARY_HOST=localhost:50051  # For replicas
export P8_WAL_ENABLED=true
```

**LLM Configuration Guide:**

For detailed LLM setup (Cerebras + Claude configuration, performance benchmarks, troubleshooting):
- See **[docs/query-engine/](docs/query-engine/)** - Complete query engine documentation including:
  - **[QUERY_LLM_QUICKSTART.md](docs/query-engine/QUERY_LLM_QUICKSTART.md)** - LLM configuration guide
  - Cerebras strict JSON schema requirements
  - Claude vs Cerebras comparison
  - Performance benchmarks (Cerebras: 2400 tok/s, ~500ms query planning)
  - Environment variable patterns
  - Debugging guide

See [CLAUDE.md](./CLAUDE.md) for full environment variable reference.

## Project Structure

```
percolate-rocks/          # Clean implementation
├── Cargo.toml            # Rust dependencies
├── pyproject.toml        # Python package (maturin)
├── README.md             # This file
├── CLAUDE.md             # Implementation guide
│
├── src/                  # Rust implementation (~3000 lines target)
│   ├── lib.rs            # PyO3 module definition (30 lines)
│   │
│   ├── types/            # Core data types (120 lines)
│   │   ├── mod.rs        # Re-exports
│   │   ├── entity.rs     # Entity, Edge structs
│   │   ├── error.rs      # Error types (thiserror)
│   │   └── result.rs     # Type aliases
│   │
│   ├── storage/          # RocksDB wrapper (400 lines)
│   │   ├── mod.rs        # Re-exports
│   │   ├── db.rs         # Storage struct + open
│   │   ├── keys.rs       # Key encoding functions
│   │   ├── batch.rs      # Batch writer
│   │   ├── iterator.rs   # Prefix iterator
│   │   └── column_families.rs  # CF constants + setup
│   │
│   ├── index/            # Indexing layer (310 lines)
│   │   ├── mod.rs        # Re-exports
│   │   ├── hnsw.rs       # HNSW vector index
│   │   ├── fields.rs     # Indexed fields
│   │   └── keys.rs       # Key index (reverse lookup)
│   │
│   ├── query/            # Query execution (260 lines)
│   │   ├── mod.rs        # Re-exports
│   │   ├── parser.rs     # SQL parser
│   │   ├── executor.rs   # Query executor
│   │   ├── predicates.rs # Predicate evaluation
│   │   └── planner.rs    # Query planner
│   │
│   ├── embeddings/       # Embedding providers (200 lines)
│   │   ├── mod.rs        # Re-exports
│   │   ├── provider.rs   # Provider trait + factory
│   │   ├── local.rs      # Local models (fastembed)
│   │   ├── openai.rs     # OpenAI API client
│   │   └── batch.rs      # Batch embedding operations
│   │
│   ├── schema/           # Schema validation (160 lines)
│   │   ├── mod.rs        # Re-exports
│   │   ├── registry.rs   # Schema registry
│   │   ├── validator.rs  # JSON Schema validation
│   │   └── pydantic.rs   # Pydantic json_schema_extra parser
│   │
│   ├── graph/            # Graph operations (130 lines)
│   │   ├── mod.rs        # Re-exports
│   │   ├── edges.rs      # Edge CRUD
│   │   └── traversal.rs  # BFS/DFS traversal
│   │
│   ├── replication/      # Replication engine (400 lines)
│   │   ├── mod.rs        # Re-exports
│   │   ├── wal.rs        # Write-ahead log
│   │   ├── primary.rs    # Primary node (gRPC server)
│   │   ├── replica.rs    # Replica node (gRPC client)
│   │   ├── protocol.rs   # gRPC protocol definitions
│   │   └── sync.rs       # Sync state machine
│   │
│   ├── export/           # Export formats (200 lines)
│   │   ├── mod.rs        # Re-exports
│   │   ├── parquet.rs    # Parquet writer
│   │   ├── csv.rs        # CSV writer
│   │   └── jsonl.rs      # JSONL writer
│   │
│   ├── ingest/           # Document ingestion (180 lines)
│   │   ├── mod.rs        # Re-exports
│   │   ├── chunker.rs    # Document chunking
│   │   ├── pdf.rs        # PDF parser
│   │   └── text.rs       # Text chunking
│   │
│   ├── llm/              # LLM query builder (150 lines)
│   │   ├── mod.rs        # Re-exports
│   │   ├── query_builder.rs  # Natural language → SQL
│   │   └── planner.rs    # Query plan generation
│   │
│   └── bindings/         # PyO3 Python bindings (300 lines)
│       ├── mod.rs        # Re-exports
│       ├── database.rs   # Database wrapper (main API)
│       ├── types.rs      # Type conversions (Python ↔ Rust)
│       ├── errors.rs     # Error conversions
│       └── async_ops.rs  # Async operation wrappers
│
├── python/               # Python package (~800 lines target)
│   └── rem_db/
│       ├── __init__.py   # Public API (thin wrapper over Rust)
│       ├── cli.py        # Typer CLI (delegates to Rust)
│       ├── models.py     # Built-in Pydantic schemas
│       └── async_api.py  # Async wrapper utilities
│
└── tests/
    ├── rust/             # Rust integration tests
    │   ├── test_crud.rs
    │   ├── test_search.rs
    │   ├── test_graph.rs
    │   ├── test_replication.rs
    │   └── test_export.rs
    │
    └── python/           # Python integration tests
        ├── test_api.py
        ├── test_cli.py
        ├── test_async.py
        └── test_end_to_end.py
```

**Key Design Notes:**

1. **Rust Core (~3000 lines in ~40 files)**: All performance-critical operations in Rust
   - Average 75 lines per file
   - Max 150 lines per file
   - Single responsibility per module

2. **Python Bindings (bindings/)**: Thin PyO3 layer
   - Database wrapper exposes high-level API
   - Type conversions between Python dict/list ↔ Rust structs
   - Error conversions for Python exceptions
   - Async operation wrappers (tokio → asyncio)
   - **No business logic** - pure translation layer

3. **Python Package (python/)**: Minimal orchestration
   - CLI delegates to Rust immediately
   - Public API is thin wrapper (`db._rust_insert()`)
   - Pydantic models define schemas, Rust validates/stores
   - Async utilities for Python async/await ergonomics

4. **Replication Module**: Primary/replica peer replication
   - WAL (write-ahead log) for durability
   - gRPC streaming for real-time sync
   - Automatic catchup after disconnection
   - Read-only replica mode

5. **Export Module**: Analytics-friendly formats
   - Parquet with ZSTD compression
   - CSV for spreadsheets
   - JSONL for streaming/batch processing

6. **LLM Module**: Natural language query interface
   - Convert questions → SQL/SEARCH queries
   - Query plan generation (`--plan` flag)
   - Confidence scoring

7. **Test Organization**: Separation of unit and integration tests

   **Rust Tests:**
   - **Unit tests**: Inline with implementation using `#[cfg(test)]` modules
     ```rust
     // src/storage/keys.rs
     #[cfg(test)]
     mod tests {
         use super::*;

         #[test]
         fn test_encode_entity_key() {
             let key = encode_entity_key(uuid);
             assert!(key.starts_with(b"entity:"));
         }
     }
     ```
   - **Integration tests**: In `tests/rust/` directory
     - Test full workflows across modules
     - Require actual RocksDB instance
     - May be slower (acceptable up to 10s per test)

   **Python Tests:**
   - **Unit tests**: NOT APPLICABLE (Python layer is thin wrapper)
   - **Integration tests**: In `tests/python/` directory
     - Test PyO3 bindings (Python ↔ Rust type conversions)
     - Test CLI commands end-to-end
     - Test async/await ergonomics
     - Require Rust library to be built

   **Running Tests:**
   ```bash
   # Rust unit tests (fast, inline with code)
   cargo test --lib

   # Rust integration tests (slower, requires RocksDB)
   cargo test --test '*'

   # Python integration tests (requires maturin build)
   maturin develop
   pytest tests/python/

   # All tests
   cargo test && pytest tests/python/
   ```

   **Coverage Targets:**
   - Rust: 80%+ coverage (critical path)
   - Python: 90%+ coverage (thin wrapper, easy to test)

## Development

### Pre-Build Checks

```bash
# Check compilation (fast, no binary output)
cargo check

# Format check (without modifying files)
cargo fmt --check

# Linting with clippy
cargo clippy --all-targets --all-features

# Security audit (requires: cargo install cargo-audit)
cargo audit

# Check for outdated dependencies (requires: cargo install cargo-outdated)
cargo outdated
```

### Building

```bash
# Development build (unoptimized, fast compile)
cargo build

# Release build (optimized, slower compile)
cargo build --release

# Python extension development install (editable)
maturin develop

# Python extension release wheel
maturin build --release
```

### Publishing to PyPI

```bash
# Build release wheel (macOS ARM64)
maturin build --release

# Upload to PyPI (requires PYPI_TOKEN environment variable)
source ~/.bash_profile
export MATURIN_PYPI_TOKEN=$PYPI_TOKEN
maturin upload target/wheels/percolate_rocks-*.whl

# Or publish directly (builds and uploads)
source ~/.bash_profile
export MATURIN_PYPI_TOKEN=$PYPI_TOKEN
maturin publish --no-sdist
```

**Note:** PyPI now requires API token authentication (username/password deprecated).
Set `PYPI_TOKEN` in your shell profile with your PyPI API token.

### Testing

```bash
# Rust unit tests
cargo test

# Rust unit tests with output
cargo test -- --nocapture

# Python integration tests (requires maturin develop first)
pytest

# Python tests with verbose output
pytest -v

# Run specific test
cargo test test_name
```

### Code Quality

```bash
# Auto-format code
cargo fmt

# Run clippy linter
cargo clippy --all-targets

# Fix clippy warnings automatically (where possible)
cargo clippy --fix

# Check for unused dependencies
cargo machete  # requires: cargo install cargo-machete
```

### Benchmarks

```bash
# Run all benchmarks
cargo bench

# Run specific benchmark
cargo bench vector_search
```

### Development Workflow

```bash
# 1. Make changes to Rust code
# 2. Check compilation
cargo check

# 3. Run tests
cargo test

# 4. Build Python extension
maturin develop

# 5. Test Python integration
pytest
```

## References

- **Specification**: See `db-specification-v0.md` in `-ref` folder
- **Python spike**: `../rem-db` (100% features, production-ready)
- **Old Rust spike**: `../percolate-rocks-ref` (~40% features)
- **Implementation guide**: [CLAUDE.md](./CLAUDE.md)
