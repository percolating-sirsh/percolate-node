# Iterated Retrieval with Staged Queries

## Overview

Staged iterated retrieval uses the default LLM to construct database queries progressively, refining search strategy based on results. The system uses registered schemas to build accurate queries and provides confidence scoring for transparency.

## How It Works

### 1. Schema-Aware Query Construction

The LLM loads registered entity schemas to understand:
- Available fields and types
- Field descriptions (for semantic matching)
- Indexed fields (for efficient queries)

This prevents hallucination and enables accurate field-based queries.

### 2. Query Response Format

LLM returns structured output with confidence scoring:

```json
{
  "query_type": "sql | vector | hybrid",
  "query": "SELECT * FROM articles WHERE category = 'tutorial'",
  "confidence": 0.85,
  "explanation": "Low confidence reason (only if < 0.6)",
  "next_steps": ["Broader search if no results", "Try semantic similarity"]
}
```

**Confidence levels:**
- `1.0`: Exact ID lookup
- `0.8-0.95`: Clear field-based query
- `0.6-0.8`: Semantic/vector search
- `< 0.6`: Ambiguous (explanation required)

### 3. Staged Execution

**Stage 1**: Execute primary query
- If results found → return immediately
- If no results → proceed to stage 2

**Stage 2**: Execute fallback query (broader)
- Relax filters or expand search scope
- If results found → return with stage metadata
- If no results → proceed to stage 3 (if max_stages > 2)

**Stage N**: Final fallback
- Most generic query (e.g., vector search without filters)
- Always returns results (may be low relevance)

### 4. Query Type Selection

**Entity lookup** (schema-agnostic key/name search):
```bash
# When user provides identifiers without context
rem ask "111213"           # Could be order_id, ticket_id, employee_id
rem ask "ABS-234"          # Could be ticket, project code, product SKU
rem ask "bob"              # Could be username, employee name, team name

# System performs global key lookup across all schemas
# → Batch key lookup in key_index CF (fast O(log n) per schema)
# → Returns matches with entity_type metadata
```

**Use entity lookup when:**
- User provides bare identifier (number, code, name)
- Schema is unknown or ambiguous
- Query pattern matches: `^\w+[-_]?\w+$` (identifier-like)

**Schema hint improves accuracy:**
```bash
rem ask "bob" --schema employees
# → SELECT * FROM employees WHERE name = 'bob' OR key = 'bob'

rem ask "ABS-234" --schema tickets
# → SELECT * FROM tickets WHERE id = 'ABS-234' OR key = 'ABS-234'
```

**SQL queries** (structured filtering):
```bash
rem ask "companies with name Acme"    # Clear schema intent
# → SELECT * FROM companies WHERE name = 'Acme'

rem ask "articles with category tutorial"
# → SELECT * FROM articles WHERE category = 'tutorial'
```

**Vector search** (semantic similarity):
```bash
rem ask "tutorials about authentication"
# → SELECT * FROM articles WHERE embedding.cosine("authentication tutorials") LIMIT 10
```

**Hybrid queries** (semantic + filters):
```bash
rem ask "Python tutorials from last month"
# → SELECT * FROM articles
#    WHERE embedding.cosine("Python tutorials")
#    AND created_at > '2025-09-24'
#    LIMIT 10
```

## Example: Multi-Stage Retrieval

```bash
# User query (ambiguous)
rem ask "recent ML resources" --max-stages 3

# Stage 1: Specific query (confidence: 0.65)
# Query: SELECT * FROM resources
#        WHERE embedding.cosine("machine learning")
#        AND created_at > '2025-10-01'
# Results: 0 (no recent ML resources)

# Stage 2: Relaxed time constraint (confidence: 0.75)
# Query: SELECT * FROM resources
#        WHERE embedding.cosine("machine learning")
#        LIMIT 20
# Results: 15 (found ML resources, older dates)
# → Return these results + metadata showing 2 stages used
```

## Schema Discovery Strategies

When schema is unknown or ambiguous, the system uses one of these strategies:

### 1. Schema Hint (Preferred)

Explicitly specify schema with `--schema` flag:
```bash
rem ask "bob" --schema employees
rem ask "recent updates" --schema projects
```

**Fast**: O(log n) lookup in single schema.

### 2. Brute Force (Small Schema Count)

If ≤ 5-10 registered schemas and no hint provided:
```bash
rem ask "111213"  # No schema hint
# → Batch key lookup across all schemas (5-10 parallel lookups)
# → Returns first match with entity_type
```

**Acceptable**: O(log n) per schema, parallelized.

### 3. Semantic Schema Search (Many Schemas)

If > 10 registered schemas and no hint:
```bash
rem ask "product information"
# → Semantic search over embedded schema descriptions
# → Find top 3 most relevant schemas
# → Execute query against those schemas only
```

**Why embed schema descriptions:**
- Schema descriptions are embedded when registered
- LLM searches schema embeddings to find relevant schemas
- Reduces search space from 100+ schemas to top 3-5
- Essential for large databases with many entity types

**Example schema with embedded description:**
```json
{
  "title": "Product",
  "description": "E-commerce product catalog with SKU, pricing, inventory, and vendor information",
  "properties": {...}
}
```

When user asks "find product ABS-234", LLM:
1. Embeds query: "find product ABS-234"
2. Searches schema embeddings for similarity
3. Finds "Product" schema (high cosine similarity)
4. Executes lookup only in `products` table

**Configuration:**
```bash
# Brute force threshold (default: 10)
export P8_SCHEMA_BRUTE_FORCE_LIMIT=10

# Schema search top-k (default: 3)
export P8_SCHEMA_SEARCH_TOP_K=3
```

## Global Key Lookup Implementation

### Column Family Design (Rust)

Schema-agnostic entity lookup uses a dedicated `key_index` column family for reverse key→entity mapping:

**Key encoding:**
```rust
// src/storage/keys.rs
pub fn encode_key_index(key: &str, entity_id: Uuid) -> Vec<u8> {
    format!("key:{}:{}", key, entity_id).into_bytes()
}

// Storage layout in key_index CF:
// key:bob:550e8400-...           → {entity_type: "employees"}
// key:bob:7c3f8e10-...           → {entity_type: "users"}
// key:ABS-234:9a2b1c30-...       → {entity_type: "tickets"}
// key:111213:4f5e6d70-...        → {entity_type: "orders"}
```

**Why separate column family:**
- **Fast prefix scan**: `key:bob:*` finds all entities with key "bob"
- **No full table scan**: Avoids iterating through all entities
- **Cross-schema lookup**: Single CF spans all entity types
- **O(log n + k)**: Log n to find prefix, k results to return

**Batch lookup implementation:**
```rust
// src/index/keys.rs
pub fn lookup_key_batch(
    &self,
    keys: &[String],
) -> Result<Vec<(Uuid, String)>> {  // (entity_id, entity_type)
    let mut results = Vec::new();

    for key in keys {
        let prefix = format!("key:{}:", key);
        let iter = self.storage.prefix_iterator(CF_KEY_INDEX, prefix.as_bytes());

        for (k, v) in iter {
            let entity_id = decode_key_index_id(&k)?;
            let entity_type: String = serde_json::from_slice(&v)?;
            results.push((entity_id, entity_type));
        }
    }

    Ok(results)
}
```

**Lookup flow:**
1. User queries: `rem ask "bob"`
2. LLM detects identifier pattern → entity lookup query type
3. Rust performs prefix scan: `key:bob:*` in `key_index` CF
4. Returns all matches: `[(uuid1, "employees"), (uuid2, "users")]`
5. Fetch full entities from `entities` CF by UUIDs
6. Return results with schema metadata

**Performance:**
- **Single key lookup**: ~0.1ms (RocksDB prefix scan)
- **Batch lookup (10 keys)**: ~1ms (parallelized)
- **Memory overhead**: ~50 bytes per indexed key

### Deterministic Key Generation

Keys are automatically indexed based on priority:

| Priority | Field | Index Key | Example |
|----------|-------|-----------|---------|
| 1 | `uri` | `uri` value | `https://docs.python.org` |
| 2 | `json_schema_extra.key_field` | Custom field value | `email: "bob@co.com"` |
| 3 | `key` | `key` value | `"PROJECT-123"` |
| 4 | `name` | `name` value | `"Bob Smith"` |

**Example:**
```json
{
  "name": "Bob Smith",
  "email": "bob@company.com",
  "employee_id": "111213"
}
```

Schema config:
```json
{
  "json_schema_extra": {
    "key_field": "employee_id"  // Priority 2
  }
}
```

Indexed keys in `key_index` CF:
- `key:111213:550e8400-...` → `{entity_type: "employees"}`  (key_field)
- `key:Bob Smith:550e8400-...` → `{entity_type: "employees"}`  (name, fallback)

### Fuzzy Search (Future)

**Current limitation**: Exact key match only.

**Future enhancement**: Fuzzy/approximate matching for typos.

**Possible approaches:**

1. **Trigram indexing** (PostgreSQL pg_trgm style)
   - Break keys into 3-character substrings
   - Index: `"bob"` → `["bob", "ob ", "b  "]`
   - Pro: Handles typos, substring matches
   - Con: High storage overhead (3x-5x), slower writes
   - **State of art for RocksDB?** Not optimal - designed for SQL databases

2. **BK-Tree** (Levenshtein distance)
   - Tree structure for edit distance queries
   - Pro: Efficient typo tolerance (1-2 char edits)
   - Con: Complex implementation, memory overhead
   - Better for in-memory or small datasets

3. **Tantivy/Sonic** (full-text search engine)
   - External index alongside RocksDB
   - Pro: Production-ready fuzzy search
   - Con: Additional dependency, sync complexity
   - Best for large-scale fuzzy search needs

4. **SimHash/MinHash** (locality-sensitive hashing)
   - Hash similar strings to nearby values
   - Pro: Constant-time approximate lookup
   - Con: False positives, complex tuning
   - Good for deduplication use cases

**Recommendation for RocksDB:**
- **Small scale (<100K keys)**: BK-Tree in memory, lazy-loaded
- **Medium scale (100K-10M keys)**: Tantivy sidecar index
- **Large scale (>10M keys)**: Dedicated search service (Elasticsearch, Meilisearch)

**Trigram concerns:**
- Designed for SQL B-tree indexes (PostgreSQL, MySQL)
- RocksDB LSM-tree has different performance characteristics
- High write amplification (each insert → 3+ index entries)
- Better alternatives exist for embedded databases

**Current workaround:**
- Use semantic search over entity embeddings for fuzzy matching
- User query: `"find bob smith"` → vector search over name embeddings
- Leverages existing HNSW index, no additional storage

## CLI Usage

**Basic query** (single stage):
```bash
rem ask "show programming articles"
```

**With schema hint** (faster, more accurate):
```bash
rem ask "bob" --schema employees
rem ask "recent items" --schema orders
```

**Multi-stage retrieval** (up to 3 attempts):
```bash
rem ask "specific technical query" --max-stages 3
```

**Show query plan** (don't execute):
```bash
rem ask "Python resources" --plan
# Output:
# {
#   "confidence": 0.85,
#   "query": "SELECT * FROM resources WHERE embedding.cosine('Python') LIMIT 10",
#   "reasoning": "Semantic search for conceptual match",
#   "next_steps": ["Broaden to all programming if no results"]
# }
```

## Low Confidence Handling

When confidence < 0.6, LLM must provide explanation:

```json
{
  "query_type": "vector",
  "query": "SELECT * FROM articles WHERE embedding.cosine('topic') LIMIT 10",
  "confidence": 0.55,
  "explanation": "Query is ambiguous - 'topic' could refer to multiple concepts. Suggest clarifying: tutorial type? programming language? difficulty level?",
  "next_steps": [
    "Ask user to specify category",
    "Try broader semantic search",
    "Show available categories as options"
  ]
}
```

## Next Steps Format

Next steps are terse, actionable suggestions for subsequent queries:

**Good next steps:**
- "Broaden time window to 90 days"
- "Try semantic search instead of exact match"
- "Search related tables: tutorials, guides"
- "Relax category filter (all programming)"

**Bad next steps:**
- "Maybe try searching differently" (vague)
- "This query might not work" (not actionable)
- "Consider using a different approach" (unhelpful)

## Configuration

Set default LLM via environment:
```bash
export P8_DEFAULT_LLM=gpt-4-turbo-preview
export OPENAI_API_KEY=sk-...
```

Override in query:
```bash
rem ask "query" --model gpt-3.5-turbo  # Faster, cheaper
rem ask "query" --model gpt-4          # More accurate
```

## Performance

- **LLM call**: 500-2000ms (depends on model)
- **Query execution**: 1-100ms (depends on type)
- **Total latency**: ~1-3 seconds typical
- **Cost**: $0.001-0.01 per query (model dependent)

**Optimization:**
- Use SQL directly for known queries (bypass LLM)
- Cache common query patterns
- Choose faster models for simple queries
- Batch similar requests

## Response Metadata

Results include retrieval metadata:

```json
{
  "results": [...],
  "query": "SELECT ...",
  "query_type": "vector",
  "confidence": 0.85,
  "stages": 2,
  "stage_results": [0, 15],
  "total_time_ms": 1250
}
```

This transparency helps users understand:
- Why specific results were returned
- How many attempts were needed
- Query confidence and reasoning
