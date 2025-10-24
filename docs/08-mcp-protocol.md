# MCP Protocol Implementation

## Overview

Percolate implements the **Model Context Protocol (MCP)** to expose agent-lets, knowledge base search, and resource access to AI assistants like Claude Desktop.

**Key Features:**
- StreamableHTTP transport (FastMCP)
- JSON-RPC 2.0 protocol
- Tools, Resources, and Prompts support
- OpenTelemetry instrumentation
- Tenant-scoped operations

## Architecture

### Protocol Stack

```
┌─────────────────────────────────────┐
│   Claude Desktop / MCP Client       │
└─────────────────┬───────────────────┘
                  │ HTTP/JSON-RPC
                  │ (StreamableHTTP)
┌─────────────────▼───────────────────┐
│   FastAPI Server (:8765)            │
│   ┌─────────────────────────────┐   │
│   │  POST /mcp                  │   │
│   │  (FastMCP Router)           │   │
│   └──────────┬──────────────────┘   │
└──────────────┼──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   MCP Server (FastMCP)              │
│   ├── Tools                         │
│   │   ├── ask_agent                 │
│   │   ├── search_knowledge_base     │
│   │   ├── create_agent              │
│   │   └── lookup_entity             │
│   ├── Resources                     │
│   │   ├── agentlet://{uri}          │
│   │   ├── system-agents://list      │
│   │   └── my-agents://list          │
│   └── Prompts (future)              │
└─────────────────────────────────────┘
```

### Transport: Streamable HTTP

Percolate uses **Streamable HTTP** (not stdio or SSE) for MCP transport:

**Why Streamable HTTP?**
- Works over standard HTTP/HTTPS
- Firewall-friendly (no websockets)
- Simple load balancing
- Compatible with FastAPI
- No special client requirements

**Protocol Details:**
- Endpoint: `POST /mcp`
- Content-Type: `application/json`
- JSON-RPC 2.0 messages
- Single request/response (not streaming chunks)

### JSON-RPC message format

All MCP messages follow JSON-RPC 2.0:

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "ask_agent",
    "arguments": {
      "agent_uri": "percolate-test-agent",
      "tenant_id": "test-tenant",
      "prompt": "Analyze this document"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"status\": \"success\", \"response\": {...}}"
      }
    ]
  }
}
```

**Error:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32600,
    "message": "Invalid request",
    "data": {"details": "Missing tenant_id"}
  }
}
```

## Components

### 1. Tools

Tools are **functions** that MCP clients can invoke.

**Available Tools:**

#### `ask_agent`
Execute an agent-let with a user prompt.

**Parameters:**
- `agent_uri` (string, required): Agent identifier (e.g., "percolate-researcher")
- `tenant_id` (string, required): Tenant scope
- `prompt` (string, required): User prompt for the agent
- `user_id` (string, optional): User identifier
- `session_id` (string, optional): Session tracking ID
- `model` (string, optional): Model override (e.g., "claude-opus-4")

**Returns:**
```json
{
  "status": "success",
  "response": {
    "answer": "Structured agent response",
    "confidence": 0.95,
    "tags": ["research", "analysis"]
  },
  "trace_id": "abc123",
  "model": "claude-sonnet-4.5"
}
```

#### `search_knowledge_base`
Search REM memory using vector and fuzzy search.

**Parameters:**
- `query` (string, required): Search query
- `tenant_id` (string, required): Tenant scope
- `knowledge_base` (enum, optional): Scope (general|codebase|documents)
- `limit` (integer, optional): Max results (default: 5, max: 20)

**Returns:**
```json
{
  "status": "success",
  "results": [
    {
      "content": "Matching text snippet",
      "score": 0.92,
      "source": "resource://doc-123",
      "metadata": {"type": "pdf", "page": 5}
    }
  ],
  "count": 3
}
```

#### `create_agent`
Create a new user-scoped agent-let.

**Parameters:**
- `tenant_id` (string, required): Tenant scope
- `user_id` (string, required): User creating the agent
- `agent_name` (string, required): Unique agent name
- `description` (string, required): System prompt
- `output_schema` (object, required): JSON Schema for structured output
- `tools` (array, optional): MCP tools the agent can use

**Returns:**
```json
{
  "status": "success",
  "agent_uri": "agentlet://user/user-123/my-custom-agent",
  "message": "Agent created successfully"
}
```

#### `lookup_entity`
Lookup entities in the REM graph.

**Parameters:**
- `entity_type` (string, required): Entity type (carrier|service|person|etc.)
- `query` (string, required): Entity name or description
- `tenant_id` (string, required): Tenant scope
- `include_related` (boolean, optional): Include graph relationships

**Returns:**
```json
{
  "status": "success",
  "entity": {
    "id": "entity-456",
    "type": "service",
    "name": "Express Shipping",
    "properties": {"sla": "next-day"}
  },
  "related": [...]
}
```

### 2. Resources

Resources are **read-only data** accessible via URI.

**Available Resources:**

#### System Agents
- URI: `system-agents://list`
- Description: List all system-provided agent-lets
- Returns: JSON array of agent schemas

#### User Agents
- URI: `my-agents://list`
- Description: List user's custom agent-lets
- Returns: JSON array of user agent schemas

#### Specific Agent
- URI: `agentlet://{uri}`
- Description: Load specific agent-let schema
- Returns: Full agent-let JSON schema

**Example Resource Read:**

Request:
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "resources/read",
  "params": {
    "uri": "system-agents://list"
  }
}
```

Response:
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "contents": [
      {
        "uri": "system-agents://list",
        "mimeType": "application/json",
        "text": "[{\"fully_qualified_name\": \"percolate-researcher\", ...}]"
      }
    ]
  }
}
```

### 3. Prompts (Future)

Prompts are **templated instructions** for common tasks.

**Planned Prompts:**
- `analyze-document`: Document analysis workflow
- `create-summary`: Multi-document summarization
- `extract-entities`: Entity extraction from text

## Client Configuration

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "percolate": {
      "url": "http://127.0.0.1:8765/mcp",
      "transport": "http"
    }
  }
}
```

### Custom client implementation

```python
import httpx
import json

async def call_mcp_tool(tool_name: str, arguments: dict):
    async with httpx.AsyncClient() as client:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        response = await client.post(
            "http://127.0.0.1:8765/mcp",
            json=request,
            headers={"Content-Type": "application/json"},
            timeout=60.0
        )

        result = response.json()
        return result["result"]

# Usage
result = await call_mcp_tool(
    "ask_agent",
    {
        "agent_uri": "percolate-researcher",
        "tenant_id": "my-tenant",
        "prompt": "Summarize recent docs"
    }
)
```

## Security Considerations

### Tenant Isolation
- All MCP tools require `tenant_id` parameter
- Resources scoped to tenant automatically
- No cross-tenant data access via MCP

### Authentication
- MCP endpoint is **unauthenticated** in embedded mode
- Production deployments should use:
  - API Gateway with OAuth 2.1
  - JWT validation in middleware
  - Rate limiting per tenant

### Input Validation
- All tool arguments validated with Pydantic
- JSON Schema validation for `create_agent`
- Query length limits on search
- Reject malformed URIs

### Rate Limiting
Production configuration:
- 100 requests/minute per tenant
- 10 concurrent requests per tenant
- 60s timeout on tool execution

## Observability

### OpenTelemetry Instrumentation

All MCP operations are traced:

**Spans:**
- `mcp.tool.call` - Tool invocation
- `mcp.resource.read` - Resource access
- `agent.run` - Agent execution (nested)
- `search.vector` - Vector search (nested)

**Attributes:**
- `mcp.tool.name`: Tool identifier
- `mcp.tenant_id`: Tenant scope
- `mcp.session_id`: Session tracking
- `mcp.user_id`: User identifier

**Metrics:**
- `mcp.tool.duration_ms`: Tool execution time
- `mcp.tool.error_rate`: Error percentage
- `mcp.resource.cache_hit_rate`: Resource caching

### Logging

Structured logs with loguru:

```python
logger.info(
    "MCP tool called",
    tool=tool_name,
    tenant_id=tenant_id,
    duration_ms=duration,
    trace_id=trace_id
)
```

## Testing

### Unit Tests

Test tool logic without server:

```python
# tests/unit/mcp/test_tools.py
from percolate.mcp.tools.agent import ask_agent

async def test_ask_agent_basic():
    result = await ask_agent(
        agent_uri="test-agent",
        tenant_id="test-tenant",
        prompt="Test prompt"
    )

    assert result["status"] == "success"
    assert "response" in result
```

### Integration Tests

Test full MCP protocol:

```python
# tests/integration/mcp/test_mcp_server.py
import httpx

async def test_mcp_call_tool():
    async with httpx.AsyncClient() as client:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "ask_agent",
                "arguments": {
                    "agent_uri": "test-agent",
                    "tenant_id": "test-tenant",
                    "prompt": "Test"
                }
            }
        }

        response = await client.post(
            "http://127.0.0.1:8765/mcp",
            json=request
        )

        assert response.status_code == 200
        result = response.json()
        assert "result" in result
```

Run tests:
```bash
# Unit tests (fast, no server needed)
uv run pytest tests/unit/mcp/

# Integration tests (requires running server)
uv run percolate serve &
uv run pytest tests/integration/mcp/
```

## Performance Tuning

### Connection Pooling
```python
# FastAPI app configuration
app = FastAPI(
    lifespan=lifespan,
    timeout=60,
)

# HTTP client pooling
httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=20),
    timeout=httpx.Timeout(60.0)
)
```

### Caching Resources
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def load_agent_schema(agent_uri: str):
    """Cache agent schemas to avoid repeated disk I/O."""
    return read_agent_file(agent_uri)
```

### Async Execution
- All MCP tools are `async def`
- Use `asyncio.gather()` for parallel operations
- Stream large responses with Server-Sent Events (future)

## Error Handling

### Standard Error Codes

Following JSON-RPC 2.0 specification:

| Code | Meaning | Usage |
|------|---------|-------|
| -32700 | Parse error | Invalid JSON |
| -32600 | Invalid request | Missing required fields |
| -32601 | Method not found | Unknown MCP method |
| -32602 | Invalid params | Validation failure |
| -32603 | Internal error | Server-side error |

### Custom Error Codes

| Code | Meaning | Usage |
|------|---------|-------|
| -32000 | Tenant not found | Invalid tenant_id |
| -32001 | Agent not found | Invalid agent_uri |
| -32002 | Rate limit exceeded | Too many requests |
| -32003 | Timeout | Tool execution timeout |

### Error Response Format

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32602,
    "message": "Invalid params: tenant_id is required",
    "data": {
      "field": "tenant_id",
      "reason": "Field required"
    }
  }
}
```

## Future Enhancements

### Streaming Responses
Use Server-Sent Events for long-running operations:
```python
@mcp.tool()
async def ask_agent_stream(agent_uri: str, prompt: str):
    """Stream agent response as it generates."""
    async for chunk in agent.run_stream(prompt):
        yield {"type": "text", "text": chunk}
```

### Batch Operations
Execute multiple tools in one request:
```python
{
  "method": "tools/call_batch",
  "params": {
    "calls": [
      {"name": "search_knowledge_base", "arguments": {...}},
      {"name": "lookup_entity", "arguments": {...}}
    ]
  }
}
```

### Resource Subscriptions
Subscribe to resource changes:
```python
{
  "method": "resources/subscribe",
  "params": {
    "uri": "my-agents://list"
  }
}
```

## References

- [MCP Specification](https://modelcontextprotocol.io/specification)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [Claude Desktop MCP Guide](https://docs.anthropic.com/claude/docs/model-context-protocol)
