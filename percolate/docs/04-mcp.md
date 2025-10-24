# Model Context Protocol (MCP)

## Table of Contents

- [Overview](#overview)
- [MCP Server Setup](#mcp-server-setup)
- [Tool Implementations](#tool-implementations)
- [Resource Providers](#resource-providers)
- [Session Management](#session-management)
- [Client Integration](#client-integration)

## Overview

Percolate implements the Model Context Protocol (MCP) to expose tools and resources to LLM clients like Claude Desktop.

**Key Features:**
- Unified search across REM memory
- Entity graph navigation
- Document parsing
- Agent-let management
- Feedback collection

## MCP Server Setup

### Server Configuration

```python
from fastmcp import FastMCP

mcp = FastMCP("percolate")

@mcp.tool()
async def search_knowledge_base(
    query: str,
    knowledge_base: str = "general",
    limit: int = 5
) -> dict:
    """Search across REM memory"""
    return await search_service.search(query, knowledge_base, limit)
```

### Endpoint

```http
GET /mcp
Content-Type: text/event-stream
```

### Client Configuration

Add to Claude Desktop config:

```json
{
  "mcpServers": {
    "percolate": {
      "url": "http://localhost:8000/mcp",
      "transport": "sse"
    }
  }
}
```

## Tool Implementations

### search_knowledge_base

Unified search across all REM data:

```python
@mcp.tool()
async def search_knowledge_base(
    query: str,
    knowledge_base: KnowledgeBase = "general",
    id: str | None = None,
    category: str | None = None,
    since_date: datetime | None = None,
    until_date: datetime | None = None,
    limit: int = 5
) -> dict:
    """Search REM memory with semantic vector search.

    Args:
        query: Semantic search query
        knowledge_base: Which knowledge base to search
            - general: All indexed content
            - codebase: Code examples (python, xml, test)
            - zendesk_tickets: Historical support tickets
            - jira_issues: Issue tracker history
        id: Exact ID lookup (resource_id, entity_id)
        category: Filter by category
        since_date: Filter results after this date
        until_date: Filter results before this date
        limit: Maximum results (default: 5, max: 20)

    Returns:
        Dictionary with search results and metadata
    """
```

**Example Usage:**

```python
# Semantic search
results = await search_knowledge_base(
    query="authentication flows",
    knowledge_base="general",
    limit=10
)

# ID lookup
resource = await search_knowledge_base(
    query="",
    id="resource-123"
)

# Category filter
code = await search_knowledge_base(
    query="parser implementation",
    knowledge_base="codebase",
    category="python"
)
```

### lookup_entity

Entity graph navigation:

```python
@mcp.tool()
async def lookup_entity(
    entity_type: str,
    query: str,
    include_related: bool = False,
    relationship_types: list[str] | None = None,
    depth: int = 1
) -> dict:
    """Look up entities in the global entity registry.

    Args:
        entity_type: Type of entity (person, company, carrier, etc.)
        query: Entity key or description
        include_related: Include related entities via graph traversal
        relationship_types: Which relationships to include
        depth: Graph traversal depth (1-3)

    Returns:
        Dictionary with entity details and related entities
    """
```

**Example Usage:**

```python
# Lookup by key
entity = await lookup_entity(
    entity_type="carrier",
    query="dhl"
)

# Lookup with relationships
entity = await lookup_entity(
    entity_type="carrier",
    query="dhl",
    include_related=True,
    relationship_types=["offers_service", "has_endpoint"],
    depth=2
)
```

### parse_document

Document processing:

```python
@mcp.tool()
async def parse_document(
    file_path: str,
    extract_types: list[str] | None = None,
    flow_id: str | None = None,
    ticket: str | None = None
) -> dict:
    """Parse document and extract structured information.

    Args:
        file_path: Path to document file
        extract_types: What to extract (text, tables, images, metadata)
        flow_id: Optional flow ID for tracking
        ticket: Optional Jira ticket to associate

    Supports:
        - Text: TXT, MD, JSON, YAML, XML, CSV, TSV
        - Documents: PDF, DOCX
        - Archives: ZIP (containing any supported files)

    Returns:
        Dictionary with extracted content
    """
```

**Example Usage:**

```python
# Parse PDF
result = await parse_document(
    file_path="/path/to/document.pdf",
    extract_types=["text", "tables"],
    ticket="TAP-1234"
)

# Parse ZIP archive
result = await parse_document(
    file_path="/path/to/archive.zip",
    flow_id="carrier-docs-v1"
)
```

### create_agent

Dynamic agent-let instantiation:

```python
@mcp.tool()
async def create_agent(
    user_id: str,
    agent_name: str,
    description: str,
    output_schema: dict,
    tools: list[dict] | None = None
) -> dict:
    """Create a new user agent.

    Args:
        user_id: User ID (UUID from OIDC)
        agent_name: Agent name (alphanumeric with hyphens)
        description: System prompt
        output_schema: JSON Schema for structured output
        tools: Optional list of MCP tool configs

    Returns:
        Dictionary with status and agent details
    """
```

### ask_agent

Execute agent:

```python
@mcp.tool()
async def ask_agent(
    agent_uri: str,
    user_id: str,
    prompt: str,
    model: str | None = None,
    session_id: str | None = None,
    case_id: str | None = None
) -> dict:
    """Chat with any agent (system or user).

    Args:
        agent_uri: Agent URI (system or user/sub/name)
        user_id: User ID (UUID)
        prompt: User prompt
        model: Optional model override
        session_id: Session UUID for tracking
        case_id: Optional case ID for project linking

    Returns:
        Dictionary with agent response and metadata
    """
```

### submit_feedback

Evaluation feedback:

```python
@mcp.tool()
async def submit_feedback(
    session_id: str,
    feedback_type: str,
    rating: str | None = None,
    feedback_text: str | None = None,
    user_id: str | None = None
) -> dict:
    """Submit feedback for an agent interaction.

    Args:
        session_id: Session UUID
        feedback_type: Type (thumbs_up, thumbs_down, comment, rating)
        rating: Optional rating (great, good, bad, terrible)
        feedback_text: Optional comment
        user_id: Optional user identifier

    Returns:
        Dictionary with status
    """
```

## Resource Providers

### Static Resources

```python
@mcp.resource("cda://field-definitions")
async def cda_field_definitions() -> str:
    """All CDA field definitions with types and validation rules"""
    return await cda_service.get_field_definitions()

@mcp.resource("cda://carriers")
async def cda_carriers() -> str:
    """Complete carrier registry"""
    return await cda_service.get_carriers()

@mcp.resource("system-agents://list")
async def system_agents() -> str:
    """Built-in system agents"""
    return await agent_service.list_system_agents()
```

### Dynamic Resources

```python
@mcp.resource("case://ticket/{ticket}")
async def case_details(ticket: str) -> str:
    """Case details for specific Jira ticket"""
    return await case_service.get_case(ticket)

@mcp.resource("parse-flow://{flow_id}")
async def parse_job_status(flow_id: str) -> str:
    """Parse job status and results"""
    return await parse_service.get_job_status(flow_id)
```

## Session Management

### Context Tracking

MCP interactions are tracked with session context:

```python
from percolate.agents.context import ExecutionContext

context = ExecutionContext(
    tenant_id=user.tenant_id,
    session_id=request.headers.get("X-Session-ID"),
    trace_id=request.headers.get("X-Trace-ID"),
    user_id=user.user_id
)
```

### Message Storage

All tool calls are stored:

```python
# Store user message
await message_service.create_message(
    session_id=context.session_id,
    role="user",
    content=query,
    trace_id=context.trace_id
)

# Store assistant response
await message_service.create_message(
    session_id=context.session_id,
    role="assistant",
    content=result,
    trace_id=context.trace_id
)
```

## Client Integration

### Claude Desktop

```json
{
  "mcpServers": {
    "percolate": {
      "url": "http://localhost:8000/mcp",
      "transport": "sse",
      "env": {
        "PERCOLATE_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Python Client

```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{"role": "user", "content": "Search for auth docs"}],
    tools=[{
        "type": "custom",
        "server": "percolate",
        "name": "search_knowledge_base"
    }]
)
```

### HTTP Client

```bash
# Establish SSE connection
curl -N http://localhost:8000/mcp \
  -H "Authorization: Bearer ${PERCOLATE_API_KEY}"

# Send tool call
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "search_knowledge_base",
    "arguments": {
      "query": "authentication flows",
      "limit": 5
    }
  },
  "id": 1
}
```

## Best Practices

### Tool Design

1. **Single responsibility** - one clear purpose per tool
2. **Descriptive names** - verb_noun pattern
3. **Clear docstrings** - explain args and returns
4. **Type hints** - enable validation
5. **Error handling** - return structured errors

### Resource Design

1. **Stable URIs** - no breaking changes
2. **Fast responses** - cache when possible
3. **Structured data** - JSON or markdown
4. **Versioning** - include in URI if needed
5. **Documentation** - describe resource purpose

### Performance

1. **Limit result sizes** - default to small limits
2. **Use pagination** - for large result sets
3. **Cache resources** - reduce redundant lookups
4. **Async operations** - non-blocking I/O
5. **Timeout handling** - fail fast on slow operations
