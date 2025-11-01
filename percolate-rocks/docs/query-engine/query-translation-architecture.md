# Query Translation Architecture

**Status:** Design document - Implementation in Rust at `../../src/llm/query_builder.rs`

**Note:** This document describes the conceptual architecture. The actual implementation uses Rust with strict JSON schema validation. For configuration details, see [QUERY_LLM_QUICKSTART.md](QUERY_LLM_QUICKSTART.md).

## Design Principle

**The LLM generates WHAT to query (parameters), QueryBuilder generates HOW to query (syntax).**

This separation ensures:
- ✅ **Generic**: No hard-coded query generation in LLM
- ✅ **Extensible**: Add new query types without changing LLM
- ✅ **Type-safe**: Pydantic validates parameters
- ✅ **Testable**: Each layer tested independently

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│ User Query: "indoor plants resources"                          │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ LLM Query Planner (Pydantic AI)                                │
│ ─────────────────────────────────────────────────────────────── │
│ Generates structured output (QueryPlan):                        │
│                                                                  │
│ {                                                                │
│   "query_type": "search",                                        │
│   "confidence": 0.75,                                            │
│   "primary_query": {                                             │
│     "parameters": {                                              │
│       "query_text": "indoor plants",                             │
│       "schema": "resources",                                     │
│       "top_k": 10                                                │
│     }                                                             │
│   }                                                               │
│ }                                                                 │
│                                                                  │
│ LLM knows WHAT to query, not HOW (no SQL generation)            │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ QueryBuilder (Python)                                           │
│ ─────────────────────────────────────────────────────────────── │
│ Translates parameters → executable REM SQL:                     │
│                                                                  │
│ builder = QueryBuilder()                                         │
│ sql = builder.build(                                             │
│     QueryType.SEARCH,                                            │
│     {                                                             │
│         "query_text": "indoor plants",                           │
│         "schema": "resources",                                   │
│         "top_k": 10                                              │
│     }                                                             │
│ )                                                                 │
│                                                                  │
│ → "SEARCH 'indoor plants' IN resources LIMIT 10"                │
│                                                                  │
│ Pure functions, no LLM, no database access                      │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ REM Database (Rust)                                             │
│ ─────────────────────────────────────────────────────────────── │
│ Parses and executes REM SQL:                                    │
│                                                                  │
│ db.query("SEARCH 'indoor plants' IN resources LIMIT 10")        │
│                                                                  │
│ → [                                                               │
│     {"name": "Indoor Plant Care", ...},                          │
│     {"name": "Best Indoor Plants", ...},                         │
│     ...                                                           │
│   ]                                                               │
│                                                                  │
│ Fast, indexed, native execution                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Why This Design?

### Problem with Hard-Coding

**❌ Bad: LLM generates SQL strings directly**
```python
# LLM output:
{
  "query": "SEARCH 'indoor plants' IN resources LIMIT 10"
}
```

**Issues:**
- LLM can hallucinate invalid syntax
- Hard to validate correctness
- Can't extend without retraining LLM
- No type safety
- Harder to test

### Solution: Parameters + Translation

**✅ Good: LLM generates parameters, QueryBuilder generates SQL**
```python
# LLM output (structured):
{
  "query_type": "search",
  "parameters": {
    "query_text": "indoor plants",
    "schema": "resources",
    "top_k": 10
  }
}

# QueryBuilder translates:
builder.build(QueryType.SEARCH, parameters)
→ "SEARCH 'indoor plants' IN resources LIMIT 10"
```

**Benefits:**
- ✅ Type-safe (Pydantic validation)
- ✅ No SQL hallucination
- ✅ Easy to extend (add new query types)
- ✅ Testable at each layer
- ✅ LLM focuses on intent detection, not syntax

## Query Types and Parameters

### 1. LOOKUP (Key-based)

**LLM generates:**
```json
{
  "query_type": "lookup",
  "parameters": {
    "keys": ["alice", "bob"]
  }
}
```

**QueryBuilder translates:**
```sql
LOOKUP 'alice', 'bob'
```

**REM executes:**
- Key index scan: `key:alice:*`, `key:bob:*`
- Returns matching entities

### 2. SEARCH (Semantic)

**LLM generates:**
```json
{
  "query_type": "search",
  "parameters": {
    "query_text": "Python tutorials",
    "schema": "articles",
    "top_k": 5,
    "filters": {"category": "tutorial"}
  }
}
```

**QueryBuilder translates:**
```sql
SEARCH 'Python tutorials' IN articles
WHERE category = 'tutorial'
LIMIT 5
```

**REM executes:**
- Generate embedding for "Python tutorials"
- HNSW vector search in articles
- Apply SQL filters
- Return top 5

### 3. TRAVERSE (Graph)

**LLM generates:**
```json
{
  "query_type": "traverse",
  "parameters": {
    "start_key": "Alice",
    "depth": 1,
    "direction": "out",
    "edge_type": "colleague"
  }
}
```

**QueryBuilder translates:**
```sql
-- Stage 1: Find Alice
LOOKUP 'Alice'
-- Stage 2: Traverse colleagues
TRAVERSE FROM <alice_uuid> DEPTH 1 DIRECTION out TYPE 'colleague'
```

**REM executes:**
- Lookup Alice entity
- Scan edges CF: `src:<alice_uuid>:dst:*:type:colleague`
- Return connected entities

### 4. SQL (Filtered)

**LLM generates:**
```json
{
  "query_type": "sql",
  "parameters": {
    "schema": "articles",
    "fields": ["name", "views"],
    "where": {
      "category": "programming",
      "views": "> 1000"
    },
    "order_by": "views",
    "direction": "DESC",
    "limit": 10
  }
}
```

**QueryBuilder translates:**
```sql
SELECT name, views FROM articles
WHERE category = 'programming' AND views > 1000
ORDER BY views DESC
LIMIT 10
```

**REM executes:**
- Scan articles table
- Apply WHERE predicates
- Sort and limit

### 5. HYBRID (Semantic + SQL)

**LLM generates:**
```json
{
  "query_type": "hybrid",
  "parameters": {
    "query_text": "machine learning",
    "schema": "articles",
    "top_k": 20,
    "filters": {"status": "published"},
    "order_by": "created_at"
  }
}
```

**QueryBuilder translates:**
```sql
SEARCH 'machine learning' IN articles
WHERE status = 'published'
ORDER BY created_at
LIMIT 20
```

**REM executes:**
- Vector search for "machine learning"
- Apply SQL filters
- Sort and return

## Extensibility: Adding New Query Types

To add a new query type (e.g., `aggregation`):

### 1. Define Parameters (Pydantic)

```python
# percolate/src/percolate/memory/query_builder.py

class AggregationParameters(BaseModel):
    """Parameters for aggregation queries."""

    schema: str
    group_by: str
    aggregates: dict[str, str]  # field → function (COUNT, SUM, AVG)
    where: dict[str, Any] = Field(default_factory=dict)
```

### 2. Add Builder Method

```python
class QueryBuilder:
    def build_aggregation(self, params: AggregationParameters) -> str:
        """Build aggregation query."""
        aggs = ", ".join(
            f"{func}({field}) AS {field}_{func.lower()}"
            for field, func in params.aggregates.items()
        )

        query = f"SELECT {aggs} FROM {params.schema}"

        if params.where:
            where = self._build_where_clauses(params.where)
            query += f" WHERE {where}"

        query += f" GROUP BY {params.group_by}"
        return query
```

### 3. Register in build()

```python
def build(self, query_type: QueryType, parameters: dict[str, Any]) -> str:
    if query_type == QueryType.AGGREGATION:
        params = AggregationParameters(**parameters)
        return self.build_aggregation(params)
    # ... other types
```

### 4. LLM Now Supports It

No LLM retraining needed! LLM learns from system prompt:

```
Available query types:
- aggregation: Group and aggregate data
  Parameters: schema, group_by, aggregates, where
  Example: {"schema": "orders", "group_by": "status", "aggregates": {"revenue": "SUM", "orders": "COUNT"}}
```

**That's it!** 3 steps, no hard-coding.

## Testing Strategy

### 1. Unit Tests (QueryBuilder)

**Test:** Parameters → SQL translation

```python
def test_search_with_filters():
    builder = QueryBuilder()
    params = {
        "query_text": "Python",
        "schema": "articles",
        "top_k": 5,
        "filters": {"category": "tutorial"}
    }

    query = builder.build(QueryType.SEARCH, params)

    assert "SEARCH 'Python' IN articles" in query
    assert "WHERE category = 'tutorial'" in query
    assert "LIMIT 5" in query
```

**Status:** ✅ 30/30 tests passing

### 2. Integration Tests (End-to-End)

**Test:** User query → QueryPlan → SQL → Execution → Results

```python
async def test_semantic_search_e2e(db):
    # User query
    user_query = "indoor plants resources"

    # LLM generates QueryPlan
    planner = QueryPlanner()
    plan = await planner.plan(user_query, available_schemas=["resources"])

    # QueryBuilder translates
    builder = QueryBuilder()
    sql = builder.build(plan.primary_query.query_type, plan.primary_query.parameters)

    # REM executes
    results = db.query(sql)

    # Verify
    assert len(results) > 0
    assert any("plant" in r["name"].lower() for r in results)
```

**Status:** 📋 TODO

### 3. Calibration Tests (Accuracy)

**Test:** Does LLM generate correct query plans?

```python
def test_query_plan_accuracy():
    test_cases = load_test_cases()  # 8 test cases
    planner = QueryPlanner()

    correct = 0
    for tc in test_cases:
        plan = planner.plan(tc.user_query, tc.context)

        # Compare generated plan vs expected
        if plan.query_type == tc.expected.query_type:
            if plan.primary_query.parameters == tc.expected.parameters:
                correct += 1

    accuracy = correct / len(test_cases)
    assert accuracy > 0.85  # >85% accuracy required
```

**Status:** 📋 TODO (requires LLM planner implementation)

## Performance Characteristics

### QueryBuilder Translation
- **Latency:** <1ms (pure Python string formatting)
- **Memory:** O(parameters size)
- **Scalability:** No bottleneck

### End-to-End Latency
1. **LLM Planning:** 500-2000ms (model dependent)
2. **Query Translation:** <1ms
3. **REM Execution:** 1-100ms (query dependent)
4. **Total:** ~1-3 seconds typical

### Optimization Opportunities
- **Cache common patterns:** Bypass LLM for frequent queries
- **Streaming:** Start execution before full plan generated
- **Batch:** Multiple queries in single LLM call

## Dialect Management

### Two Dialects Supported

**1. REM SQL (Extended)**
- Syntax: `LOOKUP`, `SEARCH`, `TRAVERSE`
- Use: Semantic search, graph traversal, key lookups
- Performance: Optimized for these patterns

**2. Standard SQL**
- Syntax: `SELECT ... FROM ... WHERE ...`
- Use: Traditional filtering and aggregation
- Performance: Table scans with indexes

### Translation Logic

```python
class QueryBuilder:
    def build(self, query_type: QueryType, parameters: dict) -> str:
        """Translates to appropriate dialect based on query type."""

        if query_type in (QueryType.LOOKUP, QueryType.SEARCH, QueryType.TRAVERSE):
            return self._build_rem_sql(query_type, parameters)
        else:
            return self._build_standard_sql(query_type, parameters)
```

### Query Plan Specifies Dialect

```python
class Query(BaseModel):
    dialect: QueryDialect  # rem_sql | standard_sql
    parameters: dict[str, Any]
```

**LLM decides dialect based on intent:**
- Semantic search → `rem_sql`
- Exact filtering → `standard_sql`
- Graph traversal → `rem_sql`

## Error Handling

### Pydantic Validation

**Invalid parameters rejected immediately:**

```python
# ❌ Invalid: missing required field
SearchParameters(query_text="test")
# → ValidationError: Field 'schema' is required

# ❌ Invalid: depth > 10
TraverseParameters(depth=15, direction="out")
# → ValidationError: depth must be <= 10

# ✅ Valid
SearchParameters(query_text="test", schema="articles", top_k=10)
```

### Execution Errors

```python
try:
    results = db.query(sql)
except QuerySyntaxError as e:
    # Invalid SQL syntax (shouldn't happen if QueryBuilder is correct)
    log.error(f"Query syntax error: {e}")
except SchemaNotFoundError as e:
    # Schema doesn't exist
    return QueryResult.error(f"Schema '{e.schema}' not found")
except Exception as e:
    # Other database errors
    log.exception(f"Query execution failed: {e}")
```

## Summary

### Clean Separation of Concerns

| Layer | Responsibility | Implementation | Testing |
|-------|---------------|----------------|---------|
| **LLM Planner** | Intent detection, parameter generation | Pydantic AI | Accuracy, confidence calibration |
| **QueryBuilder** | Parameter → SQL translation | Pure Python functions | Unit tests (30/30 ✅) |
| **REM Executor** | Parse & execute SQL | Rust query engine | Integration tests |

### Key Benefits

1. **Generic**: No hard-coded query generation
2. **Extensible**: Add query types in 3 steps
3. **Type-safe**: Pydantic validates parameters
4. **Testable**: Each layer independent
5. **Fast**: Translation <1ms, execution 1-100ms
6. **Maintainable**: Clear boundaries between layers

### Implementation Status

- ✅ **Rust LLM Query Planner** - Complete at `../../src/llm/query_builder.rs`
  - Claude Sonnet 4.5 support with markdown stripping
  - Cerebras Qwen-3-32B support with strict JSON schema
  - 100% schema adherence for both providers
  - ~500ms query planning with Cerebras
- ✅ **QueryBuilder** - Query translation implemented in Rust
- ✅ **REM Executor** - Full SQL dialect support
- ✅ **Integration tests** - See `../../../percolate/tests/integration/test_rust_query_planner.py`

**Reference:** The actual implementation differs from this conceptual architecture in that it's entirely in Rust rather than having a Python QueryBuilder layer.

This architecture ensures the system is **simple, clean, and extensible** as designed!

## See Also

### Query Engine Documentation

- **[QUERY_LLM_QUICKSTART.md](QUERY_LLM_QUICKSTART.md)** - LLM configuration guide (Cerebras + Claude)
- **[sql-dialect.md](sql-dialect.md)** - Complete REM SQL syntax reference
- **[iterated-retrieval.md](iterated-retrieval.md)** - Multi-stage query execution
- **[advanced-search.md](advanced-search.md)** - Vector search implementation details

### Implementation Files

- **[query_builder.rs](../../src/llm/query_builder.rs)** - Rust LLM query planner (actual implementation)
- **[parser.rs](../../src/query/parser.rs)** - REM SQL parser
- **[executor.rs](../../src/query/executor.rs)** - Query execution engine
- **[test_rust_query_planner.py](../../../percolate/tests/integration/test_rust_query_planner.py)** - Integration tests
