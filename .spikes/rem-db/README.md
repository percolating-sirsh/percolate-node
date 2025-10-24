# REM Database - Resources, Entities, Moments

Fast, embedded RocksDB-based database implementing the REM (Resources-Entities-Moments) memory model with automatic chunking, embeddings, and natural language query interface.

## Overview

REM Database is a **schema-driven entity store** with semantic search capabilities. It combines:
- **RocksDB** for fast key-value storage
- **HNSW vector index** for semantic similarity search
- **Pydantic models** as JSON Schema-based table definitions
- **Natural language queries** powered by LLM (GPT-4)
- **Staged iterative queries** combining SQL, vector, and graph operations

**Why Python first?** Rapid iteration on API design before committing to Rust implementation.

## REM Model Explained

### Resources (Chunked Knowledge)
- **Automatically chunked** embedded documents using semantic chunking
- Each chunk stored as a separate resource with embeddings
- Transparent to users - insert a document, get searchable chunks
- **TODO**: Add Document entity that references its chunks

### Entities (Structured Data)
- Pydantic models registered as "tables" via JSON Schema
- All data stored as entities with `type=table_name`
- Document headers created when data is inserted
- Properties stored as flexible JSON with schema validation

### Moments (Temporal Classification)
- **TODO**: Time-based indexing and classification
- Temporal queries and historical snapshots

## Features Checklist

### ✅ Core Storage & Schema

- [x] **RocksDB backend** - Fast embedded key-value store
- [x] **Tenant isolation** - Separate databases per tenant
- [x] **Pydantic models as schemas** - Type-safe table definitions
- [x] **JSON Schema registry** - Register models with metadata
- [x] **Schema categories** - System, agents, public, user namespaces
- [x] **Automatic indexing** - Secondary indexes on specified fields
- [x] **Soft deletes** - Preserve data with `deleted_at` timestamps
- [x] **System fields** - id, created_at, modified_at, deleted_at, edges

### ✅ Embeddings & Vector Search

- [x] **Dual embedding support** - Default + alternative embeddings side-by-side
- [x] **Multiple providers** - Sentence-transformers, OpenAI, Cohere
- [x] **Provider registry** - Central config for dimensions, metrics
- [x] **Automatic embedding** - Generate on insert for content/description fields
- [x] **HNSW vector index** - Fast similarity search with hnswlib
- [x] **Background worker** - Async embedding generation and index saves
- [x] **Cosine similarity** - For sentence-transformers models
- [x] **Inner product** - For normalized embeddings (OpenAI)
- [x] **Embedding normalization** - Utils for consistent distance metrics

### ✅ Query Interface

#### SQL Queries
- [x] **SQL SELECT syntax** - Standard SELECT field1, field2 FROM table
- [x] **WHERE predicates** - =, !=, >, <, >=, <=, IN, AND, OR
- [x] **Nested conditions** - Parentheses for complex logic
- [x] **ORDER BY** - ASC/DESC sorting
- [x] **LIMIT/OFFSET** - Pagination support
- [x] **Field projection** - SELECT specific columns
- [x] **Multiline queries** - Support for formatted SQL
- [x] **Semantic search in SQL** - `WHERE embedding.cosine("query text")`
- [x] **Vector metrics in SQL** - cosine and inner_product functions
- [x] **Schema-aware routing** - Query any registered table/entity type
- [ ] **JOIN support** - Cross-table joins (future)
- [ ] **Aggregations** - COUNT, SUM, AVG, GROUP BY (future)

#### Vector Search
- [x] **Semantic similarity** - Natural language concept matching
- [x] **Score ranking** - Results sorted by similarity
- [x] **Top-k retrieval** - Configurable result limits
- [x] **Min score threshold** - Filter low-similarity results

#### Graph Queries
- [x] **Edge storage** - Directed relationships between entities
- [x] **Graph traversal** - BFS/DFS algorithms
- [x] **Relationship filtering** - Filter by edge type
- [x] **Direction control** - INCOMING, OUTGOING, BOTH
- [x] **Depth limits** - Prevent infinite traversal
- [x] **Cycle detection** - Avoid loops in graphs
- [x] **Path tracking** - Full path with entities and edges
- [x] **Multi-hop queries** - Find neighbors at exact depth
- [x] **Shortest path** - BFS-based path finding
- [x] **All paths** - DFS with backtracking

### ✅ Natural Language Interface

- [x] **LLM-powered query builder** - GPT-4 converts NL to queries
- [x] **Query type detection** - entity_lookup, sql, vector, hybrid, graph
- [x] **Entity lookup** - Global search when table unknown (IDs, codes, names)
- [x] **Confidence scoring** - 0.0-1.0 confidence with explanations
- [x] **Multi-stage retrieval** - Automatic fallback queries (up to 3 stages)
- [x] **Schema-aware prompts** - Load entity metadata for accurate queries
- [x] **CLI command** - `rem-db ask "natural language question"`
- [x] **Python API** - `db.query_natural_language(query, table)`
- [ ] **Query caching** - Cache LLM-generated queries (future)
- [ ] **Alternative LLM providers** - Claude, Llama, local models (future)

### ✅ Staged Iterative Queries

- [x] **Multi-stage patterns** - Combine SQL, vector, graph in sequence
- [x] **Stage result passing** - Output of one stage feeds next
- [x] **Semantic → Graph** - Find entities semantically, explore relationships
- [x] **SQL → Graph** - Filter structurally, traverse connections
- [x] **Hybrid queries** - Semantic + temporal/metadata filters
- [x] **Scenario framework** - Test cases for complex query patterns
- [x] **Performance tracking** - Measure latency per stage

### ✅ CLI Tools

- [x] **Database management**
  - `rem-db new <name>` - Create new database
  - `rem-db init` - Initialize with system schemas
  - `rem-db info` - Show database statistics
  - `rem-db schemas` - List registered schemas

- [x] **Data operations**
  - `rem-db insert <table> --data <json>` - Insert entity
  - `rem-db sql "SELECT ..."` - Execute SQL query
  - `rem-db query "semantic query"` - Vector similarity search
  - `rem-db ask "natural language"` - LLM-powered queries

- [x] **Ingestion** (TODO: expand)
  - File ingestion to Resources table
  - Automatic chunking with semantic chunker
  - Batch document processing

### 🚧 Replication & Sync

- [x] **WAL (Write-Ahead Log)** - Sequential operation log
- [x] **WAL sequence numbers** - Monotonic ordering
- [x] **WAL persistence** - Stored in RocksDB
- [x] **WAL API** - `get_wal_entries(start_seq, end_seq, limit)`
- [ ] **gRPC protocol** - Define replication RPC service
- [ ] **Peer discovery** - Find and connect to peer nodes
- [ ] **Bidirectional sync** - Two-way replication
- [ ] **Multi-peer sync** - 3+ node replication
- [ ] **Conflict resolution** - Handle concurrent writes
- [ ] **Incremental catchup** - Sync only new changes

### ✅ Built-in Schemas

**System Entities:**
- [x] **Resources** - Chunked documents with embeddings
- [x] **Agents** - Agent-let definitions with output schemas
- [x] **Sessions** - Conversation/interaction sessions
- [x] **Messages** - Chat messages with role and content

**Metadata:**
- System prompt from model docstring
- FQN, version, category from `model_config.json_schema_extra`
- MCP tool references
- Indexed fields for fast queries

### 📋 Planned Features

**Chunking & Embedding:**
- [ ] Semantic chunking with overlap
- [ ] Document → Chunks reference tracking
- [ ] Chunk metadata (position, parent doc)
- [ ] Multi-document ingestion pipeline

**Query Enhancements:**
- [ ] JOIN support across tables
- [ ] Aggregation functions (COUNT, SUM, AVG)
- [ ] Temporal queries (date ranges, time windows)
- [ ] Full-text search integration
- [ ] Query plan visualization

**Replication:**
- [ ] gRPC bidirectional streaming
- [ ] Leader election (Raft or similar)
- [ ] Snapshot + incremental sync
- [ ] Read replicas

**Storage:**
- [ ] Compression for large documents
- [ ] Blob storage for binary data
- [ ] Multi-tenant sharding

## Quick Start

### Installation

```bash
# Clone and install
cd .spikes/rem-db
uv sync --extra embeddings

# Set up OpenAI API key (for natural language queries)
export OPENAI_API_KEY='your-key-here'
```

### Create Database

```bash
# Create and initialize
rem-db new mydb
rem-db init --db mydb

# Check schemas
rem-db schemas --db mydb
```

### Insert Data

```bash
# Insert a resource
rem-db insert resources \
  --data '{"name": "Python Guide", "content": "Learn Python programming..."}' \
  --db mydb

# Insert custom entity
rem-db insert agents \
  --data '{"name": "Code Reviewer", "description": "Reviews code for bugs"}' \
  --db mydb
```

### Query Data

```bash
# SQL query
rem-db sql "SELECT name FROM resources WHERE category = 'tutorial'" --db mydb

# Vector search
rem-db query "tutorials about programming" --db mydb

# Natural language
rem-db ask "find resources about Python" --db mydb
rem-db ask "what is 12345?" --db mydb  # Entity lookup
```

### Python API

```python
from rem_db import REMDatabase

# Create database
db = REMDatabase(tenant_id="acme", path="./data")

# Insert with automatic embedding
resource_id = db.insert("resources", {
    "name": "Python Tutorial",
    "content": "Learn Python from scratch...",
    "category": "tutorial"
})

# SQL query
results = db.sql("SELECT * FROM resources WHERE category = 'tutorial'")

# Vector search
results = db.sql("""
    SELECT name FROM resources
    WHERE embedding.cosine('programming tutorials')
    LIMIT 10
""")

# Natural language query
result = db.query_natural_language(
    "find tutorials about Python created this month",
    table="resources"
)
print(f"Found {len(result['results'])} resources")
print(f"Confidence: {result['confidence']:.2f}")

# Entity lookup (global search)
entities = db.lookup_entity("DHL")  # Brand name
entities = db.lookup_entity("TAP-1234")  # Ticket code
entities = db.lookup_entity("12345")  # Numeric ID

# Graph traversal
from rem_db import Direction
edges = db.get_edges(entity_id, direction=Direction.INCOMING)
```

## Schema Registration

### Define Pydantic Model

```python
from pydantic import BaseModel, ConfigDict, Field

class Project(BaseModel):
    """A software project."""

    model_config = ConfigDict(
        json_schema_extra={
            "fully_qualified_name": "myapp.entities.Project",
            "version": "1.0.0",
            "category": "user",
            "indexed_fields": ["status", "priority"],  # Fast queries
        }
    )

    name: str = Field(description="Project name")
    description: str = Field(description="Project description")
    status: str = Field(description="Project status")
    priority: int = Field(ge=1, le=5, description="Priority (1-5)")
```

### Register and Use

```python
# Register schema
db.register_schema(
    name="projects",
    model=Project,
    description="Software project tracker"
)

# Insert data (automatic validation + embedding)
project_id = db.insert("projects", {
    "name": "REM Database",
    "description": "Fast embedded database with semantic search",
    "status": "active",
    "priority": 5
})

# Query with indexed field (fast)
results = db.sql("SELECT * FROM projects WHERE status = 'active'")

# Semantic search
results = db.sql("""
    SELECT name FROM projects
    WHERE embedding.cosine('database search performance')
    LIMIT 5
""")
```

## Natural Language Query Examples

### Entity Lookup (Unknown Table)

```bash
# Numeric ID - could be in any table
rem-db ask "what is 12345?"
# → Searches all entities by ID/name/alias

# Code pattern
rem-db ask "find TAP-1234"
# → Finds ticket/issue with that code

# Brand/entity name
rem-db ask "tell me about DHL"
# → Finds carrier entity or related resources
```

### SQL Queries (Known Table)

```bash
# Field-based filter
rem-db ask "show me resources with category tutorial"
# → SELECT * FROM resources WHERE category = 'tutorial'

# Temporal filter
rem-db ask "agents created in the last 7 days"
# → SELECT * FROM agents WHERE created_at >= '...'

# Multiple values
rem-db ask "resources where status is active or published"
# → SELECT * FROM resources WHERE status IN ('active', 'published')
```

### Vector Search (Semantic)

```bash
# Conceptual query
rem-db ask "find resources about authentication and security"
# → SELECT * FROM resources WHERE embedding.cosine('authentication security') LIMIT 10

# Paraphrase
rem-db ask "tutorials for beginners learning to code"
# → SELECT * FROM resources WHERE embedding.cosine('tutorials beginners code') LIMIT 10
```

### Hybrid Queries (Semantic + Filters)

```bash
# Semantic + temporal
rem-db ask "Python resources from the last month"
# → Vector search + created_at filter

# Semantic + category
rem-db ask "active agents about coding"
# → Vector search + status filter
```

### Graph Queries (Multi-Stage)

```bash
# Relationship exploration
rem-db ask "who has worked on authentication-related code?"
# Stage 1: Vector search for auth files
# Stage 2: Graph traversal via 'authored' edges
# → Returns: Alice, Bob, Charlie
```

## Architecture

### Storage Model

```
RocksDB Key Prefixes:
├── schema:{tenant}:{name}        → Schema definitions
├── entity:{tenant}:{uuid}        → All entities (resources, agents, etc.)
├── edge:{tenant}:{src}:{dst}     → Graph relationships
├── index:{field}:{tenant}:{val}  → Secondary indexes
├── wal:{tenant}:seq              → WAL sequence number
└── wal:{tenant}:entry:{seq}      → WAL entries for replication
```

### Entity Storage (Unified)

**All tables stored as entities:**
```python
entity:{tenant}:{uuid} → {
    "id": "uuid",
    "type": "resources",  # Table/schema name
    "name": "Python Guide",
    "properties": {
        "content": "...",
        "category": "tutorial",
        "metadata": {"status": "active"}
    },
    "embedding": [0.1, 0.2, ...],  # Default (384-dim)
    "embedding_alt": [0.3, 0.4, ...],  # Alternative (768-dim)
    "created_at": "2025-10-24T...",
    "modified_at": "2025-10-24T...",
    "deleted_at": null
}
```

### Query Routing

```
SQL: SELECT * FROM resources WHERE category = 'tutorial'
  ↓
1. Load schema for "resources"
2. Filter entities by type='resources'
3. Apply WHERE predicates
4. Project fields
  ↓
Results: [{name: "...", category: "tutorial"}, ...]
```

### Natural Language Flow

```
User: "find resources about Python"
  ↓
LLM Query Builder (with schema context)
  ↓
Generated Query: SELECT * FROM resources WHERE embedding.cosine('Python') LIMIT 10
  ↓
Vector Search (HNSW)
  ↓
Results: [{name: "Python Guide", _score: 0.87}, ...]
```

## Performance

### Benchmarks (Python Implementation)

- **Vector search**: ~1ms p50 (HNSW, 384-dim)
- **Indexed SQL queries**: ~50ms p50 (44% faster than full scan)
- **Entity lookup**: <1ms (direct key lookup)
- **Embedding generation**: ~10-50ms (sentence-transformers, CPU)
- **Natural language query**: 1-3s (includes LLM API call)

### Optimization

- **Indexes**: 2-5x faster for equality queries
- **Vector search**: Sub-millisecond with HNSW
- **Background workers**: Non-blocking embedding generation
- **Batch operations**: Amortize RocksDB write overhead

## Testing

```bash
# Unit tests
uv run pytest tests/unit/ -v

# Integration tests
uv run pytest tests/integration/ -v

# Problem set evaluation
uv run python examples/populate_problem_set_data.py
uv run python examples/test_entity_lookup.py
uv run python examples/test_sql_queries.py

# Benchmarks
uv run pytest tests/test_performance.py --benchmark-only
```

## Documentation

### Planning and testing
- **Problem Set**: `01 - problem-set.md` - 10 query evaluation questions
- **Replication**: `02 - replication.md` - Replication design and WAL
- **Staged Query Planning**: `scenarios.md` - Multi-modal query composition (Resources-Entities-Moments)
- **Aggregations & Joins**: `aggregations-joins.md` - SQL query planning with SQLGlot, DuckDB, DataFusion
- **DuckDB vs DataFusion**: `duckdb-datafusion-strategy.md` - Index storage strategy and Rust migration path
- **DataFusion Analysis**: `datafusion-analysis.md` - Does DataFusion solve our problems? Performance analysis & recommendations
- **Analytics Export**: `analytics-export-strategy.md` - **RECOMMENDED**: Cached snapshots → DuckDB for analytics (simple, pragmatic)
- **Changelog**: `changelog.md` - Feature history

### Implementation details
Implementation documentation is in source code module docstrings:
- **Embeddings**: `src/rem_db/embeddings.py` - Dual embedding system, provider registry
- **Natural Language**: `src/rem_db/llm_query_builder.py` - LLM query builder, multi-stage retrieval
- **Async Worker**: `src/rem_db/worker.py` - Background thread, task queue, index persistence
- **Database Core**: `src/rem_db/database.py` - Entity storage, SQL, vector search, graph
- **SQL Parser**: `src/rem_db/sql.py` - SQL syntax with semantic similarity functions

## Examples

```bash
examples/
├── populate_problem_set_data.py   # Test data generator
├── test_entity_lookup.py          # Entity lookup validation
├── test_sql_queries.py            # SQL query tests
├── graph_traversal.py             # Graph query examples
├── nested_agentlets.py            # Complex nested schemas
├── carrier_agentlet_pattern.py    # Agent-let pattern demo
└── experiment_1_software.py       # End-to-end scenario
```

## Roadmap

**Q1 2025:**
- [ ] gRPC replication protocol
- [ ] Semantic chunking pipeline
- [ ] Document → Chunks tracking
- [ ] SQL JOIN support

**Q2 2025:**
- [ ] Rust port of core engine
- [ ] Multi-peer replication
- [ ] Read replicas
- [ ] Compression & blob storage

**Q3 2025:**
- [ ] Moments implementation (temporal)
- [ ] Query plan visualization
- [ ] Alternative LLM providers
- [ ] Production deployment tooling

## Contributing

This is a spike/prototype for rapid iteration. Key principles:

1. **Everything is an entity** - No hardcoded table types
2. **Schema-driven** - Pydantic models define behavior
3. **Natural language first** - LLM understands schemas
4. **Performance matters** - Measure before optimizing
5. **Test with scenarios** - Real-world query patterns

## License

MIT
