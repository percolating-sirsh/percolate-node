"""Percolate JSON Schema extensions.

These extensions are stored in `json_schema_extra` of Pydantic models
to configure REM database behavior, agent-let tools, and indexing.
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class MCPTool(BaseModel):
    """MCP tool reference for agent-let schemas.

    Tools are callable functions exposed by MCP servers.

    Example:
        >>> tool = MCPTool(
        ...     mcp_server="percolate",
        ...     tool_name="search_knowledge_base"
        ... )
    """

    mcp_server: str = Field(description="MCP server name (e.g., 'percolate')")
    tool_name: str = Field(
        description="Tool name within server (e.g., 'search_knowledge_base')"
    )

    model_config = ConfigDict(frozen=True)


class MCPResource(BaseModel):
    """MCP resource reference for agent-let schemas.

    Resources are read-only data sources exposed by MCP servers.
    They can be used like tools via the read_resource tool.

    Example:
        >>> resource = MCPResource(
        ...     mcp_server="percolate",
        ...     resource_uri="sessions://list"
        ... )
    """

    mcp_server: str = Field(description="MCP server name (e.g., 'percolate')")
    resource_uri: str = Field(
        description="Resource URI (e.g., 'sessions://list')"
    )

    model_config = ConfigDict(frozen=True)


class PercolateSchemaExtensions(BaseModel):
    """JSON Schema extensions for Percolate REM database.

    These extensions configure schema behavior in the REM database:
    - Tools: MCP tool references for agent-lets
    - Resources: MCP resource references for agent-lets
    - Name: Fully qualified unique name (e.g., 'percolate.entities.Article')
    - Short name: Brief identifier for CLI/API
    - Embedding fields: Auto-embed these fields on insert
    - Indexed columns: SQL predicate columns for fast queries
    - Key field: Primary identifier for entity lookups
    - Default embedding provider: Override default provider

    Example:
        >>> from pydantic import BaseModel, ConfigDict
        >>> class Article(BaseModel):
        ...     '''Article entity with semantic search.'''
        ...     title: str
        ...     content: str
        ...     category: str
        ...
        ...     model_config = ConfigDict(
        ...         json_schema_extra=PercolateSchemaExtensions(
        ...             name="percolate.entities.Article",  # Fully qualified
        ...             short_name="article",
        ...             embedding_fields=["title", "content"],
        ...             indexed_columns=["category"],
        ...             key_field="title",
        ...             default_embedding_provider="fastembed"
        ...         ).model_dump()
        ...     )
    """

    # Agent-let tools configuration
    tools: list[MCPTool] = Field(
        default_factory=list,
        description="MCP tool references for agent-lets (callable functions)",
    )

    resources: list[MCPResource] = Field(
        default_factory=list,
        description="MCP resource references for agent-lets (read-only data)",
    )

    # Schema identification
    name: str = Field(
        description="Fully qualified schema name (e.g., 'percolate.entities.Article'). Must be unique across all schemas.",
    )

    short_name: str = Field(
        description="Brief identifier for CLI/API (alphanumeric + hyphens, e.g., 'article')",
    )

    # REM database indexing
    embedding_fields: list[str] = Field(
        default_factory=list,
        description="Fields to auto-embed on insert (for semantic search)",
    )

    indexed_columns: list[str] = Field(
        default_factory=list,
        description="SQL predicate columns (for fast WHERE queries)",
    )

    key_field: Optional[str] = Field(
        default=None,
        description="Primary identifier field for entity lookups",
    )

    # Embedding configuration
    default_embedding_provider: str = Field(
        default="fastembed",
        description="Default embedding provider (fastembed, openai, voyage)",
    )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "name": "percolate.entities.Article",
                    "short_name": "article",
                    "embedding_fields": ["title", "content"],
                    "indexed_columns": ["category", "published_date"],
                    "key_field": "slug",
                    "default_embedding_provider": "openai",
                },
                {
                    "name": "percolate.agents.ResearchAgent",
                    "short_name": "research-agent",
                    "tools": [
                        {
                            "mcp_server": "percolate",
                            "tool_name": "search_knowledge_base",
                        },
                        {
                            "mcp_server": "percolate",
                            "tool_name": "lookup_entity",
                        },
                    ],
                    "resources": [
                        {
                            "mcp_server": "percolate",
                            "resource_uri": "sessions://list",
                        },
                        {
                            "mcp_server": "percolate",
                            "resource_uri": "moments://list",
                        },
                    ],
                    "embedding_fields": ["description"],
                    "key_field": "agent_id",
                },
            ]
        },
    )
