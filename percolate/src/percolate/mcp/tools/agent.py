"""Agent management MCP tools."""

import json
from typing import Any

from loguru import logger

from percolate.agents.context import AgentContext
from percolate.agents.factory import create_agent as create_pydantic_agent
from percolate.agents.registry import load_agentlet_schema


async def create_agent(
    ctx: Any,
    agent_name: str,
    tenant_id: str,
    description: str,
    output_schema: dict[str, Any],
    tools: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Create user-defined agent-let.

    Creates a new agent-let schema for the tenant with specified output
    structure and tool access. Agent is stored in tenant-scoped storage.

    Args:
        ctx: MCP context (not used, for compatibility)
        agent_name: Agent identifier (hyphenated, e.g., 'my-classifier')
        tenant_id: Tenant identifier for scoping
        description: System prompt describing agent purpose
        output_schema: JSON Schema for structured output
        tools: Optional list of MCP tool references

    Returns:
        Creation status and agent URI

    Example:
        >>> result = await create_agent(
        ...     ctx=None,
        ...     agent_name="my-classifier",
        ...     tenant_id="tenant-123",
        ...     description="Classifies support tickets",
        ...     output_schema={"properties": {"category": {"type": "string"}}}
        ... )
        >>> result["uri"]
        'user/tenant-123/my-classifier'
    """
    # TODO: Implement agent creation with schema storage
    raise NotImplementedError("Agent creation not yet implemented")


async def ask_agent(
    ctx: Any,
    agent_uri: str,
    tenant_id: str,
    prompt: str,
    model: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Execute agent-let with prompt.

    Loads agent schema, creates Pydantic AI agent, and executes with
    the given prompt. Optionally stores conversation in session history.

    Args:
        ctx: MCP context (not used, for compatibility)
        agent_uri: Agent identifier ('test-agent' or 'user/{tenant}/{name}')
        tenant_id: Tenant identifier for scoping
        prompt: User prompt for agent
        model: Optional model override
        session_id: Optional session for history tracking

    Returns:
        Agent response with usage metrics

    Example:
        >>> result = await ask_agent(
        ...     ctx=None,
        ...     agent_uri="test-agent",
        ...     tenant_id="tenant-123",
        ...     prompt="What is percolate?"
        ... )
        >>> result["status"]
        'success'
    """
    try:
        # Load agent schema
        agent_schema = None

        if agent_uri.startswith("user/"):
            # User agent: user/{tenant_id}/{agent_name}
            parts = agent_uri.split("/")
            if len(parts) != 3:
                return {
                    "status": "error",
                    "error": "User agent URI must be: user/{tenant_id}/{agent_name}",
                }

            owner_tenant, agent_name = parts[1], parts[2]

            # Security: only allow access to own tenant's agents
            if owner_tenant != tenant_id:
                return {
                    "status": "error",
                    "error": "Access denied: can only access your own tenant's agents",
                }

            # TODO: Load from tenant storage
            return {
                "status": "error",
                "error": "User agents not yet implemented - try system agent like 'test-agent'",
            }

        else:
            # System agent - load from schema directory
            agent_schema = load_agentlet_schema(agent_uri)
            if not agent_schema:
                return {
                    "status": "error",
                    "error": f"System agent not found: {agent_uri}",
                }

        # Create agent context
        context = AgentContext(
            tenant_id=tenant_id,
            session_id=session_id,
            agent_schema_uri=agent_uri,
            default_model=model or "anthropic:claude-3-5-sonnet-20241022",
        )

        # Create and run agent
        agent = await create_pydantic_agent(
            context=context,
            agent_schema_override=agent_schema,
            model_override=model,
        )

        result = await agent.run(prompt)

        # Extract model name and usage
        usage = result.usage()
        model_name = "unknown"
        if result.all_messages():
            last_message = result.all_messages()[-1]
            model_name = getattr(last_message, "model_name", "unknown")

        # Format response
        response_output = result.output
        if isinstance(response_output, dict):
            response_content = response_output
        else:
            # If result has a model_dump method (Pydantic model), use it
            response_content = response_output.model_dump() if hasattr(response_output, "model_dump") else str(response_output)

        return {
            "status": "success",
            "agent_uri": agent_uri,
            "response": response_content,
            "model": model_name,
            "usage": {
                "input_tokens": usage.input_tokens if usage else 0,
                "output_tokens": usage.output_tokens if usage else 0,
            },
        }

    except Exception as e:
        logger.error(f"Failed to run agent {agent_uri}: {e}")
        return {"status": "error", "agent_uri": agent_uri, "error": str(e)}
