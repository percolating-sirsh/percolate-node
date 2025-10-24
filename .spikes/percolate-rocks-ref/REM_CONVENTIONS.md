# REM database conventions

## Overview

REM (Resources-Entities-Moments) is a simple memory system for AI applications, built on a key-value database with vector search capabilities.

## Core concepts

### Three entity types

1. **Resources** - Chunked documents with URIs
   - **ID generation:** `hash(uri:chunk_ordinal)` (deterministic)
   - **Required fields:** `uri` (cannot be null)
   - **Use case:** Document chunks, files, web pages
   - **Example:**
     ```json
     {
       "uri": "docs/readme.md",
       "chunk_ordinal": 0,
       "content": "First chunk of readme",
       "metadata": {"author": "Alice"}
     }
     ```

2. **Entities** - Named objects with relationships
   - **ID generation:** `hash(key)` or `hash(name)` (deterministic)
   - **Required fields:** `key` OR `name` (cannot be null)
   - **Use case:** Users, products, concepts, agents
   - **Example:**
     ```json
     {
       "name": "Alice",
       "email": "alice@example.com",
       "role": "engineer"
     }
     ```

3. **Moments** - Temporal classifications (special type of Resource)
   - **ID generation:** `hash(time_period_classification)`
   - **Required fields:** Time period identifier (like URI but time-based)
   - **Use case:** Time-based events, logs, sessions
   - **Example:**
     ```json
     {
       "time_period": "2025-01-15T10:00:00Z",
       "classification": "meeting",
       "content": "Team standup notes"
     }
     ```

## ID generation rules

**Precedence:** uri → key → name

1. If `uri` exists → `hash(uri:chunk_ordinal)`
2. Else if `key` exists → `hash(key)`
3. Else if `name` exists → `hash(name)`
4. Otherwise → **ERROR** (one of these fields is required)

**Hash function:** blake3 (32 bytes) → first 16 bytes → UUID

**Benefits:**
- Deterministic IDs enable idempotent upserts
- Same URI/key/name always maps to same ID
- Re-importing updates existing entities

## Embedding strategy

### Default embedding

- **Local:** all-MiniLM-L6-v2 (384 dims) - downloaded on first use to `~/.p8/models/`
- **OpenAI:** text-embedding-3-small (1536 dims) - set via `P8_DEFAULT_EMBEDDING` env var

### Embedding fields

Auto-detected from schema:
- `content` (priority 1)
- `description` (priority 2)

Only one embedding generated per entity (stored in `embedding` field).

### Configuration

```bash
# Local (default)
rem-db init mydb

# OpenAI
export P8_DEFAULT_EMBEDDING="text-embedding-3-small"
export OPENAI_API_KEY="sk-..."
rem-db init mydb
```

## Query capabilities

### 1. SQL query (single table, no aggregates)

```bash
rem-db query -d mydb "SELECT * FROM resources WHERE category = 'ai'"
```

**Limitations:**
- Single table only (no JOINs)
- No aggregates (no GROUP BY, COUNT, SUM, etc.)
- Simple WHERE predicates only

**Status:** ⚠️ Partially implemented (SQL parser not yet integrated)

### 2. Key/ID lookup

```bash
rem-db lookup -d mydb <entity-id>
```

**Status:** ❌ Not implemented

### 3. Vector search (natural language)

```bash
rem-db search -d mydb "programming languages" --min-score 0.3 --top-k 10
```

**Features:**
- HNSW index for fast approximate nearest neighbor search
- Background thread for index building
- Cosine similarity scoring

**Status:** ✅ Implemented (HNSW index building pending)

### 4. Export to Parquet

```bash
rem-db export -d mydb resources --output data.parquet
```

**Status:** ⚠️ Partially implemented (exports as JSON, not Parquet yet)

## Schema management

### Built-in schemas

When `rem-db init` runs, default schemas are registered:

1. **Resources schema:**
   ```json
   {
     "type": "object",
     "properties": {
       "uri": {"type": "string"},
       "content": {"type": "string"},
       "category": {"type": "string"},
       "metadata": {"type": "object"}
     },
     "required": ["uri", "content"]
   }
   ```

2. **Agent schema** (future):
   ```json
   {
     "type": "object",
     "properties": {
       "name": {"type": "string"},
       "description": {"type": "string"},
       "system_prompt": {"type": "string"},
       "output_schema": {"type": "object"}
     },
     "required": ["name", "description"]
   }
   ```

### Schema as entities

Schemas are stored as entities in the entity table with `category: "schema"` (not hardcoded).

**Implementation note:** Currently schemas are in-memory only - need to persist as entities.

### User-defined schemas

```bash
rem-db register-schema -d mydb users schema.json
rem-db list-schemas -d mydb
```

**Status:** ❌ `register-schema` command not implemented (auto-registration exists in upsert)

## Insert operations

### Single record insert

**Python API:**
```python
# Without embedding
db.insert("users", {"name": "Alice", "email": "alice@example.com"})

# With embedding
await db.insert_with_embedding("articles", {
    "name": "Rust Guide",
    "content": "Rust is a systems language..."
})
```

**CLI:** ❌ Not implemented (only batch upsert exists)

### Batch insert

**Python API:**
```python
ids = await db.batch_insert("articles", [
    {"name": "Article 1", "content": "..."},
    {"name": "Article 2", "content": "..."}
], key_field="name")
```

**CLI:**
```bash
rem-db upsert -d mydb articles --file data.jsonl --key-field name
```

**Status:** ✅ Implemented

## Replication

### Peer sync architecture

- **Mobile ↔ Desktop:** Direct peer-to-peer sync
- **Desktop ↔ Cloud:** Sync to Kubernetes cluster
- **Cluster nodes:** Internal replication

### Protocol

- gRPC-based replication
- Change log (WAL) propagation
- Conflict resolution via vector clocks

**Status:** ❌ Not implemented (Phase 4)

## Background indexing

### HNSW index building

- Runs on background thread
- Incrementally updates as entities are inserted
- Configurable index parameters (M, ef_construction)

**Status:** ⚠️ Partially implemented (HNSW index exists but background building not active)

## Storage architecture

### RocksDB column families

1. **CF_ENTITIES:** Entity storage
   - Key: `entity:{tenant}:{entity_id}`
   - Value: JSON entity with properties

2. **CF_EDGES:** Graph relationships (future)
   - Key: `edge:{tenant}:{src_id}:{dst_id}:{type}`
   - Value: Edge properties

3. **CF_INDEXES:** Secondary indexes
   - Key: `index:resource:{tenant}:{hash}`
   - Value: Resource ID

4. **CF_SCHEMAS:** Schema registry (future)
   - Key: `schema:{tenant}:{schema_name}`
   - Value: JSON Schema definition

**Status:** ✅ Column families created, some not yet used

## CLI command reference

### Currently implemented

| Command | Status | Description |
|---------|--------|-------------|
| `init <name>` | ✅ | Initialize database with default schemas |
| `list` | ✅ | List all registered databases |
| `schemas -d <db>` | ✅ | List schemas in database |
| `query -d <db> <sql>` | ⚠️ | Execute SQL query (parser not integrated) |
| `search -d <db> <query>` | ✅ | Natural language semantic search |
| `export -d <db> <table> --output <file>` | ⚠️ | Export to JSON (Parquet pending) |
| `upsert -d <db> <table> --file <jsonl>` | ✅ | Batch insert from JSONL |

### Missing commands

| Command | Priority | Description |
|---------|----------|-------------|
| `lookup -d <db> <id>` | HIGH | Lookup entity by ID or key |
| `insert -d <db> <table> <json>` | MEDIUM | Single record insert |
| `register-schema -d <db> <name> <file>` | MEDIUM | Register JSON schema |
| `delete -d <db> <id>` | LOW | Delete entity |
| `update -d <db> <id> <json>` | LOW | Update entity |
| `replicate -d <db> --to <url>` | LOW | Replicate to peer |

## Implementation gaps

### High priority

1. **Entity lookup command:**
   ```bash
   rem-db lookup -d mydb <entity-id>
   rem-db lookup -d mydb --name "Alice"
   rem-db lookup -d mydb --uri "docs/readme.md"
   ```

2. **Schema persistence:**
   - Store schemas as entities with `category: "schema"`
   - Load schemas on database open
   - Enable schema versioning

3. **SQL query execution:**
   - Integrate sqlparser-rs
   - Implement single-table SELECT with WHERE
   - Support basic predicates (=, !=, >, <, LIKE)

### Medium priority

4. **Parquet export:**
   - Use arrow-rs for Parquet encoding
   - Convert entities to Arrow schema
   - Stream to Parquet file

5. **Background HNSW indexing:**
   - Worker thread for index updates
   - Incremental index building
   - Index persistence to RocksDB

6. **Single record insert CLI:**
   ```bash
   rem-db insert -d mydb users '{"name": "Alice", "email": "alice@example.com"}'
   ```

### Low priority

7. **Replication protocol:**
   - gRPC server/client
   - WAL propagation
   - Conflict resolution

8. **Delete/Update commands:**
   ```bash
   rem-db delete -d mydb <entity-id>
   rem-db update -d mydb <entity-id> '{"email": "newemail@example.com"}'
   ```

## Design principles

1. **Simple API:** Natural language search emphasized over complex SQL
2. **AI-first:** Embeddings and vector search as first-class features
3. **Schema-driven:** JSON Schema validation (like Pydantic)
4. **Deterministic IDs:** Hash-based IDs enable idempotent operations
5. **Peer sync:** Mobile-first architecture with replication
6. **Single table queries:** Intentionally limited SQL to keep it simple
7. **Background indexing:** Don't block inserts on index updates

## Example workflows

### Workflow 1: Document ingestion

```bash
# Init database
rem-db init docs-db

# Prepare chunks
cat > chunks.jsonl <<EOF
{"uri": "readme.md", "chunk_ordinal": 0, "content": "Introduction to REM"}
{"uri": "readme.md", "chunk_ordinal": 1, "content": "Installation guide"}
{"uri": "api.md", "chunk_ordinal": 0, "content": "API reference"}
EOF

# Batch insert (uri takes precedence)
rem-db upsert -d docs-db resources --file chunks.jsonl

# Search
rem-db search -d docs-db "how to install" --min-score 0.3
```

### Workflow 2: User management

```bash
# Init database
rem-db init users-db

# Prepare users
cat > users.jsonl <<EOF
{"name": "Alice", "email": "alice@example.com", "role": "engineer"}
{"name": "Bob", "email": "bob@example.com", "role": "designer"}
EOF

# Batch insert (name takes precedence)
rem-db upsert -d users-db users --file users.jsonl

# Lookup user (PLANNED)
rem-db lookup -d users-db --name "Alice"
```

### Workflow 3: Time-based events

```bash
# Init database
rem-db init events-db

# Prepare moments
cat > events.jsonl <<EOF
{"time_period": "2025-01-15T10:00:00Z", "classification": "meeting", "content": "Standup notes"}
{"time_period": "2025-01-15T14:00:00Z", "classification": "deployment", "content": "v1.2.0 released"}
EOF

# Batch insert
rem-db upsert -d events-db moments --file events.jsonl

# Query (PLANNED)
rem-db query -d events-db "SELECT * FROM moments WHERE classification = 'meeting'"
```

## Technical notes

### Why single-table SQL only?

- **Simplicity:** Avoid complex query planning and optimization
- **AI focus:** Natural language search is the primary interface
- **Performance:** Single table scans are predictable and fast
- **Schema flexibility:** JSON properties handle nested data

### Why hash-based IDs?

- **Idempotency:** Re-importing same data updates existing entities
- **Deduplication:** Same URI/key/name never creates duplicates
- **Determinism:** Useful for testing and debugging
- **Replication:** Conflict resolution via content hash

### Why no aggregates?

- **Keep it simple:** Aggregates complicate query planning
- **Export instead:** Use Parquet export + external tools (DuckDB, pandas)
- **Focus on retrieval:** REM is for memory recall, not analytics

### Why JSONL for batch insert?

- **Line-oriented:** Easy to stream and parse
- **Human-readable:** Easy to create and inspect
- **Standard format:** Works with jq, grep, sed
- **Append-only:** Can concatenate files easily
