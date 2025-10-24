# Percolate REM Database Specification v0.1

## Overview

The Percolate REM Database is a schema-driven embedded database implementing the **REM model**: Resources, Entities, and Moments.

### Core Concepts

1. **Resources** - Chunked, embedded content from documents
2. **Entities** - Domain knowledge nodes with properties and relationships
3. **Moments** - Temporal classifications with start/end timestamps

### Architecture

- **Storage:** RocksDB key-value store (single-tenant isolation)
- **Schema:** Pydantic models serialized as JSON Schema
- **Embeddings:** Multi-provider support (local models, OpenAI, Cohere)
- **Queries:** SQL-like syntax with semantic similarity search

## Built-in Types

The database has four core built-in types that are automatically registered during initialization:

1. **Schema** - Metadata about registered entity types (tables)
2. **Resource** - Chunked document content with embeddings
3. **File** - Original files before chunking into resources
4. **Moment** - Temporal classification with time ranges
5. **QueryResult** - LLM query plan output (not stored, returned by `--plan` flag)

## System Fields

**Important:** System fields and embeddings are **NOT** included in Pydantic models. They are added automatically by the database when entities are inserted.

### Fields Added by Database

All entities get these fields automatically:

```python
# System fields (NOT in Pydantic model, added by database)
id: UUID                            # Unique identifier (auto-generated)
created_at: datetime                # Creation timestamp (UTC, auto-generated)
modified_at: datetime               # Last modification timestamp (UTC, auto-updated)
deleted_at: Optional[datetime]      # Soft delete timestamp (UTC, nullable)
edges: list[str]                    # Graph edges (entity IDs or qualified keys)

# Embedding fields (added if schema has embedding_fields configured)
embedding: Optional[list[float]]    # Vector embedding (from embedding_fields)
embedding_alt: Optional[list[float]] # Alternative embedding (if P8_ALT_EMBEDDING set)
```

### Pydantic Model Example

**User-defined model** (what you write):

```python
from pydantic import BaseModel, Field, ConfigDict

class Person(BaseModel):
    """A person entity."""

    model_config = ConfigDict(
        json_schema_extra={
            "fully_qualified_name": "myapp.Person",
            "version": "1.0.0",
            "category": "user",
            "indexed_fields": ["email", "role"],
            "embedding_fields": ["bio"],  # Auto-embed 'bio' field
            "embedding_provider": "default",  # Use P8_DEFAULT_EMBEDDING
            "key_field": "email"  # Use 'email' as unique key
        }
    )

    # Only user-defined fields in model
    name: str = Field(description="Full name")
    email: str = Field(description="Email address")
    role: str = Field(description="Job role")
    bio: Optional[str] = Field(None, description="Biography (will be embedded)")
```

**Stored entity** (what database saves):

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "person",
  "created_at": "2025-10-24T10:30:00Z",
  "modified_at": "2025-10-24T10:30:00Z",
  "deleted_at": null,
  "edges": [],
  "properties": {
    "name": "Alice Smith",
    "email": "alice@example.com",
    "role": "engineer",
    "bio": "Software engineer with 10 years experience..."
  },
  "embedding": [0.1, 0.2, -0.3, ...],
  "embedding_alt": null
}
```

**Key differences:**
- ✅ User models: Only business logic fields
- ✅ System fields: Added automatically by database
- ✅ Embeddings: Generated from `embedding_fields` configuration
- ✅ Cleaner models: No boilerplate system fields

## Key Generation & Lookup

### ID Field Precedence

When inserting entities, the database generates a unique key using field precedence.

**Default precedence order:** `uri` → `key` → `name`

1. If `uri` field exists → use as unique key
2. Else if `key` field exists → use as unique key
3. Else if `name` field exists → use as unique key
4. Else → generate new random UUID

**Override:** Set `key_field` in `model_config.json_schema_extra` to specify a custom field:

```python
model_config = ConfigDict(
    json_schema_extra={
        "key_field": "email"  # Use 'email' field as unique key
    }
)
```

**Deterministic UUID Generation:**

When a key field is used, the database generates a deterministic UUID from the field value:

```python
# Example: email="alice@example.com" as key
tenant_key = f"{tenant_id}:{table}:{key_value}"
# "default:person:alice@example.com"

uuid = UUID(blake3(tenant_key).digest()[:16])
# Deterministic: Same input → same UUID
```

**Benefits:**
- ✅ Upserts work automatically (same key → same UUID)
- ✅ No duplicate entities with same key
- ✅ Idempotent inserts
- ✅ Cross-table references stable

### Schema-Agnostic Lookup

The `db lookup <key>` command scans all entity types and returns **all entities** matching the key, even though keys are unique per entity.

**Example:**
```bash
# Returns all entities with key="TAP-1234" across all tables
db lookup TAP-1234
```

## Pydantic Models

### 1. Schema (Metadata Type)

Stores metadata about registered entity types (tables). The `description` field is used for embedding-based semantic search.

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Optional

class MCPTool(BaseModel):
    """MCP tool reference for schema operations."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    server: Optional[str] = Field(None, description="MCP server name")
    usage: Optional[str] = Field(None, description="Usage instructions")


class Schema(BaseModel):
    """Schema definition for a REM entity type (agent-let aware).

    This stores the full Pydantic JSON schema export, following the carrier
    agent-let pattern. The JSON schema includes:
    - System prompt (from model docstring) in 'description'
    - Field definitions with types, descriptions, constraints in 'properties'
    - Nested models in '$defs'
    - Agent-let metadata in top-level fields (from model_config.json_schema_extra)
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",  # Allow extra fields from JSON schema
        populate_by_name=True,
        json_schema_extra={
            "fully_qualified_name": "rem.system.Schema",
            "short_name": "schema",
            "version": "1.0.0",
            "category": "system",
            "indexed_fields": ["name", "category"],
            "embedding_provider": "default",
            "key_field": "name"
        }
    )

    # Core identification (from model_config.json_schema_extra)
    name: str = Field(description="Schema name (table name)")
    fully_qualified_name: Optional[str] = Field(
        None, description="Fully qualified name (e.g., 'carrier.agents.module.Class')"
    )
    short_name: Optional[str] = Field(None, description="Short name for URI")
    version: Optional[str] = Field(None, description="Semantic version (e.g., '1.0.0')")
    category: str = Field(
        default="user",
        description="Schema category (system, agents, public, user)"
    )

    # JSON Schema standard fields
    title: Optional[str] = Field(None, description="Schema title (class name)")
    description: Optional[str] = Field(
        None, description="System prompt from model docstring (auto-embedded)"
    )
    type: str = Field(default="object", description="JSON schema type")
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Field definitions (JSON schema)"
    )
    required: list[str] = Field(default_factory=list, description="Required field names")
    defs: Optional[dict[str, Any]] = Field(
        None, alias="$defs", description="Nested model definitions"
    )

    # Agent-let metadata (from model_config.json_schema_extra)
    indexed_fields: list[str] = Field(
        default_factory=list, description="Fields to create indexes on"
    )
    tools: list[MCPTool] = Field(
        default_factory=list, description="MCP tools available for this entity type"
    )
```

**Key field:** `name` (unique per schema)

**Embedded field:** `description` (system prompt for semantic schema search)

---

### 2. Resource (Chunked Content)

Stores chunked document content with vector embeddings. Resources are created when ingesting files.

```python
from datetime import UTC, datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Optional


def utc_now() -> datetime:
    """Get current UTC time with timezone."""
    return datetime.now(UTC)


class SystemFields(BaseModel):
    """System-managed fields for all entities."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: str}
    )

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    created_at: datetime = Field(default_factory=utc_now, description="Creation timestamp")
    modified_at: datetime = Field(default_factory=utc_now, description="Last modification timestamp")
    deleted_at: Optional[datetime] = Field(None, description="Soft delete timestamp")
    edges: list[str] = Field(
        default_factory=list,
        description="Graph edges (other entity IDs or qualified keys)"
    )


class Resource(BaseModel):
    """Chunked, embedded content from documents.

    Used for general-purpose document storage with vector embeddings.
    System fields (id, created_at, etc.) and embeddings are added automatically.
    """

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: str},
        json_schema_extra={
            "fully_qualified_name": "rem.system.Resource",
            "short_name": "resource",
            "version": "1.0.0",
            "indexed_fields": ["category", "name"],
            "category": "system",
            "embedding_fields": ["content"],  # Fields to auto-embed
            "embedding_provider": "default",  # Use P8_DEFAULT_EMBEDDING
            "key_field": "uri"  # Key precedence: uri first
        }
    )

    # User-defined fields (in Pydantic model)
    name: str = Field(description="Resource name or title")
    content: str = Field(description="Full text content (will be auto-embedded)")
    category: Optional[str] = Field(None, description="Resource category/type")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata")
    ordinal: int = Field(default=0, description="Chunk ordinal within source file")
    uri: str = Field(description="Source URI or file path")

    # Note: System fields and embeddings NOT in model, added by database:
    # - id: UUID (auto-generated)
    # - created_at: datetime (auto-generated)
    # - modified_at: datetime (auto-generated)
    # - deleted_at: Optional[datetime] (soft delete)
    # - edges: list[str] (graph relationships)
    # - embedding: list[float] (auto-generated from 'content' field)
    # - embedding_alt: Optional[list[float]] (if P8_ALT_EMBEDDING set)
```

**Key field:** `uri` + `ordinal` (composite key for chunks)

**Embedded field:** `content` (auto-embedded using default provider)

**Example:**
- File: `/docs/guide.md` → URI: `file:///docs/guide.md`
- Chunk 1: `uri="file:///docs/guide.md"`, `ordinal=0`
- Chunk 2: `uri="file:///docs/guide.md"`, `ordinal=1`

---

### 3. File (Document Record)

Records original files before they are chunked into resources. Maintains parent-child relationship via edges.

```python
class File(BaseModel):
    """Original file record before chunking into resources.

    Maintains parent-child relationship to chunks via edges.
    System fields (id, created_at, etc.) are added automatically.
    """

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: str},
        json_schema_extra={
            "fully_qualified_name": "rem.system.File",
            "short_name": "file",
            "version": "1.0.0",
            "indexed_fields": ["uri", "file_type", "status"],
            "category": "system",
            "key_field": "uri"  # Key precedence: uri first
        }
    )

    # User-defined fields (in Pydantic model)
    uri: str = Field(description="File URI (unique)")
    name: str = Field(description="File name (e.g., 'guide.md')")
    file_type: str = Field(description="File type (e.g., 'pdf', 'markdown', 'text')")
    size_bytes: int = Field(description="File size in bytes")
    content_hash: Optional[str] = Field(None, description="SHA256 hash of content")
    status: str = Field(
        default="pending",
        description="Processing status (pending, processing, completed, failed)"
    )
    chunk_count: int = Field(default=0, description="Number of chunks (resources) created")
    metadata: dict[str, Any] = Field(default_factory=dict, description="File metadata")

    # Note: System fields added by database (NOT in Pydantic model):
    # - id: UUID (auto-generated)
    # - created_at: datetime (auto-generated)
    # - modified_at: datetime (auto-generated)
    # - deleted_at: Optional[datetime] (soft delete)
    # - edges: list[str] (references to child Resource chunks)
```

**Key field:** `uri` (unique per file)

**Embedded field:** Not auto-embedded (use summary for embedding if needed)

**Relationship:**
- `File.edges` contains UUIDs of child `Resource` entities
- `Resource.uri` references parent `File.uri`

**Example:**
```python
# File record
file = File(
    uri="file:///docs/guide.md",
    name="guide.md",
    file_type="markdown",
    size_bytes=10240,
    status="completed",
    chunk_count=5,
    edges=["uuid1", "uuid2", "uuid3", "uuid4", "uuid5"]  # Resource IDs
)

# Resource records (chunks)
chunk1 = Resource(
    uri="file:///docs/guide.md",
    ordinal=0,
    name="guide.md - Chunk 1",
    content="Introduction to..."
)
```

---

### 4. Moment (Temporal Classification)

A temporal subclass of resources with start/end timestamps for narrative structure.

```python
class Moment(BaseModel):
    """Temporal classification with time range.

    Used for narrative structure, event timelines, and temporal queries.
    System fields (id, created_at, etc.) and embeddings are added automatically.
    """

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: str},
        json_schema_extra={
            "fully_qualified_name": "rem.system.Moment",
            "short_name": "moment",
            "version": "1.0.0",
            "indexed_fields": ["moment_type", "start_time", "end_time"],
            "category": "system",
            "embedding_fields": ["description"],  # Fields to auto-embed
            "embedding_provider": "default",  # Use P8_DEFAULT_EMBEDDING
            "key_field": "name"  # Key precedence: name (since no uri)
        }
    )

    # User-defined fields (in Pydantic model)
    name: str = Field(description="Moment name or title")
    moment_type: str = Field(description="Moment type (event, period, milestone)")
    start_time: datetime = Field(description="Start timestamp")
    end_time: Optional[datetime] = Field(None, description="End timestamp (None for ongoing)")
    classifications: list[str] = Field(
        default_factory=list,
        description="Classification tags (e.g., 'meeting', 'sprint', 'release')"
    )
    description: Optional[str] = Field(None, description="Moment description (will be auto-embedded)")
    resource_refs: list[UUID] = Field(
        default_factory=list,
        description="Referenced resource IDs"
    )
    entity_refs: list[UUID] = Field(
        default_factory=list,
        description="Referenced entity IDs"
    )
    parent_moment_id: Optional[UUID] = Field(
        None,
        description="Parent moment ID (for nested time periods)"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Moment metadata")

    # Note: System fields and embeddings NOT in model, added by database:
    # - id: UUID (auto-generated)
    # - created_at: datetime (auto-generated)
    # - modified_at: datetime (auto-generated)
    # - deleted_at: Optional[datetime] (soft delete)
    # - edges: list[str] (graph relationships)
    # - embedding: list[float] (auto-generated from 'description' field)
```

**Key field:** `id` (UUID)

**Embedded field:** `description` (auto-embedded using default provider)

**Example:**
```python
# Sprint moment (2 weeks)
sprint = Moment(
    name="Sprint 42",
    moment_type="period",
    start_time=datetime(2025, 10, 1),
    end_time=datetime(2025, 10, 14),
    classifications=["sprint", "development"],
    description="Two-week sprint focusing on database performance",
    resource_refs=[doc1_id, doc2_id],  # Sprint docs
    entity_refs=[task1_id, task2_id]   # Sprint tasks
)

# Meeting moment (1 hour)
meeting = Moment(
    name="Planning Meeting",
    moment_type="event",
    start_time=datetime(2025, 10, 1, 10, 0),
    end_time=datetime(2025, 10, 1, 11, 0),
    classifications=["meeting", "planning"],
    parent_moment_id=sprint.id,  # Nested in sprint
    resource_refs=[agenda_id, notes_id]
)
```

---

### 5. QueryResult (LLM Output Schema)

Structured output from the natural language query builder. Used when `--plan` flag is specified.

```python
class QueryResult(BaseModel):
    """Structured output from LLM query builder.

    Returned when using --plan flag on natural language search.
    Contains generated query, confidence score, and fallback strategies.
    """

    query_type: str = Field(
        description="Type of query: 'entity_lookup', 'sql', 'vector', 'hybrid', or 'graph'"
    )
    query: str = Field(
        description="Generated query string (SQL or lookup command)"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in query correctness (0.0-1.0)"
    )
    explanation: Optional[str] = Field(
        None,
        description="Explanation of query reasoning (only if confidence < 0.8)"
    )
    follow_up_question: Optional[str] = Field(
        None,
        description="Optional follow-up question for staged retrieval"
    )
    fallback_query: Optional[str] = Field(
        None,
        description="Fallback query if primary returns no results"
    )
```

**Query Types:**

| Type | Description | Example |
|------|-------------|---------|
| `entity_lookup` | Global key search across all tables | `"what is TAP-1234?"` |
| `sql` | Structured query with WHERE predicates | `"resources with category tutorial"` |
| `vector` | Semantic similarity search | `"find resources about authentication"` |
| `hybrid` | Combination of semantic + filters | `"active Python resources from last week"` |
| `graph` | Relationship traversal (future) | `"who worked on this feature?"` |

**Example Usage:**

```python
from rem_db import REMDatabase

db = REMDatabase(tenant_id="default", path="./db")

# Get query plan (without execution)
result = db.query_natural_language(
    "find resources about Python programming",
    table="resources",
    plan_only=True  # Returns QueryResult, doesn't execute
)

print(f"Query type: {result['query_type']}")
print(f"Query: {result['query']}")
print(f"Confidence: {result['confidence']}")

if result['confidence'] < 0.8:
    print(f"Warning: {result['explanation']}")

# Execute the query if confident
if result['confidence'] > 0.7:
    actual_results = db.sql(result['query'])
```

## Embedding Configuration

### Field-Level Embedding

Any field can be configured for embedding using `embedding_provider` in `model_config.json_schema_extra`:

```python
model_config = ConfigDict(
    json_schema_extra={
        "embedding_provider": "default",  # Uses default from environment
        # OR
        "embedding_provider": "text-embedding-3-small",  # Specific model
    }
)
```

### Embedding Provider Priority

1. **Field-level:** Check field's `embedding_provider` annotation
2. **Schema-level:** Check `model_config.json_schema_extra["embedding_provider"]`
3. **Default:** Use `P8_DEFAULT_EMBEDDING` environment variable
4. **Fallback:** Use local model (`all-MiniLM-L6-v2`)

### Auto-Embedded Fields

Fields are automatically embedded if they match:
- Field name is `content` or `description`
- Field type is `str`
- Schema has `embedding_provider` configured

## Database Operations

### Upsert Behavior

When upserting data, the database uses **batch insert** based on the ID field (determined by key precedence).

**Example:**
```python
# First insert
db.insert("resources", {
    "uri": "file:///doc.txt",
    "ordinal": 0,
    "name": "Doc chunk 1",
    "content": "First paragraph..."
})

# Upsert (same uri + ordinal) → updates existing
db.insert("resources", {
    "uri": "file:///doc.txt",
    "ordinal": 0,
    "name": "Doc chunk 1 (updated)",
    "content": "Updated first paragraph..."
})
```

## CLI Commands

### Database Initialization

```bash
# Initialize database with default location (~/.p8/db/name.db)
db init <name>

# Initialize with custom path
db init <name> --path /custom/path
```

**What happens:**
1. Creates database directory
2. Registers built-in schemas (Schema, Resource, File, Moment)
3. Inserts schema records into Schema table
4. Embeds schema descriptions using default provider

### Key Lookup

```bash
# Schema-agnostic lookup (searches all entity types)
db lookup <key>
```

**Example:**
```bash
$ db lookup "TAP-1234"
Found 2 entities:
  • Issue (type: issue)     - TAP-1234: Database performance optimization
  • Document (type: file)   - Linked document: TAP-1234-analysis.pdf
```

### SQL Query

```bash
# Standard SQL queries
db query "SELECT * FROM resources WHERE category = 'tutorial'"

# Semantic search in SQL
db query "SELECT * FROM resources WHERE embedding.cosine('Python programming') LIMIT 10"
```

### Natural Language Search

```bash
# Search all schemas (loads and searches schema descriptions)
db search "find resources about authentication"

# Search specific schema
db search "security best practices" --schema=resources

# Show query plan without executing (dry-run)
db search "Python tutorials" --plan
```

**Strategy:**
- Small number of schemas (<10): Load all, semantic search on descriptions
- Large number of schemas (>10): Semantic search schema table first, then query

**Flags:**
- `--plan`: Show generated query plan without executing (returns QueryResult structure)
- `--strategy`: Execution strategy
  - `single`: Execute query in one pass (default)
  - `iterative`: Use LLM iterations for multi-stage retrieval

### Query Plan Structure (--plan flag)

When using `--plan`, the command returns a structured query plan instead of executing:

```json
{
  "query_type": "vector",
  "query": "SELECT * FROM resources WHERE embedding.cosine('Python tutorials') LIMIT 10",
  "confidence": 0.85,
  "explanation": null,
  "follow_up_question": null,
  "fallback_query": "SELECT * FROM resources WHERE category = 'tutorial' LIMIT 10"
}
```

**QueryResult Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `query_type` | string | Query type: `entity_lookup`, `sql`, `vector`, `hybrid`, `graph` |
| `query` | string | Generated SQL/vector query string |
| `confidence` | float | Confidence score 0.0-1.0 (higher is better) |
| `explanation` | string? | Explanation if confidence < 0.8 (why low confidence) |
| `follow_up_question` | string? | Optional follow-up for staged retrieval |
| `fallback_query` | string? | Fallback query if primary returns no results |

**Confidence Levels:**
- `1.0` - Exact ID/key lookup
- `0.8-0.95` - Clear field-based query (SQL)
- `0.6-0.8` - Semantic/vector search
- `< 0.6` - Ambiguous (explanation provided)

**Example:**
```bash
$ db search "find active resources from last week" --plan
{
  "query_type": "hybrid",
  "query": "SELECT * FROM resources WHERE status = 'active' AND created_at >= '2025-10-17' AND embedding.cosine('resources') > 0.7 LIMIT 20",
  "confidence": 0.88,
  "explanation": null,
  "follow_up_question": null,
  "fallback_query": "SELECT * FROM resources WHERE status = 'active' LIMIT 20"
}
```

### File Ingestion

```bash
# Ingest file (creates File record + Resource chunks)
db ingest --file document.pdf

# Ingest folder (recursive)
db ingest --folder /docs
```

**Process:**
1. Create `File` record with status="processing"
2. Parse and chunk document
3. Create `Resource` records for each chunk
4. Generate embeddings for chunks
5. Update `File` with status="completed" and chunk_count
6. Link File → Resources via edges

### Schema Management

```bash
# Add schema from JSON/YAML file
db schema add schema.json

# Add schema from Pydantic class (Python)
db schema add person.py::Person

# List all schemas
db schema list

# Show schema details
db schema show <name>
```

### Batch Upsert

```bash
# Upsert entities from JSONL file
db upsert data.jsonl --schema=resources
```

**JSONL format:**

```jsonl
{"uri": "file:///doc1.txt", "ordinal": 0, "name": "Doc 1", "content": "..."}
{"uri": "file:///doc2.txt", "ordinal": 0, "name": "Doc 2", "content": "..."}
```

### Export to Parquet

```bash
# Export single table to Parquet
db export resources --output data.parquet

# Export all tables to Parquet files
db export --all --output ./exports/

# Export with compression
db export resources --output data.parquet --compression snappy

# Export with filters
db export resources --output data.parquet --where "category = 'tutorial'"
```

**Features:**

- **Single table export**: Export specific schema to Parquet file
- **Bulk export**: Export all registered schemas to separate files
- **Compression**: Supports `snappy`, `gzip`, `brotli`, `lz4`, `zstd`
- **Filtering**: Apply SQL WHERE clause before export
- **Schema preservation**: Maintains Pydantic types in Parquet schema
- **Nested fields**: Handles JSON properties and embeddings as nested columns

**Output structure (--all flag):**

```text
./exports/
├── schema.parquet           # Schema metadata table
├── resources.parquet        # Resources table
├── files.parquet            # Files table
├── moments.parquet          # Moments table
└── custom_schema.parquet    # User-defined schemas
```

**Parquet schema mapping:**

| Pydantic Type | Parquet Type | Notes |
|---------------|--------------|-------|
| `str` | `STRING` | UTF-8 encoded |
| `int` | `INT64` | Signed 64-bit |
| `float` | `DOUBLE` | 64-bit floating point |
| `bool` | `BOOLEAN` | Single bit |
| `datetime` | `TIMESTAMP` | Microsecond precision, UTC |
| `UUID` | `STRING` | Hyphenated format |
| `list[float]` | `LIST<DOUBLE>` | For embeddings |
| `dict[str, Any]` | `STRUCT` | Nested JSON as struct |
| `list[str]` | `LIST<STRING>` | String arrays |

**Example:**

```bash
# Export resources for analytics
db export resources --output resources.parquet --compression snappy

# Export filtered data
db export resources --output recent.parquet \
  --where "created_at >= '2025-10-01'" \
  --compression zstd

# Export all tables for backup
db export --all --output ./backup/$(date +%Y%m%d)/
```

**Use cases:**

- **Analytics**: Export to Parquet for DuckDB, Pandas, or Spark analysis
- **Backup**: Compressed columnar format for efficient storage
- **Data sharing**: Portable format for external tools
- **ETL pipelines**: Export to data lakes (S3, GCS, Azure)
- **Machine learning**: Export embeddings for model training

### Analytical Queries with DuckDB

**Design Philosophy:** REM Database is optimized for transactional operations (CRUD, vector search, graph traversal). For **analytical workloads** (aggregations, JOINs, complex queries), delegate to **DuckDB** via Parquet export.

**Why delegate to DuckDB?**

- **DuckDB specializes in analytics**: Columnar processing, vectorized execution, parallel aggregations
- **REM specializes in transactions**: Real-time inserts, vector similarity, graph traversal
- **Separation of concerns**: Don't replicate DuckDB's functionality in REM
- **Performance**: DuckDB is 10-100x faster on analytical queries over Parquet

**Workflow:**

```bash
# 1. Export REM database to Parquet
db export --all --output ./analytics/

# 2. Run analytical queries in DuckDB
duckdb
```

```sql
-- Attach Parquet files
CREATE VIEW resources AS SELECT * FROM './analytics/resources.parquet';
CREATE VIEW files AS SELECT * FROM './analytics/files.parquet';

-- Analytical queries (fast in DuckDB)
SELECT category, COUNT(*), AVG(length(content)) as avg_length
FROM resources
WHERE created_at >= '2025-10-01'
GROUP BY category
ORDER BY COUNT(*) DESC;

-- Join across tables (DuckDB handles efficiently)
SELECT
    f.name as file_name,
    COUNT(r.id) as chunk_count,
    SUM(length(r.content)) as total_size
FROM files f
LEFT JOIN resources r ON r.uri = f.uri
GROUP BY f.name
ORDER BY chunk_count DESC;

-- Time series analysis
SELECT
    date_trunc('day', created_at) as day,
    COUNT(*) as documents,
    COUNT(DISTINCT category) as categories
FROM resources
GROUP BY day
ORDER BY day;
```

**Recommended Pattern:**

1. **OLTP (REM Database)**: Inserts, updates, vector search, real-time queries
2. **OLAP (DuckDB)**: Aggregations, JOINs, analytics, reporting
3. **Export frequency**: Hourly/daily snapshots to Parquet
4. **Caching**: DuckDB can query Parquet files directly (no import needed)

**Performance Comparison:**

| Query Type | REM Database | DuckDB (Parquet) | Winner |
|------------|--------------|------------------|--------|
| Single entity lookup | ~0.2ms | ~5ms | REM |
| Vector similarity search | ~1ms | N/A | REM |
| Full table scan (100k rows) | ~100ms | ~10ms | DuckDB |
| Aggregation (GROUP BY) | ~500ms | ~20ms | DuckDB |
| Multi-table JOIN | Not supported | ~50ms | DuckDB |
| Complex analytics | Slow | Fast | DuckDB |

**Example: Analytics Pipeline**

```bash
#!/bin/bash
# analytics.sh - Daily analytics export

# Export to Parquet (compressed)
db export --all --output ./analytics/$(date +%Y%m%d)/ --compression zstd

# Run analytics in DuckDB
duckdb analytics.db <<SQL
-- Load today's data
CREATE OR REPLACE VIEW resources AS
  SELECT * FROM './analytics/$(date +%Y%m%d)/resources.parquet';

-- Generate report
COPY (
  SELECT
    category,
    COUNT(*) as count,
    AVG(length(content)) as avg_size
  FROM resources
  GROUP BY category
) TO 'report.csv' (HEADER, DELIMITER ',');
SQL

echo "Analytics complete: report.csv"
```

## Example Workflows

### 1. Ingest Document Collection

```bash
# Initialize database
db init knowledge-base

# Ingest documents (creates Files + Resources)
db ingest --folder /docs/tutorials

# Search semantically
db search "Python type hints" --schema=resources

# Query with filters
db query "SELECT * FROM resources WHERE category = 'tutorial' AND uri LIKE '%python%'"
```

### 2. Custom Schema + Data

```python
# Define custom schema (person.py)
from pydantic import BaseModel, Field

class Person(BaseModel):
    """A person in the organization."""

    name: str = Field(description="Full name")
    email: str = Field(description="Email address")
    role: str = Field(description="Job role")
    team: str = Field(description="Team name")

    model_config = {
        "json_schema_extra": {
            "fully_qualified_name": "myapp.Person",
            "short_name": "person",
            "version": "1.0.0",
            "category": "user",
            "indexed_fields": ["role", "team"],
            "key_field": "email"
        }
    }
```

```bash
# Register schema
db schema add person.py::Person

# Upsert data (JSONL)
cat people.jsonl | db upsert --schema=person

# Query by indexed field (fast)
db query "SELECT * FROM person WHERE role = 'engineer'"

# Schema-agnostic lookup
db lookup "alice@company.com"
```

### 3. Temporal Queries (Moments)

```python
# Create sprint moment
sprint = {
    "name": "Sprint 42",
    "moment_type": "period",
    "start_time": "2025-10-01T00:00:00Z",
    "end_time": "2025-10-14T23:59:59Z",
    "classifications": ["sprint", "development"],
    "description": "Performance optimization sprint"
}

db.insert("moment", sprint)
```

```bash
# Query moments in date range
db query "SELECT * FROM moment WHERE start_time >= '2025-10-01' AND start_time < '2025-11-01'"

# Find moments by classification
db query "SELECT * FROM moment WHERE 'sprint' = ANY(classifications)"
```

## Storage Keys

### RocksDB Key Patterns

```
# Schema storage
schema:{tenant_id}:{schema_name}

# Entity storage (all types)
entity:{tenant_id}:{uuid}

# Resource key (computed from uri + ordinal)
resource:{tenant_id}:{uri_hash}:{ordinal}

# File key (computed from uri)
file:{tenant_id}:{uri_hash}

# Secondary indexes
index:{field_name}:{tenant_id}:{field_value} → [entity_ids...]

# Graph edges
edge:{tenant_id}:{src_uuid}:{dst_uuid}:{edge_type}

# WAL (replication)
wal:{tenant_id}:seq → {current_seq_num}
wal:{tenant_id}:entry:{seq_num} → {wal_entry}
```

## Implementation Details

### Schema-Agnostic Key Lookups

**Problem:** Given a key value (e.g., "bob"), we want to find ALL entities with that key across ALL types (tables) efficiently.

**Two conflicting access patterns:**
1. **Table scans** (common): "Get all resources" → Want prefix: `entity:tenant:TYPE:*`
2. **Global key lookups** (new feature): "Find all 'bob'" → Want prefix: `entity:tenant:KEY:*`

**Can't optimize for both with a single key layout!**

**Solution Approaches:**

| Approach | Table Scan | Key Lookup | Storage | Trade-off |
|----------|-----------|------------|---------|-----------|
| **Column Families (Default)** | O(log n + k) | O(log n + k) | +10% | Dual indexing |
| Multi-Get | O(log n + k) | O(types) batched | 0% | Simple, no overhead |
| Reverse Index | O(log n + k) | O(log n + k) + O(k) | +100% | Double storage |

**Default Choice: Column Families for Reverse Key Lookups**

Column families provide efficient bidirectional indexing:
- Fast table scans: `entity:{tenant}:{type}:*` prefix in main CF
- Fast key lookups: `key:{tenant}:{key_value}:*` prefix in reverse CF
- Minimal storage overhead (~10% for index)
- Native RocksDB prefix scans (no batched multi-get needed)

**Implementation:**
```rust
// Main entity storage
[CF: entities]
  entity:{tenant}:uuid1 → Entity{type: "resource", properties: {...}}
  entity:{tenant}:uuid2 → Entity{type: "schema", properties: {...}}

// Reverse key index (for global lookups)
[CF: key_index]
  key:{tenant}:{key_value}:uuid1 → {type: "resource"}
  key:{tenant}:{key_value}:uuid2 → {type: "schema"}

// When looking up key "bob" globally:
let prefix = format!("key:{}:bob:", tenant_id);
let results = db.iter_prefix(&prefix).collect();  // Single prefix scan
```

**Performance:**
- Global key lookup: ~0.1-0.2ms (single prefix scan)
- Table scan: ~0.1ms (single prefix scan)
- Storage overhead: ~10% (key index is small)

**Alternative: Multi-Get with Type Enumeration**

For deployments where storage is constrained, multi-get is viable:

```rust
// When looking up key "bob" globally:
let types = ["resources", "schema", "moments", "files"];
let keys: Vec<_> = types.iter().map(|t| {
    let uuid = blake3(format!("{}:bob", t)); // Deterministic UUID
    encode_entity_key(tenant, uuid)
}).collect();

// Single RocksDB multi-get call (batched internally)
let results = db.multi_get(keys);
```

**Multi-Get Trade-offs:**
- ✅ No storage overhead (0%)
- ✅ Simple implementation
- ❌ Slower for many types: ~1ms for 10 types (vs ~0.2ms with CF)
- ❌ Requires enumerating all types (not schema-agnostic)

**When to use Multi-Get instead:**
- Very few types (<5 schemas)
- Storage extremely constrained
- Infrequent global key lookups (<10% of queries)

### Natural Language Schema Detection

When a user runs `db search "find Python resources"` without specifying `--schema`, the system must determine which table to query.

**Strategy:**

**Small schema count (<10):**
1. Load all schema descriptions from Schema table
2. Embed user query with default LLM
3. Compute cosine similarity against schema descriptions
4. Select highest-scoring schema

**Large schema count (>10):**
1. Query Schema table with semantic search on `description` field
2. Return top-k candidate schemas
3. Present to user for selection or use highest confidence

**LLM Configuration:**
- Uses `P8_DEFAULT_LLM` environment variable (default: "gpt-4.1")
- Schema descriptions are auto-embedded during `db init`
- Embedding model: `P8_DEFAULT_EMBEDDING` (default: "text-embedding-3-small")

**Example:**
```bash
# User query (no schema specified)
$ db search "find authentication tutorials"

# System process:
# 1. Load schemas: ["resources", "schema", "moments", "files"]
# 2. Embed query: [0.1, 0.5, -0.2, ...]
# 3. Similarity scores:
#    - resources: 0.87 (description: "Chunked, embedded content...")
#    - schema: 0.23 (description: "Metadata about entity types...")
#    - moments: 0.15 (description: "Temporal classifications...")
#    - files: 0.34 (description: "Original file records...")
# 4. Select: resources (highest score)
# 5. Execute query on resources table
```

### Graph Concepts: Edge Storage Strategy

**Edge Representation:**

Edges are relationships between entities. Each entity has an `edges` field containing references to other entities.

**Storage Options:**

**1. Inline Edges (Current - Simple)**
```rust
// Entity properties include edges array
{
  "id": "uuid1",
  "type": "resource",
  "properties": {
    "name": "Tutorial",
    "edges": ["uuid2", "uuid3", "file://doc.pdf"]  // Inline array
  }
}
```

**Pros:**
- ✅ Simple: No separate edge storage
- ✅ Fast: Get entity → get edges in single read
- ✅ No storage overhead

**Cons:**
- ❌ Reverse lookup slow: "Find all edges pointing TO uuid1" requires full scan
- ❌ No edge properties: Can't store edge metadata (weight, type, timestamp)
- ❌ Large edge lists: Slow to update entity with many edges

**2. Column Family for Edges (Recommended for Complex Graphs)**
```rust
// Separate CF for edges with bidirectional indexing
[CF: entities]
  uuid1 → Entity{name: "Tutorial"}

[CF: edges]
  src:uuid1:dst:uuid2:type:references → EdgeData{weight: 1.0, created_at: ...}
  src:uuid1:dst:uuid3:type:depends_on → EdgeData{...}

[CF: edges_reverse]
  dst:uuid2:src:uuid1:type:references → EdgeData{...}
```

**Pros:**
- ✅ Fast bidirectional traversal (forward + reverse lookups)
- ✅ Edge properties: Store metadata on each edge
- ✅ Efficient updates: Don't modify entity when adding edges
- ✅ Native RocksDB prefix scans

**Cons:**
- ❌ Storage overhead: ~50-100 bytes per edge + reverse index
- ❌ Write amplification: 2x writes (forward + reverse)
- ❌ More complex implementation

**3. Hybrid: Inline + CF (Best of Both)**
```rust
// Lightweight edges inline, heavy edges in CF
{
  "properties": {
    "edges": ["uuid2", "uuid3"],  // Lightweight references
  }
}

// Complex edges with properties in CF
[CF: edges]
  src:uuid1:dst:uuid4:type:authored_by → {
    "weight": 0.9,
    "created_at": "2025-10-24T...",
    "metadata": {"role": "primary"}
  }
```

**Decision Matrix:**

| Use Case | Solution | Rationale |
|----------|----------|-----------|
| **Simple references** (current) | Inline edges | Fast, no overhead |
| **Complex graphs** (>1000 edges/entity) | Column Families | Bidirectional, efficient |
| **Mixed workload** | Hybrid | Balance simplicity + power |

**Current Implementation:**
- Using **inline edges** (simple array in properties)
- Good for: Document chunking (File → Resources), simple references
- Limitation: Reverse lookups require full table scan

**Future Enhancement (v0.2):**
- Add **Column Family for edges** when graph queries become primary use case
- Provide both APIs: `entity.edges` (inline) + `db.get_edges(uuid)` (CF)
- Migrate inline edges to CF automatically when threshold exceeded

### Fuzzy Search with Trigram Index

**Problem:** Current fuzzy fallback requires full table scan O(n) to find partial matches like "bob" matching "bobsmith".

**SQL Equivalent:**
```sql
SELECT * FROM entities WHERE name LIKE '%bob%'
-- Requires full table scan in SQL too!
```

**Solution: Trigram Index (N-gram tokenization)**

Split strings into overlapping 3-character sequences and index them in a separate Column Family.

**Example:**
```
"bobsmith" → trigrams: ["bob", "obs", "bsm", "smi", "mit", "ith"]

[CF: trigrams]
  trigram:default:bob:uuid1 → (empty - UUID in key)
  trigram:default:obs:uuid1 → (empty)
  trigram:default:bsm:uuid1 → (empty)
  trigram:default:smi:uuid1 → (empty)
  trigram:default:smi:uuid3 → (empty - another entity)
```

**Search Process:**

```rust
// Query: "bob"
// 1. Generate query trigrams: ["bob"]
// 2. Prefix scan: "trigram:default:bob:" → [uuid1, uuid2, uuid5]
// 3. Fetch entities and verify full match
// Result: O(log n + k) where k = matches
```

**Multi-trigram Query:**
```rust
// Query: "smith" (longer queries)
// 1. Generate: ["smi", "mit", "ith"]
// 2. Find entities matching ALL trigrams (intersection)
// 3. Score by trigram overlap (similarity)
// Result: Ranked fuzzy matches
```

**Implementation Strategy:**

```rust
// Generate trigrams
pub fn generate_trigrams(text: &str) -> Vec<String> {
    let text = text.to_lowercase();
    let chars: Vec<char> = text.chars().collect();

    if chars.len() < 3 {
        return vec![text]; // Short strings as-is
    }

    chars.windows(3)
        .map(|w| w.iter().collect())
        .collect()
}

// Index on insert
pub fn insert_with_trigrams(
    &self,
    entity_id: Uuid,
    field_value: &str,
) -> Result<()> {
    let trigrams = generate_trigrams(field_value);
    let mut batch = WriteBatch::default();

    for trigram in trigrams {
        let key = format!("trigram:{}:{}:{}",
            self.tenant_id, trigram, entity_id);
        batch.put_cf(&self.cf_trigrams, key.as_bytes(), &[]);
    }

    self.db.write(batch)?;
    Ok(())
}

// Fuzzy search
pub fn fuzzy_search(&self, query: &str) -> Result<Vec<(Uuid, f32)>> {
    let query_trigrams = generate_trigrams(query);
    let mut entity_scores = HashMap::new();

    // Find entities matching each trigram
    for trigram in &query_trigrams {
        let prefix = format!("trigram:{}:{}:", self.tenant_id, trigram);
        let iter = self.db.prefix_iterator_cf(&self.cf_trigrams, prefix.as_bytes())?;

        for (key, _) in iter {
            let uuid = extract_uuid_from_key(&key)?;
            *entity_scores.entry(uuid).or_insert(0) += 1;
        }
    }

    // Calculate similarity score (# matching trigrams / total trigrams)
    let mut results: Vec<(Uuid, f32)> = entity_scores
        .into_iter()
        .map(|(id, count)| {
            let score = count as f32 / query_trigrams.len() as f32;
            (id, score)
        })
        .collect();

    // Sort by score descending
    results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    Ok(results)
}
```

**Performance Characteristics:**

| Metric | Value | Notes |
|--------|-------|-------|
| **Build time** | O(m) | m = string length, ~3m trigrams |
| **Search time** | O(k × log n) | k = query trigrams, batched prefix scans |
| **Storage overhead** | ~200% | 3 trigrams per character |
| **Similarity threshold** | Configurable | e.g., score > 0.5 for "good enough" |

**Storage Calculation:**

```
Example: 1M entities, avg 20 chars per indexed field
- Trigrams per entity: 20 × 3 = 60 trigrams
- Total trigram entries: 1M × 60 = 60M entries
- Storage per entry: ~50 bytes (key) + 0 bytes (value)
- Total storage: 60M × 50 = 3 GB

Compared to entity data: ~500 MB
Overhead: 3 GB / 500 MB = 6x (600%)
```

**With compression:**
- Trigrams have high redundancy (repeated prefixes)
- RocksDB LZ4 compression: ~50% reduction
- Real overhead: ~300% (3x)

**When to Use:**

| Use Case | Recommendation |
|----------|----------------|
| **Exact lookups** | Use deterministic UUID (current) |
| **Prefix search** | Use prefix index (smaller overhead) |
| **General fuzzy** | **Use trigram index** |
| **Typo tolerance** | Use trigram + edit distance |
| **Complex queries** | Delegate to Tantivy/Meilisearch |

**Configuration:**

```rust
// Enable trigram indexing per schema
model_config = {
    "json_schema_extra": {
        "indexed_fields": ["name", "email"],  // Regular indices
        "trigram_fields": ["name", "description"],  // Fuzzy search
        "trigram_min_length": 3,  // Don't index strings < 3 chars
    }
}
```

**CLI Usage:**

```bash
# Exact lookup (current)
$ db lookup "bob"  # Fast O(1)

# Fuzzy search (with trigram index)
$ db fuzzy "bob" --schema=person
Found 3 matches:
  1. Bob Smith (score: 1.00) - exact
  2. Bobby Jones (score: 0.75) - partial
  3. Rob Dobbs (score: 0.33) - weak match

# Threshold filtering
$ db fuzzy "bob" --min-score 0.7
Found 2 matches (score >= 0.7)
```

**Trade-offs:**

**Pros:**
- ✅ Fast fuzzy search O(log n + k) instead of O(n)
- ✅ Handles partial matches ("bob" finds "bobsmith")
- ✅ Similarity scoring built-in
- ✅ Works with any string field

**Cons:**
- ❌ High storage overhead (3x entity data)
- ❌ Write amplification (many trigrams per insert)
- ❌ Not suitable for very short strings (<3 chars)
- ❌ Increased memory pressure (larger working set)

**Migration Path:**

**Phase 1 (v0.1 - Current):**
- Exact lookups via deterministic UUID
- Fuzzy fallback via full table scan (slow, but simple)

**Phase 2 (v0.2 - Optional):**
- Add trigram CF for specific high-value fields (e.g., names, emails)
- Keep exact lookups as primary path
- Use trigram only when fuzzy search requested

**Phase 3 (v0.3 - Advanced):**
- Consider external FTS engine (Tantivy, Meilisearch) for complex queries
- Trigram index as mid-tier solution

**Recommendation:** Implement trigram index only when:
1. Fuzzy search becomes frequently used (>10% of queries)
2. Table sizes exceed 10k entities (full scan becomes slow)
3. Storage overhead acceptable (3x is manageable)

For now, exact lookup + full-scan fallback is sufficient for most use cases.

## Configuration

### Environment Variables

The REM database uses a consistent `P8_*` prefix for all configuration variables.

#### Core Configuration

```bash
# Home directory for all P8 data
export P8_HOME="~/.p8"
# Default: ~/.p8
# Structure:
#   ~/.p8/db/           - Database files
#   ~/.p8/models/       - Local embedding models
#   ~/.p8/cache/        - Query and embedding cache
#   ~/.p8/logs/         - Application logs
```

#### Embedding Configuration

```bash
# Default embedding model
export P8_DEFAULT_EMBEDDING="text-embedding-3-small"
# Options:
#   - "text-embedding-3-small" (OpenAI, 1536 dims, $0.00002/1K tokens)
#   - "text-embedding-3-large" (OpenAI, 3072 dims, $0.00013/1K tokens)
#   - "text-embedding-ada-002" (OpenAI legacy, 1536 dims)
#   - "all-MiniLM-L6-v2" (Local, 384 dims, ~100MB model)
#   - "all-mpnet-base-v2" (Local, 768 dims, ~420MB model)
# Default: "all-MiniLM-L6-v2" (local, no API key needed)

# Alternative embedding model (for dual embeddings)
export P8_ALT_EMBEDDING="all-mpnet-base-v2"
# Default: None (single embedding only)

# Local model cache directory
export P8_MODELS_DIR="~/.p8/models"
# Default: ~/.p8/models
# Used by sentence-transformers and embed_anything

# Embedding batch size
export P8_EMBEDDING_BATCH_SIZE="32"
# Default: 32
# Batch size for embedding generation (affects memory usage)
```

#### LLM Configuration

```bash
# Default LLM for natural language queries
export P8_DEFAULT_LLM="gpt-4.1"
# Options:
#   - "gpt-4.1" (Latest GPT-4.1, recommended)
#   - "gpt-4-turbo-2024-04-09" (GPT-4 Turbo)
#   - "gpt-4o" (GPT-4 Omni, multimodal)
#   - "gpt-4" (GPT-4 base)
#   - "gpt-3.5-turbo" (Faster, cheaper)
#   - "claude-3-opus-20240229" (Anthropic, requires separate key)
#   - "claude-3-sonnet-20240229" (Anthropic)
# Default: "gpt-4.1"

# LLM temperature for query generation
export P8_LLM_TEMPERATURE="0.0"
# Default: 0.0 (deterministic)
# Range: 0.0-2.0 (higher = more creative)

# LLM max tokens for responses
export P8_LLM_MAX_TOKENS="2000"
# Default: 2000
```

#### API Keys

```bash
# OpenAI API key (for OpenAI embeddings and LLM)
export OPENAI_API_KEY="sk-proj-..."
# Required if using OpenAI models
# Get key from: https://platform.openai.com/api-keys

# Anthropic API key (for Claude models)
export ANTHROPIC_API_KEY="sk-ant-..."
# Required if using Claude models
# Get key from: https://console.anthropic.com/

# Cohere API key (for Cohere embeddings)
export COHERE_API_KEY="..."
# Optional: For Cohere embedding models
```

#### Database Configuration

```bash
# Database path (override default location)
export P8_DB_PATH="~/.p8/db"
# Default: ~/.p8/db

# Default tenant ID
export P8_DEFAULT_TENANT="default"
# Default: "default"
# Used when tenant not specified

# RocksDB write buffer size (MB)
export P8_ROCKSDB_WRITE_BUFFER_SIZE="64"
# Default: 64 MB
# Increase for write-heavy workloads

# RocksDB max open files
export P8_ROCKSDB_MAX_OPEN_FILES="1000"
# Default: 1000
# Increase for large databases

# Enable WAL (Write-Ahead Log)
export P8_ENABLE_WAL="true"
# Default: true
# Set to "false" to disable replication logging
```

#### Replication Configuration

```bash
# Replication mode
export P8_REPLICATION_MODE="standalone"
# Options: "standalone", "primary", "replica"
# Default: "standalone" (no replication)

# Primary endpoint (for replicas)
export P8_PRIMARY_ENDPOINT="primary:9000"
# Required if mode=replica
# Format: "host:port"

# Replica endpoints (for primary)
export P8_REPLICA_ENDPOINTS="replica1:9001,replica2:9002"
# Required if mode=primary
# Comma-separated list of "host:port"

# WAL retention size (in-memory)
export P8_WAL_RETENTION_SIZE="1000"
# Default: 1000 entries
# Number of WAL entries kept in memory for fast catchup

# WAL batch size
export P8_WAL_BATCH_SIZE="100"
# Default: 100 entries
# Batch size for streaming WAL entries

# Replication poll interval (ms)
export P8_REPLICATION_POLL_INTERVAL="100"
# Default: 100ms
# Polling interval for pull-based replication
```

#### Cache Configuration

```bash
# Enable query result caching
export P8_ENABLE_CACHE="true"
# Default: true

# Cache directory
export P8_CACHE_DIR="~/.p8/cache"
# Default: ~/.p8/cache

# Cache TTL (seconds)
export P8_CACHE_TTL="3600"
# Default: 3600 (1 hour)
# How long to cache query results

# Max cache size (MB)
export P8_CACHE_MAX_SIZE="1000"
# Default: 1000 MB (1 GB)
# Maximum disk space for cache
```

#### Logging Configuration

```bash
# Log level
export P8_LOG_LEVEL="INFO"
# Options: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
# Default: "INFO"

# Log directory
export P8_LOG_DIR="~/.p8/logs"
# Default: ~/.p8/logs

# Log format
export P8_LOG_FORMAT="json"
# Options: "json", "text"
# Default: "json" (structured logging)

# Enable performance logging
export P8_LOG_PERFORMANCE="false"
# Default: false
# Log query execution times and statistics
```

#### Performance Tuning

```bash
# Vector search index type
export P8_VECTOR_INDEX_TYPE="hnsw"
# Options: "hnsw", "flat"
# Default: "hnsw" (fast approximate search)

# HNSW M parameter (connections per node)
export P8_HNSW_M="16"
# Default: 16
# Higher = better recall, more memory

# HNSW ef_construction parameter
export P8_HNSW_EF_CONSTRUCTION="200"
# Default: 200
# Higher = better index quality, slower build

# HNSW ef_search parameter
export P8_HNSW_EF_SEARCH="50"
# Default: 50
# Higher = better recall, slower search

# Background worker threads
export P8_WORKER_THREADS="4"
# Default: 4
# Number of background threads for async operations

# Query timeout (seconds)
export P8_QUERY_TIMEOUT="30"
# Default: 30 seconds
# Maximum time for a single query
```

#### Export Configuration

```bash
# Default Parquet compression
export P8_PARQUET_COMPRESSION="snappy"
# Options: "snappy", "gzip", "brotli", "lz4", "zstd", "none"
# Default: "snappy" (good balance of speed/compression)

# Parquet row group size
export P8_PARQUET_ROW_GROUP_SIZE="10000"
# Default: 10000 rows per group
# Affects query performance on Parquet files
```

### Configuration File

Alternatively, use a TOML configuration file:

**Location:** `~/.p8/config.toml` or `$P8_HOME/config.toml`

```toml
# ~/.p8/config.toml

[core]
home = "~/.p8"
default_tenant = "default"

[embeddings]
default_model = "text-embedding-3-small"
alt_model = "all-mpnet-base-v2"
batch_size = 32

[llm]
default_model = "gpt-4.1"
temperature = 0.0
max_tokens = 2000

[database]
path = "~/.p8/db"
rocksdb_write_buffer_size = 64
rocksdb_max_open_files = 1000
enable_wal = true

[replication]
mode = "standalone"
# primary_endpoint = "primary:9000"  # For replicas
# replica_endpoints = ["replica1:9001", "replica2:9002"]  # For primary
wal_retention_size = 1000
wal_batch_size = 100

[cache]
enabled = true
directory = "~/.p8/cache"
ttl = 3600
max_size_mb = 1000

[logging]
level = "INFO"
directory = "~/.p8/logs"
format = "json"
performance = false

[vector_search]
index_type = "hnsw"
hnsw_m = 16
hnsw_ef_construction = 200
hnsw_ef_search = 50

[performance]
worker_threads = 4
query_timeout = 30

[export]
parquet_compression = "snappy"
parquet_row_group_size = 10000
```

**Priority:** Environment variables override config file settings.

### Database Location

**Default:** `$P8_HOME/db/{name}.db` or `~/.p8/db/{name}.db`

**Override via environment:**

```bash
export P8_DB_PATH="/data/databases"
db init mydb  # Creates /data/databases/mydb.db
```

**Override via CLI flag:**

```bash
db init mydb --path /data/databases/mydb
```

## Performance Characteristics

### Insert Performance
- Without embeddings: ~2,000-5,000 ops/sec
- With local embeddings: ~100 ops/sec
- With OpenAI embeddings: ~20 ops/sec (API limited)

### Query Performance
- Direct key lookup: ~20,000-50,000 ops/sec
- Indexed equality: ~5-10ms p50
- Full scan (100k entities): ~100-200ms
- Vector search (HNSW): ~0.5-1ms p50

### Storage Efficiency
- 1M entities ≈ 1-2 GB (RocksDB compressed)
- Vector index scales linearly with entity count
- Recommendation: Use SSD for production workloads

## Replication

The REM database supports **n-way replication** (n ≥ 2) via Write-Ahead Log (WAL) streaming for real-time synchronization across nodes.

### Architecture

```
┌─────────────┐
│   Primary   │
│   Database  │
└──────┬──────┘
       │
       │ WAL Stream (gRPC/TCP)
       ├───────────────┬───────────────┐
       │               │               │
       ▼               ▼               ▼
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Replica  │    │ Replica  │    │ Replica  │
│    1     │    │    2     │    │    3     │
└──────────┘    └──────────┘    └──────────┘
```

### Write-Ahead Log (WAL)

Every write operation is logged to the WAL before being applied to RocksDB. The WAL provides:

- **Monotonic sequence numbers** - Ordered log of all operations
- **Crash recovery** - Replay operations after node failure
- **Replication source** - Stream changes to replica nodes
- **Point-in-time recovery** - Replay to specific sequence number

**WAL Entry Structure:**

```python
{
    "seq_num": 12345,                    # Monotonic sequence number
    "tenant_id": "default",              # Tenant scope
    "tablespace": "default",             # Column family / namespace
    "operation": "PUT",                  # PUT, DELETE, MERGE
    "key": "656e746974793a...",         # Key (hex-encoded)
    "value": "7b226e616d65...",         # Value (hex-encoded, empty for DELETE)
    "timestamp": 1729785123456789012    # Nanosecond precision timestamp
}
```

### Replication Protocol

**Primary Node:**

1. Writes data to local RocksDB
2. Appends operation to WAL (sequence number assigned)
3. Persists WAL entry to RocksDB (`wal:{tenant}:entry:{seq}`)
4. Streams WAL entry to all connected replicas (async)
5. Keeps last 1000 entries in memory for fast catchup

**Replica Node:**

1. Receives WAL entry from primary (gRPC/TCP stream)
2. Verifies sequence number (detects gaps)
3. Applies operation to local RocksDB
4. Updates last applied sequence (`wal:{tenant}:seq`)
5. Sends acknowledgment to primary

### Catchup & Recovery

**Replica Startup:**

```bash
# Replica starts and reads last applied sequence
last_seq = db.get("wal:tenant:seq")  # e.g., 10000

# Request catchup from primary
GET /wal/entries?start_seq=10000&limit=1000

# Apply all missed entries sequentially
for entry in entries:
    apply_wal_entry(entry)
    update_seq(entry.seq_num)

# Resume real-time streaming
```

**Primary Crash:**

1. Replica detects primary disconnection
2. Replica promoted to new primary (manual or automatic)
3. Other replicas reconnect to new primary
4. WAL sequence numbers continue from last applied

### API Endpoints

**Get WAL entries (for replication):**

```bash
# Get entries since sequence 1000
GET /wal/entries?start_seq=1000&limit=100

# Get current sequence number
GET /wal/current_seq
```

**Response:**

```json
{
  "current_seq": 15234,
  "entries": [
    {
      "seq_num": 1001,
      "tenant_id": "default",
      "operation": "PUT",
      "key": "656e746974793a...",
      "value": "7b226e616d65...",
      "timestamp": 1729785123456789012
    }
  ]
}
```

### Replication Modes

**1. Real-time streaming (default)**

- Primary streams WAL entries immediately
- Low latency (< 10ms typical)
- Requires persistent connection
- Best for high-availability clusters

**2. Pull-based polling**

- Replica polls for new entries periodically
- Higher latency (poll interval)
- No persistent connection required
- Best for WAN replication

**3. Snapshot + incremental**

- Initial snapshot of full database
- Followed by WAL streaming for increments
- Best for new replica setup

### Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| **Replication lag** | < 10ms p50 | LAN, real-time streaming |
| **Catchup speed** | ~10,000 ops/sec | Depends on network/disk |
| **WAL overhead** | ~5-10% | Storage and write amplification |
| **Max replicas** | 10+ | Limited by network bandwidth |
| **Recovery time** | Seconds | Depends on lag size |

### Configuration

**Primary configuration:**

```bash
# Enable WAL replication
export REM_REPLICATION_MODE="primary"
export REM_REPLICA_ENDPOINTS="replica1:9001,replica2:9001,replica3:9001"

# WAL settings
export REM_WAL_RETENTION_SIZE=1000   # Keep last 1000 entries in memory
export REM_WAL_BATCH_SIZE=100        # Batch entries before streaming
```

**Replica configuration:**

```bash
# Connect to primary
export REM_REPLICATION_MODE="replica"
export REM_PRIMARY_ENDPOINT="primary:9000"

# Catchup settings
export REM_CATCHUP_BATCH_SIZE=1000   # Entries per catchup request
export REM_POLL_INTERVAL_MS=100      # Poll interval (if not streaming)
```

### Monitoring

**Replication metrics:**

```bash
# Check replication lag
db replication status

# Output:
Replication Status:
  Mode: replica
  Primary: primary:9000
  Last applied seq: 15234
  Primary seq: 15240
  Lag: 6 entries (~0.3ms)
  Status: SYNCED
```

**Health checks:**

- **Lag threshold**: Alert if lag > 1000 entries or > 1s
- **Connection status**: Alert on replica disconnect
- **Sequence gaps**: Alert on missing sequence numbers (data loss)

### Failure Scenarios

**Scenario 1: Replica falls behind**

- Replica accumulates lag (network/disk issues)
- Replica requests catchup batch from primary
- Primary serves historical WAL entries from RocksDB
- Replica applies entries until caught up

**Scenario 2: Primary crashes**

- Replicas detect disconnection
- Manual failover: Promote most up-to-date replica
- Other replicas reconnect to new primary
- WAL continues from last sequence

**Scenario 3: Network partition**

- Some replicas isolated from primary
- Isolated replicas stop receiving updates (read-only)
- When network heals, replicas request catchup
- Resume normal replication

### Limitations (v0.1)

- **No automatic failover** - Requires manual promotion
- **Single primary only** - No multi-master support
- **No conflict resolution** - Write conflicts not handled
- **No bidirectional sync** - Replicas are read-only
- **No data compression** - WAL entries sent uncompressed

### Future Enhancements (v0.2+)

- [ ] Automatic leader election (Raft consensus)
- [ ] Bidirectional sync (multi-master)
- [ ] Conflict resolution strategies (LWW, CRDT)
- [ ] WAL compression (zstd, snappy)
- [ ] Quorum writes (wait for N replicas)
- [ ] Read replicas (automatically promoted)

## Version History

**v0.1 (Current)**

- Initial specification
- Built-in types: Schema, Resource, File, Moment, QueryResult
- System fields: id, created_at, modified_at, deleted_at, edges
- Key precedence: uri → key → name
- Embedding support: Default provider configuration
- CLI commands: init, lookup, query, search, ingest, schema, upsert, export
- WAL-based replication (primary → replicas)
- Parquet export with compression

**Upcoming (v0.2)**

- Automatic failover and leader election
- Multi-tenant shared instances
- Graph query language
- Aggregation functions (GROUP BY, COUNT, SUM)
- JOIN support across tables
- WAL compression and optimization
