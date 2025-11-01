# Query engine documentation

This folder contains all documentation related to the REM query engine, including natural language query planning, SQL dialect, search capabilities, and LLM integration.

## Quick start

**New to query planning?** Start here:

1. **[QUERY_LLM_QUICKSTART.md](QUERY_LLM_QUICKSTART.md)** - Configure Claude and Cerebras for fast query planning
2. **[sql-dialect.md](sql-dialect.md)** - Learn the REM SQL query syntax
3. **[query-translation-architecture.md](query-translation-architecture.md)** - Understand how natural language queries work

## Documentation overview

### Configuration and setup

**[QUERY_LLM_QUICKSTART.md](QUERY_LLM_QUICKSTART.md)**
- Quick setup guide for Python and Rust configurations
- Copy-paste environment variable examples
- Troubleshooting common errors
- Link to full configuration details below

### Architecture and design

**[query-translation-architecture.md](query-translation-architecture.md)**
- Natural language → SQL translation pipeline
- LLM-based query planner design
- Query plan structure (query_type, confidence, primary_query, fallback_queries)
- Execution modes (direct, iterative, hybrid)
- Multi-stage query execution

**[iterated-retrieval.md](iterated-retrieval.md)**
- Multi-stage query execution strategy
- Pagination and result refinement
- Context-aware query expansion
- Agent-driven iterative retrieval patterns

### Query language

**[sql-dialect.md](sql-dialect.md)**
- REM SQL syntax reference
- Supported query types (lookup, search, traverse, hybrid)
- Vector search queries (`SEARCH ... TOP K`)
- Graph traversal queries (`TRAVERSE ... DEPTH`)
- Time-range queries (`WHERE moment BETWEEN`)
- Schema-specific queries (`FROM articles WHERE category = "tech"`)

### Search capabilities

**[advanced-search.md](advanced-search.md)**
- HNSW vector search (sub-2ms latency)
- Tiered memory architecture (hot HNSW + cold DiskANN)
- 89% memory reduction (1.5GB → 175MB)
- BM25 hybrid search (planned)
- Performance benchmarks and optimization strategies

## Implementation reference

### Core components

| Component | File | Description |
|-----------|------|-------------|
| **Query planner** | `src/llm/query_builder.rs` | LLM client for query planning (Claude, Cerebras) |
| **Edge builder** | `src/llm/edge_builder.rs` | LLM-based relationship extraction (document-level) |
| **SQL parser** | `src/query/parser.rs` | REM SQL parser |
| **Query executor** | `src/query/executor.rs` | Query execution engine |
| **HNSW index** | `src/index/hnsw.rs` | Vector search index |
| **DiskANN index** | `src/index/diskann.rs` | Cold storage vector index |
| **Python bindings** | `src/bindings/database.rs` | PyO3 bindings for `Database.plan_query()` and `Database.extract_edges()` |

### Environment variables

**IMPORTANT:** Percolate has two separate LLM configuration systems:

#### Rust Library (`percolate-rocks`)

Used by: `Database.plan_query()` method, CLI commands

```bash
export P8_DEFAULT_LLM=cerebras:qwen-3-32b
export CEREBRAS_API_KEY=csk-...
export ANTHROPIC_API_KEY=sk-ant-...
```

#### Python Package (`percolate`)

Used by: Agent orchestration, MCP tools, Python-based query planning

```bash
export PERCOLATE_DEFAULT_MODEL=anthropic:claude-sonnet-4-5-20250929
export PERCOLATE_QUERY_MODEL=cerebras:qwen-3-32b  # Override for queries
export PERCOLATE_CEREBRAS_API_KEY=csk-...
export PERCOLATE_ANTHROPIC_API_KEY=sk-ant-...
```

| Use Case | System | Variables |
|----------|--------|-----------|
| Python agents (Pydantic AI) | Python | `PERCOLATE_*` |
| Rust `Database.plan_query()` | Rust | `P8_DEFAULT_LLM` |
| CLI: `rem ask` | Rust | `P8_DEFAULT_LLM` |
| MCP tools | Python | `PERCOLATE_*` |

**Note:** Most users will set **both** for full functionality.

## Common patterns

### Fast query planning (recommended)

```bash
# Use Cerebras for fast query planning (500ms)
export P8_DEFAULT_LLM=cerebras:qwen-3-32b
export CEREBRAS_API_KEY=csk-your-key

# Use Claude for high-quality agents (1800ms)
export PERCOLATE_DEFAULT_MODEL=anthropic:claude-sonnet-4-5-20250929
export ANTHROPIC_API_KEY=sk-ant-your-key
```

### Natural language queries

```python
from percolate_rocks import Database

db = Database()

# Simple identifier lookup (no LLM, <1ms)
plan = db.plan_query("123456", None)

# Semantic search (requires LLM, ~500ms with Cerebras)
plan = db.plan_query("recent articles about AI", "articles")

# Complex query with filters
plan = db.plan_query(
    "show me technical articles from last week about Rust",
    "articles"
)
```

### Direct SQL queries

```python
# Vector search
results = db.query("""
    SEARCH articles
    FOR "machine learning performance"
    TOP 10
""")

# Graph traversal
results = db.query("""
    TRAVERSE FROM entity:alice
    DEPTH 3
    WHERE relationship = "knows"
""")

# Hybrid query
results = db.query("""
    SELECT * FROM articles
    WHERE category = "tech"
    AND moment BETWEEN "2025-10-01" AND "2025-10-31"
    SEARCH FOR "optimization"
    TOP 5
""")
```

### REM edge extraction

**Document-level relationship extraction** builds the knowledge graph by identifying relationships between documents.

```python
from percolate_rocks import Database

db = Database()

# Extract edges from document content
edge_plan = db.extract_edges(
    content="This architecture was influenced by Design Doc 001...",
    context="architecture/rem-database.md"
)

# Returns: EdgePlan with edges and summary
edges = edge_plan["edges"]  # List of edge specifications
summary = edge_plan["summary"]  # Statistics
```

**Key architecture principles:**

1. **Edges extracted at document level** - Not per-chunk
   - One LLM call per document (cost-efficient)
   - Edges represent document-to-document relationships
   - All chunks inherit the same edges

2. **Relationship types** (11 types recognized):
   - `references` - Document references another document
   - `authored_by` - Created by person/team
   - `depends_on` - Technical dependency
   - `implements` - Implements specification/pattern
   - `extends` - Extends another concept
   - `supersedes` - Replaces older document
   - `related_to` - General relationship
   - `part_of` - Component relationship
   - `mentions` - Brief reference
   - `cites` - Academic citation
   - `derived_from` - Derived work

3. **CLI usage**:
   ```bash
   # Extract edges during ingestion
   rem ingest docs/architecture.md --schema resources --rem

   # Post-process existing documents
   rem index --schema resources --limit 10
   ```

**Example output:**
```json
{
  "edges": [
    {
      "dst": "12345678-1234-5678-9abc-123456789001",
      "rel_type": "references",
      "properties": {
        "confidence": 0.95,
        "context": "Document references Design Doc 001..."
      },
      "created_at": "2025-11-01T10:00:00Z"
    }
  ],
  "summary": {
    "total_edges": 7,
    "relationship_types": ["references", "authored_by", "extends"],
    "avg_confidence": 0.92
  }
}
```

## Performance characteristics

| Operation | Latency | Requires LLM | Index used |
|-----------|---------|--------------|------------|
| Identifier lookup | <1ms | No | Key index |
| SQL query (indexed) | <10ms | No | RocksDB CF index |
| Vector search (HNSW) | <2ms | No | HNSW index |
| Vector search (DiskANN) | ~5ms | No | DiskANN index |
| NL → SQL (Cerebras) | ~500ms | Yes | N/A |
| NL → SQL (Claude) | ~1800ms | Yes | N/A |
| Edge extraction (document) | ~2-5s | Yes | N/A |

## Cerebras Strict JSON Schema Requirements

Cerebras requires **strict JSON schema mode** with specific constraints:

1. **`additionalProperties` MUST be false everywhere**
   ```json
   {"type": "object", "properties": {}, "additionalProperties": false}
   ```

2. **Union types MUST use `anyOf`, not array syntax**
   ```json
   // ✅ Correct
   {"anyOf": [{"type": "string"}, {"type": "null"}]}

   // ❌ Wrong
   {"type": ["string", "null"]}
   ```

3. **NO numeric constraints** (no `minimum`/`maximum`)
   ```json
   {"type": "number"}  // ✅ Correct
   ```

4. **All objects MUST define `properties` or `anyOf`**
   ```json
   {"type": "object", "properties": {}, "additionalProperties": false}  // ✅ Minimum valid
   ```

**Implementation:** See `../../src/llm/query_builder.rs` for the strict schema implementation.

**Result:** 100% schema adherence with both Claude and Cerebras, enabling fast query planning (~500ms).

## Testing

See [test_rust_query_planner.py](../../../percolate/tests/integration/test_rust_query_planner.py) for comprehensive integration tests covering:
- Identifier pattern detection
- Semantic search with LLM
- Claude-specific tests
- Cerebras strict JSON schema validation
- Performance benchmarks

## Related documentation

- [REM Memory Architecture](../../../docs/02-rem-memory.md) - Overall memory model
- [Percolate-rocks README](../../README.md) - Package overview
- [Main Documentation Index](../../../DOCS.md) - Full project navigation
- [Archived Documentation](./../../../.archive-docs/README.md) - Historical docs

## Recent changes

**November 2025:**
- ✅ Implemented REM edge extraction (document-level relationship extraction)
  - Rust-native EdgeBuilder in `src/llm/edge_builder.rs`
  - Edges extracted from full documents before chunking
  - 11 relationship types (references, authored_by, depends_on, etc.)
  - CLI commands: `rem ingest --rem` and `rem index`
- ✅ Improved text chunking (500-2000 chars per chunk, not per-paragraph)
- ✅ Implemented Cerebras strict JSON schema support
- ✅ Achieved 100% schema adherence with Claude and Cerebras
- ✅ Documented Cerebras schema requirements (no min/max, anyOf for unions, additionalProperties: false)
- ✅ Created proper pytest integration tests
- ✅ Organized all query-engine docs under this folder
