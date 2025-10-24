# Complete user flow

This document shows the complete end-to-end flow for using rem-db from installation to querying.

## Installation

```bash
# Option 1: From PyPI (Python users)
pip install percolate-rocks

# Option 2: Build CLI from source
cargo build --release --bin rem-db
```

## Flow 1: Default (local embeddings)

### Step 1: Initialize database

```bash
rem-db init my-database
```

**What happens:**
- Creates RocksDB database at `~/.p8/db/my-database`
- Registers database in `~/.p8/config.json`
- Registers system schemas (resources, etc.)
- Inserts sample entities with embeddings
- Uses local model (all-MiniLM-L6-v2, 384 dims)
- Downloads model (~100MB) to `~/.p8/models/` on first run

**Output:**
```
Initializing database...
  ✓ Registered schema: resources
✓ Registered 1 system schemas:
  • resources (resources)

Creating system entities...
  ✓ Created resource: a1b2c3d4-e5f6-7890-abcd-ef1234567890

✓ Database initialized: my-database
   Path: /Users/you/.p8/db/my-database
```

### Step 2: List all databases

```bash
rem-db list
```

**Output:**
```
Registered databases:

  • my-database
    Path: /Users/you/.p8/db/my-database
    Tenant: my-database
```

### Step 3: Query with SQL

```bash
rem-db query -d my-database "SELECT * FROM resources"
```

**What happens:**
- Resolves database name from config
- Executes SQL-like query (simplified for now)
- Returns all entities of type "resources"

**Output:**
```
→ Executing query...
Note: Full SQL support coming soon. Showing all entities for now.

✓ Found 1 entities:
  • a1b2c3d4-e5f6-7890-abcd-ef1234567890 (type: resources)
```

### Step 4: Search with natural language

```bash
rem-db search -d my-database "vector embeddings database" --min-score 0.3
```

**What happens:**
- Generates embedding for search query
- Computes cosine similarity with all entity embeddings
- Returns top matches above min-score threshold

**Output:**
```
→ Searching for: vector embeddings database

✓ Found 1 results:

1. Resource Schema (score: 0.588)
   The Resource schema stores chunked, embedded content from documents.
   It supports semantic search via vector embeddings...
```

### Step 5: List schemas

```bash
rem-db schemas -d my-database
```

**Output:**
```
✓ Database: my-database
Registered schemas:

  • resources
    Indexed fields: ["category"]
    Embedding fields: ["content"]
```

## Flow 2: OpenAI embeddings

### Step 1: Configure OpenAI

```bash
export P8_DEFAULT_EMBEDDING="text-embedding-3-small"
export OPENAI_API_KEY="sk-..."
```

### Step 2: Initialize database

```bash
rem-db init my-database-openai
```

**What happens:**
- Creates RocksDB database at `~/.p8/db/my-database-openai`
- Detects P8_DEFAULT_EMBEDDING → uses OpenAI
- Calls OpenAI API to generate embeddings (1536 dims)
- No model downloads required!

**Output:**
```
Initializing database...
  ✓ Registered schema: resources
✓ Registered 1 system schemas:
  • resources (resources)

Creating system entities...
  ✓ Created resource: b2c3d4e5-f6a7-8901-bcde-f12345678901

✓ Database initialized: my-database-openai
   Path: /Users/you/.p8/db/my-database-openai
```

### Step 3: Query (same as Flow 1)

```bash
rem-db query -d my-database-openai "SELECT * FROM resources"
```

### Step 4: Search (same as Flow 1, but with OpenAI embeddings)

```bash
rem-db search -d my-database-openai "vector embeddings database" --min-score 0.3
```

**What happens:**
- Query embedding generated via OpenAI API
- Search uses OpenAI embeddings (1536 dims)
- Typically better semantic understanding

## Flow 3: Custom path

You can override the default path with `--path`:

```bash
rem-db init my-db --path /custom/path/to/db
```

**What happens:**
- Creates database at custom path instead of `~/.p8/db/<name>`
- Still registers in config for easy access by name

## Python API flow

### Flow 1: Without embeddings (fastest)

```python
from percolate_rocks import REMDatabase

# Create database (no embeddings)
db = REMDatabase("my-app", "./db", enable_embeddings=False)

# Register schema
db.register_schema("users", {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "email": {"type": "string"}
    }
})

# Insert data
user_id = db.insert("users", {"name": "Alice", "email": "alice@example.com"})

# Query
user = db.get(user_id)
print(user["properties"]["name"])
```

### Flow 2: With OpenAI embeddings

```python
import asyncio
import os
from percolate_rocks import REMDatabase

async def main():
    # Configure OpenAI
    os.environ["P8_DEFAULT_EMBEDDING"] = "text-embedding-3-small"
    os.environ["OPENAI_API_KEY"] = "sk-..."

    # Create database
    db = REMDatabase("my-app", "./db", enable_embeddings=True)

    # Register schema with embedding fields
    db.register_schema("documents", {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"}
        }
    }, embedding_fields=["content"])

    # Insert with automatic embedding
    doc_id = await db.insert_with_embedding("documents", {
        "title": "Getting Started",
        "content": "This is a guide to using percolate-rocks..."
    })

    print(f"✓ Document inserted with OpenAI embeddings: {doc_id}")

asyncio.run(main())
```

### Flow 3: With local embeddings

```python
import asyncio
from percolate_rocks import REMDatabase

async def main():
    # Don't set P8_DEFAULT_EMBEDDING → uses local model
    db = REMDatabase("my-app", "./db", enable_embeddings=True)

    # Same as OpenAI flow, but uses local model
    db.register_schema("documents", {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"}
        }
    }, embedding_fields=["content"])

    # Insert with local embedding
    doc_id = await db.insert_with_embedding("documents", {
        "title": "Getting Started",
        "content": "This is a guide to using percolate-rocks..."
    })

    print(f"✓ Document inserted with local embeddings: {doc_id}")

asyncio.run(main())
```

## Key differences between providers

| Feature | Local | OpenAI |
|---------|-------|--------|
| Model download | Yes (~100MB) | No |
| API key required | No | Yes |
| Embedding dimensions | 384 | 1536 or 3072 |
| Offline usage | Yes | No |
| Cost | Free | $0.00002/1K tokens |
| Quality | Good | Excellent |
| Speed | Fast (local) | Depends on API latency |

## Environment variables

| Variable | Default | Purpose |
|----------|---------|----|
| `P8_DEFAULT_EMBEDDING` | Not set (uses local) | Embedding model name |
| `OPENAI_API_KEY` | Not set | OpenAI API key |
| `HF_HOME` | `~/.p8/models` | Local model cache directory |

## Configuration files

**~/.p8/config.json:**
```json
{
  "databases": {
    "my-database": {
      "name": "my-database",
      "path": "/Users/you/.p8/db/my-database",
      "tenant": "my-database"
    }
  }
}
```

This config file is automatically managed by the CLI and allows you to reference databases by name instead of path.

## Complete example: RAG application

```python
import asyncio
import os
from percolate_rocks import REMDatabase

async def main():
    # Setup
    os.environ["P8_DEFAULT_EMBEDDING"] = "text-embedding-3-small"
    os.environ["OPENAI_API_KEY"] = "sk-..."

    db = REMDatabase("rag-app", "./rag-db", enable_embeddings=True)

    # Register schema
    db.register_schema("knowledge", {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "text": {"type": "string"},
            "metadata": {"type": "object"}
        },
        "required": ["text"]
    }, embedding_fields=["text"])

    # Ingest documents
    docs = [
        {"source": "docs.md", "text": "Percolate is a REM database..."},
        {"source": "api.md", "text": "The REMDatabase class provides..."},
        {"source": "config.md", "text": "Configure with environment variables..."}
    ]

    for doc in docs:
        await db.insert_with_embedding("knowledge", doc)

    print("✓ Knowledge base populated")

    # Query: Get all documents
    all_docs = db.scan_by_type("knowledge")
    print(f"✓ Total documents: {len(all_docs)}")

    # TODO: Semantic search (coming soon)
    # results = db.search_semantic("How do I configure embeddings?", top_k=3)

asyncio.run(main())
```

## Troubleshooting

### "OPENAI_API_KEY environment variable required"

You're trying to use an OpenAI model without setting the API key:

```bash
export OPENAI_API_KEY="sk-..."
```

Or switch to local model:

```bash
unset P8_DEFAULT_EMBEDDING  # Uses local model
```

### "Database 'xyz' not found"

The database hasn't been initialized yet:

```bash
rem-db init xyz
```

Or check all registered databases:

```bash
rem-db list
```

### "Failed to load model"

Local model download failed. Options:

1. Check internet connection and retry
2. Use OpenAI instead:
   ```bash
   export P8_DEFAULT_EMBEDDING="text-embedding-3-small"
   export OPENAI_API_KEY="sk-..."
   ```

### Model downloads slowly

Local model is ~100MB. First download takes a few minutes. Subsequent runs are instant (cached to `~/.p8/models/`).

To pre-download:
```bash
# Run init once to cache the model
rem-db init preload-test
rm -rf ~/.p8/db/preload-test  # Clean up
```

## Summary

**Complete user flow:**

1. **Install**: `pip install percolate-rocks` or build from source
2. **Configure**: Set environment variables (optional for OpenAI)
3. **Init**: `rem-db init <name>` to create database with sample data
4. **List**: `rem-db list` to see all databases
5. **Query**: `rem-db query -d <name>` for SQL-like queries
6. **Search**: `rem-db search -d <name>` for semantic search
7. **Schemas**: `rem-db schemas -d <name>` to list all schemas

**Three modes:**
- **No embeddings**: Fastest, no setup
- **Local embeddings**: Privacy-first, offline-capable
- **OpenAI embeddings**: Best quality, no downloads

**All modes work seamlessly with the same API!**

## CLI command reference

### `rem-db init <name> [--path <path>]`

Initialize a new database.

- `<name>`: Database name (required)
- `--path`: Custom path (optional, defaults to `~/.p8/db/<name>`)

### `rem-db list`

List all registered databases.

### `rem-db query -d <name> <query> [--format <format>]`

Execute SQL query.

- `-d, --db`: Database name (required)
- `<query>`: SQL query string (required)
- `--format`: Output format: `table` or `json` (default: `table`)

### `rem-db search -d <name> <query> [--top-k <k>] [--min-score <score>]`

Natural language semantic search.

- `-d, --db`: Database name (required)
- `<query>`: Search query (required)
- `--top-k`: Number of results (default: 10)
- `--min-score`: Minimum similarity score (default: 0.7)

### `rem-db schemas -d <name>`

List all schemas in database.

- `-d, --db`: Database name (required)

### `rem-db export -d <name> <table> --output <file>`

Export table to Parquet (JSON for now).

- `-d, --db`: Database name (required)
- `<table>`: Table/schema name (required)
- `--output`: Output file path (required)
