"""Agent-let evaluation router.

Provides REST API for executing agent-lets with support for custom headers
to pass tenant context, session tracking, and model overrides.
"""

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field
from loguru import logger

from percolate.mcp.tools.agent import ask_agent


router = APIRouter(prefix="/v1/agents", tags=["agents"])


class AgentEvalRequest(BaseModel):
    """Request body for agent evaluation."""

    agent_uri: str = Field(description="Agent URI (e.g., 'percolate-test-agent')")
    prompt: str = Field(description="User prompt for the agent")
    model: str | None = Field(default=None, description="Optional model override")


class AgentEvalResponse(BaseModel):
    """Response from agent evaluation."""

    status: str = Field(description="Status: 'success' or 'error'")
    agent_uri: str = Field(description="Agent URI that was executed")
    response: dict | str = Field(description="Agent's structured output or error message")
    model: str | None = Field(default=None, description="Model used for generation")
    usage: dict | None = Field(default=None, description="Token usage metrics")
    error: str | None = Field(default=None, description="Error message if status is 'error'")


@router.post("/eval", response_model=AgentEvalResponse)
async def evaluate_agent(
    body: AgentEvalRequest,
    request: Request,
    x_tenant_id: str = Header(default="default", alias="X-Tenant-Id"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    """
    Evaluate an agent-let with a prompt.

    Uses the same underlying `ask_agent` function as the MCP tool and CLI command,
    ensuring consistent behavior across all invocation methods.

    Optional Headers:
    | Header              | Description                          |
    |---------------------|--------------------------------------|
    | X-Tenant-Id         | Tenant identifier (default: "default") |
    | X-Session-Id        | Session/chat identifier for history   |
    | X-User-Id           | User identifier                       |

    Request Body:
    | Field      | Type   | Description                         |
    |------------|--------|-------------------------------------|
    | agent_uri  | string | Agent URI (e.g., 'percolate-test-agent') |
    | prompt     | string | User prompt for the agent           |
    | model      | string | Optional model override             |

    Returns:
        AgentEvalResponse with structured output and usage metrics

    Example:
        ```bash
        curl -X POST http://localhost:8000/v1/agents/eval \
          -H "Content-Type: application/json" \
          -H "X-Tenant-Id: tenant-123" \
          -d '{
            "agent_uri": "percolate-test-agent",
            "prompt": "What is 2+2?"
          }'
        ```
    """
    logger.info(f"Agent eval request: {body.agent_uri} from tenant={x_tenant_id}")

    # Call the same ask_agent function used by MCP and CLI
    result = await ask_agent(
        ctx=None,
        agent_uri=body.agent_uri,
        tenant_id=x_tenant_id,
        prompt=body.prompt,
        model=body.model,
        session_id=x_session_id,
    )

    # Convert to response model
    return AgentEvalResponse(**result)
