# REM SQL Dialect

REM Database uses an extended SQL dialect that unifies key-value lookups, graph traversal, semantic search, and traditional SQL queries.

## Table of Contents

- [Key Lookups](#key-lookups)
- [Graph Traversal](#graph-traversal)
- [Semantic Search](#semantic-search)
- [Standard SQL](#standard-sql)
- [Hybrid Queries](#hybrid-queries)
- [System Fields](#system-fields)
- [Query Execution Flow](#query-execution-flow)

## Key Lookups

Global key-based entity retrieval using the key index.

### Syntax

```sql
-- Simple LOOKUP syntax (recommended)
LOOKUP 'key1', 'key2', 'key3'

-- SQL-style syntax
SELECT * FROM kv WHERE key IN ('key1', 'key2')
```

### Use Cases

- **Identifier lookups**: `LOOKUP 'user-123'`
- **Multi-entity fetch**: `LOOKUP 'TAP-1234', 'TAP-5678'`
- **Name-based lookup**: `LOOKUP 'alice', 'bob'`

### Examples

```sql
-- Single entity by ID
LOOKUP 'user-550e8400'

-- Multiple entities
LOOKUP 'alice', 'bob', 'charlie'

-- Jira ticket lookup
LOOKUP 'TAP-1234'

-- SQL-style (equivalent)
SELECT * FROM kv WHERE key IN ('alice', 'bob')
```

### Returns

All matching entities with:
- System fields: `id`, `entity_type`, `created_at`, `modified_at`, `deleted_at`
- User properties: All fields from entity schema
- Edges: (optional) Relationship references

### Performance

- **O(log n + k)** where k = number of keys
- Uses key index column family (no table scan)
- Optimized for 1-100 key lookups per query

## Graph Traversal

Navigate relationships between entities using edges.

### Syntax

```sql
TRAVERSE FROM '<uuid>' DEPTH <n> DIRECTION <dir> [TYPE '<relationship>']
```

**Parameters:**
- `FROM '<uuid>'` - Starting entity UUID (required)
- `DEPTH <n>` - Traversal depth 1-10 (required)
- `DIRECTION <dir>` - `out` | `in` | `both` (required)
- `TYPE '<relationship>'` - Relationship filter (optional)

### Use Cases

- **Find connections**: Who authored this document?
- **Relationship mapping**: All entities linked to user X
- **Graph exploration**: Multi-hop traversal

### Examples

```sql
-- Find all outgoing edges from entity (1 hop)
TRAVERSE FROM '550e8400-e29b-41d4-a716-446655440000' DEPTH 1 DIRECTION out

-- Find who authored a document (reverse lookup)
TRAVERSE FROM 'doc-uuid-123' DEPTH 1 DIRECTION in TYPE 'authored'

-- Multi-hop exploration (3 levels deep)
TRAVERSE FROM 'user-alice' DEPTH 3 DIRECTION both

-- Find all documents authored by user
TRAVERSE FROM 'user-uuid' DEPTH 1 DIRECTION out TYPE 'authored'

-- Explore knowledge graph (bidirectional)
TRAVERSE FROM 'concept-rust' DEPTH 2 DIRECTION both TYPE 'related_to'

-- Find collaborators (2-hop network)
TRAVERSE FROM 'user-alice' DEPTH 2 DIRECTION out TYPE 'collaborated_with'
```

### Returns

List of entities found during traversal with:
- Entity data (all fields)
- Edge metadata (relationship type, properties)
- Traversal path information

### Performance

- **O(depth × fanout)** complexity
- Uses bidirectional edge column families
- Limit depth to 1-3 for performance
- Consider caching for frequently traversed paths

## Semantic Search

Vector similarity search using embeddings.

### Syntax

```sql
SEARCH '<query text>' IN <table> [WHERE <conditions>] [LIMIT <n>]
```

**Parameters:**
- `'<query text>'` - Natural language search query (required)
- `IN <table>` - Target schema/table name (required)
- `WHERE <conditions>` - SQL filters for hybrid search (optional)
- `LIMIT <n>` - Maximum results (default: 10)

### Use Cases

- **Conceptual search**: Find documents about "Rust concurrency"
- **Hybrid retrieval**: Semantic + metadata filters
- **Question answering**: Search knowledge base

### Examples

```sql
-- Basic semantic search
SEARCH 'rust programming' IN articles

-- Limited results
SEARCH 'machine learning' IN papers LIMIT 5

-- Hybrid search (semantic + filter)
SEARCH 'Python tutorials' IN articles WHERE category='tutorial'

-- Time-based hybrid search
SEARCH 'async programming' IN articles WHERE created_at > '2024-01-01' LIMIT 10

-- Multi-field filter
SEARCH 'database design' IN articles WHERE category='engineering' AND status='published'

-- Fuzzy concept matching
SEARCH 'high performance computing' IN papers

-- Question-based search
SEARCH 'How do I handle errors in Rust?' IN documentation
```

### Returns

Ranked list of entities with:
- Similarity scores (0.0 - 1.0)
- Entity data
- Matching metadata

### Performance

- **~5ms for 1M documents** (HNSW index)
- Embedding generation: ~50ms (OpenAI) or ~100ms (local)
- WHERE filters applied post-retrieval
- Use LIMIT to control latency

## Standard SQL

Full SQL SELECT support (no joins).

### Supported Features

- **SELECT**: `*` or field list
- **FROM**: Single table
- **WHERE**: Comparison operators (`=`, `>`, `<`, `>=`, `<=`, `!=`)
- **WHERE**: Logical operators (`AND`, `OR`, `NOT`)
- **ORDER BY**: Field with `ASC`/`DESC`
- **LIMIT**: Result count
- **Aggregates**: `COUNT(*)`, `SUM(field)`, `AVG(field)`, `MIN(field)`, `MAX(field)`

### Not Supported

- **JOIN** - Use graph traversal instead
- **GROUP BY** - Use aggregates with WHERE
- **HAVING** - Apply filters in WHERE
- **Subqueries** - Execute separately and combine

### Examples

```sql
-- Select all
SELECT * FROM users

-- Field selection
SELECT name, email FROM users

-- WHERE clause
SELECT * FROM users WHERE role = 'admin'

-- Comparisons
SELECT * FROM articles WHERE views > 1000

-- Logical operators
SELECT * FROM users WHERE role = 'admin' AND status = 'active'

-- Pattern matching (equality only)
SELECT * FROM articles WHERE category = 'rust'

-- ORDER BY
SELECT * FROM articles WHERE category = 'rust' ORDER BY created_at DESC

-- LIMIT
SELECT * FROM users WHERE status = 'active' LIMIT 10

-- ORDER BY + LIMIT (top 5)
SELECT * FROM articles ORDER BY views DESC LIMIT 5

-- Aggregates
SELECT COUNT(*) FROM users
SELECT AVG(age) FROM users WHERE status = 'active'
SELECT SUM(revenue) FROM orders WHERE status = 'completed'
SELECT MIN(created_at), MAX(created_at) FROM articles

-- Aggregate with filter
SELECT COUNT(*) FROM articles WHERE category = 'rust' AND status = 'published'
```

## Hybrid Queries

Combine semantic search with SQL filters for powerful retrieval.

### Pattern

```sql
SEARCH '<semantic query>' IN <table> WHERE <sql predicates> LIMIT <n>
```

### Strategy

1. **Semantic retrieval** - HNSW vector search
2. **Filter application** - SQL predicates on candidates
3. **Result ranking** - By similarity score

### Examples

```sql
-- Recent content about topic
SEARCH 'Rust async' IN articles
WHERE created_at > '2024-01-01'
LIMIT 10

-- Filtered by category
SEARCH 'machine learning' IN papers
WHERE category = 'research' AND status = 'published'

-- Multi-criteria
SEARCH 'database optimization' IN articles
WHERE author = 'alice' AND views > 100
ORDER BY created_at DESC
LIMIT 5

-- Time-bounded exploration
SEARCH 'cloud architecture' IN documents
WHERE year = 2024 AND type = 'whitepaper'

-- Quality-filtered search
SEARCH 'best practices' IN articles
WHERE rating >= 4.0
LIMIT 20
```

### Performance Tips

- **Narrow filters first** - Use WHERE to reduce candidate set
- **Index common filters** - Pre-index frequently queried fields
- **Adjust LIMIT** - Higher limits = slower queries
- **Cache popular queries** - Store results for frequent searches

## System Fields

Every entity has automatic system fields.

### Core System Fields

| Field | Type | Description | Set On | Mutable |
|-------|------|-------------|--------|---------|
| `id` | UUID | Entity identifier | Insert | No |
| `entity_type` | String | Schema name | Insert | No |
| `created_at` | DateTime | Creation timestamp | Insert | No |
| `modified_at` | DateTime | Last update | Insert/Update | Yes |
| `deleted_at` | DateTime? | Soft delete timestamp | Delete | Yes |
| `edges` | Array[String] | Edge references | Insert | Yes |

### Querying System Fields

```sql
-- Recent entities
SELECT * FROM articles WHERE created_at > '2024-01-01'

-- Recently updated
SELECT * FROM users WHERE modified_at > '2024-10-01'

-- Exclude soft-deleted
SELECT * FROM articles WHERE deleted_at IS NULL

-- Specific entity type
SELECT * FROM kv WHERE entity_type = 'users'

-- Entities with relationships
SELECT * FROM articles WHERE edges IS NOT EMPTY
```

### Embedding Fields (Optional)

If schema has `embedding_fields` configured:

| Field | Type | When Added |
|-------|------|------------|
| `embedding` | Array[f32] | When `embedding_fields` specified |
| `embedding_alt` | Array[f32] | When `P8_ALT_EMBEDDING` set |

## Query Execution Flow

### 1. Parse Query

```
Input: SQL string
  ↓
Detect query type: LOOKUP | TRAVERSE | SEARCH | SELECT
  ↓
Parse to structured AST
```

### 2. Execute Query

```
LOOKUP:
  key → key_index CF → entity UUIDs → entities CF → results

TRAVERSE:
  start UUID → edges CF (forward/reverse) → entities CF → results

SEARCH:
  text → embedding → HNSW index → entity UUIDs → entities CF → results
  (optional WHERE filter applied to results)

SELECT:
  table → scan entities CF → apply WHERE → ORDER BY → LIMIT → results
```

### 3. Return Results

All queries return JSON:
```json
{
  "results": [...],
  "query": "original query",
  "query_type": "Search",
  "execution_time_ms": 12,
  "count": 5
}
```

## Best Practices

### When to Use Each Query Type

| Use Case | Query Type | Example |
|----------|------------|---------|
| Known ID/key | LOOKUP | `LOOKUP 'user-123'` |
| Find relationships | TRAVERSE | `TRAVERSE FROM ... TYPE 'authored'` |
| Conceptual search | SEARCH | `SEARCH 'async programming' IN docs` |
| Exact field match | SELECT | `SELECT * FROM users WHERE email = 'alice@co.com'` |
| Complex filters | SELECT | `WHERE status = 'active' AND role = 'admin'` |
| Semantic + filters | SEARCH + WHERE | `SEARCH 'rust' IN articles WHERE year = 2024` |

### Performance Guidelines

- **LOOKUP**: Best for 1-100 keys (< 1ms)
- **TRAVERSE**: Keep depth ≤ 3 (exponential growth)
- **SEARCH**: ~5ms for 1M docs (HNSW), limit results
- **SELECT**: O(n) table scan, use WHERE to filter early

### Query Optimization

1. **Use specific queries** - LOOKUP vs SELECT for known IDs
2. **Limit traversal depth** - Keep TRAVERSE depth ≤ 3
3. **Index common filters** - Pre-index WHERE predicates
4. **Batch lookups** - Use LOOKUP with multiple keys vs repeated queries
5. **Cache results** - Store frequently accessed data

## Error Handling

### Common Errors

```sql
-- Missing required field
TRAVERSE FROM 'uuid' DEPTH 2
-- Error: Missing DIRECTION keyword

-- Invalid depth
TRAVERSE FROM 'uuid' DEPTH 15 DIRECTION out
-- Error: Depth must be 1-10

-- Unclosed quote
SEARCH 'rust programming IN articles
-- Error: Unclosed quote

-- Invalid operator
SELECT * FROM users WHERE age LIKE '%25%'
-- Error: LIKE not supported (use = for exact match)
```

### Validation Rules

- TRAVERSE depth: 1-10
- SEARCH LIMIT: 1-1000
- LOOKUP keys: 1-100 per query
- WHERE predicates: Max 10 conditions (use AND/OR)

## Examples by Use Case

### User Management

```sql
-- Find user by email
SELECT * FROM users WHERE email = 'alice@company.com'

-- Active admins
SELECT * FROM users WHERE role = 'admin' AND status = 'active'

-- Recent signups
SELECT * FROM users WHERE created_at > '2024-10-01' ORDER BY created_at DESC
```

### Content Discovery

```sql
-- Find articles about Rust
SEARCH 'rust programming' IN articles LIMIT 10

-- Recent tutorials
SEARCH 'beginner tutorials' IN articles
WHERE category = 'tutorial' AND created_at > '2024-01-01'

-- Popular content
SELECT * FROM articles WHERE views > 1000 ORDER BY views DESC LIMIT 20
```

### Relationship Navigation

```sql
-- Find document authors
TRAVERSE FROM 'doc-uuid' DEPTH 1 DIRECTION in TYPE 'authored'

-- User's network
TRAVERSE FROM 'user-uuid' DEPTH 2 DIRECTION both TYPE 'connected_to'

-- Related documents
TRAVERSE FROM 'doc-uuid' DEPTH 1 DIRECTION both TYPE 'references'
```

### Analytics

```sql
-- Total users
SELECT COUNT(*) FROM users

-- Active user count
SELECT COUNT(*) FROM users WHERE status = 'active'

-- Average article length
SELECT AVG(word_count) FROM articles WHERE status = 'published'

-- Date range stats
SELECT COUNT(*) FROM articles
WHERE created_at >= '2024-01-01' AND created_at < '2024-02-01'
```

## CLI Usage

```bash
# Key lookup
rem ask "user-123"

# Natural language (generates SEARCH)
rem ask "Find articles about Rust concurrency"

# Explicit SQL
rem query "SELECT * FROM users WHERE role = 'admin'"

# Graph traversal
rem ask "Who authored this document?" --context doc-uuid

# Show query plan (don't execute)
rem ask "Find Python tutorials" --plan
```

## Further Reading

- [Query Planner](../src/llm/planner.rs) - LLM-powered query generation
- [Extended Parser](../src/query/extended.rs) - Syntax implementation
- [SQL Executor](../src/query/executor.rs) - Query execution engine
- [HNSW Index](../src/index/hnsw.rs) - Vector search implementation
