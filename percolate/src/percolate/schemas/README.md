# Percolate JSON Schema extensions

This module defines Pydantic models for Percolate's JSON Schema extensions.

## Overview

Percolate extends standard JSON Schema with custom fields stored in `json_schema_extra` to configure:

- **REM database behavior**: Embedding fields, indexed columns, key fields
- **Agent-let tools**: MCP tool references for agent schemas
- **Schema identification**: Display names and short names for CLI/API
- **Embedding providers**: Override default provider per schema

## Models

### PercolateSchemaExtensions

Main extension model for all Percolate schemas.

```python
from percolate.schemas import PercolateSchemaExtensions
from pydantic import BaseModel, ConfigDict

class Article(BaseModel):
    title: str
    content: str

    model_config = ConfigDict(
        json_schema_extra=PercolateSchemaExtensions(
            name="Article",
            short_name="article",
            embedding_fields=["title", "content"],
            indexed_columns=["category"],
            key_field="title"
        ).model_dump()
    )
```

### MCPTool

MCP tool reference for agent-let schemas.

```python
from percolate.schemas import MCPTool

tool = MCPTool(
    mcp_server="carrier",
    tool_name="search_knowledge_base"
)
```

### TenantContext

Gateway-stored context for tenant coordination.

```python
from percolate.schemas import TenantContext

context = TenantContext(
    tenant_id="tenant_12345678",
    tier="premium",
    account_status="active",
    peer_nodes=["node-1.percolationlabs.ai:9000"],
    quotas=ResourceQuotas(
        storage_gb=100,
        api_calls_per_day=10000
    )
)
```

## Rust implementation

The Rust implementation in `percolate-rocks` validates these extensions:

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MCPTool {
    pub mcp_server: String,
    pub tool_name: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PercolateSchemaExtensions {
    pub name: String,
    pub short_name: String,
    pub tools: Vec<MCPTool>,
    pub embedding_fields: Vec<String>,
    pub indexed_columns: Vec<String>,
    pub key_field: Option<String>,
    pub default_embedding_provider: String,
}
```

## Usage in percolate-rocks

The Rust database validates schemas and extracts extensions:

```python
import rem_db

# Schema with extensions
schema = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"}
    },
    "x-percolate": {
        "name": "Article",
        "short_name": "article",
        "embedding_fields": ["title", "content"],
        "indexed_columns": ["category"],
        "key_field": "title"
    }
}

# Register schema
db = rem_db.Database("/path/to/db")
db.register_schema(schema)

# Insert with auto-embedding
db.insert("article", {"title": "Hello", "content": "World"})
```

## See also

- [JSON Schema Extensions](../../docs/protocols/json-schema-extensions.md) - Full documentation
- [Schema Design](../../.spikes/percolate-rocks/docs/schema.md) - REM schema patterns
- [Agent-lets](../../docs/03-agentlets.md) - Agent-let architecture
