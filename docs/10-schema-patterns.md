# Schema patterns and data conventions

This document describes the schema patterns and data conventions used throughout Percolate.

## Agent-let schema

Agent-lets are JSON schema-defined AI skills that can be trained, shared, and evolved as data artifacts.

### Schema structure

```json
{
  "fully_qualified_name": "percolate-agents-researcher",
  "short_name": "researcher",
  "version": "1.0.0",
  "description": "Research agent that searches REM memory and synthesizes findings",
  "system_prompt": "You are a research assistant with access to a personal knowledge base. When asked a question:\n1. Search the knowledge base for relevant information\n2. Synthesize findings into a coherent response\n3. Cite sources with resource IDs\n4. Acknowledge gaps in knowledge when present",
  "output_schema": {
    "type": "object",
    "properties": {
      "findings": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "summary": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "source_ids": {"type": "array", "items": {"type": "string"}}
          },
          "required": ["summary", "confidence", "source_ids"]
        }
      },
      "sources": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "resource_id": {"type": "string"},
            "title": {"type": "string"},
            "relevance": {"type": "number", "minimum": 0, "maximum": 1}
          },
          "required": ["resource_id", "title", "relevance"]
        }
      },
      "knowledge_gaps": {
        "type": "array",
        "items": {"type": "string"}
      }
    },
    "required": ["findings", "sources"]
  },
  "tools": [
    {
      "mcp_server": "percolate",
      "tool_name": "search_knowledge_base",
      "usage": "Search REM memory for relevant information using semantic or keyword search"
    },
    {
      "mcp_server": "percolate",
      "tool_name": "get_entity_details",
      "usage": "Retrieve detailed information about a specific entity"
    },
    {
      "mcp_server": "percolate",
      "tool_name": "traverse_entity_graph",
      "usage": "Navigate relationships between entities to discover connections"
    }
  ],
  "metadata": {
    "author": "percolate-core",
    "created": "2025-01-15T00:00:00Z",
    "tags": ["research", "knowledge-base", "synthesis"],
    "license": "MIT"
  }
}
```

### Schema fields

- `fully_qualified_name`: Unique identifier (kebab-case, namespaced)
- `short_name`: Human-readable name for CLI/UI (alphanumeric, lowercase)
- `version`: Semantic version (major.minor.patch)
- `description`: One-sentence summary of agent purpose
- `system_prompt`: Detailed instructions for agent behavior
- `output_schema`: JSON Schema defining structured output format
- `tools`: Array of MCP tool references (not inline functions)
- `metadata`: Optional metadata for discovery and attribution

### Design principles

1. **Pure data artifacts** - No executable code in schema
2. **Tool references only** - MCP server + tool name, not inline logic
3. **Versioned** - Semantic versioning for compatibility tracking
4. **Self-documenting** - Schema should explain agent purpose and capabilities
5. **Composable** - Tools can be shared across multiple agents

## REM memory schema

The REM (Resources-Entities-Moments) model stores three types of data with specific key conventions.

### Key structure

```
# Resources - Chunked documents with embeddings
resource:{tenant_id}:{resource_id} → {
  content: string,
  metadata: {
    title: string,
    source: string,
    created_at: timestamp,
    content_type: string,
    checksum: string
  },
  embedding_id: string,
  chunk_index: int,
  total_chunks: int
}

# Entities - Graph nodes with KV properties
entity:{tenant_id}:{entity_id} → {
  type: string,  # person, organization, concept, etc.
  properties: {
    name: string,
    description?: string,
    ...custom_fields
  },
  created_at: timestamp,
  updated_at: timestamp
}

# Edges - Relationships between entities
edge:{tenant_id}:{src_id}:{dst_id}:{edge_type} → {
  properties: {...},
  weight: float,  # relationship strength
  created_at: timestamp
}

# Moments - Temporal classifications
moment:{tenant_id}:{timestamp}:{moment_id} → {
  classifications: [string],  # tags, categories
  references: [
    {
      type: "resource" | "entity",
      id: string
    }
  ],
  metadata: {...}
}

# Indexes
index:resource:{tenant_id}:{content_hash} → {resource_id}
index:entity:{tenant_id}:{normalized_name} → [entity_ids]
index:moment:{tenant_id}:{classification}:{timestamp} → [moment_ids]
```

### Tenant isolation

All keys are scoped by `tenant_id` to ensure data isolation:

- Separate RocksDB column family per tenant
- No cross-tenant queries possible
- Tenant ID validated at authentication layer
- Tenant ID propagated through all operations

### Search indexes

1. **Vector index** (HNSW): Semantic similarity search
   - Key: `vector:{tenant_id}:{embedding_id}`
   - Value: High-dimensional embedding vector

2. **Trigram index**: Fuzzy entity name matching
   - Key: `trigram:{tenant_id}:{trigram}`
   - Value: List of entity IDs containing the trigram

3. **Temporal index**: Time-based moment lookups
   - Key: `temporal:{tenant_id}:{year}:{month}:{day}`
   - Value: List of moment IDs in that time range

### Normalization rules

Entity names are normalized for consistent indexing:

```python
def normalize_entity_name(name: str) -> str:
    """Normalize entity name for indexing."""
    return (
        name.lower()
        .strip()
        .replace("-", " ")
        .replace("_", " ")
        # Collapse multiple spaces
        " ".join(name.split())
    )
```

Resource content hashes use SHA-256:

```python
import hashlib

def compute_content_hash(content: str) -> str:
    """Compute content hash for deduplication."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
```

## CLI command schema

Commands follow a consistent structure for clarity and maintainability.

### Command definition

```python
import typer
from typing_extensions import Annotated
from pathlib import Path

app = typer.Typer(
    name="percolate",
    help="Privacy-first personal AI node",
    add_completion=False
)

@app.command()
def ingest(
    file: Annotated[
        Path,
        typer.Argument(
            help="File to ingest into REM memory",
            exists=True,
            file_okay=True,
            dir_okay=False,
            resolve_path=True
        )
    ],
    tenant: Annotated[
        str,
        typer.Option(
            "--tenant", "-t",
            help="Tenant ID (defaults to active tenant)"
        )
    ] = "default",
    parse: Annotated[
        bool,
        typer.Option(
            "--parse/--no-parse",
            help="Parse document structure and extract entities"
        )
    ] = True,
    chunk_size: Annotated[
        int,
        typer.Option(
            "--chunk-size",
            help="Maximum characters per chunk"
        )
    ] = 1000,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Output results as JSON"
        )
    ] = False
) -> None:
    """Ingest a document into REM memory.

    Parses the document, chunks the content, generates embeddings,
    and stores everything in the tenant's REM database.

    Examples:
        percolate ingest document.pdf
        percolate ingest --tenant user-123 --chunk-size 500 doc.txt
        percolate ingest --no-parse data.csv --json
    """
    # Implementation
```

### Output conventions

Use `rich` for human-readable output:

```python
from rich.console import Console
from rich.progress import Progress

console = Console()

# Success
console.print("[green]✓[/green] Document ingested successfully")

# Error
console.print("[red]✗[/red] Failed to parse document", err=True)

# Warning
console.print("[yellow]⚠[/yellow] Large file, this may take a while")

# Info
console.print("[blue]ℹ[/blue] Processing 127 chunks")

# Progress
with Progress() as progress:
    task = progress.add_task("[cyan]Ingesting...", total=100)
    # Update progress
```

JSON output for machine parsing:

```python
import json

if json_output:
    result = {
        "status": "success",
        "resource_id": "res-abc123",
        "chunks": 127,
        "entities_extracted": 15
    }
    print(json.dumps(result, indent=2))
```

## Authentication data schema

### Device registration

```json
{
  "device_id": "dev-abc123",
  "public_key": "ed25519:base64_encoded_key",
  "device_name": "iPhone 15 Pro",
  "platform": "ios",
  "os_version": "17.2",
  "app_version": "1.0.0",
  "registered_at": "2025-01-15T12:00:00Z"
}
```

### OAuth token response

```json
{
  "access_token": "opaque_random_32_bytes",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "opaque_random_32_bytes",
  "scope": "read write"
}
```

### Session storage

```
session:{tenant_id}:{session_id} → {
  device_id: string,
  access_token_hash: string,  # SHA-256
  refresh_token_hash: string,  # SHA-256
  created_at: timestamp,
  expires_at: timestamp,
  last_used: timestamp,
  scope: [string]
}
```

## MCP tool schema

Tools exposed via Model Context Protocol follow this schema:

```json
{
  "name": "search_knowledge_base",
  "description": "Search REM memory using semantic or keyword search",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Search query (natural language)"
      },
      "search_type": {
        "type": "string",
        "enum": ["semantic", "keyword", "hybrid"],
        "default": "hybrid"
      },
      "limit": {
        "type": "integer",
        "minimum": 1,
        "maximum": 100,
        "default": 10
      },
      "filters": {
        "type": "object",
        "properties": {
          "resource_types": {
            "type": "array",
            "items": {"type": "string"}
          },
          "date_range": {
            "type": "object",
            "properties": {
              "start": {"type": "string", "format": "date-time"},
              "end": {"type": "string", "format": "date-time"}
            }
          }
        }
      }
    },
    "required": ["query"]
  }
}
```

## Observability schema

OpenTelemetry spans follow this convention:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span(
    "memory.search",
    attributes={
        "tenant_id": tenant_id,
        "search_type": search_type,
        "query_length": len(query)
    }
) as span:
    # Operation
    span.set_attribute("results_count", len(results))
    span.set_status(trace.Status(trace.StatusCode.OK))
```

Span naming convention:
- `{module}.{operation}` (e.g., `memory.search`, `agents.execute`)
- Use lowercase with underscores
- Keep operation names consistent across the codebase

## References

- [Agent-lets architecture](03-agentlets.md)
- [REM memory design](02-rem-memory.md)
- [MCP protocol](08-mcp-protocol.md)
- [Authentication flow](components/auth-flow.md)
