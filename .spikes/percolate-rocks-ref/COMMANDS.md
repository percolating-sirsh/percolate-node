# REM Database CLI Commands

## Overview

The `rem-db` CLI provides commands for initializing, querying, and managing the REM database.

## Installation

```bash
cargo build --release --no-default-features --bin rem-db
```

The binary will be at `target/release/rem-db`.

## Commands

### init - Initialize Database

Initialize a new database with system schemas and example entities.

```bash
rem-db init --path <path> --tenant <tenant-id>
```

**Options:**
- `--path`: Database path (default: `.rem-db`)
- `--tenant`: Tenant ID (default: `default`)

**Example:**
```bash
rem-db init --path mydb --tenant production
```

**Output:**
```
Initializing database...
  ✓ Registered schema: resources
✓ Registered 1 system schemas:
  • resources (resources)

Creating system entities...
  ✓ Created resource: c846fa9e-9178-42e2-8600-788705d2480d

✓ Database initialized at: mydb
```

### query - Execute SQL Query

Query the database using SQL (simplified for now - shows all entities).

```bash
rem-db query <query> --path <path> --tenant <tenant-id> --format <format>
```

**Options:**
- `--path`: Database path (default: `.rem-db`)
- `--tenant`: Tenant ID (default: `default`)
- `--format`: Output format - `table` or `json` (default: `table`)

**Example:**
```bash
rem-db query "SELECT * FROM resources" --path mydb
```

**Output:**
```
→ Executing query...
Note: Full SQL support coming soon. Showing all entities for now.

✓ Found 1 entities:
  • c846fa9e-9178-42e2-8600-788705d2480d (type: resources)
```

### search - Natural Language Semantic Search

Search using natural language queries with vector embeddings.

```bash
rem-db search <query> --path <path> --tenant <tenant-id> --top-k <n> --min-score <score>
```

**Options:**
- `--path`: Database path (default: `.rem-db`)
- `--tenant`: Tenant ID (default: `default`)
- `--top-k`: Number of results to return (default: `10`)
- `--min-score`: Minimum similarity score (default: `0.7`)

**Example:**
```bash
rem-db search "vector embeddings semantic search" --path mydb --min-score 0.3
```

**Output:**
```
→ Searching for: vector embeddings semantic search

✓ Found 1 results:

1. Resource Schema (score: 0.588)
   The Resource schema stores chunked, embedded content from documents. 
   It supports semantic search via vector embeddings...
```

### export - Export Data to JSON/Parquet

Export entities from a table to JSON (Parquet support coming soon).

```bash
rem-db export <table> --output <file> --path <path> --tenant <tenant-id>
```

**Options:**
- `--output`: Output file path
- `--path`: Database path (default: `.rem-db`)
- `--tenant`: Tenant ID (default: `default`)

**Example:**
```bash
rem-db export resources --output data.parquet --path mydb
```

**Output:**
```
→ Exporting table 'resources' to data.parquet
Note: Parquet export coming soon. Exporting as JSON for now.
✓ Exported 1 entities to data.json
```

### schemas - List Schemas

List all registered schemas in the database.

```bash
rem-db schemas --path <path> --tenant <tenant-id>
```

**Options:**
- `--path`: Database path (default: `.rem-db`)
- `--tenant`: Tenant ID (default: `default`)

**Example:**
```bash
rem-db schemas --path mydb
```

## End-to-End Example

```bash
# 1. Initialize database
rem-db init --path demo-db

# 2. Query all entities
rem-db query "SELECT * FROM resources" --path demo-db

# 3. Search semantically
rem-db search "database with embeddings" --path demo-db --min-score 0.3

# 4. Export data
rem-db export resources --output demo.json --path demo-db

# 5. View exported data
cat demo.json | jq '.[0] | {name: .properties.name, content: .properties.content[:100]}'
```

## Features Implemented

- ✅ Database initialization with system schemas
- ✅ Entity storage with automatic embedding generation
- ✅ Natural language semantic search using vector embeddings
- ✅ Query command (basic - full SQL coming soon)
- ✅ Export to JSON (Parquet coming soon)
- ✅ Schema listing

## Coming Soon

- Full SQL query support with WHERE, JOIN, ORDER BY
- Parquet export using Apache Arrow
- Schema persistence across database sessions
- HNSW vector index for faster similarity search
- Replication support with gRPC
