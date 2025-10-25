"""Example FastAPI integration with agent-let framework.

This demonstrates how to:
1. Parse context headers from HTTP requests
2. Create agents with context
3. Execute agents and return structured results
4. Handle streaming responses (future)

Based on carrier MCP server patterns.
"""

import asyncio
from typing import Any

from fastapi import FastAPI, Header, Request
from pydantic import BaseModel

# Import agent framework (adjust path as needed)
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from agents import AgentContext, create_agent


app = FastAPI(title="Percolate-Rocks Agent API")


class AgentRequest(BaseModel):
    """Request body for agent execution."""
    agent_uri: str
    prompt: str
    model: str | None = None


class AgentResponse(BaseModel):
    """Response from agent execution."""
    result: dict[str, Any]
    usage: dict[str, int] | None = None
    trace_id: str | None = None


@app.post("/v1/agents/ask")
async def ask_agent(
    body: AgentRequest,
    request: Request,
    x_tenant_id: str = Header(default="default", alias="X-Tenant-ID"),
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
    x_device_id: str | None = Header(default=None, alias="X-Device-ID"),
    x_model_name: str | None = Header(default=None, alias="X-Model-Name"),
    x_db_path: str | None = Header(default=None, alias="X-DB-Path"),
) -> AgentResponse:
    """Execute an agent-let with context from headers.

    Headers:
        X-Tenant-ID: Tenant identifier for data isolation (required)
        X-User-ID: User identifier (optional)
        X-Session-ID: Session identifier for chat history (optional)
        X-Device-ID: Device identifier (optional)
        X-Model-Name: Override default model (optional)
        X-DB-Path: Path to percolate-rocks database (optional)

    Body:
        agent_uri: Agent schema URI (e.g., 'researcher', 'test-agent')
        prompt: User prompt/question
        model: Model override (optional, can also use X-Model-Name header)

    Returns:
        Structured result from agent execution with usage metrics

    Example:
        ```bash
        curl -X POST http://localhost:8000/v1/agents/ask \
          -H "Content-Type: application/json" \
          -H "X-Tenant-ID: tenant-123" \
          -H "X-Session-ID: session-abc" \
          -d '{
            "agent_uri": "test-agent",
            "prompt": "What is percolate-rocks?"
          }'
        ```
    """
    # Extract context from headers
    context = AgentContext(
        tenant_id=x_tenant_id,
        user_id=x_user_id,
        session_id=x_session_id,
        device_id=x_device_id,
        default_model=x_model_name or "claude-sonnet-4.5",
        agent_schema_uri=body.agent_uri,
        db_path=x_db_path,
    )

    # Or use the from_headers() helper:
    # context = AgentContext.from_headers(
    #     headers=dict(request.headers),
    #     tenant_id=x_tenant_id
    # )
    # context.agent_schema_uri = body.agent_uri

    # Create agent with context
    agent = await create_agent(
        context=context,
        model_override=body.model,  # Override from request body if provided
    )

    # Execute agent
    result = await agent.run(body.prompt)

    # Return structured response
    return AgentResponse(
        result=result.data.model_dump() if hasattr(result, 'data') else {"response": str(result)},
        usage={
            "prompt_tokens": getattr(result, "usage", {}).get("input_tokens", 0),
            "completion_tokens": getattr(result, "usage", {}).get("output_tokens", 0),
        } if hasattr(result, "usage") else None,
        trace_id=None,  # TODO: Add OpenTelemetry trace_id when implemented
    )


@app.get("/v1/agents/list")
async def list_agents(
    x_tenant_id: str = Header(default="default", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List available agent-lets for this tenant.

    Returns both system agent-lets (available to all tenants) and
    user agent-lets (specific to this tenant).

    TODO: Implement once percolate-rocks database integration is ready.
    """
    # TODO: Query percolate-rocks for agent-lets
    # from agents.registry import list_agentlets
    # agents = list_agentlets(tenant_id=x_tenant_id)

    # PLACEHOLDER: Return static list
    return {
        "system_agents": [
            {"uri": "test-agent", "name": "Test Agent", "description": "Test agent for validation"},
            {"uri": "researcher", "name": "Research Agent", "description": "Research and knowledge synthesis"},
        ],
        "user_agents": [],
        "note": "TODO: Implement percolate-rocks database query for dynamic agent discovery"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "percolate-rocks-agent-api"}


# Example usage
if __name__ == "__main__":
    import uvicorn

    print("Starting Percolate-Rocks Agent API on http://localhost:8000")
    print("\nExample request:")
    print("""
    curl -X POST http://localhost:8000/v1/agents/ask \\
      -H "Content-Type: application/json" \\
      -H "X-Tenant-ID: tenant-123" \\
      -d '{
        "agent_uri": "test-agent",
        "prompt": "What is the capital of France?"
      }'
    """)

    uvicorn.run(app, host="0.0.0.0", port=8000)
