"""Agent management MCP tools."""

from typing import Any


async def create_agent(
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
        agent_name: Agent identifier (hyphenated, e.g., 'my-classifier')
        tenant_id: Tenant identifier for scoping
        description: System prompt describing agent purpose
        output_schema: JSON Schema for structured output
        tools: Optional list of MCP tool references

    Returns:
        Creation status and agent URI

    Example:
        >>> result = await create_agent(
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
        agent_uri: Agent identifier ('researcher' or 'user/{tenant}/{name}')
        tenant_id: Tenant identifier for scoping
        prompt: User prompt for agent
        model: Optional model override
        session_id: Optional session for history tracking

    Returns:
        Agent response with usage metrics

    Example:
        >>> result = await ask_agent(
        ...     agent_uri="researcher",
        ...     tenant_id="tenant-123",
        ...     prompt="What is percolate?"
        ... )
        >>> result["status"]
        'success'
    """
    # TODO: Implement agent execution via factory
    raise NotImplementedError("Agent execution not yet implemented")
