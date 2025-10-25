# REM Database Python Examples

Examples demonstrating the Python bindings (PyO3) for the REM database.

## Setup

### 1. Build the Python extension

```bash
# Create virtualenv (if not already created)
python3 -m venv .venv
source .venv/bin/activate

# Install maturin
pip install maturin

# Build and install the extension
maturin develop --release
```

This compiles the Rust code and installs the `rem_db` Python module.

### 2. Verify installation

```python
python3 -c "from rem_db import Database; print('✓ Module loaded')"
```

## Examples

### Basic Operations (`python_basic.py`)

Demonstrates fundamental database operations:
- Opening/creating a database
- Registering schemas
- Inserting entities
- Querying with SQL
- Updating and deleting entities
- Counting entities

**Run:**
```bash
source .venv/bin/activate
python3 examples/python_basic.py
```

**Expected output:**
```
✓ Successfully imported percolate_rocks

1. Opening database at: python-test-db
✓ Database opened

2. Registering schema...
✓ Schema registered

3. Inserting entities...
  Inserted: Alice → uuid-here
  Inserted: Bob → uuid-here
  ...

✓ All operations completed successfully!
```

### Semantic Search (`python_search.py`)

Demonstrates vector embeddings and similarity search:
- Schema with embedding configuration
- Async insert operations
- Semantic search queries
- Combining search with SQL filtering

**Prerequisites:**
```bash
# Option 1: Local embeddings (fast, runs offline)
export P8_DEFAULT_EMBEDDING="local:all-MiniLM-L6-v2"

# Option 2: OpenAI embeddings (requires API key)
export OPENAI_API_KEY="sk-..."
```

**Run:**
```bash
source .venv/bin/activate
python3 examples/python_search.py
```

**Expected output:**
```
✓ Successfully imported percolate_rocks

1. Opening database at: python-search-db
✓ Database opened

2. Registering schema with embedding support...
✓ Schema registered

3. Inserting articles...
  Inserted: Introduction to Rust
  Inserted: Python Data Science
  ...

4. Performing semantic search...
  Query: 'systems programming and memory safety'

  Results (3 found):
  1. Introduction to Rust (score: 0.8542)
     Content: Rust is a systems programming language...
  ...
```

## API Reference

### Database

```python
from rem_db import Database

# Create/open database
db = Database("/path/to/db")

# Register schema from file
db.register_schema_from_file("schema.json")

# Insert entity
entity_id = db.insert(tenant_id="default", table="people", data={"name": "Alice"})

# Query with SQL
results = db.query_sql(tenant_id="default", sql="SELECT * FROM people WHERE age > 30")

# Count entities
count = db.count(tenant_id="default", table="people", include_deleted=False)

# List all entities
entities = db.list(tenant_id="default", table="people", include_deleted=False, limit=None)

# Update entity
db.update(tenant_id="default", key="alice@company.com", table="people", data={...})

# Delete entity (soft delete)
db.delete(tenant_id="default", key="alice@company.com", table="people")

# Semantic search (async)
results = await db.search_async(
    tenant_id="default",
    table="articles",
    query="machine learning basics",
    top_k=5
)
# Returns: List[(entity: dict, score: float)]
```

### Async Operations

For async operations, use `asyncio`:

```python
import asyncio

async def main():
    db = Database("./my-db")

    # Async insert
    entity_id = await db.insert_async("default", "table", data)

    # Async search
    results = await db.search_async("default", "table", "query", top_k=10)

    # Process results
    for entity, score in results:
        print(f"{entity['title']}: {score}")

asyncio.run(main())
```

## Schema Format

Schemas use JSON Schema with Pydantic extensions:

```json
{
  "title": "Article",
  "version": "1.0.0",
  "short_name": "articles",
  "description": "Articles for semantic search",
  "properties": {
    "title": {"type": "string"},
    "content": {"type": "string"},
    "category": {"type": "string"}
  },
  "required": ["title", "content"],
  "json_schema_extra": {
    "embedding_fields": ["content"],
    "embedding_provider": "default",
    "indexed_fields": ["category"],
    "key_field": "title",
    "category": "user"
  }
}
```

**Key configuration fields:**
- `embedding_fields`: Fields to generate vector embeddings for
- `embedding_provider`: "default" (uses P8_DEFAULT_EMBEDDING) or "openai:model-name"
- `indexed_fields`: Fields to create RocksDB indexes for (fast WHERE queries)
- `key_field`: Field to use for deterministic UUID generation (enables idempotent inserts)
- `category`: "system" or "user"

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `P8_DB_PATH` | `~/.p8/db` | Database storage path |
| `P8_DEFAULT_EMBEDDING` | (none) | Default embedding provider<br>Examples: `local:all-MiniLM-L6-v2`, `openai:text-embedding-3-small` |
| `OPENAI_API_KEY` | (none) | OpenAI API key for embeddings and LLM |
| `P8_DEFAULT_LLM` | `gpt-4-turbo` | Default LLM for natural language queries |

## Performance Tips

1. **Use indexed fields** - Add frequently queried fields to `indexed_fields` in schema
2. **Batch inserts** - Insert multiple entities in a loop for bulk loading
3. **Async for I/O-bound ops** - Use `insert_async` and `search_async` for better concurrency
4. **Local embeddings** - For offline use and faster embedding generation
5. **Limit results** - Use `top_k` parameter to limit search results

## Troubleshooting

### Import Error
```
ImportError: No module named 'percolate_rocks'
```
**Solution:** Run `maturin develop --release` to build and install the extension

### Schema Validation Error
```
Schema validation failed: "field" is required
```
**Solution:** Ensure all fields marked as `"required"` in schema are present in inserted data

### Embedding Error
```
Embedding provider not configured
```
**Solution:** Set `P8_DEFAULT_EMBEDDING` or `OPENAI_API_KEY` environment variable

### Lock Error
```
IO error: lock hold by current process
```
**Solution:** Ensure only one Database instance accesses the same path at a time

## Next Steps

- See `docs/sql-dialect.md` for supported SQL syntax
- See `QUERY_TEST_RESULTS.md` for tested query patterns
- See main project README for CLI usage

## License

MIT
