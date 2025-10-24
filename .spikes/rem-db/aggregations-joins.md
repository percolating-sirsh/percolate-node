# Implementing aggregations and joins over RocksDB

## Overview

RocksDB is a key-value store, not a relational database. To support SQL aggregations (COUNT, SUM, AVG, GROUP BY) and joins, we need a **query planning layer** that sits on top of RocksDB.

## Approaches

### Approach 1: Lightweight SQL parser + custom executor (current path)
**Libraries**: SQLGlot (Python)
**Pros**: Full control, minimal dependencies, Python-native
**Cons**: Need to implement execution logic ourselves

### Approach 2: Embedded analytics engine
**Libraries**: DuckDB (Python/C++), Apache DataFusion (Rust + Python bindings)
**Pros**: Production-grade, highly optimized, full SQL support
**Cons**: More dependencies, less control

### Approach 3: Build on existing RocksDB SQL layer
**Libraries**: Rockset-style architecture, CockroachDB storage patterns
**Pros**: Proven patterns
**Cons**: Complex, requires significant engineering

## Recommended: Hybrid approach

Use **SQLGlot for parsing** + **custom executor with RocksDB** for control, with option to integrate **DuckDB or DataFusion** for complex aggregations later.

---

## Option 1: SQLGlot (recommended for REM)

### What is SQLGlot?

SQLGlot is a **Python SQL parser, transpiler, optimizer, and engine** written from scratch:
- Parses SQL into AST (Abstract Syntax Tree)
- Optimizes queries (predicate pushdown, join reordering)
- Transpiles between 18+ SQL dialects
- Includes simple execution engine for testing

**GitHub**: https://github.com/tobymao/sqlglot
**Docs**: https://sqlglot.com/

### Features relevant to REM

#### 1. SQL parsing and AST
```python
import sqlglot

# Parse SQL into AST
ast = sqlglot.parse_one("SELECT COUNT(*), category FROM resources GROUP BY category")

# Traverse AST to extract components
for select in ast.find_all(sqlglot.exp.Select):
    print(select.expressions)  # [COUNT(*), category]
    print(select.args.get('from'))  # resources
    print(select.args.get('group'))  # GROUP BY category
```

#### 2. Query optimization
```python
from sqlglot.optimizer import optimize

# Optimize AST
optimized = optimize(ast, schema={"resources": {"category": "VARCHAR", "status": "VARCHAR"}})

# SQLGlot applies:
# - Predicate pushdown
# - Constant folding
# - Join reordering
# - Redundant expression elimination
```

#### 3. Aggregation detection
```python
# Detect aggregations in query
aggregations = []
for agg in ast.find_all(sqlglot.exp.AggFunc):
    print(f"Aggregation: {agg.name}")  # COUNT, SUM, AVG, MAX, MIN
    print(f"Args: {agg.args}")
```

#### 4. Join extraction
```python
# Extract join information
for join in ast.find_all(sqlglot.exp.Join):
    print(f"Join type: {join.side}")  # LEFT, RIGHT, INNER, FULL
    print(f"Join table: {join.this}")
    print(f"Join condition: {join.args.get('on')}")
```

### Implementation strategy for REM

#### Step 1: Parse SQL with SQLGlot
```python
from rem_db.sql import parse_sql_with_aggregations

parsed = parse_sql_with_aggregations("""
    SELECT category, COUNT(*) as count, AVG(priority) as avg_priority
    FROM resources
    WHERE status = 'active'
    GROUP BY category
    HAVING COUNT(*) > 5
    ORDER BY count DESC
""")

# Returns structured query plan:
# {
#     "table": "resources",
#     "where": [{"field": "status", "op": "=", "value": "active"}],
#     "group_by": ["category"],
#     "aggregations": [
#         {"func": "COUNT", "field": "*", "alias": "count"},
#         {"func": "AVG", "field": "priority", "alias": "avg_priority"}
#     ],
#     "having": [{"func": "COUNT", "op": ">", "value": 5}],
#     "order_by": [{"field": "count", "direction": "DESC"}]
# }
```

#### Step 2: Execute plan over RocksDB
```python
def execute_aggregation_query(db: REMDatabase, plan: dict) -> list[dict]:
    """Execute aggregation query over RocksDB entities."""

    # Stage 1: Scan and filter (WHERE clause)
    filtered_entities = []
    prefix = db._key(f"entity:{db.tenant_id}")

    for key, value in db.db.iter(prefix):
        entity = Entity(**orjson.loads(value))

        # Filter by table
        if entity.type != plan["table"]:
            continue

        # Apply WHERE predicates
        if _matches_predicates(entity, plan["where"]):
            filtered_entities.append(entity)

    # Stage 2: Group by
    groups = defaultdict(list)
    for entity in filtered_entities:
        # Extract group key
        group_key = tuple(
            entity.properties.get(field)
            for field in plan["group_by"]
        )
        groups[group_key].append(entity)

    # Stage 3: Apply aggregations
    results = []
    for group_key, group_entities in groups.items():
        row = {}

        # Add group by fields
        for i, field in enumerate(plan["group_by"]):
            row[field] = group_key[i]

        # Apply aggregation functions
        for agg in plan["aggregations"]:
            if agg["func"] == "COUNT":
                row[agg["alias"]] = len(group_entities)
            elif agg["func"] == "SUM":
                row[agg["alias"]] = sum(
                    e.properties.get(agg["field"], 0)
                    for e in group_entities
                )
            elif agg["func"] == "AVG":
                values = [e.properties.get(agg["field"], 0) for e in group_entities]
                row[agg["alias"]] = sum(values) / len(values) if values else 0
            elif agg["func"] == "MAX":
                row[agg["alias"]] = max(
                    e.properties.get(agg["field"], 0)
                    for e in group_entities
                )
            elif agg["func"] == "MIN":
                row[agg["alias"]] = min(
                    e.properties.get(agg["field"], 0)
                    for e in group_entities
                )

        results.append(row)

    # Stage 4: HAVING filter
    if plan.get("having"):
        results = [r for r in results if _matches_having(r, plan["having"])]

    # Stage 5: ORDER BY
    if plan.get("order_by"):
        results = _apply_ordering(results, plan["order_by"])

    return results
```

#### Step 3: Join implementation
```python
def execute_join_query(db: REMDatabase, plan: dict) -> list[dict]:
    """Execute join query over RocksDB entities."""

    # Example: SELECT users.name, COUNT(issues.id)
    #          FROM users
    #          LEFT JOIN issues ON users.id = issues.created_by
    #          GROUP BY users.name

    # Stage 1: Load left table
    left_entities = db.sql(f"SELECT * FROM {plan['left_table']}")

    # Stage 2: Load right table
    right_entities = db.sql(f"SELECT * FROM {plan['right_table']}")

    # Stage 3: Build hash table for join (hash join algorithm)
    right_hash = defaultdict(list)
    for entity in right_entities:
        join_key = entity.properties.get(plan['right_join_field'])
        right_hash[join_key].append(entity)

    # Stage 4: Probe and join
    joined = []
    for left_entity in left_entities:
        left_key = left_entity.properties.get(plan['left_join_field'])

        if plan['join_type'] == 'INNER':
            # Only include if match exists
            if left_key in right_hash:
                for right_entity in right_hash[left_key]:
                    joined.append(_merge_entities(left_entity, right_entity))

        elif plan['join_type'] == 'LEFT':
            # Include left even if no match
            if left_key in right_hash:
                for right_entity in right_hash[left_key]:
                    joined.append(_merge_entities(left_entity, right_entity))
            else:
                joined.append(_merge_entities(left_entity, None))

    # Stage 5: Apply aggregations/filters
    return _apply_post_join_operations(joined, plan)
```

### SQLGlot pros/cons

**Pros**:
- Lightweight (pure Python, no C dependencies)
- Full SQL parsing (supports 18+ dialects)
- Built-in query optimization
- Easy to integrate with RocksDB
- Can extract AST for custom execution
- Active development

**Cons**:
- Execution engine is basic (not production-grade)
- No vectorization or SIMD
- Single-threaded
- Need to implement most execution logic ourselves

---

## Option 2: DuckDB (best for complex analytics)

### What is DuckDB?

DuckDB is an **embedded analytical database** (like SQLite for analytics):
- Columnar storage format (fast aggregations)
- Vectorized query execution
- Full SQL support (window functions, CTEs, complex joins)
- Zero external dependencies
- Python integration via `duckdb` package

**Website**: https://duckdb.org/
**GitHub**: https://github.com/duckdb/duckdb
**Python docs**: https://duckdb.org/docs/api/python/overview

### How to use with REM

#### Approach: Export RocksDB entities → DuckDB for analytics

```python
import duckdb

class REMDatabase:
    def __init__(self, ...):
        # ... RocksDB setup ...
        self.duckdb = duckdb.connect(':memory:')  # In-memory analytics

    def _sync_to_duckdb(self, table: str):
        """Sync RocksDB entities to DuckDB for analytics."""

        # Get all entities for table
        entities = self.sql(f"SELECT * FROM {table}")

        # Convert to dict records
        records = [
            {
                "id": str(e.id),
                "created_at": e.created_at.isoformat(),
                **e.properties
            }
            for e in entities
        ]

        # Load into DuckDB
        self.duckdb.execute(f"DROP TABLE IF EXISTS {table}")
        self.duckdb.execute(f"CREATE TABLE {table} AS SELECT * FROM records")

    def analytics_query(self, sql: str, tables: list[str]) -> pd.DataFrame:
        """Execute complex analytics query via DuckDB."""

        # Sync tables to DuckDB
        for table in tables:
            self._sync_to_duckdb(table)

        # Execute query
        result = self.duckdb.execute(sql).fetchdf()
        return result
```

#### Example: Complex aggregation with window functions
```python
# Query that's hard to implement manually
result = db.analytics_query("""
    SELECT
        category,
        COUNT(*) as total,
        AVG(priority) as avg_priority,
        RANK() OVER (ORDER BY COUNT(*) DESC) as rank,
        LAG(COUNT(*)) OVER (ORDER BY created_at) as prev_count
    FROM resources
    WHERE status = 'active'
    GROUP BY category, DATE_TRUNC('month', created_at)
    HAVING COUNT(*) > 10
    ORDER BY total DESC
""", tables=["resources"])
```

#### Example: Complex join with aggregations
```python
result = db.analytics_query("""
    SELECT
        u.name,
        COUNT(DISTINCT i.id) as issue_count,
        COUNT(DISTINCT pr.id) as pr_count,
        AVG(i.priority) as avg_issue_priority
    FROM users u
    LEFT JOIN issues i ON u.id = i.created_by
    LEFT JOIN pull_requests pr ON u.id = pr.author_id
    WHERE u.status = 'active'
    GROUP BY u.name
    HAVING COUNT(DISTINCT i.id) > 5
    ORDER BY issue_count DESC
""", tables=["users", "issues", "pull_requests"])
```

### DuckDB pros/cons

**Pros**:
- Production-grade query engine
- Extremely fast (columnar + vectorized)
- Full SQL support (window functions, CTEs, complex joins)
- No external dependencies (embedded)
- Python integration is seamless
- Can query Pandas DataFrames directly
- Handles large datasets efficiently

**Cons**:
- Requires data sync from RocksDB → DuckDB
- Not real-time (sync overhead)
- Adds ~50MB to binary size
- Separate storage (duplicates data in memory)

---

## Option 3: Apache DataFusion (Rust-native)

### What is DataFusion?

Apache DataFusion is a **Rust query engine** with Python bindings:
- Uses Apache Arrow for in-memory format
- Vectorized, multi-threaded execution
- Full SQL support
- Extensible (custom data sources, UDFs)
- Python bindings via `datafusion` package

**Website**: https://datafusion.apache.org/
**GitHub**: https://github.com/apache/datafusion
**Python**: https://pypi.org/project/datafusion/

### How to use with REM

#### Approach: Implement custom DataFusion TableProvider for RocksDB

```python
from datafusion import SessionContext, TableProvider
import pyarrow as pa

class RocksDBTableProvider(TableProvider):
    """DataFusion table provider backed by RocksDB."""

    def __init__(self, db: REMDatabase, table_name: str):
        self.db = db
        self.table_name = table_name

    def schema(self) -> pa.Schema:
        """Return Arrow schema for table."""
        schema_def = self.db.get_schema(self.table_name)
        # Convert Pydantic schema → Arrow schema
        return _convert_to_arrow_schema(schema_def)

    def scan(self, projection: list[str], filters: list) -> pa.Table:
        """Scan RocksDB and return Arrow table."""

        # Scan entities from RocksDB
        entities = self.db.sql(f"SELECT * FROM {self.table_name}")

        # Convert to Arrow table
        records = [
            {field: e.properties.get(field) for field in projection}
            for e in entities
        ]
        return pa.Table.from_pylist(records)

# Usage
ctx = SessionContext()
ctx.register_table_provider("resources", RocksDBTableProvider(db, "resources"))

# Execute query via DataFusion
result = ctx.sql("""
    SELECT category, COUNT(*) as count
    FROM resources
    WHERE status = 'active'
    GROUP BY category
    ORDER BY count DESC
""").to_pandas()
```

### DataFusion pros/cons

**Pros**:
- Rust-native (fast, safe)
- Vectorized + multi-threaded
- Extensible (custom table providers)
- Production-grade
- No data duplication (can scan directly)

**Cons**:
- Rust dependency (compilation complexity)
- Python bindings less mature than DuckDB
- Requires Arrow conversion
- More complex integration

---

## Recommended implementation plan

### Phase 1: SQLGlot for basic aggregations (1-2 weeks)

**Goal**: Support COUNT, SUM, AVG, GROUP BY, HAVING

**Tasks**:
1. Add SQLGlot dependency to `pyproject.toml`
2. Create `src/rem_db/aggregations.py` with:
   - `parse_aggregation_query()` - Extract aggregation info from SQL
   - `execute_aggregation()` - Run over RocksDB entities
3. Support GROUP BY with multiple fields
4. Support HAVING clause
5. Add tests for common aggregation patterns

**Example SQL to support**:
```sql
SELECT category, COUNT(*) as count, AVG(priority) as avg_priority
FROM resources
WHERE status = 'active'
GROUP BY category
HAVING COUNT(*) > 5
ORDER BY count DESC
```

### Phase 2: Hash joins for 2-table joins (2-3 weeks)

**Goal**: Support INNER JOIN, LEFT JOIN between two tables

**Tasks**:
1. Extend SQL parser to extract join information
2. Implement hash join algorithm in `src/rem_db/joins.py`
3. Support equi-joins (equality conditions only)
4. Add join + aggregation support
5. Optimize with indexes on join keys

**Example SQL to support**:
```sql
SELECT u.name, COUNT(i.id) as issue_count
FROM users u
LEFT JOIN issues i ON u.id = i.created_by
GROUP BY u.name
```

### Phase 3: DuckDB integration for complex queries (1 week)

**Goal**: Offload complex analytics to DuckDB

**Tasks**:
1. Add DuckDB dependency (optional extra)
2. Create `src/rem_db/analytics.py` with:
   - `sync_to_duckdb()` - Export entities to DuckDB
   - `analytics_query()` - Execute complex SQL
3. Support window functions, CTEs, multi-table joins
4. Add caching layer (avoid re-sync)

**Example SQL to support**:
```sql
SELECT
    category,
    COUNT(*) as total,
    RANK() OVER (ORDER BY COUNT(*) DESC) as rank
FROM resources
GROUP BY category
```

### Phase 4: Optimization (ongoing)

**Optimizations to add**:
1. **Indexed aggregations**: Use secondary indexes for GROUP BY
2. **Streaming aggregations**: Don't load all entities into memory
3. **Parallel execution**: Multi-threaded scans
4. **Predicate pushdown**: Filter early in scan
5. **Join reordering**: Smaller table as build side

---

## Code structure

```
src/rem_db/
├── sql.py              # Basic SQL parser (existing)
├── aggregations.py     # NEW: Aggregation execution
├── joins.py            # NEW: Join algorithms
├── analytics.py        # NEW: DuckDB integration (optional)
├── query_planner.py    # NEW: Query optimization
└── executor.py         # NEW: Unified query executor
```

### aggregations.py
```python
"""Aggregation execution over RocksDB entities."""

from dataclasses import dataclass
from collections import defaultdict
import sqlglot

@dataclass
class AggregationPlan:
    table: str
    where: list
    group_by: list[str]
    aggregations: list[dict]
    having: list
    order_by: list

def parse_aggregation_query(sql: str) -> AggregationPlan:
    """Parse SQL with aggregations using SQLGlot."""
    ast = sqlglot.parse_one(sql)
    # ... extract components ...
    return AggregationPlan(...)

def execute_aggregation(db: REMDatabase, plan: AggregationPlan) -> list[dict]:
    """Execute aggregation over RocksDB."""
    # Scan + filter + group + aggregate + having + order
    # ... implementation ...
```

### joins.py
```python
"""Join algorithms for RocksDB entities."""

from dataclasses import dataclass
from collections import defaultdict

@dataclass
class JoinPlan:
    left_table: str
    right_table: str
    join_type: str  # INNER, LEFT, RIGHT, FULL
    left_key: str
    right_key: str

def hash_join(left_entities: list, right_entities: list, plan: JoinPlan) -> list:
    """Hash join algorithm."""
    # Build hash table on smaller side
    # Probe and join
    # ... implementation ...
```

### analytics.py (optional)
```python
"""DuckDB integration for complex analytics."""

import duckdb

class AnalyticsEngine:
    def __init__(self, db: REMDatabase):
        self.db = db
        self.duckdb = duckdb.connect(':memory:')

    def sync_table(self, table: str):
        """Sync RocksDB table to DuckDB."""
        # ... implementation ...

    def query(self, sql: str, tables: list[str]) -> pd.DataFrame:
        """Execute analytics query."""
        # ... implementation ...
```

---

## Performance expectations

### Aggregations (SQLGlot approach)
- **Small datasets** (< 10K entities): 50-200ms
- **Medium datasets** (10K-100K entities): 200ms-2s
- **Large datasets** (> 100K entities): 2-10s

**Bottleneck**: Full table scan + in-memory grouping

**Optimization**: Secondary indexes on GROUP BY fields

### Joins (hash join)
- **Small × Small** (< 1K each): 10-50ms
- **Small × Medium** (1K × 10K): 50-500ms
- **Medium × Medium** (10K × 10K): 500ms-5s

**Bottleneck**: Hash table construction + memory

**Optimization**: Join smaller table as build side

### DuckDB analytics
- **Any size**: 10-500ms (vectorized execution)

**Bottleneck**: Sync overhead (RocksDB → DuckDB)

**Optimization**: Incremental sync, caching

---

## Summary

### Recommended stack for REM

1. **SQLGlot** for SQL parsing and query planning
2. **Custom executor** for basic aggregations and 2-table joins
3. **DuckDB** (optional) for complex analytics (window functions, multi-table joins)

### Implementation order

1. ✅ **Basic SQL** (already done - WHERE, ORDER BY, LIMIT)
2. **Aggregations** (COUNT, SUM, AVG, GROUP BY, HAVING) - SQLGlot + custom
3. **Joins** (INNER, LEFT) - Hash join algorithm
4. **Complex analytics** (window functions, CTEs) - DuckDB integration

### When to use each approach

- **Basic queries**: Current SQL implementation
- **Aggregations**: SQLGlot parser + custom executor
- **Simple joins**: Hash join implementation
- **Complex analytics**: DuckDB integration
- **Production scale**: Consider DataFusion (Rust)

This gives REM full SQL capabilities while maintaining control over the core query execution.
