# Schema Definition Guide

## Overview

REM database uses **Pydantic models** or **JSON/YAML schemas** to define entity types. Schemas drive everything: validation, indexing, embeddings, and storage.

**Preferred formats:**
1. **JSON Schema** (`.json`) - Portable, language-agnostic
2. **YAML Schema** (`.yaml`) - Human-readable, concise
3. **Pydantic models** (`.py`) - Python-native, type-safe

## Schema Requirements

All schemas must include:

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `title` | Yes | Schema name (PascalCase) | `"Article"`, `"CDAMappingAgent"` |
| `description` | Yes | What this entity represents (embedded for search) | `"Technical articles and tutorials"` |
| `version` | Yes | Semantic version | `"1.0.0"` |
| `short_name` | Yes | Table name (snake_case) | `"articles"`, `"cda_mapper"` |
| `name` | Yes | Unique schema identifier | `"myapp.resources.Article"` or just `"Article"` |
| `properties` | Yes | Field definitions with types and descriptions | See below |
| `required` | No | List of required field names | `["title", "content"]` |

**System fields** (auto-added, never define):
- `id` (UUID) - Entity identifier
- `entity_type` (string) - Schema/table name
- `created_at`, `modified_at`, `deleted_at` (ISO 8601) - Timestamps
- `edges` (array[object]) - Graph relationships stored as JSON
  - Current: JSON array of edge objects
  - Future: May use separate keys column family for better performance

**Embedding fields** (conditionally added):
- `embedding` (array[float32]) - Primary embeddings (if `embedding_fields` configured)
- `embedding_alt` (array[float32]) - Alternative embeddings (if `P8_ALT_EMBEDDING` set)

## Format 1: JSON Schema (Preferred)

### Resource Schema Example

```json
{
  "title": "Article",
  "description": "Technical articles and tutorials for developers",
  "version": "1.0.0",
  "short_name": "articles",
  "name": "myapp.resources.Article",

  "json_schema_extra": {
    "embedding_fields": ["title", "content"],
    "embedding_provider": "default",
    "indexed_fields": ["category", "status"],
    "key_field": "uri"
  },

  "properties": {
    "title": {
      "type": "string",
      "description": "Article title",
      "maxLength": 200
    },
    "content": {
      "type": "string",
      "description": "Full article content in Markdown format"
    },
    "uri": {
      "type": "string",
      "format": "uri",
      "description": "Source URI (unique identifier)"
    },
    "category": {
      "type": "string",
      "enum": ["tutorial", "guide", "reference", "blog"],
      "description": "Content category"
    },
    "status": {
      "type": "string",
      "enum": ["draft", "published", "archived"],
      "description": "Publication status"
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Topic tags for filtering",
      "default": []
    },
    "author": {
      "type": "string",
      "description": "Author name or identifier"
    },
    "published_at": {
      "type": "string",
      "format": "date-time",
      "description": "Publication timestamp (ISO 8601)"
    }
  },

  "required": ["title", "content", "uri", "category"]
}
```

### Agent-let Schema Example

Based on carrier project pattern:

```json
{
  "title": "CDAMappingAgent",
  "description": "You are a CDA Mapping Expert specialized in creating field mappings between external carrier APIs and nShift's internal CDA schema.\n\n## Your Process\n\n1. Parse carrier API specification\n2. Search for evidence in codebase and documentation\n3. Propose bipartite mappings with confidence scores\n4. Generate Python implementation\n5. Validate and flag ambiguities",
  "version": "1.0.0",
  "short_name": "cda_mapper",
  "name": "carrier.agents.cda_mapper.CDAMappingAgent",

  "json_schema_extra": {
    "tools": [
      {
        "mcp_server": "carrier",
        "tool_name": "search_knowledge_base",
        "usage": "Search codebase, CDA schema, Zendesk tickets for mapping evidence"
      }
    ],
    "resources": [
      {
        "uri": "cda://field-definitions",
        "usage": "Get all CDA field definitions with types and constraints"
      },
      {
        "uri": "cda://carriers",
        "usage": "Get list of all registered carriers"
      }
    ],
    "embedding_fields": ["description"],
    "embedding_provider": "default"
  },

  "properties": {
    "carrier_name": {
      "type": "string",
      "description": "Carrier name (e.g., 'DHL', 'FedEx')"
    },
    "operation": {
      "type": "string",
      "description": "Operation being mapped (e.g., 'book_shipment')"
    },
    "mappings": {
      "type": "array",
      "description": "Bipartite mappings between carrier and CDA fields",
      "items": {
        "type": "object",
        "required": ["source", "targets", "confidence", "evidence"],
        "properties": {
          "source": {
            "type": "object",
            "description": "Source field from carrier API",
            "properties": {
              "field_path": {"type": "string"},
              "field_type": {"type": "string"},
              "description": {"type": "string"}
            }
          },
          "targets": {
            "type": "array",
            "description": "Possible CDA field mappings",
            "items": {
              "type": "object",
              "properties": {
                "field_path": {"type": "string"},
                "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                "confidence_score": {"type": "number", "minimum": 0, "maximum": 100}
              }
            }
          },
          "confidence": {
            "type": "string",
            "enum": ["HIGH", "MEDIUM", "LOW"]
          },
          "evidence": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "type": {"type": "string", "enum": ["code_reference", "schema_definition", "documentation"]},
                "source": {"type": "string"},
                "content": {"type": "string"}
              }
            }
          }
        }
      }
    },
    "validation_report": {
      "type": "object",
      "properties": {
        "warnings": {"type": "array", "items": {"type": "string"}},
        "errors": {"type": "array", "items": {"type": "string"}}
      }
    },
    "next_steps": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Recommended actions"
    }
  },

  "required": ["carrier_name", "operation", "mappings", "validation_report", "next_steps"]
}
```

## Format 2: YAML Schema (Human-Readable)

```yaml
title: Article
description: Technical articles and tutorials for developers
version: 1.0.0
short_name: articles
name: myapp.resources.Article

json_schema_extra:
  embedding_fields:
    - title
    - content
  embedding_provider: default
  indexed_fields:
    - category
    - status
  key_field: uri

properties:
  title:
    type: string
    description: Article title
    maxLength: 200

  content:
    type: string
    description: Full article content in Markdown format

  uri:
    type: string
    format: uri
    description: Source URI (unique identifier)

  category:
    type: string
    enum: [tutorial, guide, reference, blog]
    description: Content category

  status:
    type: string
    enum: [draft, published, archived]
    description: Publication status

  tags:
    type: array
    items:
      type: string
    description: Topic tags for filtering
    default: []

  author:
    type: string
    description: Author name or identifier

  published_at:
    type: string
    format: date-time
    description: Publication timestamp (ISO 8601)

required:
  - title
  - content
  - uri
  - category
```

## Format 3: Pydantic Model (Python)

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal
from datetime import datetime

class Article(BaseModel):
    """Technical articles and tutorials for developers.

    This docstring becomes the schema description and is embedded
    for semantic schema search when many schemas are registered.
    """

    title: str = Field(
        ...,
        max_length=200,
        description="Article title"
    )

    content: str = Field(
        ...,
        description="Full article content in Markdown format"
    )

    uri: str = Field(
        ...,
        description="Source URI (unique identifier)"
    )

    category: Literal["tutorial", "guide", "reference", "blog"] = Field(
        ...,
        description="Content category"
    )

    status: Literal["draft", "published", "archived"] = Field(
        default="draft",
        description="Publication status"
    )

    tags: list[str] = Field(
        default_factory=list,
        description="Topic tags for filtering"
    )

    author: str = Field(
        ...,
        description="Author name or identifier"
    )

    published_at: datetime | None = Field(
        default=None,
        description="Publication timestamp"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "version": "1.0.0",
            "short_name": "articles",
            "name": "myapp.resources.Article",

            # Embedding configuration
            "embedding_fields": ["title", "content"],
            "embedding_provider": "default",

            # Indexing configuration
            "indexed_fields": ["category", "status"],

            # Key field (deterministic UUID)
            "key_field": "uri"
        }
    )
```

## json_schema_extra Configuration

### Core Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `version` | string | Semantic version | `"1.0.0"` |
| `short_name` | string | Table name (snake_case) | `"articles"` |
| `name` | string | Unique schema identifier | `"myapp.resources.Article"` or just `"Article"` |
| `category` | string | `"system"` or `"user"` | `"user"` |

### Embedding Configuration

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `embedding_fields` | array[string] | Fields to embed (triggers auto-embedding) | `["content", "title"]` |
| `embedding_provider` | string | Provider name | `"default"` (uses `P8_DEFAULT_EMBEDDING`) |
| `embedding_model` | string | Explicit model override | `"text-embedding-3-small"` |

**Embedding behavior:**
- If `embedding_fields` is set → `embedding` field is auto-added to entities
- Fields are concatenated with newlines before embedding
- Embeddings are generated on insert/update
- Stored in separate `embeddings` CF (binary, compressed)

### Indexing Configuration

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `indexed_fields` | array[string] | Fields to index (fast WHERE queries) | `["category", "status"]` |
| `key_field` | string | Field for deterministic UUID | `"uri"`, `"email"` |

**Indexing behavior:**
- Indexed fields create entries in `indexes` CF
- Enables O(log n) predicate evaluation instead of O(n) scan
- Key field enables idempotent upserts (same key → same UUID)

### Agent-let Configuration

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `tools` | array[object] | MCP tools agent can use | See agent example above |
| `resources` | array[object] | MCP resources agent can access | See agent example above |

**Tool object:**
```json
{
  "mcp_server": "carrier",
  "tool_name": "search_knowledge_base",
  "usage": "Search codebase for similar patterns"
}
```

**Resource object:**
```json
{
  "uri": "cda://field-definitions",
  "usage": "Get all CDA field definitions"
}
```

## Field Property Requirements

All field definitions must include:

| Property | Required | Description | Example |
|----------|----------|-------------|---------|
| `type` | Yes | JSON Schema type | `"string"`, `"number"`, `"array"`, `"object"` |
| `description` | **Yes** | Semantic meaning (used for LLM query building) | `"Full article content in Markdown"` |
| `default` | No | Default value | `[]`, `"draft"`, `null` |
| `enum` | No | Allowed values | `["draft", "published"]` |
| `format` | No | String format | `"uri"`, `"date-time"`, `"email"` |
| `maxLength` | No | String length limit | `200` |
| `minimum`/`maximum` | No | Number bounds | `0`, `100` |
| `items` | Yes (if array) | Array item type | `{"type": "string"}` |
| `properties` | Yes (if object) | Nested object fields | See examples |

**Critical: Field descriptions are mandatory**
- Used by LLM to understand field semantics
- Enables accurate natural language queries
- Required for schema-aware query construction
- Should be concise but specific (not "The name" but "Article title")

## System Schema Tables

### Table: `schemas` (System-Managed)

Stores registered schema definitions. **Never define this schema yourself.**

**Schema fields:**

| Field | Type | Description |
|-------|------|-------------|
| `short_name` | string | Table name (e.g., "articles") |
| `name` | string | Unique schema identifier |
| `version` | string | Semantic version |
| `schema` | object | Full JSON Schema definition |
| `description` | string | Schema description (taken from schema's `description` field) |

**json_schema_extra configuration:**
```json
{
  "embedding_fields": ["description"],
  "embedding_provider": "default",
  "indexed_fields": ["short_name", "name"],
  "key_field": "name"
}
```

**System fields (auto-added):**
- `id` (UUID) - Schema UUID
- `entity_type` (string) - Always "schemas"
- `created_at` (datetime) - Registration timestamp
- `modified_at` (datetime) - Last update timestamp
- `edges` (array[string]) - Graph relationships

**Embedding fields (auto-added because `embedding_fields` configured):**
- `embedding` (array[float32]) - Embedded schema description
  - **Not in schema definition** - added by system during registration
  - Generated from `description` field (as specified in `embedding_fields`)
  - Used for semantic schema search when >10 schemas registered

**How it works:**
1. User registers schema with `description` field: `"Technical articles and tutorials"`
2. System stores `description` in `schemas` table
3. System generates embedding from `description` (because `embedding_fields: ["description"]`)
4. Embedding used for semantic schema search when many schemas exist

### Table: `documents` (System-Managed)

Stores original uploaded documents before chunking. Created automatically by `rem ingest`.

**Schema fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Document name (e.g., "Python Tutorial.pdf") |
| `uri` | string | Yes | Source URI or file path (unique) |
| `content_type` | string | No | MIME type (e.g., "application/pdf", "text/markdown") |
| `file_size` | integer | No | File size in bytes |
| `file_hash` | string | No | SHA256 hash of file content |
| `category` | string | No | Document category |
| `tags` | array[string] | No | Topic tags |
| `sentiment_tags` | array[string] | No | Sentiment/tone tags |
| `active_start_time` | datetime | No | Validity period start |
| `active_end_time` | datetime | No | Validity period end |
| `chunk_count` | integer | No | Number of chunks created from this document |
| `metadata` | object | No | Arbitrary metadata (e.g., author, version) |

**json_schema_extra configuration:**
```json
{
  "key_field": "uri",
  "indexed_fields": ["content_type", "category", "file_hash"]
}
```

**System fields (auto-added):**
- `id` (UUID) - Document UUID
- `entity_type` (string) - Always "documents"
- `created_at`, `modified_at`, `deleted_at` (datetime)
- `edges` (array[object]) - Links to chunks (resources)

**No embeddings** - Documents are not embedded, only their chunks (resources) are.

**UUID generation:**
- `blake3(uri)` → idempotent document uploads
- Same URI → same UUID → re-upload replaces existing

---

### Table: `resources` (User-Defined)

Searchable document chunks with embeddings. Created automatically by `rem ingest` from documents.

**Schema fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Chunk name (e.g., "Python Tutorial - Section 1") |
| `content` | string | Yes | Chunk content (text extracted from document) |
| `uri` | string | Yes | Source document URI (links back to document) |
| `chunk_ordinal` | integer | Yes | Chunk index (0-based, sequential) |
| `content_type` | string | No | MIME type (inherited from document) |
| `category` | string | No | Content category (inherited from document) |
| `tags` | array[string] | No | Topic tags (inherited from document) |
| `sentiment_tags` | array[string] | No | Sentiment/tone tags |
| `active_start_time` | datetime | No | Validity period start (inherited from document) |
| `active_end_time` | datetime | No | Validity period end (inherited from document) |
| `document_id` | UUID | No | Reference to parent document |
| `metadata` | object | No | Chunk-specific metadata (e.g., page number, section heading) |

**json_schema_extra configuration:**
```json
{
  "embedding_fields": ["content"],
  "embedding_provider": "default",
  "key_field": "uri",
  "indexed_fields": ["content_type", "category", "active_start_time", "active_end_time", "document_id"]
}
```

**System fields (auto-added to every entity):**
- `id` (UUID) - Entity UUID
- `entity_type` (string) - Always "resources"
- `created_at`, `modified_at`, `deleted_at` (datetime)
- `edges` (array[string]) - Graph relationships

**Embedding fields (auto-added because `embedding_fields` configured):**
- `embedding` (array[float32]) - Embedded content
  - **Not defined in schema** - added by system during insert
  - Generated from `content` field (as specified in `embedding_fields`)

**UUID generation:**
- `blake3(uri + chunk_ordinal)` → idempotent chunked documents
- Same URI + ordinal → same UUID → upsert semantics

**Embedding fields (auto-added because `embedding_fields` configured):**
- `embedding` (array[float32]) - Embedded chunk content
  - **Not defined in schema** - added by system during insert
  - Generated from `content` field (as specified in `embedding_fields`)

**UUID generation:**
- `blake3(uri + chunk_ordinal)` → idempotent chunked documents
- Same URI + ordinal → same UUID → upsert semantics

---

## Document Ingestion Workflow

The `rem ingest` command handles the complete pipeline:

### CLI Usage

```bash
# Ingest a PDF document
rem ingest tutorial.pdf --category tutorial --tags python,programming

# Ingest with metadata
rem ingest guide.pdf \
  --category guide \
  --tags rust,performance \
  --metadata '{"author": "John Doe", "version": "2.0"}'

# Ingest with validity period
rem ingest seasonal-guide.pdf \
  --active-start 2024-12-01 \
  --active-end 2025-02-28

# Re-ingest (replaces existing chunks)
rem ingest tutorial.pdf  # Same URI → replaces old chunks
```

### What Happens

1. **Create document entity**:
   ```json
   {
     "id": "doc-uuid-123",
     "entity_type": "documents",
     "name": "tutorial.pdf",
     "uri": "file://tutorial.pdf",
     "content_type": "application/pdf",
     "file_size": 1048576,
     "file_hash": "sha256:abc123...",
     "category": "tutorial",
     "tags": ["python", "programming"],
     "chunk_count": 0
   }
   ```
   Stored in `documents` table (not embedded).

2. **Parse and chunk document**:
   - Extract text from PDF (or markdown, DOCX, etc.)
   - Split into chunks (~500 tokens each)
   - Preserve metadata (page numbers, section headings)

3. **Create resource entities** (one per chunk):
   ```json
   {
     "id": "resource-uuid-456",
     "entity_type": "resources",
     "name": "tutorial.pdf - Section 1",
     "content": "Chapter 1: Introduction\n\nPython is...",
     "uri": "file://tutorial.pdf",
     "chunk_ordinal": 0,
     "content_type": "application/pdf",
     "category": "tutorial",
     "tags": ["python", "programming"],
     "document_id": "doc-uuid-123",
     "metadata": {"page": 1, "section": "Introduction"},
     "embedding": [0.1, 0.5, -0.2, ...]
   }
   ```
   Stored in `resources` table (with embeddings).

4. **Update document with chunk count**:
   ```json
   {
     "chunk_count": 15,
     "edges": [
       {"type": "has_chunk", "target": "resource-uuid-456"},
       {"type": "has_chunk", "target": "resource-uuid-457"},
       ...
     ]
   }
   ```

5. **Search operates on resources**:
   ```bash
   rem search "Python introduction"
   # → Searches embeddings in resources table
   # → Returns matching chunks with document metadata
   ```

### Querying Documents vs Resources

**Search chunks** (semantic search):
```bash
rem search "async programming" --schema resources
# Returns: Individual chunks with embeddings
```

**Find original document**:
```bash
rem query "SELECT * FROM documents WHERE name = 'tutorial.pdf'"
# Returns: Document metadata + chunk_count
```

**Find all chunks from a document**:
```bash
rem query "SELECT * FROM resources WHERE document_id = 'doc-uuid-123' ORDER BY chunk_ordinal"
# Returns: All chunks in order
```

**Filter by validity period**:
```bash
rem query "SELECT * FROM resources WHERE NOW() BETWEEN active_start_time AND active_end_time"
# Returns: Only currently valid chunks
```

Note how `embedding` appears in stored resource entities but is **not in the schema definition** - it's added by the system based on `json_schema_extra.embedding_fields`.

## Registration

### CLI

```bash
# Register JSON schema
rem schema add schema.json

# Register YAML schema
rem schema add schema.yaml

# Register Pydantic model
rem schema add models.py::Article
```

### Python API

```python
from rem_db import Database
from models import Article

db = Database(path="~/.p8/db")

# From Pydantic model
db.register_schema("articles", Article)

# From JSON file
import json
with open("schema.json") as f:
    schema = json.load(f)
db.register_schema_json("articles", schema)
```

## Validation

When entities are inserted, they are validated against the registered schema:

**Validation checks:**
- Required fields present
- Field types match schema
- Enum values are valid
- String lengths within bounds
- Format constraints (URI, email, datetime)
- Nested object structure

**Validation errors:**
```json
{
  "error": "ValidationError",
  "message": "Field 'category' must be one of: tutorial, guide, reference, blog",
  "field": "category",
  "value": "invalid",
  "schema": "articles"
}
```

## Best Practices

### 1. Always Provide Field Descriptions

**Bad:**
```json
{
  "title": {"type": "string"}
}
```

**Good:**
```json
{
  "title": {
    "type": "string",
    "description": "Article title (concise, under 200 characters)"
  }
}
```

### 2. Use Enums for Categorical Fields

**Bad:**
```json
{
  "status": {"type": "string"}
}
```

**Good:**
```json
{
  "status": {
    "type": "string",
    "enum": ["draft", "published", "archived"],
    "description": "Publication status"
  }
}
```

### 3. Embed Searchable Content

```json
{
  "json_schema_extra": {
    "embedding_fields": ["title", "content", "summary"]
  }
}
```

**Multiple fields are concatenated:**
```
Title: {title}\n\nContent: {content}\n\nSummary: {summary}
```

### 4. Index Filter Fields

```json
{
  "json_schema_extra": {
    "indexed_fields": ["category", "status", "author"]
  }
}
```

**Enables fast queries:**
```bash
rem query "SELECT * FROM articles WHERE category = 'tutorial' AND status = 'published'"
# → Uses indexes, O(log n + k) instead of O(n) scan
```

### 5. Use key_field for Idempotent Inserts

```json
{
  "json_schema_extra": {
    "key_field": "uri"  // or "email", "product_sku", etc.
  }
}
```

**Benefits:**
- Same key → same UUID → upsert semantics
- Re-inserting same entity updates instead of duplicates
- Enables deterministic testing

### 6. Version Your Schemas

```json
{
  "version": "1.0.0"
}
```

**When to bump version:**
- Major (1.x.x → 2.x.x): Breaking changes (removed fields, changed types)
- Minor (x.1.x → x.2.x): Added optional fields
- Patch (x.x.1 → x.x.2): Clarified descriptions, fixed typos

### 7. Name Your Schemas Clearly

```json
{
  "name": "myapp.resources.Article",
  "short_name": "articles"
}
```

**Good naming:**
- Use namespaces for clarity: `"myapp.resources.Article"`
- Or simple names for single-app databases: `"Article"`
- Prevents collisions when multiple apps share a database
- Similar schema names (e.g., "users" in auth vs analytics) → namespace them

## Schema Evolution

**Adding optional fields:**
```json
{
  "properties": {
    "new_field": {
      "type": "string",
      "description": "New optional field",
      "default": null
    }
  }
}
```

**Updating schema:**
```bash
# Update version in schema file
# "version": "1.1.0"

# Re-register
rem schema add schema.json

# Old entities still valid (new field defaults to null)
```

**Breaking changes (avoid if possible):**
- Removing required fields → migrate data first
- Changing field types → write migration script
- Renaming fields → create new schema with data migration
