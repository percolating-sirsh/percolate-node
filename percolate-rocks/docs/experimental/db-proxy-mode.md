# Database proxy mode

**Experimental feature:** REM as a semantic layer over external databases.

## Motivation

Enterprise databases (Postgres, MySQL, etc.) often have schemas optimized for transactional workloads, not AI consumption:

- Normalized tables spread related data across multiple joins
- Cryptic column names (`cust_id`, `prod_sku`, `ord_dt`)
- Inconsistent data types (dates as strings, JSON blobs)
- Missing semantic context (what does `status=3` mean?)
- Poor documentation (or none)

**Problem:** LLMs struggle to generate correct SQL against these schemas.

**Solution:** REM acts as a semantic proxy layer that:
1. Learns schema semantics from the database
2. Builds an AI-friendly metadata layer
3. Translates natural language → correct SQL in target dialect
4. Returns results with semantic context

## Architecture

```
┌─────────────┐
│   User/LLM  │
└──────┬──────┘
       │ Natural language query
       ▼
┌─────────────────────────────────┐
│   REM Proxy Layer               │
│                                  │
│  ┌──────────────────────────┐  │
│  │  Semantic Schema         │  │
│  │  - Entity definitions    │  │
│  │  - Field descriptions    │  │
│  │  - Relationship graph    │  │
│  │  - Value examples        │  │
│  │  - Business rules        │  │
│  └──────────────────────────┘  │
│                                  │
│  ┌──────────────────────────┐  │
│  │  Query Translation       │  │
│  │  - NL → SQL generator    │  │
│  │  - Dialect adaptation    │  │
│  │  - Join resolution       │  │
│  │  - Query validation      │  │
│  └──────────────────────────┘  │
└───────────┬─────────────────────┘
            │ Postgres SQL
            ▼
┌─────────────────────────────────┐
│   External Database             │
│   (Postgres, MySQL, etc.)       │
└─────────────────────────────────┘
```

## Key Features

### 1. Schema Learning

REM introspects the target database and builds semantic metadata:

```sql
-- Postgres schema (cryptic)
CREATE TABLE cust (
  id SERIAL PRIMARY KEY,
  nm VARCHAR(100),
  eml VARCHAR(255),
  cr_dt TIMESTAMP
);

CREATE TABLE ord (
  id SERIAL PRIMARY KEY,
  cust_id INTEGER REFERENCES cust(id),
  amt DECIMAL(10,2),
  stat INTEGER,
  ord_dt TIMESTAMP
);
```

**REM learns:**
```python
# Semantic schema (AI-friendly)
class Customer(BaseModel):
    """Customer entity from cust table."""
    id: int = Field(description="Unique customer ID")
    name: str = Field(description="Customer full name", source="nm")
    email: str = Field(description="Contact email address", source="eml")
    created_at: datetime = Field(description="Account creation date", source="cr_dt")

class Order(BaseModel):
    """Order entity from ord table."""
    id: int = Field(description="Unique order ID")
    customer_id: int = Field(description="FK to customer", source="cust_id")
    amount: Decimal = Field(description="Order total (USD)", source="amt")
    status: int = Field(
        description="Order status: 1=pending, 2=shipped, 3=delivered, 4=cancelled",
        source="stat"
    )
    order_date: datetime = Field(description="Order placement date", source="ord_dt")

    model_config = ConfigDict(
        json_schema_extra={
            "relationships": [
                {
                    "name": "customer",
                    "type": "many_to_one",
                    "target": "Customer",
                    "foreign_key": "customer_id"
                }
            ]
        }
    )
```

### 2. Semantic Query Translation

User asks natural language → REM generates correct SQL:

```python
# User query
"Show me all orders over $1000 placed in the last week with customer emails"

# REM translates to Postgres SQL
SELECT
  o.id AS order_id,
  o.amt AS amount,
  o.ord_dt AS order_date,
  c.nm AS customer_name,
  c.eml AS customer_email
FROM ord o
INNER JOIN cust c ON o.cust_id = c.id
WHERE o.amt > 1000
  AND o.ord_dt > NOW() - INTERVAL '7 days'
ORDER BY o.ord_dt DESC;
```

**Without REM:**
- LLM guesses table/column names (often wrong)
- Doesn't know `stat=3` means delivered
- Doesn't know `amt` is USD
- Forgets the join condition

**With REM:**
- Semantic schema provides context
- LLM generates from clean metadata
- REM maps semantic fields → actual columns
- REM validates and executes query

### 3. Dialect Adaptation

REM generates SQL in the target database dialect:

| Database | Dialect Differences | REM Handles |
|----------|-------------------|-------------|
| **Postgres** | `INTERVAL '7 days'` | ✅ |
| **MySQL** | `DATE_SUB(NOW(), INTERVAL 7 DAY)` | ✅ |
| **SQLite** | `datetime('now', '-7 days')` | ✅ |
| **BigQuery** | `TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)` | ✅ |

Same semantic query → different SQL per database.

## Use Cases

### 1. Enterprise AI Integration

**Scenario:** Company has 200+ Postgres tables with poor documentation.

**Without REM:**
- Data team writes custom SQL for every LLM query
- LLM hallucinates table/column names
- Queries break when schema changes

**With REM:**
```python
# One-time setup
rem proxy init --connection "postgresql://prod/analytics"
rem proxy learn --auto  # Introspect schema

# Ongoing usage
rem query "How many orders shipped last month by region?"
# → REM generates correct SQL, executes, returns results
```

### 2. Multi-Database Query Layer

**Scenario:** Data spread across Postgres (orders), MySQL (inventory), Snowflake (analytics).

**With REM:**
```python
# Register all databases
rem proxy add --name orders --connection "postgresql://prod/orders"
rem proxy add --name inventory --connection "mysql://prod/inventory"
rem proxy add --name analytics --connection "snowflake://prod/analytics"

# Federated query
rem query "Join orders from Postgres with inventory levels from MySQL"
# → REM generates separate queries + join in-memory
```

### 3. Legacy System Modernization

**Scenario:** 20-year-old Oracle database with cryptic schemas.

**With REM:**
- Learn semantic schema from Oracle
- Generate documentation automatically
- Enable LLM-driven queries without rewriting database

## Implementation Design

### Schema Learning Pipeline

```rust
// 1. Introspect database
pub async fn introspect_database(conn: &DatabaseConnection) -> Result<RawSchema> {
    let tables = conn.list_tables().await?;
    let columns = conn.list_columns().await?;
    let constraints = conn.list_constraints().await?;
    let indexes = conn.list_indexes().await?;

    Ok(RawSchema { tables, columns, constraints, indexes })
}

// 2. Generate semantic schema with LLM
pub async fn generate_semantic_schema(
    raw_schema: RawSchema,
    llm: &LLM
) -> Result<SemanticSchema> {
    // Use LLM to:
    // - Expand cryptic names (cust_id → customer_id)
    // - Infer field descriptions from names/types
    // - Detect relationships from foreign keys
    // - Sample data to infer enum meanings

    let prompt = format!(
        "Generate semantic schema for database:\n{}\n\
         Include: field descriptions, relationship types, enum values",
        serde_json::to_string_pretty(&raw_schema)?
    );

    let response = llm.complete(&prompt).await?;
    Ok(serde_json::from_str(&response)?)
}

// 3. Store in REM
pub fn store_semantic_schema(db: &Database, schema: SemanticSchema) -> Result<()> {
    // Store as entities with indexed fields
    for table in schema.tables {
        db.insert("db_tables", &table)?;
    }
    for field in schema.fields {
        db.insert("db_fields", &field)?;
    }
    for relationship in schema.relationships {
        db.add_edge(
            relationship.source_table,
            relationship.target_table,
            &relationship.name,
            None
        )?;
    }
    Ok(())
}
```

### Query Translation Pipeline

```rust
pub async fn translate_query(
    db: &Database,
    nl_query: &str,
    target_db: &str,
    llm: &LLM
) -> Result<String> {
    // 1. Retrieve semantic schema
    let schema = db.query(
        "db_tables",
        "SELECT * FROM db_tables WHERE database = ?",
        &[target_db]
    )?;

    // 2. Generate SQL with LLM
    let prompt = format!(
        "Translate natural language query to {} SQL:\n\
         Query: {}\n\
         Schema: {}\n\
         Return only SQL, no explanation.",
        target_db,
        nl_query,
        serde_json::to_string_pretty(&schema)?
    );

    let sql = llm.complete(&prompt).await?;

    // 3. Validate SQL
    validate_sql(&sql, &schema)?;

    Ok(sql)
}
```

### Execution

```rust
pub async fn execute_proxy_query(
    db: &Database,
    conn: &DatabaseConnection,
    nl_query: &str,
    llm: &LLM
) -> Result<Vec<serde_json::Value>> {
    // 1. Translate to SQL
    let sql = translate_query(db, nl_query, conn.dialect(), llm).await?;

    // 2. Execute on target database
    let results = conn.execute(&sql).await?;

    // 3. Add semantic metadata to results
    let schema = db.get_semantic_schema(conn.name())?;
    let enriched = enrich_results(results, &schema)?;

    Ok(enriched)
}
```

## Configuration

### Proxy Configuration

```toml
# ~/.p8/config.toml
[proxy]
enabled = true
default_database = "orders"
cache_ttl_seconds = 300  # Cache schema metadata
llm = "gpt-4.1"          # LLM for query translation

[[proxy.databases]]
name = "orders"
connection = "postgresql://prod:5432/orders"
dialect = "postgres"
schema_refresh_interval = "1h"

[[proxy.databases]]
name = "inventory"
connection = "mysql://prod:3306/inventory"
dialect = "mysql"
schema_refresh_interval = "1h"

[[proxy.databases]]
name = "analytics"
connection = "snowflake://prod/analytics"
dialect = "snowflake"
schema_refresh_interval = "6h"
```

### CLI Usage

```bash
# Initialize proxy mode
rem proxy init --connection "postgresql://prod/orders"

# Learn schema (with LLM assistance)
rem proxy learn --database orders --llm gpt-4.1

# View learned schema
rem proxy schema --database orders --format yaml

# Test query translation
rem proxy translate "orders over $1000 last week" --database orders

# Execute query
rem query "orders over $1000 last week" --database orders

# Update schema (when database schema changes)
rem proxy refresh --database orders
```

### Python API

```python
from rem_db import Database, ProxyMode

# Initialize proxy
db = Database(mode=ProxyMode.PROXY)
db.proxy_add_database(
    name="orders",
    connection="postgresql://prod/orders",
    dialect="postgres"
)

# Learn schema
db.proxy_learn_schema("orders", llm="gpt-4.1")

# Query via proxy
results = db.query(
    "Show me all orders over $1000 placed in the last week with customer emails",
    database="orders"
)

# Direct SQL execution (bypass translation)
results = db.proxy_execute(
    "SELECT * FROM ord WHERE amt > 1000",
    database="orders"
)
```

## Benefits

### For Enterprise Adoption

1. **No database migration** - REM works with existing databases
2. **Incremental adoption** - Add semantic layer without rewriting apps
3. **Multi-database support** - One interface for Postgres, MySQL, Oracle, etc.
4. **Automatic documentation** - LLM generates schema docs from introspection
5. **Query validation** - Catch SQL errors before execution

### For AI Applications

1. **Better LLM queries** - Semantic context reduces hallucination
2. **Consistent interface** - Same query works across database types
3. **Relationship awareness** - Graph edges capture foreign keys
4. **Business logic** - Enum meanings, validation rules in metadata
5. **Query history** - Track and optimize common queries

## Comparison: Direct Mode vs Proxy Mode

| Feature | Direct Mode (RocksDB) | Proxy Mode (External DB) |
|---------|----------------------|--------------------------|
| **Storage** | RocksDB embedded | Postgres/MySQL/etc. |
| **Schema** | Pydantic models | Learned from DB |
| **Queries** | REM SQL dialect | Target DB dialect |
| **Performance** | 5-10ms | 50-200ms (network) |
| **Embeddings** | Built-in HNSW | Must sync to REM |
| **Use Case** | New apps, personal AI | Enterprise integration |

**When to use proxy mode:**
- Existing enterprise databases
- Cannot migrate data
- Need to query live data
- Multi-database federation

**When to use direct mode:**
- New applications
- Need vector search
- Want embedded database
- Performance critical

## Integration with Percolate

Percolate can use REM in both modes:

### Direct Mode (Default)
```python
# Percolate API with REM storage
from percolate.memory import Database

db = Database(path="~/.p8/db")  # RocksDB
db.insert("resources", {"content": "...", "uri": "..."})
results = db.search("resources", "Python tutorial", top_k=5)
```

### Proxy Mode (Enterprise)
```python
# Percolate API with Postgres backend
from percolate.memory import Database, ProxyMode

db = Database(
    mode=ProxyMode.PROXY,
    connection="postgresql://prod/knowledge"
)

# Same API, different backend
db.insert("resources", {"content": "...", "uri": "..."})
results = db.search("resources", "Python tutorial", top_k=5)
# → Executes on Postgres, returns results
```

**Deployment scenarios:**
1. **Personal use** → Direct mode (RocksDB)
2. **Small team** → Direct mode (shared RocksDB on NFS/S3)
3. **Enterprise** → Proxy mode (connect to existing Postgres)
4. **Hybrid** → Direct mode for embeddings, proxy mode for structured data

## Future Enhancements

### 1. Query Optimization

```rust
// Cache frequent queries
pub struct QueryCache {
    cache: HashMap<String, (String, Instant)>,  // NL → (SQL, timestamp)
    ttl: Duration,
}

impl QueryCache {
    pub fn get(&self, nl_query: &str) -> Option<&str> {
        self.cache.get(nl_query)
            .filter(|(_, ts)| ts.elapsed() < self.ttl)
            .map(|(sql, _)| sql.as_str())
    }
}
```

### 2. Schema Evolution Tracking

```rust
// Detect schema changes and update semantic layer
pub async fn detect_schema_changes(
    db: &Database,
    conn: &DatabaseConnection
) -> Result<Vec<SchemaChange>> {
    let current = introspect_database(conn).await?;
    let previous = db.get_raw_schema(conn.name())?;

    diff_schemas(&previous, &current)
}
```

### 3. Multi-Database Joins

```rust
// Execute queries across databases
pub async fn federated_query(
    db: &Database,
    nl_query: &str,
    databases: &[&str],
    llm: &LLM
) -> Result<Vec<serde_json::Value>> {
    // 1. Generate query plan
    let plan = generate_query_plan(db, nl_query, databases, llm).await?;

    // 2. Execute subqueries in parallel
    let subresults = join_all(
        plan.subqueries.iter()
            .map(|sq| execute_proxy_query(db, sq.connection, &sq.sql, llm))
    ).await;

    // 3. Join results in-memory
    join_results(subresults, &plan.join_conditions)
}
```

### 4. Materialized Views

```rust
// Cache expensive queries in REM
pub async fn create_materialized_view(
    db: &Database,
    name: &str,
    query: &str,
    refresh_interval: Duration
) -> Result<()> {
    // Execute query and store results in REM
    let results = execute_proxy_query(db, query).await?;

    for result in results {
        db.insert(&format!("mv_{}", name), &result)?;
    }

    // Schedule refresh
    schedule_refresh(name, query, refresh_interval);
    Ok(())
}
```

## Conclusion

Database proxy mode extends REM's utility beyond embedded use cases:

- **Enterprise integration** without database migration
- **Semantic layer** for AI-friendly SQL generation
- **Multi-database** federation with consistent interface
- **Incremental adoption** alongside existing systems

**Implementation priority:** Low (after core REM features stable)

**Estimated effort:** 2-3 weeks for basic proxy mode

**Dependencies:**
- Core REM implementation complete
- LLM query builder working
- Schema validation solid
- Connection pooling for external databases
