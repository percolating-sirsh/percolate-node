# JSON Schema extensions

All Percolate schemas use standard JSON Schema with custom extensions for REM database behavior, agent-let configuration, and indexing.

## Overview

Extensions are stored in the `json_schema_extra` field of Pydantic models and control:

- **Agent-let tools**: MCP tool references
- **Schema identification**: Display name and short name
- **Database indexing**: Embedding fields and SQL columns
- **Key fields**: Primary identifier for entity lookups
- **Embedding providers**: Override default provider

## PercolateSchemaExtensions model

Full Pydantic definition with inline comments:

```python
from percolate.schemas import (
    PercolateSchemaExtensions,
    MCPTool,
    MCPResource,
)
from pydantic import BaseModel, ConfigDict

class MySchema(BaseModel):
    """Schema description."""
    field1: str
    field2: str

    model_config = ConfigDict(
        json_schema_extra=PercolateSchemaExtensions(
            # Fully qualified name - must be unique across all schemas
            # Format: <namespace>.<category>.<ClassName>
            # Examples: "percolate.entities.Article", "percolate.agents.ResearchAgent"
            name="percolate.entities.MySchema",

            # Short name for CLI/API usage (alphanumeric + hyphens)
            # Used in: rem insert my-schema, rem search --schema=my-schema
            short_name="my-schema",

            # Fields to auto-embed on insert (for semantic search)
            embedding_fields=["field1"],

            # Columns for SQL WHERE clauses (indexed for fast queries)
            indexed_columns=["field2"],

            # Primary identifier field for entity lookups
            key_field="field1",

            # Override default embedding provider for this schema
            # Options: "fastembed" (local), "openai", "voyage"
            default_embedding_provider="fastembed"
        ).model_dump()
    )
```

## Extension fields

### Agent-let configuration

**tools** (`list[MCPTool]`, default: `[]`)

MCP tool references for agent-let schemas (callable functions).

```python
from percolate.schemas import MCPTool

PercolateSchemaExtensions(
    name="percolate.agents.ResearchAgent",
    short_name="research-agent",
    tools=[
        # Search REM database
        MCPTool(mcp_server="percolate", tool_name="search_knowledge_base"),

        # Entity graph lookups
        MCPTool(mcp_server="percolate", tool_name="lookup_entity"),
    ]
)
```

**resources** (`list[MCPResource]`, default: `[]`)

MCP resource references for agent-let schemas (read-only data sources).

Resources can be accessed via the `read_resource` tool at runtime.

```python
from percolate.schemas import MCPResource

PercolateSchemaExtensions(
    name="percolate.agents.ResearchAgent",
    short_name="research-agent",
    resources=[
        # Session history
        MCPResource(mcp_server="percolate", resource_uri="sessions://list"),

        # Temporal classifications
        MCPResource(mcp_server="percolate", resource_uri="moments://list"),
    ]
)
```

### Schema identification

**name** (`str`, required)

Fully qualified schema name. Must be unique across all schemas in REM database.

Format: `<namespace>.<category>.<ClassName>`

Examples:
- `"percolate.entities.Article"` - Entity schema
- `"percolate.agents.ResearchAgent"` - Agent schema
- `"myapp.resources.Document"` - Custom application schema

```python
name="percolate.entities.Article"  # Fully qualified, unique identifier
```

**short_name** (`str`, required)

Brief identifier for CLI/API usage. Alphanumeric with hyphens.

```python
short_name="article"  # CLI: rem insert article
```

### Database indexing

**embedding_fields** (`list[str]`, default: `[]`)

Fields to automatically embed on insert for semantic search.

```python
embedding_fields=["title", "content"]  # Auto-embed these fields
```

**indexed_columns** (`list[str]`, default: `[]`)

SQL predicate columns for fast WHERE queries.

```python
indexed_columns=["category", "published_date"]  # Fast filtering
```

**key_field** (`str | None`, default: `None`)

Primary identifier field for entity lookups.

```python
key_field="slug"  # Unique key for lookups
```

### Embedding configuration

**default_embedding_provider** (`str`, default: `"fastembed"`)

Override default embedding provider for this schema.

Options:
- `"fastembed"` - Local embeddings (fast, no API costs)
- `"openai"` - OpenAI embeddings (accurate, API costs)
- `"voyage"` - Voyage AI embeddings (domain-specific)

```python
default_embedding_provider="openai"  # Use OpenAI for this schema
```

## Complete examples

### Entity schema (articles)

```python
from pydantic import BaseModel, ConfigDict, Field
from percolate.schemas import PercolateSchemaExtensions

class Article(BaseModel):
    """Article with semantic search and filtering."""

    slug: str = Field(description="Unique slug")
    title: str = Field(description="Article title")
    content: str = Field(description="Article content")
    category: str = Field(description="Category")
    published_date: str = Field(description="Published date (ISO 8601)")

    model_config = ConfigDict(
        json_schema_extra=PercolateSchemaExtensions(
            # Fully qualified name - unique across all schemas
            name="percolate.entities.Article",

            # Short name for CLI usage
            short_name="article",

            # Auto-embed title and content on insert
            embedding_fields=["title", "content"],

            # Index category and date for fast SQL queries
            indexed_columns=["category", "published_date"],

            # Primary key field for lookups
            key_field="slug",

            # Use local embeddings (no API costs)
            default_embedding_provider="fastembed",
        ).model_dump()
    )
```

**Usage:**

```bash
# Insert article (auto-embeds title + content)
echo '{"slug": "hello", "title": "Hello World", "content": "..."}' | rem insert article

# Semantic search
rem search "greeting examples" --schema=article

# SQL filtering
rem query "SELECT * FROM article WHERE category = 'tech'"

# Entity lookup
rem lookup article --key=hello
```

### Agent-let schema

```python
from pydantic import BaseModel, ConfigDict, Field
from percolate.schemas import (
    PercolateSchemaExtensions,
    MCPTool,
    MCPResource,
)

class ResearchAgent(BaseModel):
    """Agent for research and analysis tasks."""

    agent_id: str = Field(description="Agent identifier")
    description: str = Field(description="Agent description")
    system_prompt: str = Field(description="System prompt")

    model_config = ConfigDict(
        json_schema_extra=PercolateSchemaExtensions(
            # Fully qualified name for agent schema
            name="percolate.agents.ResearchAgent",

            # Short name for CLI usage
            short_name="research-agent",

            # MCP tools this agent can call
            tools=[
                # Search REM database
                MCPTool(
                    mcp_server="percolate",
                    tool_name="search_knowledge_base",
                ),
                # Entity graph lookups
                MCPTool(
                    mcp_server="percolate",
                    tool_name="lookup_entity",
                ),
            ],

            # MCP resources this agent can access (via read_resource tool)
            resources=[
                # Session history
                MCPResource(
                    mcp_server="percolate",
                    resource_uri="sessions://list",
                ),
                # Temporal classifications
                MCPResource(
                    mcp_server="percolate",
                    resource_uri="moments://list",
                ),
            ],

            # Embed description for agent similarity search
            embedding_fields=["description"],

            # Primary key for agent lookup
            key_field="agent_id",
        ).model_dump()
    )
```

**Usage:**

```bash
# Insert agent
echo '{"agent_id": "research-v1", "description": "...", "system_prompt": "..."}' | rem insert research-agent

# Find similar agents
rem search "research analysis agent" --schema=research-agent

# Execute agent
percolate agent run research-v1 --prompt "Analyze recent conversations"
```

## Validation rules

1. **name** must be unique across schemas
2. **short_name** must be alphanumeric with hyphens
3. **embedding_fields** must reference existing model fields
4. **indexed_columns** must reference existing model fields
5. **key_field** must reference an existing model field
6. **tools** MCP server and tool names must exist

## Storage format

Extensions are stored in `json_schema_extra` and serialized to JSON Schema:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slug": {"type": "string"},
    "title": {"type": "string"},
    "content": {"type": "string"}
  },
  "required": ["slug", "title", "content"],
  "x-percolate": {
    "name": "Article",
    "short_name": "article",
    "embedding_fields": ["title", "content"],
    "indexed_columns": ["category"],
    "key_field": "slug",
    "default_embedding_provider": "fastembed"
  }
}
```

## Rust implementation

The Rust implementation validates and uses these extensions:

```rust
// src/schema/extensions.rs
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

impl PercolateSchemaExtensions {
    pub fn from_json_schema(schema: &Value) -> Result<Self> {
        let ext = schema["x-percolate"]
            .as_object()
            .ok_or(SchemaError::MissingExtensions)?;

        serde_json::from_value(ext.clone())
            .map_err(|e| SchemaError::InvalidExtensions(e))
    }
}
```

## Migration from old schemas

Old schemas without extensions can be migrated:

```python
# Before
class OldArticle(BaseModel):
    title: str
    content: str

# After
class Article(BaseModel):
    title: str
    content: str

    model_config = ConfigDict(
        json_schema_extra=PercolateSchemaExtensions(
            name="Article",
            short_name="article",
            embedding_fields=["title", "content"],
        ).model_dump()
    )
```

## See also

- [Schema Design](../schema.md) - REM schema patterns
- [Agent-lets Architecture](../03-agentlets.md) - Agent-let patterns
- [MCP Protocol](../08-mcp-protocol.md) - MCP tool integration
